"""Strict CPU scoring after raw panels close. No generation or output repair."""
from __future__ import annotations
from collections import Counter
import re
import chess
import chess_queen_coach_sft_eval_v1 as old

native=old.native


def facts(packet,raw):
    packet,board=native.input_packet(packet)
    sections=[section for section in native.FIELDS.finditer(raw)if section['name']=='ANALYSIS']
    moves=[];claims=[];unassociated=[]
    for section in sections:
        body=section['body'];offset=section.start('body');used=set()
        for sentence in old.MOVE_SENTENCE.finditer(body):
            move,error=native.parse_atom(sentence,board,board.turn)
            record={'span':[offset+sentence.start(),offset+sentence.end()],'text':sentence.group(0),
                'move_uci':move.uci()if move else None,'description_error':error,'capture_complete':False}
            moves.append(record)
            after=None;victim=None
            if move is not None and error is None:
                victim=chess.Piece(chess.PAWN,not board.turn)if board.is_en_passant(move)else board.piece_at(move.to_square)
                after=board.copy(stack=False);after.push(move)
            kind=sentence['check_claim'];truth=None if after is None else(
                after.is_checkmate()if kind=='gives checkmate'else after.is_check()if kind=='gives check'else not after.is_check())
            claims.append({'kind':'check_or_mate','text':kind,'span':[offset+sentence.start('check_claim'),offset+sentence.end('check_claim')],
                'true':truth,'analysis_move_uci':record['move_uci']})
            position=sentence.end();position+=len(body[position:])-len(body[position:].lstrip())
            found=old.CAPTURE.match(body,position)or old.NO_CAPTURE.match(body,position)
            if found:
                used.add((found.start(),found.end()));record['capture_complete']=True
                if after is None:capture_truth=None
                elif found.re is old.NO_CAPTURE:capture_truth=victim is None
                else:
                    described=chess.Piece(native.PIECES[found['piece']],board.turn if found['side']=='M'else not board.turn)
                    capture_truth=victim is not None and victim==described
                claims.append({'kind':'capture','text':found.group(0),'span':[offset+found.start(),offset+found.end()],
                    'true':capture_truth,'analysis_move_uci':record['move_uci']})
        for pattern in(old.CAPTURE,old.NO_CAPTURE):
            for found in pattern.finditer(body):
                if(found.start(),found.end())not in used:
                    value={'kind':'unassociated_capture','text':found.group(0),
                        'span':[offset+found.start(),offset+found.end()],'true':None,'analysis_move_uci':None}
                    unassociated.append(value);claims.append(value)
    single=len(sections)==1 and len(moves)==1 and moves[0]['description_error']is None
    complete=single and moves[0]['capture_complete']and not unassociated and len(claims)==2
    return {'analysis_sections':len(sections),'recognized_analysis_moves':moves,'claims':claims,
        'recognized_claims':len(claims),'true_claims':sum(row['true']is True for row in claims),
        'false_claims':sum(row['true']is False for row in claims),'unknown_claims':sum(row['true']is None for row in claims),
        'analysis_move_uci':moves[0]['move_uci']if single else None,
        'check_and_capture_complete':bool(complete),'ambiguous_or_duplicate':not single or bool(unassociated)or len(claims)!=2,
        'all_required_true':bool(complete and all(row['true']is True for row in claims)),
        'whole_prose_factuality_measured':False}


def score(packet,response,reference):
    value=old.score(packet,response,reference);raw=response.get('raw_text','')
    truth=facts(packet,raw);value['facts']=truth
    selected=packet.get('selected_uci');best=value['accepted_best_uci']
    best_sections=sum(section['name']=='BEST_MOVE'for section in native.FIELDS.finditer(raw))
    value['analysis_to_best_alignment']=truth['analysis_move_uci']is not None and truth['analysis_move_uci']==best
    value['joint_selected_facts_correct']=bool(selected and value['complete_eos']and best_sections==1
        and best==selected and truth['analysis_move_uci']==selected and truth['all_required_true'])
    steps=native.parse_output(packet,raw)['critical_line']['steps'];legal=[]
    for step in steps:
        if not step['legal']:break
        legal.append(step['raw_uci'])
    pv=reference.get('reference_pv_uci',[])
    value['selected_conditional_reply_agreement']=None if selected is None else(
        len(pv)>=2 and len(legal)>=2 and legal[0]==selected and legal[:2]==pv[:2])
    value['selected_conditional_two_reply_agreement']=None if selected is None else(
        len(pv)>=3 and len(legal)>=3 and legal[0]==selected and legal[:3]==pv[:3])
    value['supplied_first_ply_is_prediction']=False if selected else None
    return value


def summarize(rows):
    values=old.summarize(rows)
    values.update(statuses=dict(Counter(row['status']for row in rows)),
        selected_given_consistency=sum(row['selected_given_consistency']is True for row in rows),
        selected_joint_facts_correct=sum(row['joint_selected_facts_correct']for row in rows),
        selected_conditional_reply_agreement=sum(row['selected_conditional_reply_agreement']is True for row in rows),
        selected_conditional_two_reply_agreement=sum(row['selected_conditional_two_reply_agreement']is True for row in rows),
        unknown_recognized_claims=sum(row['facts']['unknown_claims']for row in rows),
        analysis_to_best_alignment=sum(row['analysis_to_best_alignment']for row in rows),
        ambiguous_analysis_rows=sum(row['facts']['ambiguous_or_duplicate']for row in rows),
        partial_or_non_EOS_rows=sum(not row['complete_eos']for row in rows))
    return values


def panel(rows,responses,references):
    scored=[]
    if len(rows)!=len(responses):raise ValueError('Full raw response denominator required')
    for row,response in zip(rows,responses):
        scored.append({'case_id':row['case_id'],'group_id':row['group_id'],'mode':row['mode'],
            **score(row['input'],response,references[row['case_id']])})
    modes={mode:summarize([row for row in scored if row['mode']==mode])for mode in('free','selected_a','selected_b')}
    groups={row['group_id']for row in scored};paired=0
    for group in groups:
        selected=[row for row in scored if row['group_id']==group and row['mode']!='free']
        if len(selected)==2 and {row['mode']for row in selected}=={'selected_a','selected_b'}and all(row['joint_selected_facts_correct']for row in selected):paired+=1
    free=[row for row in scored if row['mode']=='free']
    return {'rows':scored,'counts':{**summarize(scored),
        'free_critical_3ply_agreement':sum(row['critical_prefix_matches']['3']for row in free),
        'free_best_agreement':sum(row['accepted_teacher_best_agreement']for row in free),
        'matched_selected_pairs_planned':len(groups),'matched_selected_pairs_joint_correct':paired},
        'by_mode':modes,'uncertainty_unit':'source_game; three modes and both conditions are paired, not independent',
        'scope':'Recognized immediate facts only; all other prose remains unaudited. Forced first move was supplied, not predicted.'}
