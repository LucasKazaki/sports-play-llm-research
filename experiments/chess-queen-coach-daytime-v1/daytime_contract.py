"""Prospective daytime operating gates; no backend or corpus import."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

CUTOFF = '2026-10-16T22:00:00+00:00'
TRAIN_ADMISSION = '2026-10-16T19:00:00+00:00'
HELD_ADMISSION = '2026-10-16T20:30:00+00:00'
SCIENCE_FIELDS = ('training', 'generation', 'data', 'development_raw_groups', 'warm_start',
    'corpus_manifest', 'cpu_preflight', 'cpu_preflight_source', 'corpus_scientific_protocol',
    'corpus_operational_protocol', 'corpus_operational_closed', 'corpus_operational_provenance',
    'corpus_closed_audit', 'successful_memory_qualification', 'kernel_protocol', 'kernel_receipt',
    'selection_method', 'joint_fact_metric', 'conditional_prediction_metric', 'intervention',
    'expected_formatter', 'expected_tokenizer_bindings', 'resources')
UPDATE_CHECKS = {'effective_original64_equal', 'complete_eight_micros', 'finite_losses',
    'finite_nonzero_gradients', 'exact_fp32_adapter_inventory', 'adapter_changed',
    'frozen_storage_unchanged', 'strict_save_reload_equal', 'disposable_not_candidate'}


def windows(plan, bound, read):
    authority = read(bound(plan['daytime_authority']))
    if (authority.get('schema') != 'chess.daytime.resume-authority.v1'
        or authority.get('human_text') != 'Continue today until 6:00 PM Eastern'
        or authority.get('timezone') != 'America/New_York'
        or authority.get('date') != '2026-10-16' or authority.get('cutoff_utc') != CUTOFF):
        raise ValueError('Exact dated human operating authority required')
    if (plan.get('cutoff_utc') != CUTOFF or plan.get('admission_latest_utc') != TRAIN_ADMISSION
        or plan.get('held_admission_latest_utc') != HELD_ADMISSION):
        raise ValueError('Fixed daytime operating dates differ')
    return authority


def science(plan, previous):
    for key in SCIENCE_FIELDS:
        if plan.get(key) != previous.get(key):
            raise ValueError('Frozen science changed: ' + key)
    if plan['phase_maximum_seconds'] != {'training': 3000, 'heldout': 4500}:
        raise ValueError('Scientific phase caps changed')


def tokenizer(plan, actual):
    if (actual.get('official_formatter_sha256') != plan['expected_formatter']['sha256']
        or actual.get('tokenizer_bindings') != plan['expected_tokenizer_bindings']):
        raise ValueError('Actual CPU tokenizer/formatter identities differ')


def worker(receipt, script, arguments):
    expected = hashlib.sha256(json.dumps(arguments).encode()).hexdigest()
    if (receipt.get('status') != 'completed' or receipt.get('exit_code') != 0
        or str(receipt.get('script')).replace('\\', '/') != script.replace('\\', '/')
        or receipt.get('arguments_sha256') != expected
        or receipt.get('child_exited_before_lease_release') is not True):
        raise ValueError('Exact completed qualification worker required')


def qualifications(plan, bound, read):
    """Machine-enforce both closed actual routes before scientific training."""
    for name in ('update', 'cold'):
        stage = plan['qualification_gates'][name]
        protocol = read(bound(stage['protocol']))
        result = read(bound(stage['result']))
        closed_worker = read(bound(stage['worker']))
        audit = read(bound(stage['audit']))
        if (result.get('status') != 'passed'
            or result.get('protocol_sha256') != stage['protocol']['sha256']
            or audit.get('status') != 'passed'
            or audit.get('protocol_sha256') != stage['protocol']['sha256']
            or audit.get('qualification_sha256') != stage['result']['sha256']
            or audit.get('worker_sha256') != stage['worker']['sha256']):
            raise ValueError('Independent closed same-protocol qualification required: ' + name)
        worker(closed_worker, stage['script'], stage['arguments'])
        if (stage['arguments'] != protocol['expected_worker_arguments']
            or stage['script'] != protocol['expected_worker_script']):
            raise ValueError('Actual qualification dispatch vector differs')
        if name == 'update':
            if (result.get('updates_completed') != 1 or result.get('presentations_completed') != 8
                or result.get('disposable_not_candidate') is not True
                or set(result.get('checks', {})) != UPDATE_CHECKS
                or not all(value is True for value in result['checks'].values())
                or protocol.get('warm_start') != plan['warm_start']
                or protocol.get('counterfactual_runtime') != plan['counterfactual_runtime']
                or protocol.get('maximum_seconds') != 600):
                raise ValueError('Exact disposable warm-training-route qualification required')
        elif (result.get('planned') != 2 or result.get('completed_children') != 2
            or result.get('all_children_closed') is not True
            or result.get('outer_torch_imported') is not False
            or protocol['model_runtime']['warm_start'] != plan['warm_start']
            or protocol['raw_provenance'].get('candidate_id') != 'queen-pawn-8/nf4-coach-counterfactual-v1'
            or protocol['raw_provenance'].get('qualified_runtime_source_sha256') !=
                '7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349'):
            raise ValueError('Exact counterfactual cold route required; old-SFT pass is insufficient')


def admit(plan, now=None):
    now = datetime.now(timezone.utc) if now is None else now
    if now >= datetime.fromisoformat(plan['admission_latest_utc']):
        raise RuntimeError('Daytime training admission closed at19:00UTC')
