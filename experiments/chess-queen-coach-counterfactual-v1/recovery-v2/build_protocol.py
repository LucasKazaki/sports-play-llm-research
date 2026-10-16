"""Freeze operational metadata only; never run intake, teachers or a model."""
import argparse
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('counterfactual_recovery_driver',HERE/'run_cpu_once.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
TASK=Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')


def build(out):
    root=driver.ROOT
    files={
        'driver':HERE/'run_cpu_once.py','builder':Path(__file__),
        'scientific_protocol':root/'experiments/chess-queen-coach-counterfactual-v1/intake-protocol.json',
        'intake':root/'scripts/chess_queen_coach_counterfactual_intake_v1.py',
        'teacher':root/'scripts/chess_queen_coach_counterfactual_teacher_v1.py',
        'proposal':TASK/'work/chess-counterfactual-recovery-v2-proposal.json',
        'closed_held_worker':root/'data/private/chess-queen-coach-sft-training-v2/heldout-1-worker.json',
        'root_changed_context':TASK/'work/overnight/coach-held-failure-owner-closed.json'}
    plan={'schema':driver.SCHEMA,'frozen_at':driver.utc(),'driver_sha256':driver.sha(files['driver']),
        'status':'source_review_candidate_not_execution_authorization','scientific_protocol_sha256':driver.SCIENCE,
        'bindings':{key:driver.binding(path) for key,path in files.items()},
        'failed_attempt':driver.read(files['proposal'])['failed_attempt']['bindings'],
        'counts':driver.COUNTS,'teacher_requests':3168,'filelock_version':'4.2.0','policy':driver.POLICY,
        'output':str(root/'data/private/chess-queen-coach-counterfactual-recovery-v2'),
        'lock':str(root/'data/private/chess-gpu-owner.lock'),
        'scope':'ONE changed-context CPU sequence only. Root dispatch after independent full-source/test/protocol review. No automatic retry, source patches, lower reserves, changed sampling/targets/deadlines, new acquisition or learned calls.',
        'changed_context':'Original guard failed at ordinal-1 while the owner was active; exact failed held worker is now terminal and root observed child absent/free lease/two passing CPU samples. Failure is not a coaching result.',
        'admission':'Acquire existing shared lease with timeout0 across scientific work/cleanup; verify old child absent and repeat two CPU samples>=1s apart with8GiBcommit/4GiBphysical before any scientific module import. Busy/failure stops once.',
        'readiness':'Exact512/32/512 intake; exactly3168 uniquely planned teachers all completed/coherent; observed owned Stockfish parent/PID and exit before unchanged export. All phase outcomes and unknown/not_run teacher outcomes retained.',
        'deadlines':'Unchanged scientific1200s intake/3300s teachers/13UTC cutoff. Existing guards are cooperative; driver also verifies elapsed phase time before later phases. No claim of an OS hard deadline or unrelated process control.',
        'provenance':'Sibling create-only intent/phases precede scientific access. Frozen sources and prior failed receipts copied into operational-sources after output creation/return or finalizer. operational-provenance.json and sibling operational-closed.json expose exact source/plan/corpus hashes, full phase statuses and observed engine exit.',
        'future_training':'A completed CPU sequence is not independent corpus audit or model quality. New reviewed training/evaluation protocol plus explicit root dispatch still required; latest11:15UTC applies to each future GPU phase.'}
    driver.verify(plan)
    driver.save(out,plan)
    return {'path':str(out),'sha256':driver.sha(out),'status':plan['status']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=HERE/'protocol.json')
    print(build(parser.parse_args().out))
