"""Larger, game-disjoint native chess policy training and raw three-ply forecasts.

Only the root coordinator runs the CUDA phase. Intake/teachers are CPU-only.
Source solution tails are ignored. Engine reference is never model input.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import time

import chess
import chess.engine
from chess_fact_sft_common import read, save, sha
from chess_fact_sft_intake import board_key, canonical_game_id, parquet_rows
from chess_classifier_adapter import encode_fen, load_native_contract, native_text_for_fen, verify_model_mapping
import chess_classifier_experiment_v3 as previous

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess.move-policy.v5'
SPLITS = ('train', 'development', 'holdout', 'rollout')


def bound_file(binding, repo=ROOT):
    path = repo / binding['path']
    if sha(path) != binding['sha256']:
        raise ValueError('frozen file changed: ' + binding['path'])
    return path


def verify_protocol(path, repo=ROOT):
    plan = read(path)
    if plan['schema'] != SCHEMA or plan['implementation_sha256'] != sha(Path(__file__)):
        raise ValueError('wrong protocol or implementation identity')
    for binding in plan['dependencies']:
        bound_file(binding, repo)
    return plan


def add_roles(row, games, boards):
    games.add(canonical_game_id(row['game_id']))
    boards.update(row.get('successor_keys', []))
    for name in ('source_before_fen', 'fen'):
        if name in row:
            boards.add(board_key(row[name]))
    for uci in row.get('selected_pair', [row['selected_uci']] if 'selected_uci' in row else []):
        board = chess.Board(row['fen'])
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError('invalid retained exclusion move')
        board.push(move)
        boards.add(board_key(board.fen()))


def exclusions(plan, repo=ROOT):
    registry = read(bound_file(plan['known_registry'], repo))
    games, boards = set(registry['games']), set(registry['board_keys'])
    for binding in plan['additional_cohorts']:
        data = read(bound_file(binding, repo))
        rows = data.get('rows', data.get('pairs', []))
        if not rows:
            rows = [r for values in data.get('groups', data.get('splits', {})).values() for r in values]
        if not rows:
            raise ValueError('exclusion cohort empty')
        for row in rows:
            add_roles(row, games, boards)
    return games, boards


def split_for(game, seed):
    bucket = int(hashlib.sha256(f'{seed}:{game}'.encode()).hexdigest(), 16) % 1000
    return 'development' if bucket < 15 else 'holdout' if bucket < 30 else 'rollout' if bucket < 34 else 'train'


def select_rows(rows, counts, seed, excluded_games, excluded_boards, cap):
    games, boards = set(excluded_games), set(excluded_boards)
    result, rejects = {s: [] for s in SPLITS}, Counter()
    ids = set()
    scanned = 0
    for location, source in rows:
        scanned += 1
        if scanned > cap:
            break
        try:
            game = canonical_game_id(source['GameId'])
            split = split_for(game, seed)
            if len(result[split]) >= counts[split]:
                rejects['bucket_full'] += 1
                continue
            if game in games:
                rejects['excluded_game'] += 1
                continue
            board = chess.Board(source['FEN'])
            if not board.is_valid() or board.chess960:
                raise ValueError('invalid orthodox source')
            before = board.fen()
            # Never parse, store, or use source solution/theme tokens.
            setup = chess.Move.from_uci(source['Moves'].split(maxsplit=1)[0])
            if setup not in board.legal_moves:
                raise ValueError('illegal setup')
            board.push(setup)
            native_text_for_fen(board.fen())
            if board.is_game_over() or board_key(before) in boards or board_key(board.fen()) in boards:
                rejects['excluded_board_or_terminal'] += 1
                continue
            puzzle = source['PuzzleId']
            if not isinstance(puzzle, str) or not puzzle.isalnum() or puzzle in ids:
                raise ValueError('invalid or duplicate puzzle id')
        except (KeyError, ValueError, TypeError, IndexError):
            rejects['invalid'] += 1
            continue
        row = {'id': 'policy-v5-' + puzzle, 'puzzle_id': puzzle, 'game_id': game,
               'source_before_fen': before, 'setup_uci': setup.uci(), 'fen': board.fen(), **location}
        result[split].append(row)
        games.add(game)
        boards.update((board_key(before), board_key(board.fen())))
        ids.add(puzzle)
        if all(len(result[s]) == counts[s] for s in SPLITS):
            break
    if any(len(result[s]) != counts[s] for s in SPLITS):
        raise ValueError('source cap cannot fill frozen quotas: ' + str({s: len(result[s]) for s in SPLITS}))
    return result, {'scanned': scanned, 'rejections': dict(rejects)}


def snapshot(out, protocol, name='executed-sources'):
    target = out / name
    target.mkdir()
    paths = [Path(__file__), protocol] + [ROOT / item['path'] for item in read(protocol)['dependencies']]
    bindings = {}
    for path in paths:
        shutil.copyfile(path, target / path.name)
        bindings[path.name] = sha(target / path.name)
    save(target / 'manifest.json', bindings)
    return bindings


def intake(protocol, out):
    plan = verify_protocol(protocol)
    source = bound_file(plan['source'])
    games, boards = exclusions(plan)
    if out.exists():
        raise ValueError('intake is create-only')
    out.mkdir(parents=True)
    executed = snapshot(out, protocol)
    splits, selection = select_rows(parquet_rows(source), plan['counts'], plan['seed'],
                                    games, boards, plan['source_row_cap'])
    dataset = {'schema': SCHEMA, 'protocol_sha256': sha(protocol), 'source_sha256': sha(source),
               'exclusion_counts': {'games': len(games), 'board_keys': len(boards)},
               'executed_sources': executed, 'selection': selection, 'splits': splits}
    save(out / 'dataset.json', dataset)
    save(out / 'intake-receipt.json', {'dataset_sha256': sha(out / 'dataset.json'),
         'counts': {s: len(v) for s, v in splits.items()}, 'model_calls': 0, 'engine_calls': 0})
    return dataset


def teacher_observation(board, event, final_move):
    """One individual score event; never merge bound flags across UCI lines."""
    if final_move not in board.legal_moves:
        raise ValueError('missing or illegal final teacher bestmove')
    pv = event.get('pv', []) if event else []
    if not pv or pv[0] != final_move or 'score' not in event:
        raise ValueError('final bestmove and last score-event PV disagree')
    line, replay = [], board.copy(stack=False)
    for move in pv[:3]:
        if move not in replay.legal_moves:
            raise ValueError('illegal teacher continuation')
        line.append(move.uci())
        replay.push(move)
    score = event['score'].pov(board.turn)
    return {'status':'completed', 'teacher_move_uci': final_move.uci(), 'reference_pv': line,
        'score': {'cp':score.score(), 'mate':score.mate(), 'perspective':'side_to_move',
                  'lowerbound':bool(event.get('lowerbound')), 'upperbound':bool(event.get('upperbound'))},
        'nodes':event.get('nodes'), 'depth':event.get('depth')}


def teacher_chunk(engine_path, settings, rows, journal_path, cancel_path):
    records = []
    journal = Path(journal_path).open('x', encoding='utf-8', newline='\n', buffering=1)
    with chess.engine.SimpleEngine.popen_uci(engine_path, timeout=60) as engine:
        engine.configure({'Threads': 1, 'Hash': settings['hash_mb']})
        if '19' not in engine.id.get('name', ''):
            raise ValueError('pinned Stockfish19 required')
        failed_engine = False
        for split, row in rows:
            record = {**row, 'status': 'not_run', 'teacher_move_uci': None, 'reference_pv': []}
            try:
                if failed_engine or Path(cancel_path).exists():
                    record['error'] = 'not_run_after_engine_failure_or_cancel'
                    raise InterruptedError(record['error'])
                record['status'] = 'failed'
                board = chess.Board(row['fen'])
                event = None
                with engine.analysis(board, chess.engine.Limit(nodes=settings['nodes']), game=object(),
                        info=chess.engine.INFO_SCORE|chess.engine.INFO_PV|chess.engine.INFO_BASIC) as analysis:
                    for item in analysis:
                        if 'score' in item:
                            event = dict(item)
                    final = analysis.wait()
                record.update(teacher_observation(board, event, final.move))
            except Exception as error:
                record['error'] = type(error).__name__ + ':' + str(error)
                if isinstance(error, (chess.engine.EngineError, TimeoutError)):
                    failed_engine = True
            journal.write(json.dumps({'split':split,'record':record}, allow_nan=False)+'\n')
            journal.flush()
            os.fsync(journal.fileno())
            records.append((split, record))
    journal.close()
    return records


def recovered_chunk(rows, journal, error):
    actual = {}
    if journal.exists():
        for line in journal.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                break  # Torn final record remains unknown, never called again.
            key = (item['split'], item['record']['id'])
            if key in actual or key not in {(s,r['id']) for s,r in rows}:
                raise ValueError('invalid teacher journal identity')
            actual[key] = item['record']
    return [(s,actual.get((s,r['id']), {**r,'status':'not_run','teacher_move_uci':None,
             'reference_pv':[],'error':'unknown_after_worker_failure:'+type(error).__name__})) for s,r in rows]


def verify_dataset_protocol(plan, protocol, dataset, out):
    if dataset['protocol_sha256'] == sha(protocol):
        return
    amendment = plan.get('accepted_intake', {})
    if (amendment.get('original_protocol_sha256') != dataset['protocol_sha256']
            or amendment.get('dataset_sha256') != sha(out/'dataset.json')
            or amendment.get('intake_receipt_sha256') != sha(out/'intake-receipt.json')):
        raise ValueError('dataset protocol/amendment binding changed')


def label(protocol, out):
    plan = verify_protocol(protocol)
    dataset = read(out / 'dataset.json')
    verify_dataset_protocol(plan, protocol, dataset, out)
    if (out/'label-attempt.json').exists() or (out/'labels.json').exists():
        raise ValueError('label attempt already exists; never replay spent engine calls')
    engine = bound_file(plan['teacher']['binary'])
    with (out/'label-attempt.json').open('x', encoding='utf-8') as stream:
        json.dump({'protocol_sha256':sha(protocol),'started_at':datetime.now(timezone.utc).isoformat()},stream)
    snapshot(out,protocol,'label-executed-sources')
    (out/'teacher-chunks').mkdir()
    tasks = [(s, r) for s, rows in dataset['splits'].items() for r in rows]
    chunks = [tasks[i:i+128] for i in range(0, len(tasks), 128)]
    records = {s: {} for s in SPLITS}
    started, done = time.perf_counter(), 0
    with ProcessPoolExecutor(max_workers=plan['teacher']['workers']) as pool:
        futures = {}
        for index, rows in enumerate(chunks):
            journal = out/'teacher-chunks'/f'chunk-{index:04d}.jsonl'
            futures[pool.submit(teacher_chunk,str(engine),plan['teacher'],rows,str(journal),str(out/'CANCEL'))] = (rows,journal)
        for future in as_completed(futures):
            try:
                values = future.result()
            except Exception as error:
                values = recovered_chunk(*futures[future],error)
            for split, row in values:
                records[split][row['id']] = row
                done += 1
            save(out / 'label-progress.json', {'done': done, 'total': len(tasks), 'seconds': time.perf_counter()-started})
            print(json.dumps({'phase': 'teacher', 'done': done, 'total': len(tasks)}), flush=True)
    result = {'schema': SCHEMA, 'dataset_sha256': sha(out / 'dataset.json'), 'protocol_sha256': sha(protocol),
              'engine': plan['teacher'], 'elapsed_seconds': time.perf_counter()-started,
              'splits': {s: [records[s][r['id']] for r in rows] for s, rows in dataset['splits'].items()}}
    result['failure_count'] = sum(r['status'] != 'completed' for rows in result['splits'].values() for r in rows)
    save(out / 'labels.json', result)
    save(out / 'label-completed.json', {'labels_sha256':sha(out/'labels.json'), 'failures':result['failure_count']})
    return result


def forecast_rows(rows, predictor, plies=3):
    """Predict from current FEN only; the predictor receives no references."""
    records = []
    backend_failure = None
    for row in rows:
        if backend_failure is not None:
            records.append({'id':row['id'],'predicted':[],'legal_plies':0,'status':'not_run',
                            'error':'not_run_after_backend_failure:'+backend_failure})
            continue
        board = chess.Board(row['fen'])
        record = {'id': row['id'], 'predicted': [], 'legal_plies': 0, 'status': 'completed'}
        for _ in range(plies):
            if board.is_game_over():
                record['status'] = 'game_over'
                break
            try:
                uci = predictor(board.fen())
                move = chess.Move.from_uci(uci)
                record['predicted'].append(uci)
                if move not in board.legal_moves:
                    record['status'] = 'illegal_move'
                    break
                board.push(move)
                record['legal_plies'] += 1
            except Exception as error:
                record.update(status='failed', error=type(error).__name__)
                backend_failure = type(error).__name__
                break
        records.append(record)
    return records


def score_forecasts(raw, references):
    if [r['id'] for r in raw] != [r['id'] for r in references]:
        raise ValueError('forecast denominator mismatch')
    scores = {'planned': len(references), 'status': dict(Counter(r['status'] for r in raw)), 'prefix': {}}
    for k in (1, 2, 3):
        supported = sum(r['status'] == 'completed' and len(r['reference_pv']) >= k for r in references)
        correct = sum(ref['status'] == 'completed' and len(ref['reference_pv']) >= k
                      and row['legal_plies'] >= k and row['predicted'][:k] == ref['reference_pv'][:k]
                      for row, ref in zip(raw, references, strict=True))
        scores['prefix'][str(k)] = {'teacher_supported': supported, 'exact': correct,
            'all_planned_denominator': len(references), 'legal_through_ply': sum(r['legal_plies'] >= k for r in raw)}
    return scores


def rollout(model, rows, contract, device, prefix, out):
    import torch
    model.eval()
    def predict(fen):
        encoded = encode_fen(fen, contract)
        ids = torch.tensor([encoded['input_ids']], dtype=torch.long, device=device)
        with torch.inference_mode():
            logits = model(input_ids=ids, attention_mask=torch.ones_like(ids)).logits.float()
        if tuple(logits.shape) != (1, 1968) or not bool(torch.isfinite(logits).all()):
            raise ValueError('invalid policy logits')
        return contract['id2label'][int(logits[0].argmax())]
    # Strip evaluator fields before forecasting. Save all raw choices before scoring.
    raw = forecast_rows([{'id': r['id'], 'fen': r['fen']} for r in rows], predict)
    raw_path = out / (prefix + '-rollout-raw.json')
    save(raw_path, {'rows': raw})
    result = score_forecasts(raw, rows)
    result['raw_sha256'] = sha(raw_path)
    save(out / (prefix + '-rollout-score.json'), result)
    if any(row['status'] in ('failed','not_run') for row in raw):
        raise RuntimeError('forecast backend failed; raw/score saved; further backend calls prohibited')
    return result


def checked_evaluate(*args, **kwargs):
    result = previous.evaluate(*args, **kwargs)
    if result['failure_count'] or result.get('model_failure_stop'):
        raise RuntimeError('policy evaluation failed; retained results prohibit further backend calls')
    return result


def resource_check(out, plan, started):
    from chess_native_resources import windows_sample, Policy, reasons, GIB
    if (out/'CANCEL').exists():
        raise InterruptedError('owned policy cancellation requested')
    if time.perf_counter()-started > plan['maximum_seconds']:
        raise TimeoutError('owned policy deadline')
    sample = windows_sample()
    limits = Policy(stop_physical_available_bytes=4*GIB,stop_commit_headroom_bytes=8*GIB,
                    stop_gpu_free_bytes=GIB//4)
    issues = reasons(sample, limits, 'running')
    with (out/'resources.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(asdict(sample))+'\n')
    if issues:
        raise RuntimeError('resource reserve: '+','.join(issues))


def verify_label_binding(plan, protocol, labels, out):
    if labels['dataset_sha256'] != sha(out/'dataset.json'):
        raise ValueError('label dataset binding mismatch')
    if labels['protocol_sha256'] == sha(protocol):
        return
    accepted = plan.get('accepted_labels', {})
    if (accepted.get('protocol_sha256') != labels['protocol_sha256']
            or accepted.get('labels_sha256') != sha(out/'labels.json')
            or accepted.get('completed_receipt_sha256') != sha(out/'label-completed.json')
            or accepted.get('executed_source_manifest_sha256') != sha(out/'label-executed-sources/manifest.json')):
        raise ValueError('amended label/source binding mismatch')


def train(protocol, out):
    import platform
    import torch
    import transformers
    from transformers import LlamaForSequenceClassification
    plan = verify_protocol(protocol)
    labels = read(out / 'labels.json')
    verify_label_binding(plan,protocol,labels,out)
    if not torch.cuda.is_available():
        raise ValueError('root-coordinator CUDA phase requires CUDA')
    if (out / 'checkpoints').exists() or (out / 'selection-before-holdout.json').exists():
        raise ValueError('training is create-only; no replay')
    snapshot(out,protocol,'train-executed-sources')
    start = ROOT / plan['starting_model']['path']
    bound_file(plan['starting_model']['weights'])
    contract = load_native_contract(ROOT / plan['tokenizer_contract'])
    verify_model_mapping(read(start / 'config.json'))
    encoded, failures = previous.encode_rows(labels['splits']['train'], contract)
    if failures or len(encoded) != plan['counts']['train']:
        raise ValueError('all frozen training rows must encode; do not silently drop failures')
    settings = plan['training']
    started = time.perf_counter()
    resource_check(out,plan,started)
    torch.set_num_threads(4)
    torch.manual_seed(settings['seed'])
    model = LlamaForSequenceClassification.from_pretrained(start, local_files_only=True,
        attn_implementation='sdpa').float().to('cuda')
    torch.cuda.reset_peak_memory_stats()
    (out / 'checkpoints').mkdir()
    model.save_pretrained(out / 'checkpoints/step-0', safe_serialization=True)
    evaluations = {0: checked_evaluate(model, labels['splits']['development'], contract, 'cuda',
                                        'step-0-development', out, 128)}
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings['learning_rate'], weight_decay=settings['weight_decay'])
    rng, order, history = random.Random(settings['seed']), [], []
    model.train()
    for step in range(1, settings['steps']+1):
        if len(order) < settings['batch_size']:
            fresh = list(range(len(encoded)))
            rng.shuffle(fresh)
            order.extend(fresh)
        chosen, order = order[:settings['batch_size']], order[settings['batch_size']:]
        ids = torch.tensor([encoded[i][1] for i in chosen], dtype=torch.long, device='cuda')
        target = torch.tensor([encoded[i][2] for i in chosen], dtype=torch.long, device='cuda')
        optimizer.zero_grad(set_to_none=True)
        loss = model(input_ids=ids, attention_mask=torch.ones_like(ids), labels=target).loss
        if not bool(torch.isfinite(loss)):
            raise ValueError('nonfinite policy loss')
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        history.append({'step': step, 'loss': float(loss.detach()), 'gradient_norm': float(norm)})
        if step % 64 == 0:
            save(out / 'training-log.json', history)
            print(json.dumps({'phase': 'policy_train', **history[-1], 'seconds': time.perf_counter()-started}), flush=True)
            resource_check(out,plan,started)
        if step in settings['checkpoints']:
            model.save_pretrained(out / f'checkpoints/step-{step}', safe_serialization=True)
            evaluations[step] = checked_evaluate(model, labels['splits']['development'], contract, 'cuda',
                f'step-{step}-development', out, 128)
            model.train()
    selected = max(evaluations, key=lambda step: previous.selection_key(step, evaluations[step]))
    selection = {'selected_step': selected, 'rule': plan['selection'], 'holdout_opened': False,
        'development': {str(k): {x: v for x, v in score.items() if x != 'records'} for k, score in evaluations.items()},
        'selected_weights_sha256': sha(out / f'checkpoints/step-{selected}/model.safetensors')}
    save(out / 'selection-before-holdout.json', selection)
    del optimizer, model
    torch.cuda.empty_cache()
    results = {}
    for condition, step in [('starting', 0), ('selected', selected)]:
        if condition == 'selected' and selected == 0:
            results[condition] = {**results['starting'], 'reuses_starting_identical_checkpoint': True}
            continue
        model = LlamaForSequenceClassification.from_pretrained(out / f'checkpoints/step-{step}',
            local_files_only=True, attn_implementation='sdpa').float().to('cuda')
        results[condition] = {'holdout': checked_evaluate(model, labels['splits']['holdout'], contract,
            'cuda', condition+'-holdout', out, 128),
            'rollout': rollout(model, labels['splits']['rollout'], contract, 'cuda', condition, out)}
        del model
        torch.cuda.empty_cache()
    receipt = {'schema': SCHEMA, 'protocol_sha256': sha(protocol), 'labels_sha256': sha(out/'labels.json'),
        'selection_sha256': sha(out/'selection-before-holdout.json'), 'selected_step': selected,
        'training': {**settings, 'presentations': settings['steps']*settings['batch_size'],
                     'seconds_including_evaluation': time.perf_counter()-started}, 'results': results,
        'tokenizer_contract_sha256': contract['source_sha256'],
        'starting_weights_sha256': plan['starting_model']['weights']['sha256'],
        'selected_weights_sha256': selection['selected_weights_sha256'],
        'runtime': {'python': platform.python_version(), 'torch': torch.__version__,
                    'transformers': transformers.__version__, 'gpu': torch.cuda.get_device_name(),
                    'peak_cuda_allocated': torch.cuda.max_memory_allocated()}, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'limitations': plan['limitations']}
    save(out / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('intake', 'label', 'train'))
    parser.add_argument('--protocol', type=Path, default=ROOT/'experiments/chess-move-policy-v5/protocol.json')
    parser.add_argument('--out', type=Path, default=ROOT/'data/private/chess-move-policy-v5')
    args = parser.parse_args()
    try:
        result = {'intake': intake, 'label': label, 'train': train}[args.phase](args.protocol, args.out)
    except Exception as error:
        args.out.mkdir(parents=True, exist_ok=True)
        save(args.out/'failure.json', {'phase':args.phase,'status':'failed','error':type(error).__name__+':'+str(error),
             'utc':datetime.now(timezone.utc).isoformat(),'replay_allowed':False})
        raise
    print(json.dumps({'phase': args.phase, 'status': 'completed',
                      'selected_step': result.get('selected_step'), 'failures': result.get('failure_count')}))


if __name__ == '__main__':
    main()
