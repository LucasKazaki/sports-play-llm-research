"""Freeze actual source/data/runtime bindings after CPU corpus closure."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_train_v1 as pilot


def item(path):
    path=Path(path)
    return {'path':str(path).replace('\\','/'),'sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()}


data=Path('data/private/chess-queen-coach-sft-v1');manifest=json.loads((ROOT/data/'manifest.json').read_text())
preflight=json.loads((ROOT/data/'tokenizer-preflight.json').read_text())
if manifest['status']!='ready_for_training'or preflight['status']!='passed'or preflight['cuda_initialized']is not False:
    raise ValueError('Actual corpus/CPU tokenizer preflight has not passed')
if preflight['manifest_sha256']!=item(data/'manifest.json')['sha256']:raise ValueError('Preflight corpus differs')
names={'train':'train.jsonl','development':'development.jsonl','development_references':'development-references.jsonl',
    'heldout_inputs':'heldout-inputs.jsonl','heldout_references':'heldout-references.jsonl'}
bindings={key:item(data/name)for key,name in names.items()}
for key,binding in bindings.items():
    if binding['sha256']!=manifest['files'][names[key]]['sha256']:raise ValueError('Actual corpus binding differs')
raw_groups=manifest['development_raw_group_ids']
if len(raw_groups)!=4 or len(set(raw_groups))!=4:raise ValueError('Fixed raw development groups differ')
plan={
    'schema':'chess.queen-coach-sft-training-protocol.v1','frozen_at':datetime.now(timezone.utc).isoformat(),
    'implementation_sha256':item('scripts/chess_queen_coach_sft_train_v1.py')['sha256'],
    'kind':'Learned local decoder LoRA on real game-disjoint CC0 tactical roots. No general coaching/Elo claim.',
    'successful_diagnostic':item('data/private/chess-queen-qlora-v1/diagnostic-2.json'),
    'diagnostic_protocol':item('experiments/chess-queen-qlora-v1/diagnostic-protocol-v2.json'),
    'kernel_protocol':item('experiments/chess-queen-nf4-v1/kernel-protocol-v2.json'),
    'kernel_receipt':item('data/private/chess-queen-nf4-v1/kernel-2.json'),
    'corpus_manifest':item(data/'manifest.json'),'cpu_preflight':item(data/'tokenizer-preflight.json'),
    'data':bindings,'development_raw_groups':raw_groups,
    'training':{'seed':4082083,'updates':256,'batch_size':1,'gradient_accumulation':8,'presentations':2048,
        'learning_rate':.0001,'warmup_updates':16,'scheduler':'linearwarmup,cosine to10percentLR',
        'optimizer':'AdamW betas0.9/0.999 eps1e-8 decay0.01 foreachFalse, adapterFP32only',
        'gradient_clip_norm':1.,'max_total_tokens':512,'checkpoints':[0,64,128,256],
        'objective':'Full128333-vocabulary shiftedCE, completeassistant/EOSonly; meanexampleloss/8 peraccumulation.',
        'order':'One seededPythonRandom permutation of all2048 TRAINrecords, one epoch; neverdrop/replacerecords.',
        'frozen':'ActualbaseNF4/encoder/bridges/BF16tiedvocabulary, exactstoragehash before/after includingnestedquantstates.'},
    'generation':{'max_new_tokens':1024,'maximum_seconds':180,'temperature':0,'seed':20260823,
        'generation_mode':'no_cache','precision_profile':'math_sdpa_fp32_reduction'},
    'selection_method':'Prefer8/8strictacceptedlegalBEST; thenFREE3plyrootteacherprefixagreement; thenFREEBESTteacheragreement; thenlowestfull64recordresponse-tokenNLL; earliestcheckpointincl0. Ifnone8/8,mostacceptedlegalfirst. Requireall64NLL/8rawrequests complete; semanticpartialraw remainscounted, failuresnotrescued.',
    'cutoff_utc':'2026-10-16T13:00:00+00:00','phase_maximum_seconds':{'training':10800,'heldout':5400},
    'resources':'ExactlyreviewedNF4start6GiBphysical/10GiBcommit/10GiBGPU,stop4GiBphysical/4GiBcommit/1GiBGPU. Rootexclusivelease/ownedWindowsjob,cooperativeguardsandhardworker/cutoff. Noreservechange/offload/packageupgrade.',
    'failure_policy':'Firstbackend/resource/cancel/phase/globalcutoff stopsallfurthercalls. Prewriteallfuturedevelopment/heldoutrows;fsyncmicro/optimizer/NLLintents; retainunknowninflightandnotrunremaining. Nosilentaccumulationresume or repeatedattempt.',
    'heldout':'Aftercompletedsaveddevselection, freshlyloadbothbaselinecheckpoint0andselectedactualadapters; both32pendinginputrowswrittenbeforemodel/resource setup. Noheldtarget/referencecontentopensuntilall64rawresponsesretained. Reportmatched16games/2modeswithfullfailures.',
    'metrics':'RawBESTlegality/strictdescription/teacheragreement andindependentCRITICAL_LINE1/2/3prefixagreement, nativebest/lineconsistency, EOS/partial separately. Recognizedadjacentcheck/captureclaims have separatetruth/completenesscounts; unknownotherproseremainsunaudited. Selected-givenrootcopyisnotunpromptedprediction.',
    'claims':'Teacheragreementisnotchesscorrectness/Elo. Fixed3plyeligibletyped16gamepanelandLichesspuzzlesdonotestablishgeneralquiet/positionalcoaching. Concisetemplatefacttargets are supervisedtraining, notproofopenendedexplanationquality. Preserveoriginalpublisher/NF4baselineandallfailures.',
    'dependencies':[item(path)for path in('scripts/chess_queen_coach_sft_runtime_v1.py','scripts/chess_queen_coach_sft_eval_v1.py',
        'scripts/chess_queen_qlora_v2.py','scripts/chess_queen_nf4_adapter_v2.py','scripts/chess_queen_adapter.py',
        'scripts/chess_queen_materialize.py','tests/test_chess_queen_coach_sft_runtime_v1.py',
        'tests/test_chess_queen_coach_sft_train_v1.py','tests/test_chess_queen_coach_sft_eval_v1.py',
        'experiments/chess-queen-v1/gpu_worker.py','data/private/chess-queen-qlora-v1/diagnostic-worker-2.json',
        'experiments/chess-queen-coach-sft-training-v1/cpu_preflight.py')]+[item(data/name)for name in
            ('train-references.jsonl','manifest.json','tokenizer-preflight.json')]}
with(HERE/'protocol.json').open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps({'protocol':item('experiments/chess-queen-coach-sft-training-v1/protocol.json'),
    'trainer':plan['implementation_sha256'],'raw_dev_groups':raw_groups}))
