"""Authored CPU responses: no historical held content or model calls."""
from pathlib import Path
import sys
import chess
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_eval_v1 as subject
import chess_queen_coach_sft_intake_v1 as verified

FEN='8/8/8/4k3/8/8/5P2/K7 w - - 0 1'


def response(move='f2f4',fen=FEN,pv=None):
    target,_=verified.verified_target(fen,pv or[move])
    return {'status':'completed','finish_reason':'eos','raw_text':target}


def scored(raw,selected='f2f4'):
    return subject.score({'fen':FEN,'selected_uci':selected},raw,{'reference_pv_uci':[selected]})


def test_complete_single_aligned_check_and_capture_target_joint_success():
    result=scored(response())
    assert result['joint_selected_facts_correct']and result['analysis_to_best_alignment']
    assert result['facts']['true_claims']==2 and result['facts']['false_claims']==0
    assert result['supplied_first_ply_is_prediction']is False


def test_true_facts_for_other_move_cannot_score_given_move_joint_success():
    raw=response();other=response('f2f3')['raw_text'].split('\nBEST_MOVE:')[0]
    raw['raw_text']=other+'\nBEST_MOVE:'+raw['raw_text'].split('\nBEST_MOVE:',1)[1]
    result=scored(raw)
    assert result['accepted_best_uci']=='f2f4'and result['facts']['true_claims']==2
    assert result['facts']['analysis_move_uci']=='f2f3'and not result['joint_selected_facts_correct']


@pytest.mark.parametrize('kind',['duplicate_move','duplicate_analysis','duplicate_capture','contradiction','duplicate_best','partial','missing_capture','missing_analysis'])
def test_ambiguous_duplicate_incomplete_partial_or_contradictory_cannot_joint_succeed(kind):
    raw=response();text=raw['raw_text'];analysis=text.split('\n')[0];capture='It does not capture a piece.'
    if kind=='duplicate_move':text=text.replace(capture,capture+' '+analysis.removeprefix('ANALYSIS: '),1)
    elif kind=='duplicate_analysis':text=analysis+'\n'+text
    elif kind=='duplicate_capture':text=text.replace(capture,capture+' '+capture,1)
    elif kind=='contradiction':text=text.replace(capture,capture+' '+analysis.removeprefix('ANALYSIS: ').replace('gives check.','does not give check.'),1)
    elif kind=='duplicate_best':text+='\n'+next(line for line in text.splitlines()if line.startswith('BEST_MOVE:'))
    elif kind=='partial':raw['status']='partial';raw['finish_reason']='max_new_tokens'
    elif kind=='missing_capture':text=text.replace(capture,'',1)
    else:text=text.split('\n',1)[1]
    raw['raw_text']=text;result=scored(raw)
    assert not result['joint_selected_facts_correct']
    assert not result['facts']['whole_prose_factuality_measured']
    if kind=='contradiction':assert result['facts']['false_claims']>=1
    if kind=='duplicate_capture':assert result['facts']['unknown_claims']==1


def test_recognized_spans_are_actual_raw_substrings_and_unknown_prose_stays_unaudited():
    raw=response();value=scored(raw)
    for claim in value['facts']['claims']:
        start,end=claim['span'];assert raw['raw_text'][start:end]==claim['text']
    raw['raw_text']='ANALYSIS: Chess is complicated.\nBEST_MOVE:\nCRITICAL_LINE:'
    value=scored(raw);assert value['facts']['recognized_claims']==0 and not value['joint_selected_facts_correct']


def test_conditional_continuation_excludes_supplied_first_ply_prediction():
    pv=['e2e4','e7e5','g1f3'];raw=response(fen=chess.STARTING_FEN,pv=pv)
    value=subject.score({'fen':chess.STARTING_FEN,'selected_uci':'e2e4'},raw,{'reference_pv_uci':pv})
    assert value['selected_conditional_reply_agreement']and value['selected_conditional_two_reply_agreement']
    assert value['supplied_first_ply_is_prediction']is False


def test_pair_requires_both_selected_cases_and_full_planned_rows():
    rows=[{'case_id':mode,'group_id':'game','mode':mode,
        'input':{'fen':FEN,**({'selected_uci':move}if mode!='free'else{})}}
        for mode,move in[('free','f2f4'),('selected_a','f2f4'),('selected_b','f2f3')]]
    refs={row['case_id']:{'reference_pv_uci':[row['input'].get('selected_uci','f2f4')]}for row in rows}
    raw=[response(),response(),response('f2f3')]
    result=subject.panel(rows,raw,refs)
    assert result['counts']['matched_selected_pairs_joint_correct']==1
    raw[-1]={'status':'not_run','raw_text':''}
    result=subject.panel(rows,raw,refs)
    assert result['counts']['planned']==3 and result['counts']['matched_selected_pairs_joint_correct']==0
    with pytest.raises(ValueError,match='denominator'):subject.panel(rows,raw[:2],refs)
