"""Fresh reserved-owner selection and original-teacher-bound export, version2.

No acquisition, private data reads, engine, model or framework on import. The
separately pinned Python-chess helper is loaded only for final rule validation.
The formatting callback is untrusted and can never supply reference truth.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import copy
import hashlib
import json
from pathlib import Path
import re

COUNT=16
MODES=('free','selected_a','selected_b')
RULES_SHA256='0b7f81450e558be1dd94267ebceac7fe373e62f7ddeddaa8c03948b76b02b376'
UCI=re.compile(r'[a-h][1-8][a-h][1-8][qrbn]?')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def require(value,message):
    if not value:raise ValueError(message)


def key_list(value,count=None):
    require(type(value) is list and value and all(type(key) is str and key for key in value),
        'Nonempty path role keys required')
    require(len(value)==len(set(value)),'Distinct path role keys required')
    if count is not None:require(len(value)==count,'Exactly four distinct root role keys required')
    return value


def root_shape(root):
    require(type(root) is dict and type(root.get('game_id')) is str and root['game_id'], 'Root game required')
    key_list(root.get('path_keys'),4)
    ids=root.get('case_ids')
    require(type(ids) is list and len(ids)==3 and all(type(case) is str and case for case in ids)
        and len(set(ids))==3,'Three unique mode identities required')
    require(type(root.get('fen')) is str and root['fen'],'Root current FEN required')
    pair=root.get('pair')
    require(type(pair) is list and len(pair)==2 and all(type(item) is dict for item in pair),'Two original selected roles required')
    for index,item in enumerate(pair):
        require(type(item.get('uci')) is str and UCI.fullmatch(item['uci'])
            and item.get('successor_key')==root['path_keys'][index+2],'Selected root role differs')
    require(pair[0]['uci']!=pair[1]['uci'],'Selected move roles must differ')


def task_shape(root,row,case,mode,split=None):
    require(type(row) is dict and row.get('case_id')==case and row.get('group_id')==root['game_id']
        and row.get('mode')==mode and row.get('fen')==root['fen'] and row.get('status')=='completed',
        'Original teacher owner/mode/FEN/status differs')
    if split is not None:require(row.get('split')==split,'Original teacher split differs')
    pv=row.get('reference_pv')
    require(type(pv) is list and 1<=len(pv)<=3 and all(type(move) is str and UCI.fullmatch(move) for move in pv),
        'One to three stored teacher plies required')
    paths=key_list(row.get('teacher_path_keys'))
    require(len(paths)==len(pv),'Teacher path count differs from stored PV length')
    selected=None if mode=='free' else root['pair'][MODES.index(mode)-1]['uci']
    require('selected_uci' in row and row['selected_uci']==selected,'Original selected task differs from root role')
    require(row.get('teacher_move_uci')==pv[0] and (selected is None or pv[0]==selected),
        'Original teacher PV0/final/selected move differs')


def ownership(dataset,teachers,initial,reserved):
    groups=dataset['groups']
    require(type(groups) is dict and {name:len(rows) for name,rows in groups.items()}==
        {'train':512,'development':32,'reserve':512},'Exact audited512/32/512 corpus required')
    expected=[]
    for roots in groups.values():
        for root in roots:root_shape(root);expected.extend(root['case_ids'])
    rows=teachers['rows']
    require(type(rows) is list and len(rows)==3168 and len(expected)==len(set(expected))==3168,
        'Full unique teacher identities required')
    require([row.get('case_id') for row in rows]==expected,'Complete ordered teacher corpus required')
    by_case={row['case_id']:row for row in rows};owners=defaultdict(set);seen=set()
    historical=set(initial['games'])
    for key in initial['board_keys']:owners[key].add(('historical',None))
    for split,roots in groups.items():
        for root in roots:
            game=root['game_id'];require(game not in seen and game not in historical,'Repeated or historical game')
            seen.add(game)
            for key in root['path_keys']:owners[key].add((split,game))
            for case,mode in zip(root['case_ids'],MODES):
                row=by_case[case];task_shape(root,row,case,mode,split)
                for key in row['teacher_path_keys']:owners[key].add((split,game))
    require(set(reserved['games'])==historical|seen,'Reserved game union differs')
    require(set(reserved['board_keys'])==set(owners),'Reserved board union differs')
    return dict(owners),by_case


def choose(roots,by_case,owners,historical_games,spent_games,exposed_keys,full_three):
    require(len(roots)==512 and len({root['game_id'] for root in roots})==512,'All512 reserve roots required')
    for root in roots:
        root_shape(root)
        require(type(root.get('source_ordinal')) is int and root['source_ordinal']>=0,'Source ordinal required')
    require(len({root['source_ordinal'] for root in roots})==512,'Unique source ordinals required')
    require(len(spent_games)==len(set(spent_games))==16 and set(spent_games)<={root['game_id'] for root in roots},'Exact failed16-game scope required')
    selected=[];ledger=[]
    for root in sorted(roots,key=lambda row:row['source_ordinal']):
        game=root['game_id'];reason=None
        # Do not inspect any teacher record or callback for spent/historical games.
        if game in spent_games:reason='spent_game'
        elif game in historical_games:reason='historical_game'
        else:
            tasks=[];paths=set(root['path_keys'])
            for case,mode in zip(root['case_ids'],MODES):
                row=by_case[case];task_shape(root,row,case,mode,'reserve')
                tasks.append(copy.deepcopy(row));paths.update(row['teacher_path_keys'])
            if paths&exposed_keys:reason='post_corpus_generated_path_overlap'
            elif any(owners.get(key)!={('reserve',game)} for key in paths):reason='foreign_or_unproved_path_owner'
            elif not all(len(row['reference_pv'])==3 and full_three(copy.deepcopy(row)) for row in tasks):
                reason='short_or_invalid_reference'
            # Eligibility is not export truth: final export independently replays
            # every original PV and reconstructs exact facts with the pinned helper.
        take=reason is None and len(selected)<COUNT
        if take:selected.append(root)
        ledger.append({'group_id':game,'source_ordinal':root['source_ordinal'],'eligible':reason is None,
            'selected':take,'reason':reason or ('selected' if take else 'eligible_unused_reserve')})
    return selected,{'status':'ready_for_export' if len(selected)==COUNT else 'insufficient_cohort',
        'planned_reserve':512,'planned_selected':COUNT,'selected':len(selected),'unused_before_selection':496,
        'reason_counts':dict(Counter(row['reason'] for row in ledger)),'rows':ledger}


def rules():
    path=Path(__file__).with_name('reference_rules_v1.py');raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==RULES_SHA256,'Pinned reference reconstructor changed')
    namespace={'__name__':'_fresh_held_pinned_reference_rules'}
    # Execute the exact checked snapshot, avoiding a second source read/import.
    exec(compile(raw,str(path),'exec'),namespace)
    return namespace


def export_rows(roots,by_case,make_cases=None):
    require(len(roots)==COUNT and len({root['game_id'] for root in roots})==COUNT,'Never shrink/repeat the16-game cohort')
    frozen=copy.deepcopy(roots);original_roots=canonical(frozen);source={}
    for root in frozen:
        root_shape(root)
        require(type(root.get('source_ordinal')) is int and root['source_ordinal']>=0,'Source ordinal required')
        for case,mode in zip(root['case_ids'],MODES):
            require(case not in source,'Unique48 original cases required')
            require(case in by_case,'Missing original teacher record')
            source[case]=copy.deepcopy(by_case[case]);task_shape(root,source[case],case,mode,'reserve')
            require(len(source[case]['reference_pv'])==3,'Full stored three-ply reference required')
    original_tasks=canonical(source);rule=rules();inputs=[];references=[]
    for root in frozen:
        rule['validate_root'](root)
        expected=[];expected_rows=[]
        for case,mode in zip(root['case_ids'],MODES):
            task=source[case];truth=rule['expected_reference'](root,task);expected.append(truth)
            packet={'fen':root['fen']}
            if mode!='free':packet['selected_uci']=task['selected_uci']
            expected_rows.append({'case_id':case,'group_id':root['game_id'],'mode':mode,'input':packet})
        if make_cases is None:values,truth=expected_rows,expected
        else:
            # The callback receives copies of this selected root's tasks only,
            # never the entire3168 map or mutable authoritative source objects.
            values,truth=make_cases(copy.deepcopy(root),{case:copy.deepcopy(source[case]) for case in root['case_ids']},False)
        require(canonical(roots)==original_roots and canonical({case:by_case.get(case) for case in source})==original_tasks,
            'Formatting callback mutated original source records')
        require(type(values) is list and type(truth) is list and len(values)==len(truth)==3,'Three modes required')
        require(canonical(values)==canonical(expected_rows),'Generator packets differ from original root/selected tasks')
        require(canonical(truth)==canonical(expected),'Reference PV/facts/shape differ from original teacher and rule replay')
        inputs.extend(copy.deepcopy(values));references.extend(copy.deepcopy(truth))
    require(len(inputs)==len(references)==48 and len({row['case_id'] for row in inputs})==48,'Unique48 inputs required')
    return inputs,references


def legal_generated_keys(raw,native,chess,board_key):
    packet,board=native.input_packet(raw['input']);keys={board_key(board.fen())}
    parsed=native.parse_output(packet,raw.get('raw_text',''))
    for step in parsed['critical_line']['steps']:
        if not step.get('legal') or board.is_game_over(claim_draw=False):break
        move=chess.Move.from_uci(step['raw_uci'])
        require(move in board.legal_moves,'Native legal step disagrees with rule replay')
        board.push(move);require(board.fen()==step['fen_after'],'Native successor differs');keys.add(board_key(board.fen()))
    return keys


def evidence_digest(owners):
    return hashlib.sha256(canonical({key:sorted(value) for key,value in sorted(owners.items())})).hexdigest()
