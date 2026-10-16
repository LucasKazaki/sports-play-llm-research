"""Freeze unchanged daytime science after both actual direct-route software gates."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_protocols as preserved
import prepare_direct_protocols_v3 as source
import daytime_train as trainer


def prepare(gates, out, actual_out):
    # This immutable builder enforces all existing scientific/qualification fields.
    plan = preserved.final_training(gates)
    qualified = source.cold.read(source.cold.bound(gates['cold']['protocol']))
    source.launch.environment(qualified, source.cold.bound, source.cold.read)
    for gate in gates.values():
        source.launch.owned_worker(source.cold.read(source.cold.bound(gate['worker'])),
            qualified['owned_worker_source'], qualified['interpreters'])
    plan.update(**{key: qualified[key] for key in ['launch_profile', 'owned_worker_source',
        'cpu_environment_parity', 'interpreters']})
    script = 'experiments/chess-queen-coach-daytime-v1/daytime_train.py'
    plan.update(frozen_at=datetime.now(timezone.utc).isoformat(), expected_worker_script=script,
        expected_worker_arguments=[script, 'train', '--protocol', str(Path(out).resolve()),
            '--out', str(Path(actual_out).resolve())],
        authorized_entrypoints={
            'training': script+' train with this exact protocol after both actual audited direct-route software gates',
            'heldout': 'ONLY experiments/chess-queen-coach-daytime-v1/cold_eval_v7.py with separately frozen full96 daytime held plan after actual closed TRAIN/audit; embedded trainer.heldout remains unauthorized'},
        prospective_metadata_correction='Actual current freeze timestamp and direct-route held entrypoint only. Immutable science, old source/protocol chronology and all expired/unrun/failure records remain exact.')
    plan['dependencies'] = source.dependencies(plan['dependencies'])+qualified['dependencies']+[
        source.bind(Path(__file__)), source.bind(HERE/'test_freeze_direct_training_v1.py')]
    receipt = source.create(out, plan)
    trainer.verify_protocol(out)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['gates', 'out', 'actual-out']: parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(source.cold.read(args.gates), args.out, args.actual_out)))
