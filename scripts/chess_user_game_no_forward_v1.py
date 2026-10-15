#!/usr/bin/env python3
"""Project one verified completed-game review move into no-forward input.

This packet is for post-game practice only. It carries no PGN header, annotation,
other move, score comparison, engine line or post-move position. No generator is
called here; structural admission does not establish explanation quality.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward
import chess_paired_review_v3 as paired
import chess_review_completed_game as previous


SCHEMA = 'chess-user-game-no-forward-input/v1'
USE_ROLE = 'postgame_practice_only'
ROLES = ('played', 'alternative')
MAX_PAGE_BYTES = 2_000_000
MAX_PACKET_BYTES = 16_384
SOURCE_FIELDS = ('pgn_sha256', 'review_receipt_sha256', 'review_page_sha256',
                 'selected_ply', 'move_role', 'use_role')
ROOT_FIELDS = ('schema', 'source', 'fen', 'side_to_move', 'selected_move',
               'transition', 'engine_observation', 'concept_vocabulary',
               'assertion_kinds')
ENGINE_FIELDS = ('name', 'sha256', 'score', 'observation_only',
                 'independently_reproduced')
SCORE_FIELDS = ('type', 'value', 'bound', 'order', 'perspective', 'side_to_move')


def _digest_arg(value: str, name: str) -> None:
    if (type(value) is not str or len(value) != 64 or
            any(character not in '0123456789abcdef' for character in value)):
        raise ValueError(f'invalid_{name}')


def _read_bounded(path: Path, maximum: int, error: str) -> bytes:
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(error)
    return raw


def load_verified_review(pgn_path: Path, review_dir: Path, pgn_sha256: str,
                         review_sha256: str, page_sha256: str) -> tuple[dict, bytes]:
    """Check caller-pinned bytes, legal PGN replay, v3 receipt and rendered page."""
    for name, value in (('pgn_sha256', pgn_sha256),
                        ('review_sha256', review_sha256),
                        ('page_sha256', page_sha256)):
        _digest_arg(value, name)
    game, raw, moves = previous.load_completed_game(Path(pgn_path))
    if previous.digest(raw) != pgn_sha256:
        raise ValueError('pgn_sha256_changed')
    review_dir = Path(review_dir)
    receipt_bytes = _read_bounded(review_dir / 'review.json', paired.MAX_RECORD_BYTES,
                                  'review_receipt_too_large')
    if previous.digest(receipt_bytes) != review_sha256:
        raise ValueError('review_sha256_changed')
    try:
        record = json.loads(receipt_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_review_receipt_json') from error
    if receipt_bytes != previous.canonical(record) + b'\n':
        raise ValueError('review_receipt_not_canonical')
    paired.validate_record(record, game, raw, moves)
    page_bytes = _read_bounded(review_dir / 'index.html', MAX_PAGE_BYTES,
                               'review_page_too_large')
    if previous.digest(page_bytes) != page_sha256:
        raise ValueError('review_page_sha256_changed')
    if page_bytes != paired.render(record):
        raise ValueError('review_page_differs_from_receipt')
    return record, raw


def _shape(packet: object) -> None:
    """Reject all unknown fields, including evaluator material at any depth."""
    cf.exact_keys(packet, ROOT_FIELDS, 'user_game_no_forward_root_fields')
    cf.exact_keys(packet['source'], SOURCE_FIELDS, 'user_game_no_forward_source_fields')
    cf.exact_keys(packet['selected_move'], ('uci', 'san'),
                  'user_game_no_forward_move_fields')
    cf.exact_keys(packet['transition'], no_forward.TRANSITION_FIELDS,
                  'user_game_no_forward_transition_fields')
    cf.exact_keys(packet['engine_observation'], ENGINE_FIELDS,
                  'user_game_no_forward_engine_fields')
    cf.exact_keys(packet['engine_observation']['score'], SCORE_FIELDS,
                  'user_game_no_forward_score_fields')
    if packet['schema'] != SCHEMA:
        raise ValueError('user_game_no_forward_schema')
    if (packet['source']['use_role'] != USE_ROLE or
            packet['source']['move_role'] not in ROLES or
            type(packet['source']['selected_ply']) is not int):
        raise ValueError('user_game_no_forward_source_role')
    if (packet['engine_observation']['observation_only'] is not True or
            packet['engine_observation']['independently_reproduced'] is not False):
        raise ValueError('user_game_no_forward_engine_qualification')
    if (packet['concept_vocabulary'] != list(no_forward.CONCEPTS) or
            packet['assertion_kinds'] != list(no_forward.ASSERTIONS)):
        raise ValueError('user_game_no_forward_declarations')


def build_packet(pgn_path: Path, review_dir: Path, pgn_sha256: str,
                 review_sha256: str, page_sha256: str, *, role: str) -> dict:
    """Reproject just one legal move; source labels and continuations stay out."""
    if role not in ROLES or type(role) is not str:
        raise ValueError('invalid_user_game_move_role')
    record, _ = load_verified_review(pgn_path, review_dir, pgn_sha256,
                                     review_sha256, page_sha256)
    selection = record['selection']
    observations = record['engine']['paired_observations']
    if role == 'alternative' and len(observations) != 2:
        raise ValueError('user_game_alternative_not_available')
    item = observations[0 if role == 'played' else 1]
    board = chess.Board(selection['fen_before'])
    move = chess.Move.from_uci(item['move_uci'])
    facts = cf.transition_evidence(board, move)
    packet = {
        'schema': SCHEMA,
        'source': {'pgn_sha256': pgn_sha256,
                   'review_receipt_sha256': review_sha256,
                   'review_page_sha256': page_sha256,
                   'selected_ply': selection['ply'], 'move_role': role,
                   'use_role': USE_ROLE},
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': move.uci(), 'san': board.san(move)},
        'transition': {name: facts[name] for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {'name': record['engine']['name'],
                               'sha256': record['engine']['sha256'],
                               'score': copy.deepcopy(item['score']),
                               'observation_only': True,
                               'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    _shape(packet)
    if len(cf.canonical(packet)) > MAX_PACKET_BYTES:
        raise ValueError('user_game_no_forward_packet_too_large')
    return packet


def encode_packet(pgn_path: Path, review_dir: Path, pgn_sha256: str,
                  review_sha256: str, page_sha256: str, *, role: str,
                  packet: object) -> bytes:
    """Emit bytes only after exact allowlist and fresh source reprojection match."""
    _shape(packet)
    encoded = cf.canonical(packet)
    if len(encoded) > MAX_PACKET_BYTES:
        raise ValueError('user_game_no_forward_packet_too_large')
    expected = build_packet(pgn_path, review_dir, pgn_sha256, review_sha256,
                            page_sha256, role=role)
    if encoded != cf.canonical(expected):
        raise ValueError('user_game_no_forward_differs_from_verified_review')
    return encoded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--pgn', type=Path, required=True)
    parser.add_argument('--review-dir', type=Path, required=True)
    parser.add_argument('--pgn-sha256', required=True)
    parser.add_argument('--review-sha256', required=True)
    parser.add_argument('--page-sha256', required=True)
    parser.add_argument('--role', choices=ROLES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    source = (args.pgn, args.review_dir, args.pgn_sha256,
              args.review_sha256, args.page_sha256)
    if args.command == 'build':
        packet = build_packet(*source, role=args.role)
        encoded = encode_packet(*source, role=args.role, packet=packet)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(encoded)
    else:
        raw = _read_bounded(args.output, MAX_PACKET_BYTES,
                            'user_game_packet_file_too_large')
        try:
            packet = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('invalid_user_game_packet_json') from error
        encoded = encode_packet(*source, role=args.role, packet=packet)
        if raw != encoded:
            raise ValueError('user_game_packet_file_not_canonical')
    print(json.dumps({'schema': SCHEMA, 'status': 'verified',
                      'packet_sha256': previous.digest(encoded),
                      'bytes': len(encoded), 'role': args.role,
                      'model_calls': 0, 'engine_calls': 0,
                      'heldout_outcomes_scored': 0,
                      'commentary_capability_gate_passed': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
