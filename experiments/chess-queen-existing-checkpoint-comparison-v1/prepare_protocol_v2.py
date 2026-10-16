"""Freeze a no-training comparison of two previously trained SFT checkpoints."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_cold_eval_v4 as outer


def bind(path):
    path=Path(path)
    if not path.is_absolute():path=ROOT/path
    return {'path':str(path),'sha256':outer.digest(path)}


def prepare(design_path,qualification_protocol,qualification,worker,audit,spent_intent,out):
    design=outer.read(design_path)
    if (design.get('schema')!='chess.existing-coach-checkpoint-fresh-comparison-design.v1'
        or design['planned']!=96 or design['records_per_condition']!=48
        or design['source_game_groups']!=16 or design['reserved_source_games']!=512
        or design['condition_order']!=['baseline','selected'] or not design['no_new_training']
        or design['whole_phase_admission_latest_utc']!='2026-10-16T11:30:00+00:00'
        or design['cutoff_utc']!='2026-10-16T13:00:00+00:00'
        or design['phase_maximum_seconds']!=4500 or design['effective_request_guard_seconds']is not None
        or design['resource_policy_metadata_seconds']!=120 or design['resource_policy_timer_enforced']is not False
        or design['child_outer_maximum_seconds']!=210):
        raise ValueError('Exact prospective no-training comparison design required')
    expected={
        'baseline':(256,'bd8a7b886f94c1199e2fc0a14481dc0603f72fe9503a562a82cf12ba0bf8059e'),
        'selected':(64,'73e632f65d9146c789223ddcd7cbe106041b84aecab25ed9a775efc11bb28e3e')}
    for key,(step,sha) in expected.items():
        identity=design['conditions'][key]
        metadata=outer.read(outer.bound(design['checkpoint_metadata'][key]))
        if (metadata!=identity or identity['step']!=step or identity['sha256']!=sha
            or identity['candidate_id']!='queen-pawn-8/nf4-coach-sft-v2'
            or identity['source_sha256']!='7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349'
            or outer.digest(Path(identity['path']))!=sha):
            raise ValueError('Previously fixed old-SFT checkpoint identity differs')
    corpus=outer.read(outer.bound(design['closed_corpus_audit']))
    original=outer.read(outer.bound(design['closed_original_training_audit']))
    if corpus.get('status')!='passed' or not original.get('verdict','').startswith('PASS:'):
        raise ValueError('Actual closed corpus and original training audits required')
    inputs=outer.bound(design['inputs'])
    rows=[json.loads(line)for line in inputs.read_text().splitlines()if line.strip()]
    if len(rows)!=48 or len({r['group_id']for r in rows})!=16:
        raise ValueError('Full frozen48input/16group cohort required')
    for row in rows:
        if set(row)!={'case_id','group_id','mode','input'} or set(row['input'])not in({'fen'},{'fen','selected_uci'}):
            raise ValueError('Label-free current-only rows required')
    spent=outer.read(spent_intent)
    if (spent.get('schema')!='chess.once-only-fresh-cohort-reservation.v1'
        or spent.get('design_sha256')!=outer.digest(design_path)
        or spent.get('input_sha256')!=design['inputs']['sha256']
        or spent.get('group_ids')!=sorted({r['group_id']for r in rows})
        or spent.get('all512_reserved_from_future_training')is not True
        or spent.get('these16_forbidden_for_future_evaluation')is not True):
        raise ValueError('Separate exact cohort reservation required before dispatch')
    outer.bound(design['references'])  # Bytes only; never parse held reference content.
    outer.bound(design['reserved_exclusions'])
    qplan=outer.read(qualification_protocol)
    outer.verify(qplan)
    if (qplan['model_runtime']['generation']!=design['generation']
        or qplan['raw_provenance']['candidate_id']!='queen-pawn-8/nf4-coach-sft-v2'
        or qplan['raw_provenance']['schema']!='chess.queen-coach-sft-output.v2'
        or qplan['raw_provenance']['adapter_sha256']!='7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349'):
        raise ValueError('Actual qualified direct old-SFT profile required')
    plan=dict(qplan)
    names=[outer.bound(item)for item in qplan['dependencies']]
    names += [Path(__file__),ROOT/'tests/test_chess_existing_checkpoint_comparison_v2.py',Path(design_path),
              Path(qualification_protocol),Path(qualification),Path(worker),Path(audit),Path(spent_intent)]
    for item in ('closed_original_training_audit','closed_corpus_audit'):
        names.append(outer.bound(design[item]))
    names += [ROOT/'scripts/chess_queen_coach_counterfactual_train_v1.py',
              ROOT/'scripts/chess_queen_coach_counterfactual_eval_v1.py']
    plan.update(schema='chess.existing-coach-checkpoint-fresh-comparison.v1',mode='heldout',
        frozen_at=datetime.now(timezone.utc).isoformat(),design=bind(design_path),
        input_rows=design['inputs'],heldout_references=design['references'],
        conditions={name:design['conditions'][name]for name in design['condition_order']},
        condition_labels=design['condition_labels'],condition_order=design['condition_order'],
        planned=96,source_game_groups=16,reserved_source_games=512,no_new_training=True,
        phase_maximum_seconds=4500,admission_latest_utc=design['whole_phase_admission_latest_utc'],
        cutoff_utc=design['cutoff_utc'],effective_request_guard_seconds=None,
        resource_policy_metadata_seconds=120,resource_policy_timer_enforced=False,
        spent_cohort_intent=bind(spent_intent),
        qualification_protocol=bind(qualification_protocol),successful_qualification=bind(qualification),
        closed_qualification_worker=bind(worker),qualification_audit=bind(audit),
        qualification_worker_script=qplan['expected_worker_script'],
        qualification_worker_arguments=qplan['expected_worker_arguments'],
        future_spent_policy=design['future_spent_policy'],
        interpretation=design['claims'],metrics=design['metrics'],
        dependencies=[bind(p)for p in dict.fromkeys(names)])
    outer.verify(plan)  # Requires actual2request software success and its exact independent audit.
    with Path(out).open('x',encoding='utf-8')as stream:
        json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return bind(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('design','qualification-protocol','qualification','worker','audit','spent-intent','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.design,args.qualification_protocol,args.qualification,args.worker,args.audit,args.spent_intent,args.out)))
