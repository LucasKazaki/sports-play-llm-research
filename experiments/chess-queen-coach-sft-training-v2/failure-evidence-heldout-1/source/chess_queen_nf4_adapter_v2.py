"""Separate native Queen NF4 candidate and frozen tiny kernel diagnostic.

Only the root GPU owner executes diagnostics or models. Import/contract checks
never import Torch or bitsandbytes. Existing BF16 source and receipts stay intact.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
import math
from pathlib import Path
import sys
import time

import chess_queen_adapter as base
from chess_queen_materialize import materialize_pinned_module

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'experiments/chess-queen-nf4-v1/kernel-protocol-v2.json'
CANDIDATE = 'queen-pawn-8/native-nf4-v2'
QUANTIZATION = {'load_in_4bit': True, 'bnb_4bit_quant_type': 'nf4',
    'bnb_4bit_use_double_quant': True, 'bnb_4bit_compute_dtype': 'bfloat16',
    'bnb_4bit_quant_storage': 'uint8', 'llm_int8_skip_modules': ['lm_head']}


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def binding(item):
    path = ROOT / item['path']
    if base.digest(path) != item['sha256']:
        raise ValueError('Pinned file changed: ' + item['path'])
    return path


def verify_protocol(path):
    plan = base.read_json(path)
    if plan['schema'] != 'chess.queen-nf4-kernel.v1' or plan['implementation_sha256'] != base.digest(Path(__file__)):
        raise ValueError('Frozen NF4 protocol/source changed')
    for item in plan['dependencies']:
        binding(item)
    for name, version in plan['runtime_versions'].items():
        if metadata.version(name) != version:
            raise ValueError('Pinned runtime changed: ' + name)
    if '.'.join(str(x) for x in sys.version_info[:3]) != plan['python_version']:
        raise ValueError('Pinned Python runtime changed')
    if dict(plan['quantization']) != QUANTIZATION:
        raise ValueError('NF4 configuration differs from the frozen candidate')
    return plan


def verify_package(plan):
    """Validate retained wheel provenance and installed bytes before importing it."""
    binding(plan['package']['wheel'])
    installation = base.read_json(binding(plan['package']['installation_receipt']))
    distribution = metadata.distribution('bitsandbytes')
    root = Path(distribution.locate_file('')).resolve()
    for item in installation['verified_wheel_files']:
        path = Path(distribution.locate_file(item['path'])).resolve()
        if not path.is_relative_to(root) or base.digest(path) != item['sha256']:
            raise ValueError('Installed bitsandbytes file changed: ' + item['path'])


def relative_error(actual, reference):
    if len(actual) != len(reference) or not actual:
        raise ValueError('Comparison shape/length differs')
    if not all(math.isfinite(x) for x in [*actual, *reference]):
        raise ValueError('Nonfinite diagnostic values')
    norm = math.sqrt(sum(x*x for x in reference))
    if norm == 0:
        raise ValueError('Reference norm must be nonzero')
    return {'max_absolute_error': max(abs(a-b) for a, b in zip(actual, reference)),
            'relative_l2_error': math.sqrt(sum((a-b)**2 for a, b in zip(actual, reference))) / norm}


def passes(metrics, limits):
    return all(type(metrics.get(name)) in (int, float) and math.isfinite(metrics[name])
               and metrics[name] <= limit for name, limit in limits.items())


def guard_for(plan, out):
    from chess_native_resources import windows_sample, reasons, Policy
    policy = Policy(**plan['resources'])
    last, first, samples = -float('inf'), True, []
    def guard(force=False):
        nonlocal last, first
        if out.with_suffix('.CANCEL').exists():
            raise RuntimeError('Owned NF4 cancellation')
        now = time.monotonic()
        if not force and now-last < 1:
            return
        sample = windows_sample(); samples.append(asdict(sample)); last = now
        with out.with_suffix('.resources.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(asdict(sample)) + '\n'); stream.flush()
        issues = reasons(sample, policy, 'start' if first else 'running'); first = False
        if issues:
            raise RuntimeError('Resource reserve: ' + ','.join(issues))
    return guard, samples, policy


def diagnostic(protocol, out):
    """One tiny NF4 forward/input-backward vs the same dequantized weights."""
    if out.exists():
        raise ValueError('Diagnostic attempt is create-only')
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {'schema': 'chess.queen-nf4-kernel-result.v1', 'status': 'attempt_started',
        'phase': 'before_backend_import', 'started_at': datetime.now(timezone.utc).isoformat(),
        'protocol_sha256': base.digest(protocol), 'source_sha256': base.digest(Path(__file__)),
        'kind': 'Synthetic software diagnostic; no pretrained model or chess capability measurement',
        'pretrained_model_calls': 0}
    save(out, result)
    started = time.monotonic()
    samples = []
    try:
        plan = verify_protocol(protocol); verify_package(plan)
        result.update(publisher_model_id=base.MODEL_ID, publisher_model_revision=base.MODEL_REVISION,
                      publisher_asset_manifest_sha256=base.digest(base.MANIFEST),
                      publisher_source_manifest_sha256=base.digest(base.SOURCE_MANIFEST),
                      wheel_sha256=plan['package']['wheel']['sha256'], frozen_tolerances=plan['tolerances'],
                      runtime_versions=plan['runtime_versions'], quantization=QUANTIZATION)
        guard, samples, policy = guard_for(plan, out); guard()
        result.update(phase='backend_import_started', resource_policy=asdict(policy)); save(out, result)
        import torch
        import bitsandbytes as bnb
        torch.set_num_threads(4)
        capability = list(torch.cuda.get_device_capability(0))
        device_name = torch.cuda.get_device_name(0)
        if capability != plan['device']['compute_capability'] or plan['device']['name_contains'] not in device_name or torch.version.cuda != plan['device']['torch_cuda']:
            raise ValueError('Actual GPU differs from the frozen diagnostic')
        result.update(device_name=device_name, compute_capability=capability, torch_cuda=torch.version.cuda)
        shape = plan['fixture']; random = torch.Generator(device='cpu').manual_seed(shape['seed'])
        weight = torch.randn(shape['output_width'], shape['input_width'], generator=random) / math.sqrt(shape['input_width'])
        host_x = torch.randn(shape['batch_size'], shape['input_width'], generator=random)
        host_probe = torch.randn(shape['batch_size'], shape['output_width'], generator=random)
        layer = bnb.nn.Linear4bit(shape['input_width'], shape['output_width'], bias=False,
            compute_dtype=torch.bfloat16, compress_statistics=True, quant_type='nf4', quant_storage=torch.uint8)
        layer.weight = bnb.nn.Params4bit(weight, requires_grad=False, compress_statistics=True,
                                        quant_type='nf4', quant_storage=torch.uint8)
        result['phase'] = 'quantization_started'; save(out, result); guard()
        layer = layer.to('cuda:0')
        if layer.weight.dtype != torch.uint8 or layer.weight.quant_state is None or not layer.weight.quant_state.nested:
            raise ValueError('Actual NF4/double-quantized storage contract failed')
        x = host_x.to(device='cuda:0', dtype=torch.bfloat16).requires_grad_(True)
        probe = host_probe.to(device='cuda:0', dtype=torch.bfloat16)
        reference_x = x.detach().clone().requires_grad_(True)
        with base.precision_context(torch, 'math_sdpa_fp32_reduction'):
            result['phase'] = 'forward_started'; save(out, result); guard()
            actual = layer(x)
            dequantized = bnb.functional.dequantize_4bit(layer.weight.data, layer.weight.quant_state).to(torch.bfloat16)
            reference = torch.nn.functional.linear(reference_x, dequantized)
            if actual.shape != reference.shape or tuple(actual.shape) != (shape['batch_size'], shape['output_width']):
                raise ValueError('Tiny kernel output shape differs')
            result['phase'] = 'backward_started'; save(out, result); guard()
            (actual.float() * probe.float()).mean().backward()
            (reference.float() * probe.float()).mean().backward()
        if x.grad is None or reference_x.grad is None or layer.weight.grad is not None:
            raise ValueError('Expected input gradients and frozen quantized weights')
        metrics = {'forward': relative_error(actual.detach().float().flatten().cpu().tolist(),
                                             reference.detach().float().flatten().cpu().tolist()),
                   'input_backward': relative_error(x.grad.float().flatten().cpu().tolist(),
                                                    reference_x.grad.float().flatten().cpu().tolist())}
        checks = {name: passes(value, plan['tolerances'][name]) for name, value in metrics.items()}
        result.update(status='passed' if all(checks.values()) else 'failed', phase='completed',
            metrics=metrics, checks=checks, all_checks_passed=all(checks.values()),
            quantized_weight_dtype=str(layer.weight.dtype), compute_dtype=str(layer.compute_dtype),
            nested_quantization=bool(layer.weight.quant_state.nested),
            frozen_quantized_weight_requires_grad=bool(layer.weight.requires_grad),
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
        guard(force=True)
    except Exception as error:
        result.update(status='failed', all_checks_passed=False, error=type(error).__name__ + ': ' + str(error))
    finally:
        result.update(resource_samples=samples, elapsed_seconds=time.monotonic()-started)
        save(out, result)
    return result


def require_diagnostic(path, protocol):
    value = base.read_json(path)
    plan = base.read_json(protocol)
    if value.get('schema') != 'chess.queen-nf4-kernel-result.v1' or value.get('status') != 'passed' or value.get('all_checks_passed') is not True:
        raise ValueError('A successful frozen tiny diagnostic is required before pretrained loading')
    if value.get('protocol_sha256') != base.digest(protocol) or value.get('source_sha256') != base.digest(Path(__file__)):
        raise ValueError('Diagnostic protocol/source identity differs')
    if value.get('runtime_versions') != plan['runtime_versions'] or value.get('wheel_sha256') != plan['package']['wheel']['sha256'] or value.get('frozen_tolerances') != plan['tolerances']:
        raise ValueError('Diagnostic runtime/package/tolerances differ')
    if value.get('checks') != {'forward': True, 'input_backward': True} or not all(
            passes(value.get('metrics', {}).get(name, {}), limits) for name, limits in plan['tolerances'].items()):
        raise ValueError('Diagnostic numerical metrics do not satisfy the frozen limits')
    return value


def decoder_inventory(decoder, bnb, torch):
    names = []
    for name, module in decoder.named_modules():
        if isinstance(module, bnb.nn.Linear4bit):
            if not name.startswith('model.layers.') or name.rsplit('.', 1)[-1] not in {
                    'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'}:
                raise ValueError('Unexpected quantized module: ' + name)
            if module.compute_dtype != torch.bfloat16 or module.weight.dtype != torch.uint8:
                raise ValueError('Quantized linear dtype differs')
            if module.weight.quant_state is None or module.weight.quant_state.quant_type != 'nf4' or not module.weight.quant_state.nested:
                raise ValueError('Quantized linear is not nested NF4')
            names.append(name)
    if len(names) != 7 * decoder.config.num_hidden_layers or decoder.config.num_hidden_layers != 36:
        raise ValueError('Expected all252 decoder attention/MLP linears to be quantized')
    embedding, output = decoder.get_input_embeddings().weight, decoder.get_output_embeddings().weight
    if tuple(embedding.shape) != (128333, 2048) or embedding.dtype != torch.bfloat16 or output.dtype != torch.bfloat16:
        raise ValueError('Full vocabulary BF16 embedding/lm_head must be preserved')
    if embedding.data_ptr() != output.data_ptr() or next(decoder.parameters()).dtype != torch.bfloat16:
        raise ValueError('Expected tied vocabulary and BF16 generation conditioning dtype')
    for tensor in [*decoder.parameters(), *decoder.buffers()]:
        if tensor.device.type != 'cuda' or tensor.device.index != 0:
            raise ValueError('Decoder tensor offloaded outside cuda:0')
    if any(parameter.requires_grad for parameter in decoder.parameters()):
        raise ValueError('Quantized candidate decoder must remain frozen')
    # Transformers5 may consume an explicit device_map without retaining this
    # optional attribute. Registered tensor placement above stays mandatory.
    device_map = getattr(decoder, 'hf_device_map', None)
    if device_map is not None:
        if not isinstance(device_map, dict) or any(value not in (0, 'cuda:0') for value in device_map.values()):
            raise ValueError('CPU/disk/automatic offload is forbidden')
    return {'linear4bit_count': len(names), 'linear4bit_names': names,
        'full_vocabulary': 128333, 'embedding_lm_head_tied': True,
        'embedding_dtype': str(embedding.dtype),
        'registered_tensor_placement': 'all_cuda0_verified',
        'hf_device_map_status': 'present' if device_map is not None else 'absent',
        'hf_device_map': dict(device_map) if device_map is not None else None}


class NativeQueenNF4(base.NativeQueen):
    def __init__(self, protocol=PROTOCOL, diagnostic_receipt=None, model_dir=base.DEFAULT_ASSETS,
                 source_root=None, guard=lambda: None):
        super().__init__(model_dir, source_root, 'cuda', guard)
        self.protocol = Path(protocol)
        self.diagnostic_receipt = Path(diagnostic_receipt) if diagnostic_receipt else None
        self.inventory = None
        self.backend_failure = None

    def load(self):
        if self.model is not None:
            return
        plan = verify_protocol(self.protocol)
        if self.diagnostic_receipt is None:
            raise ValueError('Supply the root-owned successful tiny diagnostic receipt')
        require_diagnostic(self.diagnostic_receipt, self.protocol); verify_package(plan)
        source_root, self.assets, self.source = base.verify_assets(self.model_dir, self.source_root)
        self.guard()
        import torch
        import bitsandbytes as bnb
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self.torch = torch; torch.set_num_threads(4)
        modules = base.import_audited_source(source_root)
        settings = {**QUANTIZATION, 'bnb_4bit_compute_dtype': torch.bfloat16,
                    'bnb_4bit_quant_storage': torch.uint8}
        decoder = AutoModelForCausalLM.from_pretrained(self.model_dir, local_files_only=True,
            trust_remote_code=False, use_safetensors=True, dtype=torch.bfloat16, device_map={'': 0},
            attn_implementation='sdpa', quantization_config=BitsAndBytesConfig(**settings))
        if decoder.config.model_type != 'smollm3' or decoder.config.vocab_size != 128333:
            raise ValueError('Unexpected Queen decoder contract')
        decoder.eval().requires_grad_(False)
        inventory = decoder_inventory(decoder, bnb, torch)
        self.guard()
        bridges = materialize_pinned_module(torch,
            lambda: torch.nn.ModuleList([modules['models.flamingo'].DenseXAttn(1024, 2048) for _ in range(16)]),
            self.model_dir / 'xattn.pt', 'cuda:0', torch.bfloat16)
        encoder_module = modules['models.encoder']
        config = encoder_module.Lc0Bt4HFConfig.from_pretrained(self.model_dir / 'lc0', local_files_only=True)
        encoder = materialize_pinned_module(torch, lambda: encoder_module.Lc0Bt4HFModel(config),
            self.model_dir / 'lc0/model.safetensors', 'cuda:0', torch.bfloat16)
        for component in (bridges, encoder):
            component.eval().requires_grad_(False)
            if any(t.dtype != torch.bfloat16 for t in [*component.parameters(), *component.buffers()] if t.is_floating_point()):
                raise ValueError('Board encoder/bridges must remain BF16')
        if encoder.policy_index_map.dtype != torch.int64:
            raise ValueError('Integer encoder policy mapping changed')
        tokenizer = AutoTokenizer.from_pretrained(self.model_dir, local_files_only=True, trust_remote_code=False)
        if len(tokenizer) != 128333:
            raise ValueError('Tokenizer differs from full Queen vocabulary')
        self.guard()
        self.model, self.encoder, self.bridges, self.tokenizer, self.modules = decoder, encoder, bridges, tokenizer, modules
        self.inventory = inventory

    def generate(self, value, max_new_tokens=1024, maximum_seconds=240, temperature=0., seed=20260823,
                 generation_mode='no_cache', precision_profile='math_sdpa_fp32_reduction'):
        packet, _ = base.input_packet(value)
        if generation_mode != 'no_cache' or precision_profile != 'math_sdpa_fp32_reduction' or temperature != 0:
            raise ValueError('Initial NF4 candidate requires deterministic no-cache/math inference')
        if self.backend_failure is not None:
            record = {'status': 'not_run', 'error': 'not_run_after_backend_failure: ' + self.backend_failure,
                'raw_text': '', 'decoded_text': '', 'generated_tokens': [], 'limitations': [],
                'input': packet, 'prompt': base.prompt_for(packet),
                'input_sha256': hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'model_id': base.MODEL_ID, 'model_revision': base.MODEL_REVISION,
                'source_revision': base.SOURCE_REVISION, 'adapter_sha256': base.digest(Path(base.__file__))}
        else:
            record = super().generate(value, max_new_tokens, maximum_seconds, temperature, seed,
                                      generation_mode, precision_profile)
            if record['status'] == 'failed':
                self.backend_failure = record.get('error', 'failed_backend')
        record['base_adapter_sha256'] = record.get('adapter_sha256')
        record['adapter_sha256'] = base.digest(Path(__file__))
        record['schema'] = 'chess.queen-native-nf4-candidate.v2'
        record['candidate_id'] = CANDIDATE
        record['quantization'] = {'requested': QUANTIZATION, 'actual_decoder_inventory': self.inventory,
            'status': 'loaded_and_verified' if self.inventory is not None else 'not_loaded',
            'origin': 'Local separately versioned NF4 decoder override; not a publisher-provided quantized release',
            'encoder_and_bridges': 'Frozen BF16; no quantization override',
            'bitsandbytes_version': metadata.version('bitsandbytes')}
        record['nf4_protocol_sha256'] = base.digest(self.protocol) if self.protocol.is_file() else None
        record['diagnostic_receipt_sha256'] = base.digest(self.diagnostic_receipt) if self.diagnostic_receipt and self.diagnostic_receipt.is_file() else None
        record['limitations'].append('NF4 changes decoder weights in memory; BF16 equivalence, playing strength and coaching quality remain unestablished.')
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=PROTOCOL)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--diagnostic-receipt', type=Path)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('NF4 attempt receipt is create-only')
    if args.diagnostic:
        result = diagnostic(args.protocol, args.out)
    else:
        if not args.input or not args.diagnostic_receipt:
            parser.error('Generation requires --input and a successful --diagnostic-receipt')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        result = {'status': 'attempt_started', 'phase': 'before_model_setup',
            'protocol_sha256': base.digest(args.protocol), 'source_sha256': base.digest(Path(__file__))}
        save(args.out, result)
        try:
            plan = verify_protocol(args.protocol)
            guard, samples, policy = guard_for(plan, args.out)
            result = NativeQueenNF4(args.protocol, args.diagnostic_receipt, guard=guard).generate(base.read_json(args.input))
            result.update(resource_samples=samples, resource_policy=asdict(policy))
        except Exception as error:
            result.update(status='failed', error=type(error).__name__ + ': ' + str(error))
        save(args.out, result)
    print(json.dumps({'status': result['status'], 'out': str(args.out), 'phase': result.get('phase')}))
    raise SystemExit(0 if result['status'] in ('passed', 'completed', 'terminal') else 2)


if __name__ == '__main__':
    main()
