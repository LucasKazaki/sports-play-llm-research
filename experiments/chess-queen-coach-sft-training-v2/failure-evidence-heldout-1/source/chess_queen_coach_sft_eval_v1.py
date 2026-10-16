"""CPU scoring of raw Queen outputs; no generator, rescue or model calls.

Recognized factual claims are deliberately separate from unknown free prose.
Evaluator rules are never supplied as generator features or output repairs.
"""
from __future__ import annotations
import re

import chess
import chess_queen_adapter as native

MOVE_SENTENCE = re.compile(r'\bThe move\s+(?P<move>'+native.MOVE.pattern+
    r')\s+(?P<check_claim>gives checkmate|gives check|does not give check)\.')
CAPTURE = re.compile(r'\bIt captures\s+<PIECE_(?P<side>[MO])(?P<piece>[PNBRQK])>\.')
NO_CAPTURE = re.compile(r'\bIt does not capture a piece\.')
CHECKERS = re.compile(r'\bThe checking pieces? (?:is|are)\s+(?P<body>[^.]+)\.')
CHECKER_ATOM = re.compile(r'<PIECE_(?P<side>[MO])(?P<piece>[PNBRQK])><SQUARE_(?P<square>\d+)>')


def recognized_facts(packet, raw):
    packet, board = native.input_packet(packet)
    sections = {match['name']: match['body'].strip() for match in native.FIELDS.finditer(raw)}
    body = sections.get('ANALYSIS', '')
    result = {'scope': 'Only exact recognized immediate claims; other prose remains unaudited.',
        'recognized_move_sentence': False, 'recognized_claims': 0, 'true_claims': 0,
        'false_claims': 0, 'claims': [], 'check_and_capture_complete': False,
        'other_prose_audited': False}
    sentence = MOVE_SENTENCE.search(body)
    if sentence is None: return result
    result['recognized_move_sentence'] = True
    move, reason = native.parse_atom(sentence, board, board.turn)
    result.update(analysis_move_uci=move.uci() if move else None, native_move_description_error=reason)
    if reason is not None or move is None: return result
    if 'selected_uci' in packet:
        result['selected_move_alignment'] = move.uci() == packet['selected_uci']
    result['truth_scope'] = 'Actual legal move described by the recognized sentence, independently replayed.'
    victim = chess.Piece(chess.PAWN,not board.turn) if board.is_en_passant(move) else board.piece_at(move.to_square)
    after = board.copy(); after.push(move)
    def claim(kind, truth, text):
        result['claims'].append({'kind':kind,'true':bool(truth),'text':text})
    check = sentence['check_claim']
    truth = after.is_checkmate() if check == 'gives checkmate' else (
        after.is_check() if check == 'gives check' else not after.is_check())
    claim('check_or_mate', truth, check)
    # Associate only immediately adjacent grammar with this move. A capture
    # mentioned later in an unrelated variation must not inherit its board.
    position = sentence.end()
    position += len(body[position:])-len(body[position:].lstrip())
    found_capture = CAPTURE.match(body,position); found_negative = NO_CAPTURE.match(body,position)
    if found_capture:
        found = found_capture
        described = chess.Piece(native.PIECES[found['piece']], board.turn if found['side']=='M' else not board.turn)
        claim('capture', victim is not None and victim == described, found.group(0))
    elif found_negative:
        claim('capture', victim is None, found_negative.group(0))
    capture = found_capture or found_negative
    result['check_and_capture_complete'] = capture is not None
    if capture:
        position=capture.end(); position+=len(body[position:])-len(body[position:].lstrip())
    checker = CHECKERS.match(body,position) if capture else None
    if checker:
        found=checker
        atoms = list(CHECKER_ATOM.finditer(found['body']))
        remaining = CHECKER_ATOM.sub('',found['body'])
        if not atoms or not re.fullmatch(r'[\s,]*(?:and[\s,]*)?',remaining):
            result.setdefault('unrecognized_checker_clauses',[]).append(found.group(0))
        else:
            actual = {(square,after.piece_at(square)) for square in after.checkers()}
            described = []
            for atom in atoms:
                number=int(atom['square'])-1
                square=number if board.turn else number^56
                piece=chess.Piece(native.PIECES[atom['piece']],board.turn if atom['side']=='M' else not board.turn)
                described.append((square,piece))
            claim('checking_pieces', len(described)==len(set(described)) and set(described)==actual, found.group(0))
    result.update(recognized_claims=len(result['claims']),
        true_claims=sum(row['true'] for row in result['claims']),
        false_claims=sum(not row['true'] for row in result['claims']))
    return result


def score(packet, response, reference):
    """Score one retained raw response; caller controls closed-heldout timing."""
    packet,_=native.input_packet(packet)
    raw=response.get('raw_text','')
    if not isinstance(raw,str): raise ValueError('Retained raw output must be text')
    parsed=native.parse_output(packet,raw)
    pv=reference.get('reference_pv_uci',[])
    if not isinstance(pv,list) or any(not isinstance(value,str) for value in pv):
        raise ValueError('Reference PV must be an evaluator-only UCI list')
    steps=parsed['critical_line']['steps']; legal=[]
    for step in steps:
        if not step['legal']: break
        legal.append(step['raw_uci'])
    accepted=parsed['accepted_move_uci']
    return {'status':response.get('status','unknown'),'finish_reason':response.get('finish_reason'),
        'complete_eos':response.get('status')=='completed' and response.get('finish_reason')=='eos',
        'raw_best_uci':parsed['raw_choice_uci'],'raw_best_legal':parsed['raw_choice_is_legal'],
        'native_best_description_valid':parsed['description_valid'],
        'accepted_best_uci':accepted,'accepted_best_legal':accepted is not None,
        'raw_teacher_best_agreement':bool(pv) and parsed['raw_choice_is_legal'] and parsed['raw_choice_uci']==pv[0],
        'accepted_teacher_best_agreement':bool(pv) and accepted==pv[0],
        'selected_given_consistency':accepted==packet['selected_uci'] if 'selected_uci'in packet else None,
        'reference_plies':len(pv),'legal_critical_prefix_plies':len(legal),
        'critical_prefix_matches':{str(depth):len(pv)>=depth and len(legal)>=depth and legal[:depth]==pv[:depth]
            for depth in (1,2,3)},
        'critical_3ply_legal':len(legal)>=3,'best_line_consistent':bool(legal) and accepted==legal[0],
        'critical_failure':parsed['critical_line']['failure'],
        'facts':recognized_facts(packet,raw), 'engine_interventions':0,'rule_replacements':0}


def summarize(scored):
    count=len(scored)
    return {'planned':count,'raw_best_legal':sum(row['raw_best_legal'] for row in scored),
        'accepted_best_legal':sum(row['accepted_best_legal'] for row in scored),
        'teacher_best_agreement':sum(row['accepted_teacher_best_agreement'] for row in scored),
        'complete_eos':sum(row['complete_eos'] for row in scored),
        'critical_3ply_legal':sum(row['critical_3ply_legal'] for row in scored),
        'critical_prefix_matches':{str(depth):sum(row['critical_prefix_matches'][str(depth)] for row in scored)for depth in(1,2,3)},
        'recognized_fact_claims':sum(row['facts']['recognized_claims'] for row in scored),
        'false_recognized_claims':sum(row['facts']['false_claims'] for row in scored),
        'grammar_complete_rows':sum(row['facts']['check_and_capture_complete'] for row in scored),
        'whole_prose_unscored_rows':count,'whole_prose_factuality_measured':False}
