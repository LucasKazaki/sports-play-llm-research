"""CPU-only contracts; no pretrained model, encoder, engine, or GPU forward."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import chess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('queen_adapter',ROOT/'scripts/chess_queen_adapter.py')
queen=importlib.util.module_from_spec(spec);spec.loader.exec_module(queen)


def test_current_only_packet_rejects_every_evaluator_field():
    packet={'fen':chess.STARTING_FEN}
    actual,board=queen.input_packet(packet)
    assert actual=={'fen':chess.STARTING_FEN,'history':[]}
    assert board.fen()==chess.STARTING_FEN
    for key in ['pv','post_fen','solution','theme','expected_answer','engine','annotation','future_moves']:
        with pytest.raises(ValueError):queen.input_packet({**packet,key:'forbidden'})


def test_prior_history_must_replay_and_selected_move_must_be_legal():
    board=chess.Board();history=[board.fen()];board.push_uci('e2e4')
    packet,replay=queen.input_packet({'fen':board.fen(),'history':history,'selected_uci':'e7e5'})
    assert len(replay.move_stack)==1
    assert packet['selected_uci']=='e7e5'
    with pytest.raises(ValueError):queen.input_packet({'fen':board.fen(),'history':[board.fen()]})
    with pytest.raises(ValueError):queen.input_packet({'fen':chess.STARTING_FEN,'history':history})
    with pytest.raises(ValueError):queen.input_packet({'fen':board.fen(),'selected_uci':'e7e4'})
    with pytest.raises(ValueError):queen.input_packet({'fen':board.fen(),'history':[chess.STARTING_FEN]*513})


def test_model_prompts_contain_no_solution_or_successor():
    packet,_=queen.input_packet({'fen':chess.STARTING_FEN,'selected_uci':'e2e4'})
    prompt=queen.prompt_for(packet)
    assert 'e2e4' in prompt and 'reply' in prompt
    assert '4P3' not in prompt


def test_white_structured_best_and_three_half_moves_are_replayed():
    raw='BEST_MOVE: <PIECE_MP><SQUARE_13><SQUARE_29>\nCRITICAL_LINE: 1. <PIECE_MP><SQUARE_13><SQUARE_29> <PIECE_OP><SQUARE_53><SQUARE_37> 2. <PIECE_MN><SQUARE_7><SQUARE_22>\nEVALUATION: equal'
    result=queen.parse_output({'fen':chess.STARTING_FEN},raw)
    assert result['accepted_move_uci']=='e2e4'
    assert result['fallback_used'] is False and result['engine_interventions']==0
    assert [step['raw_uci'] for step in result['critical_line']['steps']]==['e2e4','e7e5','g1f3']
    assert result['critical_line']['legal_prefix_plies']==3


def test_black_pov_square_mapping_is_root_anchored():
    board=chess.Board();board.push_uci('e2e4')
    # Black's e7 is root POV e2=13; e5 is root POV e4=29.
    result=queen.parse_output({'fen':board.fen()},'BEST_MOVE: <PIECE_MP><SQUARE_13><SQUARE_29>')
    assert result['accepted_move_uci']=='e7e5'


@pytest.mark.parametrize('raw,reason',[
    ('BEST_MOVE: <PIECE_MP><SQUARE_13><SQUARE_45>','illegal_move'),
    ('BEST_MOVE: <PIECE_MQ><SQUARE_13><SQUARE_29>','mover_mismatch'),
    ('BEST_MOVE: <PIECE_MP><SQUARE_99><SQUARE_29>','square_out_of_range'),
    ('BEST_MOVE: <PIECE_MP><SQUARE_13><PIECE_OP><SQUARE_29>','capture_description_mismatch'),
    ('ANALYSIS: e4 is a strong move.','missing_or_ambiguous_best_move'),
    ('BEST_MOVE: <PIECE_MP><SQUARE_13><SQUARE_29> <PIECE_MP><SQUARE_12><SQUARE_28>','missing_or_ambiguous_best_move'),
])
def test_raw_bad_best_never_gets_random_rule_or_engine_rescue(raw,reason):
    result=queen.parse_output({'fen':chess.STARTING_FEN},raw)
    assert result['accepted_move_uci'] is None
    assert result['raw_choice_is_legal'] is (reason in ('mover_mismatch','capture_description_mismatch'))
    assert result['description_valid'] is False
    assert result['move_rejection']==reason
    assert result['fallback_used'] is False and result['rule_replacements']==0


def test_critical_line_stops_at_bad_first_move_and_does_not_salvage_later_move():
    raw='CRITICAL_LINE: <PIECE_MP><SQUARE_13><SQUARE_45> <PIECE_MP><SQUARE_12><SQUARE_28>'
    line=queen.parse_output({'fen':chess.STARTING_FEN},raw)['critical_line']
    assert line['legal_prefix_plies']==0
    assert len(line['steps'])==1 and line['failure']['error']=='illegal_move'
    raw='CRITICAL_LINE: <PIECE_MX><SQUARE_13><SQUARE_29> <PIECE_MP><SQUARE_12><SQUARE_28>'
    line=queen.parse_output({'fen':chess.STARTING_FEN},raw)['critical_line']
    assert line['legal_prefix_plies']==0 and line['failure']['reason']=='unparsed_line_content'


def test_duplicate_or_malformed_best_sections_cannot_rescue_earlier_failure():
    valid='<PIECE_MP><SQUARE_13><SQUARE_29>'
    bad='<PIECE_MP><SQUARE_13><SQUARE_45>'
    result=queen.parse_output({'fen':chess.STARTING_FEN},f'BEST_MOVE: {bad}\nBEST_MOVE: {valid}')
    assert result['accepted_move_uci'] is None and result['move_rejection']=='duplicate_best_move_section'
    result=queen.parse_output({'fen':chess.STARTING_FEN},f'BEST_MOVE: <PIECE_MX><SQUARE_13><SQUARE_29> {valid}')
    assert result['accepted_move_uci'] is None and result['move_rejection']=='unparsed_best_move_content'
    result=queen.parse_output({'fen':chess.STARTING_FEN},f'CRITICAL_LINE: {bad}\nCRITICAL_LINE: {valid}')
    assert result['critical_line']['legal_prefix_plies']==0
    assert result['critical_line']['failure']['reason']=='duplicate_critical_line_section'
    assert queen.parse_output({'fen':chess.STARTING_FEN},f'BEST_MOVE: **{valid}**<|im_end|>')['accepted_move_uci']=='e2e4'


def test_critical_line_eos_is_formatting_but_missing_line_is_visible_failure():
    result=queen.parse_output({'fen':chess.STARTING_FEN},'CRITICAL_LINE: <PIECE_MP><SQUARE_13><SQUARE_29><|im_end|>')
    assert result['critical_line']['legal_prefix_plies']==1 and result['critical_line']['failure'] is None
    result=queen.parse_output({'fen':chess.STARTING_FEN},'ANALYSIS: no line supplied')
    assert result['critical_line']['failure']['reason']=='missing_or_empty_critical_line'


def test_capture_en_passant_and_explicit_promotion_tokens():
    ep='4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2'
    result=queen.parse_output({'fen':ep},'BEST_MOVE: <PIECE_MP><SQUARE_37><PIECE_OP><SQUARE_44>')
    assert result['accepted_move_uci']=='e5d6'
    promotion='4k3/P7/8/8/8/8/8/4K3 w - - 0 1'
    assert queen.parse_output({'fen':promotion},'BEST_MOVE: <PIECE_MP><SQUARE_49><SQUARE_57><PIECE_MN>')['accepted_move_uci']=='a7a8n'
    assert queen.parse_output({'fen':promotion},'BEST_MOVE: <PIECE_MP><SQUARE_49><SQUARE_57>')['accepted_move_uci'] is None


def test_terminal_position_never_loads_or_calls_model():
    model=queen.NativeQueen()
    model.load=lambda:pytest.fail('terminal board must not load pretrained model')
    result=model.generate({'fen':'7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'})
    assert result['status']=='terminal' and result['finish_reason']=='game_over'


@pytest.mark.parametrize('mode,lengths,use_cache',[('no_cache',[2,3,4],False),('cached',[2,1,1],True)])
def test_actual_decode_loop_uses_declared_prefix_mode_without_pretrained_weights(mode,lengths,use_cache):
    import torch
    model=queen.NativeQueen(device='cpu');calls=[]
    class Decoder:
        def parameters(self):yield torch.zeros(1)
        def __call__(self,**kwargs):
            calls.append(kwargs)
            logits=torch.full((1,1,10),-100.);logits[0,0,[3,4,9][len(calls)-1]]=100
            return SimpleNamespace(logits=logits,past_key_values='owned-kv')
    model.model=Decoder();model.torch=torch;model.load=lambda:None
    model.tokenizer=SimpleNamespace(apply_chat_template=lambda *a,**k:[1,2],
        convert_tokens_to_ids=lambda token:9,decode=lambda *a,**k:'ANALYSIS: authored CPU software output')
    model.modules={'utils.lc0_planes':SimpleNamespace(encode_fen_batch=lambda *a:torch.zeros(1)),
        'utils.utils':SimpleNamespace(encode_planes=lambda *a,**k:torch.zeros(1,16,64,1024)),
        'utils.translate_helpers':SimpleNamespace(Translator=lambda pov:SimpleNamespace(decode_absolute=lambda raw:raw))}
    original=queen.board_conditioning_hooks;queen.board_conditioning_hooks=lambda *a:[]
    try:
        result=model.generate({'fen':chess.STARTING_FEN,'selected_uci':'e2e4'},max_new_tokens=4,
            generation_mode=mode,precision_profile='default_sdpa')
    finally:queen.board_conditioning_hooks=original
    assert result['status']=='completed' and result['generated_tokens']==[3,4,9]
    assert [call['input_ids'].shape[1] for call in calls]==lengths
    assert all(call['use_cache'] is use_cache for call in calls)
    assert calls[0]['past_key_values'] is None
    assert [call['past_key_values'] for call in calls[1:]]==(['owned-kv']*2 if use_cache else [None]*2)
    assert result['settings']['generation_mode']==mode and result['settings']['use_kv_cache'] is use_cache
    assert result['no_forward_input_audit']['selected_move_supplied'] is True
    assert result['no_forward_input_audit']['engine_evaluation_or_pv_input'] is False
    assert 'engine_input' not in result['no_forward_input_audit']
    timing=result['generation_timing']
    assert timing['tokens_per_decode_second']>0 if timing['decode_seconds'] else timing['tokens_per_decode_second'] is None


def test_precision_context_restores_backend_flags_even_when_forward_fails():
    from contextlib import contextmanager
    math=[True];events=[];matmul=SimpleNamespace(allow_bf16_reduced_precision_reduction=True,allow_tf32=True)
    @contextmanager
    def sdpa(backends):
        assert backends==['math'];events.append('enter');yield;events.append('exit')
    cuda=SimpleNamespace(matmul=matmul,fp16_bf16_reduction_math_sdp_allowed=lambda:math[0],
        allow_fp16_bf16_reduction_math_sdp=lambda value:math.__setitem__(0,value))
    fake=SimpleNamespace(backends=SimpleNamespace(cuda=cuda),
        nn=SimpleNamespace(attention=SimpleNamespace(sdpa_kernel=sdpa,SDPBackend=SimpleNamespace(MATH='math'))))
    with pytest.raises(RuntimeError):
        with queen.precision_context(fake,'math_sdpa_fp32_reduction'):
            assert not matmul.allow_bf16_reduced_precision_reduction and not matmul.allow_tf32 and not math[0]
            raise RuntimeError('authored forward failure')
    assert matmul.allow_bf16_reduced_precision_reduction and matmul.allow_tf32 and math[0]
    assert events==['enter']


def test_installed_precision_context_api_executes_only_cpu_attention_and_restores_flags():
    import torch
    cuda=torch.backends.cuda
    previous=(cuda.matmul.allow_bf16_reduced_precision_reduction,cuda.matmul.allow_tf32,
        cuda.fp16_bf16_reduction_math_sdp_allowed())
    with queen.precision_context(torch,'math_sdpa_fp32_reduction'):
        query=torch.ones(1,1,2,4,device='cpu')
        values=torch.arange(8,dtype=torch.float32,device='cpu').reshape(1,1,2,4)
        result=torch.nn.functional.scaled_dot_product_attention(query,query,values)
        assert result.device.type=='cpu' and torch.equal(result,values.mean(-2,keepdim=True).expand_as(values))
        assert not cuda.matmul.allow_bf16_reduced_precision_reduction and not cuda.matmul.allow_tf32
        assert not cuda.fp16_bf16_reduction_math_sdp_allowed()
    assert previous==(cuda.matmul.allow_bf16_reduced_precision_reduction,cuda.matmul.allow_tf32,
        cuda.fp16_bf16_reduction_math_sdp_allowed())


def test_local_file_bindings_reject_tampering_and_escape(tmp_path):
    path=tmp_path/'source.py';path.write_bytes(b'pass\n')
    records={'source.py':{'bytes':5,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    queen.verify_files(tmp_path,records)
    path.write_bytes(b'evil\n')
    with pytest.raises(ValueError):queen.verify_files(tmp_path,records)
    with pytest.raises(ValueError):queen.verify_files(tmp_path,{'../outside':records['source.py']})


def test_hooks_insert_at_exact_flamingo_layers_and_clean_up():
    class Layer:
        def __init__(self):self.hook=None
        def register_forward_pre_hook(self,hook,with_kwargs):
            assert with_kwargs is True
            self.hook=hook
            return SimpleNamespace(remove=lambda:setattr(self,'hook',None))
    class Encoded:
        def __getitem__(self,item):return item[1]
    layers=[Layer() for _ in range(36)]
    model=SimpleNamespace(model=SimpleNamespace(layers=layers))
    bridges=[lambda hidden,encoder:hidden+encoder+1 for _ in range(16)]
    handles=queen.board_conditioning_hooks(model,bridges,Encoded())
    assert [i for i,layer in enumerate(layers) if layer.hook]==list(range(0,32,2))
    args,kwargs=layers[2].hook(layers[2],(10,),{'other':'unchanged'})
    assert args==(12,) and kwargs=={'other':'unchanged'}
    args,kwargs=layers[4].hook(layers[4],(),{'hidden_states':10})
    assert args==() and kwargs['hidden_states']==13
    for handle in handles:handle.remove()
    assert not any(layer.hook for layer in layers)


def test_partial_hook_installation_failure_removes_prior_board_hooks():
    removed=[]
    class Layer:
        def __init__(self,index):self.index=index
        def register_forward_pre_hook(self,hook,with_kwargs):
            if self.index==4:raise RuntimeError('injected installation failure')
            return SimpleNamespace(remove=lambda:removed.append(self.index))
    model=SimpleNamespace(model=SimpleNamespace(layers=[Layer(i) for i in range(36)]))
    with pytest.raises(RuntimeError):queen.board_conditioning_hooks(model,[object()]*16,object())
    assert removed==[0,2]


def test_meta_materialization_has_no_real_constructor_storage_and_copies_exact_cast_values(tmp_path,monkeypatch):
    import torch
    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__();self.layer=torch.nn.Linear(3,2)
            self.register_buffer('floating',torch.zeros(2))
            self.register_buffer('indices',torch.zeros(2,dtype=torch.int64))
    original=Tiny()
    with torch.no_grad():
        original.layer.weight.copy_(torch.arange(6).reshape(2,3)/7)
        original.layer.bias.copy_(torch.tensor([.1,-.2]))
        original.floating.copy_(torch.tensor([.3,-.4]));original.indices.copy_(torch.tensor([3,7]))
    path=tmp_path/'tiny.pt';torch.save(original.state_dict(),path)
    seen=[];actual_load=torch.load;load_calls=[]
    def factory():
        module=Tiny();seen.extend(t.is_meta for t in [*module.parameters(),*module.buffers()]);return module
    def load(*args,**kwargs):
        load_calls.append(kwargs.copy());return actual_load(*args,**kwargs)
    monkeypatch.setattr(torch,'load',load)
    result=queen.materialize_pinned_module(torch,factory,path,'cpu',torch.bfloat16)
    assert seen and all(seen)
    assert load_calls==[{'map_location':'cpu','weights_only':True,'mmap':True}]
    for name,tensor in result.state_dict().items():
        assert tensor.device.type=='cpu' and not tensor.is_meta
        expected=original.state_dict()[name]
        assert tensor.dtype==(torch.bfloat16 if expected.is_floating_point() else expected.dtype)
        assert torch.equal(tensor,expected.to(tensor.dtype))
    broken=original.state_dict();del broken['layer.bias'];torch.save(broken,path)
    with pytest.raises(RuntimeError,match='Missing key'):
        queen.materialize_pinned_module(torch,factory,path,'cpu',torch.bfloat16)


def test_audited_encoder_materializes_tiny_local_buffers_in_requested_dtype(tmp_path):
    import torch
    source=queen.read_json(queen.SOURCE_MANIFEST);source_root=Path(source['checkout'])
    queen.verify_files(source_root,source['files'])
    module=queen.import_audited_source(source_root)['models.encoder']
    config=module.Lc0Bt4HFConfig(embedding_dense_size=1,embedding_size=4,input_size=112,
        num_encoders=1,num_heads=1,head_dim=4,dff_size=8,smolgen_hidden_channels=1,
        smolgen_hidden_size=1,smolgen_gen_size=1,smolgen_gen_size_per_head=1,
        policy_embedding_size=4,policy_d_model=4,value_embedding_size=4,value_hidden_size=4,
        moves_left_embedding_size=4,moves_left_hidden_size=4)
    original=module.Lc0Bt4HFModel(config)
    for tensor in original.buffers():
        if tensor.is_floating_point():tensor.fill_(.125)
    from safetensors.torch import save_file
    config.to_json_file(tmp_path/'config.json',use_diff=False)
    save_file(original.state_dict(),tmp_path/'model.safetensors')
    loaded_config=module.Lc0Bt4HFConfig.from_pretrained(tmp_path,local_files_only=True)
    observed=[]
    def factory():
        result=module.Lc0Bt4HFModel(loaded_config)
        observed.extend(tensor.is_meta for tensor in result.buffers());return result
    loaded=queen.materialize_pinned_module(torch,factory,tmp_path/'model.safetensors','cpu',torch.bfloat16)
    assert observed and all(observed)
    assert not list(loaded.parameters()) # Pinned encoder stores weights as buffers.
    for name,tensor in loaded.state_dict().items():
        expected=original.state_dict()[name]
        assert tensor.device.type=='cpu' and not tensor.is_meta
        assert tensor.dtype==(torch.bfloat16 if expected.is_floating_point() else expected.dtype)
        assert torch.equal(tensor,expected.to(tensor.dtype))


def worker_module():
    spec=importlib.util.spec_from_file_location('queen_gpu_worker',ROOT/'experiments/chess-queen-v1/gpu_worker.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def parity_module(version):
    spec=importlib.util.spec_from_file_location('queen_parity_'+version,
        ROOT/f'experiments/chess-queen-v1/parity_pretrained_{version}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_parity_v3_changes_only_authorized_running_reserve_and_preserves_numerical_thresholds():
    old,new=parity_module('v2'),parity_module('v3')
    assert new.THRESHOLDS==old.THRESHOLDS and new.FIXTURE==old.FIXTURE and new.SUFFIX==old.SUFFIX
    spec=importlib.util.spec_from_file_location('queen_resources',ROOT/'scripts/chess_native_resources.py')
    resources=importlib.util.module_from_spec(spec);sys.modules[spec.name]=resources;spec.loader.exec_module(resources)
    policy=resources.Policy(**new.RESOURCE_POLICY);gib=resources.GIB
    assert (policy.start_physical_available_bytes,policy.start_commit_headroom_bytes,policy.start_gpu_free_bytes)==(6*gib,10*gib,10*gib)
    assert (policy.stop_physical_available_bytes,policy.stop_commit_headroom_bytes,policy.stop_gpu_free_bytes)==(4*gib,5*gib,gib)
    sample=resources.Sample(32*gib,5*gib,50*gib,44*gib+gib//2,16*gib,2*gib)
    assert resources.reasons(sample,policy,'running')==[]
    assert resources.reasons(sample,resources.Policy(stop_commit_headroom_bytes=6*gib),'running')==['commit_headroom_bytes_below_reserve']
    assert len(new.PRIOR_ATTEMPTS)==2
    for prior in new.PRIOR_ATTEMPTS:
        assert prior['path'].endswith(('-v2-1.json','-v2-2.json')) and len(prior['sha256'])==64


def test_parity_v4_retains_checks_and_binds_actual_exact_hook_observation():
    old,new=parity_module('v3'),parity_module('v4')
    assert new.THRESHOLDS==old.THRESHOLDS and new.FIXTURE==old.FIXTURE and new.SUFFIX==old.SUFFIX
    assert {**old.RESOURCE_POLICY,'stop_commit_headroom_bytes':4*1024**3}==new.RESOURCE_POLICY
    assert new.PRIOR_ATTEMPTS[:2]==old.PRIOR_ATTEMPTS and len(new.PRIOR_ATTEMPTS)==3
    observed=new.PRIOR_NUMERICAL_EVIDENCE
    assert observed['receipt']==new.PRIOR_ATTEMPTS[-1]['path']
    assert observed['encoder_shape']==[1,16,64,1024]
    assert observed['hook_vs_upstream_manual']['max_absolute_error']==0
    assert observed['hook_vs_upstream_manual']['top1_equal'] is True
    assert observed['hook_vs_upstream_manual']['finite'] is True


def test_parity_v5_preserves_thresholds_and_never_relabels_cache_failure_as_success():
    old,new=parity_module('v4'),parity_module('v5')
    assert new.THRESHOLDS==old.THRESHOLDS and new.RESOURCE_POLICY==old.RESOURCE_POLICY
    assert new.PRECISION_PROFILE=='math_sdpa_fp32_reduction'
    assert new.PRIOR_ATTEMPTS[:3]==old.PRIOR_ATTEMPTS and len(new.PRIOR_ATTEMPTS)==4
    row={'finite':True,'top1_equal':True,'cosine_similarity':1.,'max_absolute_error':0.,'mean_absolute_error':0.}
    failed_cache={**row,'max_absolute_error':.546875,'mean_absolute_error':.0868,'cosine_similarity':.9992589}
    canonical,cached=new.qualify(row,[failed_cache,row,row],[row,row,row])
    assert canonical is True and cached is False


def test_short_lived_queen_child_records_same_resource_policy_as_parity_v4(tmp_path,monkeypatch):
    new=parity_module('v4');worker=worker_module()
    spec=importlib.util.spec_from_file_location('queen_child_resources',ROOT/'scripts/chess_native_resources.py')
    resources=importlib.util.module_from_spec(spec);sys.modules[spec.name]=resources;spec.loader.exec_module(resources)
    observed=[]
    class FakeNative:
        def __init__(self,device,guard):
            assert device=='cuda';observed.append(guard.policy)
        def generate(self,value,**settings):
            assert value=={'fen':chess.STARTING_FEN} and settings['temperature']==0
            return {'status':'completed','finish_reason':'eos'}
    monkeypatch.setitem(sys.modules,'chess_queen_adapter',SimpleNamespace(NativeQueen=FakeNative,read_json=lambda path:{'fen':chess.STARTING_FEN}))
    monkeypatch.setitem(sys.modules,'chess_native_resources',resources)
    args=SimpleNamespace(input=tmp_path/'input.json',out=tmp_path/'result.json',cancel=None,max_tokens=8,maximum_seconds=10,
        generation_mode='no_cache',precision_profile='math_sdpa_fp32_reduction')
    assert worker.queen_child(args)==0
    result=json.loads(args.out.read_text())
    assert observed and all(getattr(observed[0],key)==value for key,value in new.RESOURCE_POLICY.items())
    assert all(result['resource_policy'][key]==value for key,value in new.RESOURCE_POLICY.items())
    assert result['resource_samples']==[]


def test_worker_lease_excludes_second_child_and_is_released_after_exit(tmp_path):
    worker=worker_module();lock=tmp_path/'shared.lock';marker=tmp_path/'started.txt'
    first_result=[]
    def first():
        first_result.append(worker.run_worker(['experiments/chess-queen-v1/lease_probe_child.py','--sleep','1.5','--marker',str(marker)],tmp_path/'first.json',maximum_seconds=5,lock_path=lock))
    thread=threading.Thread(target=first);thread.start()
    deadline=time.monotonic()+5
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
    assert marker.exists()
    blocked=worker.run_worker(['experiments/chess-queen-v1/lease_probe_child.py'],tmp_path/'blocked.json',lock_path=lock)
    assert blocked['status']=='busy' and blocked['child_pid'] is None
    thread.join(timeout=8)
    assert first_result[0]['status']=='completed'
    assert first_result[0]['child_exited_before_lease_release'] is True
    after=worker.run_worker(['experiments/chess-queen-v1/lease_probe_child.py'],tmp_path/'after.json',lock_path=lock)
    assert after['status']=='completed'


def test_worker_deadline_terminates_its_owned_child_before_unlock(tmp_path):
    worker=worker_module()
    result=worker.run_worker(['experiments/chess-queen-v1/lease_probe_child.py','--sleep','4'],tmp_path/'deadline.json',maximum_seconds=1,lock_path=tmp_path/'shared.lock')
    assert result['status']=='deadline' and result['child_exited_before_lease_release'] is True


@pytest.mark.skipif(sys.platform!='win32',reason='Windows parent-death/job lifecycle regression')
def test_parent_death_before_job_assignment_never_releases_target_import_gate(tmp_path):
    import ctypes
    from ctypes import wintypes
    receipt=tmp_path/'parent.json';lock=tmp_path/'shared.lock';marker=tmp_path/'target-imported.txt'
    wrapper=subprocess.Popen([sys.executable,str(ROOT/'experiments/chess-queen-v1/lease_probe_parent.py'),
        '--receipt',str(receipt),'--lock',str(lock),'--marker',str(marker)],cwd=ROOT,
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    handle=None
    try:
        deadline=time.monotonic()+6;record={}
        while time.monotonic()<deadline:
            try:record=json.loads(receipt.read_text())
            except (FileNotFoundError,json.JSONDecodeError):pass
            if record.get('status')=='awaiting_job_assignment':break
            time.sleep(.01)
        assert record.get('status')=='awaiting_job_assignment'
        handle=kernel.OpenProcess(0x100000,False,record['child_pid']) # SYNCHRONIZE only
        assert handle
        wrapper.terminate();wrapper.wait(timeout=5)
        assert kernel.WaitForSingleObject(handle,5000)==0
        assert not marker.exists()
        after=worker_module().run_worker(['experiments/chess-queen-v1/lease_probe_child.py'],
            tmp_path/'after.json',maximum_seconds=5,lock_path=lock)
        assert after['status']=='completed'
    finally:
        if wrapper.poll() is None:wrapper.terminate();wrapper.wait(timeout=5)
        if handle:kernel.CloseHandle(handle)


def test_worker_guard_throttles_samples_but_checks_cancel_every_call(tmp_path):
    from dataclasses import dataclass
    @dataclass
    class Sample:value:int=1
    worker=worker_module();now=[0];calls=[];cancel=tmp_path/'cancel.json'
    guard=worker.CooperativeGuard(lambda:(calls.append(now[0]) or Sample()),lambda *args:[],object(),cancel,lambda:now[0])
    for stamp in [0,.1,.5,.99,1.01,1.5,2.02]:now[0]=stamp;guard()
    assert calls==[0,1.01,2.02]
    cancel.write_text('{}')
    with pytest.raises(RuntimeError,match='cancellation'):guard()
