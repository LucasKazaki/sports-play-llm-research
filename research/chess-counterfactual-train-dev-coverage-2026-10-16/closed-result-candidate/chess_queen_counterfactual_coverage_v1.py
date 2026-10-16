"""Descriptive TRAIN/DEV coverage only; no reference files, frameworks or models."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import chess
import chess_queen_adapter as native

ROOT=Path(__file__).resolve().parents[1]
MODES=('free','selected_a','selected_b')
FIELDS={'case_id','group_id','mode','input','response'}
VALUES={chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3,chess.ROOK:5,chess.QUEEN:9,chess.KING:0}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def bound(item):
    path=Path(item['path']);path=path if path.is_absolute()else ROOT/path
    if digest(path)!=item['sha256']:raise ValueError('Pinned file bytes differ: '+str(path))
    return path
def framework_free():
    if any(name in sys.modules for name in('torch','transformers','bitsandbytes','pyarrow')):
        raise RuntimeError('Coverage audit must remain framework/model free')
def distribution(counter,denominator,keys=()):
    counts={str(key):counter.get(key,0)for key in sorted(set(counter)|set(keys),key=str)}
    return {'counts':counts,'denominator':denominator,
        'rates':{key:value/denominator if denominator else None for key,value in counts.items()}}
def board_key(board):return ' '.join(board.fen().split()[:4])
def group_digest(groups):return hashlib.sha256(json.dumps(sorted(groups),separators=(',',':')).encode()).hexdigest()
def overlap_profile(train,development):
    count=len(train&development)
    return {'count':count,'train_distinct_denominator':len(train),'development_distinct_denominator':len(development),
        'train_rate':count/len(train)if train else None,'development_rate':count/len(development)if development else None}


def describe(row):
    if type(row)is not dict or set(row)!=FIELDS:raise ValueError('row_schema')
    if any(type(row[key])is not str or not row[key].strip()for key in('case_id','group_id','mode','response')):
        raise ValueError('missing_or_wrong_type')
    mode=row['mode'];packet=row['input']
    if mode not in MODES:raise ValueError('mode')
    if row['case_id']!=f"queen-counterfactual-v1:{row['group_id']}:{mode}":raise ValueError('case_group_identity')
    expected={'fen'}if mode=='free'else{'fen','selected_uci'}
    if type(packet)is not dict or set(packet)!=expected or any(type(x)is not str or not x for x in packet.values()):
        raise ValueError('input_whitelist_or_type')
    if len(packet['fen'].split())!=6:raise ValueError('six_field_fen')
    try:board=chess.Board(packet['fen'])
    except ValueError:raise ValueError('invalid_fen')from None
    if not board.is_valid()or board.is_game_over(claim_draw=False):raise ValueError('invalid_or_terminal_board')
    sections=[part for part in native.FIELDS.finditer(row['response'])if part['name']=='BEST_MOVE']
    if len(sections)!=1:raise ValueError('unique_target_best')
    atom=native.MOVE.fullmatch(sections[0]['body'].strip())
    if atom is None:raise ValueError('target_atom')
    move,error=native.parse_atom(atom,board,board.turn)
    if error:raise ValueError('target_'+error)
    if mode!='free'and move.uci()!=packet['selected_uci']:raise ValueError('supplied_target_mismatch')
    generator_packet,_=native.input_packet(packet)
    capture=board.is_capture(move);check=board.gives_check(move)
    victim=chess.PAWN if board.is_en_passant(move)else board.piece_type_at(move.to_square)
    after=board.copy(stack=False);after.push(move)
    return {'case_id':row['case_id'],'group_id':row['group_id'],'mode':mode,'board':board,'key':board_key(board),
        'fen':board.fen(),'packet_hash':hashlib.sha256(json.dumps(generator_packet,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'uci':move.uci(),'origin':move.from_square,
        'mover':chess.piece_symbol(board.piece_type_at(move.from_square)).upper(),
        'side':'white'if board.turn else'black','capture':capture,'check':check,
        'victim':chess.piece_symbol(victim).upper()if victim else'none','checkmate':after.is_checkmate(),
        'double_check':len(after.checkers())>=2,'promotion':bool(move.promotion),'castling':board.is_castling(move),
        'en_passant':board.is_en_passant(move),'quiet_immediate':not capture and not check}


def move_profile(rows):
    n=len(rows)
    values={key:distribution(Counter(row[key]for row in rows),n,keys)for key,keys in(
        ('mover',tuple('PNBRQK')),('side',('white','black')),('victim',('none',*'PNBRQ')))}
    values['presentations']=n
    for key in('capture','check','checkmate','double_check','promotion','castling','en_passant','quiet_immediate'):
        count=sum(row[key]for row in rows);values[key]={'count':count,'denominator':n,'rate':count/n if n else None}
    values['king_move_gives_check']={'count':sum(row['mover']=='K'and row['check']for row in rows),'denominator':n,
        'rate':sum(row['mover']=='K'and row['check']for row in rows)/n if n else None}
    return values


def root_profile(rows):
    counters=defaultdict(Counter)
    for row in rows:
        b=row['board'];pieces=list(b.piece_map().values())
        total=sum(VALUES[p.piece_type]for p in pieces)
        nonpawn=sum(VALUES[p.piece_type]for p in pieces if p.piece_type!=chess.PAWN)
        counters['material_points_total'][total]+=1
        counters['nonpawn_material_bin']['0_13'if nonpawn<=13 else'14_38'if nonpawn<=38 else'39_plus']+=1
        counters['nonking_piece_count'][sum(p.piece_type!=chess.KING for p in pieces)]+=1
        counters['material_white_minus_black'][sum(VALUES[p.piece_type]*(1 if p.color else-1)for p in pieces)]+=1
        counters['queen_count'][sum(p.piece_type==chess.QUEEN for p in pieces)]+=1
        counters['side_to_move'][row['side']]+=1
        counters['legal_king_move_count'][sum(b.piece_type_at(m.from_square)==chess.KING for m in b.legal_moves)]+=1
        counters['side_to_move_in_check'][b.is_check()]+=1
    return {key:distribution(value,len(rows))for key,value in counters.items()}


def audit_lines(lines,requested,check=lambda:None):
    valid=[];errors=[];missing=Counter();groups=defaultdict(list);case_ids=[];seen=0
    for index,line in enumerate(lines,1):
        check();seen+=1
        try:
            if len(line)>100000:raise ValueError('row_size')
            row=json.loads(line)
            if type(row)is dict:
                for key in FIELDS:
                    if key not in row or row[key]is None or row[key]=='':missing[key]+=1
                if type(row.get('case_id'))is str:case_ids.append(row['case_id'])
            value=describe(row);valid.append(value);groups[value['group_id']].append(value)
        except(ValueError,TypeError,KeyError)as error:
            errors.append({'line':index,'kind':type(error).__name__})
    findings=[];roots=[];pairs=[];root_movers=Counter()
    for group,rows in groups.items():
        if len(rows)!=3 or {row['mode']for row in rows}!=set(MODES)or len({row['fen']for row in rows})!=1:
            findings.append('incomplete_duplicate_mode_or_mixed_fen');continue
        roots.append(next(row for row in rows if row['mode']=='free'))
        root_movers.update({row['mover']for row in rows})
        selected=[row for row in rows if row['mode']!='free'];pairs.append(selected)
        if len({row['uci']for row in selected})!=2:findings.append('duplicate_supplied_move')
    cases=Counter(case_ids);boards=Counter(row['key']for row in roots)
    result={'planned_presentations':requested,'observed_rows':seen,'valid_presentations':len(valid),'invalid_rows':len(errors),
        'missing_rows':max(0,requested-seen),'extra_rows':max(0,seen-requested),'errors':errors,
        'missing_required_fields':distribution(missing,requested,FIELDS),'duplicate_case_ids':{'keys':sum(v>1 for v in cases.values()),'excess_rows':sum(v-1 for v in cases.values()if v>1),'affected_rows':sum(v for v in cases.values()if v>1),'denominator':seen},
        'groups_with_valid_presentations':len(groups),'complete_root_groups':len(roots),'group_ids_sha256':group_digest(groups),
        'expected_root_groups':requested//3,'group_findings':dict(Counter(findings)),
        'duplicate_packet_excess_presentations':sum(v-1 for v in Counter(row['packet_hash']for row in valid).values()if v>1),
        'duplicate_current_board_groups':sum(v-1 for v in boards.values()if v>1),
        'by_mode':{mode:move_profile([row for row in valid if row['mode']==mode])for mode in MODES},
        'all_presentations':move_profile(valid),'combined_selected':move_profile([row for row in valid if row['mode']!='free']),
        'root_group_coverage':root_profile(roots),
        'root_groups_with_target_piece':{**distribution(root_movers,len(roots),tuple('PNBRQK')),
            'multi_label':True,'scope':'One count per complete source-game group having that mover in any of its three targets; pieces may overlap.'},
        'selected_pairs':{'groups':len(pairs),'one_check_one_noncheck':sum(sorted(row['check']for row in pair)==[False,True]for pair in pairs),
            'same_origin':sum(pair[0]['origin']==pair[1]['origin']for pair in pairs),
            'one_check_one_noncheck_rate':sum(sorted(row['check']for row in pair)==[False,True]for pair in pairs)/len(pairs)if pairs else None,
            'same_origin_rate':sum(pair[0]['origin']==pair[1]['origin']for pair in pairs)/len(pairs)if pairs else None}}
    return result,{'groups':set(groups),'cases':set(case_ids),'current_board_state_first4':set(boards),
        'full_fen6':{row['fen']for row in roots},'generator_packet_inputs':{row['packet_hash']for row in valid}}


def execute(plan,protocol,out):
    if out.exists():raise ValueError('Create-only descriptive audit')
    out.mkdir(parents=True);started=time.monotonic()
    result={'status':'started','kind':'Descriptive TRAIN/DEV corpus coverage, not model quality or cohort reselection',
        'protocol_sha256':digest(protocol),'planned_presentations':{'train':1536,'development':96},'splits':{},
        'opened_data_files':[],'frameworks_imported':False}
    save(out/'result.json',result)
    try:
        framework_free()
        if plan['implementation_sha256']!=digest(Path(__file__)):raise ValueError('Audit source differs')
        for item in plan['dependencies']:bound(item)
        corpus=Path(plan['corpus_root']).resolve();manifest_path=Path(plan['manifest']['path']).resolve()
        if manifest_path!=corpus/'manifest.json':raise ValueError('Manifest whitelist path differs')
        manifest=json.loads(bound(plan['manifest']).read_text())
        def check():
            if time.monotonic()-started>=30 or datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):
                raise RuntimeError('Descriptive audit30s/global13UTC bound')
        memberships={}
        for split,name,expected in(('train','train.jsonl',1536),('development','development.jsonl',96)):
            check();item=plan['data_files'][name]
            if item['sha256']!=manifest['files'][name]['sha256']or manifest['files'][name]['rows']!=expected:
                raise ValueError('Pinned TRAIN/DEV manifest contract differs')
            path=Path(item['path']).resolve()
            if path!=corpus/name:raise ValueError('TRAIN/DEV whitelist path differs')
            if path.stat().st_size>8*1024**2:raise ValueError('Bounded local export size')
            bound(item)
            result['opened_data_files'].append(name)
            with path.open(encoding='utf-8')as stream:result['splits'][split],memberships[split]=audit_lines(stream,expected,check)
            save(out/'result.json',result)
        result['train_dev_overlap']={key:overlap_profile(memberships['train'][key],memberships['development'][key])for key in('groups','cases','current_board_state_first4','full_fen6','generator_packet_inputs')}
        result['development_raw_groups_from_manifest']={'count':len(manifest['development_raw_group_ids']),
            'all_present':set(manifest['development_raw_group_ids']).issubset(memberships['development']['groups']),
            'sha256':group_digest(manifest['development_raw_group_ids'])}
        result['train_dev_overlap']['scope']='Only these TRAIN/DEV exports; first4-state collisions, full6-FEN collisions and exact packet collisions are distinct. No historical, reserve or held paths checked. A state collision alone is not full input leakage.'
        result.update(status='completed',frameworks_imported=False,
            limitations=plan['limitations'],source_bindings=plan['data_files'])
        framework_free()
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:
        result['frameworks_imported']=any(name in sys.modules for name in('torch','transformers','bitsandbytes','pyarrow'))
        result['elapsed_seconds']=time.monotonic()-started;save(out/'result.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    execute(json.loads(args.protocol.read_text()),args.protocol,args.out)
