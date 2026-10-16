"""Malformed text-prefix authored fixtures; no actual corpus or backend."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import chess
import pytest
import targets
import evaluate_v2 as evaluate

@pytest.mark.parametrize('fault',['before','other_section'])
def test_third_clause_requires_same_section_preceding_legal_second_clause(fault):
    raw,old,facts=targets.target(chess.STARTING_FEN,['e2e4','e7e5','g1f3'])
    second=evaluate.PLY2.search(raw).group(0);third=evaluate.PLY3.search(raw).group(0)
    body,fields=raw.split('\nBEST_MOVE:',1)
    root=body.replace(second,'').replace(third,'')
    if fault=='before':wrong=root+' '+third+' '+second+'\nBEST_MOVE:'+fields
    else:wrong=root+' '+second+'\nANALYSIS: '+third+'\nBEST_MOVE:'+fields
    result=evaluate.facts({'fen':chess.STARTING_FEN},wrong,3)
    ply3=[claim for claim in result['recognized_branch_claims']if claim['ply']==3]
    assert len(ply3)==2 and all(claim['true']is None for claim in ply3)
    assert result['unknown_branch_claims']==2
    assert not result['all_required_conditional_facts_true']

def test_valid_order_preserves_all_four_true_branch_claims():
    raw,_,_=targets.target(chess.STARTING_FEN,['e2e4','e7e5','g1f3'])
    result=evaluate.facts({'fen':chess.STARTING_FEN},raw,3)
    assert result['true_branch_claims']==4 and result['all_required_conditional_facts_true']
