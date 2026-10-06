#!/usr/bin/env python3
"""Offline, evaluator-side teaching facts from a completed PGN and verified v3 review.

This script replays legal positions and saved engine lines. It never calls an
engine or a model. Its continuation facts must not enter a no-forward generator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import chess
import chess.svg

import chess_paired_review_v3 as paired
import chess_real_evidence_interface as ui
import chess_review_completed_game as previous


SCHEMA = 'chess-paired-teaching/v4'
MAX_RECORD_BYTES = 1_000_000
MAX_LINE_PLIES = 4
LIMITATIONS = [
    'Post-game study only. The PGN result is a supplied completion declaration.',
    'Saved engine lines and the hypothetical pass are evaluator-side examples, not forced play.',
    'A legal threat or capture does not prove why Stockfish assigned a score.',
    'No engine or model was called to build this page. No teaching-quality claim is made.',
]


def _validated_moves(board: chess.Board, pv_uci: object) -> list[chess.Move]:
    if not isinstance(pv_uci, list) or not 1 <= len(pv_uci) <= 128:
        raise ValueError('illegal_saved_line')
    replay = board.copy(stack=False)
    moves = []
    for uci in pv_uci:
        try:
            move = chess.Move.from_uci(uci)
        except (TypeError, ValueError) as error:
            raise ValueError('illegal_saved_line') from error
        if move not in replay.legal_moves:
            raise ValueError('illegal_saved_line')
        replay.push(move)
        moves.append(move)
    return moves


def _capture(board: chess.Board, move: chess.Move) -> tuple[str | None, str | None]:
    if not board.is_capture(move):
        return None, None
    if board.is_en_passant(move):
        square = move.to_square + (-8 if board.turn == chess.WHITE else 8)
        return 'pawn', chess.square_name(square)
    piece = board.piece_at(move.to_square)
    if piece is None:
        raise ValueError('illegal_saved_line')
    return chess.piece_name(piece.piece_type), chess.square_name(move.to_square)


def derive_line(board: chess.Board, pv_uci: object,
                max_plies: int = MAX_LINE_PLIES) -> dict:
    """Summarize a short prefix of one fully checked legal saved line."""
    if type(max_plies) is not int or not 1 <= max_plies <= MAX_LINE_PLIES:
        raise ValueError('line_limit_out_of_bounds')
    moves = _validated_moves(board, pv_uci)
    shown = moves[:max_plies]
    replay = board.copy(stack=False)
    facts = []
    captures = []
    for move in shown:
        san = replay.san(move)
        mover = chess.COLOR_NAMES[replay.turn]
        captured_piece, square = _capture(replay, move)
        fact = {'san': san, 'uci': move.uci(), 'mover': mover,
                'captured_piece': captured_piece, 'capture_square': square,
                'gives_check': replay.gives_check(move)}
        if captured_piece:
            captures.append({'san': san, 'mover': mover,
                             'captured_side': chess.COLOR_NAMES[not replay.turn],
                             'captured_piece': captured_piece, 'square': square})
        replay.push(move)
        facts.append(fact)
    return {'san_line': board.variation_san(shown), 'moves': facts,
            'captures': captures, 'final_fen': replay.fen(),
            'truncated': len(moves) > len(shown)}


def _abstain(reason: str) -> dict:
    return {'status': 'abstain', 'reason': reason, 'threat': None,
            'saved_reply': None, 'shared_reply': None,
            'legal_reply_example': None}


def _mate_in_one_after_pass(board_after_candidate: chess.Board) -> list[chess.Move]:
    """A hypothetical pass tests threats; it is never an actual game move."""
    if board_after_candidate.is_check() or board_after_candidate.is_game_over():
        return []
    passed = board_after_candidate.copy(stack=False)
    passed.push(chess.Move.null())
    mates = []
    for move in list(passed.legal_moves):
        after = passed.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            mates.append(move)
    return mates


def _legal_reply_example(after_candidate: chess.Board,
                         threat: chess.Move) -> dict | None:
    """Find one quiet legal reply that still permits the exact mate move."""
    options = []
    for reply in after_candidate.legal_moves:
        if (after_candidate.is_capture(reply) or after_candidate.gives_check(reply)
                or reply.promotion):
            continue
        piece = after_candidate.piece_at(reply.from_square)
        single_pawn_push = (piece is not None and piece.piece_type == chess.PAWN
                            and abs(reply.to_square - reply.from_square) == 8)
        options.append((not single_pawn_push, reply.uci(), reply))
    for _, _, reply in sorted(options):
        after_reply = after_candidate.copy(stack=False)
        reply_san = after_reply.san(reply)
        after_reply.push(reply)
        if threat not in after_reply.legal_moves:
            continue
        threat_san = after_reply.san(threat)
        after_reply.push(threat)
        if after_reply.is_checkmate():
            return {'reply_san': reply_san, 'reply_uci': reply.uci(),
                    'reply_side': chess.COLOR_NAMES[after_candidate.turn],
                    'threat_san': threat_san, 'threat_uci': threat.uci()}
    return None


def _threat_after_reply(after_candidate: chess.Board, reply: chess.Move,
                        threat: chess.Move) -> dict:
    if reply not in after_candidate.legal_moves:
        raise ValueError('illegal_saved_line')
    reply_san = after_candidate.san(reply)
    reply_capture, reply_square = _capture(after_candidate, reply)
    reply_gives_check = after_candidate.gives_check(reply)
    after_reply = after_candidate.copy(stack=False)
    after_reply.push(reply)
    result = {'reply_san': reply_san, 'reply_uci': reply.uci(),
              'reply_capture': reply_capture, 'reply_capture_square': reply_square,
              'reply_gives_check': reply_gives_check,
              'threat_available': threat in after_reply.legal_moves,
              'threat_san': None, 'threat_capture': None,
              'threat_capture_square': None, 'threat_gives_check': None,
              'threat_checkmate': None, 'blocked_on': None,
              'blocker_piece': None, 'threat_does_not_answer_check': False}
    if result['threat_available']:
        result['threat_san'] = after_reply.san(threat)
        result['threat_capture'], result['threat_capture_square'] = _capture(after_reply, threat)
        result['threat_gives_check'] = after_reply.gives_check(threat)
        advanced = after_reply.copy(stack=False)
        advanced.push(threat)
        result['threat_checkmate'] = advanced.is_checkmate()
    else:
        result['threat_does_not_answer_check'] = (
            after_reply.is_check() and after_reply.is_pseudo_legal(threat)
            and not after_reply.is_legal(threat))
        mover = after_candidate.piece_at(threat.from_square)
        blocker = after_reply.piece_at(reply.to_square)
        between = chess.SquareSet(chess.between(threat.from_square, threat.to_square))
        if (mover and mover.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN)
                and reply.to_square in between and blocker
                and blocker.color != mover.color):
            result['blocked_on'] = chess.square_name(reply.to_square)
            result['blocker_piece'] = chess.piece_name(blocker.piece_type)
    return result


def derive_threat_contrast(board: chess.Board, played_pv_uci: object,
                           alternative_pv_uci: object) -> dict:
    """Check one mate threat and two observed/counterfactual replies, if available."""
    played = _validated_moves(board, played_pv_uci)
    alternative = _validated_moves(board, alternative_pv_uci)
    if played[0] == alternative[0]:
        raise ValueError('same_candidate_move')
    after_alternative = board.copy(stack=False)
    alternative_san = after_alternative.san(alternative[0])
    after_alternative.push(alternative[0])
    if after_alternative.is_check():
        return _abstain('alternative_gives_check')
    mates = _mate_in_one_after_pass(after_alternative)
    if len(mates) != 1:
        return _abstain('no_unique_mate_in_one_threat')
    threat = mates[0]
    passed = after_alternative.copy(stack=False)
    passed.push(chess.Move.null())
    threat_san = passed.san(threat)
    threat_capture, threat_square = _capture(passed, threat)
    record = {'status': 'supported', 'reason': None,
              'threat': {'candidate_san': alternative_san, 'uci': threat.uci(),
                         'san_after_pass': threat_san,
                         'piece': chess.piece_name(after_alternative.piece_at(
                             threat.from_square).piece_type),
                         'from_square': chess.square_name(threat.from_square),
                         'to_square': chess.square_name(threat.to_square),
                         'captured_piece_after_pass': threat_capture,
                         'capture_square_after_pass': threat_square},
              'saved_reply': None, 'shared_reply': None,
              'legal_reply_example': _legal_reply_example(after_alternative, threat)}
    if len(alternative) >= 2:
        record['saved_reply'] = _threat_after_reply(after_alternative,
                                                     alternative[1], threat)
    if len(played) >= 2:
        shared = played[1]
        if shared in after_alternative.legal_moves:
            record['shared_reply'] = {'status': 'legal',
                                      **_threat_after_reply(after_alternative,
                                                            shared, threat)}
        else:
            record['shared_reply'] = {'status': 'unavailable'}
    return record


def load_verified_v3(pgn_path: Path, v3_dir: Path) -> tuple[bytes, bytes, bytes, dict]:
    """Validate the completed source and exact saved v3 page without new searches."""
    game, pgn_raw, moves = previous.load_completed_game(pgn_path)
    v3_path = v3_dir / 'review.json'
    with v3_path.open('rb') as stream:
        v3_raw = stream.read(paired.MAX_RECORD_BYTES + 1)
    if not v3_raw or len(v3_raw) > paired.MAX_RECORD_BYTES:
        raise ValueError('v3_receipt_empty_or_too_large')
    v3_record = json.loads(v3_raw)
    paired.validate_record(v3_record, game, pgn_raw, moves)
    with (v3_dir / 'index.html').open('rb') as stream:
        v3_page_raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(v3_page_raw) > MAX_RECORD_BYTES:
        raise ValueError('v3_page_too_large')
    if v3_page_raw != paired.render(v3_record):
        raise ValueError('v3_page_differs_from_receipt')
    return pgn_raw, v3_raw, v3_page_raw, v3_record


def build_record(pgn_raw: bytes, v3_raw: bytes, v3_page_raw: bytes,
                 v3_record: dict) -> dict:
    selection = v3_record['selection']
    board = chess.Board(selection['fen_before'])
    observations = v3_record['engine']['paired_observations']
    played_line = derive_line(board, observations[0]['pv_uci'])
    contrast = (_abstain('no_alternative') if len(observations) < 2 else
                derive_threat_contrast(board, observations[0]['pv_uci'],
                                       observations[1]['pv_uci']))
    return {
        'schema': SCHEMA,
        'source': {'pgn_sha256': previous.digest(pgn_raw),
                   'v3_receipt_sha256': previous.digest(v3_raw),
                   'v3_page_sha256': previous.digest(v3_page_raw)},
        'selection': {'ply': selection['ply'], 'fen_before': selection['fen_before'],
                      'played_san': selection['played_san'],
                      'alternative_san': observations[1]['san'] if len(observations) > 1 else None,
                      'side_to_move': selection['side_to_move'],
                      'white': v3_record['source']['headers'].get('White', 'White'),
                      'black': v3_record['source']['headers'].get('Black', 'Black')},
        'played_line': played_line,
        'threat_contrast': contrast,
        'engine_context': {'name': v3_record['engine']['name'],
                           'sha256': v3_record['engine']['sha256'],
                           'requested_nodes': v3_record['engine']['settings'][
                               'requested_nodes_per_search'],
                           'played_score': observations[0]['score'],
                           'alternative_score': observations[1]['score']
                           if len(observations) > 1 else None,
                           'comparison': v3_record['comparison']},
        'limitations': list(LIMITATIONS),
    }


def _capture_text(event: dict) -> str:
    return (f'{event["mover"].title()}\'s {event["san"]} captures '
            f'{event["captured_side"].title()}\'s {event["captured_piece"]} '
            f'on {event["square"]}.')


def _score_text(score: dict) -> str:
    unit = 'centipawns' if score['type'] == 'cp' else 'mate moves'
    bound = {'exact': '', 'lower': 'lower bound ', 'upper': 'upper bound '}[
        score['bound']]
    return (f'{bound}{score["value"]:+d} {unit} from '
            f'{score["side_to_move"].title()}\'s perspective')


def _threat_paragraphs(contrast: dict) -> list[str]:
    if contrast['status'] != 'supported':
        return [f'No single mate-in-one threat was established by this bounded test '
                f'({contrast["reason"].replace("_", " ")}).']
    threat = contrast['threat']
    result = [f'After {threat["candidate_san"]}, a hypothetical pass by the opponent '
              f'would allow {threat["san_after_pass"]}. A pass is not a chess move; '
              'this tests a threat, not a forced outcome.']
    example = contrast['legal_reply_example']
    if example is not None:
        result.append(f'For one legal illustration, {example["reply_side"].title()} '
                      f'can play {example["reply_san"]}; then '
                      f'{example["threat_san"]} is checkmate. This does not mean '
                      'the defender must choose that reply.')
    saved = contrast['saved_reply']
    if saved is not None:
        if saved['blocked_on']:
            result.append(f'In the saved alternative line, the reply '
                          f'{saved["reply_san"]} puts a {saved["blocker_piece"]} on '
                          f'{saved["blocked_on"]}, between the {threat["piece"]} on '
                          f'{threat["from_square"]} and {threat["to_square"]}. '
                          f'The move toward {threat["to_square"]} is then unavailable.')
        elif saved['threat_available']:
            result.append(f'After the saved reply {saved["reply_san"]}, the same move '
                          f'is still legal as {saved["threat_san"]}; this does not '
                          'establish that it is best.')
        elif saved['threat_does_not_answer_check']:
            result.append(f'The saved reply {saved["reply_san"]} gives check. '
                          f'The exact threat move toward {threat["to_square"]} '
                          'would leave the king in check, so it is illegal here.')
        else:
            result.append(f'After the saved reply {saved["reply_san"]}, that exact '
                          'threat move is unavailable. The reason is not established here.')
    shared = contrast['shared_reply']
    if shared is not None and shared['status'] == 'legal':
        reply_detail = ' and gives check' if shared['reply_gives_check'] else ''
        if shared['threat_available']:
            details = []
            if shared['threat_capture']:
                details.append(f'captures a {shared["threat_capture"]}')
            if shared['threat_gives_check']:
                details.append('gives check')
            if shared['threat_checkmate']:
                details.append('ends in checkmate')
            suffix = f'. It {" and ".join(details)}.' if details else '.'
            result.append(f'If the opponent instead uses the played line\'s reply '
                          f'{shared["reply_san"]}{reply_detail}, the candidate can answer '
                          f'{shared["threat_san"]}{suffix} This is a legal '
                          'counterfactual, not a best-response claim.')
        else:
            result.append(f'The played line\'s reply {shared["reply_san"]}{reply_detail} '
                          'is legal after the candidate too, but the exact threat move '
                          'is then unavailable.')
    return result


def render(record: dict) -> bytes:
    selection = record['selection']
    board = chess.Board(selection['fen_before'])
    move_label = (f'{board.fullmove_number}{"..." if board.turn == chess.BLACK else "."}'
                  f'{selection["played_san"]}')
    played = board.copy(stack=False)
    played.push_san(selection['played_san'])
    figures = [f'<figure><figcaption>Before {ui.safe(selection["played_san"])}</figcaption>'
               f'{chess.svg.board(board, orientation=board.turn, size=390)}</figure>',
               f'<figure><figcaption>After {ui.safe(selection["played_san"])}</figcaption>'
               f'{chess.svg.board(played, orientation=board.turn, size=390)}</figure>']
    if selection['alternative_san']:
        alternative = board.copy(stack=False)
        alternative.push_san(selection['alternative_san'])
        figures.append(f'<figure><figcaption>After {ui.safe(selection["alternative_san"])}</figcaption>'
                       f'{chess.svg.board(alternative, orientation=board.turn, size=390)}</figure>')
    line = record['played_line']
    captures = ''.join(f'<li>{ui.safe(_capture_text(item))}</li>' for item in line['captures'])
    if not captures:
        captures = '<li>No capture occurs in the shown line prefix.</li>'
    threat = ''.join(f'<p>{ui.safe(paragraph)}</p>' for paragraph in
                     _threat_paragraphs(record['threat_contrast']))
    context = record['engine_context']
    score_text = (f'The verified v3 receipt recorded {selection["played_san"]}: '
                  f'{_score_text(context["played_score"])}.')
    if context['alternative_score'] is not None:
        score_text += (f' {selection["alternative_san"]}: '
                       f'{_score_text(context["alternative_score"])}.')
    limitations = ''.join(f'<li>{ui.safe(item)}</li>' for item in record['limitations'])
    css = ui.CSS.read_text(encoding='utf-8')
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chess teaching evidence · {ui.safe(selection['white'])} vs {ui.safe(selection['black'])}</title>
<style>{css}</style></head><body><main>
<section class="hero"><p class="eyebrow">Offline post-game study · v4 candidate</p>
<h1>{ui.safe(selection['white'])} vs {ui.safe(selection['black'])}</h1>
<p class="lead">Move {ui.safe(move_label)} (ply {selection['ply']}). These are
legally replayed examples from a saved game and engine receipt, not a model explanation.</p></section>
<section class="case"><div class="boards">{''.join(figures)}</div>
<div class="panel"><p class="eyebrow">Saved line</p><h2>What happens in one continuation</h2>
<p>{ui.safe(line['san_line'])}. This is one legal line from the saved search, not a forced reply.</p>
<ul class="claims">{captures}</ul></div>
<div class="panel"><p class="eyebrow">Alternative</p><h2>A threat and two possible replies</h2>
{threat}</div>
<div class="panel"><p class="eyebrow">Engine context</p><h2>What the scores do and do not say</h2>
<p>{ui.safe(score_text)}</p><p>The legal examples above do not prove why the engine
scored the moves differently. Its search was bounded to {context['requested_nodes']:,}
requested nodes in the earlier paired review.</p></div>
<div class="notice"><strong>Limits</strong><ul>{limitations}</ul></div></section>
<footer><p>PGN SHA-256: <code>{record['source']['pgn_sha256']}</code></p>
<p>Verified v3 receipt SHA-256: <code>{record['source']['v3_receipt_sha256']}</code></p>
<p>Verified v3 page SHA-256: <code>{record['source']['v3_page_sha256']}</code></p></footer>
</main></body></html>'''
    return html.encode('utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('review', 'verify'):
        current = sub.add_parser(command)
        current.add_argument('--pgn', type=Path, required=True)
        current.add_argument('--v3-dir', type=Path, required=True)
        current.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    pgn_raw, v3_raw, v3_page_raw, v3_record = load_verified_v3(args.pgn, args.v3_dir)
    expected = build_record(pgn_raw, v3_raw, v3_page_raw, v3_record)
    record_bytes = previous.canonical(expected) + b'\n'
    page = render(expected)
    if args.command == 'review':
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / 'review.json').write_bytes(record_bytes)
        (args.output_dir / 'index.html').write_bytes(page)
    else:
        with (args.output_dir / 'review.json').open('rb') as stream:
            saved_record = stream.read(MAX_RECORD_BYTES + 1)
        if saved_record != record_bytes:
            raise ValueError('v4_record_differs_from_inputs')
        if (args.output_dir / 'index.html').read_bytes() != page:
            raise ValueError('v4_page_differs_from_receipt')
    print(json.dumps({'schema': SCHEMA, 'status': 'verified', 'engine_calls': 0,
                      'model_calls': 0, 'page_sha256': previous.digest(page),
                      'output': str(args.output_dir / 'index.html')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
