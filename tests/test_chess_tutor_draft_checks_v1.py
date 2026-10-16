"""Authored software fixtures only: no models, engines or quality measurements."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import chess
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / 'prototype/chess_tutor_v1'
sys.path.insert(0, str(PROTO))
import draft_checks_v1 as audit
import coaching_jobs as jobs


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


def atom(board, uci):
    move = chess.Move.from_uci(uci)
    def square(s):
        return '<SQUARE_' + str((s if board.turn else s ^ 56) + 1) + '>'
    def piece(p):
        return '<PIECE_' + ('M' if p.color == board.turn else 'O') + p.symbol().upper() + '>'
    victim = chess.Piece(chess.PAWN, not board.turn) if board.is_en_passant(move) else board.piece_at(move.to_square)
    return piece(board.piece_at(move.from_square)) + square(move.from_square) + (piece(victim) if victim else '') + square(move.to_square) + (piece(chess.Piece(move.promotion, board.turn)) if move.promotion else '')


def fixture(fen=chess.STARTING_FEN, move='e2e4', phrase='does not give check', capture=None, *, selected=None, best=None, prefix='', suffix=''):
    board = chess.Board(fen)
    packet = {'fen': board.fen()}
    if selected:
        packet['selected_uci'] = selected
    captured = audit._victim(board, chess.Move.from_uci(move))
    if capture is None:
        cap = 'It does not capture a piece.' if captured is None else 'It captures <PIECE_O' + captured['piece'][0].upper().replace('K', 'N') + '>.'
        if captured and captured['piece'] == 'king':
            cap = 'It captures <PIECE_OK>.'
    else:
        cap = capture
    raw = prefix + 'ANALYSIS:\nThe move ' + atom(board, move) + ' ' + phrase + '. ' + cap + suffix + '\nBEST_MOVE: ' + atom(board, best or move) + '\nCRITICAL_LINE:\nPROMISING_MOVES:\nEVALUATION: Not assessed'
    response = {'status': 'completed', 'finish_reason': 'eos', 'input': packet, 'raw_text': raw,
                'decoded_text': 'Different translated display text: 😀', 'parsed': {'untouched': ['exact', 1]}}
    context = {'fen': board.fen(), 'selected_uci': selected}
    return packet, response, context


def run_case(values, **changes):
    packet, response, context = values
    input_bytes = encoded(packet)
    arguments = dict(response_bytes=encoded(response), input_bytes=input_bytes,
                     input_sha256=audit.digest(input_bytes), packet=packet, context=context,
                     base_result=copy.deepcopy(response), qualified=True)
    arguments.update(changes)
    return audit.audit_bytes(**arguments)


@pytest.mark.parametrize('fen,move,phrase', [
    (chess.STARTING_FEN, 'e2e4', 'does not give check'),
    (chess.STARTING_FEN.replace(' w ', ' b '), 'e7e5', 'does not give check'),
    ('6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1', 'g5d8', 'gives checkmate'),
    ('6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1', 'g5d8', 'gives check'),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2', 'e5d6', 'does not give check'),
    ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7a8q', 'gives check'),
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1', 'does not give check'),
    ('7k/8/8/8/8/8/R7/K7 w - - 149 76', 'a2a8', 'gives check'),
    ('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5', 'does not give check'),
    ('4k3/8/8/8/8/8/4B3/4R1K1 w - - 0 1', 'e2b5', 'gives check'),
])
def test_legal_root_facts_black_pov_and_special_moves(fen, move, phrase):
    values = fixture(fen, move, phrase)
    result = run_case(values)
    assert result['status'] == 'checked'
    assert [row['status'] for row in result['claims']] == ['supported', 'supported']
    assert result['move_observations']['move_uci'] == move
    assert result['whole_prose_assessed'] is False
    raw = values[1]['raw_text']
    for row in result['claims']:
        s = row['span']
        assert s['unit'] == 'unicode_code_points'
        assert raw[s['start']:s['end']] == row['exact_raw_text']
        assert audit.digest(row['exact_raw_text'].encode()) == s['sha256']


def test_contradictions_do_not_repair_raw_or_confuse_analysis_best_and_selected():
    values = fixture(move='g1f3', phrase='gives checkmate', capture='It captures <PIECE_OQ>.', selected='e2e4', best='e2e4')
    original = copy.deepcopy(values[1])
    result = run_case(values)
    assert [r['status'] for r in result['claims']] == ['contradicted', 'contradicted']
    assert all(r['analysis_move_uci'] == 'g1f3' and r['analysis_move_san'] == 'Nf3' for r in result['claims'])
    assert result['selected_identity']['status'] == 'supported'
    assert result['analysis_alignment']['status'] == 'contradicted'
    assert result['move_observations']['move_uci'] == 'e2e4'
    assert values[1] == original
    other = run_case(fixture(selected='d2d4'))
    assert other['selected_identity']['status'] == 'contradicted'


@pytest.mark.parametrize('prefix,suffix', [
    ('If a different variation occurs then\n', ''), ('<script>untrusted</script>\n', ''),
    ('A note before the section.\n', ''), ('', ' If a reply changes the position.'),
    ('', ' The move is only a hypothetical alternative.'), ('', ' "Quoted claim."'),
])
def test_unknown_prefix_conditional_and_extra_prose_abstain(prefix, suffix):
    result = run_case(fixture(prefix=prefix, suffix=suffix))
    assert result['claims'] == [] and result['unassessed_regions']
    assert result['status'] == 'unassessed'
    assert result['move_observations']['status'] == 'observed'


@pytest.mark.parametrize('alter', [
    lambda text: text + '\nANALYSIS: another section',
    lambda text: text + '\nBEST_MOVE: <PIECE_MP><SQUARE_13><SQUARE_29>',
    lambda text: text.replace('The move ', 'The move <PIECE_MX>'),
    lambda text: text.replace('<SQUARE_29>', '<SQUARE_37>'),
    lambda text: text.replace('<PIECE_MP>', '<PIECE_MN>'),
    lambda text: text.replace('It does not capture a piece.', 'Other text. It does not capture a piece.'),
])
def test_ambiguous_or_invalid_descriptions_never_gain_supported_claims(alter):
    values = fixture()
    values[1]['raw_text'] = alter(values[1]['raw_text'])
    result = run_case(values)
    assert not any(row['status'] == 'supported' for row in result['claims'])


@pytest.mark.parametrize('change', ['input_hash', 'same_path_bytes', 'packet', 'context_fen', 'context_selected', 'response_snapshot', 'duplicate_json', 'nonfinite_json'])
def test_binding_failures_hard_reject(change):
    values = fixture()
    kwargs = {}
    if change == 'input_hash': kwargs['input_sha256'] = '0'*64
    elif change == 'same_path_bytes': kwargs['input_bytes'] = encoded({'fen': chess.STARTING_FEN, 'unexpected': True})
    elif change == 'packet': kwargs['packet'] = {'fen': 'changed'}
    elif change == 'context_fen': kwargs['context'] = {'fen': 'changed', 'selected_uci': None}
    elif change == 'context_selected': kwargs['context'] = {'fen': chess.STARTING_FEN, 'selected_uci': 'd2d4'}
    elif change == 'response_snapshot': kwargs['response_bytes'] = encoded({**values[1], 'raw_text': 'changed'})
    elif change == 'duplicate_json': kwargs['response_bytes'] = b'{"status":"a","status":"b"}'
    elif change == 'nonfinite_json': kwargs['response_bytes'] = b'{"value":NaN}'
    with pytest.raises(audit.BindingError): run_case(values, **kwargs)


def test_noncompleted_unqualified_and_terminal_drafts_are_not_assessed():
    assert run_case(fixture(), qualified=False)['claims'] == []
    values = fixture(); values[1]['status'] = 'partial'
    assert run_case(values)['status'] == 'unassessed'
    board = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
    packet = {'fen': board.fen()}; response = {'status': 'completed', 'finish_reason': 'eos', 'input': packet, 'raw_text': 'ANALYSIS: Unsupported'}
    result = run_case((packet, response, {'fen': board.fen(), 'selected_uci': None}))
    assert result['status'] == 'unassessed' and 'already over' in result['reason']


def test_unicode_span_is_not_a_byte_or_utf16_offset():
    text = '😀 gives check'
    value = audit.span(text, 2, len(text))
    assert value['start'] == 2 and text[value['start']:value['end']] == 'gives check'
    assert value['sha256'] == audit.digest(b'gives check')


def test_parser_pin_failure_is_not_silently_accepted(monkeypatch):
    monkeypatch.setattr(audit, 'NATIVE_SHA256', '0'*64)
    with pytest.raises(audit.BindingError, match='parser changed'): run_case(fixture())


def test_prior_automatic_draw_history_never_receives_root_claim_verdicts():
    board = chess.Board(); history = []
    for uci in ['g1f3', 'g8f6', 'f3g1', 'f6g8']*4:
        history.append(board.fen()); board.push_uci(uci)
    assert board.is_fivefold_repetition()
    packet = {'fen': board.fen(), 'history': history}
    response = {'status': 'completed', 'finish_reason': 'eos', 'input': packet, 'raw_text': 'ANALYSIS: No claim'}
    result = run_case((packet, response, {'fen': board.fen(), 'selected_uci': None}))
    assert result['claims'] == [] and 'already over' in result['reason']


def test_wrong_promotion_identity_abstains():
    values = fixture('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7a8q', 'gives check')
    values[1]['raw_text'] = values[1]['raw_text'].replace('<PIECE_MQ>', '<PIECE_OQ>')
    assert not run_case(values)['claims']


def test_original_profile_admission_is_separate_from_trained_or_fixture():
    result = {'execution': {'qualification_sha256': audit.QUALIFICATION_SHA256, 'canonical_provenance': {'response_binding_verified': True}}}
    worker = {'status': 'completed', 'exit_code': 0, 'child_exited_before_lease_release': True}
    assert audit.original_profile(result, worker, False, 'queen-runtime.json')
    assert not audit.original_profile(result, worker, True, 'queen-runtime.json')
    assert not audit.original_profile(result, worker, False, 'queen-tuned-runtime-v1.json')
    assert not audit.original_profile(result, {**worker, 'status': 'failed'}, False, 'queen-runtime.json')


def test_controller_keeps_raw_bytes_and_exports_sibling_evidence(tmp_path):
    packet, response, context = fixture(selected='e2e4')
    input_path = tmp_path/'input.json'; output = tmp_path/'response.json'
    input_path.write_bytes(encoded(packet)); output.write_bytes(encoded(response))
    before = output.read_bytes(); original = copy.deepcopy(response)
    runner = type('AuthoredFakeRunner', (), {'qualification_path': Path('queen-runtime.json')})()
    controller = jobs.CoachingJobs(tmp_path, None, runner)
    job = {'status': 'completed', 'fixture': False, 'request_id': 'authored-software-fixture', 'out': output,
           'input': input_path, 'input_sha256': audit.digest(input_path.read_bytes()),
           'request_packet': packet, 'context': context}
    decorated = {**response, 'execution': {'qualification_sha256': audit.QUALIFICATION_SHA256, 'canonical_provenance': {'response_binding_verified': True}}}
    worker = {'status': 'completed', 'exit_code': 0, 'child_exited_before_lease_release': True}
    result = controller._draft_checks(job, decorated, worker, response)
    assert result['status'] == 'checked' and result['request_id'] == job['request_id']
    assert output.read_bytes() == before and response == original
    assert json.loads((tmp_path/'draft-checks-v1.json').read_bytes()) == result
    # Create-only retention refuses overwrite and leaves raw/old metadata intact.
    assert controller._draft_checks(job, decorated, worker, response)['status'] == 'unavailable'
    assert output.read_bytes() == before


def test_parser_and_full_check_can_run_with_heavy_backends_forbidden():
    program = '''
import builtins,sys
sys.path.insert(0,sys.argv[1])
old=builtins.__import__
def guarded(name,*a,**kw):
 if name.split('.')[0] in {'torch','transformers','bitsandbytes'} or name=='chess.engine':raise AssertionError(name)
 return old(name,*a,**kw)
builtins.__import__=guarded
import draft_checks_v1
import json
packet,response,context=json.loads(sys.argv[2])
ib=json.dumps(packet,ensure_ascii=False).encode()
rb=json.dumps(response,ensure_ascii=False).encode()
result=draft_checks_v1.audit_bytes(rb,ib,draft_checks_v1.digest(ib),packet,context,response,qualified=True)
assert result['status']=='checked' and all(r['status']=='supported' for r in result['claims'])
assert not any(n.split('.')[0] in {'torch','transformers','bitsandbytes'} for n in sys.modules)
'''
    subprocess.run([sys.executable, '-c', program, str(PROTO), json.dumps(fixture())], check=True, capture_output=True, text=True)
