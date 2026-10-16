"""CPU-only, source-bound coaching targets. No learned/model/GPU calls.

Freeze and independently review the protocol before intake or teacher dispatch.
Source answer tails are ignored. Targets and references never enter model input.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import threading
import time

import chess
import chess.engine
import chess_move_policy_v5 as policy
import chess_queen_adapter as native
from chess_fact_sft_common import read, save, sha

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='chess.queen-coach-sft-intake.v1'
COUNTS={'train':1024,'development':32,'holdout':512,'rollout':0}
STRATA={'discovered_or_double_check':2,'king_mover':2,'pawn_mover':2,
        'direct_check':4,'quiet':4,'noncheck_capture':2}
SOURCE='data/private/chess-fact-sft-v1/source/lichess-hf-train-00000.parquet'
DEFAULT_PROTOCOL=ROOT/'experiments/chess-queen-coach-sft-v1/protocol-v3.json'
DEFAULT_OUT=ROOT/'data/private/chess-queen-coach-sft-v1'


def binding(path):
    path=Path(path)
    return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size}


def bound(item):
    path=(ROOT/item['path']).resolve()
    if not path.is_relative_to(ROOT) or sha(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
        raise ValueError('frozen file changed: '+item['path'])
    return path


def protocol(path):
    plan=read(path)
    if plan.get('schema')!=SCHEMA or plan.get('implementation_sha256')!=sha(Path(__file__)):
        raise ValueError('protocol/source identity differs')
    if plan['counts']!=COUNTS or plan['strata']!=STRATA or plan['seed']!=4082083 or plan['source_row_cap']!=500000:
        raise ValueError('frozen selection differs')
    if plan['source']['bytes']!=294920084 or plan['source']['sha256']!='5352e3bff4d6163851c07a0cc922b1ff72875cc6f75d994bdfc3272a37ca9e87':
        raise ValueError('original CC0 source differs')
    for item in [plan['source'],*plan['dependencies'],*plan['exclusions'].values(),*plan['authored_responses']]:bound(item)
    if plan['teacher']!={'binary':plan['teacher']['binary'],'workers':3,'threads':1,'hash_mb':32,
                         'nodes':50000,'deadline_seconds':30,'multipv':1}:
        raise ValueError('frozen teacher settings differ')
    bound(plan['teacher']['binary'])
    for name,version in plan['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('CPU runtime changed: '+name)
    return plan


def freeze(path):
    """Read only already retained metadata; never scan/select new source rows."""
    if path.exists():raise ValueError('protocol is create-only')
    exclusions={
      'registry':'data/private/chess-encoder-check-v1/initial-exclusions.json',
      'head':'data/private/chess-encoder-check-v1/dataset.json',
      'queen_pool':'data/private/chess-queen-benchmark-v1/dataset.json',
      'queen_teachers':'data/private/chess-queen-benchmark-v1/labels.json',
      'authored_ledger':'data/private/chess-queen-nf4-v1/authored-outcomes.json'}
    ledger=read(ROOT/exclusions['authored_ledger'])
    if ledger.get('status')!='completed' or ledger.get('completed_count')!=4:raise ValueError('authored closure missing')
    dependencies=['scripts/chess_move_policy_v5.py','scripts/chess_queen_adapter.py',
                  'scripts/chess_fact_sft_common.py','tests/test_chess_queen_coach_sft_intake_v1.py']
    dependencies += [item['path'] for item in read(ROOT/'experiments/chess-move-policy-v5/protocol-amendment-v3.json')['dependencies']]
    plan={'schema':SCHEMA,'frozen_at':datetime.now(timezone.utc).isoformat(),
      'implementation_sha256':sha(Path(__file__)),'seed':4082083,'counts':COUNTS,'strata':STRATA,'source_row_cap':500000,
      'source':{**binding(ROOT/SOURCE),'license':'CC0-1.0','upstream':'https://huggingface.co/datasets/Lichess/chess-puzzles/resolve/461725966ea46898ec6481372a6326de3281bfbd/data/train-00000-of-00003.parquet'},
      'exclusions':{role:binding(ROOT/name) for role,name in exclusions.items()},
      'authored_responses':[binding(ROOT/row['output']) for row in ledger['rows']],
      'expected_initial_registry':{'games':107208,'board_keys':242535},
      'teacher':{'binary':binding(ROOT/'data/private/chess-distill-v1/tools/stockfish/stockfish-windows-x86-64-universal.exe'),
                 'workers':3,'threads':1,'hash_mb':32,'nodes':50000,'deadline_seconds':30,'multipv':1},
      'runtime_versions':{name:importlib.metadata.version(name) for name in ('chess','pyarrow')},
      'dependencies':[binding(ROOT/name) for name in dict.fromkeys(dependencies)],
      'selection':'Reuse frozen v5 select_rows, source order and original-game SHA buckets. Consume first setup token only, never source answer tail/themes. One game and before/current board role globally, including full unused512 holdout reservoir.',
      'exclusion_policy':'Exact initial head registry; every head group and selected-pair successor; all96 Queen pool games/before/current and every legal teacher-PV successor; all4 authored current/legal critical successors. Verify raw response bindings against closed ledger.',
      'historical_board_scope':'These historical-role exclusions apply to candidate before/current root boards. Future teacher successors may revisit older spent boards; no claim of historical successor-board novelty.',
      'development_raw_selection':'Before learned calls, retain the first4 development games in frozen source order with complete legal3-ply teacher references. Fail export if fewer4. Report both free/selected cases; all32 development games remain training-selection references.',
      'held_selection':'After ALL planned teachers complete, full legal3-ply references only. Mutually exclusive priority: discovered/doublecheck; kingmover; pawnmover; remainingcheck; remainingquiet; remainingnoncheckcapture. First source-order roots per frozen quota; fail if any quota cannot fill. No model peeking or adaptation.',
      'new_split_audit':'All original games and before/current roles unique. Fail before export on any new cross-split root/PV-successor or PV/PV-successor board overlap; no adaptive replacements.',
      'grammar':{'ANALYSIS':'The move {native_atom} gives checkmate.|gives check.|does not give check. Then immediately: It captures {native_victim_piece}.|It does not capture a piece.',
                 'BEST_MOVE':'verified teacher first atom','CRITICAL_LINE':'first up to3 legally replayed atoms, root POV throughout',
                 'PROMISING_MOVES':'teacher first atom only','EVALUATION':'Checkmate|Draw|Not assessed'},
      'inputs':'Exactly {fen}, or {fen,selected_uci:teacherbest}. No history/eval/future boards/PV/facts/labels. Two stable case IDs per original game.',
      'proof':'Create-only intake/teacher attempt; snapshots; pre-call fsynced intent, raw UCI lines, terminal completion journal. Unknown active attempts distinguished from never-run. No replay. No target/readiness until all1568 teacher outcomes completed and held quotas filled.',
      'claims':'Verified immediate board-fact grammar and bounded Stockfish target, not strategic why-best or human coaching acceptance. No learned call or source solution supplied.'}
    previous=path.with_name('protocol-v2.json') if path.with_name('protocol-v2.json').exists() else path.with_name('protocol.json')
    if previous.exists() and previous!=path:plan['previous_unexecuted_candidate']=binding(previous)
    path.parent.mkdir(parents=True,exist_ok=True);save(path,plan)
    return plan


def rows_of(data):
    for values in data.get('groups',data.get('splits',{})).values():
        yield from values


def add_reference_roles(row,games,boards):
    policy.add_roles(row,games,boards)
    board=chess.Board(row['fen'])
    for text in row.get('reference_pv',[]):
        move=chess.Move.from_uci(text)
        if move not in board.legal_moves or board.is_game_over(claim_draw=False):raise ValueError('invalid retained teacher exclusion')
        board.push(move);boards.add(policy.board_key(board.fen()))


def exclusions(plan):
    data={role:read(bound(item)) for role,item in plan['exclusions'].items()}
    registry=data['registry'];games=set(registry['games']);boards=set(registry['board_keys'])
    if {'games':len(games),'board_keys':len(boards)}!=plan['expected_initial_registry']:raise ValueError('initial registry counts differ')
    for row in rows_of(data['head']):add_reference_roles(row,games,boards)
    pool=list(rows_of(data['queen_pool']))
    if len(pool)!=96:raise ValueError('Queen96 pool incomplete')
    for row in pool:add_reference_roles(row,games,boards)
    teachers=list(rows_of(data['queen_teachers']))
    if len(teachers)!=96 or any(row.get('status')!='completed' for row in teachers):raise ValueError('Queen teachers incomplete')
    for row in teachers:add_reference_roles(row,games,boards)
    ledger=data['authored_ledger']
    if ledger.get('status')!='completed' or len(ledger.get('rows',[]))!=4:raise ValueError('authored ledger incomplete')
    for row,item in zip(ledger['rows'],plan['authored_responses']):
        if item['path']!=row['output'] or item['sha256']!=row['response_sha256']:raise ValueError('authored raw binding differs')
        raw=read(bound(item));packet,board=native.input_packet(raw['input'])
        if raw.get('status')!='completed':raise ValueError('authored response incomplete')
        boards.add(policy.board_key(board.fen()))
        for step in raw['parsed']['critical_line']['steps']:
            if not step.get('legal'):break
            move=chess.Move.from_uci(step['raw_uci'])
            if move not in board.legal_moves or board.is_game_over(claim_draw=False):raise ValueError('authored successor illegal')
            board.push(move)
            if board.fen()!=step['fen_after']:raise ValueError('authored successor differs')
            boards.add(policy.board_key(board.fen()))
    return games,boards


def snapshot(out,path,plan,name):
    folder=out/name;folder.mkdir()
    files={'implementation':Path(__file__),'protocol':path}
    files.update({f'dependency-{i:02d}':ROOT/item['path'] for i,item in enumerate(plan['dependencies'])})
    receipt={}
    for role,source in files.items():
        destination=folder/(role+'-'+source.name);shutil.copyfile(source,destination)
        receipt[role]={'file':destination.name,'sha256':sha(destination)}
    save(folder/'manifest.json',receipt)
    return receipt


def intake(path,out):
    plan=protocol(path)
    if out.exists():raise ValueError('intake is create-only')
    out.mkdir(parents=True);save(out/'intake-attempt.json',{'status':'started','protocol_sha256':sha(path)})
    try:
        snapshots=snapshot(out,path,plan,'executed-sources');games,boards=exclusions(plan)
        save(out/'initial-exclusions.json',{'games':sorted(games),'board_keys':sorted(boards)})
        groups,selection=policy.select_rows(policy.parquet_rows(bound(plan['source'])),plan['counts'],plan['seed'],games,boards,plan['source_row_cap'])
        dataset={'schema':SCHEMA,'protocol_sha256':sha(path),'source_sha256':plan['source']['sha256'],
                 'initial_exclusions_sha256':sha(out/'initial-exclusions.json'),'selection':selection,'splits':groups,'snapshots':snapshots}
        save(out/'dataset.json',dataset)
        save(out/'intake-completed.json',{'status':'completed','dataset_sha256':sha(out/'dataset.json'),
             'counts':{s:len(v) for s,v in groups.items()},'model_calls':0,'engine_calls':0})
        return dataset
    except Exception as error:
        save(out/'intake-failed.json',{'status':'failed','error':type(error).__name__+':'+str(error)});raise


def piece_atom(piece,pov):return '<PIECE_'+('M' if piece.color==pov else 'O')+piece.symbol().upper()+'>'


def move_atom(board,move,pov):
    if move not in board.legal_moves or board.is_game_over(claim_draw=False):raise ValueError('target move is illegal or terminal')
    square=lambda value:f'<SQUARE_{(value if pov else value^56)+1}>'
    piece=board.piece_at(move.from_square)
    victim=chess.Piece(chess.PAWN,not board.turn) if board.is_en_passant(move) else board.piece_at(move.to_square)
    atom=piece_atom(piece,pov)+square(move.from_square)+(piece_atom(victim,pov) if victim else '')+square(move.to_square)
    return atom+(piece_atom(chess.Piece(move.promotion,piece.color),pov) if move.promotion else '')


def move_facts(board,move):
    if move not in board.legal_moves or board.is_game_over(claim_draw=False):raise ValueError('facts need legal nonterminal board')
    piece=board.piece_at(move.from_square);ep=board.is_en_passant(move)
    victim=chess.Piece(chess.PAWN,not board.turn) if ep else board.piece_at(move.to_square)
    victim_square=(move.to_square-8 if board.turn else move.to_square+8) if ep else move.to_square
    after=board.copy(stack=False);after.push(move);checker_squares=list(after.checkers());checkers=[chess.square_name(s) for s in checker_squares]
    return {'mover':chess.piece_name(piece.piece_type),'promotion':chess.piece_name(move.promotion) if move.promotion else None,
      'castling':board.is_castling(move),'capture':board.is_capture(move),
      'victim':chess.piece_name(victim.piece_type) if victim else None,
      'victim_color':('white' if victim.color else 'black') if victim else None,
      'victim_square':chess.square_name(victim_square) if victim else None,'en_passant':ep,
      'gives_check':after.is_check(),'checkmate':after.is_checkmate(),'stalemate':after.is_stalemate(),
      'checkers':checkers,'discovered_or_double_check':after.is_check() and (len(checkers)>1 or any(s!=move.to_square and board.piece_at(s)==after.piece_at(s) for s in checker_squares)),
      'fen_after':after.fen(),'automatic_game_over':after.is_game_over(claim_draw=False)}


def verified_target(fen,pv):
    board=chess.Board(fen);pov=board.turn;atoms=[];facts=[]
    if not pv or len(pv)>3:raise ValueError('target requires one to three teacher plies')
    for text in pv:
        move=chess.Move.from_uci(text);atoms.append(move_atom(board,move,pov));facts.append(move_facts(board,move));board.push(move)
    first=facts[0]
    check='gives checkmate' if first['checkmate'] else 'gives check' if first['gives_check'] else 'does not give check'
    initial=chess.Board(fen);move=chess.Move.from_uci(pv[0])
    victim=chess.Piece(chess.PAWN,not initial.turn) if initial.is_en_passant(move) else initial.piece_at(move.to_square)
    capture='It captures '+piece_atom(victim,pov)+'.' if victim else 'It does not capture a piece.'
    evaluation='Checkmate' if first['checkmate'] else 'Draw' if first['automatic_game_over'] else 'Not assessed'
    text=f'ANALYSIS: The move {atoms[0]} {check}. {capture}\nBEST_MOVE: {atoms[0]}\nCRITICAL_LINE: '+ ' '.join(atoms)+f'\nPROMISING_MOVES: {atoms[0]}\nEVALUATION: {evaluation}'
    for packet in ({'fen':fen},{'fen':fen,'selected_uci':pv[0]}):
        parsed=native.parse_output(packet,text)
        if parsed['accepted_move_uci']!=pv[0] or parsed['critical_line']['failure'] or [s['raw_uci'] for s in parsed['critical_line']['steps']]!=pv:
            raise ValueError('native target roundtrip differs')
    return text,facts


def journal_write(stream,lock,value):
    with lock:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


class AuditedUciProtocol(chess.engine.UciProtocol):
    def line_received(self,line):
        audit=getattr(self,'audit',None)
        if audit:audit(line)
        return super().line_received(line)


def teacher_worker(engine_path,settings,tasks,journal_path,cancel_path):
    """One owned CPU engine; raw incoming UCI plus intent/completion are durable."""
    lock=threading.Lock();stop=threading.Event();failed=False;engine=None
    with Path(journal_path).open('x',encoding='utf-8',newline='\n') as stream:
        emit=lambda value:journal_write(stream,lock,value)
        try:
            engine=chess.engine.SimpleEngine.popen(AuditedUciProtocol,engine_path,timeout=settings['deadline_seconds'])
            engine.configure({'Threads':settings['threads'],'Hash':settings['hash_mb']})
            if '19' not in engine.id.get('name',''):raise ValueError('pinned Stockfish19 required')
            emit({'event':'engine_opened','identity':engine.id})
            def cancel_watch():
                while not stop.wait(.05):
                    if Path(cancel_path).exists():engine.close();return
            threading.Thread(target=cancel_watch,daemon=True).start()
            for split,row in tasks:
                if failed or Path(cancel_path).exists():
                    emit({'event':'outcome','split':split,'id':row['id'],'status':'not_run','error':'engine_failed_or_owned_cancel'});continue
                emit({'event':'intent','split':split,'id':row['id'],'fen':row['fen'],'nodes':settings['nodes'],'utc':datetime.now(timezone.utc).isoformat()})
                engine.protocol.audit=lambda line:emit({'event':'uci_line','id':row['id'],'line':line})
                timer=threading.Timer(settings['deadline_seconds'],engine.close);timer.daemon=True;timer.start()
                record={'event':'outcome','split':split,'id':row['id'],'status':'failed'}
                try:
                    board=chess.Board(row['fen']);last=None
                    with engine.analysis(board,chess.engine.Limit(nodes=settings['nodes']),game=object(),
                        info=chess.engine.INFO_SCORE|chess.engine.INFO_PV|chess.engine.INFO_BASIC) as analysis:
                        for event in analysis:
                            if 'score' in event:last=dict(event)
                        final=analysis.wait()
                    record.update(policy.teacher_observation(board,last,final.move))
                except Exception as error:
                    record['error']=type(error).__name__+':'+str(error);failed=True
                finally:
                    timer.cancel();engine.protocol.audit=None
                emit(record)
        except Exception as error:
            emit({'event':'worker_failure','error':type(error).__name__+':'+str(error)})
        finally:
            stop.set()
            if engine is not None:engine.close()


def recover_outcomes(tasks,path):
    intents=set();outcomes={};planned={row['id'] for _,row in tasks}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:event=json.loads(line)
            except json.JSONDecodeError:break # Torn suffix preserved; active intent remains unknown.
            if event.get('event') not in {'intent','outcome'}:continue
            identity=event.get('id')
            if identity not in planned:raise ValueError('foreign teacher journal identity')
            if event['event']=='intent':
                if identity in intents:raise ValueError('duplicate teacher intent')
                intents.add(identity)
            else:
                if identity in outcomes or (event['status']!='not_run' and identity not in intents):raise ValueError('invalid teacher completion')
                outcomes[identity]=event
    return [(split,{**row,**outcomes.get(row['id'],{'status':'active_unknown' if row['id'] in intents else 'not_run',
                   'error':'interrupted_teacher_attempt'})}) for split,row in tasks]


def teachers(path,out):
    plan=protocol(path);dataset=read(out/'dataset.json')
    if dataset['protocol_sha256']!=sha(path) or read(out/'intake-completed.json')['dataset_sha256']!=sha(out/'dataset.json'):
        raise ValueError('dataset protocol/completed receipt differs')
    attempt=out/'teacher-attempt.json'
    if attempt.exists():raise ValueError('teacher attempt is create-only; no replay')
    with attempt.open('x',encoding='utf-8') as stream:json.dump({'status':'started','dataset_sha256':sha(out/'dataset.json'),'protocol_sha256':sha(path)},stream)
    tasks=[(s,r) for s,rows in dataset['splits'].items() for r in rows]
    chunks=[tasks[i::plan['teacher']['workers']] for i in range(plan['teacher']['workers'])]
    journals=out/'teacher-journals';errors=[]
    try:
        snapshot(out,path,plan,'teacher-executed-sources')
        journals.mkdir()
        with ProcessPoolExecutor(max_workers=plan['teacher']['workers']) as pool:
            futures={pool.submit(teacher_worker,str(bound(plan['teacher']['binary'])),plan['teacher'],chunk,str(journals/f'worker-{i}.jsonl'),str(out/'CANCEL')):i for i,chunk in enumerate(chunks)}
            try:
                for future in as_completed(futures):
                    try:future.result()
                    except Exception as error:errors.append({'worker':futures[future],'error':type(error).__name__+':'+str(error)})
            except BaseException:
                (out/'CANCEL').touch(exist_ok=True);raise
    except BaseException as error:
        errors.append({'stage':'setup_or_dispatch','error':type(error).__name__+':'+str(error)})
        (out/'CANCEL').touch(exist_ok=True);raise
    finally:
        records={s:{} for s in policy.SPLITS}
        for i,chunk in enumerate(chunks):
            for split,row in recover_outcomes(chunk,journals/f'worker-{i}.jsonl'):records[split][row['id']]=row
        result={'schema':SCHEMA,'protocol_sha256':sha(path),'dataset_sha256':sha(out/'dataset.json'),'worker_errors':errors,
            'splits':{s:[records[s][r['id']] for r in rows] for s,rows in dataset['splits'].items()}}
        result['statuses']=dict(Counter(row['status'] for rows in result['splits'].values() for row in rows))
        result['all_planned_completed']=result['statuses']=={'completed':sum(COUNTS.values())}
        save(out/'teachers.json',result)
        save(out/'teacher-closed.json',{'teachers_sha256':sha(out/'teachers.json'),'statuses':result['statuses'],'all_planned_completed':result['all_planned_completed']})
    return result


def stratum(facts):
    if facts['discovered_or_double_check']:return 'discovered_or_double_check'
    if facts['mover']=='king':return 'king_mover'
    if facts['mover']=='pawn':return 'pawn_mover'
    if facts['gives_check']:return 'direct_check'
    return 'noncheck_capture' if facts['capture'] else 'quiet'


def held_roots(rows):
    selected=[];counts=Counter()
    for row in rows:
        pv=row.get('reference_pv',[])
        if row['status']!='completed' or len(pv)!=3:continue
        _,facts=verified_target(row['fen'],pv);role=stratum(facts[0])
        if counts[role]<STRATA[role]:selected.append({**row,'stratum':role});counts[role]+=1
    if dict(counts)!=STRATA:raise ValueError('frozen held strata cannot fill: '+str(dict(counts)))
    return selected


def case_rows(row,include_response=True):
    pv=row['reference_pv'];target,facts=verified_target(row['fen'],pv);records=[];references=[]
    if pv[0]!=row['teacher_move_uci']:raise ValueError('teacher bestmove differs from reference prefix')
    for mode in ('free','selected'):
        identity=f"queen-coach-v1:{row['game_id']}:{mode}"
        packet={'fen':row['fen']}
        if mode=='selected':packet['selected_uci']=pv[0]
        record={'case_id':identity,'group_id':row['game_id'],'mode':mode,'input':packet}
        if include_response:record['response']=target
        records.append(record)
        references.append({'case_id':identity,'group_id':row['game_id'],'selected_uci':pv[0],
            'reference_pv_uci':pv,'facts':facts[0],'per_ply_facts':facts,'stratum':row.get('stratum'),
            'source_puzzle_id':row['puzzle_id'],'source_ordinal':row['source_ordinal']})
    return records,references


def write_lines(path,rows):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        for row in rows:stream.write(json.dumps(row,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())


def audit_splits(groups):
    games=set();roles={}
    for split,rows in groups.items():
        for row in rows:
            if row['game_id'] in games:raise ValueError('duplicate source game across corpus')
            games.add(row['game_id'])
            for fen in (row['source_before_fen'],row['fen']):
                key=policy.board_key(fen)
                if key in roles and roles[key][1]!=row['game_id']:raise ValueError('duplicate before/current board role')
                roles[key]=(split,row['game_id'])
    for split,rows in groups.items():
        for row in rows:
            board=chess.Board(row['fen'])
            for text in row['reference_pv']:
                board.push_uci(text);key=policy.board_key(board.fen())
                if key in roles and roles[key][0]!=split:raise ValueError('cross-split teacher successor board overlap')
                roles.setdefault(key,(split,row['game_id']))


def export(path,out):
    plan=protocol(path);dataset=read(out/'dataset.json');labels=read(out/'teachers.json')
    if (out/'manifest.json').exists() or (out/'export-attempt.json').exists():raise ValueError('export is create-only')
    save(out/'export-attempt.json',{'protocol_sha256':sha(path),'teachers_sha256':sha(out/'teachers.json')})
    try:
        if dataset['protocol_sha256']!=sha(path) or labels['protocol_sha256']!=sha(path) or labels['dataset_sha256']!=sha(out/'dataset.json'):
            raise ValueError('cohort teacher bindings differ')
        if read(out/'intake-completed.json')['dataset_sha256']!=sha(out/'dataset.json') or read(out/'teacher-closed.json')['teachers_sha256']!=sha(out/'teachers.json'):
            raise ValueError('completed source/teacher receipt changed')
        for split in policy.SPLITS:
            rows=labels['splits'][split]
            if len(rows)!=COUNTS[split] or any(r['status']!='completed' for r in rows):raise ValueError('all planned teacher outcomes must complete')
            if [r['id'] for r in rows]!=[r['id'] for r in dataset['splits'][split]]:raise ValueError('teacher identities differ')
        audit_splits(labels['splits'])
        held=held_roots(labels['splits']['holdout']);files={}
        raw_development=[row['game_id'] for row in labels['splits']['development'] if len(row['reference_pv'])==3][:4]
        if len(raw_development)!=4:raise ValueError('development raw cohort lacks four full3-ply roots')
        for split,rows in [('train',labels['splits']['train']),('development',labels['splits']['development']),('heldout',held)]:
            inputs=[];refs=[]
            for row in rows:
                cases,references=case_rows(row,split!='heldout');inputs.extend(cases);refs.extend(references)
            name=split+('-inputs' if split=='heldout' else '')+'.jsonl';reference=split+'-references.jsonl'
            write_lines(out/name,inputs);write_lines(out/reference,refs)
            files[name]={'sha256':sha(out/name),'rows':len(inputs)};files[reference]={'sha256':sha(out/reference),'rows':len(refs)}
        registry=read(out/'initial-exclusions.json');games=set(registry['games']);boards=set(registry['board_keys'])
        for rows in labels['splits'].values():
            for row in rows:add_reference_roles(row,games,boards)
        save(out/'reserved-exclusions.json',{'games':sorted(games),'board_keys':sorted(boards)})
        manifest={'schema':SCHEMA,'status':'ready_for_training','protocol_sha256':sha(path),
            'dataset_sha256':sha(out/'dataset.json'),'teachers_sha256':sha(out/'teachers.json'),'files':files,
            'teacher_outcomes':labels['statuses'],'held_root_game_ids':[r['game_id'] for r in held],
            'development_raw_group_ids':raw_development,
            'held_strata':dict(Counter(r['stratum'] for r in held)),
            'reserved_holdout_games':512,'reserved_exclusions_sha256':sha(out/'reserved-exclusions.json'),
            'heldout_reference_policy':'Private evaluator-only. Open only after complete prediction ledgers; never trainer input.',
            'model_calls':0,'scope':'Rule-verified immediate facts and bounded Stockfish target; not accepted strategic coaching.'}
        save(out/'manifest.json',manifest);return manifest
    except Exception as error:
        save(out/'export-failed.json',{'status':'failed','error':type(error).__name__+':'+str(error)});raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['freeze','intake','teachers','export'])
    parser.add_argument('--protocol',type=Path,default=DEFAULT_PROTOCOL);parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    result={'freeze':lambda:freeze(args.protocol),'intake':lambda:intake(args.protocol,args.out),
            'teachers':lambda:teachers(args.protocol,args.out),'export':lambda:export(args.protocol,args.out)}[args.command]()
    print(json.dumps({'command':args.command,'status':result.get('status','completed'),'out':str(args.out)}),flush=True)


if __name__=='__main__':main()
