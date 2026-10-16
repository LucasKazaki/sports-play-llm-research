"""Authored ownership fixtures; no private corpus, model, engine or OS probe."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('fresh_held_selection_v1',Path(__file__).with_name('selection.py'))
selection=importlib.util.module_from_spec(spec);spec.loader.exec_module(selection)


def fixture():
    roots=[];teachers={};owners={}
    for i in range(512):
        game=f'authored{i:04d}';cases=[f'{game}:{mode}' for mode in selection.MODES]
        root={'game_id':game,'source_ordinal':i,'case_ids':cases,'path_keys':[f'root-{i}'],'fen':f'root-fen-{i}'}
        roots.append(root)
        owners[f'root-{i}']={('reserve',game)}
        for case in cases:
            teachers[case]={'teacher_path_keys':[f'teacher-{case}'],'valid':True}
            owners[f'teacher-{case}']={('reserve',game)}
    return roots,teachers,owners,{r['game_id']for r in roots[:16]}


def choose(roots,teachers,owners,spent,exposed=set(),history=set(),validator=lambda row:row['valid']):
    return selection.choose(roots,teachers,owners,history,spent,exposed,validator)


def test_first16_unused_and_all512_accounted_without_spent_reference_access():
    roots,t,owners,spent=fixture()
    for r in roots[:16]:
        for case in r['case_ids']:t[case].pop('valid')
    selected,ledger=choose(roots,t,owners,spent)
    assert selected==roots[16:32] and ledger['selected']==16 and len(ledger['rows'])==512
    assert ledger['reason_counts']=={'spent_game':16,'selected':16,'eligible_unused_reserve':480}


@pytest.mark.parametrize('kind',['historical','other_reserve','training','missing'])
def test_own_role_never_erases_foreign_or_unknown_owner(kind):
    roots,t,owners,spent=fixture();key=roots[16]['path_keys'][0]
    if kind=='missing':owners.pop(key)
    else:owners[key].add((kind,None if kind=='historical'else'foreign-game'))
    selected,ledger=choose(roots,t,owners,spent)
    assert roots[16]not in selected and selected==roots[17:33]
    assert ledger['rows'][16]['reason']=='foreign_or_unproved_path_owner'


def test_generated_tail_overlap_rejects_before_reference_visit():
    roots,t,owners,spent=fixture();case=roots[16]['case_ids'][2];t[case].pop('valid')
    selected,ledger=choose(roots,t,owners,spent,{t[case]['teacher_path_keys'][0]})
    assert selected==roots[17:33]
    assert ledger['rows'][16]['reason']=='post_corpus_generated_path_overlap'


def test_shortage_retains_full_denominator_and_refuses_export():
    roots,t,owners,spent=fixture()
    for r in roots[31:]:
        for case in r['case_ids']:t[case]['valid']=False
    selected,ledger=choose(roots,t,owners,spent)
    assert ledger['status']=='insufficient_cohort' and len(selected)==15 and len(ledger['rows'])==512
    with pytest.raises(ValueError,match='Never shrink'):selection.export_rows(selected,t,None)


def test_source_order_is_fixed_and_no_selected_response_quality_input_exists():
    roots,t,owners,spent=fixture()
    selected,_=choose(list(reversed(roots)),t,owners,spent)
    assert selected==roots[16:32]


@pytest.mark.parametrize('delta',[1,-1])
def test_exact_spent_scope_required(delta):
    roots,t,owners,spent=fixture()
    if delta==1:spent.add(roots[16]['game_id'])
    else:spent.pop()
    with pytest.raises(ValueError,match='Exact failed16'):choose(roots,t,owners,spent)


def test_duplicate_reserve_game_rejected():
    roots,t,owners,spent=fixture();roots[-1]['game_id']=roots[-2]['game_id']
    with pytest.raises(ValueError,match='All512'):choose(roots,t,owners,spent)


def test_full_export_input_allowlist_and_conditioned_move_binding():
    roots,t,owners,spent=fixture();selected,_=choose(roots,t,owners,spent)
    def cases(root,by_case,targets):
        assert targets is False
        inputs=[];refs=[]
        for case,mode in zip(root['case_ids'],selection.MODES):
            packet={'fen':root['fen']}
            if mode!='free':packet['selected_uci']='e2e4'
            inputs.append({'case_id':case,'group_id':root['game_id'],'mode':mode,'input':packet})
            refs.append({'case_id':case,'group_id':root['game_id'],'selected_uci':'e2e4','reference_pv_uci':['e2e4','e7e5','g1f3']})
        return inputs,refs
    inputs,refs=selection.export_rows(selected,t,cases)
    assert len(inputs)==len(refs)==48
    def leaking(*args):
        inputs,refs=cases(*args);inputs[0]['input']['pv']=['future'];return inputs,refs
    with pytest.raises(ValueError,match='extra context'):selection.export_rows(selected,t,leaking)


def test_replay_stops_at_illegal_prefix_without_successor():
    class Board:
        def __init__(self):self.pushed=[];self.legal_moves={'a'}
        def fen(self):return 'root'if not self.pushed else'after-a'
        def is_game_over(self,claim_draw):return False
        def push(self,move):self.pushed.append(move)
    b=Board()
    class Native:
        @staticmethod
        def input_packet(packet):return packet,b
        @staticmethod
        def parse_output(packet,raw):return {'critical_line':{'steps':[
            {'legal':True,'raw_uci':'a','fen_after':'after-a'},
            {'legal':False,'raw_uci':'bad'},
            {'legal':True,'raw_uci':'never','fen_after':'invented'}]}}
    class Chess:
        class Move:
            @staticmethod
            def from_uci(value):return value
    assert selection.legal_generated_keys({'input':{'fen':'root'},'raw_text':'authored'},Native,Chess,lambda x:x)=={'root','after-a'}
    assert b.pushed==['a']


def full_ownership_fixture():
    dataset={'groups':{}};rows=[];keys={'historical-key'};games={'historical-game'}
    for split,count in [('train',512),('development',32),('reserve',512)]:
        roots=[]
        for i in range(count):
            game=f'{split}{i}';cases=[f'{game}:{mode}'for mode in selection.MODES]
            root={'game_id':game,'case_ids':cases,'path_keys':[f'root-{game}']};roots.append(root)
            keys.update(root['path_keys']);games.add(game)
            for case,mode in zip(cases,selection.MODES):
                path=f'tail-{case}';keys.add(path)
                rows.append({'case_id':case,'group_id':game,'split':split,'mode':mode,
                    'status':'completed','teacher_path_keys':[path]})
        dataset['groups'][split]=roots
    initial={'games':['historical-game'],'board_keys':['historical-key']}
    return dataset,{'rows':rows},initial,{'games':list(games),'board_keys':list(keys)}


def test_complete_role_union_preserves_history_and_distinct_game_owners():
    dataset,teachers,initial,reserved=full_ownership_fixture()
    first=dataset['groups']['reserve'][0];other=dataset['groups']['reserve'][1]
    first['path_keys'].append('historical-key');other['path_keys'].append(first['path_keys'][0])
    owners,by_case=selection.ownership(dataset,teachers,initial,reserved)
    assert owners['historical-key']=={('historical',None),('reserve',first['game_id'])}
    assert owners[first['path_keys'][0]]=={('reserve',first['game_id']),('reserve',other['game_id'])}
    assert len(by_case)==3168


@pytest.mark.parametrize('fault',['teacher_order','incomplete_teacher','game_union','board_union','repeated_game'])
def test_incomplete_or_incoherent_provenance_fails(fault):
    dataset,teachers,initial,reserved=full_ownership_fixture()
    if fault=='teacher_order':teachers['rows'][0],teachers['rows'][1]=teachers['rows'][1],teachers['rows'][0]
    elif fault=='incomplete_teacher':teachers['rows'][0]['status']='unknown'
    elif fault=='game_union':reserved['games'].append('unproved-game')
    elif fault=='board_union':reserved['board_keys'].append('unproved-key')
    else:dataset['groups']['reserve'][0]['game_id']=dataset['groups']['train'][0]['game_id']
    with pytest.raises(ValueError):selection.ownership(dataset,teachers,initial,reserved)
