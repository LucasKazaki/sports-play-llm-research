"""Freeze exactly two deterministically chosen already-spent DEV software inputs."""
from pathlib import Path
from datetime import datetime,timezone
import json
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_cold_eval_v1 as outer


def bind(path):
    path=Path(path);path=path if path.is_absolute()else ROOT/path
    return {'path':str(path.relative_to(ROOT))if path.is_relative_to(ROOT)else str(path),'sha256':outer.digest(path)}


def main():
    directory=ROOT/'data/private/chess-queen-coach-counterfactual-cold-qualification-v1'
    if directory.exists():raise ValueError('Qualification input preparation is create-only')
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
    directory.mkdir();inputs=directory/'inputs.jsonl'
    with inputs.open('x',encoding='utf-8')as stream:
        for row in rows:stream.write(json.dumps(row)+'\n')
    names=[item['path']for item in parent['dependencies']]
    names += ['scripts/chess_queen_coach_counterfactual_runtime_v1.py','scripts/chess_queen_coach_counterfactual_cold_child_v1.py',
        'scripts/chess_queen_coach_counterfactual_cold_eval_v1.py','tests/test_chess_queen_coach_counterfactual_cold_child_v1.py',
        'tests/test_chess_queen_coach_counterfactual_cold_eval_v1.py',str(Path(__file__))]
    child=bind('scripts/chess_queen_coach_counterfactual_cold_child_v1.py')
    model_runtime={key:parent[key]for key in('kernel_protocol','kernel_receipt','generation')}
    model_runtime.update(training={'seed':4082086,'gradient_accumulation':8,'max_total_tokens':512},warm_start=warm)
    plan={'schema':'chess.queen-counterfactual-cold-qualification.v1','mode':'qualification',
        'frozen_at':datetime.now(timezone.utc).isoformat(),
        'implementation_sha256':bind('scripts/chess_queen_coach_counterfactual_cold_eval_v1.py')['sha256'],
        'child_script':child,'child_implementation_sha256':child['sha256'],'model_runtime':model_runtime,
        'input_rows':bind(inputs),'conditions':{'software':warm},'child_maximum_seconds':210,'phase_maximum_seconds':450,
        'cutoff_utc':'2026-10-16T13:00:00+00:00','admission_latest_utc':'2026-10-16T11:15:00+00:00',
        'planned':2,'selection':'Firstsourceorder alreadyspent step64DEVFREE, then firstsourceorder spentDEVselected fromdifferentgroup. No outputquality or references used. Bothinputs stripped to case/group/mode/currentFEN+optionalgivenmove only.',
        'spent_development_inputs':bind(development),'closed_spent_panel':bind(spent_path),
        'acceptance':'Exactly2closedchildren, samefixed64, inheritedownedjob, actualexitbefore next, exactrawinput/checkpoint/settings/sourceSHA, rawsavedbeforecleanup/storage, unchangedfrozenstorage, outerneverTorch, noresource/backend/timeoutfailure. Postexitglobalcommit growth<=1GiB frominitialouterbaseline aftereachchild. No accuracycriterion and no claim96request stability.',
        'resources':parent['resources'],'root_dispatch':'OneouterGPUworker/lease/job, no nestedlease, serializedinheritedchildren. NoagentGPU/modelcalls. Wholephase450s/perchild210s/global13UTC. No oldheldinputs/references or repeatedoldheldcandidate.',
        'failure_basis':bind('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-review/coach-heldout-v2-failure-closed-review.json'),
        'failure_limit':'Priorcommitfailuredoesnotproveexclusiveprocessattribution orsinglecall safety. Coldlifetime is a softwarehypothesis; untouchedfull96freshheld protocol requiresactualclosedqualification andindependentreview.',
        'dependencies':[bind(name)for name in dict.fromkeys(names)]}
    target=ROOT/'experiments/chess-queen-coach-counterfactual-v1/cold-qualification-protocol.json'
    with target.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2);stream.write('\n')
    outer.verify(plan)
    print(json.dumps({'protocol':bind(target),'two_case_ids':[row['case_id']for row in rows],
        'outer_imported_torch':'torch'in sys.modules,'no_model_calls':True}))


if __name__=='__main__':main()
