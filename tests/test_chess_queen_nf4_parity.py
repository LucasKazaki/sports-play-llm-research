"""Pure CPU contracts for the separately frozen same-NF4 parity verdict."""
import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('nf4_parity_fixture', ROOT / 'experiments/chess-queen-nf4-v1/parity_no_cache.py')
parity = importlib.util.module_from_spec(spec); spec.loader.exec_module(parity)
LIMITS = {'max_absolute_error': .01, 'mean_absolute_error': .001, 'minimum_cosine_similarity': .9999}


def comparisons():
    metrics = {'finite': True, 'top1_equal': True, 'max_absolute_error': 0.,
               'mean_absolute_error': 0., 'cosine_similarity': 1.}
    return [{'kind': name, **{scope: copy.deepcopy(metrics) for scope in
        ('all_logits', 'original_vocab_logits', 'added_vocab_logits')}}
        for name in ('base_prompt', 'synthetic_vocabulary_suffix')]


@pytest.mark.parametrize('defect', ['missing_suffix', 'missing_added_vocab', 'wrong_top1', 'nonfinite', 'max_error', 'mean_error', 'similarity'])
def test_both_prompts_and_all_vocabulary_ranges_are_required(defect):
    rows = comparisons(); assert parity.verdict(rows, LIMITS)
    if defect == 'missing_suffix': rows.pop()
    if defect == 'missing_added_vocab': rows[0].pop('added_vocab_logits')
    if defect == 'wrong_top1': rows[0]['all_logits']['top1_equal'] = False
    if defect == 'nonfinite': rows[0]['original_vocab_logits']['max_absolute_error'] = float('nan')
    if defect == 'max_error': rows[1]['all_logits']['max_absolute_error'] = .011
    if defect == 'mean_error': rows[1]['added_vocab_logits']['mean_absolute_error'] = .0011
    if defect == 'similarity': rows[1]['added_vocab_logits']['cosine_similarity'] = .9998
    assert not parity.verdict(rows, LIMITS)


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_nonfinite_logits_stop_before_metrics_and_leave_serializable_failure(bad, tmp_path):
    result = {'status': 'attempt_started', 'comparisons': [], 'forward_attempts': ['native']}
    def never_compare(*args):
        pytest.fail('No metric computation may follow nonfinite logits')
    with pytest.raises(ValueError, match='Nonfinite logits') as error:
        parity.append_comparison(result, 'base_prompt', 1, [1.], [bad],
            lambda values: all(math.isfinite(value) for value in values), never_compare)
    result.update(status='failed', error=str(error.value))
    out = tmp_path / 'failure.json'; parity.nf4.save(out, result)
    saved = json.loads(out.read_text())
    assert saved['status'] == 'failed' and saved['comparisons'] == []
    assert saved['nonfinite_logits'] == {'kind': 'base_prompt', 'stage': 'native_no_cache', 'finite': False}


def test_nonfinite_derived_metric_never_enters_receipt(tmp_path):
    result = {'status': 'attempt_started', 'comparisons': []}
    with pytest.raises(ValueError, match='Nonfinite comparison metric') as error:
        parity.append_comparison(result, 'base_prompt', 1, [1.], [1.], lambda value: True,
            lambda left, right: {'cosine_similarity': float('nan')})
    result.update(status='failed', error=str(error.value))
    out = tmp_path / 'metric-failure.json'; parity.nf4.save(out, result)
    assert json.loads(out.read_text())['nonfinite_comparison']['kind'] == 'base_prompt'


def test_nonfinite_manual_output_stops_before_native_call():
    result = {'status': 'attempt_started', 'comparisons': []}; calls = ['manual']
    with pytest.raises(ValueError, match='Nonfinite logits'):
        parity.require_finite_logits(result, 'base_prompt', 'upstream_manual', [float('nan')],
            lambda values: all(math.isfinite(value) for value in values))
        calls.append('native')
    assert calls == ['manual'] and result['nonfinite_logits']['stage'] == 'upstream_manual'
    json.dumps(result, allow_nan=False)
