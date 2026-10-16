"""Post-closure paired immediate/conditional facts; no inference or engine."""
from pathlib import Path
from collections import Counter
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'experiments/chess-queen-coach-conditional-line-v1'))
import chess_queen_coach_counterfactual_eval_v1 as immediate
import evaluate_v2 as conditional


def references(path,rows):
    values=[json.loads(line)for line in Path(path).read_text(encoding='utf-8-sig').splitlines()if line.strip()]
    result={value['case_id']:value for value in values}
    if len(result)!=len(values)or set(result)!={row['case_id']for row in rows}:raise ValueError('Reference IDs differ')
    for row in rows:
        reference=result[row['case_id']]
        if reference['group_id']!=row['group_id']:raise ValueError('Reference group differs')
        if row['mode']!='free'and reference['selected_uci']!=row['input']['selected_uci']:raise ValueError('Selected input/reference differs')
    return result


def ratio(numerator,denominator):return None if denominator==0 else numerator/denominator


def panel(rows,responses,refs):
    if(len(rows)!=len(responses)or len(rows)!=len({row['case_id']for row in rows})
        or {row['case_id']for row in rows}!=set(refs)):raise ValueError('Exact full requested case/reference denominator required')
    first=immediate.panel(rows,responses,refs);branches=conditional.panel(rows,responses,refs)
    groups={row['group_id']for row in rows}
    if len(rows)!=48 or len(groups)!=16:raise ValueError('Fixed48presentations/16sourcegames required')
    for group in groups:
        values=[row for row in rows if row['group_id']==group]
        if(len(values)!=3 or {row['mode']for row in values}!={'free','selected_a','selected_b'}):raise ValueError('Exact matched triplets required')
    true=branches['counts']['true_branch_claims'];false=branches['counts']['false_branch_claims'];unknown=branches['counts']['unknown_branch_claims']
    expected=sum(2*(len(refs[row['case_id']]['reference_pv_uci'])-1)for row in rows)
    return {'schema':'chess.conditional-comparison-score.v1','immediate':first,'conditional':branches,
        'requested_presentations':48,'requested_source_games':16,
        'conditional_claims':{'true':true,'false':false,'unassessed':unknown,'recognized':true+false+unknown,
            'requested_target_branch_claims':expected,'recognized_true_fraction':ratio(true,true+false),
            'recognized_claims_per_requested_target_claim':ratio(true+false+unknown,expected),
            'denominator_note':'Extra/duplicate recognized claims may make recognition ratio exceed1; unique/complete joint criteria reject them.'},
        'limits':['Only exact recognized immediate/conditional grammar is audited; other prose unknown.',
            'Template coverage/NLL is not broad coaching/why-best truth. Legal alternative facts can be true with teacher disagreement.',
            'Teacher-prefix agreement is not Elo/correctness. Supplied first moves are not predictions.',
            'Same16puzzle-biased roots,3modes and bothconditions are paired; not96 independent games.']}


def paired(baseline,selected):
    if(baseline['requested_presentations']!=48 or selected['requested_presentations']!=48):raise ValueError('Complete48/condition required')
    def indexed(value):return {row['case_id']:row for row in value['conditional']['rows']}
    left=indexed(baseline);right=indexed(selected)
    if set(left)!=set(right)or len(left)!=48:raise ValueError('Condition cases differ')
    by_group={}
    for case,a in left.items():
        b=right[case]
        if(a['group_id'],a['mode'])!=(b['group_id'],b['mode']):raise ValueError('Paired condition identity differs')
        by_group.setdefault(a['group_id'],[]).append((a,b))
    output={}
    metrics={'conditional_joint':'joint_conditional_line_facts_correct','raw_BEST_legal':'raw_best_legal','accepted_BEST_legal':'accepted_best_legal'}
    for name,key in metrics.items():
        wins=losses=ties=0
        for values in by_group.values():
            if len(values)!=3:raise ValueError('Three paired presentations per sourcegame required')
            a=sum(bool(pair[0][key])for pair in values);b=sum(bool(pair[1][key])for pair in values)
            wins+=b>a;losses+=b<a;ties+=a==b
        output[name]={'source_games':len(by_group),'conditional_higher':wins,'current_higher':losses,'ties':ties,
            'unit':'Per-sourcegame count among the3paired presentations; descriptive, no independence/Elo claim.'}
    return output


def score_phase(plan,rows,out):
    """Called by the unchanged coordinator only after all96 raw/owned jobs close."""
    from run_conditional import read,bound,digest,write,no_torch
    for name in ('baseline','selected'):
        ledger=read(out/(name+'.json'))
        if(ledger.get('status')!='completed'or ledger.get('planned')!=48 or len(ledger['rows'])!=48
            or any(row.get('status')not in('completed','partial')for row in ledger['rows'])):
            raise ValueError('Both full raw ledgers must close before truth access')
    write(out/'truth-access.json',{'status':'opening_reference_parse','reference':plan['heldout_references']},create=True)
    refs=references(bound(plan['heldout_references']),rows)
    write(out/'truth-access.json',{'status':'references_opened','reference':plan['heldout_references']})
    scored={}
    for name in ('baseline','selected'):
        ledger=read(out/(name+'.json'));responses=[]
        for expected,record in zip(rows,ledger['rows']):
            if(expected['case_id']!=record['case_id']or digest(Path(record['response_path']))!=record['response_sha256']):raise ValueError('Saved actual raw bytes/order changed')
            responses.append(read(record['response_path']))
        scored[name]=panel(rows,responses,refs)
        write(out/(name+'-score.json'),scored[name],create=True)
    write(out/'paired-score.json',{'conditions':plan['condition_names'],'paired':paired(scored['baseline'],scored['selected']),
        'whole_prose_or_tutor_quality_measured':False,'NLL_compared_across_target_definitions':False},create=True)
    no_torch()
