#!/usr/bin/env python3
"""Create a bounded, offline comparison for one move in a completed chess PGN.

This is deterministic post-game study material, not an LLM commentator. Engine
continuations stay in the evaluator-side receipt and never enter a generator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import chess
import chess.engine
import chess.svg

import chess_review_completed_game as previous
import chess_real_evidence_interface as ui


SCHEMA = 'chess-paired-review/v3'
LIMITATIONS = [
    'Post-game study only; the PGN Result is a supplied completion declaration.',
    'When two moves are compared, they share one bounded root-restricted MultiPV search. Its scores are observations, not proof.',
    'An earlier unrestricted search only selects the alternative; its score is not used in the comparison.',
    'A saved engine line illustrates one legal continuation. It does not explain why Stockfish chose its move.',
    'No LLM commentary, independent chess review, or teaching-quality result is claimed.',
]
MAX_RECORD_BYTES = 1_000_000


def _keys(value: object, expected: set[str], error: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(error)


def _moves_from_info(board: chess.Board, infos: object) -> list[chess.Move]:
    if not isinstance(infos, list) or len(infos) != 2:
        raise ValueError('alternative_search_did_not_return_two_lines')
    roots = []
    for info in infos:
        if not isinstance(info, dict) or not isinstance(info.get('pv'), list) or not info['pv']:
            raise ValueError('alternative_search_missing_line')
        root = info['pv'][0]
        if root not in board.legal_moves or root in roots:
            raise ValueError('alternative_search_invalid_root')
        roots.append(root)
    return roots


def compare_scores(played: dict, alternative: dict | None) -> dict:
    """Compare only unqualified centipawn observations from the same paired call."""
    if alternative is None:
        return {'status': 'unavailable', 'reason': 'only_one_legal_move', 'delta_cp': None}
    for score in (played, alternative):
        _keys(score, {'type', 'value', 'bound', 'order', 'perspective', 'side_to_move'},
              'invalid_comparison_score_shape')
        ui.score_label(score)
        if score['order'] != 'engine_score':
            raise ValueError('invalid_comparison_score_order')
    if played['side_to_move'] != alternative['side_to_move']:
        raise ValueError('comparison_perspective_mismatch')
    if (played['type'] != 'cp' or alternative['type'] != 'cp'
            or played['bound'] != 'exact' or alternative['bound'] != 'exact'):
        return {'status': 'abstain', 'reason': 'mate_or_bounded_score', 'delta_cp': None}
    delta = alternative['value'] - played['value']
    status = ('alternative_higher' if delta > 0 else
              'played_higher' if delta < 0 else 'equal')
    return {'status': status, 'reason': None, 'delta_cp': delta}


def first_reply_fact(board: chess.Board, observation: dict) -> dict | None:
    """Replay the first reply from an evaluator-side line; make no causal claim."""
    pv = observation['pv_uci']
    if len(pv) < 2:
        return None
    replay = board.copy(stack=False)
    root = chess.Move.from_uci(pv[0])
    if root not in replay.legal_moves:
        raise ValueError('record_engine_line_not_legal')
    replay.push(root)
    moved_piece = replay.piece_at(root.to_square)
    previously_attacked = replay.is_attacked_by(replay.turn, root.to_square)
    reply = chess.Move.from_uci(pv[1])
    if reply not in replay.legal_moves:
        raise ValueError('record_engine_line_not_legal')
    captured = (chess.PAWN if replay.is_en_passant(reply) else
                replay.piece_type_at(reply.to_square))
    san = replay.san(reply)
    check = replay.gives_check(reply)
    replay.push(reply)
    newly_attacked = (moved_piece is not None and
                      replay.piece_at(root.to_square) == moved_piece and
                      not previously_attacked and
                      replay.is_attacked_by(not replay.turn, root.to_square))
    return {'san': san, 'uci': reply.uci(), 'captured_piece':
            chess.piece_name(captured) if captured else None,
            'gives_check': check, 'checkmate': replay.is_checkmate(),
            'new_attack_on_moved_piece':
            {'piece': chess.piece_name(moved_piece.piece_type),
             'square': chess.square_name(root.to_square)} if newly_attacked else None}


def analyze(game, raw: bytes, moves: list[chess.Move], ply: int, nodes: int) -> dict:
    if type(nodes) is not int or not 1_000 <= nodes <= 100_000:
        raise ValueError('nodes_out_of_bounds')
    previous.engine_ready()
    board = previous.board_at_ply(game, moves, ply)
    played_move = moves[ply - 1]
    after = board.copy(stack=False)
    after.push(played_move)
    legal_count = board.legal_moves.count()
    with chess.engine.SimpleEngine.popen_uci(str(previous.ENGINE)) as engine:
        engine.configure({'Threads': 1, 'Hash': 16})
        if engine.id.get('name') != 'Stockfish 19':
            raise ValueError('engine_identity_changed')
        roots = []
        alternative = None
        if legal_count > 1:
            discovery = engine.analyse(board, chess.engine.Limit(nodes=nodes), multipv=2)
            roots = _moves_from_info(board, discovery)
            alternative = next(root for root in roots if root != played_move)
        requested_roots = [played_move] + ([alternative] if alternative else [])
        paired = engine.analyse(board, chess.engine.Limit(nodes=nodes),
                                root_moves=requested_roots, multipv=len(requested_roots))
    infos = paired if isinstance(paired, list) else [paired]
    if len(infos) != len(requested_roots):
        raise ValueError('paired_search_missing_line')
    by_root = {}
    for info in infos:
        item = previous.observation(board, info)
        root = item['move_uci']
        if root in by_root or root not in {move.uci() for move in requested_roots}:
            raise ValueError('paired_search_root_changed')
        by_root[root] = item
    if set(by_root) != {move.uci() for move in requested_roots}:
        raise ValueError('paired_search_missing_root')
    observations = [by_root[move.uci()] for move in requested_roots]
    record = {
        'schema': SCHEMA,
        'source': {'pgn_sha256': previous.digest(raw), 'pgn_bytes': len(raw),
                   'headers': dict(game.headers), 'plies': len(moves)},
        'selection': {'ply': ply, 'fen_before': board.fen(), 'fen_after': after.fen(),
                      'played_uci': played_move.uci(), 'played_san': board.san(played_move),
                      'side_to_move': chess.COLOR_NAMES[board.turn],
                      'legal_move_count': legal_count,
                      'capture': board.is_capture(played_move),
                      'gives_check': board.gives_check(played_move),
                      'checkmate': after.is_checkmate()},
        'engine': {'name': 'Stockfish 19', 'sha256': previous.ENGINE_SHA256,
                   'settings': {'threads': 1, 'hash_mb': 16,
                                'requested_nodes_per_search': nodes,
                                'searches': 2 if alternative else 1,
                                'discovery_multipv': 2 if alternative else 0,
                                'paired_multipv': len(requested_roots)},
                   'discovery_roots_uci': [move.uci() for move in roots],
                   'alternative_uci': alternative.uci() if alternative else None,
                   'paired_observations': observations},
        'comparison': compare_scores(observations[0]['score'],
                                     observations[1]['score'] if alternative else None),
        'limitations': list(LIMITATIONS),
    }
    validate_record(record, game, raw, moves)
    return record


def validate_record(record: dict, game, raw: bytes, moves: list[chess.Move]) -> None:
    _keys(record, {'schema', 'source', 'selection', 'engine', 'comparison', 'limitations'},
          'invalid_record_shape')
    if record['schema'] != SCHEMA:
        raise ValueError('invalid_record_schema')
    source = record['source']
    _keys(source, {'pgn_sha256', 'pgn_bytes', 'headers', 'plies'}, 'invalid_source_shape')
    if type(source['pgn_bytes']) is not int or type(source['plies']) is not int:
        raise ValueError('invalid_source_types')
    if source != {'pgn_sha256': previous.digest(raw), 'pgn_bytes': len(raw),
                  'headers': dict(game.headers), 'plies': len(moves)}:
        raise ValueError('record_source_binding_changed')
    selection = record['selection']
    _keys(selection, {'ply', 'fen_before', 'fen_after', 'played_uci', 'played_san',
                      'side_to_move', 'legal_move_count', 'capture', 'gives_check', 'checkmate'},
          'invalid_selection_shape')
    if (type(selection['legal_move_count']) is not int or
            any(type(selection[name]) is not bool for name in
                ('capture', 'gives_check', 'checkmate'))):
        raise ValueError('invalid_selection_types')
    board = previous.board_at_ply(game, moves, selection['ply'])
    played_move = moves[selection['ply'] - 1]
    after = board.copy(stack=False)
    after.push(played_move)
    expected_selection = {
        'ply': selection['ply'], 'fen_before': board.fen(), 'fen_after': after.fen(),
        'played_uci': played_move.uci(), 'played_san': board.san(played_move),
        'side_to_move': chess.COLOR_NAMES[board.turn],
        'legal_move_count': board.legal_moves.count(),
        'capture': board.is_capture(played_move),
        'gives_check': board.gives_check(played_move),
        'checkmate': after.is_checkmate(),
    }
    if selection != expected_selection:
        raise ValueError('record_board_replay_changed')
    engine = record['engine']
    _keys(engine, {'name', 'sha256', 'settings', 'discovery_roots_uci',
                   'alternative_uci', 'paired_observations'}, 'invalid_engine_shape')
    if engine['name'] != 'Stockfish 19' or engine['sha256'] != previous.ENGINE_SHA256:
        raise ValueError('record_engine_identity_changed')
    settings = engine['settings']
    _keys(settings, {'threads', 'hash_mb', 'requested_nodes_per_search', 'searches',
                     'discovery_multipv', 'paired_multipv'}, 'invalid_settings_shape')
    if any(type(value) is not int for value in settings.values()):
        raise ValueError('invalid_settings_types')
    nodes = settings['requested_nodes_per_search']
    if type(nodes) is not int or not 1_000 <= nodes <= 100_000:
        raise ValueError('record_nodes_out_of_bounds')
    roots = engine['discovery_roots_uci']
    if not isinstance(roots, list):
        raise ValueError('invalid_discovery_roots')
    if selection['legal_move_count'] > 1:
        if len(roots) != 2 or len(set(roots)) != 2:
            raise ValueError('invalid_discovery_roots')
        try:
            discovery_moves = [chess.Move.from_uci(value) for value in roots]
        except (TypeError, ValueError) as error:
            raise ValueError('invalid_discovery_roots') from error
        if any(move not in board.legal_moves for move in discovery_moves):
            raise ValueError('invalid_discovery_roots')
        alternative = next(move for move in discovery_moves if move != played_move)
        if engine['alternative_uci'] != alternative.uci():
            raise ValueError('alternative_selection_changed')
    else:
        if roots != [] or engine['alternative_uci'] is not None:
            raise ValueError('unexpected_alternative')
        alternative = None
    expected_settings = {'threads': 1, 'hash_mb': 16,
                         'requested_nodes_per_search': nodes,
                         'searches': 2 if alternative else 1,
                         'discovery_multipv': 2 if alternative else 0,
                         'paired_multipv': 2 if alternative else 1}
    if settings != expected_settings:
        raise ValueError('record_engine_settings_changed')
    observations = engine['paired_observations']
    requested = [played_move] + ([alternative] if alternative else [])
    if not isinstance(observations, list) or len(observations) != len(requested):
        raise ValueError('paired_observations_changed')
    for item, expected_move in zip(observations, requested):
        _keys(item, {'move_uci', 'san', 'score', 'depth', 'nodes_observed', 'pv_uci'},
              'invalid_observation_shape')
        if item['move_uci'] != expected_move.uci() or item['san'] != board.san(expected_move):
            raise ValueError('paired_observation_move_changed')
        if (type(item['depth']) is not int or item['depth'] <= 0 or
                type(item['nodes_observed']) is not int or item['nodes_observed'] <= 0):
            raise ValueError('paired_observation_search_metadata_invalid')
        score = item['score']
        _keys(score, {'type', 'value', 'bound', 'order', 'perspective', 'side_to_move'},
              'invalid_observation_score_shape')
        ui.score_label(score)
        if score['side_to_move'] != selection['side_to_move'] or score['order'] != 'engine_score':
            raise ValueError('paired_observation_perspective_changed')
        pv = item['pv_uci']
        if not isinstance(pv, list) or not 1 <= len(pv) <= 128:
            raise ValueError('paired_observation_line_size_invalid')
        replay = board.copy(stack=False)
        for uci in pv:
            try:
                move = chess.Move.from_uci(uci)
            except (TypeError, ValueError) as error:
                raise ValueError('record_engine_line_not_legal') from error
            if move not in replay.legal_moves:
                raise ValueError('record_engine_line_not_legal')
            replay.push(move)
        if pv[0] != expected_move.uci():
            raise ValueError('paired_observation_root_changed')
    expected_comparison = compare_scores(observations[0]['score'],
                                         observations[1]['score'] if alternative else None)
    _keys(record['comparison'], {'status', 'reason', 'delta_cp'},
          'invalid_comparison_shape')
    delta = record['comparison']['delta_cp']
    if delta is not None and type(delta) is not int:
        raise ValueError('invalid_comparison_delta')
    if record['comparison'] != expected_comparison:
        raise ValueError('record_comparison_changed')
    if record['limitations'] != LIMITATIONS:
        raise ValueError('record_limitations_changed')


def _move_fact(board: chess.Board, move: chess.Move) -> str:
    piece = board.piece_at(move.from_square)
    assert piece is not None
    role = chess.piece_name(piece.piece_type)
    capture = (chess.PAWN if board.is_en_passant(move) else
               board.piece_type_at(move.to_square))
    text = (f'{board.san(move)} moves the {role} from '
            f'{chess.square_name(move.from_square)} to {chess.square_name(move.to_square)}')
    if capture:
        text += f' and captures a {chess.piece_name(capture)}'
    if board.gives_check(move):
        text += ', giving check'
    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        text += ' and checkmate'
    return text + '.'


def _comparison_text(record: dict) -> str:
    comparison = record['comparison']
    observations = record['engine']['paired_observations']
    played = observations[0]
    if comparison['status'] == 'unavailable':
        return 'This was the only legal move, so there is no legal alternative to compare.'
    other = observations[1]
    if comparison['status'] == 'abstain':
        return (f'The paired search recorded {previous.display_score(played["score"])} for '
                f'{played["san"]} and {previous.display_score(other["score"])} for '
                f'{other["san"]}. The score types or bounds do not support a centipawn difference.')
    delta = comparison['delta_cp']
    if delta > 0:
        relation = f'the alternative scored {delta} centipawns higher'
    elif delta < 0:
        relation = f'the played move scored {-delta} centipawns higher'
    else:
        relation = 'both moves had the same recorded centipawn score'
    return (f'In one bounded paired Stockfish search, {played["san"]} scored '
            f'{played["score"]["value"]:+d} and {other["san"]} scored '
            f'{other["score"]["value"]:+d} centipawns from '
            f'{record["selection"]["side_to_move"].title()}\'s perspective; {relation}. '
            'This is an observed search result, not a proof that one move is objectively best.')


def _reply_text(board: chess.Board, observation: dict) -> str:
    reply = first_reply_fact(board, observation)
    if reply is None:
        return 'The saved engine line has no reply to inspect.'
    details = []
    if reply['captured_piece']:
        details.append(f'captures a {reply["captured_piece"]}')
    if reply['gives_check']:
        details.append('gives check')
    if reply['checkmate']:
        details.append('ends in checkmate')
    newly_attacked = reply['new_attack_on_moved_piece']
    if newly_attacked:
        details.append(f'newly attacks the {newly_attacked["piece"]} on '
                       f'{newly_attacked["square"]}')
    if details:
        return (f'In the saved line after the played move, the reply {reply["san"]} '
                f'{" and ".join(details)}. This is one legal continuation, not a forced reply.')
    return (f'The saved line begins with the reply {reply["san"]}. Its first reply '
            'shows no immediate capture, check, checkmate or new attack on the moved piece; this trace alone does not '
            'identify a simple tactical reason for the score.')


def render(record: dict) -> bytes:
    selection = record['selection']
    board = chess.Board(selection['fen_before'])
    played = chess.Move.from_uci(selection['played_uci'])
    after = board.copy(stack=False)
    after.push(played)
    observations = record['engine']['paired_observations']
    figures = [f'<figure><figcaption>Before {ui.safe(selection["played_san"])}</figcaption>'
               f'{chess.svg.board(board, orientation=board.turn, size=390)}</figure>',
               f'<figure><figcaption>After {ui.safe(selection["played_san"])}</figcaption>'
               f'{chess.svg.board(after, orientation=board.turn, lastmove=played, size=390)}</figure>']
    if len(observations) == 2:
        alternative = chess.Move.from_uci(observations[1]['move_uci'])
        other_board = board.copy(stack=False)
        other_board.push(alternative)
        figures.append(f'<figure><figcaption>After {ui.safe(observations[1]["san"])}</figcaption>'
                       f'{chess.svg.board(other_board, orientation=board.turn, lastmove=alternative, size=390)}</figure>')
    headers = record['source']['headers']
    title = f'{headers.get("White") or "White"} vs {headers.get("Black") or "Black"}'
    rows = ''.join(
        f'<tr><td>{"Played" if index == 0 else "Alternative"}</td>'
        f'<td>{ui.safe(item["san"])}</td><td>{ui.safe(previous.display_score(item["score"]))}</td>'
        f'<td>{item["depth"]}</td><td>{item["nodes_observed"]}</td></tr>'
        for index, item in enumerate(observations))
    lines = ''.join(
        f'<details><summary>{"Played" if index == 0 else "Alternative"} saved engine line '
        '(evaluator-side trace)</summary><code>'
        f'{ui.safe(" ".join(item["pv_uci"]))}</code></details>'
        for index, item in enumerate(observations))
    limitations = ''.join(f'<li>{ui.safe(value)}</li>' for value in record['limitations'])
    css = ui.CSS.read_text(encoding='utf-8')
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paired chess review · {ui.safe(title)}</title><style>{css}</style></head>
<body><main><section class="hero"><p class="eyebrow">Offline post-game study · v3 candidate</p>
<h1>{ui.safe(title)}</h1><p class="lead">Move {selection['ply']}:
<strong>{ui.safe(selection['played_san'])}</strong>. This page explains legal move facts
and the limits of one local engine comparison. It is not model commentary.</p></section>
<section class="case"><div class="boards">{''.join(figures)}</div>
<div class="panel"><p class="eyebrow">The move</p><h2>What happened on the board</h2>
<p>{ui.safe(_move_fact(board, played))}</p></div>
<div class="panel"><p class="eyebrow">Paired search</p><h2>How the two moves scored</h2>
<p>{ui.safe(_comparison_text(record))}</p><p>{ui.safe(_reply_text(board, observations[0]))}</p>
<p class="small">The alternative came from a separate unrestricted discovery search.
Both displayed scores came from one root-restricted MultiPV search with
{record['engine']['settings']['requested_nodes_per_search']:,} requested nodes total.
Bounded search can change with budget and settings.</p>
<div class="table-wrap"><table><thead><tr><th>Move</th><th>SAN</th><th>Score</th>
<th>Depth</th><th>Observed nodes</th></tr></thead><tbody>{rows}</tbody></table></div>{lines}</div>
<div class="notice"><strong>Limits</strong><ul>{limitations}</ul></div></section>
<footer><p>PGN SHA-256: <code>{record['source']['pgn_sha256']}</code></p>
<p>Stockfish binary SHA-256: <code>{previous.ENGINE_SHA256}</code></p></footer>
</main></body></html>'''
    return html.encode('utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
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
        print(json.dumps({'schema': SCHEMA, 'engine': previous.engine_ready(),
                          'status': 'ready'}, sort_keys=True))
        return 0
    game, raw, moves = previous.load_completed_game(args.pgn)
    if args.command == 'review':
        record = analyze(game, raw, moves, args.ply, args.nodes)
        page = render(record)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / 'review.json').write_bytes(previous.canonical(record) + b'\n')
        (args.output_dir / 'index.html').write_bytes(page)
    else:
        with (args.output_dir / 'review.json').open('rb') as stream:
            raw_record = stream.read(MAX_RECORD_BYTES + 1)
        if len(raw_record) > MAX_RECORD_BYTES:
            raise ValueError('review_record_too_large')
        record = json.loads(raw_record)
        validate_record(record, game, raw, moves)
        page = render(record)
        if (args.output_dir / 'index.html').read_bytes() != page:
            raise ValueError('rendered_page_differs_from_receipt')
    print(json.dumps({'schema': SCHEMA, 'status': 'verified',
                      'engine_calls': record['engine']['settings']['searches']
                      if args.command == 'review' else 0,
                      'model_calls': 0, 'page_sha256': previous.digest(page),
                      'output': str(args.output_dir / 'index.html')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
