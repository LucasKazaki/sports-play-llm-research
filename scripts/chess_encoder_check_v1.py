"""Frozen current-board LC0 features and a learned selected-move check head.

Intake is CPU only. All pretrained extraction and actual head learning belong
to the root GPU coordinator. No Queen decoder or engine is used by this model.
"""
from __future__ import annotations
import argparse
from collections import Counter, OrderedDict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

import chess
import chess_board_fact_core as facts
import chess_check_balanced_v2 as balanced
from chess_queen_materialize import materialize_pinned_module
from chess_fact_sft_common import read, save, sha
from chess_fact_sft_intake import board_key, canonical_game_id, parquet_rows

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess.encoder-check.v1'
PROMOTIONS = {None: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4}


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def bound(item):
    path = ROOT / item['path']
    if sha(path) != item['sha256']:
        raise ValueError('Pinned file changed: ' + item['path'])
    return path


def verify(protocol):
    plan = read(protocol)
    if plan['schema'] != SCHEMA or plan['implementation_sha256'] != sha(Path(__file__)):
        raise ValueError('Protocol or implementation identity changed')
    for item in plan['dependencies']:
        bound(item)
    # A missing Queen benchmark is a hard precondition, never an empty exclusion.
    bound(plan['queen_benchmark'])
    return plan


def snapshot(protocol, target):
    target.mkdir()
    paths = [Path(__file__), Path(protocol)] + [ROOT / x['path'] for x in read(protocol)['dependencies']]
    manifest = {}
    for index, source in enumerate(paths):
        name = f'{index:02d}-' + source.name
        shutil.copyfile(source, target / name)
        manifest[name] = {'source': str(source), 'sha256': sha(target / name)}
    save(target / 'manifest.json', manifest)


def packet(value):
    """The complete inference boundary: current FEN and one selected legal UCI."""
    if type(value) is not dict or set(value) != {'fen', 'selected_uci'}:
        raise ValueError('Exactly current FEN and selected UCI are permitted')
    fen, uci = value['fen'], value['selected_uci']
    if type(fen) is not str or len(fen) > 256 or len(fen.split()) != 6 or type(uci) is not str:
        raise ValueError('Complete FEN and ordinary UCI required')
    board, move = facts.board_and_move(fen, uci)
    if board.is_game_over(claim_draw=False):
        raise ValueError('Current board is terminal')
    return {'fen': board.fen(), 'selected_uci': move.uci()}


def move_indices(value):
    value = packet(value)
    board, move = chess.Board(value['fen']), chess.Move.from_uci(value['selected_uci'])
    flip = 0 if board.turn else 56
    return move.from_square ^ flip, move.to_square ^ flip, PROMOTIONS[move.promotion]


def requests(rows):
    """Deduplicate exact canonical current FENs without changing request order."""
    groups, seen = OrderedDict(), set()
    for row in rows:
        if type(row) is not dict or set(row) != {'case_id', 'fen', 'selected_uci'}:
            raise ValueError('Input rows must contain only ID, current FEN and move')
        if row['case_id'] in seen:
            raise ValueError('Duplicate request ID')
        seen.add(row['case_id'])
        value = packet({'fen': row['fen'], 'selected_uci': row['selected_uci']})
        groups.setdefault(value['fen'], []).append({'case_id': row['case_id'], 'input': value,
                                                   'input_sha256': json_hash(value)})
    return list(groups.items())


def add_exclusions(row, games, boards):
    games.add(canonical_game_id(row['game_id']))
    boards.update(row.get('successor_keys', []))
    for field in ('source_before_fen', 'fen'):
        if field in row:
            boards.add(board_key(row[field]))
    for uci in row.get('selected_pair', [row['selected_uci']] if 'selected_uci' in row else []):
        board, move = facts.board_and_move(row['fen'], uci)
        board.push(move)
        boards.add(board_key(board.fen()))


def exclusions(plan):
    registry = read(bound(plan['known_registry']))
    games, boards = set(registry['games']), set(registry['board_keys'])
    for binding in [*plan['excluded_cohorts'], plan['queen_benchmark']]:
        data = read(bound(binding))
        rows = data.get('rows', data.get('pairs', []))
        if not rows:
            groups = data.get('new_splits', data.get('groups', data.get('splits', {})))
            rows = [row for values in groups.values() for row in values]
        if not rows:
            raise ValueError('Empty exclusion cohort: ' + binding['path'])
        for row in rows:
            add_exclusions(row, games, boards)
    return games, boards


def select_holdout(source_rows, games, boards, pairs, seed, cap):
    games, boards = set(games), set(boards)
    inputs, labels, metadata, rejected = [], [], [], Counter()
    seen = set()
    for location, row in source_rows:
        ordinal = location['source_ordinal']
        if ordinal >= cap:
            break
        try:
            game = canonical_game_id(row['GameId'])
            if game in games:
                rejected['excluded_game'] += 1
                continue
            board = chess.Board(row['FEN'])
            if not board.is_valid() or board.chess960:
                raise ValueError('Invalid orthodox source board')
            before = board.fen()
            if board_key(before) in boards or board.is_game_over(claim_draw=False):
                rejected['excluded_before_or_terminal'] += 1
                continue
            # Only the first source setup token is consumed; never answer tails/themes.
            setup = chess.Move.from_uci(row['Moves'].split(maxsplit=1)[0])
            if setup not in board.legal_moves:
                raise ValueError('Illegal source setup')
            board.push(setup)
            if not board.is_valid() or board.is_game_over(claim_draw=False) or board_key(board.fen()) in boards:
                rejected['excluded_current_or_terminal'] += 1
                continue
            selected = balanced.pair_for(board, game, seed, boards)
            if selected is None:
                rejected['no_matched_pair'] += 1
                continue
            puzzle = row['PuzzleId']
            if type(puzzle) is not str or not puzzle.isalnum() or puzzle in seen:
                raise ValueError('Invalid/duplicate puzzle ID')
            ordered = sorted(selected, key=lambda u: hashlib.sha256(f'{game}:{u}'.encode()).hexdigest())
            pair_inputs, pair_labels = [], []
            for uci in ordered:
                truth = facts.expected_facts(board.fen(), uci)
                if truth != facts.independent_facts(board.fen(), uci):
                    raise RuntimeError('Independent immediate-fact routes disagree')
                case_id = f'encoder-check-v1-{puzzle}-{uci}'
                pair_inputs.append({'case_id': case_id, **packet({'fen': board.fen(), 'selected_uci': uci})})
                pair_labels.append({'case_id': case_id, 'gives_check': truth['gives_check']})
            if sum(label['gives_check'] for label in pair_labels) != 1:
                raise RuntimeError('Pair is not balanced')
        except (ValueError, KeyError, TypeError, IndexError):
            rejected['invalid'] += 1
            continue
        record = {'game_id': game, 'puzzle_id': puzzle, 'source_before_fen': before,
                  'setup_uci': setup.uci(), 'fen': board.fen(), 'selected_pair': ordered, **location}
        add_exclusions(record, games, boards)
        inputs.extend(pair_inputs); labels.extend(pair_labels); metadata.append(record); seen.add(puzzle)
        if len(metadata) == pairs:
            break
    if len(metadata) != pairs:
        raise ValueError('Frozen source cap cannot fill the holdout')
    return inputs, labels, metadata, dict(rejected)


def intake(protocol, out):
    plan = verify(protocol)
    # This binding must exist before intake; no placeholder or adaptive benchmark exclusion.
    source = bound(plan['source'])
    games, boards = exclusions(plan)
    if out.exists():
        raise ValueError('Intake is create-only')
    out.mkdir(parents=True)
    snapshot(protocol, out / 'intake-sources')
    save(out / 'initial-exclusions.json', {'games': sorted(games), 'board_keys': sorted(boards)})
    inputs, labels, metadata = {}, {}, {}
    prior = read(bound(plan['reused_dataset']))
    for split in ('train', 'dev'):
        inputs[split] = read(bound(plan['reuse'][split + '_inputs']))['rows']
        labels[split] = read(bound(plan['reuse'][split + '_labels']))['rows']
        metadata[split] = prior['groups'][split]
        if len(inputs[split]) != 2 * plan['reused_pairs'][split] or len(labels[split]) != len(inputs[split]):
            raise ValueError('Exact reused count differs')
        validate_labels(inputs[split], labels[split])
    inputs['holdout'], labels['holdout'], metadata['holdout'], rejected = select_holdout(
        parquet_rows(source), games, boards, plan['holdout_pairs'], plan['seed'], plan['source_row_cap'])
    for split in inputs:
        save(out / (split + '-inputs.json'), {'rows': inputs[split]})
        save(out / (split + '-labels.json'), {'rows': labels[split]})
    save(out / 'dataset.json', {'schema': SCHEMA, 'protocol_sha256': sha(protocol), 'groups': metadata,
        'excluded_games': len(games), 'excluded_board_keys': len(boards), 'rejections': rejected})
    files = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    result = {'protocol_sha256': sha(protocol), 'files_sha256': files,
              'counts': {s: len(v) for s, v in inputs.items()}, 'model_calls': 0, 'engine_calls': 0}
    save(out / 'frozen.json', result)
    return result


def validate_labels(rows, labels):
    if [r['case_id'] for r in rows] != [r['case_id'] for r in labels]:
        raise ValueError('Input/label order differs')
    if len({r['case_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate case ID')
    groups = OrderedDict()
    for row, label in zip(rows, labels):
        if type(label.get('gives_check')) is not bool:
            raise ValueError('Boolean ground truth required')
        groups.setdefault(row['fen'], []).append(label['gives_check'])
    if any(len(items) != 2 or sum(items) != 1 for items in groups.values()):
        raise ValueError('Each board must have exactly one checking and one nonchecking move')


def panel(out, split, include_labels=False):
    frozen = read(out / 'frozen.json')
    paths = [out / (split + '-inputs.json')]
    if include_labels:
        paths.append(out / (split + '-labels.json'))
    for path in paths:
        if sha(path) != frozen['files_sha256'][path.name]:
            raise ValueError('Frozen panel changed')
    rows = read(paths[0])['rows']
    requests(rows)
    labels = read(paths[1])['rows'] if include_labels else None
    if labels is not None:
        validate_labels(rows, labels)
    return rows, labels


def check_cohort(protocol, out):
    frozen = read(out / 'frozen.json')
    if frozen['protocol_sha256'] != sha(protocol) or sha(out / 'dataset.json') != frozen['files_sha256']['dataset.json']:
        raise ValueError('Cohort and execution protocol differ')
    return frozen


def guard_for(out, maximum_seconds):
    from chess_native_resources import windows_sample, reasons, Policy, GIB
    policy = Policy(start_physical_available_bytes=6*GIB, start_commit_headroom_bytes=8*GIB,
                    start_gpu_free_bytes=4*GIB, stop_physical_available_bytes=4*GIB,
                    stop_commit_headroom_bytes=6*GIB, stop_gpu_free_bytes=512*1024**2)
    started, first, last = time.monotonic(), True, -float('inf')
    def guard():
        nonlocal first, last
        now = time.monotonic()
        if (out / 'CANCEL').exists() or now - started >= maximum_seconds:
            raise InterruptedError('Owned cancellation or deadline')
        if now - last < 1:
            return
        sample = windows_sample()
        last = now
        with (out / 'resources.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(asdict(sample)) + '\n')
        issues = reasons(sample, policy, 'start' if first else 'running'); first = False
        if issues:
            raise RuntimeError('Resource reserve: ' + ','.join(issues))
    return guard


def audited_module(name, binding):
    path = bound(binding)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def compact_features(states, values):
    """Use current-state context only: mean board, source square, target square."""
    import torch
    if states.ndim != 3 or tuple(states.shape[1:]) != (64, 1024) or len(values) != len(states):
        raise ValueError('Expected one finite [64,1024] current state per move')
    if not torch.isfinite(states).all():
        raise ValueError('Nonfinite encoder state')
    result = []
    for state, value in zip(states, values):
        source, target, _ = move_indices(value)
        result.append(torch.cat((state.float().mean(0), state[source].float(), state[target].float())))
    return torch.stack(result)


def extract_groups(groups, encode, emit, attempt):
    """One backend failure latches the batch and all remaining requested moves."""
    ledger = [{'case_id': r['case_id'], 'input_sha256': r['input_sha256'], 'status': 'not_run'}
              for _, rows in groups for r in rows]
    cursor, failure = 0, None
    for group_index, (fen, rows) in enumerate(groups):
        indices = range(cursor, cursor + len(rows)); cursor += len(rows)
        if failure is not None:
            continue
        for i in indices:
            ledger[i]['status'] = 'unknown_after_interruption'
        attempt(group_index, rows)
        try:
            state = encode(fen)
            emitted = emit(group_index, rows, state)
            for i, info in zip(indices, emitted, strict=True):
                ledger[i].update(info, status='completed')
        except Exception as error:
            failure = type(error).__name__ + ': ' + str(error)
            for i in indices:
                ledger[i].update(status='failed', error=failure)
    return ledger, failure


def features(protocol, out, scope):
    plan = verify(protocol)
    check_cohort(protocol, out)
    if scope not in ('training', 'holdout'):
        raise ValueError('Unknown feature scope')
    if scope == 'holdout':
        selection_path = out / 'selection-before-holdout.json'
        if not selection_path.is_file():
            raise ValueError('Freeze development selection before heldout pretrained calls')
        selection = read(selection_path)
        if selection['protocol_sha256'] != sha(protocol) or selection['feature_manifest_sha256'] != sha(out / 'features-training/manifest.json'):
            raise ValueError('Development selection identity differs')
        bound(selection['selected'])
    target = out / ('features-' + scope)
    target.mkdir()
    snapshot(protocol, target / 'sources')
    splits = ('train', 'dev') if scope == 'training' else ('holdout',)
    rows = [row for split in splits for row in panel(out, split)[0]]
    grouped = requests(rows)
    save(target / 'planned.json', {'protocol_sha256': sha(protocol), 'requested_moves': len(rows),
        'unique_current_fens': len(grouped), 'inputs': {s: sha(out / (s + '-inputs.json')) for s in splits},
        'requests': [{'case_id': r['case_id'], 'input_sha256': r['input_sha256'], 'status': 'not_run'}
                     for _, group in grouped for r in group]})
    guard = guard_for(out, plan['maximum_seconds']); guard()
    import torch
    torch.set_num_threads(4)
    for item in (plan['encoder']['weights'], plan['encoder']['config']):
        bound(item)
    encoder_module = audited_module('encoder_check_lc0', plan['encoder']['source'])
    planes_module = audited_module('encoder_check_planes', plan['encoder']['planes_source'])
    config = encoder_module.Lc0Bt4HFConfig.from_pretrained(ROOT / plan['encoder']['directory'], local_files_only=True)
    encoder = materialize_pinned_module(torch, lambda: encoder_module.Lc0Bt4HFModel(config),
        ROOT / plan['encoder']['weights']['path'], 'cuda', torch.bfloat16)
    if any(value.dtype != torch.bfloat16 for value in encoder.buffers() if value.is_floating_point()):
        raise ValueError('Floating encoder buffers must be explicitly BF16')
    if encoder.policy_index_map.dtype != torch.int64:
        raise ValueError('Integer encoder mapping must retain int64')
    encoder.eval().requires_grad_(False)
    guard()
    # Pair-level deduplication is exact: one current FEN per forward. The public
    # encoder also computes policy/value heads internally; none enter our cache.
    def encode(fen):
        guard()
        with torch.inference_mode():
            planes = planes_module.encode_fen_batch([fen], [[]]).to('cuda')
            result = encoder(input_planes=planes, return_dict=True).last_hidden_state
            if tuple(result.shape) != (1, 64, 1024) or not torch.isfinite(result).all():
                raise ValueError('Encoder state contract failed')
            return result[0].float().cpu().clone()
    with (target / 'attempts.jsonl').open('x', encoding='utf-8') as journal:
        def attempt(index, group):
            journal.write(json.dumps({'index': index, 'ids': [r['case_id'] for r in group], 'status': 'started'}) + '\n')
            journal.flush(); os.fsync(journal.fileno())
        def emit(index, group, state):
            values = [r['input'] for r in group]
            tensors = compact_features(state.unsqueeze(0).expand(len(group), -1, -1), values)
            path = target / f'features-{index:05d}.pt'
            torch.save({'features': tensors, 'indices': torch.tensor([move_indices(v) for v in values], dtype=torch.long)}, path)
            digest = sha(path)
            result = [{'shard': path.name, 'row': i, 'shard_sha256': digest} for i in range(len(group))]
            journal.write(json.dumps({'index': index, 'status': 'completed', 'records': result}) + '\n')
            journal.flush(); os.fsync(journal.fileno())
            if index % 128 == 0:
                save(target / 'progress.json', {'completed_fens': index + 1, 'total_fens': len(grouped)})
            return result
        ledger, failure = extract_groups(grouped, encode, emit, attempt)
    manifest = {'schema': SCHEMA, 'protocol_sha256': sha(protocol), 'scope': scope,
        'requested_moves': len(rows), 'unique_current_fens': len(grouped),
        'input_files_sha256': {s: sha(out / (s + '-inputs.json')) for s in splits},
        'encoder_weights_sha256': plan['encoder']['weights']['sha256'],
        'feature_contract': 'FP32 [mean-current-state, source-current-state, target-current-state],3072; native POV source,target,promotion indices; no labels or future features',
        'statuses': dict(Counter(r['status'] for r in ledger)), 'records': ledger}
    save(target / 'manifest.json', manifest)
    del encoder
    if failure:
        raise RuntimeError('Feature backend failed; remaining requests not run: ' + failure)
    return manifest


def make_head():
    import torch
    class CheckHead(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.source = torch.nn.Embedding(64, 32)
            self.target = torch.nn.Embedding(64, 32)
            self.promotion = torch.nn.Embedding(5, 8)
            self.layers = torch.nn.Sequential(torch.nn.Linear(3144, 512), torch.nn.ReLU(),
                torch.nn.Linear(512, 128), torch.nn.ReLU(), torch.nn.Linear(128, 1))
        def forward(self, features, indices):
            if features.ndim != 2 or features.shape[1] != 3072 or indices.shape != (len(features), 3):
                raise ValueError('Head feature shape differs')
            value = torch.cat((features, self.source(indices[:, 0]), self.target(indices[:, 1]),
                               self.promotion(indices[:, 2])), dim=-1)
            return self.layers(value).squeeze(-1)
    return CheckHead()


def cached_panel(protocol, out, split):
    import torch
    rows, labels = panel(out, split, True)
    target = out / ('features-holdout' if split == 'holdout' else 'features-training')
    manifest = read(target / 'manifest.json')
    if manifest['protocol_sha256'] != sha(protocol) or manifest['input_files_sha256'][split] != sha(out / (split + '-inputs.json')):
        raise ValueError('Feature manifest input/protocol mismatch')
    records = {r['case_id']: r for r in manifest['records']}
    features, indices, loaded = [], [], {}
    for row in rows:
        record = records[row['case_id']]
        value = packet({'fen': row['fen'], 'selected_uci': row['selected_uci']})
        if record['status'] != 'completed' or record['input_sha256'] != json_hash(value):
            raise ValueError('Incomplete or mismatched requested feature')
        path = target / record['shard']
        if path not in loaded:
            if sha(path) != record['shard_sha256']:
                raise ValueError('Feature shard changed')
            loaded[path] = torch.load(path, map_location='cpu', weights_only=True)
        item = loaded[path]
        vector, move = item['features'][record['row']], item['indices'][record['row']]
        if tuple(vector.shape) != (3072,) or not torch.isfinite(vector).all() or move.tolist() != list(move_indices(value)):
            raise ValueError('Cached feature contract differs')
        features.append(vector); indices.append(move)
    return rows, labels, torch.stack(features), torch.stack(indices)


def score(rows, labels, predictions):
    validate_labels(rows, labels)
    if len(predictions) != len(rows) or [r['case_id'] for r in predictions] != [r['case_id'] for r in rows]:
        raise ValueError('Keep every planned prediction in exact order')
    counts = Counter(tp=0, tn=0, fp=0, fn=0, invalid_positive=0, invalid_negative=0)
    pairs, statuses = OrderedDict(), Counter()
    for row, label, prediction in zip(rows, labels, predictions):
        value, truth = prediction.get('prediction'), label['gives_check']
        valid = prediction['status'] == 'completed' and type(value) is bool
        key = ('tp' if value else 'fn') if truth else ('fp' if value else 'tn')
        counts[key if valid else 'invalid_positive' if truth else 'invalid_negative'] += 1
        pairs.setdefault(row['fen'], []).append(valid and value == truth)
        statuses[prediction['status']] += 1
    positive = sum(r['gives_check'] for r in labels)
    negative = len(rows) - positive
    return {'planned': len(rows), 'positive_support': positive, 'negative_support': negative,
        'statuses': dict(statuses), 'confusion': dict(counts), 'correct': counts['tp'] + counts['tn'],
        'checking_recall': counts['tp']/positive, 'nonchecking_recall': counts['tn']/negative,
        'pairs_planned': len(pairs), 'pairs_correct': sum(all(items) for items in pairs.values())}


def evaluate_head(model, rows, labels, x, indices, batch_size, guard, device='cuda', event=lambda value: None):
    import torch
    result = [{'case_id': row['case_id'], 'status': 'not_run'} for row in rows]
    failure = None
    model.eval()
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            if failure:
                break
            end = min(start + batch_size, len(rows))
            try:
                guard()
                event({'status': 'started', 'ids': [row['case_id'] for row in rows[start:end]]})
                logits = model(x[start:end].to(device), indices[start:end].to(device)).float().cpu()
                if tuple(logits.shape) != (end-start,) or not torch.isfinite(logits).all():
                    raise ValueError('Nonfinite or malformed raw head logits')
                for index, logit in enumerate(logits.tolist(), start):
                    result[index] = {'case_id': rows[index]['case_id'], 'status': 'completed',
                        'logit': logit, 'probability': float(torch.sigmoid(torch.tensor(logit))), 'prediction': logit >= 0}
                event({'status': 'completed', 'records': result[start:end]})
            except Exception as error:
                failure = type(error).__name__ + ': ' + str(error)
                for index in range(start, end):
                    result[index].update(status='failed', error=failure)
                event({'status': 'failed', 'records': result[start:end]})
    return result, score(rows, labels, result), failure


def recover_predictions(rows, journal_path):
    """Read completed/started events; never call a model or replay a request."""
    result = {row['case_id']: {'case_id': row['case_id'], 'status': 'not_run'} for row in rows}
    if journal_path.exists():
        lines = journal_path.read_text(encoding='utf-8').splitlines()
        for index, line in enumerate(lines):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                if index == len(lines) - 1:
                    break  # A torn final append leaves its durable start unknown.
                raise ValueError('Nonterminal malformed prediction journal')
            if event['status'] == 'started':
                for case_id in event['ids']:
                    if case_id not in result or result[case_id]['status'] != 'not_run':
                        raise ValueError('Unplanned or repeated backend request')
                    result[case_id] = {'case_id': case_id, 'status': 'unknown_after_interruption'}
            elif event['status'] in ('completed', 'failed'):
                for row in event['records']:
                    case_id = row['case_id']
                    if case_id not in result or result[case_id]['status'] not in ('unknown_after_interruption', 'completed'):
                        raise ValueError('Outcome lacks a durable backend intent')
                    result[case_id] = row
            else:
                raise ValueError('Unknown prediction event')
    return [result[row['case_id']] for row in rows]


def recorded_evaluate(path, model, rows, labels, x, indices, batch_size, guard, device='cuda'):
    """Persist batch intent/results and a complete denominator around each call."""
    journal_path = path.with_suffix('.attempts.jsonl')
    existing = read(path) if path.exists() else {}
    pending = [{'case_id': row['case_id'], 'status': 'not_run'} for row in rows]
    save(path, {**existing, 'raw': pending, 'score': score(rows, labels, pending)})
    with journal_path.open('x', encoding='utf-8') as journal:
        def event(value):
            journal.write(json.dumps(value, allow_nan=False) + '\n')
            journal.flush(); os.fsync(journal.fileno())
            recovered = recover_predictions(rows, journal_path)
            save(path, {**existing, 'raw': recovered, 'score': score(rows, labels, recovered)})
        try:
            return evaluate_head(model, rows, labels, x, indices, batch_size, guard, device, event)
        finally:
            recovered = recover_predictions(rows, journal_path)
            save(path, {**existing, 'raw': recovered, 'score': score(rows, labels, recovered)})


def recover_evaluations(protocol, out):
    verify(protocol); check_cohort(protocol, out)
    results = {}
    for directory, pattern, split in ((out / 'training', 'dev-epoch-*.attempts.jsonl', 'dev'),
                                       (out / 'evaluation', '*.attempts.jsonl', 'holdout')):
        if not directory.is_dir():
            continue
        for journal in sorted(directory.glob(pattern)):
            rows, labels = panel(out, split, True)
            raw = recover_predictions(rows, journal)
            path = journal.with_name(journal.name.replace('.attempts.jsonl', '.json'))
            existing = read(path) if path.exists() else {}
            value = {**existing, 'raw': raw, 'score': score(rows, labels, raw), 'recovered_without_model_calls': True}
            save(path, value); results[str(path)] = value['score']['statuses']
    return {'status': 'recovered_saved_journals_only', 'model_calls': 0, 'files': results}


def selection_key(row):
    return row['correct'], row['pairs_correct'], -row['epoch']


def train(protocol, out):
    plan = verify(protocol)
    check_cohort(protocol, out)
    target = out / 'training'; target.mkdir()
    snapshot(protocol, target / 'sources')
    guard = guard_for(out, plan['maximum_seconds']); guard()
    import torch
    torch.set_num_threads(4); torch.manual_seed(plan['training']['seed'])
    train_rows, train_labels, x, indices = cached_panel(protocol, out, 'train')
    dev_rows, dev_labels, dev_x, dev_indices = cached_panel(protocol, out, 'dev')
    labels = torch.tensor([r['gives_check'] for r in train_labels], dtype=torch.float32)
    head = make_head().to('cuda')
    optimizer = torch.optim.AdamW(head.parameters(), lr=plan['training']['learning_rate'],
                                 weight_decay=plan['training']['weight_decay'])
    checkpoints = []
    def checkpoint(epoch):
        path = target / f'epoch-{epoch}.pt'
        torch.save({k: v.cpu() for k, v in head.state_dict().items()}, path)
        raw, scored, failure = recorded_evaluate(target / f'dev-epoch-{epoch}.json', head,
            dev_rows, dev_labels, dev_x, dev_indices, plan['training']['batch_size'], guard)
        save(target / f'dev-epoch-{epoch}.json', {'raw': raw, 'score': scored})
        if failure:
            raise RuntimeError('Development backend failed; stop all subsequent calls: ' + failure)
        row = {'epoch': epoch, 'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
               'correct': scored['correct'], 'pairs_correct': scored['pairs_correct']}
        checkpoints.append(row); save(target / 'checkpoints.json', checkpoints)
    checkpoint(0)
    generator = torch.Generator().manual_seed(plan['training']['seed'] + 1)
    updates = 0
    with (target / 'loss.jsonl').open('x', encoding='utf-8') as journal:
        for epoch in range(1, plan['training']['epochs'] + 1):
            order = torch.randperm(len(train_rows), generator=generator)
            head.train()
            for start in range(0, len(order), plan['training']['batch_size']):
                if updates % 64 == 0:
                    guard()
                batch = order[start:start + plan['training']['batch_size']]
                optimizer.zero_grad(set_to_none=True)
                logits = head(x[batch].to('cuda'), indices[batch].to('cuda'))
                loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels[batch].to('cuda'))
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite head loss')
                loss.backward(); torch.nn.utils.clip_grad_norm_(head.parameters(), 1, error_if_nonfinite=True)
                optimizer.step(); updates += 1
                journal.write(json.dumps({'epoch': epoch, 'update': updates, 'loss': float(loss)}) + '\n')
                journal.flush(); os.fsync(journal.fileno())
            if epoch in plan['training']['checkpoint_epochs']:
                checkpoint(epoch)
    selected = max(checkpoints, key=selection_key)
    selection = {'protocol_sha256': sha(protocol), 'feature_manifest_sha256': sha(out / 'features-training/manifest.json'),
                 'selected': selected, 'candidates': checkpoints, 'actual_updates': updates,
                 'heldout_learned_calls_before_selection': 0}
    save(out / 'selection-before-holdout.json', selection)
    return selection


def evaluate(protocol, out):
    plan = verify(protocol)
    check_cohort(protocol, out)
    selection = read(out / 'selection-before-holdout.json')
    if selection['protocol_sha256'] != sha(protocol):
        raise ValueError('Selection protocol differs')
    target = out / 'evaluation'; target.mkdir()
    rows, labels = panel(out, 'holdout', True)
    pending = [{'case_id': row['case_id'], 'status': 'not_run'} for row in rows]
    result = {name: score(rows, labels, pending) for name in ('untrained_head', 'selected_head')}
    for name in result:
        save(target / (name + '.json'), {'raw': pending, 'score': result[name], 'checkpoint':
             selection['candidates'][0] if name == 'untrained_head' else selection['selected']})
    majority = [{'case_id': row['case_id'], 'status': 'completed', 'prediction': False} for row in rows]
    save(target / 'majority-false.json', {'raw': majority, 'score': score(rows, labels, majority)})
    snapshot(protocol, target / 'sources')
    _, _, x, indices = cached_panel(protocol, out, 'holdout')
    guard = guard_for(out, plan['maximum_seconds']); guard()
    import torch
    torch.set_num_threads(4)
    for name, candidate in (('untrained_head', selection['candidates'][0]), ('selected_head', selection['selected'])):
        if name == 'selected_head' and candidate['epoch'] == 0:
            prior = read(target / 'untrained_head.json')
            save(target / 'selected_head.json', {**prior, 'alias_of': 'untrained_head', 'additional_forward_calls': 0})
            result[name] = result['untrained_head']
            continue
        model = make_head()
        model.load_state_dict(torch.load(bound(candidate), map_location='cpu', weights_only=True), strict=True)
        model.to('cuda')
        raw, scored, failure = recorded_evaluate(target / (name + '.json'), model, rows, labels, x,
                                                indices, plan['training']['batch_size'], guard)
        save(target / (name + '.json'), {'raw': raw, 'score': scored, 'checkpoint': candidate})
        result[name] = scored
        del model
        if failure:
            save(target / 'summary.json', {'status': 'failed', 'conditions': result,
                'remaining_condition': 'selected_head_not_run' if name == 'untrained_head' else None})
            raise RuntimeError('Heldout backend failed; stop subsequent conditions: ' + failure)
    value = {'status': 'completed', 'protocol_sha256': sha(protocol),
        'selection_sha256': sha(out / 'selection-before-holdout.json'),
        'majority_false': score(rows, labels, majority), 'conditions': result,
        'scope': 'Learned check discrimination from frozen expert current-board features; not language understanding, move strength or explanation correctness.'}
    save(target / 'summary.json', value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['intake', 'features', 'train', 'evaluate', 'run', 'recover'])
    parser.add_argument('--protocol', type=Path, default=ROOT / 'experiments/chess-encoder-check-v1/protocol-v2.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'data/private/chess-encoder-check-v1')
    parser.add_argument('--scope', choices=['training', 'holdout'], default='training')
    args = parser.parse_args()
    try:
        if args.phase == 'run':
            features(args.protocol, args.out, 'training')
            train(args.protocol, args.out)
            features(args.protocol, args.out, 'holdout')
            result = evaluate(args.protocol, args.out)
        elif args.phase == 'recover':
            result = recover_evaluations(args.protocol, args.out)
        else:
            result = features(args.protocol, args.out, args.scope) if args.phase == 'features' else globals()[args.phase](args.protocol, args.out)
        print(json.dumps(result, allow_nan=False))
    except Exception as error:
        if args.out.exists():
            save(args.out / f'failure-{args.phase}.json', {'phase': args.phase,
                'utc': datetime.now(timezone.utc).isoformat(), 'error': type(error).__name__ + ': ' + str(error)})
        raise


if __name__ == '__main__':
    main()
