"""Versioned, source-bound generator input boundary; no inference or quality claim.

Full typed receipts stay on the evaluator side. Only canonical bytes from
encode_no_forward_packet may be sent by this module's dispatch adapter. The
legacy forward-assisted generator is deliberately not modified or enabled.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import chess
import chess_counterfactual_evidence as cf
import chess_typed_position_evidence as adapter

SCHEMA = 'chess-no-forward-generator-input/v1'
CONCEPTS = ('king_safety', 'material', 'development', 'center', 'piece_activity',
            'pawn_structure', 'space', 'tactical_threat', 'endgame_transition')
ASSERTIONS = ('legal_board_fact', 'retained_engine_observation',
              'bounded_strategic_hypothesis', 'abstention')
TRANSITION_FIELDS = ('moving_piece', 'moving_color', 'from', 'to', 'capture',
                     'captured_piece', 'captured_square', 'en_passant', 'castling',
                     'promotion', 'gives_check')
ROOT_FIELDS = ('schema', 'source', 'fen', 'side_to_move', 'selected_move',
               'transition', 'engine_observation', 'concept_vocabulary', 'assertion_kinds')
SOURCE_FIELDS = ('position_id', 'game_id', 'url', 'split', 'manifest_sha256',
                 'projection_sha256', 'receipt_sha256', 'typed_packet_sha256')
OBSERVATION_FIELDS = ('evidence_id', 'engine_sha256', 'score',
                      'observation_only', 'independently_reproduced')
SCORE_FIELDS = ('type', 'value', 'perspective', 'side_to_move', 'bound', 'order')
MAX_PACKET_BYTES = 16384


def _shape(packet):
    """An exact allowlist, not a list of known prohibited spellings."""
    cf.exact_keys(packet, ROOT_FIELDS, 'no_forward_root_fields')
    cf.exact_keys(packet['source'], SOURCE_FIELDS, 'no_forward_source_fields')
    cf.exact_keys(packet['selected_move'], ('uci', 'san'), 'no_forward_move_fields')
    cf.exact_keys(packet['transition'], TRANSITION_FIELDS, 'no_forward_transition_fields')
    observation = packet['engine_observation']
    cf.exact_keys(observation, OBSERVATION_FIELDS, 'no_forward_observation_fields')
    score = observation['score']
    cf.require(isinstance(score, dict), 'no_forward_score_shape')
    fields = SCORE_FIELDS + (('mate_zero',) if score.get('type') == 'mate' and
                            type(score.get('value')) is int and score['value'] == 0 else ())
    cf.exact_keys(score, fields, 'no_forward_score_fields')
    cf.require(packet['schema'] == SCHEMA, 'no_forward_schema')
    cf.require(packet['concept_vocabulary'] == list(CONCEPTS), 'no_forward_concept_vocabulary')
    cf.require(packet['assertion_kinds'] == list(ASSERTIONS), 'no_forward_assertion_kinds')


def build_no_forward_packet(data_root, source_receipt_path, expected_source_sha256,
                            typed_packet, position_id, evidence_id):
    """Project a selected real development move from independently pinned evidence.

    Source checks legally replay all retained inputs. The generator receives one
    selected move's deterministic transition and typed score, never other moves,
    PVs, evaluator annotations or post-move FENs. The score is an observation,
    not an inferred rationale, best-move judgment or independently rerun result.
    """
    adapter.validate_typed_position_evidence(data_root, source_receipt_path,
                                           expected_source_sha256, typed_packet)
    cf.require(type(position_id) is str and type(evidence_id) is str, 'invalid_selected_reference')
    row = next((r for r in typed_packet['positions'] if r['position_id'] == position_id), None)
    cf.require(row is not None and row['status'] == 'succeeded' and row['split'] == 'dev',
               'unknown_or_non_development_position')
    candidate = next((c for c in row['engine_evidence'] if c['evidence_id'] == evidence_id), None)
    cf.require(candidate is not None, 'unknown_position_bound_candidate')
    board = chess.Board(row['fen'])
    move = chess.Move.from_uci(candidate['move_uci'])
    facts = cf.transition_evidence(board, move)
    packet = {
        'schema': SCHEMA,
        'source': {'position_id': position_id, 'game_id': row['game_id'], 'url': row['source_url'],
                   'split': 'dev', 'manifest_sha256': typed_packet['source_manifest_sha256'],
                   'projection_sha256': typed_packet['source_projection_sha256'],
                   'receipt_sha256': expected_source_sha256,
                   'typed_packet_sha256': cf.digest(cf.canonical(typed_packet))},
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': move.uci(), 'san': board.san(move)},
        'transition': {name: facts[name] for name in TRANSITION_FIELDS},
        'engine_observation': {'evidence_id': evidence_id,
                               'engine_sha256': typed_packet['engine']['sha256'],
                               'score': copy.deepcopy(candidate['score']),
                               'observation_only': True, 'independently_reproduced': False},
        'concept_vocabulary': list(CONCEPTS), 'assertion_kinds': list(ASSERTIONS),
    }
    _shape(packet)
    cf.require(len(cf.canonical(packet)) <= MAX_PACKET_BYTES, 'no_forward_packet_too_large')
    return packet


def encode_no_forward_packet(data_root, source_receipt_path, expected_source_sha256,
                             typed_packet, position_id, evidence_id, packet):
    """Reject unknown fields AND changed allowed values before emitting any bytes.

    Canonical byte equality distinguishes bool/int/float substitutions. References
    are separate trusted arguments: changing a packet's claimed reference cannot
    silently select a different board or candidate. No unsafe packet is repaired
    by dropping fields or replaced with an assisted-generation fallback.
    """
    _shape(packet)
    encoded = cf.canonical(packet)
    cf.require(len(encoded) <= MAX_PACKET_BYTES, 'no_forward_packet_too_large')
    expected = build_no_forward_packet(data_root, source_receipt_path, expected_source_sha256,
                                      typed_packet, position_id, evidence_id)
    cf.require(encoded == cf.canonical(expected), 'no_forward_differs_from_pinned_source')
    return encoded


def dispatch_no_forward(data_root, source_receipt_path, expected_source_sha256,
                        typed_packet, position_id, evidence_id, packet, generator):
    """Call an injected generator with ONLY validated canonical input bytes.

    This does not configure or contact a model itself. Raw output is returned
    unchanged; the caller must retain it and independently evaluate it before
    acceptance. Transport errors propagate, with no retry, endpoint change or
    input fallback. This adapter does not establish commentary competence.
    """
    encoded = encode_no_forward_packet(data_root, source_receipt_path, expected_source_sha256,
                                       typed_packet, position_id, evidence_id, packet)
    return generator(encoded)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--typed-packet', type=Path, required=True)
    parser.add_argument('--position-id', required=True)
    parser.add_argument('--evidence-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    typed = json.loads(adapter._read_bounded(args.typed_packet))
    inputs = (args.data, args.source, args.source_sha256, typed, args.position_id, args.evidence_id)
    if args.command == 'build':
        packet = build_no_forward_packet(*inputs)
        encoded = encode_no_forward_packet(*inputs, packet)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(encoded)
    else:
        with args.output.open('rb') as stream:
            raw = stream.read(MAX_PACKET_BYTES + 1)
        cf.require(len(raw) <= MAX_PACKET_BYTES, 'no_forward_packet_too_large')
        encoded = encode_no_forward_packet(*inputs, json.loads(raw))
        cf.require(raw == encoded, 'no_forward_file_not_canonical')
    print(json.dumps({'schema': SCHEMA, 'packet_sha256': cf.digest(encoded),
                      'bytes': len(encoded), 'model_calls': 0, 'engine_calls': 0,
                      'commentary_quality_evaluated': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
