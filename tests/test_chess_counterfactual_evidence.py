"""Software controls on real dev inputs; fake engine output is never quality evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import chess
import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('counterfactual', ROOT / 'scripts/chess_counterfactual_evidence.py')
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)
DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'


class FakeEngine:
    id = {'name': 'Synthetic test double, not a real engine observation'}

    def __init__(self, fail_index=None):
        self.calls = []
        self.options = None
        self.fail_index = fail_index

    def configure(self, options):
        self.options = options

    def analysis(self, *args, **kwargs):
        from test_chess_counterfactual_streaming import RawStream
        return RawStream(self.analyse(*args, **kwargs))

    def close(self):
        pass

    def analyse(self, board, limit, *, multipv, game):
        self.calls.append((board.copy(stack=True), limit, multipv, game))
        if len(self.calls) == self.fail_index:
            raise chess.engine.EngineError('synthetic engine failure')
        moves = sorted(board.legal_moves, key=lambda move: move.uci())[:2]
        return [{'pv': [move], 'score': chess.engine.PovScore(chess.engine.Cp(12 - index), board.turn),
                 'nodes': 100003, 'depth': 4, 'multipv': index + 1}
                for index, move in enumerate(moves)]


def receipt():
    return cf.collect_receipt(DATA, FakeEngine(), cf.ENGINE_SHA256)


def test_eight_real_dev_cases_two_distinct_candidates_full_setup_history_and_frozen_budget():
    engine = FakeEngine()
    result = cf.collect_receipt(DATA, engine, cf.ENGINE_SHA256)
    assert cf.verify_receipt(DATA, result)['complete'] is True
    assert result['requested_positions'] == len(result['results']) == len(engine.calls) == 8
    assert engine.options == {'Threads': 1, 'Hash': 16}
    assert all(len(board.move_stack) == 1 and limit.nodes == 100000 and multipv == 2
               for board, limit, multipv, game in engine.calls)
    assert len({game for board, limit, multipv, game in engine.calls}) == 8
    assert all(row['split'] == 'dev' and len(row['candidates']) == 2 for row in result['results'])
    assert all(row['candidates'][0]['move_uci'] != row['candidates'][1]['move_uci'] for row in result['results'])
    assert all(candidate['nodes_observed'] == 100003 for row in result['results'] for candidate in row['candidates'])
    source = json.loads((DATA / 'manifest.json').read_bytes())
    text = json.dumps(result)
    for case in source['items']:
        if case['split'] != 'dev':
            assert case['position_id'] not in text and case['fen'] not in text
    for key in ('target_move', 'solution_uci', 'themes', 'rating'):
        assert f'"{key}"' not in text


@pytest.mark.parametrize('mutation', ['illegal_pv', 'foreign_reference', 'reversed_perspective', 'mate_as_cp',
                                      'missing_candidate', 'duplicate_candidate', 'foreign_position',
                                      'source_hash', 'engine_hash', 'missing_case', 'fabricated_fact'])
def test_invalid_evidence_cannot_verify(mutation):
    value = receipt()
    case, candidate = value['results'][0], value['results'][0]['candidates'][0]
    if mutation == 'illegal_pv': candidate['pv_uci'] = ['a1a8']
    elif mutation == 'foreign_reference': candidate['evidence_id'] = value['results'][1]['candidates'][0]['evidence_id']
    elif mutation == 'reversed_perspective': candidate['score']['side_to_move'] = 'black' if candidate['score']['side_to_move'] == 'white' else 'white'
    elif mutation == 'mate_as_cp': candidate['score']['mate_in'] = 3
    elif mutation == 'missing_candidate': case['candidates'].pop()
    elif mutation == 'duplicate_candidate': case['candidates'][1] = copy.deepcopy(candidate)
    elif mutation == 'foreign_position': case['position_id'] = 'foreign-position'
    elif mutation == 'source_hash': value['source_manifest_sha256'] = '0' * 64
    elif mutation == 'engine_hash': value['engine']['sha256'] = '0' * 64
    elif mutation == 'missing_case': value['results'].pop()
    elif mutation == 'fabricated_fact': candidate['transition']['gives_check'] = not candidate['transition']['gives_check']
    with pytest.raises(ValueError):
        cf.verify_receipt(DATA, value)


def test_failure_keeps_all_requested_cases_and_cannot_report_completion():
    engine = FakeEngine(fail_index=3)
    value = cf.collect_receipt(DATA, engine, cf.ENGINE_SHA256)
    checked = cf.verify_receipt(DATA, value)
    assert len(value['results']) == 8 and checked['failed_positions'] == 6
    assert checked['complete'] is False and checked['successful_positions'] == 2
    assert value['results'][2]['status'] == 'failed' and value['results'][2]['candidates'] == []
    assert len(engine.calls) == 3
    assert all(row['error']['message'] == 'engine_session_closed_after_stream_failure'
               for row in value['results'][3:])


@pytest.mark.parametrize('bound', ['lowerbound', 'upperbound'])
def test_qualified_engine_score_is_an_explicit_failed_case_not_an_unqualified_value(bound):
    class BoundEngine(FakeEngine):
        def analyse(self, *args, **kwargs):
            infos = super().analyse(*args, **kwargs)
            infos[0][bound] = True
            return infos
    value = cf.collect_receipt(DATA, BoundEngine(), cf.ENGINE_SHA256)
    checked = cf.verify_receipt(DATA, value)
    assert checked['complete'] is False and checked['failed_positions'] == 8
    assert len(value['results']) == 8
    assert all(row['candidates'] == [] and row['error']['message'] == 'engine_bound_score_not_supported'
               for row in value['results'])


def test_score_conversion_preserves_side_and_distinct_cp_mate_types():
    board = chess.Board(); board.push_uci('e2e4')
    cp = cf.typed_score(chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE), board.turn)
    mate = cf.typed_score(chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE), board.turn)
    assert cp == {'type': 'cp', 'value': -30, 'perspective': 'side_to_move', 'side_to_move': 'black'}
    assert mate == {'type': 'mate', 'value': -3, 'perspective': 'side_to_move', 'side_to_move': 'black'}
    # MateGiven versus being checkmated must remain distinguishable, even though mate() returns zero for both.
    given = cf.typed_score(chess.engine.PovScore(chess.engine.MateGiven, chess.WHITE), chess.WHITE)
    lost = cf.typed_score(chess.engine.PovScore(chess.engine.Mate(0), chess.WHITE), chess.WHITE)
    assert given['mate_zero'] == 'delivered' and lost['mate_zero'] == 'received'


@pytest.mark.parametrize('fen,move,captured,promotion,castle,check', [
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6', 'pawn', None, False, False),
    ('4k2r/6P1/8/8/8/8/8/4K3 w - - 0 1', 'g7h8q', 'rook', 'queen', False, True),
    ('4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1', 'e1g1', None, None, True, False),
])
def test_recomputed_special_move_facts(fen, move, captured, promotion, castle, check):
    facts = cf.transition_evidence(chess.Board(fen), chess.Move.from_uci(move))
    assert facts['captured_piece'] == captured and facts['promotion'] == promotion
    assert facts['castling'] is castle and facts['gives_check'] is check
    if captured: assert facts['material_delta']['black'][captured] == -1
    if promotion:
        assert facts['material_delta']['white']['pawn'] == -1
        assert facts['material_delta']['white']['queen'] == 1
    if move == 'e5d6': assert facts['en_passant'] is True and facts['captured_square'] == 'd5'


def test_ids_are_stable_and_output_cannot_overwrite_existing_evidence(tmp_path):
    first, second = receipt(), receipt()
    assert [[c['evidence_id'] for c in r['candidates']] for r in first['results']] == [[c['evidence_id'] for c in r['candidates']] for r in second['results']]
    output = tmp_path / 'receipt.json'
    cf.write_receipt(first, output)
    before = output.read_bytes()
    with pytest.raises(FileExistsError): cf.write_receipt(second, output)
    assert output.read_bytes() == before
