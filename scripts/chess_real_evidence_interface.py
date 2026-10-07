#!/usr/bin/env python3
"""Build an offline, source-bound review of retained real chess development evidence.

This page makes no model or engine calls. Board-fact templates, saved engine
observations, raw engine lines, and model-validation results stay distinct.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from urllib.parse import urlparse

import chess
import chess.svg

import chess_counterfactual_evidence as counterfactual
import chess_no_forward_generation_runner as generation
import chess_no_forward_output_validator as output_validator
import chess_typed_position_evidence as typed_evidence


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
SOURCE_SHA256 = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'
TYPED = ROOT / 'artifacts/chess-typed-position-evidence-v1/dev8-adapter-v1.json'
RUN = ROOT / 'artifacts/chess-no-forward-generation-v1/dev8-20260923T105300Z'
REPORT = ROOT / 'artifacts/chess-no-forward-output-validation-v1/dev8-20260923T124549Z/report.json'
CSS = ROOT / 'prototype/chess_evidence_review.css'
DEFAULT_OUTPUT = ROOT / 'artifacts/chess-evidence-review-v1/index.html'


def safe(value: object) -> str:
    return escape(str(value), quote=True)


def source_url(row: dict) -> str:
    url = str(row['source_url'])
    parsed = urlparse(url)
    allowed_paths = {'/' + row['game_id'], '/' + row['game_id'] + '/white',
                     '/' + row['game_id'] + '/black'}
    if (parsed.scheme != 'https' or parsed.netloc != 'lichess.org'
            or parsed.path not in allowed_paths or parsed.query
            or not parsed.fragment.isdigit()):
        raise ValueError('unexpected_source_game_url')
    return url


def score_label(score: dict) -> str:
    if (score.get('type') not in ('cp', 'mate') or
            score.get('bound') not in ('exact', 'lower', 'upper') or
            score.get('side_to_move') not in ('white', 'black') or
            score.get('perspective') != 'side_to_move' or
            type(score.get('value')) is not int):
        raise ValueError('unsupported_engine_score')
    unit = 'centipawns' if score['type'] == 'cp' else 'mate moves'
    qualifier = {'exact': 'unqualified score event', 'lower': 'lower bound',
                 'upper': 'upper bound'}[score['bound']]
    return f"{score['value']:+d} {unit} for {score['side_to_move'].title()} · {qualifier}"


def replay_candidate(board: chess.Board, candidate: dict) -> tuple[chess.Move, str, chess.Board]:
    move = chess.Move.from_uci(candidate['move_uci'])
    if move not in board.legal_moves:
        raise ValueError('candidate_move_not_legal')
    san = board.san(move)
    after = board.copy(stack=False)
    after.push(move)
    transition = candidate['transition']
    if (transition['fen_before'] != board.fen()
            or transition['fen_after'] != after.fen()
            or transition['san'] != san
            or transition['from'] != chess.square_name(move.from_square)
            or transition['to'] != chess.square_name(move.to_square)):
        raise ValueError('candidate_transition_not_replayed')
    return move, san, after


def model_status(outcome: dict | None) -> str:
    if outcome is None:
        return 'No saved model result is bound to this position.'
    if outcome['decision'] == 'admissible_typed_assertions':
        return 'Typed assertions passed structural validation; explanation quality is unreviewed.'
    if outcome['reason'] == 'untyped_response_content':
        return 'A local model replied in prose. No assertion was admitted by the typed validator.'
    if outcome['capture_status'] == 'transport_failure':
        return 'The local model call timed out. No response was available to validate.'
    if outcome['decision'] == 'admissible_abstention':
        return 'The local model abstained.'
    return 'No model assertion passed validation (' + str(outcome['reason']) + ').'


def render_case(row: dict, outcome: dict | None, ordinal: int) -> str:
    """Render one position, including a visible safe state for failed evidence."""
    game_link = (f'<a href="{safe(source_url(row))}" target="_blank" '
                 f'rel="noopener noreferrer">Open source game ↗</a>')
    heading = (f'<header class="case-head"><div><p class="eyebrow">Case {ordinal + 1:02d} · '
               f'{safe(row["position_id"])}</p><h2>Real game position</h2></div>{game_link}</header>')
    if row['status'] != 'succeeded':
        error = row.get('error', {}).get('message', 'The retained analysis failed.')
        return (f'<section class="case" id="case-{ordinal}">{heading}'
                f'<div class="notice failure"><strong>Evidence unavailable</strong>'
                f'<p>{safe(error)}</p><p>No move or engine claim is displayed for this position.</p>'
                f'</div></section>')
    board = chess.Board(row['fen'])
    if not board.is_valid() or not row['engine_evidence']:
        raise ValueError('invalid_successful_position')
    candidates = sorted(row['engine_evidence'], key=lambda candidate: candidate['rank'])
    if candidates[0]['rank'] != 1 or len({c['rank'] for c in candidates}) != len(candidates):
        raise ValueError('missing_or_duplicate_engine_rank')
    selected = candidates[0]
    move, san, after = replay_candidate(board, selected)
    side = 'White' if board.turn == chess.WHITE else 'Black'
    before_svg = chess.svg.board(board, orientation=board.turn, coordinates=True, size=420)
    after_svg = chess.svg.board(after, orientation=board.turn, coordinates=True,
                                lastmove=move, size=420)
    transition = selected['transition']
    move_fact = (f"{side} moved the {transition['moving_piece']} from "
                 f"{transition['from']} to {transition['to']} ({san}).")
    capture_fact = (f"This move captures {transition['captured_piece']}."
                    if transition['capture'] else 'This move does not capture a piece.')
    check_fact = 'This move gives check.' if transition['gives_check'] else 'This move does not give check.'
    evidence_anchor = f'evidence-{ordinal}-1'
    claims = ''.join(
        f'<li><span class="tag">Rule verified</span><span>{safe(claim)}</span>'
        f'<a href="#{evidence_anchor}">Board replay ↗</a></li>'
        for claim in (move_fact, capture_fact, check_fact))
    alternatives = []
    for candidate in candidates:
        _, candidate_san, _ = replay_candidate(board, candidate)
        alternatives.append(
            f'<tr id="evidence-{ordinal}-{candidate["rank"]}">'
            f'<td>{candidate["rank"]}</td><td><strong>{safe(candidate_san)}</strong>'
            f'<span class="muted">{safe(candidate["move_uci"])}</span></td>'
            f'<td>{safe(score_label(candidate["score"]))}</td>'
            f'<td>{safe(candidate["depth"])}</td>'
            f'<td>{safe(candidate["nodes_observed"])}</td></tr>')
    return f'''<section class="case" id="case-{ordinal}">
{heading}
<div class="case-meta"><span>{side} to move</span><span>{side} at bottom</span>
<span>Development sample</span></div>
<div class="boards"><figure><figcaption>Before move</figcaption>{before_svg}</figure>
<figure><figcaption>After {safe(san)} · {safe(selected['move_uci'])}</figcaption>{after_svg}</figure></div>
<div class="columns"><div class="panel"><p class="eyebrow">Selected move</p>
<h3>{safe(san)} <span class="muted">{safe(selected['move_uci'])}</span></h3>
<p>{safe(move_fact)}</p><p>{safe(capture_fact)} {safe(check_fact)}</p>
<p class="small">Deterministic wording from legal board replay.</p></div>
<div class="panel"><p class="eyebrow">Model explanation</p><h3>No validated explanation</h3>
<p>{safe(model_status(outcome))}</p><p class="small">Saved development attempt only.
No heldout quality judgment.</p></div></div>
<div class="panel"><p class="eyebrow">Checkable claims</p><h3>What the board proves</h3>
<ul class="claims">{claims}</ul><p class="small">These are rule facts, not a strategic reason
to play the move.</p></div>
<div class="panel"><p class="eyebrow">Retained engine observations</p><h3>Searched moves</h3>
<p class="small">Stockfish observations are estimates from bounded search. Bound labels
are retained. Rank is saved engine order, not a proof of best play.</p>
<div class="table-wrap"><table><thead><tr><th>Rank</th><th>Move</th><th>Score and perspective</th>
<th>Depth</th><th>Nodes</th></tr></thead><tbody>{''.join(alternatives)}</tbody></table></div>
<details><summary>Show raw engine line for the selected move</summary>
<p class="small">Evaluator-only principal variation. It was excluded from model input
and has not been turned into a commentary claim.</p>
<code>{safe(' '.join(selected['pv_uci']))}</code></details></div>
<div class="notice"><strong>Strategic explanation withheld</strong><p>A legal move and an engine
score do not establish its strategic purpose or teaching value. This case awaits a validated
typed model claim and independent chess review.</p></div></section>'''


def render_page(typed: dict, projection: dict, report: dict, manifest: dict) -> bytes:
    rows = typed['positions']
    if (typed['requested_positions'] != len(rows)
            or typed['successful_positions'] + typed['failed_positions'] != len(rows)
            or projection['selected_split'] != 'dev'
            or len(projection['items']) != len(rows)
            or report['requested'] != len(rows) or report['accounted'] != len(rows)
            or report['commentary_capability_gate_passed']
            or report['commentary_quality_evaluated']):
        raise ValueError('interface_denominator_or_gate_mismatch')
    outcomes = {}
    for request, outcome in zip(manifest['requests'], report['outcomes']):
        if request['position_id'] in outcomes or request['ordinal'] != outcome['ordinal']:
            raise ValueError('model_result_position_binding_mismatch')
        outcomes[request['position_id']] = outcome
    if set(outcomes) != {row['position_id'] for row in rows}:
        raise ValueError('model_result_position_set_mismatch')
    for row, item in zip(rows, projection['items']):
        if (row['position_id'] != item['position_id']
                or row['game_id'] != item['game_id']
                or row['fen'] != item['fen']
                or row['split'] != 'dev'
                or row['source_url'] != item['game_url']):
            raise ValueError('source_projection_position_binding_mismatch')
    cases = ''.join(render_case(row, outcomes[row['position_id']], index)
                    for index, row in enumerate(rows))
    nav = ''.join(f'<a href="#case-{index}">Case {index + 1:02d}'
                  f'<small>{safe(row["position_id"])}</small></a>'
                  for index, row in enumerate(rows))
    envelopes = Counter(outcome['response_envelope'] for outcome in report['outcomes'])
    admitted = report['decision_counts'].get('admissible_typed_assertions', 0)
    css = CSS.read_text(encoding='utf-8')
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chess evidence review · local development sample</title><style>{css}</style></head>
<body><div class="layout"><aside><div class="brand"><span class="brand-mark">♞</span>
Chess evidence</div><p class="side-label">Cases</p><nav aria-label="Position navigation">
{nav}</nav></aside><main><section class="hero">
<p class="eyebrow">Offline local review · development evidence</p>
<h1>See the move.<br>Check the evidence.</h1>
<p class="lead">Eight positions from real public games. Each board move is legally replayed;
the engine observations and source game remain visible. Strategic explanations are withheld
when the saved model output cannot be validated.</p>
<div class="stats"><div class="stat"><strong>{len(rows)}</strong><span>Real development positions</span></div>
<div class="stat"><strong>{typed['legal_candidates']}</strong><span>Legally replayed searched moves</span></div>
<div class="stat"><strong>{admitted}</strong><span>Admitted model explanations</span></div>
<div class="stat"><strong>{report['heldout_outcomes_scored']}</strong><span>Fresh heldout outcomes scored</span></div></div>
<p class="small">Saved model run: {report['captured_model_calls']} calls,
{envelopes.get('openai_chat_completion', 0)} raw replies,
{envelopes.get('none', 0)} without a captured reply.
No new model or engine call is made by this page.</p></section>
{cases}
<footer><p>Source: Lichess CC0 game-derived puzzle development sample.
Local analysis: Stockfish 19, 100,000 requested nodes per position, two saved candidate moves.
The displayed score is an engine observation, not a proof or human teaching judgment.</p>
<p>Limit: the sample is small and selected; no fresh game-disjoint heldout commentary test
or qualified chess review has passed. This is a local study tool, not a professional commentator.</p>
<p>Retained source receipt SHA-256: <code>{SOURCE_SHA256}</code></p></footer>
</main></div></body></html>'''
    return html.encode('utf-8')


def build() -> bytes:
    typed = json.loads(TYPED.read_bytes())
    typed_evidence.validate_typed_position_evidence(DATA, SOURCE, SOURCE_SHA256, typed)
    projection, _ = counterfactual.load_development(DATA)
    report = output_validator.verify_report(DATA, SOURCE, SOURCE_SHA256, TYPED, RUN, REPORT)
    manifest_path = RUN / 'manifest.json'
    if report['generation_manifest_sha256'] != counterfactual.file_digest(manifest_path):
        raise ValueError('generation_manifest_hash_mismatch')
    return render_page(typed, projection, report, generation._read_json(manifest_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=('build', 'verify'), default='build')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    expected = build()
    if args.command == 'build':
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(expected)
    elif args.output.read_bytes() != expected:
        raise ValueError('interface_output_differs_from_retained_evidence')
    print(json.dumps({'schema': 'chess-evidence-review/v1', 'status': 'verified',
                      'positions': 8, 'model_calls': 0, 'engine_calls': 0,
                      'sha256': sha256(expected).hexdigest(),
                      'output': str(args.output)}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
