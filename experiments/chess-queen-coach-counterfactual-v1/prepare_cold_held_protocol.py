"""Freeze fresh held phase only after closed training and actual cold audit."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_cold_eval_v1 as outer
import chess_queen_coach_counterfactual_train_v1 as trainer


def bind(path):
    path=Path(path);path=path if path.is_absolute()else ROOT/path
    return {'path':str(path.relative_to(ROOT))if path.is_relative_to(ROOT)else str(path),'sha256':outer.digest(path)}


def prepare(training_protocol,selection,qualification_protocol,qualification,worker,audit,training_audit,out):
    scientific=trainer.verify_protocol(training_protocol)
    selected=outer.read(selection);trainer.verify_selection(selected,training_protocol)
    run_path=Path(selection).parent/'run.json';completed=outer.read(run_path)
    if(completed.get('status')!='completed'or completed.get('updates_completed')!=192
        or completed.get('presentations_completed')!=1536 or completed.get('partial_accumulation')!=0
        or not completed.get('frozen_storage',{}).get('identical')):
        raise ValueError('Complete unchanged-base192update training required')
    qualification_plan=outer.read(qualification_protocol);outer.verify(qualification_plan)
    if any(qualification_plan['model_runtime'][key]!=scientific[key]for key in('kernel_protocol','kernel_receipt','generation','warm_start')):
        raise ValueError('Actual qualified runtime and trained scientific source differ')
    plan=dict(qualification_plan)
    names=[item['path']for item in qualification_plan['dependencies']+scientific['dependencies']]
    names += [str(Path(__file__)),'tests/test_chess_queen_coach_counterfactual_cold_builder_v1.py',str(selection),str(run_path),str(training_protocol),str(qualification_protocol),str(qualification),str(worker),str(audit),str(training_audit)]
    plan.update(schema='chess.queen-counterfactual-cold-held.v1',mode='heldout',
        frozen_at=datetime.now(timezone.utc).isoformat(),input_rows=scientific['data']['heldout_inputs'],
        heldout_references=scientific['data']['heldout_references'],
        conditions={key:selected[key]for key in('baseline','selected')},
        planned=96,source_game_groups=16,reserved_source_games=512,phase_maximum_seconds=4500,
        qualification_protocol=bind(qualification_protocol),successful_qualification=bind(qualification),
        closed_qualification_worker=bind(worker),qualification_audit=bind(audit),
        qualification_worker_script=qualification_plan['expected_worker_script'],
        qualification_worker_arguments=qualification_plan['expected_worker_arguments'],
        selected_training_protocol=bind(training_protocol),closed_training_audit=bind(training_audit),
        selected_before_held=bind(selection),
        purpose='Fresh16game xFREE/twoopaque suppliedmoves x2fixedconditions. No newtraining/selection. Both48rawledgers close before references open; no oldheldretry.',
        admission='WHOLEouterheldphase must startbefore11:15UTC. Fixed96children are continuations underONElease/job, not newphases. All210schildren/4500sphase/global13UTC and unchangedresources apply.',
        scope='Supplied first move is not prediction. Recognized immediate check/capture and conditionalcontinuations only; wholeprose coaching/Elo remain unmeasured.',
        dependencies=[bind(path)for path in dict.fromkeys(names)])
    outer.verify(plan)
    with Path(out).open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return bind(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('training-protocol','selection','qualification-protocol','qualification','worker','audit','training-audit','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.training_protocol,args.selection,args.qualification_protocol,args.qualification,
        args.worker,args.audit,args.training_audit,args.out)))
