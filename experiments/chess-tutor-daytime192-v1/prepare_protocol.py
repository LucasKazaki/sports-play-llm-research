"""Create a source-bound preactivation protocol, never an enabled UI admission.

Only small source/metadata files are read. The selected tensor hash is the fixed
closed-training identity, not a fresh tensor read. Root must separately review
the prospective authored qualification plan before any actual request.
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_daytime192_tutor_v1 as child

OLD_PROTOCOL_SHA='3d0672eae40cd3543ef838c0a3bba1aadccea1a44b59b62803b776c9f8f3477c'


def binding(repo,path,expected=None):
    file=Path(repo)/path
    return {'path':path,'sha256':expected or child.digest(file)}


def prepare(repo,source_out,protocol_out):
    repo=Path(repo)
    old=repo/'experiments/chess-queen-tutor-adapter-v1/protocol.json'
    child.require(child.digest(old)==OLD_PROTOCOL_SHA,'Original helper protocol differs.')
    bindings=dict(child.read_json(old)['bindings'])
    bindings['original_worker']=bindings['worker'];bindings['qualified_runtime']=bindings['runtime']
    changes={'runtime':'scripts/chess_queen_coach_counterfactual_runtime_v1.py',
        'worker':'experiments/chess-queen-coach-daytime-v1/owned_worker_v2.py',
        'helpers':'scripts/chess_queen_coach_tutor_v1.py',
        'training_protocol':'experiments/chess-queen-coach-daytime-v1/training-direct-protocol-v1.json',
        'selection':'data/private/chess-queen-coach-daytime-v1/train-1/selection.json',
        'checkpoint':'data/private/chess-queen-coach-daytime-v1/train-1/checkpoint-0192/adapter.pt',
        'checkpoint_metadata':'data/private/chess-queen-coach-daytime-v1/train-1/checkpoint-0192/metadata.json'}
    for role,path in changes.items():bindings[role]=binding(repo,path,child.FIXED.get(role))
    # Metadata/source pins are verified now, with the explicit tensor exception.
    for role,item in bindings.items():
        if role!='checkpoint':child.inside(repo,item)
    closure=sorted(set(child.PREVIEW_FILES+child.UI_FILES)|{item['path'] for name,item in bindings.items()
        if name not in {'selection','checkpoint','checkpoint_metadata','training_protocol','kernel_receipt'}})
    manifest={'schema':'chess.daytime192-preview-sources.v1','files':[binding(repo,path) for path in closure],
        'scope':'Source closure only; no model quality or activation. Native assets remain separately publisher-bound.'}
    child.write_new(source_out,manifest)
    bindings['preview_manifest']=binding(repo,Path(source_out).resolve().relative_to(repo.resolve()).as_posix())
    plan={'schema':child.PROTOCOL_SCHEMA,'profile_id':child.PROFILE,
        'scope':'root_qualification_or_explicitly_admitted_research_preview',
        'implementation_sha256':child.digest(repo/'scripts/chess_queen_daytime192_tutor_v1.py'),
        'generation':child.SETTINGS,'resources':child.RESOURCES,'outer_seconds':210,
        'worker_seconds_after_go':240,'runner_seconds':270,'cutoff_utc':child.CUTOFF,
        'python_version':'3.12.2','runtime_versions':child.safe.VERSIONS,'bindings':bindings,
        'availability':False,'preactivation_requests_authorized':False,
        'qualification_required':'One already-spent authored EOS and separate owned cancellation after192 load and infer start, under a separately reviewed exact root-dispatch plan.'}
    child.write_new(protocol_out,plan)
    return manifest,plan


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-out',type=Path,required=True);parser.add_argument('--protocol-out',type=Path,required=True)
    args=parser.parse_args();prepare(ROOT,args.source_out,args.protocol_out)
