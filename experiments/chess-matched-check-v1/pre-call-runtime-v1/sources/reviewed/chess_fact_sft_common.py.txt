"""Frozen native-token boundaries and strict file-only fact evaluation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
import chess_board_fact_core as core


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    for attempt in range(51):
        try:
            temp.replace(path)
            break
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5,32,33) or attempt == 50:
                raise
            time.sleep(.020)  # Local sharing conflicts only; never replay model work.


def native_prompt(tokenizer, row):
    prompt = core.build_prompt(row, 'fen_uci_piece_map')
    ids = tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=True,
        add_generation_prompt=True, enable_thinking=False, return_dict=False)
    if not 0 < len(ids) <= 1408:
        raise ValueError('prompt length outside frozen domain')
    return ids


def native_training_row(tokenizer, row, expected):
    prefix = native_prompt(tokenizer, row)
    target = json.dumps(expected, sort_keys=True, separators=(',', ':'))
    core.parse_facts(target)
    joint = tokenizer.apply_chat_template([
        {'role': 'user', 'content': core.build_prompt(row, 'fen_uci_piece_map')},
        {'role': 'assistant', 'content': target}], tokenize=True,
        add_generation_prompt=False, enable_thinking=False, return_dict=False)
    if joint[:len(prefix)] != prefix:
        raise ValueError('native assistant prefix differs')
    try:
        end = joint.index(tokenizer.eos_token_id, len(prefix)) + 1
    except ValueError as error:
        raise ValueError('assistant EOS absent') from error
    ids = joint[:end]
    count = end - len(prefix)
    if not 0 < count <= 127 or len(ids) > 1536:
        raise ValueError('target/window/sequence outside frozen domain')
    decoded = tokenizer.decode(ids[len(prefix):-1], skip_special_tokens=False)
    if decoded != target:
        raise ValueError('native target did not round-trip exactly')
    return {'input_ids': ids, 'labels': [-100] * len(prefix) + ids[len(prefix):],
            'target_count': count, 'prompt_count': len(prefix), 'case_id': row['case_id']}


def collate_training(rows, pad_id, torch, device):
    width = max(128, max(len(row['input_ids']) for row in rows))
    ids = torch.full((len(rows), width), pad_id, dtype=torch.long)
    labels = torch.full_like(ids, -100)
    mask = torch.zeros_like(ids)
    for index, row in enumerate(rows):
        length = len(row['input_ids'])
        ids[index, -length:] = torch.tensor(row['input_ids'])
        labels[index, -length:] = torch.tensor(row['labels'])
        mask[index, -length:] = 1
    expected = sum(row['target_count'] for row in rows)
    if int((labels[:, -127:] != -100).sum()) != expected or int((labels != -100).sum()) != expected:
        raise ValueError('cropped causal window would drop target')
    positions = (mask.cumsum(-1) - 1).masked_fill(mask == 0, 0)
    return {'input_ids': ids.to(device), 'attention_mask': mask.to(device),
            'position_ids': positions.to(device), 'labels': labels[:, -128:].to(device)}, expected


def decode_generated(tokenizer, ids):
    ids = list(ids)
    try:
        end = ids.index(tokenizer.eos_token_id)
    except ValueError:
        return {'status': 'truncated', 'text': tokenizer.decode(ids, skip_special_tokens=False), 'new_ids': ids}
    if any(token != tokenizer.pad_token_id for token in ids[end + 1:]):
        raise ValueError('nonpadding generated tokens after first EOS')
    return {'status': 'completed', 'text': tokenizer.decode(ids[:end], skip_special_tokens=False), 'new_ids': ids}


def seal_raw(directory, rows, planned_ids, metadata):
    directory = Path(directory)
    if directory.exists():
        raise ValueError('raw cohort cannot be overwritten')
    directory.mkdir(parents=True)
    if len(rows) != len(planned_ids) or [row['case_id'] for row in rows] != planned_ids:
        raise ValueError('all planned outcomes in exact order required')
    save(directory / 'raw.json', {'rows': rows, 'planned': len(planned_ids), 'metadata': metadata})
    save(directory / 'seal.json', {'raw_sha256': sha(directory / 'raw.json'), 'planned_ids': planned_ids,
                                  'planned': len(planned_ids), 'metadata': metadata})
    return sha(directory / 'seal.json')


def score_sealed(directory, labels_path, expected_label_sha256):
    directory = Path(directory)
    seal = read(directory / 'seal.json')
    if sha(directory / 'raw.json') != seal['raw_sha256']:
        raise ValueError('raw seal mismatch before label access')
    raw = read(directory / 'raw.json')
    rows = raw['rows']
    if [row['case_id'] for row in rows] != seal['planned_ids'] or len(rows) != seal['planned']:
        raise ValueError('raw planned denominator mismatch')
    if sha(labels_path) != expected_label_sha256:
        raise ValueError('frozen evaluator label hash mismatch')
    labels = read(labels_path)['rows']
    if [row['case_id'] for row in labels] != seal['planned_ids']:
        raise ValueError('labels and sealed outcomes differ')
    fields = {field: {'correct': 0, 'unknown': 0, 'classes': {}, 'confusion': {}} for field in core.FIELDS}
    counts = {'planned': len(rows), 'all_eight_correct': 0, 'strict_parse_completed': 0,
              'parse_error': 0, 'truncated': 0, 'error': 0, 'not_run': 0}
    outcomes = []
    for row, label in zip(rows, labels, strict=True):
        expected, parsed = label['expected'], None
        if row['status'] == 'completed':
            try:
                parsed = core.parse_facts(row['text'])
                counts['strict_parse_completed'] += 1
            except (ValueError, TypeError):
                counts['parse_error'] += 1
        elif row['status'] in ('truncated', 'error', 'not_run'):
            counts[row['status']] += 1
        else:
            raise ValueError('unrecognized raw status')
        correct = []
        for field in core.FIELDS:
            truth = expected[field]
            prediction = parsed[field] if parsed is not None else '__invalid__'
            # Type identity prevents bool/int equality and gives unknown no credit.
            match = type(prediction) is type(truth) and prediction == truth
            correct.append(match)
            item = fields[field]
            item['correct'] += int(match)
            item['unknown'] += int(prediction == 'unknown')
            key = json.dumps(truth)
            stat = item['classes'].setdefault(key, {'support': 0, 'correct': 0})
            stat['support'] += 1
            stat['correct'] += int(match)
            confusion = key + ' -> ' + json.dumps(prediction)
            item['confusion'][confusion] = item['confusion'].get(confusion, 0) + 1
        counts['all_eight_correct'] += int(all(correct))
        outcomes.append({'case_id': row['case_id'], 'all_eight_correct': all(correct), 'field_correct': dict(zip(core.FIELDS, correct))})
    return {'schema': 'chess.fact-sft.score.v1', 'seal_sha256': sha(directory / 'seal.json'),
            'labels_sha256': sha(labels_path), 'counts': counts, 'fields': fields, 'outcomes': outcomes}


def select_checkpoint(scores):
    if [item['step'] for item in scores] != [0, 128, 256, 512, 1024]:
        raise ValueError('all predeclared dev checkpoints required')
    if any(item['counts']['planned'] != 128 or item['counts']['error'] or item['counts']['not_run'] for item in scores):
        raise ValueError('incomplete dev experiment cannot select')
    ordered = sorted(scores, key=lambda item: (-item['counts']['all_eight_correct'],
        -item['counts']['strict_parse_completed'], item['step']))
    return {'selected_step': ordered[0]['step'], 'ranking': ordered}


def declare_run(out, dev_ids, holdout_ids):
    cohorts = {'dev-'+str(step): list(dev_ids) for step in (0,128,256,512,1024)}
    cohorts.update({'holdout-base': list(holdout_ids), 'holdout-selected': list(holdout_ids)})
    save(Path(out)/'planned-outcomes.json', {'cohorts': cohorts,
        'planned': sum(len(ids) for ids in cohorts.values())})


def finalize_run_ledger(out):
    """File-only full denominator recovery, also callable after owned hard stop."""
    out = Path(out)
    plan = read(out/'planned-outcomes.json')
    progress = read(out/'progress.json') if (out/'progress.json').exists() else {}
    cohorts, notes = {}, []
    for name, ids in plan['cohorts'].items():
        found = {}
        raw = out/name
        if (raw/'seal.json').exists():
            seal = read(raw/'seal.json')
            if sha(raw/'raw.json') != seal['raw_sha256']:
                raise ValueError('outcome ledger raw seal mismatch')
            found = {row['case_id']: row for row in read(raw/'raw.json')['rows']}
        journal = out/(name+'.journal.jsonl')
        if journal.exists():
            with journal.open(encoding='utf-8') as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        if row['case_id'] not in found:
                            found[row['case_id']] = row
                    except (ValueError, KeyError):
                        notes.append({'cohort':name, 'journal_partial_or_invalid':True, 'sha256':sha(journal)})
        attempted = progress.get('attempted_case') if progress.get('cohort') == name else None
        rows = []
        for case_id in ids:
            if case_id in found:
                rows.append(found[case_id])
            elif attempted == case_id:
                rows.append({'case_id':case_id, 'status':'error', 'text':'',
                    'actual_call_status':'unknown_after_local_failure', 'reason':'prepared case has no durable outcome'})
            else:
                rows.append({'case_id':case_id, 'status':'not_run', 'text':'', 'reason':'no retained attempted outcome'})
        cohorts[name] = rows
    save(out/'outcome-ledger.json', {'schema':'chess.fact-sft.full-outcomes.v1', 'planned':plan['planned'],
        'cohorts':cohorts, 'recovery_notes':notes,
        'limits':'File-only accounting; not_run/unknown outcomes do not complete missing experiments or permit selection.'})
