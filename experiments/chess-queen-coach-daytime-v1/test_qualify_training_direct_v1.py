"""No backend calls: full eight pending rows survive new operational gate failures."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import pytest
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import qualify_training_direct_v1 as subject
from test_direct_launch_contract import receipt


def test_all_learning_loss_update_save_reload_functions_are_AST_identical():
    functions = lambda path: {node.name: ast.dump(node) for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef)}
    old, current = functions(HERE/'qualify_training.py'), functions(HERE/'qualify_training_direct_v1.py')
    assert set(old) == set(current)
    assert {name for name in old if old[name] != current[name]} == {'verify'}


@pytest.mark.parametrize('failure', ['missing_parity', 'failed_parity', 'wrong_worker', 'failed_observer'])
def test_new_operational_failure_retains8notrun_before_any_model(tmp_path, monkeypatch, failure):
    files = {}
    def file(name, value):
        path = tmp_path/name; path.write_text(json.dumps(value))
        files[name] = path
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    parity_plan = file('parity-plan.json', {})
    worker = receipt(); worker['ownership']['before_go']['creator_identity']['image'] = 'base.exe'
    worker_binding = file('worker.json', worker)
    result = file('parity.json', {'status': 'failed' if failure == 'failed_parity' else 'passed',
        'launch_profile': subject.launch_contract.PROFILE, 'worker_source_sha256': 'new-source',
        'protocol_sha256': parity_plan['sha256'], 'candidate_worker_sha256': worker_binding['sha256']})
    audit = file('parity-audit.json', {'status': 'passed', 'protocol_sha256': parity_plan['sha256'],
        'parity_sha256': result['sha256'], 'worker_sha256': 'wrong' if failure == 'wrong_worker' else worker_binding['sha256']})
    if failure == 'missing_parity': files['parity.json'].unlink()
    observer = file('observer-gate.json', {'status': 'authored_failed_observer'})
    plan = {'implementation_sha256': subject.checked.nf4.base.digest(Path(subject.__file__)),
        'schema': 'chess.queen-coach-daytime-warm-qualification.v1', 'maximum_seconds': 600,
        'planned_updates': 1, 'planned_presentations': 8, 'disposable_not_candidate': True, 'dependencies': [],
        'owned_worker_source': {'path': str(HERE/'owned_worker_v2.py'), 'sha256': 'new-source'},
        'launch_profile': subject.launch_contract.PROFILE, 'interpreters': {'delegate': 'base.exe'},
        'cpu_environment_parity': {'protocol': parity_plan, 'result': result, 'worker': worker_binding, 'audit': audit},
        'cpu_observer_gate_protocol': observer}
    protocol = tmp_path/'protocol.json'; protocol.write_text(json.dumps(plan))
    # Hash validation is separately tested; these callbacks read only authored fixtures.
    monkeypatch.setattr(subject.checked.nf4, 'binding', lambda item: Path(item['path']))
    monkeypatch.setattr(subject.cold_route, 'bound', lambda item: Path(item['path']))
    def observer_failure(value): raise ValueError('authored observer not actually passed')
    monkeypatch.setattr(subject.cold_route, 'verify', observer_failure)
    def forbidden(*args): raise AssertionError('Model setup must not occur')
    out = tmp_path/'attempt'
    with pytest.raises((ValueError, FileNotFoundError)):
        subject.run(plan, protocol, out, runtime_factory=forbidden, guard_factory=forbidden)
    actual = json.loads((out/'qualification.json').read_text())
    assert actual['status'] == 'failed' and actual['updates_completed'] == actual['presentations_completed'] == 0
    assert len(actual['rows']) == 8 and all(row['status'] == 'not_run' for row in actual['rows'])
    assert (out/'resources.json').exists()
