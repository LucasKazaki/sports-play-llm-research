"""Pure authored API/rule fixtures, not a private corpus/export or quality result."""
import copy
import importlib.util
from pathlib import Path
import sys

import chess
import pytest

spec=importlib.util.spec_from_file_location('fresh_held_selection_v2',Path(__file__).with_name('selection_v2.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def metadata_fixture():
    dataset={'groups':{}};rows=[];keys={'historical-key'};games={'historical-game'}
    for split,count in [('train',512),('development',32),('reserve',512)]:
        roots=[]
        for i in range(count):
            game=f'authored-{split}-{i:04d}';ids=[f'{game}:{mode}' for mode in s.MODES]
            paths=[f'root-role-{game}-{j}' for j in range(4)]
            root={'game_id':game,'case_ids':ids,'path_keys':paths,'fen':f'AUTHORED-FEN-{game}',
                'source_ordinal':i,'pair':[{'uci':'e7e5','successor_key':paths[2]},
                    {'uci':'c7c5','successor_key':paths[3]}]}
            roots.append(root);keys.update(paths);games.add(game)
            for case,mode in zip(ids,s.MODES):
                pv=['c7c5','g1f3','d7d6'] if mode=='selected_b' else ['e7e5','g1f3','b8c6']
                teacher_paths=[f'teacher-{case}-{j}' for j in range(3)];keys.update(teacher_paths)
                rows.append({'case_id':case,'group_id':game,'split':split,'mode':mode,'status':'completed',
                    'fen':root['fen'],'selected_uci':None if mode=='free' else pv[0],
                    'teacher_move_uci':pv[0],'reference_pv':pv,'teacher_path_keys':teacher_paths})
        dataset['groups'][split]=roots
    return dataset,{'rows':rows},{'games':['historical-game'],'board_keys':['historical-key']},\
        {'games':list(games),'board_keys':list(keys)}


def selected_metadata():
    d,t,i,r=metadata_fixture();owners,by=s.ownership(d,t,i,r);roots=d['groups']['reserve']
    return roots,by,owners,{root['game_id'] for root in roots[:16]}


def choose(roots,by,owners,spent,exposed=set(),history=set(),predicate=lambda row:True):
    return s.choose(roots,by,owners,history,spent,exposed,predicate)


def test_exact_four_role_denominator_and_teacher_lengths():
    d,t,i,r=metadata_fixture();owners,by=s.ownership(d,t,i,r)
    assert sum(len(root['path_keys']) for roots in d['groups'].values() for root in roots)==4224
    assert len(by)==3168 and owners['historical-key']=={('historical',None)}


@pytest.mark.parametrize('value',[None,[],['only'],['a','b','c'],['a','b','c','c'],['a','b','c','']])
def test_missing_empty_or_duplicate_root_roles_reject(value):
    d,t,i,r=metadata_fixture();d['groups']['reserve'][0]['path_keys']=value
    with pytest.raises(ValueError):s.ownership(d,t,i,r)


@pytest.mark.parametrize('value',[None,[],['one'],['a','b'],['a','b','c','d'],['a','b','b']])
def test_missing_or_wrong_teacher_paths_reject(value):
    d,t,i,r=metadata_fixture();t['rows'][0]['teacher_path_keys']=value
    with pytest.raises(ValueError):s.ownership(d,t,i,r)


def test_short_teacher_path_allowed_only_with_same_original_pv_length():
    d,t,i,r=metadata_fixture();row=t['rows'][0]
    removed=row['teacher_path_keys'][1:];row['teacher_path_keys']=row['teacher_path_keys'][:1];row['reference_pv']=row['reference_pv'][:1]
    r['board_keys']=[key for key in r['board_keys'] if key not in removed]
    s.ownership(d,t,i,r)
    row['reference_pv']=[]
    with pytest.raises(ValueError):s.ownership(d,t,i,r)


def test_both_empty_role_lists_cannot_make_ownership_vacuous():
    roots,by,owners,spent=selected_metadata();root=roots[16];root['path_keys']=[]
    for case in root['case_ids']:by[case]['teacher_path_keys']=[]
    with pytest.raises(ValueError):choose(roots,by,{},spent)


def test_choose_rejects_empty_teacher_roles_with_valid_root_roles():
    roots,by,owners,spent=selected_metadata();by[roots[16]['case_ids'][0]]['teacher_path_keys']=[]
    with pytest.raises(ValueError):choose(roots,by,owners,spent)


def test_first_unused_order_all512_and_no_spent_teacher_access():
    roots,by,owners,spent=selected_metadata()
    for root in roots[:16]:
        for case in root['case_ids']:by.pop(case)
    selected,ledger=choose(list(reversed(roots)),by,owners,spent)
    assert selected==roots[16:32] and len(ledger['rows'])==512
    assert ledger['reason_counts']=={'spent_game':16,'selected':16,'eligible_unused_reserve':480}


@pytest.mark.parametrize('kind',['historical','train','other_reserve','missing'])
def test_foreign_or_missing_owner_rejects_root(kind):
    roots,by,owners,spent=selected_metadata();key=roots[16]['path_keys'][0]
    if kind=='missing':owners.pop(key)
    else:owners[key].add((kind,'foreign'))
    selected,ledger=choose(roots,by,owners,spent)
    assert selected==roots[17:33] and ledger['rows'][16]['reason']=='foreign_or_unproved_path_owner'


def test_generated_path_exclusion_before_reference_callback():
    roots,by,owners,spent=selected_metadata();case=roots[16]['case_ids'][2]
    def validator(row):
        assert row['case_id']!=case
        return True
    selected,ledger=choose(roots,by,owners,spent,{by[case]['teacher_path_keys'][0]},predicate=validator)
    assert selected==roots[17:33] and ledger['rows'][16]['reason']=='post_corpus_generated_path_overlap'


@pytest.mark.parametrize('field,value',[('fen','STALE'),('selected_uci','e7e6'),
    ('teacher_move_uci','e7e6'),('mode','selected_b'),('split','reserve')])
def test_original_task_role_identity_is_required(field,value):
    d,t,i,r=metadata_fixture();t['rows'][1][field]=value
    with pytest.raises(ValueError):s.ownership(d,t,i,r)


def legal_fixture():
    rule=s.rules();roots=[];by={};before=chess.Board();setup=chess.Move.from_uci('e2e4')
    current=before.copy(stack=False);current.push(setup)
    def paths(pv):
        board=current.copy(stack=False);keys=[]
        for text in pv:board.push_uci(text);keys.append(rule['key'](board.fen()))
        return keys
    lines=[['e7e5','g1f3','b8c6'],['e7e5','g1f3','b8c6'],['c7c5','g1f3','d7d6']]
    roles=[rule['key'](before.fen()),rule['key'](current.fen()),paths(lines[1])[0],paths(lines[2])[0]]
    for index in range(16):
        game=f'authored-rule-fixture-{index:02d}';ids=[f'{game}:{mode}' for mode in s.MODES]
        root={'game_id':game,'case_ids':ids,'fen':current.fen(),'source_before_fen':before.fen(),
            'setup_uci':'e2e4','source_ordinal':index,'path_keys':list(roles),
            'pair':[{'uci':lines[j][0],'successor_key':roles[j+1]} for j in (1,2)]}
        roots.append(root)
        for case,mode,pv in zip(ids,s.MODES,lines):
            by[case]={'case_id':case,'group_id':game,'split':'reserve','mode':mode,'fen':root['fen'],
                'status':'completed','selected_uci':None if mode=='free' else pv[0],
                'teacher_move_uci':pv[0],'reference_pv':list(pv),'teacher_path_keys':paths(pv)}
    # Repeated positions are deliberate API fixtures, never a fresh-cohort proof.
    return roots,by


def formatting(root,by,targets):
    assert targets is False
    rule=s.rules();values=[];truth=[]
    for case,mode in zip(root['case_ids'],s.MODES):
        task=by[case];packet={'fen':root['fen']}
        if mode!='free':packet['selected_uci']=task['selected_uci']
        values.append({'case_id':case,'group_id':root['game_id'],'mode':mode,'input':packet})
        truth.append(rule['expected_reference'](root,task))
    return values,truth


def test_exact_export48_and_originals_untouched():
    roots,by=legal_fixture();snapshot=copy.deepcopy((roots,by))
    values,refs=s.export_rows(roots,by,formatting)
    assert len(values)==len(refs)==48 and (roots,by)==snapshot
    assert set(values[0]['input'])=={'fen'} and values[1]['input']['selected_uci']=='e7e5'
    assert refs[0]['check_role'] is None and refs[1]['check_role'] is False
    assert s.export_rows(roots,by)==(values,refs)


def test_joint_callback_input_and_reference_mutation_cannot_rebind_original_selected():
    roots,by=legal_fixture()
    def joint(root,tasks,targets):
        case=root['case_ids'][1];task=tasks[case]
        task.update(selected_uci='d7d5',teacher_move_uci='d7d5',reference_pv=['d7d5','g1f3','g8f6'])
        board=chess.Board(root['fen']);task['teacher_path_keys']=[]
        for text in task['reference_pv']:board.push_uci(text);task['teacher_path_keys'].append(s.rules()['key'](board.fen()))
        return formatting(root,tasks,targets)
    with pytest.raises(ValueError,match='packets'):s.export_rows(roots,by,joint)


def test_different_legal_pv_with_same_given_move_rejected():
    roots,by=legal_fixture()
    def different(root,tasks,targets):
        task=tasks[root['case_ids'][1]];task['reference_pv']=['e7e5','g1f3','g8f6']
        board=chess.Board(root['fen']);task['teacher_path_keys']=[]
        for text in task['reference_pv']:board.push_uci(text);task['teacher_path_keys'].append(s.rules()['key'](board.fen()))
        return formatting(root,tasks,targets)
    with pytest.raises(ValueError,match='Reference'):s.export_rows(roots,by,different)


@pytest.mark.parametrize('fault',['free_given','extra_context','extra_ref','capture','checker','later_fact','facts_shape','selected_ref'])
def test_packets_and_exact_reference_fact_invariants(fault):
    roots,by=legal_fixture()
    def mutate(*args):
        values,refs=formatting(*args)
        if fault=='free_given':values[0]['input']['selected_uci']='e7e5'
        elif fault=='extra_context':values[0]['input']['pv']=['e7e5']
        elif fault=='extra_ref':refs[0]['new_truth']='invented'
        elif fault=='capture':refs[0]['facts']['capture']=True
        elif fault=='checker':refs[0]['facts']['checkers']=['e8']
        elif fault=='later_fact':refs[0]['per_ply_facts'][2]['mover']='king'
        elif fault=='facts_shape':refs[0]['facts'].pop('victim_color')
        else:refs[1]['selected_uci']='d7d5'
        return values,refs
    with pytest.raises(ValueError):s.export_rows(roots,by,mutate)


def test_callback_cannot_mutate_sources_through_arguments_or_external_alias():
    roots,by=legal_fixture();before=copy.deepcopy((roots,by))
    def mutate_copy(root,tasks,targets):
        values,refs=formatting(root,tasks,targets);root['fen']='changed';tasks.clear();return values,refs
    s.export_rows(roots,by,mutate_copy);assert (roots,by)==before
    def external(*args):
        values,refs=formatting(*args);by[roots[0]['case_ids'][0]]['reference_pv'][2]='g8f6';return values,refs
    with pytest.raises(ValueError,match='mutated original'):s.export_rows(roots,by,external)


def test_root_roles_and_stored_teacher_successors_reconstructed_not_trusted():
    roots,by=legal_fixture();roots[0]['path_keys'][0]='FAKE BEFORE ROLE'
    with pytest.raises(ValueError,match='roles'):s.export_rows(roots,by)
    roots,by=legal_fixture();by[roots[0]['case_ids'][0]]['teacher_path_keys'][2]='FAKE TEACHER ROLE'
    with pytest.raises(ValueError,match='successor'):s.export_rows(roots,by)


@pytest.mark.parametrize('fen,uci,expected',[
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6',{'en_passant':True,'capture':True,'victim':'pawn','victim_square':'d5','victim_color':'black'}),
    ('4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1','e4d3',{'en_passant':True,'capture':True,'victim':'pawn','victim_square':'d4','victim_color':'white'}),
    ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1','a7a8q',{'promotion':'queen','gives_check':True}),
    ('4k3/8/8/8/8/8/8/4K2R w K - 0 1','e1g1',{'castling':True,'mover':'king'}),
    ('4k3/8/8/8/8/8/4B3/4R1K1 w - - 0 1','e2f3',{'gives_check':True,'discovered_or_double_check':True,'checkers':['e1']}),
    ('7k/5Q2/6K1/8/8/8/8/8 w - - 0 1','f7g7',{'gives_check':True,'checkmate':True,'automatic_game_over':True})])
def test_pinned_rule_reconstruction_special_moves(fen,uci,expected):
    facts=s.rules()['fact'](chess.Board(fen),chess.Move.from_uci(uci))
    assert {key:facts[key] for key in expected}==expected


def test_gameover_illegal_pv_and_pinned_helper_tamper_reject(monkeypatch):
    rule=s.rules();b=chess.Board('7k/5Q2/6K1/8/8/8/8/8 w - - 0 1');b.push_uci('f7g7')
    with pytest.raises(ValueError):rule['fact'](b,chess.Move.from_uci('h8h7'))
    roots,by=legal_fixture();by[roots[0]['case_ids'][0]]['reference_pv'][2]='e8e6'
    with pytest.raises(ValueError):s.export_rows(roots,by)
    monkeypatch.setattr(s,'RULES_SHA256','0'*64)
    with pytest.raises(ValueError,match='reconstructor'):s.rules()


def test_no_learning_framework_imported():
    assert not {'torch','transformers','peft','bitsandbytes','accelerate'}&set(sys.modules)
