"""CPU admission boundaries and unchanged scientific functions; no learned calls."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_train_v1 as old
import chess_queen_coach_counterfactual_train_v2 as current


def test_training_admission_closes_at1100_while_old1115_contract_is_preserved():
    plan={'admission_latest_utc':'2026-10-16T11:00:00+00:00'}
    current.admit(plan,datetime(2026,10,16,10,59,59,tzinfo=timezone.utc))
    for minute in (0,1,15,30):
        with pytest.raises(RuntimeError,match='11:00'):
            current.admit(plan,datetime(2026,10,16,11,minute,tzinfo=timezone.utc))
    old.admit({'admission_latest_utc':'2026-10-16T11:15:00+00:00'},datetime(2026,10,16,11,14,59,tzinfo=timezone.utc))


def test_scientific_and_failure_accounting_functions_are_unchanged_from_frozen_v1():
    def functions(module):
        tree=ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
        return {node.name:ast.dump(node,include_attributes=False)for node in tree.body if isinstance(node,ast.FunctionDef)}
    before=functions(old);after=functions(current)
    changed={'verify_protocol','admit','main'}
    assert before.keys()==after.keys()
    assert all(before[name]==after[name]for name in before.keys()-changed)
    assert before['train']==after['train']and before['score_panel']==after['score_panel']


def test_training_entrypoint_cannot_dispatch_preserved_single_process_held_mode(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'argv',['new-trainer','heldout','--out',str(tmp_path/'never')])
    with pytest.raises(SystemExit)as result:current.main()
    assert result.value.code==2 and not(tmp_path/'never').exists()
