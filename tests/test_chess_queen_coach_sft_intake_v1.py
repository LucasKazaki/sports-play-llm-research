"""CPU rule, provenance and failure-ledger tests; no real engine/model calls."""
import importlib.util
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_intake_v1 as app


@pytest.mark.parametrize('fen,moves',[
    (chess.STARTING_FEN,['e2e4','e7e5','g1f3']),
    ('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',['e7e5','g1f3','b8c6']),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',['e5d6']),
    ('4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1',['e4d3']),
    ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1',['a7a8q']),
    ('4k3/8/8/8/8/8/p7/4K3 b - - 0 1',['a2a1n']),
    ('4k3/8/8/8/8/8/8/4K2R w K - 0 1',['e1g1']),
    ('4k2r/8/8/8/8/8/8/4K3 b k - 0 1',['e8g8']),
    ('6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',['g5d8']),
    ('7k/8/5KQ1/8/8/8/8/8 w - - 0 1',['g6f7']),
])
def test_native_targets_roundtrip_both_modes_and_pov_with_special_moves(fen,moves):
    text,facts=app.verified_target(fen,moves)
    for selected in (False,True):
        packet={'fen':fen}
        if selected:packet['selected_uci']=moves[0]
        parsed=app.native.parse_output(packet,text)
        assert parsed['accepted_move_uci']==moves[0] and parsed['critical_line']['failure'] is None
        assert [row['raw_uci'] for row in parsed['critical_line']['steps']]==moves
    assert len(facts)==len(moves)
    assert 'Not assessed' in text or facts[0]['automatic_game_over']


def test_capture_ep_promotion_castling_and_checkers_come_from_actual_replay():
    ep=app.move_facts(chess.Board('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1'),chess.Move.from_uci('e5d6'))
    assert ep['capture'] and ep['en_passant'] and ep['victim']=='pawn' and ep['victim_square']=='d5'
    text,_=app.verified_target('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',['e5d6'])
    assert '<PIECE_OP>' in text and 'It captures <PIECE_OP>.' in text
    board=chess.Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
    assert app.move_facts(board,chess.Move.from_uci('a7a8q'))['promotion']=='queen'
    board=chess.Board('4k3/8/8/8/8/8/8/4K2R w K - 0 1')
    assert app.move_facts(board,chess.Move.from_uci('e1g1'))['castling']
    # Bishop vacates the e-file, uncovering a stationary rook's check.
    board=chess.Board('4k3/8/8/8/8/8/4B3/K3R3 w - - 0 1')
    facts=app.move_facts(board,chess.Move.from_uci('e2d3'))
    assert facts['gives_check'] and facts['checkers']==['e1'] and facts['discovered_or_double_check']
    assert app.stratum(facts)=='discovered_or_double_check'


def test_terminal_and_bad_references_fail_without_fallback():
    with pytest.raises(ValueError):app.verified_target(chess.STARTING_FEN,['e2e5'])
    with pytest.raises(ValueError):app.verified_target(chess.STARTING_FEN,[])
    with pytest.raises(ValueError):app.verified_target('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1',['h8g8'])
    with pytest.raises(ValueError):app.verified_target('6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',['g5d8','g8f8'])


def test_inputs_are_fen_only_paired_by_original_game_and_references_separate():
    row={'game_id':'Abc12345','puzzle_id':'abc','source_ordinal':1,'fen':chess.STARTING_FEN,
         'teacher_move_uci':'e2e4','reference_pv':['e2e4','e7e5','g1f3']}
    rows,refs=app.case_rows(row)
    assert rows[0]['group_id']==rows[1]['group_id']=='Abc12345'
    assert set(rows[0]['input'])=={'fen'} and set(rows[1]['input'])=={'fen','selected_uci'}
    assert rows[0]['case_id']!=rows[1]['case_id'] and rows[0]['response']==rows[1]['response']
    assert refs[0]['reference_pv_uci']==row['reference_pv'] and 'fen_after' in refs[0]['facts']
    held,_=app.case_rows(row,False)
    assert all('response' not in item for item in held)
    for item in rows:
        assert not set(item['input'])&{'history','facts','evaluation','reference_pv_uci','fen_after','pv','response'}


def test_source_setup_tail_is_ignored_and_before_current_roles_are_globally_disjoint():
    source={'GameId':'Abc12345','PuzzleId':'A1','FEN':chess.STARTING_FEN,'Moves':'e2e4 ILLEGAL_ANSWER_TAIL'}
    split=app.policy.split_for('Abc12345',4082083)
    counts={s:0 for s in app.policy.SPLITS};counts[split]=1
    selected,info=app.policy.select_rows([({'source_ordinal':0},source)],counts,4082083,set(),set(),1)
    row=selected[split][0]
    assert row['setup_uci']=='e2e4' and 'ILLEGAL' not in json.dumps(row)
    with pytest.raises(ValueError,match='cannot fill'):
        app.policy.select_rows([({'source_ordinal':0},source)],counts,4082083,{'Abc12345'},set(),1)
    with pytest.raises(ValueError,match='cannot fill'):
        app.policy.select_rows([({'source_ordinal':0},source)],counts,4082083,set(),{app.policy.board_key(chess.STARTING_FEN)},1)


def test_teacher_intent_unknown_and_never_run_are_separate_and_no_replay(tmp_path):
    tasks=[('train',{'id':'a'}),('train',{'id':'b'}),('holdout',{'id':'c'}),('holdout',{'id':'d'})]
    journal=tmp_path/'journal.jsonl'
    events=[{'event':'intent','id':'a'},{'event':'outcome','id':'a','status':'completed'},
            {'event':'intent','id':'b'},{'event':'outcome','id':'c','status':'not_run'}]
    journal.write_text('\n'.join(json.dumps(e) for e in events)+'\n{"event":')
    rows=app.recover_outcomes(tasks,journal)
    assert [row['status'] for _,row in rows]==['completed','active_unknown','not_run','not_run']
    journal.write_text(json.dumps({'event':'outcome','id':'a','status':'completed'})+'\n')
    with pytest.raises(ValueError,match='invalid teacher completion'):app.recover_outcomes(tasks,journal)


def test_held_selection_has_fixed_priority_and_refuses_short_or_unfilled_support():
    facts={'discovered_or_double_check':True,'mover':'king','gives_check':True,'capture':False}
    assert app.stratum(facts)=='discovered_or_double_check'
    facts['discovered_or_double_check']=False
    assert app.stratum(facts)=='king_mover'
    facts['mover']='pawn';assert app.stratum(facts)=='pawn_mover'
    facts['mover']='queen';assert app.stratum(facts)=='direct_check'
    facts['gives_check']=False;assert app.stratum(facts)=='quiet'
    facts['capture']=True;assert app.stratum(facts)=='noncheck_capture'
    with pytest.raises(ValueError,match='cannot fill'):app.held_roots([])


def test_protocol_source_tamper_rejected_before_source_scan(tmp_path):
    path=tmp_path/'protocol.json';path.write_text(json.dumps({'schema':app.SCHEMA,'implementation_sha256':'0'*64}))
    with pytest.raises(ValueError,match='identity'):app.protocol(path)


def test_retained_exclusion_successors_include_every_legal_teacher_ply():
    row={'game_id':'Abc12345','fen':chess.STARTING_FEN,'source_before_fen':chess.STARTING_FEN,
         'reference_pv':['e2e4','e7e5','g1f3']}
    games=set();boards=set();app.add_reference_roles(row,games,boards)
    replay=chess.Board()
    for move in row['reference_pv']:
        replay.push_uci(move);assert app.policy.board_key(replay.fen()) in boards
    assert games=={'Abc12345'}


def test_teacher_failure_has_durable_intent_and_completion_then_no_further_calls(tmp_path,monkeypatch):
    from types import SimpleNamespace
    class FakeEngine:
        id={'name':'Stockfish19 CPU test fixture'}
        protocol=SimpleNamespace(audit=None)
        calls=0
        def configure(self,options):assert options=={'Threads':1,'Hash':32}
        def analysis(self,*args,**kwargs):self.calls+=1;raise RuntimeError('deliberate fixture failure')
        def close(self):pass
    engine=FakeEngine();monkeypatch.setattr(app.chess.engine.SimpleEngine,'popen',lambda *a,**k:engine)
    tasks=[('train',{'id':str(i),'fen':chess.STARTING_FEN}) for i in range(2)]
    journal=tmp_path/'worker.jsonl'
    app.teacher_worker('unused fixture',{'threads':1,'hash_mb':32,'nodes':50000,'deadline_seconds':30},tasks,journal,tmp_path/'CANCEL')
    records=app.recover_outcomes(tasks,journal)
    assert engine.calls==1 and [r['status'] for _,r in records]==['failed','not_run']
    events=[json.loads(line) for line in journal.read_text().splitlines()]
    assert [e['event'] for e in events]==['engine_opened','intent','outcome','outcome']


def test_new_split_duplicate_original_games_and_board_roles_rejected():
    row={'game_id':'Abc12345','fen':chess.STARTING_FEN,'source_before_fen':chess.STARTING_FEN,'reference_pv':['e2e4']}
    with pytest.raises(ValueError,match='duplicate source game'):app.audit_splits({'train':[row],'holdout':[row]})
    with pytest.raises(ValueError,match='board role'):app.audit_splits({'train':[row],'holdout':[{**row,'game_id':'Diff1234'}]})


def test_teacher_setup_failure_still_closes_full_never_run_outcomes(tmp_path,monkeypatch):
    plan={'teacher':{'workers':3}}
    protocol=tmp_path/'plan.json';protocol.write_text('{}')
    dataset={'protocol_sha256':app.sha(protocol),'splits':{s:[] for s in app.policy.SPLITS}}
    dataset['splits']['train']=[{'id':'a'},{'id':'b'}]
    app.save(tmp_path/'dataset.json',dataset)
    app.save(tmp_path/'intake-completed.json',{'dataset_sha256':app.sha(tmp_path/'dataset.json')})
    monkeypatch.setattr(app,'protocol',lambda path:plan)
    def fail_setup(*args):raise OSError('deliberate source snapshot failure')
    monkeypatch.setattr(app,'snapshot',fail_setup)
    monkeypatch.setattr(app,'ProcessPoolExecutor',lambda **kwargs:pytest.fail('No engine worker may start.'))
    with pytest.raises(OSError,match='snapshot'):app.teachers(protocol,tmp_path)
    closed=app.read(tmp_path/'teachers.json')
    assert closed['statuses']=={'not_run':2} and closed['all_planned_completed'] is False
    assert closed['worker_errors'][0]['stage']=='setup_or_dispatch'
    assert (tmp_path/'teacher-closed.json').exists()
    with pytest.raises(ValueError,match='no replay'):app.teachers(protocol,tmp_path)
