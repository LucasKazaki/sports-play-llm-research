"""Authored data fixtures only; never open the real corpus or references."""
import json
from pathlib import Path
import sys
import pytest
import chess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chess_queen_counterfactual_coverage_v1 as s

FEN='4k3/8/8/8/8/8/8/Q3K2R w K - 0 1'


def atom(board,uci):
    move=chess.Move.from_uci(uci);p=board.piece_at(move.from_square)
    square=lambda n:n+1 if board.turn else(n^56)+1
    text=f'<PIECE_M{p.symbol().upper()}><SQUARE_{square(move.from_square)}>'
    victim=chess.Piece(chess.PAWN,not board.turn)if board.is_en_passant(move)else board.piece_at(move.to_square)
    if victim:text+=f'<PIECE_O{victim.symbol().upper()}>'
    text+=f'<SQUARE_{square(move.to_square)}>'
    if move.promotion:text+=f'<PIECE_M{chess.piece_symbol(move.promotion).upper()}>'
    return text


def row(group,mode,uci,fen=FEN):
    board=chess.Board(fen)
    return {'case_id':f'queen-counterfactual-v1:{group}:{mode}','group_id':group,'mode':mode,
        'input':{'fen':fen,**({'selected_uci':uci}if mode!='free'else{})},
        'response':'ANALYSIS: authored fixture.\nBEST_MOVE: '+atom(board,uci)+'\nCRITICAL_LINE:\nPROMISING_MOVES:\nEVALUATION: Not assessed'}


def trio(group='AUTHORED',fen=FEN,moves=('a1e5','a1e5','a1a2')):
    return [row(group,mode,uci,fen)for mode,uci in zip(s.MODES,moves)]


def audit(rows,expected=None):return s.audit_lines([json.dumps(value)for value in rows],expected or len(rows))


def test_root_and_presentation_grain_and_deliberate_pair_balance():
    result,_=audit(trio())
    assert result['complete_root_groups']==1 and result['all_presentations']['presentations']==3
    assert result['combined_selected']['check']=={'count':1,'denominator':2,'rate':.5}
    assert result['root_group_coverage']['side_to_move']['counts']=={'white':1}
    assert result['all_presentations']['mover']['counts']['Q']==3
    assert result['root_groups_with_target_piece']['counts']['Q']==1
    assert result['all_presentations']['mover']['counts']['K']==0
    assert result['selected_pairs']['one_check_one_noncheck']==1


def test_black_pov_is_replayed_in_absolute_coordinates():
    fen=chess.Board(FEN).mirror().fen()
    value=s.describe(row('BLACK','selected_a','a8e4',fen))
    assert value['uci']=='a8e4'and value['side']=='black'and value['check']


@pytest.mark.parametrize('fen,uci,flag,mover',[
 ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6','en_passant','P'),
 ('7k/P7/8/8/8/8/8/7K w - - 0 1','a7a8q','promotion','P'),
 ('4k3/8/8/8/8/8/8/4K2R w K - 0 1','e1g1','castling','K')])
def test_special_moves_keep_original_mover_and_capture_semantics(fen,uci,flag,mover):
    value=s.describe(row('SPECIAL','selected_a',uci,fen))
    assert value[flag]and value['mover']==mover
    if flag=='en_passant':assert value['capture']and value['victim']=='P'


def test_king_availability_and_material_are_descriptive_counts():
    result,_=audit(trio())
    coverage=result['root_group_coverage']
    assert coverage['nonpawn_material_bin']['counts']=={'14_38':1}
    assert coverage['material_points_total']['counts']=={'14':1}
    assert sum(coverage['legal_king_move_count']['counts'].values())==1


def test_schema_missing_fields_unknown_input_and_duplicate_best_fail_without_payload():
    rows=trio();rows[0]['response']=None;rows[1]['input']['future_fen']='FORBIDDEN';rows[2]['response']+='\nBEST_MOVE: '+atom(chess.Board(FEN),'a1a2')
    result,_=audit(rows)
    assert result['invalid_rows']==3 and result['missing_required_fields']['counts']['response']==1
    assert result['complete_root_groups']==0 and result['combined_selected']['check']['rate']is None
    text=json.dumps(result)
    assert FEN not in text and 'FORBIDDEN'not in text and 'AUTHORED'not in text


def test_duplicate_cases_and_incomplete_modes_keep_full_denominator():
    rows=trio();rows.append(rows[0]);result,_=audit(rows,3)
    assert result['observed_rows']==4 and result['extra_rows']==1
    assert result['duplicate_case_ids']['keys']==1 and result['duplicate_case_ids']['affected_rows']==2
    assert result['complete_root_groups']==0 and result['group_findings']
    assert result['duplicate_packet_excess_presentations']==1


def test_state_overlap_is_distinct_from_full_fen_and_exact_packet():
    _,a=audit(trio('TRAIN'))
    changed=FEN.replace('0 1','4 9');_,b=audit(trio('DEV',changed))
    assert a['groups'].isdisjoint(b['groups'])and a['cases'].isdisjoint(b['cases'])
    assert len(a['current_board_state_first4']&b['current_board_state_first4'])==1
    assert not(a['full_fen6']&b['full_fen6'])and not(a['generator_packet_inputs']&b['generator_packet_inputs'])


def test_illegal_or_terminal_target_never_becomes_quiet_example():
    value=row('BAD','selected_a','a1a2');value['input']['selected_uci']='a1a3'
    result,_=audit([value],3)
    assert result['invalid_rows']==1 and result['missing_rows']==2
    assert result['all_presentations']['quiet_immediate']['rate']is None


def test_deadline_failure_preserves_requested_count_in_created_attempt(tmp_path):
    protocol=tmp_path/'p.json';protocol.write_text('{}')
    plan={'implementation_sha256':'wrong','dependencies':[]}
    with pytest.raises(ValueError):s.execute(plan,protocol,tmp_path/'out')
    value=json.loads((tmp_path/'out/result.json').read_text())
    assert value['status']=='failed'and value['planned_presentations']=={'train':1536,'development':96}
    assert value['opened_data_files']==[]


def test_import_and_authored_probe_remain_framework_free():
    s.framework_free()


def test_overlap_rates_keep_both_split_denominators_and_empty_unknown():
    assert s.overlap_profile({'one','two'},{'two'})=={'count':1,'train_distinct_denominator':2,
        'development_distinct_denominator':1,'train_rate':.5,'development_rate':1.}
    assert s.overlap_profile(set(),set())['development_rate']is None


def authored_plan(tmp_path):
    corpus=tmp_path/'corpus';corpus.mkdir();files={}
    for name,group,expected in(('train.jsonl','TRAIN',1536),('development.jsonl','DEV',96)):
        path=corpus/name;path.write_text(''.join(json.dumps(value)+'\n'for value in trio(group)))
        files[name]={'path':str(path),'sha256':s.digest(path),'rows':expected}
    manifest=corpus/'manifest.json';manifest.write_text(json.dumps({'files':files,'development_raw_group_ids':['DEV']}))
    plan={'implementation_sha256':s.digest(Path(s.__file__)),'dependencies':[],
        'manifest':{'path':str(manifest),'sha256':s.digest(manifest)},'corpus_root':str(corpus),
        'data_files':files,'cutoff_utc':'2099-01-01T00:00:00+00:00','limitations':['Authored software fixture only']}
    protocol=tmp_path/'plan.json';protocol.write_text(json.dumps(plan));return plan,protocol


def test_full_authored_execution_opens_only_two_exports_and_preserves_missing_denominators(tmp_path):
    plan,protocol=authored_plan(tmp_path);result=s.execute(plan,protocol,tmp_path/'out')
    assert result['status']=='completed'and result['opened_data_files']==['train.jsonl','development.jsonl']
    assert result['splits']['train']['missing_rows']==1533 and result['splits']['development']['missing_rows']==93
    assert result['train_dev_overlap']['groups']['count']==0
    assert result['train_dev_overlap']['current_board_state_first4']['count']==1
    assert not result['frameworks_imported']
    assert 'queen-counterfactual-v1:'not in json.dumps(result)and FEN not in json.dumps(result)


def test_reference_path_rejected_before_any_read_or_hash(tmp_path,monkeypatch):
    plan,protocol=authored_plan(tmp_path);forbidden=tmp_path/'corpus/heldout-references.jsonl'
    plan['data_files']['train.jsonl']['path']=str(forbidden)
    original=s.digest
    def checked(path):
        assert Path(path)!=forbidden,'forbidden reference was accessed'
        return original(path)
    monkeypatch.setattr(s,'digest',checked)
    with pytest.raises(ValueError,match='whitelist'):s.execute(plan,protocol,tmp_path/'out')
    assert json.loads((tmp_path/'out/result.json').read_text())['opened_data_files']==[]
