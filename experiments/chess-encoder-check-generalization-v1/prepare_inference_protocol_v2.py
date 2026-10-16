"""Freeze only the strengthened inference guard; no backend imports or calls."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def binding(path):
    return {'path':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    old=ROOT/'scripts/chess_encoder_check_generalization_eval_v1.py'
    new=ROOT/'scripts/chess_encoder_check_generalization_eval_v2.py'
    old_functions={node.name:node for node in ast.parse(old.read_text()).body if isinstance(node,ast.FunctionDef)}
    new_functions={node.name:node for node in ast.parse(new.read_text()).body if isinstance(node,ast.FunctionDef)}
    assert set(new_functions)==set(old_functions)|{'guard_for'}
    new_run=new_functions['run']
    for node in ast.walk(new_run):
        if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='guard_for':
            node.func=ast.Attribute(value=ast.Name(id='head',ctx=ast.Load()),attr='guard_for',ctx=ast.Load())
    assert all(ast.dump(node)==ast.dump(new_functions[name])for name,node in old_functions.items())
    plan=json.loads((HERE/'inference-protocol.json').read_text())
    plan.update(schema='chess.encoder-check-generalization-inference.v2',
        frozen_at=datetime.now(timezone.utc).isoformat(), implementation_sha256=binding(new)['sha256'])
    for item in plan['dependencies']:
        if item['path']=='tests/test_chess_encoder_check_generalization_eval_v1.py':
            item.update(binding(ROOT/'tests/test_chess_encoder_check_generalization_eval_v2.py'))
    plan['dependencies'] += [binding(old),binding(HERE/'inference-protocol.json'),binding(Path(__file__))]
    plan['resources']='Root-owned inference only. Start >=6GiB physical/8GiB commit/4GiB GPU available; running >=4GiB physical/6GiB commit/1GiB GPU. At most one resource sample per second; cancellation and deadlines checked on every guard invocation. Owned CANCEL/900s/13UTC checks; no settings changes, no optimizer or training.'
    plan['amendment']='Guard-only strengthening of unexecuted published v1: running GPU reserve512MiB to1GiB. All science, data, checkpoints, conditions, feature extraction, raw logits, full denominators and label embargo unchanged. Function ASTs match v1 after normalizing the owned guard call.'
    plan['prior_unexecuted_protocol']=binding(HERE/'inference-protocol.json')
    target=HERE/'inference-protocol-v2.json'
    if target.exists():raise ValueError('Frozen protocol is create-only')
    target.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'protocol':binding(target),'source':binding(new),'scientific_function_AST_equal':True}))


if __name__=='__main__':main()
