"""Synthetic v4 checker checks; no engine, model, or Chess.com review call."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_v4 as teaching  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


FEN = '2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20'


def packet_for(fen=FEN, selected_uci='c2c3'):
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    facts = cf.transition_evidence(board, selected)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {'pgn_sha256': '1' * 64, 'review_receipt_sha256': '2' * 64,
                   'review_page_sha256': '3' * 64, 'selected_ply': 39,
                   'move_role': 'played', 'use_role': user_packet.USE_ROLE},
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected.uci(), 'san': board.san(selected)},
        'transition': {name: facts[name] for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {'name': 'synthetic', 'sha256': '4' * 64,
                               'score': {'type': 'cp', 'value': -471, 'bound': 'exact',
                                         'order': 'engine_score',
                                         'perspective': 'side_to_move',
                                         'side_to_move': 'white'},
                               'observation_only': True,
                               'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    raw = cf.canonical(packet)
    return raw, cf.digest(raw)


@pytest.fixture
def bound_source(tmp_path, monkeypatch):
    binding = {
        'schema': tactical.BINDING_SCHEMA, 'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(tmp_path / 'game.pgn'), 'review_dir': str(tmp_path / 'review'),
        'pgn_sha256': '1' * 64, 'review_sha256': '2' * 64,
        'page_sha256': '3' * 64, 'role': 'played',
    }
    calls = []

    def exact_encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        calls.append((pgn, review, pgn_sha, review_sha, page_sha, role))
        assert (pgn_sha, review_sha, page_sha, role) == (
            '1' * 64, '2' * 64, '3' * 64, 'played')
        return cf.canonical(packet)

    monkeypatch.setattr(user_packet, 'encode_packet', exact_encoder)
    return binding, calls


def proposal(alternative='c2e4'):
    return {'schema': teaching.CLAIM_SCHEMA, 'kind': teaching.CLAIM_KIND,
            'selected_uci': 'c2c3', 'alternative_uci': alternative,
            'hypothesis': teaching.HYPOTHESIS, 'modality': 'candidate_only',
            'uncertainty': 'other_replies_and_engine_intent_unverified'}


def test_same_nine_field_projection_has_no_forward_or_answer_material(bound_source):
    binding, calls = bound_source
    raw, digest = packet_for()
    value = json.loads(teaching.build_generator_input(raw, digest,
                                                       source_binding=binding))
    assert set(value) == {'schema', 'source_packet_sha256', 'source', 'fen',
                          'side_to_move', 'selected_move', 'transition',
                          'engine_observation', 'assertion_kinds'}
    assert value['schema'] == teaching.INPUT_SCHEMA
    assert value['assertion_kinds'] == [teaching.CLAIM_KIND, 'abstention']
    encoded = json.dumps(value)
    assert 'c2e4' not in encoded
    assert 'd7d4' not in encoded
    assert 'pv_uci' not in encoded
    assert 'post_move_fen' not in encoded
    assert 'legal_reply_candidates' not in encoded
    assert calls


def test_qc3_qe4_hypothesis_gets_checked_conditional_witness(bound_source):
    binding, _ = bound_source
    raw, digest = packet_for()
    result = teaching.evaluate(raw, digest, cf.canonical(proposal()),
                               source_binding=binding)
    assert result['decision'] == 'verified_conditional_option'
    assert result['model_alternative_uci'] == 'c2e4'
    assert result['witness_search_counts']['exclusive_concrete_witness_count'] > 0
    assert result['witness'] is not None
    assert 'Qc3' in result['teaching_text']
    assert 'Qe4' in result['teaching_text']
    assert 'move quality' in result['teaching_text']
    assert result['quality_evaluated'] is False
    assert result['model_calls'] == result['engine_calls'] == 0
    board = chess.Board(FEN)
    witnesses, _ = teaching._candidate_witnesses(
        board, chess.Move.from_uci('c2c3'), chess.Move.from_uci('c2e4'))
    assert any(item['reply_uci'] == 'd7d4' and
               item['option_uci'] == 'e4b7' and
               item['property'] == 'capture_with_check' for item in witnesses)


def test_promoted_pawn_is_called_a_promoted_piece(bound_source):
    binding, _ = bound_source
    fen = '1r6/P6k/8/8/8/8/8/6K1 w - - 0 1'
    raw, digest = packet_for(fen, 'a7a8q')
    claim = proposal('a7b8q')
    claim['selected_uci'] = 'a7a8q'
    result = teaching.evaluate(raw, digest, cf.canonical(claim),
                               source_binding=binding)
    assert result['decision'] == 'verified_conditional_option'
    assert result['witness']['piece'] == 'queen'
    assert 'promoted queen' in result['teaching_text']
    assert 'moved queen' not in result['teaching_text']


def test_illegal_or_wrong_origin_alternative_is_rejected(bound_source):
    binding, _ = bound_source
    raw, digest = packet_for()
    illegal = teaching.evaluate(raw, digest, cf.canonical(proposal('e5d7')),
                                source_binding=binding)
    assert illegal['decision'] == 'rejected'
    assert illegal['reason'] == 'illegal_alternative'
    assert illegal['witness'] is None
    other_piece = teaching.evaluate(raw, digest, cf.canonical(proposal('f3e4')),
                                    source_binding=binding)
    assert other_piece['decision'] == 'rejected'
    assert other_piece['reason'] == 'alternative_not_same_moved_piece'


def test_model_and_evaluator_abstentions_are_separate(bound_source, monkeypatch):
    binding, _ = bound_source
    raw, digest = packet_for()
    abstain = {'schema': teaching.CLAIM_SCHEMA, 'kind': 'abstention',
               'reason': 'insufficient_evidence'}
    model = teaching.evaluate(raw, digest, cf.canonical(abstain),
                              source_binding=binding)
    assert model['decision'] == 'model_abstention'
    assert model['witness_search_counts'] is None
    monkeypatch.setattr(teaching, '_candidate_witnesses', lambda *_: (
        [], {'common_reply_uci_count': 0,
             'same_san_reply_count': 0,
             'comparable_moved_piece_reply_count': 0,
             'moved_piece_options_examined': 0,
             'exclusive_concrete_witness_count': 0}))
    evaluator = teaching.evaluate(raw, digest, cf.canonical(proposal()),
                                  source_binding=binding)
    assert evaluator['decision'] == 'evaluator_abstention'
    assert evaluator['reason'] == 'no_conditional_witness'
    assert evaluator['model_alternative_uci'] == 'c2e4'


def test_source_binding_is_checked_before_claim_evaluation(bound_source):
    binding, calls = bound_source
    raw, digest = packet_for()
    changed = dict(binding, unexpected_source_field='not_allowed')
    with pytest.raises(tactical.ClaimRejected):
        teaching.evaluate(raw, digest, cf.canonical(proposal()),
                          source_binding=changed)
    assert not calls
