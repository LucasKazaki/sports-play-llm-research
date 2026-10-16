"""Freeze only after actual fresh recovery corpus, tokenizer and independent audit."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_train_v2 as pilot


def bind(path):
    path=Path(path);path=path if path.is_absolute()else ROOT/path
    return {'path':str(path.relative_to(ROOT))if path.is_relative_to(ROOT)else str(path),
        'sha256':pilot.checked.nf4.base.digest(path)}


def prepare(data,operational_protocol,operational_closed,audit,out):
    data=Path(data).resolve();manifest=json.loads((data/'manifest.json').read_text())
    provenance=json.loads((data/'operational-provenance.json').read_text())
    if(manifest['status']!='ready_for_training'or provenance['status']!='completed'
        or provenance['owned_engine_exit_verified']is not True):raise ValueError('Actual closed operational corpus required')
    parent_path=ROOT/'experiments/chess-queen-coach-sft-training-v2/protocol.json'
    parent=pilot.prior.verify_protocol(parent_path)
    preflight=json.loads((data/'tokenizer-preflight.json').read_text())
    if(preflight['status']!='passed'or preflight['cuda_initialized']
        or preflight['manifest_sha256']!=bind(data/'manifest.json')['sha256']):raise ValueError('Actual new CPUtokenizer preflight required')
    diagnostic=json.loads(Path(pilot.checked.nf4.binding(parent['diagnostic_protocol'])).read_text())
    formatter=next(item for item in diagnostic['dependencies']if item['path'].replace('\\','/').endswith('/utils/instance_format.py'))
    pilot.checked.nf4.binding(formatter)
    assets=json.loads(Path(pilot.checked.nf4.base.MANIFEST).read_text())
    expected_tokenizer={name:value for name,value in assets['files'].items()if name.startswith('tokenizer')or name in('chat_template.jinja','special_tokens_map.json','added_tokens.json')}
    if(preflight['official_formatter_sha256']!=formatter['sha256']or preflight['tokenizer_bindings']!=expected_tokenizer):
        raise ValueError('Actual pinned formatter/tokenizer receipt differs')
    warm_path=ROOT/'data/private/chess-queen-coach-sft-training-v2/train-1/checkpoint-0064/metadata.json'
    warm=json.loads(warm_path.read_text());pilot.validate_start(warm)
    runtime_keys=['successful_diagnostic','diagnostic_protocol','kernel_protocol','kernel_receipt',
        'successful_memory_qualification','closed_memory_worker','memory_protocol','memory_implementation','resources']
    plan={key:parent[key]for key in runtime_keys}
    names=[item['path']for item in parent['dependencies']]
    names += ['scripts/chess_queen_coach_sft_train_v2.py','scripts/chess_queen_coach_sft_eval_v1.py',
        'scripts/chess_queen_coach_counterfactual_runtime_v1.py','scripts/chess_queen_coach_counterfactual_eval_v1.py',
        'scripts/chess_queen_coach_counterfactual_train_v2.py',
        'scripts/chess_queen_coach_counterfactual_train_v1.py','tests/test_chess_queen_coach_counterfactual_train_v2.py',
        'scripts/chess_queen_coach_counterfactual_contract_v1.py','tests/test_chess_queen_coach_counterfactual_contract_v1.py',
        'tests/test_chess_queen_coach_counterfactual_runtime_v1.py','tests/test_chess_queen_coach_counterfactual_eval_v1.py',
        'tests/test_chess_queen_coach_counterfactual_train_v1.py',
        'experiments/chess-queen-coach-counterfactual-v1/cpu_preflight.py',str(Path(__file__)),formatter['path']]
    plan.update(schema='chess.queen-coach-counterfactual-training-protocol.v2',frozen_at=datetime.now(timezone.utc).isoformat(),
        implementation_sha256=bind('scripts/chess_queen_coach_counterfactual_train_v2.py')['sha256'],
        qualified_parent_protocol=bind(parent_path),warm_start=warm,warm_start_metadata=bind(warm_path),
        corpus_manifest=bind(data/'manifest.json'),cpu_preflight=bind(data/'tokenizer-preflight.json'),
        cpu_preflight_source=bind('experiments/chess-queen-coach-counterfactual-v1/cpu_preflight.py'),
        corpus_scientific_protocol=bind('experiments/chess-queen-coach-counterfactual-v1/intake-protocol.json'),
        corpus_operational_protocol=bind(operational_protocol),corpus_operational_closed=bind(operational_closed),
        corpus_operational_provenance=bind(data/'operational-provenance.json'),corpus_closed_audit=bind(audit),
        data={key:bind(data/name)for key,name in [('train','train.jsonl'),('development','development.jsonl'),
            ('train_references','train-references.jsonl'),('development_references','development-references.jsonl'),
            ('heldout_inputs','heldout-inputs.jsonl'),('heldout_references','heldout-references.jsonl')]},
        development_raw_groups=manifest['development_raw_group_ids'],
        training={**parent['training'],'seed':4082086,'updates':192,'presentations':1536,'checkpoints':[0,48,96,192],
            'order':'One seeded permutation of all1536examples,512freshgames xFREE+two supplied contrasting legalmoves, oneepoch. No weighted loss or extra objective.'},
        generation=parent['generation'],phase_maximum_seconds={'training':3000,'heldout':4500},
        authorized_entrypoints={'training':'scripts/chess_queen_coach_counterfactual_train_v2.py mode=train only',
            'heldout':'ONLY scripts/chess_queen_coach_counterfactual_cold_eval_v2.py with separately frozen cold-held protocol after actual software qualification; preserved unexecuted trainer.heldout is not an authorized entrypoint'},
        expected_formatter=formatter,expected_tokenizer_bindings=expected_tokenizer,
        admission_latest_utc='2026-10-16T11:00:00+00:00',held_admission_latest_utc='2026-10-16T11:30:00+00:00',
        operating_amendment=bind('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/overnight/prospective-admission-amendment-v2.json'),
        superseded_unexecuted_protocol=bind(ROOT/'experiments/chess-queen-coach-counterfactual-v1/training-protocol.json'),
        cutoff_utc='2026-10-16T13:00:00+00:00',
        selection_method='Prefer6/6 acceptedlegalBEST, elsemostlegal; thenFREE3plyagreement,FREEBESTagreement,lowest96recordtokenNLL,earliestincl0. Require96NLL+6raw complete. Facts do not alter selector.',
        heldout='Fresh16full3plyeligible reservegames x3modes x2conditions=96rawcalls, both48pendingledgers before setup. All rawconditions must close before newheldrefs open. No oldcoachheldcontent used.',
        joint_fact_metric='CompletedEOS+exactlyone acceptedBEST equals given+one unambiguous recognized ANALYSISmove equals given+complete true check/capture. Duplicates/contradictions/mismatch/unrecognized cannot jointsuccess; retainallrecognizedspans,unknown/partial. Other prose unaudited.',
        conditional_prediction_metric='FREE1/2/3Stockfishprefix; suppliedfirstmove is not prediction. Report conditionalreply/2reply match and givenconsistency separately.',
        intervention='Only freshpaired selected-move data plus retainedFREE supervision. Same qualifiedmodel/LoRA/tokenCE; fixedselected64warmbaseline, freshAdamW/no optimizerresume. Additionaldata+learning do not causally isolate pairdesign.',
        admission='TRAIN must startbefore11:00UTC; separately qualified wholecoldheld must startbefore11:30UTC. This prospective operational amendment preserves the unexecuted11:15 plan; it changes no science, quotas, reserves, phase caps or13UTC cutoff. Root must leave plausibleheldadmission; no192step/96response shrink or delayed implicitpermission. Global13UTC and phasecaps apply.',
        failures='Firstbackend/resource/cancel/deadlinefailure haltsalllatercalls; fsyncedintent/rawoutcomes, allplannedunknown/notrun retained. No retries, repair, legalmask, wholeprose orElo claim.',
        dependencies=[bind(name)for name in dict.fromkeys(names)])
    out=Path(out)
    with out.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    pilot.verify_protocol(out);return bind(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('data','operational-protocol','operational-closed','audit','out'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.data,args.operational_protocol,args.operational_closed,args.audit,args.out)))
