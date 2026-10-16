"""Exact conditional claims and legal branches; unknown prose stays unaudited."""
from collections import Counter
import re
import chess
import targets
from targets import native
import chess_queen_coach_counterfactual_eval_v1 as immediate

ATOM = re.sub(r'\(\?P<[^>]+>', '(?:', native.MOVE.pattern)
CHECK = r'gives checkmate|gives check|does not give check'
CAP = r'captures <PIECE_[MO][PNBRQK]> on <SQUARE_\d+>|captures no piece'
PLY2 = re.compile(r'Conditional line: If (?P<a1>'+ATOM+r') is played, the opponent can reply (?P<move>'+ATOM+
    r'); that reply (?P<capture>'+CAP+r') and (?P<check>'+CHECK+r')\.')
PLY3 = re.compile(r'If that reply is played, the mover can play (?P<move>'+ATOM+
    r'); that move (?P<capture>'+CAP+r') and (?P<check>'+CHECK+r')\.')


def parse(text, board, pov):
    match = native.MOVE.fullmatch(text)
    if match is None: return None, 'unrecognized_atom'
    if board is None: return None, 'invalid_prior_prefix'
    if board.is_game_over(claim_draw=False): return None, 'automatic_terminal_prefix'
    return native.parse_atom(match, board, pov)


def assess_claims(match, board, pov, ply, offset):
    move, error = parse(match['move'], board, pov)
    expected = None if error or move is None else targets.move_facts(board, move)
    claims = []
    for kind in ('capture','check'):
        truth = None
        if expected is not None:
            truth = (match[kind] == targets.capture_words(expected,pov)) if kind=='capture' else (
                expected['checkmate'] if match[kind]=='gives checkmate' else expected['gives_check']
                if match[kind]=='gives check' else not expected['gives_check'])
        claims.append({'ply':ply,'kind':kind,'span':[offset+match.start(kind),offset+match.end(kind)],
            'text':match[kind],'true':truth})
    after = None
    if expected is not None: after=board.copy(stack=False); after.push(move)
    return {'ply':ply,'span':[offset+match.start(),offset+match.end()], 'move_uci':move.uci() if move else None,
        'description_error':error,'claims':claims}, after


def facts(packet, raw, required_plies):
    packet, root = native.input_packet(packet); pov = root.turn
    if type(required_plies) is not int or not 1 <= required_plies <= 3: raise ValueError('Bounded reference length required')
    root_facts = immediate.facts(packet,raw)
    sections = [match for match in native.FIELDS.finditer(raw) if match['name']=='ANALYSIS']
    parsed = native.parse_output(packet,raw); best=parsed['accepted_move_uci']
    best_fields=sum(match['name']=='BEST_MOVE' for match in native.FIELDS.finditer(raw))
    clauses=[]; anchors=[]; all_claims=[]; second_board=None; second_section=None; second_end=None; chain=[]
    all2=[];all3=[]
    for section in sections:
        body=section['body'];offset=section.start('body')
        for match in PLY2.finditer(body): all2.append((match,offset))
        for match in PLY3.finditer(body): all3.append((match,offset))
    for match,offset in all2:
        first,error=parse(match['a1'],root,pov); board=None
        if first is not None and error is None: board=root.copy(stack=False);board.push(first)
        anchor={'move_uci':first.uci() if first else None,'error':error,
            'span':[offset+match.start('a1'),offset+match.end('a1')]}
        anchors.append(anchor)
        clause,after=assess_claims(match,board,pov,2,offset);clauses.append(clause);all_claims.extend(clause['claims'])
        if len(all2)==1:
            chain=[anchor['move_uci'],clause['move_uci']];second_board=after
            second_section=offset;second_end=offset+match.end()
    for match,offset in all3:
        prefix_board=second_board if offset==second_section and second_end is not None and offset+match.start()>=second_end else None
        clause,after=assess_claims(match,prefix_board,pov,3,offset);clauses.append(clause);all_claims.extend(clause['claims'])
        if len(all2)==1 and len(all3)==1: chain.append(clause['move_uci'])
    expected2=int(required_plies>=2);expected3=int(required_plies>=3)
    body=sections[0]['body'] if len(sections)==1 else ''
    # Count malformed/duplicate recognizable markers as ambiguity, never select a favorable chain.
    markers_ok=(body.count('Conditional line:')==len(all2) and body.count('If that reply is played')==len(all3))
    order_ok=not all2 or not all3 or all2[0][1]+all2[0][0].end() <= all3[0][1]+all3[0][0].start()
    unique=(len(sections)==1 and len(all2)==expected2 and len(all3)==expected3 and markers_ok and order_ok)
    selected=packet.get('selected_uci')
    aligned=(root_facts['analysis_move_uci'] is not None and root_facts['analysis_move_uci']==best
        and best_fields==1 and (selected is None or best==selected)
        and all(anchor['move_uci']==best and anchor['error'] is None for anchor in anchors))
    if required_plies==1: chain=[root_facts['analysis_move_uci']]
    raw_steps=parsed['critical_line']['steps'];raw_legal=[]
    for step in raw_steps:
        if not step['legal']:break
        raw_legal.append(step['raw_uci'])
    consistent=(unique and None not in chain and len(chain)==required_plies
        and parsed['critical_line']['failure'] is None and len(raw_steps)==required_plies and raw_legal==chain)
    required_true=unique and aligned and consistent and root_facts['all_required_true'] and all(value['true']is True for value in all_claims)
    return {'root_immediate_facts':root_facts,'required_plies':required_plies,'conditional_clauses':clauses,
        'conditional_anchors':anchors,'recognized_branch_claims':all_claims,
        'true_branch_claims':sum(value['true']is True for value in all_claims),
        'false_branch_claims':sum(value['true']is False for value in all_claims),
        'unknown_branch_claims':sum(value['true']is None for value in all_claims),
        'invalid_prefix_or_atom_clauses':sum(value['description_error']is not None for value in clauses),
        'unique_complete_chain':unique,'analysis_best_selected_alignment':bool(aligned),
        'conditional_to_raw_critical_alignment':bool(consistent),
        'all_required_conditional_facts_true':bool(required_true),
        'other_prose_audited':False,'forced_reply_or_bestness_measured':False}


def score(packet,response,reference):
    value=immediate.score(packet,response,reference)
    pv=reference['reference_pv_uci'];truth=facts(packet,response.get('raw_text',''),len(pv))
    value['conditional_facts']=truth
    value['joint_conditional_line_facts_correct']=bool(value['complete_eos']and truth['all_required_conditional_facts_true'])
    return value


def panel(rows,responses,references):
    if len(rows)!=len(responses) or {row['case_id']for row in rows}!=set(references):raise ValueError('Full panel/reference denominator required')
    if len({row['case_id']for row in rows})!=len(rows):raise ValueError('Duplicate requested case')
    scored=[{'case_id':row['case_id'],'group_id':row['group_id'],'mode':row['mode'],
        **score(row['input'],response,references[row['case_id']])}for row,response in zip(rows,responses)]
    def counts(values):
        return {'presentations':len(values),'statuses':dict(Counter(row['status']for row in values)),
            'conditional_joint_correct':sum(row['joint_conditional_line_facts_correct']for row in values),
            'true_branch_claims':sum(row['conditional_facts']['true_branch_claims']for row in values),
            'false_branch_claims':sum(row['conditional_facts']['false_branch_claims']for row in values),
            'unknown_branch_claims':sum(row['conditional_facts']['unknown_branch_claims']for row in values),
            'unique_complete_chain':sum(row['conditional_facts']['unique_complete_chain']for row in values),
            'free_best_agreement':sum(row['accepted_teacher_best_agreement']is True for row in values if row['mode']=='free'),
            'free_3ply_agreement':sum(row['critical_prefix_matches']['3']for row in values if row['mode']=='free')}
    groups={row['group_id']for row in rows}
    complete_groups=0
    for group in groups:
        values=[row for row in scored if row['group_id']==group]
        if len(values)==3 and {row['mode']for row in values}=={'free','selected_a','selected_b'}and all(row['joint_conditional_line_facts_correct']for row in values):complete_groups+=1
    return {'rows':scored,'counts':counts(scored),'modes':{mode:counts([row for row in scored if row['mode']==mode])for mode in('free','selected_a','selected_b')},
        'source_games_planned':len(groups),'all_three_presentations_joint_correct_games':complete_groups,
        'whole_prose_or_tutoring_quality_measured':False}
