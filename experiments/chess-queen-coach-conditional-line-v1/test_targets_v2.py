"""Authored selected-mode original output-field semantics; no data/backend."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import chess,pytest
import targets_v2 as targets
import prepare_v3 as prepare
import chess_queen_coach_sft_intake_v1 as original

@pytest.mark.parametrize('mode',['free','selected_a','selected_b'])
@pytest.mark.parametrize('fen,pv',[
    (chess.STARTING_FEN,['e2e4','e7e5','g1f3']),
    ('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1',['e4d5','e8f7','d5d6']),
    ('4k3/8/8/3p4/4P3/8/8/4K3 b - - 0 1',['d5e4','e1f2','e4e3']),
    ('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',['e7e5','g1f3','b8c6'])])
def test_original_selected_promising_semantics_and_analysis_only_change(mode,fen,pv):
    old,root_facts=original.verified_target(fen,pv)
    selected=mode!='free'
    if selected:
        board=chess.Board(fen)
        old=old.replace('PROMISING_MOVES: '+original.move_atom(board,chess.Move.from_uci(pv[0]),board.turn),'PROMISING_MOVES:')
    enriched,immediate,facts=targets.target(fen,pv,selected=selected)
    assert immediate==old
    packet={'fen':fen}
    if selected:packet['selected_uci']=pv[0]
    case={'case_id':'authored','group_id':'authored','mode':mode,'input':packet,'response':old}
    ref={'case_id':'authored','group_id':'authored','reference_pv_uci':pv,'facts':facts[0],'per_ply_facts':facts}
    changed=targets.transform_case(case,ref)
    assert changed['input']is packet and case['response']==old
    assert {key for key in case if case[key]!=changed[key]}=={'response'}
    assert changed['response'].split('\nBEST_MOVE:',1)[1]==old.split('\nBEST_MOVE:',1)[1]
    if selected:assert '\nPROMISING_MOVES:\n' in changed['response']
    else:assert '\nPROMISING_MOVES: <PIECE_' in changed['response']
    assert changed['response']==enriched


def test_selected_case_with_unexpected_bestness_field_is_rejected():
    fen=chess.STARTING_FEN;pv=['e2e4','e7e5','g1f3']
    enriched,old,facts=targets.target(fen,pv) # FREE-style field is wrong for selected source.
    row={'case_id':'authored','group_id':'authored','mode':'selected_a','input':{'fen':fen,'selected_uci':pv[0]},'response':old}
    ref={'case_id':'authored','group_id':'authored','reference_pv_uci':pv,'facts':facts[0],'per_ply_facts':facts}
    with pytest.raises(ValueError,match='Old target text differs'):targets.transform_case(row,ref)


def test_copied_rule_helpers_remain_exact_AST():
    prepare.verify_helpers(Path(__file__).resolve().parents[2]/'scripts/chess_queen_coach_sft_intake_v1.py')
