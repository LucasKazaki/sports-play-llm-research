"""Root-only same-NF4 native/canonical numerical preflight; no chess evaluation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_queen_nf4_adapter as nf4

FIXTURE = {'fen': '6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'}
SUFFIX = '<SQUARE_1><PIECE_MP><EMPTY>'


def verdict(rows, thresholds):
    if [row.get('kind') for row in rows] != ['base_prompt', 'synthetic_vocabulary_suffix']:
        return False
    for row in rows:
        for scope in ('all_logits', 'original_vocab_logits', 'added_vocab_logits'):
            value = row.get(scope, {})
            if value.get('finite') is not True or value.get('top1_equal') is not True:
                return False
            if not nf4.passes(value, {'max_absolute_error': thresholds['max_absolute_error'],
                                      'mean_absolute_error': thresholds['mean_absolute_error']}):
                return False
            similarity = value.get('cosine_similarity')
            if type(similarity) not in (int, float) or not nf4.math.isfinite(similarity) or similarity < thresholds['minimum_cosine_similarity']:
                return False
    return True


def verify_plan(protocol, diagnostic_receipt):
    """Metadata-only gates; this does not import a model backend."""
    plan = nf4.base.read_json(protocol)
    if plan['implementation_sha256'] != nf4.base.digest(Path(__file__)) or plan['fixture'] != FIXTURE or plan['suffix'] != SUFFIX:
        raise ValueError('Frozen parity source/input differs')
    for item in plan['dependencies']:
        nf4.binding(item)
    if diagnostic_receipt.resolve() != nf4.binding(plan['diagnostic_receipt']).resolve():
        raise ValueError('Use the exact successful root-owned diagnostic receipt')
    worker = nf4.base.read_json(nf4.binding(plan['diagnostic_worker_receipt']))
    if worker.get('status') != 'completed' or worker.get('exit_code') != 0 or worker.get('child_exited_before_lease_release') is not True:
        raise ValueError('Tiny diagnostic worker did not close successfully')
    kernel_path = nf4.binding(plan['kernel_protocol'])
    kernel_plan = nf4.verify_protocol(kernel_path)
    nf4.require_diagnostic(diagnostic_receipt, kernel_path)
    return plan, kernel_path, kernel_plan


def require_finite_logits(result, kind, stage, value, finite_check):
    """Run immediately after each forward, before any subsequent forward."""
    if not bool(finite_check(value)):
        result['nonfinite_logits'] = {'kind': kind, 'stage': stage, 'finite': False}
        raise ValueError('Nonfinite logits; stop subsequent preflight calls')


def append_comparison(result, kind, count, expected, actual, finite_check, compare):
    """Reject nonfinite tensors/metrics before changing the durable JSON rows."""
    require_finite_logits(result, kind, 'upstream_manual', expected, finite_check)
    require_finite_logits(result, kind, 'native_no_cache', actual, finite_check)
    row = {'kind': kind, 'prefix_token_count': count, 'all_logits': compare(expected, actual),
        'original_vocab_logits': compare(expected[:nf4.base.FROZEN_VOCAB], actual[:nf4.base.FROZEN_VOCAB]),
        'added_vocab_logits': compare(expected[nf4.base.FROZEN_VOCAB:], actual[nf4.base.FROZEN_VOCAB:])}
    try:
        json.dumps(row, allow_nan=False)
    except ValueError:
        result['nonfinite_comparison'] = {'kind': kind, 'error': 'Nonfinite derived metric'}
        raise ValueError('Nonfinite comparison metric; stop subsequent preflight calls') from None
    result['comparisons'].append(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=Path(__file__).parent / 'parity-protocol-v2.json')
    parser.add_argument('--diagnostic-receipt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Pretrained preflight is create-only')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = {'schema': 'chess.queen-nf4-no-cache-parity.v1', 'status': 'attempt_started',
        'phase': 'before_model_setup', 'protocol_sha256': nf4.base.digest(args.protocol),
        'source_sha256': nf4.base.digest(Path(__file__)), 'fixture': FIXTURE, 'synthetic_suffix': SUFFIX,
        'kind': 'Authored numerical software fixture. Synthetic token suffix is not a chess task response.',
        'forward_attempts': [], 'comparisons': [], 'resource_samples': []}
    nf4.save(args.out, result)
    samples = []
    try:
        plan, kernel_path, kernel_plan = verify_plan(args.protocol, args.diagnostic_receipt)
        guard, samples, policy = nf4.guard_for(kernel_plan, args.out)
        model = nf4.NativeQueenNF4(kernel_path, args.diagnostic_receipt, guard=guard)
        model.load()
        result.update(quantized_decoder_inventory=model.inventory, thresholds=plan['thresholds'],
                      kernel_protocol_sha256=nf4.base.digest(kernel_path),
                      diagnostic_receipt_sha256=nf4.base.digest(args.diagnostic_receipt), resource_policy=asdict(policy))
        import torch
        from accelerate import init_empty_weights
        packet, _ = nf4.base.input_packet(FIXTURE)
        prompt = model.tokenizer.apply_chat_template([{'role': 'user', 'content': nf4.base.prompt_for(packet)}],
            tokenize=True, add_generation_prompt=True, enable_thinking=False, return_dict=False)
        suffix_ids = model.tokenizer.encode(SUFFIX, add_special_tokens=False)
        if len(suffix_ids) != 3 or any(token < nf4.base.FROZEN_VOCAB for token in suffix_ids):
            raise ValueError('Synthetic suffix did not exercise added Queen vocabulary')
        result['synthetic_suffix_ids'] = suffix_ids
        with init_empty_weights():
            manual = model.modules['models.flamingo'].FlamingoChessLM(model.model,
                model.modules['models.adapters.smollm'].SmolLM3Adapter(model.model), n_new_tokens=0, lora_rank=-1)
        manual.x_attn_layers = model.bridges; manual.eval()
        def compare(left, right):
            delta = (left-right).abs()
            return {'max_absolute_error': float(delta.max()), 'mean_absolute_error': float(delta.mean()),
                'cosine_similarity': float(torch.nn.functional.cosine_similarity(left, right, dim=0)),
                'top1_equal': int(left.argmax()) == int(right.argmax()),
                'left_top1': int(left.argmax()), 'right_top1': int(right.argmax()),
                'finite': bool(torch.isfinite(left).all() and torch.isfinite(right).all())}
        with torch.inference_mode(), nf4.base.precision_context(torch, 'math_sdpa_fp32_reduction'):
            result['phase'] = 'encoder_forward_started'; nf4.save(args.out, result); guard()
            planes = model.modules['utils.lc0_planes'].encode_fen_batch([packet['fen']], [[]]).to('cuda:0')
            encoded = model.modules['utils.utils'].encode_planes(model.encoder, planes, torch.bfloat16, pov=True)
            if tuple(encoded.shape) != (1,16,64,1024) or not torch.isfinite(encoded).all():
                raise ValueError('Board conditioning contract differs')
            for kind, tokens in (('base_prompt', prompt), ('synthetic_vocabulary_suffix', prompt + suffix_ids)):
                ids = torch.tensor([tokens], dtype=torch.long, device='cuda:0')
                guard(); result['forward_attempts'].append(kind + ':upstream_manual'); nf4.save(args.out, result)
                hidden = manual._hidden_states(ids, encoded, attention_mask=torch.ones_like(ids))[:, -1:]
                expected = model.model.lm_head(hidden)[0,-1].float()
                if tuple(expected.shape) != (128333,):
                    raise ValueError('Manual comparison must include all128333 raw vocabulary logits')
                require_finite_logits(result, kind, 'upstream_manual', expected, lambda value: torch.isfinite(value).all())
                handles = nf4.base.board_conditioning_hooks(model.model, model.bridges, encoded)
                try:
                    guard(); result['forward_attempts'].append(kind + ':native_no_cache'); nf4.save(args.out, result)
                    actual = model.model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False,
                                         logits_to_keep=1).logits[0,-1].float()
                finally:
                    for handle in handles: handle.remove()
                if tuple(actual.shape) != (128333,):
                    raise ValueError('Native comparison must include all128333 raw vocabulary logits')
                require_finite_logits(result, kind, 'native_no_cache', actual, lambda value: torch.isfinite(value).all())
                append_comparison(result, kind, len(tokens), expected, actual,
                    lambda value: torch.isfinite(value).all(), compare)
                nf4.save(args.out, result)
        guard(force=True)
        result.update(status='passed' if verdict(result['comparisons'], plan['thresholds']) else 'failed', phase='completed',
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
    except Exception as error:
        result.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    finally:
        result.update(resource_samples=samples, elapsed_seconds=time.monotonic()-started)
        nf4.save(args.out, result)
    print(json.dumps({'status': result['status'], 'out': str(args.out)}))
    raise SystemExit(0 if result['status'] == 'passed' else 2)


if __name__ == '__main__': main()
