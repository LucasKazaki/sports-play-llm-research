"""No-forward runner tests use real development packets and fake local transport only."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_generation_runner as runner


DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
TYPED = ROOT / 'artifacts/chess-typed-position-evidence-v1/dev8-adapter-v1.json'
INPUTS = ROOT / 'artifacts/chess-no-forward-input-v1/dev8-inputs/manifest.json'
SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'
FORBIDDEN = (b'pv_uci', b'pv_final_fen', b'fen_after', b'post_move_fen', b'future_moves',
             b'solution', b'themes', b'answer_label', b'annotations', b'reply_sequence',
             b'future_board_feature', b'score_info_sequence', b'commentary_evidence')


def route(**changes):
    value = {
        'route_id': 'sports-play-llm-local-131k-v1',
        'endpoint': 'http://127.0.0.1:1234/v1',
        'model_id': 'loops-cpu-gpt-oss-20b',
        'context_window_tokens': 131072,
        'reasoning': {'effort': 'medium'},
        'sampling': {'temperature': 0, 'top_p': 1, 'max_output_tokens': 512},
        'seed': 20260923,
        'request_schema': 'openai-chat-completions/v1',
        'timeout_seconds': 30,
        'automatic_retries': 0,
    }
    value.update(changes)
    return value


def attestation(tmp_path, observed):
    path = tmp_path / 'route-attestation.json'
    snapshot = models_snapshot(observed)
    (tmp_path / runner.RUNTIME_SNAPSHOT_NAME).write_bytes(snapshot)
    path.write_bytes(cf.canonical({
        'schema': runner.ATTESTATION_SCHEMA,
        'captured_at': '2026-09-23T08:34:00Z',
        'runtime': runner.runtime_observation_from_models_snapshot(snapshot, observed),
        'route': observed,
    }) + b'\n')
    return path


def models_snapshot(observed):
    return cf.canonical({
        'models': [{
            'key': runner.LOCAL_MODEL_CATALOG_KEY,
            'max_context_length': observed['context_window_tokens'],
            'loaded_instances': [{
                'id': observed['model_id'],
                'config': {
                    'context_length': observed['context_window_tokens'],
                    'parallel': 1,
                },
            }],
            'capabilities': {
                'reasoning': {
                    'allowed_options': ['low', 'medium', 'high'],
                    'default': 'low',
                },
            },
        }],
    })


def frozen(tmp_path, *, declared=None, observed=None):
    declared = route() if declared is None else declared
    observed = copy.deepcopy(declared) if observed is None else observed
    run_dir = tmp_path / 'run'
    manifest = runner.freeze_run(
        DATA, SOURCE, SHA, TYPED, INPUTS, declared, observed,
        attestation(tmp_path, observed), run_dir,
    )
    return run_dir, manifest, declared


def response(route_value, raw='plain raw output'):
    return {'raw_output': raw, 'observed_route': copy.deepcopy(route_value),
            'transport_status': 'completed'}


def test_freeze_binds_eight_real_packets_route_attestation_and_zero_calls(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    assert len(manifest['requests']) == 8
    assert manifest['declared_route'] == manifest['observed_route'] == declared
    assert manifest['commentary_capability_gate_passed'] is False
    assert manifest['model_calls'] == manifest['new_engine_calls'] == manifest['heldout_outcomes_scored'] == 0
    original = json.loads(INPUTS.read_bytes())
    for request, record in zip(manifest['requests'], original['records']):
        raw = (run_dir / request['input_path']).read_bytes()
        assert raw == (ROOT / record['path']).read_bytes()
        assert request['input_sha256'] == cf.digest(raw) == record['sha256']
        assert request['input_bytes'] == len(raw) == record['bytes']
    assert (run_dir / 'route-attestation.json').read_bytes() == attestation_bytes(tmp_path, declared)
    assert (run_dir / runner.RUNTIME_SNAPSHOT_NAME).read_bytes() == models_snapshot(declared)


def attestation_bytes(tmp_path, observed):
    return cf.canonical({
        'schema': runner.ATTESTATION_SCHEMA,
        'captured_at': '2026-09-23T08:34:00Z',
        'runtime': runner.runtime_observation_from_models_snapshot(models_snapshot(observed), observed),
        'route': observed,
    }) + b'\n'


def test_fake_transport_gets_only_canonical_bytes_and_raw_outputs_are_retained(tmp_path, monkeypatch):
    run_dir, manifest, declared = frozen(tmp_path)
    calls = []
    def engine_forbidden(*args, **kwargs):
        raise AssertionError('The generation runner must not start an engine')
    # The runner never imports chess.engine; this protects the surrounding packet path too.
    import chess.engine
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', engine_forbidden)
    def transport(*args):
        assert len(args) == 1 and type(args[0]) is bytes
        for forbidden in FORBIDDEN:
            assert forbidden not in args[0]
        calls.append(args[0])
        return response(declared, 'raw-{} not a scored explanation'.format(len(calls)))
    result = runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir, transport)
    assert len(calls) == 8
    assert result['model_calls'] == 8
    assert result['status_counts'] == {'captured': 8}
    assert [row['raw_classification'] for row in result['outcomes']] == ['malformed_json'] * 8
    for request, sent, outcome in zip(manifest['requests'], calls, result['outcomes']):
        assert sent == (run_dir / request['input_path']).read_bytes()
        assert (run_dir / outcome['raw_path']).read_bytes().startswith(b'raw-')
    assert runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)['integrity_passed'] is True


def test_malformed_abstention_empty_and_transport_failure_are_all_retained_without_retry(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    calls = []
    values = [b'\xff\xfe', '{"status":"abstain","reason":"insufficient evidence"}',
              None, OSError('synthetic local transport failure'), 'ordinary raw text',
              '{"other":"json"}', '[]', b'']
    def transport(raw):
        calls.append(raw)
        value = values[len(calls) - 1]
        if isinstance(value, Exception):
            raise value
        return response(declared, value)
    result = runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir, transport)
    assert len(calls) == len(manifest['requests']) == 8
    assert result['model_calls'] == 8
    assert result['status_counts'] == {'captured': 7, 'transport_failure': 1}
    classes = [row['raw_classification'] for row in result['outcomes']]
    assert classes == ['raw_text', 'declared_abstention', 'empty', 'transport_failure',
                       'malformed_json', 'raw_text', 'raw_text', 'empty']
    failed = result['outcomes'][3]
    assert failed['error']['type'] == 'OSError' and failed['raw_path'] is None
    assert runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)['model_calls'] == 8


@pytest.mark.parametrize('change', [
    {'model_id': 'foreign-model'}, {'seed': 1}, {'context_window_tokens': 32768},
    {'reasoning': {'effort': 'low'}},
    {'sampling': {'temperature': 1, 'top_p': 1, 'max_output_tokens': 512}},
])
def test_foreign_observed_route_is_retained_once_then_remaining_requests_are_not_run(tmp_path, change):
    run_dir, manifest, declared = frozen(tmp_path)
    calls = []
    observed = route(**change)
    def transport(raw):
        calls.append(raw)
        return response(observed, 'retained despite foreign route')
    result = runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir, transport)
    assert len(calls) == 1
    assert result['outcomes'][0]['status'] == 'identity_mismatch'
    assert result['outcomes'][0]['raw_path'] == 'raw/00.bin'
    assert [row['status'] for row in result['outcomes'][1:]] == ['not_run'] * 7
    assert result['model_calls'] == 1
    assert runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)['integrity_passed'] is True


@pytest.mark.parametrize('route_change', [
    {'endpoint': 'https://example.invalid/v1'}, {'context_window_tokens': 32768},
    {'automatic_retries': 1}, {'reasoning': {'effort': 'ultra'}},
])
def test_invalid_or_mismatched_pre_call_attestation_fails_without_a_transport(tmp_path, route_change):
    declared = route()
    observed = route(**route_change)
    with pytest.raises(ValueError):
        frozen(tmp_path, declared=declared, observed=observed)
    assert not (tmp_path / 'run').exists()


def test_tampered_frozen_packet_creates_durable_not_run_results_before_transport(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    packet = run_dir / manifest['requests'][0]['input_path']
    packet.write_bytes(packet.read_bytes() + b'\n')
    calls = []
    result = runner.execute_frozen_run(
        DATA, SOURCE, SHA, TYPED, run_dir,
        lambda raw: calls.append(raw) or response(declared),
    )
    assert calls == []
    assert result['status_counts'] == {'not_run': 8}
    assert all(row['error']['type'] == 'PreflightValidationError' for row in result['outcomes'])


def test_packet_corruption_after_preflight_is_sealed_without_a_transport(tmp_path, monkeypatch):
    run_dir, manifest, declared = frozen(tmp_path)
    original_verify = runner._verify_frozen_run
    def corrupt_after_verify(*args, **kwargs):
        result = original_verify(*args, **kwargs)
        (run_dir / manifest['requests'][0]['input_path']).write_bytes(b'not-json-after-preflight')
        return result
    monkeypatch.setattr(runner, '_verify_frozen_run', corrupt_after_verify)
    calls = []
    result = runner.execute_frozen_run(
        DATA, SOURCE, SHA, TYPED, run_dir,
        lambda raw: calls.append(raw) or response(declared),
    )
    assert calls == []
    assert result['status_counts'] == {'not_run': 8}
    assert result['outcomes'][0]['error']['type'] in ('ValueError', 'JSONDecodeError')


def test_malformed_transport_metadata_keeps_raw_bytes_as_a_failure_receipt(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    calls = []
    def transport(raw):
        calls.append(raw)
        return {
            'raw_output': b'raw retained before malformed metadata validation',
            'observed_route': {'not': 'a complete route'},
            'transport_status': 'completed',
        }
    result = runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir, transport)
    assert len(calls) == 8
    assert result['status_counts'] == {'transport_failure': 8}
    for outcome in result['outcomes']:
        assert outcome['raw_path'] is not None
        assert (run_dir / outcome['raw_path']).read_bytes().startswith(b'raw retained')
        assert outcome['observed_route'] is None
    assert runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)['integrity_passed'] is True


def test_second_execution_and_existing_attempts_cannot_replay_calls(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    calls = []
    runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir,
                              lambda raw: calls.append(raw) or response(declared))
    assert len(calls) == 8
    with pytest.raises(ValueError, match='already_started'):
        runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir,
                                  lambda raw: calls.append(raw) or response(declared))
    assert len(calls) == 8


def test_seal_interrupted_run_accounts_for_remaining_requests_without_calls(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    partial = runner._base_outcome(
        manifest['requests'][0], status='not_run', input_dispatched=False,
        model_call_began=False, raw_classification='not_run', transport_status='not_run',
        error={'type': 'SyntheticInterruption', 'message': 'test interruption'},
    )
    runner.write_json(partial, run_dir / 'attempts/00.json')
    result = runner.seal_interrupted_run(run_dir, 'synthetic interruption')
    assert result['requested'] == result['accounted'] == 8
    assert result['model_calls'] == 0
    assert result['status_counts'] == {'not_run': 8}
    assert runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)['integrity_passed'] is True


def test_results_verifier_rejects_tampered_raw_and_summary(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir,
                              lambda raw: response(declared, 'stable raw'))
    assert runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)['integrity_passed'] is True
    raw = run_dir / 'raw/00.bin'
    raw.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='binding'):
        runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)
    # Restore the exact expected raw then make a report-only counter claim; retained attempt wins.
    raw.write_bytes(b'stable raw')
    results = json.loads((run_dir / 'results.json').read_bytes())
    results['model_calls'] = 0
    (run_dir / 'results.json').write_bytes(cf.canonical(results) + b'\n')
    with pytest.raises(ValueError, match='summary'):
        runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)


def test_results_verifier_rejects_paired_captured_route_tampering(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    runner.execute_frozen_run(DATA, SOURCE, SHA, TYPED, run_dir,
                              lambda raw: response(declared, 'stable raw'))
    foreign = route(model_id='foreign-but-well-shaped-model')
    attempt_path = run_dir / 'attempts/00.json'
    attempt = json.loads(attempt_path.read_bytes())
    attempt['observed_route'] = foreign
    attempt['observed_route_sha256'] = cf.digest(cf.canonical(foreign))
    attempt_path.write_bytes(cf.canonical(attempt) + b'\n')
    results_path = run_dir / 'results.json'
    results = json.loads(results_path.read_bytes())
    results['outcomes'][0] = attempt
    results_path.write_bytes(cf.canonical(results) + b'\n')
    with pytest.raises(ValueError, match='captured_outcome_route'):
        runner.verify_results(DATA, SOURCE, SHA, TYPED, run_dir)


def test_tampered_route_snapshot_seals_every_request_before_transport(tmp_path):
    run_dir, manifest, declared = frozen(tmp_path)
    (run_dir / runner.RUNTIME_SNAPSHOT_NAME).write_bytes(b'{"models":[]}')
    calls = []
    result = runner.execute_frozen_run(
        DATA, SOURCE, SHA, TYPED, run_dir,
        lambda raw: calls.append(raw) or response(declared),
    )
    assert calls == []
    assert result['model_calls'] == 0
    assert result['status_counts'] == {'not_run': 8}
    assert all(row['error']['type'] == 'PreflightValidationError'
               for row in result['outcomes'])


def test_create_only_json_and_cli_freeze_verify_never_call_a_model(tmp_path):
    value = {'one': 1}
    output = tmp_path / 'once.json'
    runner.write_json(value, output)
    with pytest.raises(FileExistsError):
        runner.write_json(value, output)
    declared_path = tmp_path / 'declared.json'
    observed_path = tmp_path / 'observed.json'
    declared_path.write_bytes(cf.canonical(route()) + b'\n')
    observed_path.write_bytes(cf.canonical(route()) + b'\n')
    run_dir = tmp_path / 'cli-run'
    command = [
        sys.executable, str(ROOT / 'scripts/chess_no_forward_generation_runner.py'), 'freeze',
        '--data', str(DATA), '--source', str(SOURCE), '--source-sha256', SHA,
        '--typed-packet', str(TYPED), '--input-manifest', str(INPUTS),
        '--declared-route', str(declared_path), '--observed-route', str(observed_path),
        '--route-attestation', str(attestation(tmp_path, route())), '--run-dir', str(run_dir),
    ]
    frozen_process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert frozen_process.returncode == 0, frozen_process.stderr
    assert json.loads(frozen_process.stdout)['model_calls'] == 0
    verified = subprocess.run([
        sys.executable, str(ROOT / 'scripts/chess_no_forward_generation_runner.py'), 'verify',
        '--data', str(DATA), '--source', str(SOURCE), '--source-sha256', SHA,
        '--typed-packet', str(TYPED), '--run-dir', str(run_dir),
    ], cwd=ROOT, text=True, capture_output=True, timeout=60)
    # A frozen-only run has no results and verify deliberately refuses to turn it into a call.
    assert verified.returncode != 0


def test_loopback_transport_uses_exact_canonical_packet_as_user_content(tmp_path):
    captured = {}
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size): return b'{"local":"raw"}'
    class FakeOpener:
        def open(self, request, timeout):
            captured['payload'] = json.loads(request.data)
            captured['timeout'] = timeout
            return FakeResponse()
    run_dir, manifest, declared = frozen(tmp_path)
    raw = (run_dir / manifest['requests'][0]['input_path']).read_bytes()
    transport = runner.build_loopback_transport(declared, opener=FakeOpener())
    outcome = transport(raw)
    assert captured['payload']['messages'] == [{'role': 'user', 'content': raw.decode('utf-8')}]
    assert captured['payload']['messages'][0]['content'].encode('utf-8') == raw
    assert outcome == response(declared, b'{"local":"raw"}')
