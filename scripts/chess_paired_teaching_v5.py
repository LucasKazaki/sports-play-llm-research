#!/usr/bin/env python3
"""Offline, source-bound step lesson for one paired completed-game review.

All continuations are evaluator-side legal replays. Neither this page nor its
continuations may be supplied to a no-forward commentary generator. No engine
or model is called here, and the examples do not establish engine intent.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path

import chess
import chess.svg

import chess_paired_teaching_v4 as v4
import chess_review_completed_game as previous


SCHEMA = 'chess-paired-teaching/v5'
V4_SOURCE_SHA256 = '3ae374f0560ab2d90ac8220ed0c34c0b22acb401e6981a97c70e3f7062a6d9ed'
MAX_RECORD_BYTES = 1_000_000
MAX_PAGE_BYTES = 2_000_000
LIMITATIONS = [
    'Post-game practice only. The PGN result is a supplied completion declaration.',
    'Every shown line is a legal example, not a forced or best-response line.',
    'These legal options do not prove Stockfish\'s complete reason for its scores.',
    'No engine or model was called to build this page; teaching quality is untested.',
]


def _check_v4_source() -> None:
    """Keep the approved v4 source projection fixed for this version."""
    if previous.digest(Path(v4.__file__).read_bytes()) != V4_SOURCE_SHA256:
        raise ValueError('v4_source_sha256_changed')


def replay_steps(board: chess.Board, pv_uci: list[str], *, focus_square: str) -> dict:
    """Retain every displayed board after a fully legal, short continuation."""
    if type(focus_square) is not str or focus_square not in chess.SQUARE_NAMES:
        raise ValueError('invalid_focus_square')
    if type(pv_uci) is not list or not 1 <= len(pv_uci) <= v4.MAX_LINE_PLIES:
        raise ValueError('invalid_step_line_length')
    moves = v4._validated_moves(board, pv_uci)
    replay = board.copy(stack=False)
    steps = []
    for move in moves:
        number = f'{replay.fullmove_number}{"..." if replay.turn == chess.BLACK else "."}'
        san = replay.san(move)
        captured_piece, capture_square = v4._capture(replay, move)
        gives_check = replay.gives_check(move)
        replay.push(move)
        steps.append({'notation': f'{number} {san}', 'san': san, 'uci': move.uci(),
                      'fen_after': replay.fen(), 'captured_piece': captured_piece,
                      'capture_square': capture_square, 'gives_check': gives_check})
    return {'steps': steps, 'final_fen': replay.fen(), 'focus_square': focus_square}


def _no_shared_exchange(reason: str) -> dict:
    return {'status': 'abstain', 'reason': reason, 'same_final_board': None,
            'played': None, 'alternative': None, 'focus_square': None}


def derive_shared_exchange(board: chess.Board, played_pv_uci: object,
                           alternative_pv_uci: object) -> dict:
    """Test whether the saved pawn/queen exchange also works after the alternative."""
    played = v4._validated_moves(board, played_pv_uci)
    alternative = v4._validated_moves(board, alternative_pv_uci)
    if len(played) < 4 or played[0] == alternative[0]:
        return _no_shared_exchange('missing_distinct_four_ply_exchange')
    focus = chess.square_name(played[1].to_square)
    played_line = replay_steps(board, [move.uci() for move in played[:4]],
                               focus_square=focus)
    facts = played_line['steps']
    if ([step['captured_piece'] for step in facts[1:]] !=
            ['pawn', 'queen', 'queen'] or
            any(step['capture_square'] != focus for step in facts[1:])):
        return _no_shared_exchange('saved_line_not_pawn_queen_exchange')
    alt_board = board.copy(stack=False)
    alt_board.push(alternative[0])
    if played[1] not in alt_board.legal_moves:
        return _no_shared_exchange('reply_unavailable_after_alternative')
    alt_board.push(played[1])
    alt_capture = chess.Move(alternative[0].to_square, played[1].to_square)
    if alt_capture not in alt_board.legal_moves or not alt_board.is_capture(alt_capture):
        return _no_shared_exchange('queen_recapture_unavailable')
    taken = alt_board.piece_at(alt_capture.to_square)
    if taken is None or taken.piece_type != chess.QUEEN:
        return _no_shared_exchange('queen_recapture_unavailable')
    alt_board.push(alt_capture)
    if played[3] not in alt_board.legal_moves or not alt_board.is_capture(played[3]):
        return _no_shared_exchange('rook_recapture_unavailable')
    taken = alt_board.piece_at(played[3].to_square)
    if taken is None or taken.piece_type != chess.QUEEN:
        return _no_shared_exchange('rook_recapture_unavailable')
    candidate = [alternative[0], played[1], alt_capture, played[3]]
    alternative_line = replay_steps(board, [move.uci() for move in candidate],
                                    focus_square=focus)
    if alternative_line['final_fen'] != played_line['final_fen']:
        return _no_shared_exchange('different_resulting_board')
    return {'status': 'supported', 'reason': None, 'same_final_board': True,
            'played': played_line, 'alternative': alternative_line,
            'focus_square': focus}


def _line(id_: str, title: str, source_kind: str, hypothetical: bool,
          evidence: dict) -> dict:
    return {'id': id_, 'title': title, 'source_kind': source_kind,
            'hypothetical': hypothetical, **evidence}


def _option_contrast(board: chess.Board, played_pv: object,
                     alternative_pv: object, contrast: dict) -> dict:
    """Check whether the exact checking capture is absent after the played move."""
    if contrast['status'] != 'supported' or alternative_pv is None:
        return {'status': 'abstain', 'reason': 'no_verified_checking_option'}
    reply = contrast['shared_reply']
    if reply is None or reply['status'] != 'legal' or not reply['threat_available']:
        return {'status': 'abstain', 'reason': 'no_shared_reply_with_threat'}
    played = v4._validated_moves(board, played_pv)
    alternative = v4._validated_moves(board, alternative_pv)
    candidate = board.copy(stack=False)
    candidate.push(alternative[0])
    reply_move = chess.Move.from_uci(reply['reply_uci'])
    if reply_move not in candidate.legal_moves:
        raise ValueError('illegal_shared_reply')
    candidate.push(reply_move)
    threat_move = chess.Move.from_uci(contrast['threat']['uci'])
    if threat_move not in candidate.legal_moves or candidate.san(threat_move) != reply['threat_san']:
        raise ValueError('changed_checking_option')
    played_board = board.copy(stack=False)
    played_board.push(played[0])
    if reply_move not in played_board.legal_moves:
        return {'status': 'abstain', 'reason': 'reply_unavailable_after_played'}
    played_board.push(reply_move)
    analogous = chess.Move(played[0].to_square, threat_move.to_square)
    return {'status': 'supported', 'reason': None,
            'san_after_alternative': reply['threat_san'],
            'capture_piece': reply['threat_capture'],
            'gives_check': reply['threat_gives_check'],
            'played_can_move_to_same_target': analogous in played_board.legal_moves}


def build_record(pgn_raw: bytes, v3_raw: bytes, v3_page_raw: bytes,
                 v3_record: dict) -> dict:
    _check_v4_source()
    base = v4.build_record(pgn_raw, v3_raw, v3_page_raw, v3_record)
    board = chess.Board(base['selection']['fen_before'])
    observations = v3_record['engine']['paired_observations']
    played_pv = observations[0]['pv_uci']
    alternative_pv = observations[1]['pv_uci'] if len(observations) > 1 else None
    shared = (_no_shared_exchange('no_alternative') if alternative_pv is None else
              derive_shared_exchange(board, played_pv, alternative_pv))
    focus = (shared['focus_square'] if shared['status'] == 'supported' else
             (base['played_line']['captures'][0]['square']
              if base['played_line']['captures'] else
              chess.square_name(v4._validated_moves(board, played_pv)[0].to_square)))
    lines = [_line('played_exchange', 'Saved line after the played move',
                   'saved_v3_line', False,
                   replay_steps(board, played_pv[:v4.MAX_LINE_PLIES], focus_square=focus))]
    if shared['status'] == 'supported':
        lines.append(_line('alternative_exchange', 'Same exchange after the alternative',
                           'verified_counterfactual', False, shared['alternative']))
    contrast = base['threat_contrast']
    option = _option_contrast(board, played_pv, alternative_pv, contrast)
    if contrast['status'] == 'supported' and alternative_pv is not None:
        candidate = alternative_pv[0]
        saved = contrast['saved_reply']
        if saved is not None:
            block = saved['blocked_on'] or chess.square_name(
                chess.Move.from_uci(saved['reply_uci']).to_square)
            lines.append(_line('saved_block', 'Saved reply after the alternative',
                               'saved_v3_line', False,
                               replay_steps(board, [candidate, saved['reply_uci']],
                                            focus_square=block)))
        reply = contrast['shared_reply']
        if reply is not None and reply['status'] == 'legal' and reply['threat_available']:
            lines.append(_line('checking_option', 'Another option after the shared reply',
                               'verified_counterfactual', False,
                               replay_steps(board, [candidate, reply['reply_uci'],
                                                    contrast['threat']['uci']],
                                            focus_square=contrast['threat']['to_square'])))
        example = contrast['legal_reply_example']
        if example is not None:
            lines.append(_line('hypothetical_reply',
                               f'Hypothetical reply after {board.san(chess.Move.from_uci(candidate))}',
                               'hypothetical_legal_reply', True,
                               replay_steps(board, [candidate, example['reply_uci'],
                                                    example['threat_uci']],
                                            focus_square=contrast['threat']['to_square'])))
    base['schema'] = SCHEMA
    base['source']['v4_source_sha256'] = V4_SOURCE_SHA256
    base['shared_exchange'] = shared
    base['option_contrast'] = option
    base['step_lines'] = lines
    base['limitations'] = list(LIMITATIONS)
    return base


def _step_html(line: dict, orientation: chess.Color) -> str:
    items = []
    focus = chess.parse_square(line['focus_square'])
    for step in line['steps']:
        move = chess.Move.from_uci(step['uci'])
        board = chess.Board(step['fen_after'])
        picture = chess.svg.board(board, orientation=orientation, lastmove=move,
                                  fill={focus: '#ffdf6688'}, size=320)
        detail = (f' Captures a {step["captured_piece"]} on '
                  f'{step["capture_square"]}.' if step['captured_piece'] else '')
        check = ' Gives check.' if step['gives_check'] else ''
        items.append(f'<li><details class="step"><summary>{escape(step["notation"])}'
                     f'{escape(detail + check)}</summary><figure data-focus="{escape(line["focus_square"])}">'
                     f'<figcaption>After {escape(step["notation"])} · gold marks '
                     f'{escape(line["focus_square"])}.</figcaption>{picture}</figure></details></li>')
    source_label = ('Saved engine line' if line['source_kind'] == 'saved_v3_line' else
                    'Hypothetical legal illustration; not a saved engine line'
                    if line['hypothetical'] else
                    'Legal counterfactual; not a saved engine line')
    return (f'<details class="line"><summary>{escape(line["title"])} '
            f'<span class="muted">({escape(source_label)})</span></summary>'
            f'<ol>{"".join(items)}</ol></details>')


def _ordinal(number: int) -> str:
    suffix = ('th' if 11 <= number % 100 <= 13 else
              {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th'))
    return f'{number}{suffix}'


def render(record: dict) -> bytes:
    selection = record['selection']
    board = chess.Board(selection['fen_before'])
    shared = record['shared_exchange']
    option = record['option_contrast']
    played = selection['played_san']
    alternative = selection['alternative_san']
    if shared['status'] == 'supported':
        mover = chess.COLOR_NAMES[board.turn].title()
        responder = chess.COLOR_NAMES[not board.turn].title()
        explanation = (f'In the saved {played} line, {responder} takes {mover}\'s pawn on '
                       f'{shared["focus_square"]} before the queens trade. '
                       f'{alternative} does not stop that same exchange: the '
                       'same queen trade is legal and reaches the same board.')
    elif alternative is None:
        explanation = ('This saved line shows one legal continuation after the played move. '
                       'No alternative was recorded for this review.')
    else:
        explanation = ('This saved line shows one legal continuation after the played move. '
                       'A matching pawn-and-queen exchange after the alternative was not established.')
    if option['status'] == 'supported':
        reply = record['threat_contrast']['shared_reply']['reply_san']
        if shared['status'] == 'supported' and board.turn == chess.WHITE:
            explanation += (f' After {board.fullmove_number}.{alternative} {reply}, '
                            f'White can choose {board.fullmove_number + 1}.'
                            f'{option["san_after_alternative"]} instead of trading queens.')
        else:
            side = chess.COLOR_NAMES[board.turn].title()
            explanation += (f' After {alternative} and the reply {reply}, {side} '
                            f'has a legal option: {option["san_after_alternative"]}.')
        facts = []
        if option['capture_piece']:
            facts.append(f'captures a {option["capture_piece"]}')
        if option['gives_check']:
            facts.append('gives check')
        if facts:
            explanation += f' It {" and ".join(facts)}.'
        explanation += ' This is not a best-response claim.'
    explanation += ((' This legal line does not establish why Stockfish scored the move '
                     'as it did.') if alternative is None else
                    (' These examples do not prove Stockfish\'s complete reason '
                     'for scoring the moves differently.'))
    context = record['engine_context']
    score = (f'{played}: {v4._score_text(context["played_score"])}.')
    if context['alternative_score'] is not None:
        score += f' {alternative}: {v4._score_text(context["alternative_score"])}.'
    lines = ''.join(_step_html(line, board.turn) for line in record['step_lines'])
    limitations = ''.join(f'<li>{escape(item)}</li>' for item in record['limitations'])
    move_comparison = (f'{escape(played)} compared with {escape(alternative)}'
                       if alternative is not None else escape(played))
    start_caption = ('Before either candidate move' if alternative is not None
                     else 'Before the played move')
    start_heading = ('Start with the same position' if alternative is not None
                     else 'Start with the position')
    contrast_heading = ('What changes between the moves?' if alternative is not None
                        else 'What does the saved line show?')
    search_note = (f'This was one root-restricted paired search with '
                   f'{context["requested_nodes"]:,} requested nodes.'
                   if alternative is not None else
                   f'The saved search requested {context["requested_nodes"]:,} nodes.')
    css = '''body{margin:0;background:#0d1419;color:#e9edf0;font:16px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:1000px;margin:auto;padding:32px 20px 70px}h1{font-size:2.5rem;line-height:1.1}
h2{margin:0 0 12px}.eyebrow{color:#a9d9c5;text-transform:uppercase;font-size:.75rem;letter-spacing:.1em}
.panel,.line{background:#162027;border:1px solid #38505a;border-radius:12px;padding:18px;margin:18px 0}
summary{cursor:pointer;color:#c8e7da;font-weight:650}details.step{margin:12px 0}
details.step summary{color:#e9edf0}ol{padding-left:26px}li{padding:3px 0}
figure{margin:12px 0 20px}figure svg{width:min(100%,320px);height:auto;display:block}
figcaption,.muted,footer{color:#b4c2c9;font-size:.85rem}.limit{border-left:4px solid #edc889}
code{overflow-wrap:anywhere}'''
    preboard = chess.svg.board(board, orientation=board.turn, size=320)
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chess practice lesson · {escape(selection['white'])} vs {escape(selection['black'])}</title>
<style>{css}</style></head><body><main>
<p class="eyebrow">Offline post-game study · v5 candidate</p>
<h1>{escape(selection['white'])} vs {escape(selection['black'])}</h1>
<p>{chess.COLOR_NAMES[board.turn].title()}'s {_ordinal(board.fullmove_number)} move (game ply {selection['ply']}):
{move_comparison}.
These are evaluator-side examples from a saved game, not a model explanation.</p>
<section class="panel"><h2>{start_heading}</h2><figure><figcaption>{start_caption}</figcaption>{preboard}</figure></section>
<section class="panel"><h2>{contrast_heading}</h2>
<p>{escape(explanation)}</p>
<p class="muted">Open a line, then each move to see the legal board position. Gold marks the square in question.</p>
{lines}</section>
<section class="panel"><h2>What the engine observed</h2><p>{escape(score)}</p>
<p>{search_note}
These numbers are not Chess.com move labels or a measured explanation of cause.</p></section>
<section class="panel limit"><h2>Limits</h2><ul>{limitations}</ul></section>
<footer><p>PGN SHA-256: <code>{record['source']['pgn_sha256']}</code></p>
<p>Verified v3 receipt SHA-256: <code>{record['source']['v3_receipt_sha256']}</code></p>
<p>Verified v3 page SHA-256: <code>{record['source']['v3_page_sha256']}</code></p>
<p>Approved v4 source SHA-256: <code>{record['source']['v4_source_sha256']}</code></p></footer>
</main></body></html>'''
    return html.encode('utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('review', 'verify'):
        current = sub.add_parser(command)
        current.add_argument('--pgn', type=Path, required=True)
        current.add_argument('--v3-dir', type=Path, required=True)
        current.add_argument('--v3-receipt-sha256', required=True)
        current.add_argument('--v3-page-sha256', required=True)
        current.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    _check_v4_source()
    pgn_raw, v3_raw, v3_page_raw, v3_record = v4.load_verified_v3(
        args.pgn, args.v3_dir, v3_receipt_sha256=args.v3_receipt_sha256,
        v3_page_sha256=args.v3_page_sha256)
    expected = build_record(pgn_raw, v3_raw, v3_page_raw, v3_record)
    record_bytes = previous.canonical(expected) + b'\n'
    page = render(expected)
    if len(record_bytes) > MAX_RECORD_BYTES or len(page) > MAX_PAGE_BYTES:
        raise ValueError('v5_output_too_large')
    if args.command == 'review':
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / 'review.json').write_bytes(record_bytes)
        (args.output_dir / 'index.html').write_bytes(page)
    else:
        with (args.output_dir / 'review.json').open('rb') as stream:
            if stream.read(MAX_RECORD_BYTES + 1) != record_bytes:
                raise ValueError('v5_record_differs_from_inputs')
        with (args.output_dir / 'index.html').open('rb') as stream:
            if stream.read(MAX_PAGE_BYTES + 1) != page:
                raise ValueError('v5_page_differs_from_receipt')
    print(json.dumps({'schema': SCHEMA, 'status': 'verified', 'engine_calls': 0,
                      'model_calls': 0, 'page_sha256': previous.digest(page),
                      'output': str(args.output_dir / 'index.html')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
