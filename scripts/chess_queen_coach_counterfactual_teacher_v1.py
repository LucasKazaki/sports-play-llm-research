"""One-thread forced Stockfish targets and exports; never invokes a model."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import threading

import chess
import chess.engine
import chess_queen_coach_sft_intake_v1 as verified
import chess_queen_coach_counterfactual_intake_v1 as intake

head=intake.head;ROOT=intake.ROOT


def tasks_for(dataset):
    tasks=[]
    for split,rows in dataset['groups'].items():
        for row in rows:
            for index,mode in enumerate(intake.MODES):
                tasks.append({'case_id':row['case_ids'][index],'group_id':row['game_id'],'split':split,
                    'mode':mode,'fen':row['fen'],'selected_uci':None if mode=='free'else row['pair'][index-1]['uci']})
    return tasks


def observation(board,event,final,selected=None):
    if board.is_game_over(claim_draw=False)or final not in board.legal_moves:raise ValueError('Illegal/terminal teacher root or final')
    if selected is not None and final.uci()!=selected:raise ValueError('Forced final differs from selected root move')
    pv=event.get('pv',[])if event else[]
    if not pv or pv[0]!=final or 'score'not in event:raise ValueError('Same-event PV/score/final mismatch')
    replay=board.copy(stack=False);line=[];keys=[]
    for move in pv[:3]:
        if replay.is_game_over(claim_draw=False):break
        if move not in replay.legal_moves:raise ValueError('Illegal teacher continuation')
        line.append(move.uci());replay.push(move);keys.append(intake.board_key(replay.fen()))
    score=event['score'].pov(board.turn)
    return {'status':'completed','teacher_move_uci':final.uci(),'reference_pv':line,'teacher_path_keys':keys,
        'score':{'cp':score.score(),'mate':score.mate(),'lowerbound':bool(event.get('lowerbound')),
            'upperbound':bool(event.get('upperbound')),'perspective':'side_to_move'},
        'nodes':event.get('nodes'),'depth':event.get('depth')}


def recover(tasks,journal):
    records={row['case_id']:{**row,'status':'not_run'}for row in tasks};started=set();done=set()
    if Path(journal).exists():
        lines=Path(journal).read_bytes().splitlines();nonempty=[i for i,line in enumerate(lines)if line.strip()]
        for index in nonempty:
            try:event=json.loads(lines[index])
            except(UnicodeDecodeError,json.JSONDecodeError):
                if index!=nonempty[-1]:raise ValueError('Teacher journal corruption before later event')
                break # Original torn suffix stays untouched; prior intent remains unknown.
            if event.get('event')not in('intent','outcome'):continue
            case=event['case_id']
            if case not in records:raise ValueError('Foreign teacher identity')
            if event['event']=='intent':
                if case in started:raise ValueError('Repeated teacher intent')
                started.add(case);records[case]['status']='active_unknown'
            else:
                if case not in started or case in done:raise ValueError('Teacher outcome lacks unique intent')
                done.add(case);records[case].update(event)
    return [records[row['case_id']]for row in tasks]


def teachers(protocol,out):
    plan=intake.verify(protocol);dataset=head.read(out/'dataset.json');closed=head.read(out/'intake-closed.json')
    if(dataset['status']!='ready_for_teachers'or closed['status']!='ready_for_teachers'
        or closed['dataset_sha256']!=head.sha(out/'dataset.json')or dataset['protocol_sha256']!=head.sha(protocol)):
        raise ValueError('Exact complete fresh intake is required')
    marker=out/'teacher-attempt.json'
    if marker.exists():raise ValueError('No teacher retries')
    tasks=tasks_for(dataset)
    if len(tasks)!=3168 or len({row['case_id']for row in tasks})!=3168:raise ValueError('Full3168 unique teacher requests required')
    head.save(marker,{'status':'started','protocol_sha256':head.sha(protocol),'dataset_sha256':head.sha(out/'dataset.json')})
    head.save(out/'teacher-planned.json',{'planned':3168,'rows':[{**row,'status':'not_run'}for row in tasks]})
    journal=out/'teacher-journal.jsonl';engine=None;stop=threading.Event();lock=threading.Lock()
    def emit(event):
        with lock:intake.append(journal,event)
    try:
        intake.snapshot(out,protocol,plan,'teacher-sources')
        cpu=intake.prior.cpu_guard(out,{**plan,'maximum_cpu_seconds':3300})
        def guard(index):
            if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):raise RuntimeError('Global cutoff')
            cpu(index)
        guard(-1)
        engine=chess.engine.SimpleEngine.popen(verified.AuditedUciProtocol,str(head.bound(plan['teacher']['binary'])),timeout=30)
        engine.configure({'Threads':1,'Hash':32})
        if '19'not in engine.id.get('name',''):raise ValueError('Pinned Stockfish19 required')
        emit({'event':'engine_opened','identity':engine.id,'threads':1,'hash_mb':32})
        def watch():
            while not stop.wait(.05):
                if(out/'CANCEL').exists():engine.close();return
        threading.Thread(target=watch,daemon=True).start()
        for index,task in enumerate(tasks):
            guard(index)
            emit({'event':'intent',**task,'nodes':50000,'utc':datetime.now(timezone.utc).isoformat()})
            engine.protocol.audit=lambda line:emit({'event':'uci_line','case_id':task['case_id'],'line':line})
            timer=threading.Timer(30,engine.close);timer.daemon=True;timer.start()
            try:
                board=chess.Board(task['fen']);last=None
                forced=[chess.Move.from_uci(task['selected_uci'])]if task['selected_uci']else None
                if not board.is_valid()or board.is_game_over(claim_draw=False)or(forced and forced[0]not in board.legal_moves):
                    raise ValueError('Teacher root/input is invalid, terminal or illegal')
                with engine.analysis(board,chess.engine.Limit(nodes=50000),root_moves=forced,
                    game=task['case_id'],info=chess.engine.INFO_ALL)as analysis:
                    for event in analysis:
                        if 'score'in event:last=dict(event)
                    final=analysis.wait()
                result=observation(board,last,final.move,task['selected_uci'])
                emit({'event':'outcome','case_id':task['case_id'],**result})
            except BaseException as error:
                if isinstance(error,Exception):emit({'event':'outcome','case_id':task['case_id'],
                    'status':'failed','error':type(error).__name__+': '+str(error)})
                raise
            finally:timer.cancel();engine.protocol.audit=None
    except BaseException as error:
        head.save(out/'teacher-failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),'no_retry':True})
        raise
    finally:
        stop.set()
        if engine is not None:engine.close()
        rows=recover(tasks,journal);statuses=dict(Counter(row['status']for row in rows))
        head.save(out/'teachers.json',{'protocol_sha256':head.sha(protocol),'dataset_sha256':head.sha(out/'dataset.json'),
            'planned':3168,'rows':rows,'statuses':statuses,'all_planned_completed':statuses=={'completed':3168}})
        head.save(out/'teacher-closed.json',{'teachers_sha256':head.sha(out/'teachers.json'),'statuses':statuses})


def paths_for(root,records):
    return set(root['path_keys'])|{key for row in records for key in row['teacher_path_keys']}


def audit_paths(dataset,records):
    roles={}
    by_case={row['case_id']:row for row in records}
    for split,roots in dataset['groups'].items():
        for root in roots:
            for key in paths_for(root,[by_case[case]for case in root['case_ids']]):
                previous=roles.get(key)
                if previous is not None and previous!=split:raise ValueError('Cross-split teacher/root path collision')
                roles[key]=split
    return roles


def validate_selected_pair(root,by_case):
    tasks=[by_case[case]for case in root['case_ids'][1:]]
    facts=[verified.move_facts(chess.Board(row['fen']),chess.Move.from_uci(row['selected_uci']))for row in tasks]
    if(sum(row['gives_check']for row in facts)!=1
        or len({tuple(row[key]for key in('mover','capture','victim'))for row in facts})!=1):
        raise ValueError('Selected pair is not balanced/matched under independent replay')


def full_three(task):
    pv=task.get('reference_pv',[])
    if task['status']!='completed'or len(pv)!=3:return False
    board=chess.Board(task['fen'])
    for text in pv:
        if board.is_game_over(claim_draw=False):return False
        move=chess.Move.from_uci(text)
        if move not in board.legal_moves:return False
        board.push(move)
    return True


def held_roots(roots,by_case,historical,train_dev_paths):
    selected=[];eligibility=[]
    for root in sorted(roots,key=lambda row:row['source_ordinal']):
        tasks=[by_case[case]for case in root['case_ids']]
        paths=paths_for(root,tasks)
        reason='short_or_invalid_reference'if not all(full_three(task)for task in tasks)else(
            'historical_or_training_path_overlap'if paths&(historical|train_dev_paths)else None)
        take=reason is None and len(selected)<16
        if take:selected.append(root)
        eligibility.append({'group_id':root['game_id'],'source_ordinal':root['source_ordinal'],
            'eligible':reason is None,'selected':take,'reason':reason or('selected'if take else'eligible_reserve')})
    return selected,eligibility


def cases(root,by_case,targets):
    inputs=[];references=[]
    for case in root['case_ids']:
        task=by_case[case];response,facts=verified.verified_target(task['fen'],task['reference_pv'])
        selected=task['mode']!='free'
        if selected:
            if task['reference_pv'][0]!=task['selected_uci']:raise ValueError('Forced target differs')
            response=response.replace('PROMISING_MOVES: '+verified.move_atom(chess.Board(task['fen']),
                chess.Move.from_uci(task['selected_uci']),chess.Board(task['fen']).turn),'PROMISING_MOVES:')
        packet={'fen':task['fen']}
        if selected:packet['selected_uci']=task['selected_uci']
        row={'case_id':case,'group_id':root['game_id'],'mode':task['mode'],'input':packet}
        if targets:row['response']=response
        inputs.append(row)
        references.append({'case_id':case,'group_id':root['game_id'],'selected_uci':task['reference_pv'][0],
            'reference_pv_uci':task['reference_pv'],'facts':facts[0],'per_ply_facts':facts,
            'check_role':facts[0]['gives_check']if selected else None,'source_ordinal':root['source_ordinal']})
    return inputs,references


def export(protocol,out):
    plan=intake.verify(protocol)
    if(out/'export-attempt.json').exists():raise ValueError('Export is create-only')
    head.save(out/'export-attempt.json',{'protocol_sha256':head.sha(protocol)})
    try:
        dataset=head.read(out/'dataset.json');labels=head.read(out/'teachers.json');closed=head.read(out/'teacher-closed.json')
        if(labels['protocol_sha256']!=head.sha(protocol)or labels['dataset_sha256']!=head.sha(out/'dataset.json')
            or closed['teachers_sha256']!=head.sha(out/'teachers.json')or not labels['all_planned_completed']):
            raise ValueError('All exact3168 teacher outcomes must complete')
        expected=tasks_for(dataset);records=labels['rows']
        if len(records)!=3168 or any({key:row[key]for key in task}!=task or row['status']!='completed'
            for task,row in zip(expected,records)):raise ValueError('Teacher task ordering/status differs')
        by_case={row['case_id']:row for row in records};roles=audit_paths(dataset,records)
        for roots in dataset['groups'].values():
            for root in roots:validate_selected_pair(root,by_case)
        registry=head.read(out/'initial-exclusions.json');historical=set(registry['board_keys'])
        train_dev={key for key,split in roles.items()if split!='reserve'}
        held,eligibility=held_roots(dataset['groups']['reserve'],by_case,historical,train_dev)
        head.save(out/'reserve-eligibility.json',{'planned_reserve':512,'eligible':sum(row['eligible']for row in eligibility),
            'selected':len(held),'rows':eligibility})
        if len(held)!=16:raise ValueError('insufficient_cohort: fewer16 eligible reserved roots')
        raw_dev=[root['game_id']for root in sorted(dataset['groups']['development'],key=lambda row:row['source_ordinal'])
            if all(full_three(by_case[case])for case in root['case_ids'])][:2]
        if len(raw_dev)!=2:raise ValueError('insufficient_cohort: fewer2 complete3ply dev roots')
        files={};balance={}
        for name,roots in [('train',dataset['groups']['train']),('development',dataset['groups']['development']),('heldout',held)]:
            rows=[];refs=[]
            for root in roots:
                values,truth=cases(root,by_case,name!='heldout');rows.extend(values);refs.extend(truth)
            filename=name+('-inputs'if name=='heldout'else'')+'.jsonl'
            for fname,values in [(filename,rows),(name+'-references.jsonl',refs)]:
                verified.write_lines(out/fname,values);files[fname]={'sha256':head.sha(out/fname),'rows':len(values)}
            balance[name]=dict(Counter(str(row['facts']['gives_check'])for row in refs if row['check_role']is not None))
        games=set(registry['games'])|{root['game_id']for roots in dataset['groups'].values()for root in roots}
        head.save(out/'reserved-exclusions.json',{'games':sorted(games),'board_keys':sorted(historical|set(roles))})
        result={'schema':intake.SCHEMA,'status':'ready_for_training','protocol_sha256':head.sha(protocol),
            'dataset_sha256':head.sha(out/'dataset.json'),'teachers_sha256':head.sha(out/'teachers.json'),'files':files,
            'teacher_outcomes':labels['statuses'],'development_raw_group_ids':raw_dev,
            'held_root_game_ids':[root['game_id']for root in held],'reserved_holdout_games':512,
            'reserved_exclusions_sha256':head.sha(out/'reserved-exclusions.json'),'selected_check_balance':balance,
            'historical_teacher_tail_overlapping_keys':len({key for row in records for key in row['teacher_path_keys']}&historical),
            'model_calls':0,'no_replacement':True,'scope':'Forced selected candidates are not global best/promising; no whole-prose coaching claim.'}
        head.save(out/'manifest.json',result);return result
    except BaseException as error:
        head.save(out/'export-failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),'no_retry':True});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=('teachers','export'))
    parser.add_argument('--protocol',type=Path,default=intake.PROTOCOL);parser.add_argument('--out',type=Path,default=intake.OUTPUT)
    args=parser.parse_args();result=globals()[args.phase](args.protocol,args.out)
    if result is not None:print(json.dumps(result))
