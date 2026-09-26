"""Bounded real-development engine alternatives and recomputable board evidence.

This is evidence infrastructure. Engine evaluations are observations, not ground
truth or explanations. Verification replays chess facts and bindings; it does
not independently reproduce an engine score or prove human teaching value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import chess
import chess.engine

from chess_dev_projection import projection_bytes
from chess_score_bounds import typed_score_bound

ENGINE_SHA256 = '45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0'
SETTINGS = {'threads': 1, 'hash_mb': 16, 'nodes_per_position': 100000, 'multipv': 2}
PROJECTION = 'dev-source-projection-v1.json'
MAX_PV = 256
MAX_RECEIPT_BYTES = 512 * 1024
MAX_INFO_EVENTS = 4096
STREAM_TIMEOUT_SECONDS = 30
BOUNDARIES = ['Real development positions only; no heldout outcome scoring or model calls.',
              'Engine scores are observations, not independently verified truth or explanations.',
              'Available setup history is preserved; earlier full-game history is unavailable.',
              'Board facts and evidence bindings can be recomputed without another engine run.',
              'Node limits are requested per position; observed nodes are retained, including overshoot.',
              'Score, PV, depth, nodes and bound qualification come from the same latest score event for each rank.',
              'Latest UCI lower/upper-bound or incomplete score events are failed positions; earlier events are not substituted.',
              'PositionEvidence v1 cannot represent mate scores; this typed v2 receipt requires a future explicit adapter.']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def file_digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_keys(value, keys, message):
    require(isinstance(value, dict) and set(value) == set(keys), message)


def integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**53 - 1


def load_development(data):
    expected = projection_bytes(data)
    require((data / PROJECTION).read_bytes() == expected, 'development_projection_changed')
    return json.loads(expected), digest(expected)


def source_code_hashes(allow_bounds=False):
    return {name: file_digest(Path(__file__).with_name(name)) for name in
            (('chess_counterfactual_evidence.py', 'chess_dev_projection.py', 'chess_real_data.py')
             + (('chess_score_bounds.py',) if allow_bounds else ())) }


def board_for(case):
    require(case['split'] == 'dev', 'non_development_position')
    board = chess.Board(case['source_fen'])
    require(board.is_valid(), 'invalid_source_position')
    move = chess.Move.from_uci(case['setup_move'])
    require(move in board.legal_moves, 'illegal_setup_move')
    board.push(move)
    require(board.fen() == case['fen'], 'setup_does_not_match_decision_position')
    return board


def material(board):
    return {chess.COLOR_NAMES[color]: {chess.piece_name(piece): len(board.pieces(piece, color))
            for piece in chess.PIECE_TYPES} for color in chess.COLORS}


def transition_evidence(board, move):
    require(board.is_valid() and move in board.legal_moves, 'illegal_candidate_transition')
    before = material(board)
    mover = board.piece_at(move.from_square)
    en_passant = board.is_en_passant(move)
    captured_square = (move.to_square - 8 if board.turn else move.to_square + 8) if en_passant else move.to_square
    captured = board.piece_at(captured_square)
    after = board.copy(stack=True)
    after.push(move)
    counts = material(after)
    return {'fen_before': board.fen(), 'fen_after': after.fen(), 'san': board.san(move),
            'moving_piece': chess.piece_name(mover.piece_type), 'moving_color': chess.COLOR_NAMES[mover.color],
            'from': chess.square_name(move.from_square), 'to': chess.square_name(move.to_square),
            'capture': board.is_capture(move), 'captured_piece': chess.piece_name(captured.piece_type) if captured else None,
            'captured_square': chess.square_name(captured_square) if captured else None,
            'en_passant': en_passant, 'castling': board.is_castling(move),
            'promotion': chess.piece_name(move.promotion) if move.promotion else None,
            'gives_check': after.is_check(), 'checkmate': after.is_checkmate(),
            'material_delta': {color: {piece: counts[color][piece] - count for piece, count in pieces.items()}
                               for color, pieces in before.items()}}


def typed_score(pov_score, turn):
    score = pov_score.pov(turn)
    result = {'type': 'mate' if score.is_mate() else 'cp',
              'value': score.mate() if score.is_mate() else score.score(),
              'perspective': 'side_to_move', 'side_to_move': chess.COLOR_NAMES[turn]}
    require(type(result['value']) is int, 'engine_missing_typed_score')
    if result['type'] == 'mate' and result['value'] == 0:
        result['mate_zero'] = 'delivered' if score == chess.engine.MateGiven else 'received'
    return result


def candidate_id(case, candidate, source_sha, engine_sha):
    content = {key: value for key, value in candidate.items() if key != 'evidence_id'}
    return 'chess-candidate:' + digest(canonical({'source_manifest_sha256': source_sha,
        'position_id': case['position_id'], 'engine_sha256': engine_sha, 'settings': SETTINGS, 'candidate': content}))


class EngineStreamFailure(RuntimeError):
    """The bounded collection failed and this engine session has been closed."""


def latest_score_events(engine, board, game):
    # Public analysis() yields each original info event. Its merged multipv view
    # can retain a bound flag from an earlier score, so never read that view.
    latest = {}
    try:
        with engine.analysis(board, chess.engine.Limit(nodes=SETTINGS['nodes_per_position']),
                             multipv=2, game=game) as stream:
            deadline = time.monotonic() + STREAM_TIMEOUT_SECONDS
            sequence = 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('engine_info_stream_timeout')
                if stream.would_block():
                    time.sleep(0.01)
                    continue
                info = stream.next()
                if info is None:
                    break  # Completion marker also propagates protocol failures.
                sequence += 1
                require(sequence <= MAX_INFO_EVENTS, 'engine_info_event_budget_exceeded')
                if 'score' in info:
                    rank = info.get('multipv', 1)
                    require(type(rank) is int and 1 <= rank <= 2, 'engine_invalid_candidate_rank')
                    # Preserve the complete raw score event, including qualifiers.
                    # Scoreless updates must not replace or borrow its fields.
                    latest[rank] = dict(info, score_info_sequence=sequence)
    except Exception as error:
        # Context exit requests stop; close the transport after an unfinished
        # stream instead of issuing another search against an uncertain engine.
        engine.close()
        raise EngineStreamFailure(str(error)[:500]) from error
    require(set(latest) == {1, 2}, 'engine_did_not_return_two_candidates')
    return [latest[rank] for rank in (1, 2)]


def candidate_from_info(case, board, info, rank, source_sha, engine_sha, allow_bounds=False):
    if not allow_bounds:
        require(info.get('lowerbound', False) is False and info.get('upperbound', False) is False,
                'engine_bound_score_not_supported')
    pv = info.get('pv')
    require(isinstance(pv, list) and 1 <= len(pv) <= MAX_PV, 'engine_missing_or_excessive_pv')
    replay = board.copy(stack=True)
    for move in pv:
        require(move in replay.legal_moves, 'engine_illegal_pv')
        replay.push(move)
    require(integer(info.get('nodes')) and integer(info.get('depth')), 'engine_missing_search_accounting')
    require(integer(info.get('score_info_sequence'), 1), 'engine_missing_score_event_identity')
    candidate = {'rank': rank, 'move_uci': pv[0].uci(), 'pv_uci': [move.uci() for move in pv],
                 'pv_final_fen': replay.fen(), 'score': typed_score_bound(info, board.turn) if allow_bounds else typed_score(info['score'], board.turn),
                 'nodes_observed': info['nodes'], 'depth': info['depth'],
                 'score_info_sequence': info['score_info_sequence'],
                 'transition': transition_evidence(board, pv[0])}
    candidate['evidence_id'] = candidate_id(case, candidate, source_sha, engine_sha)
    return candidate


def receipt_boundaries(allow_bounds):
    result = list(BOUNDARIES)
    if allow_bounds:
        result[6] = 'Latest qualified scores retain explicit lower/upper bounds in engine Score order; they are not exact values, centipawn intervals or statistical confidence.'
        result[7] = 'Typed v3 evidence retains mate/centipawn separation; a PositionEvidence adapter and independent factuality checks remain future work.'
    return result


def collect_receipt(data, engine, engine_sha, allow_bounds=False):
    require(engine_sha == ENGINE_SHA256, 'unreviewed_engine_binary')
    source, projection_sha = load_development(data)
    engine.configure({'Threads': 1, 'Hash': 16})
    rows = []
    stream_failed = False
    for case in source['items']:
        row = {'position_id': case['position_id'], 'game_id': case['game_id'], 'source_url': case['game_url'],
               'split': 'dev', 'status': 'failed', 'candidates': []}
        try:
            require(not stream_failed, 'engine_session_closed_after_stream_failure')
            board = board_for(case)
            infos = latest_score_events(engine, board, case['position_id'])
            candidates = [candidate_from_info(case, board, info, index + 1,
                          source['source_manifest_sha256'], engine_sha, allow_bounds) for index, info in enumerate(infos)]
            require(len({candidate['move_uci'] for candidate in candidates}) == 2, 'engine_duplicate_candidates')
            row.update(status='succeeded', candidates=candidates)
        except Exception as error:
            stream_failed = stream_failed or isinstance(error, EngineStreamFailure)
            row['error'] = {'type': type(error).__name__, 'message': str(error)[:500]}
        rows.append(row)
    value = {'schema': 'chess-counterfactual-evidence/v3' if allow_bounds else 'chess-counterfactual-evidence/v2',
             'source_manifest_sha256': source['source_manifest_sha256'], 'source_projection_sha256': projection_sha,
             'implementation_sha256': source_code_hashes(allow_bounds),
             'engine': {'sha256': engine_sha, 'settings': dict(SETTINGS)},
             'requested_positions': 8, 'results': rows,
             'boundaries': receipt_boundaries(allow_bounds)}
    verify_receipt(data, value)
    return value


def verify_receipt(data, value):
    source, projection_sha = load_development(data)
    exact_keys(value, ('schema', 'source_manifest_sha256', 'source_projection_sha256', 'implementation_sha256',
                       'engine', 'requested_positions', 'results', 'boundaries'), 'invalid_receipt_fields')
    require(value['schema'] in ('chess-counterfactual-evidence/v2', 'chess-counterfactual-evidence/v3'), 'invalid_receipt_schema')
    allow_bounds = value['schema'] == 'chess-counterfactual-evidence/v3'
    require(value['source_manifest_sha256'] == source['source_manifest_sha256'] and
            value['source_projection_sha256'] == projection_sha, 'receipt_source_changed')
    require(value['implementation_sha256'] == source_code_hashes(allow_bounds), 'receipt_implementation_changed')
    require(canonical(value['engine']) == canonical({'sha256': ENGINE_SHA256, 'settings': SETTINGS}), 'engine_identity_or_budget_changed')
    require(value['requested_positions'] == 8 and isinstance(value['results'], list) and len(value['results']) == 8,
            'requested_position_denominator_changed')
    require(value['boundaries'] == receipt_boundaries(allow_bounds), 'invalid_boundaries')
    successful = 0
    exact_candidates = qualified_candidates = 0
    for case, row in zip(source['items'], value['results']):
        base_keys = ('position_id', 'game_id', 'source_url', 'split', 'status', 'candidates')
        exact_keys(row, (*base_keys, 'error') if row.get('status') == 'failed' else base_keys, 'invalid_position_fields')
        require((row['position_id'], row['game_id'], row['source_url'], row['split']) ==
                (case['position_id'], case['game_id'], case['game_url'], 'dev'), 'foreign_or_reordered_position')
        if row['status'] == 'failed':
            exact_keys(row['error'], ('type', 'message'), 'invalid_failed_position')
            require(row['candidates'] == [] and all(isinstance(t, str) and len(t) <= 500 for t in row['error'].values()),
                    'failed_position_contains_success_evidence')
            continue
        require(row['status'] == 'succeeded' and isinstance(row['candidates'], list) and len(row['candidates']) == 2,
                'missing_success_candidates')
        require(len({c['move_uci'] for c in row['candidates']}) == 2, 'duplicate_candidates')
        board = board_for(case)
        for rank, candidate in enumerate(row['candidates'], 1):
            exact_keys(candidate, ('rank', 'move_uci', 'pv_uci', 'pv_final_fen', 'score', 'nodes_observed',
                                   'depth', 'score_info_sequence', 'transition', 'evidence_id'), 'invalid_candidate_fields')
            pv = candidate['pv_uci']
            require(isinstance(pv, list) and 1 <= len(pv) <= MAX_PV and candidate['move_uci'] == pv[0], 'invalid_pv')
            replay = board.copy(stack=True)
            for uci in pv:
                require(isinstance(uci, str), 'invalid_pv_move')
                move = chess.Move.from_uci(uci)
                require(move in replay.legal_moves, 'illegal_pv')
                replay.push(move)
            score = candidate['score']
            require(isinstance(score, dict), 'invalid_score')
            zero_mate = score.get('type') == 'mate' and score.get('value') == 0
            score_keys = ('type', 'value', 'perspective', 'side_to_move') + (('mate_zero',) if zero_mate else ())
            exact_keys(score, score_keys + (('bound', 'order') if allow_bounds else ()), 'invalid_score_type_fields')
            if allow_bounds:
                require(score['bound'] in ('exact', 'lower', 'upper') and score['order'] == 'engine_score', 'invalid_score_qualification')
                exact_candidates += score['bound'] == 'exact'
                qualified_candidates += score['bound'] != 'exact'
            require(score['type'] in ('mate', 'cp') and type(score['value']) is int and
                    abs(score['value']) < 2**31 and score['perspective'] == 'side_to_move' and
                    score['side_to_move'] == chess.COLOR_NAMES[board.turn], 'score_type_or_perspective_mismatch')
            if zero_mate: require(score['mate_zero'] in ('delivered', 'received'), 'ambiguous_zero_mate')
            require(type(candidate['rank']) is int and candidate['rank'] == rank and
                    integer(candidate['nodes_observed']) and integer(candidate['depth']) and
                    integer(candidate['score_info_sequence'], 1) and candidate['score_info_sequence'] <= MAX_INFO_EVENTS,
                    'search_accounting_changed')
            require(candidate['pv_final_fen'] == replay.fen() and canonical(candidate['transition']) ==
                    canonical(transition_evidence(board, chess.Move.from_uci(candidate['move_uci']))), 'board_evidence_mismatch')
            require(candidate['evidence_id'] == candidate_id(case, candidate, source['source_manifest_sha256'], ENGINE_SHA256),
                    'evidence_reference_mismatch')
        successful += 1
    return {'schema': 'chess-counterfactual-check/v3' if allow_bounds else 'chess-counterfactual-check/v2', 'integrity_passed': True, 'complete': successful == 8,
            'requested_positions': 8, 'successful_positions': successful, 'failed_positions': 8 - successful,
            'legal_candidates': successful * 2, 'model_calls': 0, 'test_outcomes_scored': 0,
            'engine_scores_independently_reproduced': False,
            **({'exact_candidates': exact_candidates, 'qualified_candidates': qualified_candidates} if allow_bounds else {})}


def write_receipt(value, output):
    encoded = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'
    require(len(encoded) <= MAX_RECEIPT_BYTES, 'receipt_exceeds_byte_budget')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(encoded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', type=Path)
    parser.add_argument('--allow-qualified-scores', action='store_true', help='Write typed v3 qualified-score observations; never relabel a bound as exact.')
    args = parser.parse_args()
    if args.command == 'build':
        require(not args.output.exists(), 'output_exists_use_new_version')
        require(args.engine is not None and args.engine.is_file(), 'missing_engine_binary')
        require(file_digest(args.engine) == ENGINE_SHA256, 'unreviewed_engine_binary')
        with chess.engine.SimpleEngine.popen_uci(str(args.engine.resolve()), timeout=30) as engine:
            value = collect_receipt(args.data, engine, ENGINE_SHA256, allow_bounds=args.allow_qualified_scores)
        write_receipt(value, args.output)
    else:
        require(args.output.stat().st_size <= MAX_RECEIPT_BYTES, 'receipt_exceeds_byte_budget')
        value = json.loads(args.output.read_bytes())
    result = verify_receipt(args.data, value)
    result['receipt_sha256'] = file_digest(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
