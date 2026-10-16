"""Authored chess/JSON fixtures only; no real corpus, tokenizer, engine or model."""
import ast
import copy
import json
from pathlib import Path
import sys
import chess
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import targets
import evaluate
import prepare


def response(raw,status='completed',finish='eos'):return {'status':status,'finish_reason':finish,'raw_text':raw}
def reference(fen,pv):
    enriched,old,facts=targets.target(fen,pv)
    return enriched,old,{'case_id':'authored:free','group_id':'authored','reference_pv_uci':pv,'facts':facts[0],'per_ply_facts':facts}


@pytest.mark.parametrize('fen,pv',[
    (chess.STARTING_FEN,['e2e4','e7e5','g1f3']),
    ('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',['e7e5','g1f3','b8c6']),
    ('4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1',['d7d5','e5d6','e8f7']),
    ('6k1/P7/8/8/8/8/8/6K1 b - - 0 1',['g8f7','a7a8q','f7g6']),
    ('6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',['g5d8']),
    (chess.STARTING_FEN,['e2e4','e7e5'])])
def test_rule_targets_roundtrip_and_complete_conditional_claims(fen,pv):
    enriched,old,ref=reference(fen,pv)
    actual=evaluate.score({'fen':fen},response(enriched),ref)
    assert actual['joint_conditional_line_facts_correct']
    assert actual['conditional_facts']['true_branch_claims']==2*(len(pv)-1)
    assert actual['conditional_facts']['false_branch_claims']==0
    assert '\nBEST_MOVE:' in enriched and enriched.split('\nBEST_MOVE:')[1:]==old.split('\nBEST_MOVE:')[1:]


def test_only_target_changes_and_selected_input_is_identical():
    fen=chess.STARTING_FEN;pv=['e2e4','e7e5','g1f3'];enriched,old,ref=reference(fen,pv)
    case={'case_id':ref['case_id'],'group_id':ref['group_id'],'mode':'selected_a',
        'input':{'fen':fen,'selected_uci':'e2e4'},'response':old}
    before=json.dumps(case,sort_keys=True);changed=targets.transform_case(case,ref)
    assert changed['response']==enriched and changed['input'] is case['input']
    assert json.dumps(case,sort_keys=True)==before
    assert {key for key in case if case[key]!=changed[key]}=={'response'}


@pytest.mark.parametrize('fault',['future_input','wrong_given','old_target','fact','group','empty_pv'])
def test_corrupt_source_case_fails_without_rewriting_or_dropping(fault):
    fen=chess.STARTING_FEN;pv=['e2e4','e7e5','g1f3'];_,old,ref=reference(fen,pv)
    case={'case_id':ref['case_id'],'group_id':ref['group_id'],'mode':'selected_b','input':{'fen':fen,'selected_uci':'e2e4'},'response':old}
    if fault=='future_input':case['input']['future_fen']='forbidden'
    elif fault=='wrong_given':case['input']['selected_uci']='d2d4'
    elif fault=='old_target':case['response']+=' unsupported prose'
    elif fault=='fact':ref['per_ply_facts'][1]['capture']=True
    elif fault=='group':ref['group_id']='different'
    else:ref['reference_pv_uci']=[]
    with pytest.raises(ValueError):targets.transform_case(case,ref)


@pytest.mark.parametrize('pv',[[],['e2e5'],['e2e4','e7e5','g1f3','b8c6']])
def test_missing_illegal_or_overlong_line_is_not_truncated(pv):
    with pytest.raises(ValueError):targets.target(chess.STARTING_FEN,pv)


def test_automatic_terminal_continuation_fails_whole_target():
    with pytest.raises(ValueError):targets.target('7k/8/8/8/8/8/R7/K7 w - - 149 76',['a2a8','h8h7'])


def test_en_passant_claim_uses_removed_pawn_square_black_rootPOV():
    fen='4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1';pv=['d7d5','e5d6','e8f7']
    enriched,_,ref=reference(fen,pv)
    assert 'captures <PIECE_MP> on <SQUARE_28>' in enriched
    wrong=enriched.replace('captures <PIECE_MP> on <SQUARE_28>','captures <PIECE_MP> on <SQUARE_20>')
    result=evaluate.score({'fen':fen},response(wrong),ref)
    assert result['conditional_facts']['false_branch_claims']==1 and not result['joint_conditional_line_facts_correct']


def test_illegal_conditional_prefix_leaves_later_claims_unassessed():
    enriched,_,ref=reference(chess.STARTING_FEN,['e2e4','e7e5','g1f3'])
    before,fields=enriched.split('\nBEST_MOVE:',1)
    second=evaluate.PLY2.search(before)['move']
    wrong=before.replace(second,'<PIECE_OP><SQUARE_53><SQUARE_29>')+'\nBEST_MOVE:'+fields
    actual=evaluate.score({'fen':chess.STARTING_FEN},response(wrong),ref)
    assert actual['conditional_facts']['unknown_branch_claims']==4
    assert actual['conditional_facts']['invalid_prefix_or_atom_clauses']==2
    assert actual['critical_prefix_matches']['3'] and not actual['joint_conditional_line_facts_correct']


@pytest.mark.parametrize('fault',['duplicate_chain','duplicate_best','partial','missing_chain'])
def test_duplicate_ambiguous_partial_and_missing_chain_prevent_joint_success(fault):
    enriched,old,ref=reference(chess.STARTING_FEN,['e2e4','e7e5','g1f3'])
    if fault=='duplicate_chain':
        clause=evaluate.PLY2.search(enriched).group(0);enriched=enriched.replace('\nBEST_MOVE:',' '+clause+'\nBEST_MOVE:')
    elif fault=='duplicate_best':enriched+='\nBEST_MOVE: '+enriched.split('\nBEST_MOVE: ')[1].splitlines()[0]
    elif fault=='missing_chain':enriched=old
    actual=evaluate.score({'fen':chess.STARTING_FEN},response(enriched,'partial'if fault=='partial'else'completed'),ref)
    assert not actual['joint_conditional_line_facts_correct']
    if fault=='missing_chain':assert actual['conditional_facts']['false_branch_claims']==0


def test_legal_alternative_line_facts_are_separate_from_teacher_agreement():
    alternative,_,_=reference(chess.STARTING_FEN,['e2e4','c7c5','g1f3'])
    _,_,ref=reference(chess.STARTING_FEN,['e2e4','e7e5','g1f3'])
    actual=evaluate.score({'fen':chess.STARTING_FEN},response(alternative),ref)
    assert actual['joint_conditional_line_facts_correct'] and not actual['critical_prefix_matches']['3']
    assert not actual['conditional_facts']['other_prose_audited']


def test_copied_local_rule_helper_functions_are_AST_identical():
    prepare.verify_helpers(HERE.parents[1]/'scripts/chess_queen_coach_sft_intake_v1.py')


def test_group_shape_and_duplicate_schema_risks_rejected():
    data=[{'case_id':str(i),'group_id':'g','mode':mode,'input':{'fen':'authored'}}for i,mode in enumerate(['free','selected_a','selected_b'])]
    assert len(prepare.aligned(data,data,3,1))==3
    bad=copy.deepcopy(data);bad[2]['mode']='selected_a'
    with pytest.raises(ValueError):prepare.aligned(bad,bad,3,1)
    with pytest.raises(ValueError):prepare.aligned(data+[data[0]],data+[data[0]],4,1)
    with pytest.raises(ValueError):prepare.pairs([('input',1),('input',2)])


def test_no_framework_or_engine_backend_loaded():
    assert 'torch' not in sys.modules and 'transformers' not in sys.modules


@pytest.mark.parametrize('length',[512,513])
def test_real_reviewed_formatter_boundary_helper_rejects_overlong_whole_example(length):
    import chess_queen_qlora_v2 as checked
    class Tokenizer:
        def apply_chat_template(self,*args,**kwargs):
            assert kwargs['return_dict']is False
            return [11,12]
        def convert_tokens_to_ids(self,value):assert value=='<|im_end|>';return 99
    observed=[]
    def official(tokenizer,prompt,response,max_length):
        observed.append(max_length)
        ids=[11,12]+[7]*(length-3)+[99]
        return ids,[-100,-100]+ids[2:]
    if length==512:
        ids,labels,prefix=checked.tokenize_training(Tokenizer(),'authored prompt','authored response',official,maximum=512)
        assert len(ids)==512 and prefix==2 and labels[-1]==99
    else:
        with pytest.raises(ValueError,match='exceeds'):checked.tokenize_training(Tokenizer(),'authored','authored',official,maximum=512)
    assert observed==[None]  # Official formatter must receive untruncated full target.
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules
