"""Fresh, game-disjoint Queen measurements; engine references never enter generation.

Run intake and labels on CPU. The root coordinator alone runs development or
holdout with exclusive GPU ownership. Retained attempts are never replayed.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time

import chess
from chess_fact_sft_common import read, save, sha
from chess_fact_sft_intake import parquet_rows, board_key
import chess_move_policy_v5 as policy

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess.queen-benchmark.v1'


def verify(protocol):
    plan = read(protocol)
    if plan['schema'] != SCHEMA or plan['implementation_sha256'] != sha(Path(__file__)):
        raise ValueError('Frozen benchmark implementation changed')
    for item in plan['dependencies']:
        policy.bound_file(item)
    if plan.get('generation_allowed') is not False and not any(
            item['path']=='scripts/chess_queen_adapter.py' for item in plan['dependencies']):
        raise ValueError('Generation must bind the exact Queen adapter')
    return plan


def all_exclusions(plan):
    prior = read(policy.bound_file(plan['prior_protocol']))
    games, boards = policy.exclusions(prior)
    latest = read(policy.bound_file(plan['v6_dataset']))
    for rows in latest['new_splits'].values():
        for row in rows:
            policy.add_roles(row, games, boards)
    for binding in plan['authored_packets']:
        value = read(policy.bound_file(binding))
        board=chess.Board(value['fen'])
        if not board.is_valid():raise ValueError('Invalid authored exclusion FEN')
        boards.add(board_key(board.fen()))
    for binding in plan.get('authored_responses', []):
        value = read(policy.bound_file(binding))
        boards.add(board_key(value['input']['fen']))
        for step in value.get('parsed', {}).get('critical_line', {}).get('steps', []):
            if step.get('legal') and 'fen_after' in step:
                boards.add(board_key(step['fen_after']))
    return games, boards


def snapshot(protocol, out, name):
    target = out/name
    target.mkdir()
    paths = [Path(__file__), Path(protocol)] + [ROOT/item['path'] for item in read(protocol)['dependencies']]
    manifest = {}
    for source in paths:
        if source.name in manifest:
            raise ValueError('Ambiguous snapshot filename')
        shutil.copyfile(source, target/source.name)
        manifest[source.name] = sha(target/source.name)
    save(target/'manifest.json', manifest)


def intake(protocol, out):
    plan = verify(protocol)
    source = policy.bound_file(plan['source'])
    games, boards = all_exclusions(plan)
    if out.exists():
        raise ValueError('Intake is create-only')
    out.mkdir(parents=True)
    snapshot(protocol, out, 'intake-sources')
    splits, selection = policy.select_rows(parquet_rows(source), plan['counts'], plan['seed'],
                                           games, boards, plan['source_row_cap'])
    for rows in splits.values():
        for row in rows:
            row['id'] = row['id'].replace('policy-v5-', 'queen-v1-', 1)
    save(out/'dataset.json', {'schema': SCHEMA, 'protocol_sha256': sha(protocol),
        'source_sha256': sha(source), 'excluded_games': len(games), 'excluded_boards': len(boards),
        'selection': selection, 'splits': splits})
    return {'counts': {s: len(rows) for s, rows in splits.items()}, 'model_calls': 0, 'engine_calls': 0}


def label(protocol, out):
    plan = verify(protocol)
    data = read(out/'dataset.json')
    if data['protocol_sha256'] != sha(protocol):
        raise ValueError('Dataset protocol differs')
    with (out/'teacher-attempt.json').open('x', encoding='utf-8') as stream:
        json.dump({'utc': datetime.now(timezone.utc).isoformat(), 'dataset_sha256': sha(out/'dataset.json')}, stream)
    snapshot(protocol, out, 'teacher-sources')
    tasks = [(split, row) for split, rows in data['splits'].items() for row in rows]
    journal = out/'teachers.jsonl'
    try:
        results = policy.teacher_chunk(str(policy.bound_file(plan['teacher']['binary'])), plan['teacher'],
                                       tasks, str(journal), str(out/'CANCEL'))
    except Exception as error:
        results = policy.recovered_chunk(tasks, journal, error)
    labels = {s: [] for s in data['splits']}
    for split, row in results:
        labels[split].append(row)
    value = {'schema': SCHEMA, 'dataset_sha256': sha(out/'dataset.json'),
        'protocol_sha256': sha(protocol), 'splits': labels,
        'requested': len(tasks), 'statuses': dict(Counter(r['status'] for _, r in results))}
    save(out/'labels.json', value)
    return {'requested': len(tasks), 'statuses': value['statuses']}


def request_packet(row, mode):
    import chess_queen_adapter as queen
    # Never pass the row itself: it also contains evaluator-only engine fields.
    value = {'fen': row['fen']}
    if mode == 'selected':
        if row['status'] != 'completed':
            return None
        value['selected_uci'] = row['teacher_move_uci']
    elif mode != 'free':
        raise ValueError('Unknown request mode')
    return queen.input_packet(value)[0]


def score_response(row, mode, response):
    parsed = response.get('parsed', {})
    legal = bool(parsed.get('raw_choice_is_legal', False))
    accepted = parsed.get('accepted_move_uci')
    best = parsed.get('raw_choice_uci')
    reference = []
    teacher_board = chess.Board(row['fen'])
    for uci in row.get('reference_pv', []):
        if teacher_board.is_game_over(claim_draw=False):
            break
        try:
            move = chess.Move.from_uci(uci)
            if move not in teacher_board.legal_moves:
                break
        except ValueError:
            break
        reference.append(uci)
        teacher_board.push(move)
    line = parsed.get('critical_line', {})
    steps = line.get('steps', [])
    prefix = []
    for step in steps:
        if not step['legal']:
            break
        prefix.append(step['raw_uci'])
    return {'id': row['id'], 'mode': mode, 'status': response['status'],
        'finish_reason': response.get('finish_reason'), 'raw_best_legal': legal,
        'best_description_valid': bool(parsed.get('description_valid', False)),
        'free_best_teacher_match': mode == 'free' and row['status'] == 'completed' and best == row['teacher_move_uci'],
        'selected_move_followed': mode == 'selected' and accepted == row.get('teacher_move_uci') and accepted is not None,
        'critical_line_legal_through': {str(n): len(prefix) >= n for n in (1, 2, 3)},
        'critical_line_exact_prefix': {str(n): len(reference) >= n and len(prefix) >= n and prefix[:n] == reference[:n]
                                       for n in (1, 2, 3)},
        'teacher_support_plies': len(reference), 'line_starts_with_raw_best': bool(prefix) and prefix[0] == best,
        'elapsed_seconds': response.get('elapsed_seconds'),
        'explanation_quality': 'unrated; legality and engine agreement do not establish prose factuality or teaching value'}


def summarize(rows):
    value = {}
    for mode in ('free', 'selected'):
        group = [row for row in rows if row['mode'] == mode]
        value[mode] = {'planned': len(group), 'statuses': dict(Counter(row['status'] for row in group))}
        for field in ('raw_best_legal', 'best_description_valid', 'free_best_teacher_match', 'selected_move_followed',
                      'line_starts_with_raw_best'):
            value[mode][field] = sum(row[field] for row in group)
        for field in ('critical_line_legal_through', 'critical_line_exact_prefix'):
            value[mode][field] = {str(n): sum(row[field][str(n)] for row in group) for n in (1, 2, 3)}
        value[mode]['teacher_support'] = {str(n): sum(row['teacher_support_plies'] >= n for row in group) for n in (1, 2, 3)}
    return value


def finalize_attempt(target, planned):
    """Complete the denominator from saved responses without rerunning a call."""
    started = set()
    journal = target/'attempts.jsonl'
    if journal.exists():
        for line in journal.read_text(encoding='utf-8').splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if value.get('status') == 'started':
                started.add(value['index'])
    results = []
    for index, (row, mode) in enumerate(planned):
        path = target/f'response-{index:04d}.json'
        response = read(path) if path.exists() else {'status': 'unknown_after_interruption' if index in started else 'not_run'}
        results.append(score_response(row, mode, response))
    save(target/'outcome-ledger.json', results)
    return results


def run(protocol, out, split):
    plan = verify(protocol)
    if plan.get('generation_allowed') is False:
        raise ValueError('This frozen protocol permits CPU intake/teachers only; no model calls')
    import chess_queen_adapter as queen
    data, labels = read(out/'dataset.json'), read(out/'labels.json')
    if (data['protocol_sha256'] != sha(protocol) or labels['protocol_sha256'] != sha(protocol)
            or labels['dataset_sha256'] != sha(out/'dataset.json')):
        raise ValueError('Dataset/label identity differs')
    if split not in ('development', 'holdout'):
        raise ValueError('Unknown panel')
    if split == 'holdout':
        complete = out/'development'/'summary.json'
        if not complete.is_file():
            raise ValueError('Complete development before opening holdout')
        receipt = read(complete)
        if (receipt.get('execution_status') != 'complete_without_backend_failure'
                or receipt.get('protocol_sha256') != sha(protocol)
                or receipt.get('labels_sha256') != sha(out/'labels.json')):
            raise ValueError('Development did not complete successfully; holdout remains unopened')
    target = out/split
    target.mkdir()  # Create-only, including attempts that failed before loading.
    snapshot(protocol, target, 'executed-sources')
    rows = labels['splits'][split]
    planned = [(row, mode) for row in rows for mode in ('free', 'selected')]
    save(target/'planned.json', {'protocol_sha256': sha(protocol), 'labels_sha256': sha(out/'labels.json'),
        'requests': [{'id': row['id'], 'mode': mode} for row, mode in planned]})
    from chess_native_resources import windows_sample, reasons, Policy, GIB
    policy_guard = Policy(start_physical_available_bytes=6*GIB, start_commit_headroom_bytes=10*GIB,
        start_gpu_free_bytes=10*GIB, stop_physical_available_bytes=4*GIB, stop_commit_headroom_bytes=5*GIB)
    samples, first, last = [], True, -float('inf')
    def guard():
        nonlocal first, last
        now = time.monotonic()
        if (out/'CANCEL').exists():
            raise InterruptedError('Owned benchmark cancelled')
        if now-last < 1:
            return
        sample = windows_sample(); samples.append(asdict(sample)); last = now
        with (target/'resources.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(asdict(sample))+'\n')
        issues = reasons(sample, policy_guard, 'start' if first else 'running'); first = False
        if issues:
            raise RuntimeError('resource reserve: '+','.join(issues))
    model = queen.NativeQueen(device='cuda', guard=guard)
    outcomes, failed = [], False
    try:
        with (target/'attempts.jsonl').open('x', encoding='utf-8', buffering=1) as journal:
            for index, (row, mode) in enumerate(planned):
                packet = request_packet(row, mode)
                response = {'status': 'not_run', 'error': 'not_run_after_backend_failure' if failed else 'teacher_unavailable'}
                if packet is not None and not failed:
                    journal.write(json.dumps({'index': index, 'id': row['id'], 'mode': mode, 'status': 'started'})+'\n')
                    journal.flush(); os.fsync(journal.fileno())
                    response = model.generate(packet, **plan['generation'])
                    if response['status'] == 'failed':
                        failed = True
                save(target/f'response-{index:04d}.json', response)
                result = score_response(row, mode, response); outcomes.append(result)
                journal.write(json.dumps({'index': index, **result})+'\n'); journal.flush(); os.fsync(journal.fileno())
                save(target/'progress.json', {'done': index+1, 'planned': len(planned), 'last': result})
                print(json.dumps({'phase': split, 'done': index+1, 'planned': len(planned), 'status': response['status']}), flush=True)
    finally:
        finalize_attempt(target, planned)
    save(target/'outcomes.json', outcomes)
    save(target/'resources.json', samples)
    complete = not failed and all(row['status'] in ('completed', 'partial') for row in outcomes)
    summary = {'schema': SCHEMA, 'split': split,
        'execution_status': 'complete_without_backend_failure' if complete else 'failed_or_incomplete',
        'protocol_sha256': sha(protocol), 'labels_sha256': sha(out/'labels.json'),
        'metrics': summarize(outcomes), 'limitations': plan['limitations']}
    save(target/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('intake', 'label', 'development', 'holdout'))
    parser.add_argument('--protocol', type=Path, default=ROOT/'experiments/chess-queen-benchmark-v1/protocol.json')
    parser.add_argument('--out', type=Path, default=ROOT/'data/private/chess-queen-benchmark-v1')
    args = parser.parse_args()
    result = intake(args.protocol,args.out) if args.phase == 'intake' else label(args.protocol,args.out) if args.phase == 'label' else run(args.protocol,args.out,args.phase)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
