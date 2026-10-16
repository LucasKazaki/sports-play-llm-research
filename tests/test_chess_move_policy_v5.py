"""Behavioral software checks; no GPU, real source selection, or teacher calls."""
import copy
import json
from types import SimpleNamespace
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_move_policy_v5 as policy


def counts(train=1):
    return dict(train=train, development=0, holdout=0, rollout=0)


def source(game='abcdefgh', puzzle='Abc12', moves=(), setup='e2e4', tail='invalid solution ignored'):
    board = chess.Board()
    for move in moves:
        board.push_uci(move)
    return ({'source_ordinal': 0, 'row_group': 0, 'row_in_group': 0},
            {'GameId': game, 'PuzzleId': puzzle, 'FEN': board.fen(), 'Moves': setup+' '+tail})


def test_source_solution_tail_is_never_consumed_or_stored(monkeypatch):
    monkeypatch.setattr(policy, 'split_for', lambda *_: 'train')
    a, _ = policy.select_rows([source(tail='garbage answer')], counts(), 1, set(), set(), 10)
    b, _ = policy.select_rows([source(tail='e7e5 g1f3')], counts(), 1, set(), set(), 10)
    assert a == b
    assert 'Moves' not in a['train'][0] and 'theme' not in a['train'][0]


def test_one_original_game_cannot_cross_or_repeat_in_cohort(monkeypatch):
    monkeypatch.setattr(policy, 'split_for', lambda *_: 'train')
    rows = [source(), source(puzzle='Abc13', moves=('e2e4',), setup='e7e5'),
            source(game='ijklmnop', puzzle='Abc14', moves=('e2e4','e7e5'), setup='g1f3')]
    selected, audit = policy.select_rows(rows, counts(2), 1, set(), set(), 10)
    assert [r['game_id'] for r in selected['train']] == ['abcdefgh', 'ijklmnop']
    assert audit['rejections']['excluded_game'] == 1


@pytest.mark.parametrize('role', ['before', 'current'])
def test_excluded_before_or_current_board_cannot_enter_any_split(monkeypatch, role):
    monkeypatch.setattr(policy, 'split_for', lambda *_: 'train')
    board = chess.Board()
    if role == 'current':
        board.push_uci('e2e4')
    with pytest.raises(ValueError, match='cannot fill'):
        policy.select_rows([source()], counts(), 1, set(), {policy.board_key(board.fen())}, 10)


def test_balanced_pair_exclusion_includes_both_successors():
    games, boards = set(), set()
    row = {'game_id': 'abcdefgh', 'fen': chess.STARTING_FEN,
           'source_before_fen': chess.STARTING_FEN, 'selected_pair': ['e2e4','d2d4']}
    policy.add_roles(row, games, boards)
    assert games == {'abcdefgh'}
    for move in row['selected_pair']:
        board = chess.Board()
        board.push_uci(move)
        assert policy.board_key(board.fen()) in boards
    assert len(boards) == 3


def test_illegal_retained_exclusion_move_stops_instead_of_weakening_registry():
    with pytest.raises(ValueError, match='exclusion move'):
        policy.add_roles({'game_id':'abcdefgh','fen':chess.STARTING_FEN,
                          'selected_pair':['a1a8']}, set(), set())


def test_source_cap_never_replenishes_with_later_answers(monkeypatch):
    monkeypatch.setattr(policy, 'split_for', lambda *_: 'train')
    with pytest.raises(ValueError, match='cannot fill'):
        policy.select_rows([source(game='abcdefgh'),source(game='ijklmnop',puzzle='X')],
                           counts(), 1, {'abcdefgh'}, set(), 1)


def test_split_is_deterministic_and_each_bucket_has_one_owner():
    values = [policy.split_for(f'game{i:04d}', 4082050) for i in range(2000)]
    assert set(values) == set(policy.SPLITS)
    assert values == [policy.split_for(f'game{i:04d}', 4082050) for i in range(2000)]


def references(pv=('e2e4','e7e5','g1f3')):
    return [{'id':'one','fen':chess.STARTING_FEN,'status':'completed','reference_pv':list(pv)}]


def test_raw_forecast_uses_predicted_board_and_scores_three_prefixes():
    moves, seen = iter(['e2e4','e7e5','g1f3']), []
    def predict(fen):
        seen.append(fen)
        return next(moves)
    raw = policy.forecast_rows([{'id':'one','fen':chess.STARTING_FEN}], predict)
    assert chess.Board(seen[1]).piece_at(chess.E4) == chess.Piece(chess.PAWN,chess.WHITE)
    assert policy.score_forecasts(raw, references())['prefix']['3']['exact'] == 1
    assert raw[0]['legal_plies'] == 3


def test_legal_divergent_continuation_is_not_teacher_prefix_match():
    moves = iter(['e2e4','c7c5','g1f3'])
    raw = policy.forecast_rows([{'id':'one','fen':chess.STARTING_FEN}], lambda _: next(moves))
    score = policy.score_forecasts(raw, references())
    assert [score['prefix'][str(k)]['exact'] for k in (1,2,3)] == [1,0,0]
    assert score['prefix']['3']['legal_through_ply'] == 1


def test_illegal_raw_choice_is_not_rescued_and_stops_future_calls():
    seen = []
    def predict(fen):
        seen.append(fen)
        return 'a1a8'
    raw = policy.forecast_rows([{'id':'one','fen':chess.STARTING_FEN}], predict)
    assert len(seen) == 1 and raw[0]['status'] == 'illegal_move'
    assert raw[0]['legal_plies'] == 0 and raw[0]['predicted'] == ['a1a8']
    assert policy.score_forecasts(raw, references())['prefix']['1']['exact'] == 0


def test_model_exception_and_missing_reference_remain_in_original_denominator():
    def fail(_):
        raise RuntimeError('deliberate software fixture')
    raw = policy.forecast_rows([{'id':'one','fen':chess.STARTING_FEN}], fail)
    ref = references()
    ref[0].update(status='failed',reference_pv=[])
    score = policy.score_forecasts(raw, ref)
    assert score['planned'] == 1 and score['status'] == {'failed':1}
    assert score['prefix']['3'] == {'teacher_supported':0,'exact':0,
                                   'all_planned_denominator':1,'legal_through_ply':0}


def test_terminal_board_is_game_over_without_calling_model():
    board = chess.Board()
    for move in ('f2f3','e7e5','g2g4','d8h4'):
        board.push_uci(move)
    raw = policy.forecast_rows([{'id':'one','fen':board.fen()}], lambda _: pytest.fail('terminal model call'))
    assert raw[0]['status'] == 'game_over' and raw[0]['legal_plies'] == 0


def test_reordered_or_missing_prediction_records_are_not_silently_joined():
    with pytest.raises(ValueError, match='denominator'):
        policy.score_forecasts([], references())


def test_selection_uses_raw_teacher_agreement_legality_then_earliest():
    results = {0:{'raw_top1_match_count':3,'raw_legal_count':5},
               256:{'raw_top1_match_count':3,'raw_legal_count':5},
               512:{'raw_top1_match_count':2,'raw_legal_count':7}}
    assert max(results,key=lambda k:policy.previous.selection_key(k,results[k])) == 0
    results[512]['raw_top1_match_count'] = 3
    assert max(results,key=lambda k:policy.previous.selection_key(k,results[k])) == 512


def test_teacher_uses_final_individual_event_without_sticky_bound_flags(monkeypatch,tmp_path):
    early = {'score':chess.engine.PovScore(chess.engine.Cp(35),chess.WHITE),
             'pv':[chess.Move.from_uci('e2e4')], 'lowerbound':True, 'depth':8}
    final = {'score':chess.engine.PovScore(chess.engine.Cp(21),chess.WHITE),
             'pv':[chess.Move.from_uci(x) for x in ('e2e4','e7e5')], 'nodes':50000, 'depth':12}
    class Context:
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def __iter__(self): return iter([early,final])
        def wait(self): return SimpleNamespace(move=chess.Move.from_uci('e2e4'))
    class Engine(Context):
        id={'name':'Stockfish19 fixture'}
        def configure(self,settings): assert settings == {'Threads':1,'Hash':32}
        def analysis(self,*args,**kwargs): return Context()
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**kw:Engine())
    path=tmp_path/'chunk.jsonl'
    result=policy.teacher_chunk('fixture',{'hash_mb':32,'nodes':50000},
            [('train',{'id':'one','fen':chess.STARTING_FEN})],path,tmp_path/'CANCEL')
    assert result[0][1]['status']=='completed'
    assert result[0][1]['score']['lowerbound'] is False
    assert result[0][1]['score']['cp']==21
    assert json.loads(path.read_text())['record']==result[0][1]


def test_score_pv_must_match_actual_final_bestmove():
    board=chess.Board()
    event={'score':chess.engine.PovScore(chess.engine.Cp(10),chess.WHITE),
           'pv':[chess.Move.from_uci('d2d4')]}
    with pytest.raises(ValueError,match='disagree'):
        policy.teacher_observation(board,event,chess.Move.from_uci('e2e4'))


def test_worker_failure_recovers_completed_calls_and_keeps_unknown_rows(tmp_path):
    rows=[('train',{'id':'one','fen':chess.STARTING_FEN}),('holdout',{'id':'two','fen':chess.STARTING_FEN})]
    journal=tmp_path/'chunk.jsonl'
    retained={'id':'one','status':'completed','teacher_move_uci':'e2e4','reference_pv':['e2e4']}
    journal.write_text(json.dumps({'split':'train','record':retained})+'\n{torn')
    result=policy.recovered_chunk(rows,journal,RuntimeError())
    assert result[0][1]==retained
    assert result[1][1]['status']=='not_run' and result[1][1]['teacher_move_uci'] is None


@pytest.mark.parametrize('result',[{'failure_count':1,'model_failure_stop':None},
                                  {'failure_count':0,'model_failure_stop':'backend_error'}])
def test_failed_evaluation_latches_before_any_new_backend_call(monkeypatch,result):
    calls=[]
    monkeypatch.setattr(policy.previous,'evaluate',lambda *a,**kw:calls.append(1) or result)
    with pytest.raises(RuntimeError,match='prohibit further'):
        policy.checked_evaluate('fixture')
    assert len(calls)==1


def test_owned_cancel_is_checked_before_resource_sample(tmp_path):
    (tmp_path/'CANCEL').touch()
    with pytest.raises(InterruptedError):
        policy.resource_check(tmp_path,{'maximum_seconds':7200},policy.time.perf_counter())


def test_forecast_backend_failure_latches_across_all_remaining_root_ids():
    calls=[]
    def fail(_):
        calls.append(1)
        raise RuntimeError('synthetic backend failure')
    rows=[{'id':str(i),'fen':chess.STARTING_FEN} for i in range(3)]
    result=policy.forecast_rows(rows,fail)
    assert calls==[1]
    assert [r['id'] for r in result]==['0','1','2']
    assert [r['status'] for r in result]==['failed','not_run','not_run']


def test_rollout_persists_complete_failure_evidence_then_stops(tmp_path):
    torch=pytest.importorskip('torch')
    from chess_classifier_adapter import native_vocab,expected_action_space
    class BrokenModel:
        calls=0
        def eval(self): return self
        def __call__(self,**kwargs):
            self.calls+=1
            raise RuntimeError('synthetic CPU backend')
    model=BrokenModel()
    rows=[{'id':str(i),'fen':chess.STARTING_FEN,'status':'completed',
           'reference_pv':['e2e4','e7e5','g1f3']} for i in range(3)]
    with pytest.raises(RuntimeError,match='further backend calls prohibited'):
        policy.rollout(model,rows,{'vocab':native_vocab(),'id2label':expected_action_space()},'cpu','fixture',tmp_path)
    assert model.calls==1
    assert len(policy.read(tmp_path/'fixture-rollout-raw.json')['rows'])==3
    score=policy.read(tmp_path/'fixture-rollout-score.json')
    assert score['planned']==3 and score['status']=={'failed':1,'not_run':2}


def test_training_amendment_requires_exact_completed_labels_and_source_snapshot(tmp_path):
    for name in ('dataset.json','labels.json','label-completed.json'):
        (tmp_path/name).write_text('{}')
    (tmp_path/'label-executed-sources').mkdir()
    (tmp_path/'label-executed-sources/manifest.json').write_text('{}')
    protocol=tmp_path/'protocol.json'
    protocol.write_text('{"amended":true}')
    accepted={'protocol_sha256':'old','labels_sha256':policy.sha(tmp_path/'labels.json'),
              'completed_receipt_sha256':policy.sha(tmp_path/'label-completed.json'),
              'executed_source_manifest_sha256':policy.sha(tmp_path/'label-executed-sources/manifest.json')}
    labels={'dataset_sha256':policy.sha(tmp_path/'dataset.json'),'protocol_sha256':'old'}
    policy.verify_label_binding({'accepted_labels':accepted},protocol,labels,tmp_path)
    (tmp_path/'labels.json').write_text('{"altered":true}')
    with pytest.raises(ValueError,match='binding mismatch'):
        policy.verify_label_binding({'accepted_labels':accepted},protocol,labels,tmp_path)
