"""Synthetic request-boundary controls; no model or engine call."""
from pathlib import Path
import json
import sys

import chess
import pytest

STAGE = Path(__file__).resolve().parent


def _project_root() -> Path:
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / 'scripts/chess_endgame_promotion_contrast_v11.py').is_file():
            return ancestor
        project = ancestor / 'projects/SportsPlayLLMResearch'
        if (project / 'scripts/chess_endgame_promotion_contrast_v11.py').is_file():
            return project
    raise RuntimeError('SportsPlayLLMResearch checkout not found')


ROOT = _project_root()
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(STAGE))

import chess_promotion_one_ply_input_v12 as candidate  # noqa: E402
import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


@pytest.fixture
def source_bound_packet(tmp_path, monkeypatch):
    board = chess.Board(candidate.checker.teaching_v8.CASES[93][1])
    move = chess.Move.from_uci('h8b8')
    facts = cf.transition_evidence(board, move)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {
            'pgn_sha256': candidate.checker.teaching_v8.PGN_SHA256,
            'review_receipt_sha256': '2' * 64,
            'review_page_sha256': '3' * 64,
            'selected_ply': 93, 'move_role': 'played',
            'use_role': user_packet.USE_ROLE},
        'fen': board.fen(), 'side_to_move': 'white',
        'selected_move': {'uci': move.uci(), 'san': board.san(move)},
        'transition': {key: facts[key]
                       for key in no_forward.TRANSITION_FIELDS},
        'engine_observation': {
            'name': 'synthetic', 'sha256': '4' * 64,
            'score': {'type': 'cp', 'value': 0, 'bound': 'exact',
                      'order': 'engine_score', 'perspective': 'side_to_move',
                      'side_to_move': 'white'},
            'observation_only': True, 'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    raw = cf.canonical(packet)
    binding = {
        'schema': tactical.BINDING_SCHEMA,
        'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(tmp_path / 'game.pgn'),
        'review_dir': str(tmp_path / 'review'),
        'pgn_sha256': candidate.checker.teaching_v8.PGN_SHA256,
        'review_sha256': '2' * 64, 'page_sha256': '3' * 64,
        'role': 'played',
    }

    def encoder(_pgn, _review, pgn_sha, review_sha, page_sha, *, role,
                packet):
        if (pgn_sha, review_sha, page_sha, role) != (
                binding['pgn_sha256'], '2' * 64, '3' * 64, 'played'):
            raise ValueError('synthetic_source_binding_changed')
        return raw

    monkeypatch.setattr(user_packet, 'encode_packet', encoder)
    return raw, cf.digest(raw), binding


def test_request_is_exact_two_message_pre_move_projection(source_bound_packet):
    packet, sha, binding = source_bound_packet
    projection, raw = candidate.build_request(packet, sha, binding)
    request = json.loads(raw)
    projected = json.loads(projection)
    assert raw == cf.canonical(request)
    assert set(projected) == set(candidate.capture_v7.PROJECTION_FIELDS)
    assert projected['schema'] == candidate.checker.INPUT_SCHEMA
    assert projected['assertion_kinds'] == [candidate.checker.KIND,
                                           'abstention']
    assert request['model'] == 'loops-cpu-gpt-oss-20b'
    assert request['messages'] == [
        {'role': 'system', 'content': candidate.checker.PROMPT},
        {'role': 'user', 'content': projection.decode()}]
    assert request['stream'] is False
    assert (request['max_tokens'], request['temperature'], request['top_p'],
            request['seed'], request['reasoning_effort']) == (
                1024, 0, 1, 20260923, 'low')
    for forbidden in ('rc8', 'b1=q', 'rxb1', 'b2b1q', 'h8c8',
                      'pv_uci', 'post_move_fen', 'future_feature',
                      'review_label', 'human_annotation'):
        assert forbidden not in raw.decode().lower()


@pytest.mark.parametrize(('scope', 'field', 'value'), [
    ('engine_observation', 'pv_uci', ['b2b1q']),
    ('engine_observation', 'post_move_fen', 'future'),
    ('engine_observation', 'alternative_score', 283),
    ('transition', 'future_feature', 'promotion'),
    ('source', 'human_annotation', 'Rc8 loses'),
    ('selected_move', 'review_label', 'best'),
])
def test_nested_forbidden_fields_rejected_before_request(
        source_bound_packet, scope, field, value):
    packet, _, binding = source_bound_packet
    altered = json.loads(packet)
    altered[scope][field] = value
    raw = cf.canonical(altered)
    with pytest.raises((ValueError, tactical.ClaimRejected)):
        candidate.build_request(raw, cf.digest(raw), binding)


@pytest.mark.parametrize(('scope', 'field', 'value'), [
    ('fen', None, '7R/8/2p5/2k2p1P/r7/7K/1p4P1/8 b - - 4 47'),
    ('selected_move', 'uci', 'h8c8'),
    ('engine_observation', 'score', {'type': 'cp', 'value': 283}),
])
def test_tampered_allowed_values_rejected_by_source_reprojection(
        source_bound_packet, scope, field, value):
    packet, _, binding = source_bound_packet
    altered = json.loads(packet)
    if field is None:
        altered[scope] = value
    else:
        altered[scope][field] = value
    raw = cf.canonical(altered)
    with pytest.raises((ValueError, tactical.ClaimRejected)):
        candidate.build_request(raw, cf.digest(raw), binding)


def test_wrong_source_binding_and_duplicate_json_rejected(source_bound_packet):
    packet, sha, binding = source_bound_packet
    with pytest.raises((ValueError, tactical.ClaimRejected)):
        candidate.build_request(packet, sha,
                                dict(binding, review_sha256='5' * 64))
    duplicate = packet.replace(b'"schema":',
                               b'"schema":"duplicate","schema":', 1)
    with pytest.raises((ValueError, tactical.ClaimRejected)):
        candidate.build_request(duplicate, cf.digest(duplicate), binding)


def test_route_must_remain_frozen_model_and_endpoint(source_bound_packet,
                                                     monkeypatch):
    packet, sha, binding = source_bound_packet
    original = candidate.capture_v9._route
    monkeypatch.setattr(candidate.capture_v9, '_route',
                        lambda path: (b'', dict(original(path)[1],
                                                 model_id='wrong-model')))
    with pytest.raises(ValueError, match='route_changed'):
        candidate.build_request(packet, sha, binding)
