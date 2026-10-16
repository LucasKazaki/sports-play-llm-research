"""No-forward NF4 measurements on an explicitly accepted, already frozen CPU pool.

No backend imports happen before all source, cohort and qualification checks.
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
import chess_queen_benchmark_v1 as cpu
from chess_fact_sft_common import read, save, sha
from chess_fact_sft_intake import board_key

ROOT = cpu.ROOT
SCHEMA = 'chess.queen-benchmark-nf4.v1'


def get_field(value, dotted):
    for part in dotted.split('.'):
        value = value[part]
    return value


def bound(item):
    return cpu.policy.bound_file(item)


def verify(protocol):
    plan = read(protocol)
    if plan['schema'] != SCHEMA or plan['implementation_sha256'] != sha(Path(__file__)):
        raise ValueError('Frozen NF4 benchmark source/protocol changed')
    for item in plan['dependencies']:
        bound(item)
    if {item['role'] for item in plan['qualifications']} != {'kernel', 'canonical', 'authored'}:
        raise ValueError('Kernel, canonical and authored qualification receipts are required')
    if plan['generation_allowed'] is not True:
        raise ValueError('Generation is not authorized by this frozen plan')
    required = {'scripts/chess_queen_nf4_adapter_v2.py', 'scripts/chess_queen_adapter.py',
                'scripts/chess_queen_benchmark_v1.py', 'scripts/chess_native_resources.py'}
    if not required.issubset({item['path'] for item in plan['dependencies']}):
        raise ValueError('Missing exact runtime dependency')
    intake = bound(plan['accepted_pool']['intake_protocol'])
    old = cpu.verify(intake)
    if old['generation_allowed'] is not False:
        raise ValueError('Accepted pool must have been acquired without model calls')
    for qualification in plan['qualifications']:
        value = read(bound(qualification['receipt']))
        if not qualification['required_fields']:
            raise ValueError('Qualification needs explicit required result fields')
        for dotted, expected in qualification['required_fields'].items():
            if get_field(value, dotted) != expected:
                raise ValueError('Qualification failed: ' + dotted)
    if plan['generation'] != {**plan['generation'], 'generation_mode': 'no_cache',
                             'precision_profile': 'math_sdpa_fp32_reduction', 'temperature': 0.0}:
        raise ValueError('Unqualified generation configuration')
    resources = plan['resources']
    if (resources['stop_commit_headroom_bytes'] < 4*1024**3
            or resources['stop_physical_available_bytes'] < 4*1024**3
            or resources['stop_gpu_free_bytes'] < 1024**3):
        raise ValueError('Resource reserves cannot be lowered')
    return plan


def accepted_pool(plan):
    pool = plan['accepted_pool']
    dataset_path, labels_path = bound(pool['dataset']), bound(pool['labels'])
    data, labels = read(dataset_path), read(labels_path)
    identity = pool['intake_protocol']['sha256']
    if (data['protocol_sha256'] != identity or labels['protocol_sha256'] != identity
            or labels['dataset_sha256'] != pool['dataset']['sha256']):
        raise ValueError('Accepted CPU cohort/teacher identity differs')
    for split, count in pool['available_counts'].items():
        inputs, teachers = data['splits'][split], labels['splits'][split]
        if len(inputs) != count or len(teachers) != count:
            raise ValueError('Accepted pool count differs')
        for source, teacher in zip(inputs, teachers):
            if any(teacher.get(key) != value for key, value in source.items()) or teacher['status'] != 'completed':
                raise ValueError('Teacher does not match original completed input')
    if set(data['splits']) != set(pool['available_counts']) or set(labels['splits']) != set(data['splits']):
        raise ValueError('Unexpected pool splits')
    return data, labels


def collision_check(plan, data):
    """Abort; never silently replace a frozen pool member after authored probing."""
    known = set()
    for item in plan['authored_boards']:
        value = read(bound(item))
        for fen in value['board_fens']:
            board = chess.Board(fen)
            if not board.is_valid():
                raise ValueError('Invalid authored collision exclusion')
            known.add(board_key(board.fen()))
    for rows in data['splits'].values():
        for row in rows:
            for key in ('fen', 'source_before_fen'):
                if board_key(row[key]) in known:
                    raise ValueError('Authored board collides with frozen CPU pool')
    return {'authored_board_keys': len(known), 'collisions': 0,
            'scope': 'Current/setup boards of the entire frozen CPU pool; no replacement'}


def selected_rows(plan, labels, split):
    if split not in ('development', 'holdout'):
        raise ValueError('Unknown panel')
    count = plan['panel_counts'][split]
    if type(count) is not int or count < 1 or count > len(labels['splits'][split]):
        raise ValueError('Invalid predeclared panel count')
    # A future plan can use fewer than all CPU teacher rows. The choice is only
    # source order, frozen before any decoder call; unused rows stay visible.
    return labels['splits'][split][:count]


def packet(row, mode):
    value = {'fen': row['fen']}
    if mode == 'selected':
        value['selected_uci'] = row['teacher_move_uci']
    elif mode != 'free':
        raise ValueError('Unknown mode')
    return value


def model_factory(plan, guard):
    import chess_queen_nf4_adapter_v2 as nf4
    return nf4.NativeQueenNF4(protocol=bound(plan['nf4_kernel_protocol']),
        diagnostic_receipt=bound(plan['nf4_kernel_receipt']), guard=guard)


def snapshot(protocol, plan, target):
    destination = target/'executed-sources'; destination.mkdir()
    bindings = [*plan['dependencies'], plan['accepted_pool']['intake_protocol'],
                plan['nf4_kernel_protocol'], plan['nf4_kernel_receipt'],
                *plan['authored_boards'], *[item['receipt'] for item in plan['qualifications']]]
    files = [Path(__file__), Path(protocol)] + [bound(x) for x in bindings]
    manifest = []
    for index, source in enumerate(files):
        name = f'{index:03d}-{source.name}'
        shutil.copyfile(source, destination/name)
        manifest.append({'original_path': str(source), 'snapshot': name, 'sha256': sha(destination/name)})
    save(destination/'manifest.json', manifest)


def ensure_development(protocol, plan, out):
    complete = out/'development'/'summary.json'
    if not complete.is_file():
        raise ValueError('Complete development before opening holdout')
    value = read(complete)
    expected = 2*plan['panel_counts']['development']
    if (value.get('execution_status') != 'complete_without_backend_failure'
            or value.get('protocol_sha256') != sha(protocol)
            or value.get('labels_sha256') != plan['accepted_pool']['labels']['sha256']
            or value.get('completed_request_count') != expected
            or value.get('planned_request_count') != expected):
        raise ValueError('Development failed or incomplete; holdout remains unopened')


def write_event(stream, value):
    stream.write(json.dumps(value, allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())


def run(protocol, out, split):
    plan = verify(protocol)
    data, labels = accepted_pool(plan)
    collisions = collision_check(plan, data)
    rows = selected_rows(plan, labels, split)
    if split == 'holdout':
        ensure_development(protocol, plan, out)
    planned = [(row, mode) for row in rows for mode in ('free', 'selected')]
    target = out/split; target.mkdir(parents=True)
    snapshot(protocol, plan, target)
    save(target/'planned.json', {'protocol_sha256': sha(protocol),
        'labels_sha256': plan['accepted_pool']['labels']['sha256'],
        'requests': [{'id': row['id'], 'mode': mode} for row, mode in planned],
        'unused_cpu_pool_rows': len(labels['splits'][split])-len(rows),
        'selection': 'First frozen source-order rows, before any decoder call', 'collision_check': collisions})
    from chess_native_resources import windows_sample, reasons, Policy
    policy = Policy(**plan['resources'])
    started, last, first, samples = time.monotonic(), -float('inf'), True, []
    phase_seconds = plan['phase_maximum_seconds'][split]
    def guard(force=False):
        nonlocal last, first
        now = time.monotonic()
        if (out/'CANCEL').exists():
            raise InterruptedError('Owned NF4 benchmark cancellation')
        if now-started >= phase_seconds:
            raise TimeoutError('Frozen benchmark phase budget exhausted')
        if not force and now-last < 1:
            return
        sample = windows_sample(); samples.append(asdict(sample)); last = now
        with (target/'resources.jsonl').open('a', encoding='utf-8') as stream:
            write_event(stream, asdict(sample))
        issues = reasons(sample, policy, 'start' if first else 'running'); first = False
        if issues:
            raise RuntimeError('Resource reserve: '+','.join(issues))
    failure = None
    outcomes = []
    try:
        guard()
        model = model_factory(plan, guard)
        with (target/'attempts.jsonl').open('x', encoding='utf-8', buffering=1) as journal:
            for index, (row, mode) in enumerate(planned):
                write_event(journal, {'utc': datetime.now(timezone.utc).isoformat(), 'index': index,
                    'id': row['id'], 'mode': mode, 'status': 'started'})
                response = model.generate(packet(row, mode), **plan['generation'])
                save(target/f'response-{index:04d}.json', response)
                result = cpu.score_response(row, mode, response); outcomes.append(result)
                write_event(journal, {'utc': datetime.now(timezone.utc).isoformat(), 'index': index, **result})
                save(target/'progress.json', {'done': index+1, 'planned': len(planned), 'last': result})
                if response['status'] not in ('completed', 'partial', 'terminal'):
                    failure = 'First backend/resource failure: '+response.get('error', response['status'])
                    break
    except Exception as error:
        failure = type(error).__name__+': '+str(error)
    finally:
        outcomes = cpu.finalize_attempt(target, planned)
        save(target/'resources.json', samples)
        completed = sum(row['status'] in ('completed', 'partial', 'terminal') for row in outcomes)
        summary = {'schema': SCHEMA, 'split': split,
            'execution_status': 'complete_without_backend_failure' if not failure and completed == len(planned) else 'failed_or_incomplete',
            'protocol_sha256': sha(protocol), 'labels_sha256': plan['accepted_pool']['labels']['sha256'],
            'planned_request_count': len(planned), 'completed_request_count': completed,
            'metrics': cpu.summarize(outcomes), 'error': failure, 'elapsed_seconds': time.monotonic()-started,
            'limitations': plan['limitations']}
        save(target/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('split', choices=('development', 'holdout'))
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.protocol, args.out, args.split)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['execution_status'] == 'complete_without_backend_failure' else 2)


if __name__ == '__main__':
    main()
