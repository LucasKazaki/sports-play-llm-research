"""Real development bindings and explicitly synthetic software edge controls."""
import copy
from pathlib import Path
import sys

import chess
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_typed_position_evidence as adapter
import chess_extended_claims as extended

DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'


@pytest.fixture(scope='module')
def packet():
    return adapter.build_typed_position_evidence(DATA, SOURCE, SHA)


def check(packet, claim, row=None, candidate=None, **kwargs):
    row = row or packet['positions'][0]
    candidate = candidate or row['engine_evidence'][0]
    return extended.validate_extended_claim(DATA, kwargs.get('source', SOURCE), kwargs.get('sha', SHA),
        packet, kwargs.get('position_id', row['position_id']), kwargs.get('evidence_id', candidate['evidence_id']), claim)


def piece_claim(board, square, stage='before'):
    piece = board.piece_at(chess.parse_square(square))
    return {'kind': 'square_occupation', 'board': stage, 'square': square,
            'piece': None if piece is None else {'type': chess.piece_name(piece.piece_type),
                                               'color': chess.COLOR_NAMES[piece.color]}}


def variation(moves, origin='asserted_variation'):
    return {'kind': 'variation_legality', 'origin': origin, 'moves_uci': moves}


def test_real_occupations_before_and_after_all_16_selected_candidates(packet):
    seen = 0
    for row in packet['positions']:
        for candidate in row['engine_evidence']:
            board = chess.Board(row['fen'])
            move = chess.Move.from_uci(candidate['move_uci'])
            for stage in ('before', 'after_selected_move'):
                if stage == 'after_selected_move': board.push(move)
                for square in (chess.square_name(move.from_square), chess.square_name(move.to_square)):
                    result = check(packet, piece_claim(board, square, stage), row, candidate)
                    assert result['status'] == 'verified_board_fact'
                    assert result['evaluation_only'] and result['source_receipt_sha256'] == SHA
                    seen += 1
    assert seen == 64


def test_real_false_occupation_is_rejected_for_every_candidate(packet):
    for row in packet['positions']:
        for candidate in row['engine_evidence']:
            claim = {'kind': 'square_occupation', 'board': 'before',
                     'square': candidate['move_uci'][:2], 'piece': None}
            assert check(packet, claim, row, candidate)['reason'] == 'contradicted_by_replayed_occupation'


@pytest.mark.parametrize('field,value', [
    ('square', 'A1'), ('square', 'a9'), ('square', 1), ('square', ['a1']),
    ('board', 'future'), ('board', None), ('piece', True), ('piece', 'pawn'),
    ('piece', {'type': 'pawn', 'color': True}), ('piece', {'type': [], 'color': 'white'}),
    ('piece', {'type': 'pawn', 'color': 'white', 'rating': 2000}),
])
def test_occupation_schema_abstains(packet, field, value):
    claim = piece_claim(chess.Board(packet['positions'][0]['fen']), 'a1')
    claim[field] = value
    assert check(packet, claim)['status'] == 'abstain'


def test_real_retained_pvs_and_asserted_single_moves_are_different_claims(packet):
    for row in packet['positions']:
        for candidate in row['engine_evidence']:
            retained = check(packet, variation(candidate['pv_uci'], 'retained_engine_pv'), row, candidate)
            asserted = check(packet, variation([candidate['move_uci']]), row, candidate)
            assert retained['status'] == asserted['status'] == 'verified_legal_variation'
            assert retained['engine_attribution_verified'] is True
            assert asserted['engine_attribution_verified'] is False
            assert retained['legality_only'] and asserted['legality_only']
            assert not retained['engine_scores_independently_reproduced']


def test_real_legal_pv_prefix_must_not_claim_to_be_the_full_retained_pv(packet):
    row = next(r for r in packet['positions'] if any(len(c['pv_uci']) > 1 for c in r['engine_evidence']))
    candidate = next(c for c in row['engine_evidence'] if len(c['pv_uci']) > 1)
    prefix = [candidate['move_uci']]
    assert check(packet, variation(prefix, 'retained_engine_pv'), row, candidate)['reason'] == 'differs_from_retained_engine_pv'
    assert check(packet, variation(prefix), row, candidate)['status'] == 'verified_legal_variation'


@pytest.mark.parametrize('moves', [[], 'e2e4', None, [1], ['0000'], ['e2e9'], ['e2e4q'], ['e2e4'] * 65])
def test_invalid_empty_excessive_or_foreign_variations_abstain(packet, moves):
    assert check(packet, variation(moves))['status'] == 'abstain'


def test_real_first_move_must_bind_exact_selected_candidate(packet):
    row = packet['positions'][0]
    a, b = row['engine_evidence']
    assert a['move_uci'] != b['move_uci']
    result = check(packet, variation([b['move_uci']]), row, a)
    assert result['reason'] == 'variation_does_not_start_with_selected_move'


def test_real_illegal_second_move_is_checked_with_turn_change(packet):
    candidate = packet['positions'][0]['engine_evidence'][0]
    result = check(packet, variation([candidate['move_uci'], candidate['move_uci']]))
    assert result['reason'] == 'illegal_variation_move' and result['failed_ply'] == 2


@pytest.mark.parametrize('claim', [
    {'kind': 'strategy', 'text': 'forced win'}, {'kind': 'teaching_quality', 'rating': 10},
    {'kind': 'variation_legality', 'origin': 'retained_engine_pv', 'moves_uci': [], 'forced': True},
    {'kind': 'variation_legality', 'origin': 'human_annotation', 'moves_uci': ['e2e4']},
    {'kind': 'square_occupation', 'board': 'before', 'square': 'a1', 'piece': None, 'annotation': 'strong'},
    'confident commentary', None, [],
])
def test_unsupported_strategy_attribution_and_extra_fields_abstain(packet, claim):
    assert check(packet, claim)['status'] == 'abstain'


def test_foreign_and_wrongly_typed_references_abstain(packet):
    claim = variation([packet['positions'][0]['engine_evidence'][0]['move_uci']])
    for kwargs in ({'position_id': 'absent'}, {'evidence_id': 'absent'},
                   {'evidence_id': packet['positions'][1]['engine_evidence'][0]['evidence_id']},
                   {'position_id': None}, {'evidence_id': 1}):
        assert check(packet, claim, **kwargs)['status'] == 'abstain'


def test_integrity_checked_before_any_abstention_or_judgment(packet, tmp_path):
    changed = copy.deepcopy(packet)
    changed['positions'][0]['fen'] = chess.STARTING_FEN
    with pytest.raises(ValueError, match='pinned_source'):
        check(changed, {'kind': 'unsupported'}, position_id='absent')
    source = tmp_path / 'synthetic-changed-receipt.json'
    source.write_bytes(SOURCE.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='pinned_source_receipt_changed'):
        check(packet, {}, source=source)


@pytest.mark.parametrize('fen,move,squares', [
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6', {'e5': None, 'd5': None, 'd6': ('pawn', 'white')}),
    ('4k3/8/8/8/8/8/8/4K2R w K - 0 1', 'e1g1', {'e1': None, 'h1': None, 'f1': ('rook', 'white'), 'g1': ('king', 'white')}),
    ('7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7a8n', {'a7': None, 'a8': ('knight', 'white')}),
])
def test_synthetic_special_move_occupations_are_literal_expectations(fen, move, squares):
    board = chess.Board(fen)
    before = board.fen()
    for square, piece in squares.items():
        claim = {'kind': 'square_occupation', 'board': 'after_selected_move', 'square': square,
                 'piece': None if piece is None else {'type': piece[0], 'color': piece[1]}}
        result = extended._replayed_claim(board, move, [move], 'synthetic-software-control', claim)
        assert result['status'] == 'verified_board_fact'
    assert board.fen() == before and board.move_stack == []
    assert extended._replayed_claim(board, move, [move], 'synthetic-software-control', variation([move]))['status'] == 'verified_legal_variation'


def test_synthetic_unrelated_legal_variation_is_not_engine_attributed():
    board = chess.Board()
    claim = variation(['e2e4', 'c7c5'])
    result = extended._replayed_claim(board, 'e2e4', ['e2e4', 'e7e5'], 'synthetic', claim)
    assert result['status'] == 'verified_legal_variation' and not result['engine_attribution_verified']
    claim['origin'] = 'retained_engine_pv'
    assert extended._replayed_claim(board, 'e2e4', ['e2e4', 'e7e5'], 'synthetic', claim)['status'] == 'abstain'


def test_synthetic_move_after_checkmate_abstains():
    moves = ['f2f3', 'e7e5', 'g2g4', 'd8h4', 'a2a3']
    result = extended._replayed_claim(chess.Board(), 'f2f3', [], 'synthetic', variation(moves))
    assert result['reason'] == 'illegal_variation_move' and result['failed_ply'] == 5


def test_public_api_does_not_mutate_packet_or_call_engine(packet, monkeypatch):
    old = cf.canonical(packet)
    def forbidden(*args, **kwargs): raise AssertionError('No engine call is authorized by this evaluator')
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', forbidden)
    candidate = packet['positions'][0]['engine_evidence'][0]
    result = check(packet, variation([candidate['move_uci']]))
    assert result['status'] == 'verified_legal_variation' and cf.canonical(packet) == old
    assert extended.EVALUATOR_ONLY is True

def test_source_integrity_raises(packet, tmp_path):
    # modify receipt to trigger integrity error
    source = tmp_path / 'modified.json'
    source.write_bytes(open('artifacts/chess-counterfactual-v1/dev8-node100k-v3.json','rb').read() + b'\n')
    with pytest.raises(ValueError, match='pinned_source_receipt_changed'):
        check(packet, {'kind':'square_occupation','board':'before','square':'a1','piece':None}, source=source)


def test_unknown_position_abstains(packet):
    claim = {'kind':'square_occupation','board':'before','square':'e2','piece':None}
    result = check(packet, claim, position_id='unknown-id')
    assert result['status']=='abstain' and result['reason']=='unknown_or_failed_position'


def test_unknown_kind_abstains(packet):
    claim = {'kind': 'unknown', 'field':'fen_before','value':None}
    assert check(packet, claim)['status']=='abstain'
