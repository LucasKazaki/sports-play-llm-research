"""CPU contracts only. No bitsandbytes import, GPU or pretrained model call."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_queen_nf4_adapter_v2 as candidate

FEN = '6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'


def test_import_has_no_torch_bnb_model_or_gpu_side_effect():
    code = "import sys;sys.path.insert(0,'scripts');import chess_queen_nf4_adapter_v2;print('torch' in sys.modules,'bitsandbytes' in sys.modules)"
    value = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert value.stdout.strip() == 'False False'


def test_nf4_spec_preserves_bfloat_compute_double_quant_and_unquantized_output_head():
    assert candidate.QUANTIZATION == {'load_in_4bit': True, 'bnb_4bit_quant_type': 'nf4',
        'bnb_4bit_use_double_quant': True, 'bnb_4bit_compute_dtype': 'bfloat16',
        'bnb_4bit_quant_storage': 'uint8', 'llm_int8_skip_modules': ['lm_head']}


@pytest.mark.parametrize('field', ['reference_pv', 'post_fen', 'gives_check', 'solution'])
def test_forward_or_answer_fields_are_rejected_before_any_model_load(field, monkeypatch):
    model = candidate.NativeQueenNF4()
    calls = []
    monkeypatch.setattr(model, 'load', lambda: calls.append(True))
    with pytest.raises(ValueError):
        model.generate({'fen': FEN, field: 'forbidden'})
    assert not calls


@pytest.mark.parametrize('override', [{'generation_mode': 'cached'}, {'precision_profile': 'default_sdpa'}, {'temperature': .6}])
def test_initial_nf4_mode_is_explicit_and_does_not_silently_override_requested_modes(override):
    with pytest.raises(ValueError, match='requires deterministic'):
        candidate.NativeQueenNF4().generate({'fen': FEN}, **override)


def test_provenance_identifies_actual_override_and_first_backend_failure_stops_retries(monkeypatch):
    calls = []
    def failed(self, *args):
        calls.append(True)
        return {'status': 'failed', 'error': 'fixture backend failure', 'adapter_sha256': 'bf16-actual-source',
                'raw_text': 'partial fixture', 'limitations': []}
    monkeypatch.setattr(candidate.base.NativeQueen, 'generate', failed)
    model = candidate.NativeQueenNF4()
    first = model.generate({'fen': FEN})
    assert first['schema'] == 'chess.queen-native-nf4-candidate.v2'
    assert first['base_adapter_sha256'] == 'bf16-actual-source'
    assert first['adapter_sha256'] == candidate.base.digest(Path(candidate.__file__))
    assert first['quantization']['status'] == 'not_loaded'
    assert first['raw_text'] == 'partial fixture'
    second = model.generate({'fen': FEN})
    assert len(calls) == 1 and second['status'] == 'not_run'
    assert second['generated_tokens'] == [] and second['input']['fen'] == FEN


def test_quantized_numerical_comparison_uses_dequantized_reference_and_finite_relative_error():
    metrics = candidate.relative_error([1., 2.], [1., 2.])
    assert metrics == {'max_absolute_error': 0, 'relative_l2_error': 0}
    assert candidate.passes(metrics, {'max_absolute_error': .0625, 'relative_l2_error': .02})
    assert not candidate.passes({'max_absolute_error': .0626, 'relative_l2_error': 0},
                                {'max_absolute_error': .0625, 'relative_l2_error': .02})
    assert not candidate.passes({'max_absolute_error': float('nan')}, {'max_absolute_error': 1})
    for left, right in (([1], []), ([1], [0]), ([float('inf')], [1])):
        with pytest.raises(ValueError):
            candidate.relative_error(left, right)


def diagnostic_fixture(tmp_path):
    protocol = tmp_path / 'protocol.json'
    limits = {'forward': {'max_absolute_error': .0625, 'relative_l2_error': .02},
              'input_backward': {'max_absolute_error': .03125, 'relative_l2_error': .02}}
    plan = {'runtime_versions': {'bitsandbytes': '0.50.2'}, 'package': {'wheel': {'sha256': 'pinned-wheel'}}, 'tolerances': limits}
    protocol.write_text(json.dumps(plan))
    record = {'schema': 'chess.queen-nf4-kernel-result.v1', 'status': 'passed', 'all_checks_passed': True,
        'protocol_sha256': candidate.base.digest(protocol), 'source_sha256': candidate.base.digest(Path(candidate.__file__)),
        'runtime_versions': plan['runtime_versions'], 'wheel_sha256': 'pinned-wheel', 'frozen_tolerances': limits,
        'checks': {'forward': True, 'input_backward': True},
        'metrics': {name: {'max_absolute_error': 0, 'relative_l2_error': 0} for name in limits}}
    path = tmp_path / 'software-fixture-only.json'; path.write_text(json.dumps(record))
    return protocol, path, record


@pytest.mark.parametrize('defect', ['failed', 'stale_source', 'wrong_runtime', 'bad_metric', 'missing_backward'])
def test_pretrained_gate_requires_source_runtime_and_actual_numerical_fields(tmp_path, defect):
    protocol, receipt, record = diagnostic_fixture(tmp_path)
    candidate.require_diagnostic(receipt, protocol)
    if defect == 'failed': record['status'] = 'failed'
    if defect == 'stale_source': record['source_sha256'] = 'different'
    if defect == 'wrong_runtime': record['runtime_versions'] = {}
    if defect == 'bad_metric': record['metrics']['forward']['relative_l2_error'] = .021
    if defect == 'missing_backward': record['metrics'].pop('input_backward')
    receipt.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        candidate.require_diagnostic(receipt, protocol)


class Tensor:
    def __init__(self, dtype='bf16', pointer=17, device='cuda', requires_grad=False):
        self.dtype = dtype; self.shape = (128333, 2048); self.pointer = pointer
        self.device = NS(type=device, index=0); self.requires_grad = requires_grad
    def data_ptr(self): return self.pointer


class FourBit:
    def __init__(self):
        self.compute_dtype = 'bf16'; self.weight = Tensor('uint8')
        self.weight.quant_state = NS(quant_type='nf4', nested=True)


def decoder_fixture():
    embedding = Tensor()
    suffixes = ('q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj')
    modules = [(f'model.layers.{index}.{name}', FourBit()) for index in range(36) for name in suffixes]
    model = NS(config=NS(num_hidden_layers=36), hf_device_map={'': 0},
        named_modules=lambda: iter(modules), get_input_embeddings=lambda: NS(weight=embedding),
        get_output_embeddings=lambda: NS(weight=embedding),
        parameters=lambda: iter([embedding] + [module.weight for _, module in modules]), buffers=lambda: iter([]))
    return model, modules, embedding


def test_actual_inventory_requires_all252_nf4_decoder_linears_full_tied_vocab_and_cuda0():
    model, modules, embedding = decoder_fixture()
    result = candidate.decoder_inventory(model, NS(nn=NS(Linear4bit=FourBit)), NS(bfloat16='bf16', uint8='uint8'))
    assert result['linear4bit_count'] == 252 and result['full_vocabulary'] == 128333
    assert result['embedding_lm_head_tied']


@pytest.mark.parametrize('map_state', ['absent_attribute', 'none'])
def test_transformers5_optional_device_map_absence_requires_actual_cuda0_tensors(map_state):
    model, modules, embedding = decoder_fixture()
    if map_state == 'absent_attribute': del model.hf_device_map
    else: model.hf_device_map = None
    result = candidate.decoder_inventory(model, NS(nn=NS(Linear4bit=FourBit)), NS(bfloat16='bf16', uint8='uint8'))
    assert result['hf_device_map_status'] == 'absent' and result['hf_device_map'] is None
    assert result['registered_tensor_placement'] == 'all_cuda0_verified'
    embedding.device = NS(type='cpu', index=None)
    with pytest.raises(ValueError, match='outside cuda:0'):
        candidate.decoder_inventory(model, NS(nn=NS(Linear4bit=FourBit)), NS(bfloat16='bf16', uint8='uint8'))


@pytest.mark.parametrize('device', [NS(type='cuda', index=1), NS(type='meta', index=None), NS(type='cpu', index=None)])
def test_actual_tensor_placement_overrides_even_claimed_cuda0_metadata(device):
    model, modules, embedding = decoder_fixture(); modules[0][1].weight.device = device
    with pytest.raises(ValueError, match='outside cuda:0'):
        candidate.decoder_inventory(model, NS(nn=NS(Linear4bit=FourBit)), NS(bfloat16='bf16', uint8='uint8'))


def test_malformed_present_device_map_cannot_be_accepted_as_absent():
    model, modules, embedding = decoder_fixture(); model.hf_device_map = ['cuda:0']
    with pytest.raises(ValueError, match='offload is forbidden'):
        candidate.decoder_inventory(model, NS(nn=NS(Linear4bit=FourBit)), NS(bfloat16='bf16', uint8='uint8'))


@pytest.mark.parametrize('defect', ['missing', 'non_nested', 'wrong_quant_type', 'offload', 'untied', 'trainable'])
def test_inventory_rejects_partial_quantization_or_altered_placement_and_weights(defect):
    model, modules, embedding = decoder_fixture()
    if defect == 'missing': modules.pop()
    if defect == 'non_nested': modules[0][1].weight.quant_state.nested = False
    if defect == 'wrong_quant_type': modules[0][1].weight.quant_state.quant_type = 'fp4'
    if defect == 'offload': model.hf_device_map = {'': 'cpu'}
    if defect == 'untied': model.get_output_embeddings = lambda: NS(weight=Tensor(pointer=18))
    if defect == 'trainable': embedding.requires_grad = True
    with pytest.raises(ValueError):
        candidate.decoder_inventory(model, NS(nn=NS(Linear4bit=FourBit)), NS(bfloat16='bf16', uint8='uint8'))
