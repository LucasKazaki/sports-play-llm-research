#!/usr/bin/env python3
"""Offline post-game review of one PGN move with a pinned local Stockfish.

The output is a source-bound evidence page, not a model explanation. The program
does not send game data anywhere and does not use the no-forward generator.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import chess.svg

import chess_real_evidence_interface as ui


SCHEMA = 'chess-completed-game-review/v2'
ENGINE = ui.ROOT / 'vendor/stockfish-19/stockfish/stockfish-windows-x86-64-universal.exe'
ENGINE_SHA256 = '45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0'
MAX_PGN_BYTES = 2 * 1024 * 1024
MAX_PLIES = 1000
RESULTS = {'1-0', '0-1', '1/2-1/2'}
LIMITATIONS = [
    'Post-game local review only; PGN Result is a supplied completion declaration.',
    'The played move uses a root-restricted engine search; the alternative uses a separate unrestricted search.',
    'Bounded Stockfish scores are observations, not proof of best play or a human explanation.',
    'No model commentary, independent chess review, or learning outcome is present.',
]


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def engine_ready() -> dict:
    if not ENGINE.is_file() or digest(ENGINE.read_bytes()) != ENGINE_SHA256:
        raise ValueError('pinned_stockfish_binary_missing_or_changed')
    return {'path': str(ENGINE), 'sha256': ENGINE_SHA256}


def load_completed_game(path: Path) -> tuple[chess.pgn.Game, bytes, list[chess.Move]]:
    with path.open('rb') as stream:
        raw = stream.read(MAX_PGN_BYTES + 1)
    if not raw or len(raw) > MAX_PGN_BYTES:
        raise ValueError('pgn_empty_or_too_large')
    try:
        source = raw.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('pgn_not_utf8') from error
    stream = StringIO(source)
    game = chess.pgn.read_game(stream)
    if game is None or chess.pgn.read_game(stream) is not None:
        raise ValueError('expected_exactly_one_game')
    if game.errors:
        raise ValueError('pgn_parse_or_replay_error')
    if game.headers.get('Variant', 'Standard') != 'Standard':
        raise ValueError('only_standard_chess_supported')
    if game.headers.get('Result') not in RESULTS:
        raise ValueError('completed_game_result_required')
    moves = list(game.mainline_moves())
    if not 1 <= len(moves) <= MAX_PLIES:
        raise ValueError('pgn_move_count_out_of_bounds')
    board = game.board()
    if not board.is_valid():
        raise ValueError('invalid_initial_board')
    for move in moves:
        if move not in board.legal_moves:
            raise ValueError('illegal_pgn_move')
        board.push(move)
    return game, raw, moves


def board_at_ply(game: chess.pgn.Game, moves: list[chess.Move], ply: int) -> chess.Board:
    if type(ply) is not int or not 1 <= ply <= len(moves):
        raise ValueError('requested_ply_out_of_bounds')
    board = game.board()
    for move in moves[:ply - 1]:
        board.push(move)
    return board


def score_record(info: dict, side_to_move: bool) -> dict:
    if 'score' not in info:
        raise ValueError('engine_score_missing')
    score = info['score'].pov(side_to_move)
    kind = 'mate' if score.is_mate() else 'cp'
    value = score.mate() if kind == 'mate' else score.score()
    if type(value) is not int:
        raise ValueError('engine_score_unrepresentable')
    if info.get('lowerbound') and info.get('upperbound'):
        raise ValueError('engine_score_conflicting_bounds')
    bound = 'lower' if info.get('lowerbound') else 'upper' if info.get('upperbound') else 'exact'
    return {'type': kind, 'value': value, 'bound': bound, 'order': 'engine_score',
            'perspective': 'side_to_move', 'side_to_move': chess.COLOR_NAMES[side_to_move]}


def display_score(score: dict) -> str:
    """Render the typed engine value without promoting it to a proved result."""
    ui.score_label(score)
    qualifier = {'exact': 'unqualified event', 'lower': 'lower bound',
                 'upper': 'upper bound'}[score['bound']]
    if score['type'] == 'mate':
        return (f"Engine mate score {score['value']:+d}, "
                f"{score['side_to_move'].title()} perspective · {qualifier}")
    return (f"Engine score {score['value']:+d} centipawns, "
            f"{score['side_to_move'].title()} perspective · {qualifier}")


def observation(board: chess.Board, info: dict, expected_move: chess.Move | None = None) -> dict:
    pv = info.get('pv')
    if not isinstance(pv, list) or not pv:
        raise ValueError('engine_pv_missing')
    if expected_move is not None and pv[0] != expected_move:
        raise ValueError('restricted_engine_root_changed')
    replay = board.copy(stack=False)
    for move in pv:
        if move not in replay.legal_moves:
            raise ValueError('engine_pv_not_legal')
        replay.push(move)
    if type(info.get('nodes')) is not int or info['nodes'] <= 0:
        raise ValueError('engine_nodes_missing')
    return {'move_uci': pv[0].uci(), 'san': board.san(pv[0]),
            'score': score_record(info, board.turn),
            'depth': info.get('depth'), 'nodes_observed': info['nodes'],
            'pv_uci': [move.uci() for move in pv]}


def analyze(game: chess.pgn.Game, raw: bytes, moves: list[chess.Move],
            ply: int, nodes: int) -> dict:
    if type(nodes) is not int or not 1_000 <= nodes <= 100_000:
        raise ValueError('nodes_out_of_bounds')
    engine_ready()
    before = board_at_ply(game, moves, ply)
    selected_move = moves[ply - 1]
    after = before.copy(stack=False)
    after.push(selected_move)
    with chess.engine.SimpleEngine.popen_uci(str(ENGINE)) as engine:
        engine.configure({'Threads': 1, 'Hash': 16})
        actual_info = engine.analyse(before, chess.engine.Limit(nodes=nodes),
                                     root_moves=[selected_move])
        best_info = engine.analyse(before, chess.engine.Limit(nodes=nodes), multipv=2)
        engine_name = engine.id.get('name', 'Stockfish')
    actual = observation(before, actual_info, selected_move)
    alternatives = []
    for info in best_info if isinstance(best_info, list) else [best_info]:
        if info.get('pv') and info['pv'][0] != selected_move:
            alternatives.append(observation(before, info))
            break
    headers = dict(game.headers)
    timeline = []
    replay = game.board()
    for index, played in enumerate(moves, 1):
        timeline.append({'ply': index, 'san': replay.san(played), 'uci': played.uci()})
        replay.push(played)
    return {
        'schema': SCHEMA, 'source': {'pgn_sha256': digest(raw), 'pgn_bytes': len(raw),
                                    'headers': headers, 'plies': len(moves),
                                    'declared_completed': True},
        'timeline': timeline,
        'selection': {'ply': ply, 'fen_before': before.fen(), 'fen_after': after.fen(),
                      'actual_move_uci': selected_move.uci(), 'actual_move_san': before.san(selected_move),
                      'side_to_move': chess.COLOR_NAMES[before.turn],
                      'capture': before.is_capture(selected_move),
                      'gives_check': before.gives_check(selected_move),
                      'checkmate': after.is_checkmate()},
        'engine': {'name': engine_name, 'sha256': ENGINE_SHA256,
                   'settings': {'threads': 1, 'hash_mb': 16, 'requested_nodes_per_search': nodes,
                                'searches': 2, 'multipv_for_unrestricted_search': 2},
                   'actual_move': actual, 'other_searched_move': alternatives[0] if alternatives else None},
        'limitations': list(LIMITATIONS),
    }


def validate_record(record: dict, game: chess.pgn.Game, raw: bytes,
                    moves: list[chess.Move]) -> None:
    if record.get('schema') != SCHEMA or record.get('source', {}).get('pgn_sha256') != digest(raw):
        raise ValueError('record_source_binding_changed')
    selection = record['selection']
    board = board_at_ply(game, moves, selection['ply'])
    move = moves[selection['ply'] - 1]
    after = board.copy(stack=False)
    after.push(move)
    expected_headers = dict(game.headers)
    if (record['source']['plies'] != len(moves)
            or record['source']['pgn_bytes'] != len(raw)
            or record['source']['headers'] != expected_headers
            or record['source']['declared_completed'] is not True
            or selection['fen_before'] != board.fen()
            or selection['fen_after'] != after.fen()
            or selection['actual_move_uci'] != move.uci()
            or selection['actual_move_san'] != board.san(move)
            or selection['side_to_move'] != chess.COLOR_NAMES[board.turn]
            or selection['capture'] is not board.is_capture(move)
            or selection['gives_check'] is not board.gives_check(move)
            or selection['checkmate'] is not after.is_checkmate()):
        raise ValueError('record_board_replay_changed')
    if record['limitations'] != LIMITATIONS:
        raise ValueError('record_limitations_changed')
    replay = game.board()
    expected_timeline = []
    for index, played in enumerate(moves, 1):
        expected_timeline.append({'ply': index, 'san': replay.san(played),
                                  'uci': played.uci()})
        replay.push(played)
    if record['timeline'] != expected_timeline:
        raise ValueError('record_timeline_changed')
    if record['engine']['sha256'] != ENGINE_SHA256 or record['engine']['name'] != 'Stockfish 19':
        raise ValueError('record_engine_identity_changed')
    settings = record['engine']['settings']
    if (settings['threads'] != 1 or settings['hash_mb'] != 16
            or settings['searches'] != 2 or settings['multipv_for_unrestricted_search'] != 2
            or type(settings['requested_nodes_per_search']) is not int
            or not 1_000 <= settings['requested_nodes_per_search'] <= 100_000):
        raise ValueError('record_engine_settings_changed')
    for label in ('actual_move', 'other_searched_move'):
        item = record['engine'][label]
        if item is None:
            continue
        pv = [chess.Move.from_uci(value) for value in item['pv_uci']]
        replay = board.copy(stack=False)
        for candidate in pv:
            if candidate not in replay.legal_moves:
                raise ValueError('record_engine_line_not_legal')
            replay.push(candidate)
        if item['move_uci'] != pv[0].uci() or item['san'] != board.san(pv[0]):
            raise ValueError('record_engine_move_changed')
        if (item['score']['side_to_move'] != selection['side_to_move']
                or type(item['nodes_observed']) is not int or item['nodes_observed'] <= 0
                or type(item['depth']) is not int or item['depth'] <= 0):
            raise ValueError('record_engine_observation_invalid')
        ui.score_label(item['score'])
    if record['engine']['actual_move']['move_uci'] != move.uci():
        raise ValueError('record_actual_engine_move_changed')
    other = record['engine']['other_searched_move']
    if other is not None and other['move_uci'] == move.uci():
        raise ValueError('record_alternative_duplicates_played_move')


def annotated_pgn(game: chess.pgn.Game, moves: list[chess.Move], record: dict) -> bytes:
    """Export legal mainline and separately labeled saved engine evidence."""
    exported = chess.pgn.Game()
    exported.setup(game.board())
    # JSON canonicalization sorts receipt keys. Replay the source's header order
    # so review and verify export identical PGN bytes for multi-header games.
    for key, value in game.headers.items():
        exported.headers[key] = value
    node = exported
    selected_parent = None
    selected_node = None
    for index, move in enumerate(moves, 1):
        if index == record['selection']['ply']:
            selected_parent = node
        node = node.add_main_variation(move)
        if index == record['selection']['ply']:
            selected_node = node
    actual = record['engine']['actual_move']
    nodes = record['engine']['settings']['requested_nodes_per_search']
    selected_node.comment = (f"Local Stockfish observation, root restricted, "
                             f"{nodes} requested nodes: {display_score(actual['score'])}. "
                             "Bounded search; not a human explanation.")
    alternative = record['engine']['other_searched_move']
    if alternative is not None:
        branch = selected_parent
        for index, uci in enumerate(alternative['pv_uci']):
            branch = branch.add_variation(chess.Move.from_uci(uci))
            if index == 0:
                branch.comment = (f"Other searched move, separate unrestricted search: "
                                  f"{display_score(alternative['score'])}. "
                                  "Engine trace, not a proven comparison.")
    return (str(exported).rstrip() + '\n').encode('utf-8')


def render(record: dict) -> bytes:
    selected = record['selection']
    board = chess.Board(selected['fen_before'])
    move = chess.Move.from_uci(selected['actual_move_uci'])
    after = board.copy(stack=False)
    after.push(move)
    side = selected['side_to_move'].title()
    before_svg = chess.svg.board(board, orientation=board.turn, coordinates=True, size=420)
    after_svg = chess.svg.board(after, orientation=board.turn, coordinates=True,
                                lastmove=move, size=420)
    alternative = record['engine']['other_searched_move']
    alternative_figure = ''
    if alternative is not None:
        alternative_move = chess.Move.from_uci(alternative['move_uci'])
        other = board.copy(stack=False)
        other.push(alternative_move)
        other_svg = chess.svg.board(other, orientation=board.turn, coordinates=True,
                                    lastmove=alternative_move, size=420)
        alternative_figure = (f'<figure><figcaption>After other searched move '
                              f'{ui.safe(alternative["san"])}</figcaption>{other_svg}</figure>')
    facts = [
        f"{side} played {selected['actual_move_san']} from "
        f"{chess.square_name(move.from_square)} to {chess.square_name(move.to_square)}.",
        'The move captures a piece.' if selected['capture'] else 'The move does not capture a piece.',
        'The move gives check.' if selected['gives_check'] else 'The move does not give check.',
    ]
    if selected['checkmate']:
        facts.append('The move ends the game in checkmate.')
    claims = ''.join(f'<li><span class="tag">Rule verified</span>{ui.safe(fact)}</li>' for fact in facts)
    observed = []
    for label, item in [('Played move', record['engine']['actual_move']),
                        ('Other searched move', alternative)]:
        if item is None:
            continue
        observed.append(
            f'<tr><td>{label}</td><td><strong>{ui.safe(item["san"])}</strong>'
            f'<span class="muted">{ui.safe(item["move_uci"])}</span></td>'
            f'<td>{ui.safe(display_score(item["score"]))}</td>'
            f'<td>{ui.safe(item["depth"])}</td><td>{ui.safe(item["nodes_observed"])}</td></tr>')
    headers = record['source']['headers']
    title = f"{headers['White'] or 'White'} vs {headers['Black'] or 'Black'}"
    limitations = ''.join(f'<li>{ui.safe(value)}</li>' for value in record['limitations'])
    timeline = ''.join(
        f'<span class="move-chip{" selected" if item["ply"] == selected["ply"] else ""}">'
        f'{item["ply"]}. {ui.safe(item["san"])}</span>'
        for item in record['timeline'])
    css = ui.CSS.read_text(encoding='utf-8') + '''
.move-list{display:flex;gap:7px;flex-wrap:wrap;max-height:190px;overflow:auto;margin:12px 0 20px}
.move-chip{border:1px solid var(--line);border-radius:6px;padding:3px 7px;font-size:.82rem;color:var(--muted)}
.move-chip.selected{color:var(--bg);background:var(--gold);border-color:var(--gold);font-weight:700}
'''
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Post-game chess review · {ui.safe(title)}</title><style>{css}</style></head>
<body><main><section class="hero"><p class="eyebrow">Offline post-game review</p>
<h1>{ui.safe(title)}</h1><p class="lead">Played move at ply {selected['ply']} of {record['source']['plies']}:
<strong>{ui.safe(selected['actual_move_san'])}</strong>. Rule facts and local Stockfish observations
are shown separately. This report contains no generated explanation.</p>
<div class="case-meta"><span>{side} to move</span><span>{side} at bottom</span>
<span>PGN result: {ui.safe(headers['Result'])}</span></div></section>
<section class="case"><div class="boards"><figure><figcaption>Before the played move</figcaption>
{before_svg}</figure><figure><figcaption>After {ui.safe(selected['actual_move_san'])}</figcaption>
{after_svg}</figure>{alternative_figure}</div>
<div class="columns"><div class="panel"><p class="eyebrow">Checkable claims</p>
<h3>What the board proves</h3><ul class="claims">{claims}</ul>
<p class="small">Deterministic templates from legal PGN replay.</p></div>
<div class="panel"><p class="eyebrow">Strategic explanation</p><h3>Withheld</h3>
<p>The engine score and legal facts cannot by themselves explain why a human should choose
this move. No model claim or teaching-quality review is available.</p></div></div>
<div class="panel"><p class="eyebrow">Local engine evidence</p><h3>Played move and alternative</h3>
<p class="small">The two observations come from separate searches with
{record['engine']['settings']['requested_nodes_per_search']:,} requested nodes each.
The played move was searched with its root move restricted. Scores and bounds retain the
perspective of the player to move; they are not an exact comparison.</p>
<div class="table-wrap"><table><thead><tr><th>Search</th><th>Move</th><th>Score and perspective</th>
<th>Depth</th><th>Observed nodes</th></tr></thead><tbody>{''.join(observed)}</tbody></table></div>
<details><summary>Show raw engine line for played move</summary><p class="small">
Engine trace only; no model used this line.</p><code>
{ui.safe(' '.join(record['engine']['actual_move']['pv_uci']))}</code></details></div>
<div class="panel"><p class="eyebrow">Game record</p><h3>Move list</h3>
<p class="small">The highlighted move is the one reviewed above. This timeline is
legally replayed from the supplied PGN.</p><div class="move-list">{timeline}</div>
<p><a href="review.pgn" download>Download annotated PGN ↧</a></p></div>
<div class="notice"><strong>Use boundary</strong><ul>{limitations}</ul></div></section>
<footer><p>PGN SHA-256: <code>{record['source']['pgn_sha256']}</code></p>
<p>Stockfish binary SHA-256: <code>{ENGINE_SHA256}</code></p></footer></main></body></html>'''
    return html.encode('utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    moves_command = sub.add_parser('moves')
    moves_command.add_argument('--pgn', type=Path, required=True)
    review = sub.add_parser('review')
    review.add_argument('--pgn', type=Path, required=True)
    review.add_argument('--ply', type=int, required=True)
    review.add_argument('--nodes', type=int, default=10_000)
    review.add_argument('--output-dir', type=Path, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--pgn', type=Path, required=True)
    verify.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        print(json.dumps({'schema': SCHEMA, 'engine': engine_ready(), 'status': 'ready'},
                         sort_keys=True))
        return 0
    game, raw, moves = load_completed_game(args.pgn)
    if args.command == 'moves':
        board = game.board()
        for index, played in enumerate(moves, 1):
            print(f'{index:>3}. {board.san(played):<8} {played.uci()}')
            board.push(played)
        return 0
    if args.command == 'review':
        record = analyze(game, raw, moves, args.ply, args.nodes)
        validate_record(record, game, raw, moves)
        page = render(record)
        export = annotated_pgn(game, moves, record)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / 'review.json').write_bytes(canonical(record) + b'\n')
        (args.output_dir / 'index.html').write_bytes(page)
        (args.output_dir / 'review.pgn').write_bytes(export)
    else:
        record = json.loads((args.output_dir / 'review.json').read_bytes())
        validate_record(record, game, raw, moves)
        page = render(record)
        export = annotated_pgn(game, moves, record)
        if (args.output_dir / 'index.html').read_bytes() != page:
            raise ValueError('rendered_page_differs_from_receipt')
        if (args.output_dir / 'review.pgn').read_bytes() != export:
            raise ValueError('annotated_pgn_differs_from_receipt')
    print(json.dumps({'schema': SCHEMA, 'status': 'verified', 'engine_calls': 0 if args.command == 'verify' else 2,
                      'model_calls': 0, 'page_sha256': digest(page),
                      'output': str(args.output_dir / 'index.html')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
