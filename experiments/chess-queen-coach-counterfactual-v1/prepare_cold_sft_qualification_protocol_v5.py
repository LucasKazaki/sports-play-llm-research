"""Freeze exactly two deterministically chosen already-spent DEV software inputs."""
from pathlib import Path
from datetime import datetime,timezone
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_cold_eval_v4 as outer
import chess_queen_coach_sft_runtime_v2 as runtime


def bind(path):
    path=Path(path);path=path if path.is_absolute()else ROOT/path
    return {'path':str(path.relative_to(ROOT))if path.is_relative_to(ROOT)else str(path),'sha256':outer.digest(path)}


def main():
    directory=ROOT/'data/private/chess-queen-coach-counterfactual-cold-qualification-v1'
    if not directory.exists():raise ValueError('Preserved unexecuted2-input qualification preparation required')
    parent_path=ROOT/'experiments/chess-queen-coach-sft-training-v2/protocol.json';parent=outer.read(parent_path)
    development=ROOT/'data/private/chess-queen-coach-sft-v1/development.jsonl'
    spent_path=ROOT/'data/private/chess-queen-coach-sft-training-v2/train-1/raw-development-0064.json'
    spent=outer.read(spent_path)
    if spent['status']!='completed':raise ValueError('Closed spent development panel required')
    spent_ids={row['case_id']for row in spent['rows']if row['status']in('completed','partial')}
    records=[json.loads(line)for line in development.read_text().splitlines()if line.strip()]
    free=next(row for row in records if row['case_id']in spent_ids and row['mode']=='free')
    selected=next(row for row in records if row['case_id']in spent_ids and row['mode']=='selected'and row['group_id']!=free['group_id'])
    rows=[{key:row[key]for key in('case_id','group_id','mode','input')}for row in(free,selected)]
    warm=outer.read(ROOT/'data/private/chess-queen-coach-sft-training-v2/train-1/checkpoint-0064/metadata.json')
    if warm['sha256']!='73e632f65d9146c789223ddcd7cbe106041b84aecab25ed9a775efc11bb28e3e':raise ValueError('Fixed selected64 identity differs')
    inputs=directory/'inputs.jsonl'
    preserved=[json.loads(line)for line in inputs.read_text().splitlines()if line.strip()]
    if preserved!=rows:raise ValueError('Preserved deterministic software inputs changed')
    names=[item['path']for item in parent['dependencies']]
    names += ['scripts/chess_queen_coach_sft_runtime_v2.py','scripts/chess_queen_process_lineage_v3.py','scripts/chess_queen_coach_sft_compare_cold_child_v1.py',
        'scripts/chess_queen_coach_counterfactual_cold_eval_v4.py','tests/test_chess_queen_coach_sft_compare_cold_child_v1.py',
        'tests/test_chess_queen_coach_counterfactual_cold_eval_v4.py',str(Path(__file__)),'tests/test_chess_queen_process_lineage_v3.py','experiments/chess-queen-coach-counterfactual-v1/probe_venv_sampler_topology_v3.py']
    child=bind('scripts/chess_queen_coach_sft_compare_cold_child_v1.py')
    model_runtime={key:parent[key]for key in('kernel_protocol','kernel_receipt','generation')}
    model_runtime.update(training={'seed':4082086,'gradient_accumulation':8,'max_total_tokens':512},warm_start=warm)
    base=runtime.checked.nf4.base
    projection={'schema':'chess.queen-coach-sft-output.v2','candidate_id':'queen-pawn-8/nf4-coach-sft-v2',
        'base_candidate_id':runtime.checked.nf4.CANDIDATE,'model_id':base.MODEL_ID,'model_revision':base.MODEL_REVISION,
        'source_revision':base.SOURCE_REVISION,'adapter_sha256':bind(Path(runtime.__file__))['sha256'],
        'base_generator_source_sha256':bind(Path(base.__file__))['sha256'],
        'base_nf4_source_sha256':bind(Path(runtime.checked.nf4.__file__))['sha256'],
        'nf4_protocol_sha256':model_runtime['kernel_protocol']['sha256'],'kernel_receipt_sha256':model_runtime['kernel_receipt']['sha256'],
        'asset_manifest_sha256':bind(base.MANIFEST)['sha256'],'source_manifest_sha256':bind(base.SOURCE_MANIFEST)['sha256'],
        'quantization.requested':runtime.checked.nf4.QUANTIZATION,'quantization.actual_lora_dtype':'float32',
        'quantization.actual_lora_parameters':1916928,'quantization.encoder_and_bridges':'Frozen BF16'}
    arguments=['scripts/chess_queen_coach_counterfactual_cold_eval_v4.py','--protocol','experiments/chess-queen-coach-counterfactual-v1/cold-sft-qualification-protocol-v5.json',
        '--out','data/private/chess-queen-coach-counterfactual-cold-qualification-v1/attempt-3']
    plan={'schema':'chess.queen-counterfactual-cold-qualification.v1','mode':'qualification',
        'frozen_at':datetime.now(timezone.utc).isoformat(),
        'implementation_sha256':bind('scripts/chess_queen_coach_counterfactual_cold_eval_v4.py')['sha256'],
        'process_lineage_helper':bind('scripts/chess_queen_process_lineage_v3.py'),
        'resource_sampler_auxiliary':{'executable':bind(Path(shutil.which('nvidia-smi')).resolve()),
            'arguments':['nvidia-smi','--query-gpu=memory.total,memory.free','--format=csv,noheader,nounits'],
            'source':bind('scripts/chess_native_resources.py'),
            'argument_evidence':'Frozen subprocess.run source only; OS process command line not inspected.',
            'ownership':'Exact resolved executable/hash, direct observed runtime parent, creation>=runtime, inherited job, stablehandle EXIT. No extra query console host was observed or permitted.'},
        'interpreters':{'launcher':outer.normalized(sys.executable),'delegate':outer.normalized(sys._base_executable)},
        'prior_sampler_failure_review':bind('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-review/cold-sft-qualification-attempt2-failure-closed-review.json'),
        'transient_process_rule':'Only image-query WinError5 after successful OpenProcess, creation/job metadata and a stable handle already signaled EXIT, under an observed known runtime parent. Record separately as unverified exited; no claimed image/nvidia identity, never runtime/ancestry parent/termination target. Live or unretainable unknowns fail. Preserve observation errors. Prior failure PID/EXIT unavailable, so exit race remains hypothesis.',
        'profile':'Original SFT-v2 fixed64 software qualification; no counterfactual training or identity.',
        'lineage_contract':'Live OS observations and retained creation-bound handles admit direct launcher/runtime or exact one base-Python delegate; exact GetSystemDirectoryW/conhost auxiliary only. Hashed exact resource-query auxiliaries are direct runtime children only. Every retained handle requires inherited-job membership and EXIT before next request. Unknown topology fails; only verified owned handles may be terminated. No BREAKAWAY.',
        'cpu_topology_probe':bind('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/counterfactual-venv-sampler-topology-probe-v3/closed.json'),
        'prior_topology_failure_review':bind('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-review/counterfactual-cold-qualification-attempt1-failure-review.json'),
        'prior_topology_protocol':bind('experiments/chess-queen-coach-counterfactual-v1/cold-qualification-protocol-v3.json'),
        'policy_metadata_request_seconds':120,
        'guard_limit':'Policy metadata maximum_owned_request_seconds remains120, but unchanged nf4.guard_for calls reserve-only reasons() and does not enforce that elapsed timer. Actual unchanged limits: generator180s, child cumulative210s, outer qualification450s, global13UTC. Cooperative resource checks remain unchanged; no claimed active120s bound.',
        'child_script':child,'child_implementation_sha256':child['sha256'],'model_runtime':model_runtime,
        'input_rows':bind(inputs),'conditions':{'software':warm},'child_maximum_seconds':210,'phase_maximum_seconds':450,
        'cutoff_utc':'2026-10-16T13:00:00+00:00','admission_latest_utc':'2026-10-16T11:30:00+00:00',
        'raw_provenance':projection,'expected_worker_script':'scripts/chess_queen_coach_counterfactual_cold_eval_v4.py',
        'expected_worker_arguments':arguments,'planned':2,'selection':'Firstsourceorder alreadyspent step64DEVFREE, then firstsourceorder spentDEVselected fromdifferentgroup. No outputquality or references used. Bothinputs stripped to case/group/mode/currentFEN+optionalgivenmove only.',
        'spent_development_inputs':bind(development),'closed_spent_panel':bind(spent_path),
        'acceptance':'Exactly2closedchildren, samefixed64, inheritedownedjob, actualexitbefore next, exactrawinput/checkpoint/settings/sourceSHA, rawsavedbeforecleanup/storage, unchangedfrozenstorage, outerneverTorch, noresource/backend/timeoutfailure. Postexitglobalcommit growth<=1GiB frominitialouterbaseline aftereachchild. No accuracycriterion and no claim96request stability.',
        'resources':parent['resources'],'root_dispatch':'OneouterGPUworker/lease/job, no nestedlease, serializedinheritedchildren. NoagentGPU/modelcalls. Wholephase450s/perchild210s/global13UTC. No oldheldinputs/references or repeatedoldheldcandidate.',
        'failure_basis':bind('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-review/coach-heldout-v2-failure-closed-review.json'),
        'failure_limit':'Priorcommitfailuredoesnotproveexclusiveprocessattribution orsinglecall safety. Coldlifetime is a softwarehypothesis; untouchedfull96freshheld protocol requiresactualclosedqualification andindependentreview.',
        'dependencies':[bind(name)for name in dict.fromkeys(names)]}
    plan['dependencies'] += [plan[key]for key in('cpu_topology_probe','prior_topology_failure_review','prior_topology_protocol','prior_sampler_failure_review')]
    plan['dependencies'] += [plan['resource_sampler_auxiliary']['executable'],plan['resource_sampler_auxiliary']['source']]
    target=ROOT/'experiments/chess-queen-coach-counterfactual-v1/cold-sft-qualification-protocol-v5.json'
    with target.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2);stream.write('\n')
    outer.verify(plan)
    print(json.dumps({'protocol':bind(target),'two_case_ids':[row['case_id']for row in rows],
        'outer_imported_torch':'torch'in sys.modules,'no_model_calls':True}))


if __name__=='__main__':main()
