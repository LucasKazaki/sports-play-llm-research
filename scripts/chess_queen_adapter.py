"""Native Torch Queen candidate, with explicit local assets and no move fallback.

Board conditioning follows queen-project/queen@c372da22 (Apache-2.0). Only
audited, hash-pinned local source modules execute. No trust_remote_code, vLLM,
engine assistance, network inference, or model loading occurs on import.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import sys
import time
import types

import chess

ROOT=Path(__file__).resolve().parents[1]
MODEL_REVISION='5027687fac08b64b2403b13aca5b198e68294fe9'
SOURCE_REVISION='c372da22ca75e95c3c79bee8a83c220fc54d0dcb'
MODEL_ID='princeton-nlp/queen_pawn-8'
FROZEN_VOCAB=128256
GENERATION_MODES=('no_cache','cached')
PRECISION_PROFILES=('default_sdpa','math_sdpa_fp32_reduction')
DEFAULT_ASSETS=ROOT/'data/private/chess-queen-v1/pawn-8'
MANIFEST=ROOT/'experiments/chess-queen-v1/asset-manifest.json'
SOURCE_MANIFEST=ROOT/'experiments/chess-queen-v1/source-manifest.json'
FIELDS=re.compile(r'(?ms)^(?P<name>ANALYSIS|BEST_MOVE|CRITICAL_LINE|PROMISING_MOVES|EVALUATION):\s*(?P<body>.*?)(?=^(?:ANALYSIS|BEST_MOVE|CRITICAL_LINE|PROMISING_MOVES|EVALUATION):|\Z)')
MOVE=re.compile(r'<PIECE_(?P<side>[MO])(?P<piece>[PNBRQK])>\s*<SQUARE_(?P<source>\d+)>\s*(?:<PIECE_(?P<victim_side>[MO])(?P<victim>[PNBRQK])>\s*)?<SQUARE_(?P<target>\d+)>(?:<PIECE_(?P<promotion_side>[MO])(?P<promotion>[QRBN])>)?')
PIECES={symbol:chess.PIECE_SYMBOLS.index(symbol.lower()) for symbol in 'PNBRQK'}


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024**2),b''):value.update(chunk)
    return value.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def board_for(fen):
    if type(fen) is not str or len(fen)>256 or len(fen.split())!=6:
        raise ValueError('A complete six-field standard FEN is required.')
    board=chess.Board(fen,chess960=False)
    if not board.is_valid():raise ValueError('Invalid standard chess board.')
    return board


def input_packet(value):
    """Reject future/evaluator fields before loading or calling a model."""
    if type(value) is not dict or set(value)-{'fen','history','selected_uci'}:
        raise ValueError('Only current FEN, prior FEN history and a selected move are allowed.')
    board=board_for(value.get('fen'))
    history=value.get('history',[])
    if type(history) is not list or len(history)>512:
        raise ValueError('History must be at most512 prior FENs, excluding the current board.')
    previous=[board_for(fen) for fen in history]
    # Do not accept future boards, disjoint games, duplicate states, or arbitrary
    # claimed past context. Every adjacent state must be a single legal move.
    replay=previous[0].copy() if previous else board.copy()
    for after in [*previous[1:],board] if previous else []:
        if replay.is_game_over(claim_draw=False):raise ValueError('History continues after game over.')
        matching=[]
        for move in replay.legal_moves:
            successor=replay.copy();successor.push(move)
            if successor.fen()==after.fen():matching.append(move)
        if len(matching)!=1:raise ValueError('Prior FENs must form one legally consecutive history.')
        replay.push(matching[0])
    selected=value.get('selected_uci')
    if selected is not None:
        if type(selected) is not str or not re.fullmatch(r'[a-h][1-8][a-h][1-8][qrbn]?',selected):
            raise ValueError('Selected move must be ordinary UCI.')
        if chess.Move.from_uci(selected) not in replay.legal_moves or replay.is_game_over(claim_draw=False):
            raise ValueError('Selected move must be legal in a nonterminal current board.')
    packet={'fen':board.fen(),'history':[item.fen() for item in previous]}
    if selected is not None:packet['selected_uci']=selected
    return packet,replay


def prompt_for(packet):
    if 'selected_uci' not in packet:
        return 'Analyze the position carefully and find the best move for player.'
    return ('Explain the selected legal move '+packet['selected_uci']+
            ' for player. Describe its purpose and a possible reply. Treat uncertain plans as uncertain.')


def parse_atom(atom,board,pov):
    first,last=int(atom.group('source'))-1,int(atom.group('target'))-1
    if not(0<=first<64 and 0<=last<64):return None,'square_out_of_range'
    origin,target=(first,last) if pov else (first^56,last^56)
    colour=pov if atom.group('side')=='M' else not pov
    piece=board.piece_at(origin)
    if piece!=chess.Piece(PIECES[atom.group('piece')],colour):return None,'mover_mismatch'
    promotion=PIECES.get(atom.group('promotion'))
    if promotion and atom.group('promotion_side')!=atom.group('side'):return None,'promotion_colour_mismatch'
    move=chess.Move(origin,target,promotion=promotion)
    if move not in board.legal_moves or board.is_game_over(claim_draw=False):return move,'illegal_move'
    victim=chess.Piece(chess.PAWN,not board.turn) if board.is_en_passant(move) else board.piece_at(target)
    expected=None if not atom.group('victim') else chess.Piece(PIECES[atom.group('victim')],pov if atom.group('victim_side')=='M' else not pov)
    if victim!=expected:return move,'capture_description_mismatch'
    return move,None


def parse_output(packet,raw_text):
    packet,board=input_packet(packet)
    if type(raw_text) is not str or len(raw_text)>100_000:raise ValueError('Raw output exceeds bounded parser.')
    section_rows=list(FIELDS.finditer(raw_text))
    duplicates={name for name in ('BEST_MOVE','CRITICAL_LINE') if sum(row.group('name')==name for row in section_rows)>1}
    sections={match.group('name'):match.group('body').strip() for match in section_rows}
    best_field=sections.get('BEST_MOVE','')
    atoms=list(MOVE.finditer(best_field))
    if 'BEST_MOVE' in duplicates:best,error=None,'duplicate_best_move_section'
    elif len(atoms)!=1:best,error=None,'missing_or_ambiguous_best_move'
    else:
        remainder=best_field[:atoms[0].start()]+best_field[atoms[0].end():]
        remainder=re.sub(r'<\|im_end\|>\s*\Z','',remainder)
        best,error=(None,'unparsed_best_move_content') if not re.fullmatch(r'[\s*`.,;:()\-\d]*',remainder) else parse_atom(atoms[0],board,board.turn)
    raw_candidate=best
    if len(atoms)==1 and not duplicates and error!='unparsed_best_move_content':
        first,last=int(atoms[0].group('source'))-1,int(atoms[0].group('target'))-1
        if 0<=first<64 and 0<=last<64:
            origin,target=(first,last) if board.turn else (first^56,last^56)
            raw_candidate=chess.Move(origin,target,promotion=PIECES.get(atoms[0].group('promotion')))
    result={'raw_best_field':best_field,'raw_choice_uci':best.uci() if best else None,
            'raw_choice_is_legal':raw_candidate is not None and raw_candidate in board.legal_moves and not board.is_game_over(claim_draw=False),
            'description_valid':error is None,
            'accepted_move_uci':best.uci() if best is not None and error is None else None,
            'move_rejection':error,'move_source':'raw_structured_best' if best is not None and error is None else 'abstention',
            'duplicate_sections':sorted(duplicates),
            'fallback_used':False,'engine_interventions':0,'rule_replacements':0}
    result['raw_choice_uci']=raw_candidate.uci() if raw_candidate else None
    line=sections.get('CRITICAL_LINE','')
    parse_line=re.sub(r'<\|im_end\|>\s*\Z','',line)
    replay=board.copy();steps=[];failure=None;end=0
    if 'CRITICAL_LINE' in duplicates:failure={'ply':1,'reason':'duplicate_critical_line_section'}
    for index,atom in enumerate(MOVE.finditer(parse_line) if failure is None else [],1):
        gap=parse_line[end:atom.start()]
        if not re.fullmatch(r'[\s\d.,;:()\-–→>*]*',gap):
            failure={'ply':index,'reason':'unparsed_line_content','raw':gap};break
        move,reason=parse_atom(atom,replay,board.turn)
        step={'ply':index,'raw':atom.group(0),'raw_uci':move.uci() if move else None,'legal':reason is None,'error':reason}
        if reason is not None:
            failure=step;steps.append(step);break
        step['san']=replay.san(move);replay.push(move);step['fen_after']=replay.fen();steps.append(step)
        end=atom.end()
        if replay.is_game_over(claim_draw=False):break
    if failure is None and not re.fullmatch(r'[\s\d.,;:()\-–→>*]*',parse_line[end:]):
        failure={'ply':len(steps)+1,'reason':'unparsed_line_content','raw':parse_line[end:]}
    if failure is None and not steps and not replay.is_game_over(claim_draw=False):
        failure={'ply':1,'reason':'missing_or_empty_critical_line'}
    result['critical_line']={'raw':line,'steps':steps,'failure':failure,
        'legal_prefix_plies':sum(step['legal'] for step in steps),'terminal':replay.is_game_over(claim_draw=False),
        'scope':'Legality checked only. Engine agreement and strategic quality are not measured.'}
    return result


def verify_files(root,records):
    root=Path(root).resolve()
    for name,record in records.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Manifest path escapes its root.')
        if not path.is_file() or path.stat().st_size!=record['bytes'] or digest(path)!=record['sha256']:
            raise ValueError('Pinned local file mismatch: '+name)


def verify_assets(model_dir=DEFAULT_ASSETS,source_root=None):
    assets,source=read_json(MANIFEST),read_json(SOURCE_MANIFEST)
    if assets['revision']!=MODEL_REVISION or source['revision']!=SOURCE_REVISION:raise ValueError('Unexpected pinned revision.')
    source_root=Path(source_root or source['checkout'])
    verify_files(model_dir,assets['files']);verify_files(source_root,source['files'])
    return source_root,assets,source


def import_audited_source(source_root):
    """Bypass broad upstream package initializers; import only pinned modules."""
    source_root=Path(source_root).resolve()
    for package in ('models','utils'):
        existing=sys.modules.get(package)
        existing_paths=list(getattr(existing,'__path__',[])) if existing is not None else []
        if existing is not None and (not existing_paths or not all(Path(path).resolve().is_relative_to(source_root) for path in existing_paths)):
            raise RuntimeError('Source namespace already belongs to another checkout; use a separate process.')
        if existing is None:
            module=types.ModuleType(package);module.__path__=[str(source_root/package)];sys.modules[package]=module
    modules={name:importlib.import_module(name) for name in
        ('models.encoder','models.flamingo','models.adapters.smollm','utils.lc0_planes','utils.utils','utils.translate_helpers')}
    return modules


def board_conditioning_hooks(decoder,bridges,encoded):
    """Match Flamingo's pre-layer insertion while keeping stock decoder KV cache.

    Callers must remove every returned handle after the request. An exception
    during installation also removes earlier handles, preventing stale boards.
    """
    if len(bridges)!=16 or len(decoder.model.layers)<32:raise ValueError('Expected16bridges and at least32decoder layers.')
    handles=[]
    try:
        for i,bridge in enumerate(bridges):
            def condition(module,args,kwargs,bridge=bridge,i=i):
                if args:return (bridge(args[0],encoded[:,i]),*args[1:]),kwargs
                if 'hidden_states' not in kwargs:raise ValueError('Decoder layer received no hidden state.')
                return args,{**kwargs,'hidden_states':bridge(kwargs['hidden_states'],encoded[:,i])}
            handles.append(decoder.model.layers[2*i].register_forward_pre_hook(condition,with_kwargs=True))
    except Exception:
        for handle in handles:handle.remove()
        raise
    return handles


def materialize_pinned_module(torch,factory,state_path,device,dtype):
    """Allocate only target storage; copy restricted mapped weights strictly.

    Meta initialization prevents a full temporary CPU FP32 random module. Set
    floating dtype while still meta, then allocate exactly the target tensors.
    assign=False preserves that device/dtype while copying the pinned values.
    """
    with torch.device('meta'):
        module=factory()
    module.to(dtype=dtype)
    module.to_empty(device=device)
    if Path(state_path).suffix=='.safetensors':
        from safetensors.torch import load_file
        state=load_file(str(state_path),device='cpu')
    else:
        state=torch.load(state_path,map_location='cpu',weights_only=True,mmap=True)
    module.load_state_dict(state,strict=True,assign=False)
    del state
    if any(tensor.is_meta for tensor in [*module.parameters(),*module.buffers()]):
        raise ValueError('Pinned module contains unmaterialized tensors.')
    return module


@contextmanager
def precision_context(torch,profile):
    """Scoped settings for one isolated worker; restore even after failure."""
    if profile not in PRECISION_PROFILES:raise ValueError('Unknown precision profile.')
    if profile=='default_sdpa':
        yield
        return
    cuda=torch.backends.cuda
    old_bf16=cuda.matmul.allow_bf16_reduced_precision_reduction
    old_tf32=cuda.matmul.allow_tf32
    old_math=cuda.fp16_bf16_reduction_math_sdp_allowed()
    try:
        cuda.matmul.allow_bf16_reduced_precision_reduction=False
        cuda.matmul.allow_tf32=False
        cuda.allow_fp16_bf16_reduction_math_sdp(False)
        with torch.nn.attention.sdpa_kernel([torch.nn.attention.SDPBackend.MATH]):
            yield
    finally:
        cuda.matmul.allow_bf16_reduced_precision_reduction=old_bf16
        cuda.matmul.allow_tf32=old_tf32
        cuda.allow_fp16_bf16_reduction_math_sdp(old_math)


class NativeQueen:
    def __init__(self,model_dir=DEFAULT_ASSETS,source_root=None,device='cpu',guard=lambda:None):
        if device not in ('cpu','cuda'):raise ValueError('Choose an explicit CPU or CUDA device.')
        self.model_dir=Path(model_dir);self.source_root=source_root;self.device=device;self.guard=guard
        self.model=self.encoder=self.tokenizer=self.modules=self.torch=self.bridges=None

    def load(self):
        if self.model is not None:return
        source_root,self.assets,self.source=verify_assets(self.model_dir,self.source_root)
        self.guard()
        import torch
        from transformers import AutoTokenizer,AutoModelForCausalLM
        self.torch=torch;torch.set_num_threads(4)
        modules=import_audited_source(source_root)
        dtype=torch.bfloat16 if self.device=='cuda' else torch.float32
        decoder=AutoModelForCausalLM.from_pretrained(self.model_dir,local_files_only=True,trust_remote_code=False,
            dtype=dtype,device_map=self.device,attn_implementation='sdpa',use_safetensors=True)
        if decoder.config.model_type!='smollm3' or decoder.config.vocab_size!=128333:
            raise ValueError('Unexpected Queen decoder contract.')
        bridges=materialize_pinned_module(torch,
            lambda:torch.nn.ModuleList([modules['models.flamingo'].DenseXAttn(1024,2048) for _ in range(16)]),
            self.model_dir/'xattn.pt',self.device,dtype)
        decoder.eval().requires_grad_(False);bridges.eval().requires_grad_(False);self.guard()
        # The LC0 model stores its weights as buffers. In this Transformers
        # release from_pretrained(dtype=...) leaves those FP32 buffers intact;
        # materialize them directly in the target dtype without a CPU model.
        encoder_module=modules['models.encoder']
        encoder_config=encoder_module.Lc0Bt4HFConfig.from_pretrained(self.model_dir/'lc0',local_files_only=True)
        encoder=materialize_pinned_module(torch,lambda:encoder_module.Lc0Bt4HFModel(encoder_config),
            self.model_dir/'lc0/model.safetensors',self.device,dtype)
        encoder.eval().requires_grad_(False)
        tokenizer=AutoTokenizer.from_pretrained(self.model_dir,local_files_only=True,trust_remote_code=False)
        if len(tokenizer)!=128333:raise ValueError('Queen tokenizer size differs from pinned decoder.')
        self.guard()
        self.model,self.encoder,self.tokenizer,self.modules,self.bridges=decoder,encoder,tokenizer,modules,bridges

    def generate(self,value,max_new_tokens=192,maximum_seconds=180,temperature=0.0,seed=20260823,
                 generation_mode='no_cache',precision_profile='math_sdpa_fp32_reduction'):
        packet,board=input_packet(value)
        if type(max_new_tokens) is not int or not 1<=max_new_tokens<=1024:raise ValueError('Token budget must be1..1024.')
        if not 1<=maximum_seconds<=600 or not math.isfinite(temperature) or not 0<=temperature<=2:
            raise ValueError('Use a bounded deadline and temperature in0..2.')
        if generation_mode not in GENERATION_MODES or precision_profile not in PRECISION_PROFILES:
            raise ValueError('Choose an explicit supported generation mode and precision profile.')
        started=time.monotonic();generated=[];finish='token_limit';raw='';decode_started=None;first_token_seconds=None
        record={'schema':'chess.queen-native-candidate.v1','input':packet,'prompt':prompt_for(packet),
            'model_id':MODEL_ID,'model_revision':MODEL_REVISION,'source_revision':SOURCE_REVISION,
            'settings':{'device':self.device,'max_new_tokens':max_new_tokens,'maximum_seconds':maximum_seconds,
                        'temperature':temperature,'seed':seed,'top_k':20,'top_p':.95,'use_kv_cache':generation_mode=='cached',
                        'generation_mode':generation_mode,'precision_profile':precision_profile,
                        'backend':'stock SmolLM3 with pinned16pre-layer board cross-attention hooks; '+generation_mode+'; '+precision_profile},
            'no_forward_input_audit':{'passed':True,'allowed_fields':sorted(packet),'engine_evaluation_or_pv_input':False,
                                     'selected_move_supplied':'selected_uci' in packet},
            'status':'not_run','raw_text':'','decoded_text':'',
            'limitations':['Native Torch candidate port; not a reproduction of published H100/vLLM strength.',
                          'Generated explanations are unverified model output, not accepted board facts.',
                          'No random legal fallback, no engine move replacement, no claim of tutor quality.']}
        record['input_sha256']=hashlib.sha256(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        record['prompt_sha256']=hashlib.sha256(record['prompt'].encode()).hexdigest()
        record['adapter_sha256']=digest(Path(__file__))
        record['history_mode']='validated prior boards' if packet['history'] else 'FEN only; upstream synthesizes missing history planes'
        if board.is_game_over(claim_draw=False):
            record.update(status='terminal',finish_reason='game_over');return record
        try:
            self.load();torch=self.torch
            record['asset_manifest_sha256']=digest(MANIFEST)
            record['source_manifest_sha256']=digest(SOURCE_MANIFEST)
            self.guard()
            prompt_ids=self.tokenizer.apply_chat_template([{'role':'user','content':record['prompt']}],
                tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)
            if len(prompt_ids)+max_new_tokens>2304:raise ValueError('Prompt exceeds the declared context budget.')
            ids=torch.tensor([prompt_ids],dtype=torch.long,device=self.device)
            random=torch.Generator(device=self.device).manual_seed(seed)
            dtype=next(self.model.parameters()).dtype
            with torch.inference_mode(),precision_context(torch,precision_profile):
                planes=self.modules['utils.lc0_planes'].encode_fen_batch([packet['fen']],[packet['history']]).to(self.device)
                encoded=self.modules['utils.utils'].encode_planes(self.encoder,planes,dtype,pov=True)
                if tuple(encoded.shape)!=(1,16,64,1024) or not torch.isfinite(encoded).all():
                    raise ValueError('Encoder conditioning is not finite (1,16,64,1024).')
                self.guard()
                stop=self.tokenizer.convert_tokens_to_ids('<|im_end|>')
                handles=board_conditioning_hooks(self.model,self.bridges,encoded)
                try:
                    past=None;current=ids;attention=torch.ones_like(ids);decode_started=time.monotonic()
                    for _ in range(max_new_tokens):
                        self.guard()
                        if time.monotonic()-started>=maximum_seconds:
                            finish='deadline';break
                        output=self.model(input_ids=current,attention_mask=attention,past_key_values=past,
                            use_cache=generation_mode=='cached',logits_to_keep=1)
                        logits=output.logits[0,-1].float()
                        past=output.past_key_values if generation_mode=='cached' else None
                        if not torch.isfinite(logits).all():raise ValueError('Nonfinite native decoder logits.')
                        if temperature==0:token=int(logits.argmax())
                        else:
                            scores=logits/temperature
                            top=torch.topk(scores,20).values[-1];scores=scores.masked_fill(scores<top,float('-inf'))
                            ordered,indices=scores.sort(descending=True);remove=ordered.softmax(-1).cumsum(-1)>.95
                            remove[1:]=remove[:-1].clone();remove[0]=False
                            scores[indices[remove]]=float('-inf')
                            token=int(torch.multinomial(scores.softmax(-1),1,generator=random))
                        generated.append(token)
                        if first_token_seconds is None:first_token_seconds=time.monotonic()-decode_started
                        if token==stop:finish='eos';break
                        next_token=torch.tensor([[token]],device=self.device,dtype=torch.long)
                        current=next_token if generation_mode=='cached' else torch.cat((current,next_token),dim=1)
                        attention=torch.cat((attention,torch.ones_like(next_token)),dim=1)
                finally:
                    for handle in handles:handle.remove()
            raw=self.tokenizer.decode(generated,skip_special_tokens=False)
            record.update(status='completed' if finish=='eos' else 'partial',raw_text=raw,
                decoded_text=self.modules['utils.translate_helpers'].Translator(board.turn).decode_absolute(raw),
                finish_reason=finish,generated_tokens=generated,parsed=parse_output(packet,raw))
        except Exception as error:
            if self.tokenizer is not None:
                raw=self.tokenizer.decode(generated,skip_special_tokens=False)
            record.update(status='failed',error=type(error).__name__+': '+str(error),raw_text=raw,generated_tokens=generated,finish_reason='error')
        record['elapsed_seconds']=round(time.monotonic()-started,3)
        if decode_started is not None:
            decode_seconds=time.monotonic()-decode_started
            record['generation_timing']={'decode_seconds':decode_seconds,'first_token_seconds':first_token_seconds,
                'tokens_per_decode_second':len(generated)/decode_seconds if decode_seconds else None,
                'scope':'Includes per-token resource guard and output parsing; excludes model load and board encoding.'}
        if self.torch is not None and self.device=='cuda':
            try:
                record['peak_cuda_allocated_bytes']=self.torch.cuda.max_memory_allocated()
                record['peak_cuda_reserved_bytes']=self.torch.cuda.max_memory_reserved()
                record['cuda_peak_scope']='This worker process including loading; allocator counters exclude some driver allocations.'
            except Exception as error:
                record['cuda_peak_error']=type(error).__name__+': '+str(error)
        return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,default=DEFAULT_ASSETS)
    parser.add_argument('--source-root',type=Path)
    parser.add_argument('--input',type=Path,help='JSON current-board packet; no evaluator fields.')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--max-tokens',type=int,default=192)
    parser.add_argument('--maximum-seconds',type=float,default=180)
    parser.add_argument('--temperature',type=float,default=0)
    parser.add_argument('--generation-mode',choices=GENERATION_MODES,default='no_cache')
    parser.add_argument('--precision-profile',choices=PRECISION_PROFILES,default='math_sdpa_fp32_reduction')
    parser.add_argument('--preflight',action='store_true',help='Verify assets only; never import or run pretrained models.')
    args=parser.parse_args()
    if args.out and args.out.exists():raise ValueError('Receipt is create-only; select a new output path.')
    if args.preflight:
        source,assets,_=verify_assets(args.model_dir,args.source_root)
        result={'status':'pinned_assets_verified','source_root':str(source),'model_revision':assets['revision'],'pretrained_forwards':0}
    else:
        if not args.input:parser.error('--input is required unless using --preflight')
        if not args.out:parser.error('--out is required to retain every inference response')
        from chess_native_resources import windows_sample,reasons,Policy,GIB
        policy=Policy(start_physical_available_bytes=6*GIB,start_commit_headroom_bytes=10*GIB,
                      start_gpu_free_bytes=10*GIB,stop_physical_available_bytes=4*GIB,stop_commit_headroom_bytes=6*GIB)
        first=True
        def guard():
            nonlocal first
            sample=windows_sample();issues=reasons(sample,policy,'start' if first else 'running');first=False
            if issues:raise RuntimeError('resource reserve: '+','.join(issues))
        result=NativeQueen(args.model_dir,args.source_root,args.device,guard).generate(read_json(args.input),
            args.max_tokens,args.maximum_seconds,args.temperature,generation_mode=args.generation_mode,
            precision_profile=args.precision_profile)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['status'] in ('completed','terminal','pinned_assets_verified') else 2)


if __name__=='__main__':main()
