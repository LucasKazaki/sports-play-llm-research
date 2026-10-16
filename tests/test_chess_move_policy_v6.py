"""CPU software fixtures for the v6 objective, selector and eligible forecast set."""
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chess_move_policy_v6 as policy
from chess_classifier_adapter import expected_action_space


def tensors():
    torch=pytest.importorskip('torch')
    logits=torch.zeros((1,1968),dtype=torch.float64,requires_grad=True)
    target=torch.tensor([5],dtype=torch.long)
    mask=torch.zeros((1,1968),dtype=torch.bool)
    mask[0,[5,10]]=True
    return torch,logits,target,mask


def test_objective_matches_full_class_ce_and_legal_probability_mass():
    torch,logits,target,mask=tensors()
    total,ce,mass=policy.objective(logits,target,mask)
    assert float(ce.detach())==pytest.approx(float(torch.log(torch.tensor(1968.,dtype=torch.float64))))
    assert float(mass.detach())==pytest.approx(float(torch.log(torch.tensor(984.,dtype=torch.float64))))
    assert float(total.detach())==pytest.approx(float((ce+mass).detach()))
    # A masked two-class CE would equal log(2), which this full-vocabulary CE does not.
    assert float(ce.detach())>7


def test_one_cpu_gradient_update_reduces_illegal_probability_without_inference_mask():
    torch,logits,target,mask=tensors()
    initial=logits.detach().softmax(dim=1)[~mask].sum()
    total,_,_=policy.objective(logits,target,mask)
    total.backward()
    assert bool(torch.isfinite(logits.grad).all())
    assert float(logits.grad[0,0])>0 and float(logits.grad[0,5])<0
    updated=logits.detach()-.5*logits.grad
    assert updated.softmax(dim=1)[~mask].sum()<initial
    assert updated.shape==(1,1968)


def test_large_logits_remain_numerically_stable():
    torch,logits,target,mask=tensors()
    logits=logits.detach()+10000
    total,ce,mass=policy.objective(logits,target,mask)
    assert bool(torch.isfinite(total)) and float(mass)>=0


@pytest.mark.parametrize('defect',['empty','illegal_target','nonfinite','wrong_shape','wrong_mask_dtype'])
def test_invalid_objective_inputs_fail_instead_of_silently_dropping_classes(defect):
    torch,logits,target,mask=tensors()
    if defect=='empty': mask[:]=False
    if defect=='illegal_target': target[0]=0
    if defect=='nonfinite': logits=logits.detach().fill_(float('nan'))
    if defect=='wrong_shape': logits=logits[:,:1967]
    if defect=='wrong_mask_dtype': mask=mask.float()
    with pytest.raises(ValueError): policy.objective(logits,target,mask)


def score(legal,match):
    return {'count':512,'raw_legal_count':legal,'raw_top1_match_count':match}


def test_995_per_thousand_raw_legality_precedes_teacher_agreement():
    results={0:score(509,450),256:score(510,300),512:score(512,299)}
    selected=max(results,key=lambda k:policy.selection_key(k,results[k]))
    assert selected==256
    assert policy.selection_key(0,results[0])[0]==0
    assert policy.selection_key(256,results[256])[0]==1


def test_eligible_ties_prefer_agreement_then_legality_then_earliest():
    results={0:score(510,400),256:score(511,400),512:score(511,400)}
    assert max(results,key=lambda k:policy.selection_key(k,results[k]))==256


def test_fallback_when_no_checkpoint_is_eligible_is_predeclared_teacher_then_legality():
    results={0:score(509,400),256:score(508,401),512:score(507,401)}
    assert not any(policy.selection_key(k,r)[0] for k,r in results.items())
    assert max(results,key=lambda k:policy.selection_key(k,results[k]))==256


def candidate(case,ordinal,pv=('e2e4','e7e5','g1f3'),status='completed'):
    return {'id':case,'game_id':case,'source_ordinal':ordinal,'fen':chess.STARTING_FEN,
            'reference_pv':list(pv),'status':status}


def test_rollout_selects_source_order_not_completion_order_and_retains_all_rejections():
    rows=[candidate('later',50),candidate('short',20,('e2e4',)),
          candidate('failed',10,(),status='failed'),candidate('first',30),candidate('remainder',60)]
    selected,audit=policy.choose_rollout(rows,2)
    assert [r['id'] for r in selected]==['first','later']
    assert audit['planned_candidates']==5 and len(audit['outcomes'])==5
    assert audit['reasons']=={'teacher_failed':1,'short_reference':1,'selected':2,
                              'eligible_reservoir_remainder':1}


def test_illegal_teacher_third_ply_never_qualifies_for_forecast():
    selected,audit=policy.choose_rollout([candidate('bad',0,('e2e4','e7e5','a1a8'))],1)
    assert selected==[] and audit['reasons']=={'invalid_reference':1}


def test_automatic_terminal_state_before_third_reference_ply_is_not_three_ply_support():
    row=candidate('automatic-draw',0,('a2a8','h8h7','a8a7'))
    row['fen']='7k/8/8/8/8/8/R7/K7 w - - 149 76'
    selected,audit=policy.choose_rollout([row],1)
    assert selected==[] and audit['reasons']=={'terminal_reference':1}


def test_insufficient_reservoir_remains_insufficient_not_silently_replenished():
    selected,audit=policy.choose_rollout([candidate('one',0),candidate('short',1,('e2e4',))],2)
    assert len(selected)==1 and audit['selected']==1 and audit['planned_candidates']==2


def test_training_legal_actions_use_actual_board_and_include_special_moves():
    actions=expected_action_space()
    contract={'label2id':{move:i for i,move in enumerate(actions)}}
    initial=policy.legal_action_indices(chess.STARTING_FEN,contract)
    assert len(initial)==20 and contract['label2id']['a1a8'] not in initial
    fen='r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
    legal=policy.legal_action_indices(fen,contract)
    assert contract['label2id']['e1g1'] in legal and contract['label2id']['e1c1'] in legal


def test_cpu_teacher_resource_policy_can_reduce_concurrency_or_stop(monkeypatch,tmp_path):
    import chess_native_resources as resources
    def sample(available):
        return resources.Sample(32*resources.GIB,available*resources.GIB,
            64*resources.GIB,(64-available)*resources.GIB,16*resources.GIB,8*resources.GIB)
    monkeypatch.setattr(resources,'windows_sample',lambda:sample(8))
    assert policy.cpu_workers({'teacher':{'resource_rule':'frozen fixture'}},tmp_path)==3
    monkeypatch.setattr(resources,'windows_sample',lambda:sample(5))
    with pytest.raises(RuntimeError,match='no calls started'):
        policy.cpu_workers({'teacher':{'resource_rule':'frozen fixture'}},tmp_path)
