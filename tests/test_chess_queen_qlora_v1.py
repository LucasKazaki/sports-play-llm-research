"""Pure CPU contract checks; no Torch/PEFT/backend import or model calls."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_queen_qlora_v1 as experiment


def test_import_has_no_backend_or_gpu_side_effects():
    code = "import sys;sys.path.insert(0,'scripts');import chess_queen_qlora_v1;print(any(x in sys.modules for x in ('torch','bitsandbytes','peft')))"
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'False'


def test_authored_target_only_supervises_verified_mate_and_strict_native_moves():
    target = experiment.target_for_fixture()
    parsed = experiment.nf4.base.parse_output(experiment.FIXTURE, target)
    assert parsed['accepted_move_uci'] == 'g5d8' and parsed['description_valid']
    assert parsed['critical_line']['failure'] is None
    assert parsed['critical_line']['legal_prefix_plies'] == 1 and parsed['critical_line']['terminal']
    assert 'gives checkmate' in target and 'does not capture' in target
    assert set(experiment.FIXTURE) == {'fen'}


class Tokenizer:
    def apply_chat_template(self, *args, **kwargs):
        assert kwargs['enable_thinking'] is False and kwargs['add_generation_prompt'] is True
        return [10, 20]
    def convert_tokens_to_ids(self, text):
        assert text == '<|im_end|>'; return 99


def tokens(tokenizer, prompt, response, max_length):
    assert max_length is None
    return [10, 20, 30, 99, 40], [-100, -100, 30, 99, 40]


def test_official_tokenization_masks_exact_complete_prefix_and_supervises_closing():
    ids, labels, length = experiment.tokenize_training(Tokenizer(), 'question', 'answer', tokens)
    assert length == 2 and labels[:2] == [-100, -100] and labels[2:] == ids[2:]


@pytest.mark.parametrize('defect', ['prefix_mismatch', 'unmasked_input', 'lost_closing', 'lost_response', 'too_long', 'different_lengths'])
def test_bad_or_truncated_training_tokenization_is_rejected(defect):
    def bad(*args, **kwargs):
        ids, labels = tokens(*args, **kwargs)
        if defect == 'prefix_mismatch': ids[0] = 11
        if defect == 'unmasked_input': labels[0] = ids[0]
        if defect == 'lost_closing': ids[3] = labels[3] = 50
        if defect == 'lost_response': ids, labels = ids[:2], labels[:2]
        if defect == 'too_long': ids = [10,20]+[30]*510+[99]; labels = [-100,-100]+ids[2:]
        if defect == 'different_lengths': labels.pop()
        return ids, labels
    with pytest.raises(ValueError):
        experiment.tokenize_training(Tokenizer(), 'q', 'a', bad)


def trainables():
    values = []
    for layer in range(36):
        for target in ('q_proj', 'v_proj'):
            for matrix in ('A', 'B'):
                shape = (8,2048) if matrix == 'A' else ((2048,8) if target == 'q_proj' else (512,8))
                values.append((f'model.layers.{layer}.self_attn.{target}.lora_{matrix}.default.weight',
                    NS(requires_grad=True, shape=shape, dtype='fp32', device=NS(type='cuda',index=0))))
    return values


def test_expected_only_qv_fp32_adapter_inventory_and_count():
    values = trainables(); values.append(('model.embed_tokens.weight', NS(requires_grad=False)))
    actual = experiment.trainable_inventory(NS(named_parameters=lambda: iter(values)), 'fp32')
    assert len(actual) == 144 and sum(math.prod(value.shape) for _, value in actual) == 1916928


@pytest.mark.parametrize('defect', ['missing', 'unexpected', 'wrong_dtype', 'wrong_rank', 'wrong_device', 'duplicate'])
def test_trainable_inventory_rejects_weight_drift_or_unintended_trainables(defect):
    values = trainables()
    if defect == 'missing': values.pop()
    if defect == 'unexpected': values.append(('bridge.W_Q.weight', values[0][1]))
    if defect == 'wrong_dtype': values[0][1].dtype = 'bf16'
    if defect == 'wrong_rank': values[0][1].shape = (4,2048)
    if defect == 'wrong_device': values[0][1].device.index = 1
    if defect == 'duplicate': values.append(values[0])
    with pytest.raises(ValueError):
        experiment.trainable_inventory(NS(named_parameters=lambda: iter(values)), 'fp32')


@pytest.mark.parametrize('defect', ['missing_check', 'failed_check', 'nan_loss', 'no_update', 'string_check'])
def test_diagnostic_qualification_requires_all_real_step_checks(defect):
    result = {'loss': 1.5, 'updates_completed': 1, 'checks': {name: True for name in experiment.EXPECTED_CHECKS}}
    assert experiment.qualified(result)
    if defect == 'missing_check': result['checks'].pop('lora_storage_actually_changed')
    if defect == 'failed_check': result['checks']['frozen_storage_exactly_unchanged'] = False
    if defect == 'nan_loss': result['loss'] = float('nan')
    if defect == 'no_update': result['updates_completed'] = 0
    if defect == 'string_check': result['checks']['finite_loss'] = 'true'
    assert not experiment.qualified(result)


def test_setup_failure_preserves_pending_full_update_denominator_and_create_only(tmp_path, monkeypatch):
    protocol = tmp_path / 'protocol.json'; protocol.write_text('{}')
    out = tmp_path / 'result.json'
    def fail(*args): raise ValueError('fixture protocol failure before any model setup')
    monkeypatch.setattr(experiment, 'verify_protocol', fail)
    value = experiment.diagnostic(protocol, out)
    assert value['status'] == 'failed' and value['updates_planned'] == 1 and value['updates_completed'] == 0
    assert value['phases'] == [] and json.loads(out.read_text())['status'] == 'failed'
    with pytest.raises(ValueError, match='create-only'):
        experiment.diagnostic(protocol, out)
