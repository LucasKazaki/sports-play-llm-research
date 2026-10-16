"""Metadata-only freeze after actual CPU cohort and independent audit close."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import chess_encoder_check_generalization_eval_v1 as candidate


def prepare(audit):
    if(HERE/'inference-protocol.json').exists():raise ValueError('Inference protocol is create-only')
    intake_protocol=HERE/'protocol-v2.json';intake_plan=candidate.intake.verify(intake_protocol)
    old=candidate.head.verify(candidate.head.bound(intake_plan['old_head_protocol']))
    audit=Path(audit)
    if not audit.is_file():raise ValueError('Actual independent cohort receipt is required')
    verdict=candidate.head.read(audit)
    if(not verdict.get('verdict','').startswith('PASS:')or verdict.get('blocking_findings')
        or verdict.get('new_model_calls')or verdict.get('engine_calls')or verdict.get('gpu_calls')
        or verdict.get('coach_teacher_or_held_reference_content_read')):
        raise ValueError('Independent actual-cohort audit has not passed without model/coach-reference calls')
    for key,name in{'closed':'closed.json','dataset':'dataset.json','inputs':'inputs.json','labels':'labels.json'}.items():
        if verdict[key]['sha256']!=candidate.head.sha(ROOT/'data/private/chess-encoder-check-generalization-v1'/name):
            raise ValueError('Actual audited cohort identity differs')
    copied=HERE/'actual-cohort-review.json'
    if copied.exists():raise ValueError('Audit receipt copy is create-only')
    shutil.copyfile(audit,copied)
    cohort=Path('data/private/chess-encoder-check-generalization-v1')
    plan={'schema':'chess.encoder-check-generalization-inference.v1','frozen_at':datetime.now(timezone.utc).isoformat(),
        'implementation_sha256':candidate.head.sha(Path(candidate.__file__)),
        'intake_protocol':candidate.intake.binding(str(intake_protocol)),
        'actual_cohort_audit':candidate.intake.binding(str(copied)),
        'independent_audit_origin':{'path':str(audit),'sha256':candidate.head.sha(audit)},
        'cohort':{key:candidate.intake.binding(str(cohort/name))for key,name in{
            'closed':'closed.json','inputs':'inputs.json','labels':'labels.json','dataset':'dataset.json'}.items()},
        'selected':intake_plan['selected'],'original_untrained':intake_plan['original_untrained'],
        'encoder':old['encoder'],'batch_size':128,'maximum_seconds':900,
        'cutoff_utc':'2026-10-16T13:00:00+00:00',
        'conditions':['savedoriginalepoch0','savedselectedepoch4','majorityfalseCPUaftersameclosedrawconditions'],
        'no_training':'Zerooptimizerupdates,nocheckpointselection,noretuning; originalepoch4wasfrozenbeforefreshcohortconstruction.',
        'inputs':'ExactlycurrentFENandselectedlegalUCI. IDs usedforledgersonly. Nolabels,stratum,checkers,successors,history orPV entersencoder/head/featurecache.',
        'features':'ExactoldfrozenLC0BF16eval,emptyhistoryFENplanes,currentstate mean/source/target3072FP32 andnativePOVsource/target/promotionindicesint64. ExactcurrentFENdedup, oneencoderforwardperboard; newcachepaths, allmoveidentitiesretained. NoLC0policy/value outputs cached.',
        'loading':'Exactoldreviewedtarget-onlymaterializer, floatingbuffersBF16/policy_index_mapint64. Encoderreleasedbeforeheadinference. Strictactualepoch0/4FP32headloads1680169parameters; rawlogit>=0, no masks/fallback/rulereplacement.',
        'proof':'Bothfullactualrawmodelledgers,64requestedsourcepairslots/128moveslots andlabel-freefeaturemanifestwrittenBEFOREresource/backendsetup. Fsyncedpre-callintents/completedrawresults andfullunknown/notrunrows. Firstbackend/resource/cancel/cutofffailurestopsalllatercalls/conditions; noreplay.',
        'label_policy':'Hashinput/label/datasetbytesbeforecalls, butsemanticlabelsandcase-to-stratum/checker/successormetadataopenONLYafterBOTHrawconditionledgerscomplete. Anyfailedconditionendswithoutopeninglabels.',
        'metrics':'Same-paneloverallandperexclusiveallocation/overlappingpositiveflags TP/TN/FP/FN,checking/noncheckingrecalls,completepaircorrectness andfullstatuses. Majorityfalseafterrawclosure. Reportrequestedsourcecoverage/shortagesseparatelyfromactualpredictions. Lasttwocategoriesusedifferentpieceinstancecontrasts; no matched-originclaimthere.',
        'resources':old['resources'],'dispatcher':'Rootonlyaftercoachheldphase, independentclosedcohortauditandfullsource/protocolreview. SharedexclusiveGPUworker/ownedjob. AgentCPUtestsuseauthoredcallbacksandmakenomodelcalls.',
        'limitations':'Smalltargetedmissing-coveragetacticaldiagnostic,unknownoriginalencoderpretrainingoverlap. Not coachingfactuality,languageunderstanding,movestrength,Eloorpopulationprevalence. NoUIpromotionfromthisresult.',
        'dependencies':old['dependencies']+[candidate.intake.binding(name)for name in[
            'scripts/chess_encoder_check_v1.py','scripts/chess_encoder_check_generalization_v1.py',
            'tests/test_chess_encoder_check_generalization_eval_v1.py','experiments/chess-queen-v1/gpu_worker.py',
            'experiments/chess-encoder-check-generalization-v1/actual-cohort-ready.json']]}
    target=HERE/'inference-protocol.json'
    with target.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2);stream.write('\n')
    candidate.verify(target)
    return {'path':str(target),'sha256':candidate.head.sha(target)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--audit',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.audit)))
