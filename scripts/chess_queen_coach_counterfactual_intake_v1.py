"""Fresh CC0 paired-move curriculum intake. CPU only; no teachers or models."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

import chess
import chess_encoder_check_generalization_v1 as prior
from chess_fact_sft_intake import board_key,canonical_game_id,parquet_rows

head=prior.head;ROOT=prior.ROOT
SCHEMA='chess.queen-coach-counterfactual-intake.v1'
PROTOCOL=ROOT/'experiments/chess-queen-coach-counterfactual-v1/intake-protocol.json'
OUTPUT=ROOT/'data/private/chess-queen-coach-counterfactual-v1'
COUNTS={'train':512,'development':32,'reserve':512}
MODES=('free','selected_a','selected_b')


def append(path,value):
    with Path(path).open('a',encoding='utf-8')as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def split_for(game,seed):
    value=int(hashlib.sha256(f'counterfactual-coach-v1:{seed}:{game}'.encode()).hexdigest(),16)%16
    return 'train'if value<8 else'development'if value==8 else'reserve'


def matched_pair(board,game,seed,forbidden,before_key):
    """One checking/nonchecking contrast; origin preference is predeclared."""
    grouped=defaultdict(lambda:{True:[],False:[]})
    current=board_key(board.fen())
    for move in sorted(board.legal_moves,key=lambda move:move.uci()):
        if move.promotion or board.is_castling(move)or board.is_en_passant(move):continue
        truth=prior.describe_move(board,move)
        if truth['successor_key']in forbidden:continue
        grouped[tuple(truth[key]for key in('piece','capture','victim'))][truth['gives_check']].append(truth)
    choices=[]
    for values in grouped.values():
        for yes in values[True]:
            for no in values[False]:
                if len({before_key,current,yes['successor_key'],no['successor_key']})!=4:continue
                rank=hashlib.sha256(f'{seed}:{game}:{yes["uci"]}:{no["uci"]}'.encode()).hexdigest()
                choices.append((yes['source']!=no['source'],rank,yes,no))
    if not choices:return None
    _,_,yes,no=min(choices,key=lambda row:row[:2])
    # Opaque a/b names contain no check label and their assignment ignores truth.
    pair=sorted((yes,no),key=lambda row:hashlib.sha256(f'{seed}:opaque:{game}:{row["uci"]}'.encode()).hexdigest())
    return pair


def select_rows(rows,games,boards,seed,cap,counts,record=lambda row:None,guard=lambda ordinal:None):
    groups={split:[]for split in counts};games=set(games);boards=set(boards)
    rejected=Counter();scanned=0;seen_puzzles=set()
    guard(-1) # Must precede even iterator construction/access.
    for location,source in rows:
        ordinal=location['source_ordinal']
        if ordinal>=cap:break
        if ordinal!=scanned:raise ValueError('Source prefix ordinals must be consecutive')
        scanned+=1
        if ordinal%512==0:guard(ordinal)
        try:
            game=canonical_game_id(source['GameId']);split=split_for(game,seed)
            if game in games:rejected['reserved_game']+=1;continue
            if len(groups[split])>=counts[split]:rejected['split_full']+=1;continue
            before=chess.Board(source['FEN'])
            if before.chess960 or not before.is_valid()or before.is_game_over(claim_draw=False):
                rejected['invalid_or_terminal_before']+=1;continue
            before_key=board_key(before.fen())
            if before_key in boards:rejected['reserved_before']+=1;continue
            if not isinstance(source['Moves'],str):raise ValueError('Setup must be text')
            setup=chess.Move.from_uci(source['Moves'].split(maxsplit=1)[0])
            if setup not in before.legal_moves:raise ValueError('Illegal setup')
            current=before.copy(stack=False);current.push(setup)
            if not current.is_valid()or current.is_game_over(claim_draw=False):
                rejected['invalid_or_terminal_current']+=1;continue
            current_key=board_key(current.fen())
            if current_key in boards:rejected['reserved_current']+=1;continue
            pair=matched_pair(current,game,seed,boards,before_key)
            if pair is None:rejected['no_novel_matched_pair']+=1;continue
            puzzle=source['PuzzleId']
            if not isinstance(puzzle,str)or not puzzle.isalnum()or puzzle in seen_puzzles:raise ValueError('Invalid/repeated PuzzleId')
            paths=[before_key,current_key]+[row['successor_key']for row in pair]
            row={'game_id':game,'puzzle_id':puzzle,'split':split,'fen':current.fen(),
                'source_before_fen':before.fen(),'setup_uci':setup.uci(),'path_keys':paths,
                'pair':pair,'source_square_matched':pair[0]['source']==pair[1]['source'],
                'case_ids':[f'queen-counterfactual-v1:{game}:{mode}'for mode in MODES],**location}
        except(ValueError,TypeError,KeyError,IndexError):
            rejected['invalid_source']+=1;continue
        # Journal before changing accepted-state counts; I/O failures propagate.
        record(row);groups[split].append(row);games.add(game);boards.update(paths);seen_puzzles.add(puzzle)
        if all(len(groups[name])==quota for name,quota in counts.items()):break
    shortages={name:quota-len(groups[name])for name,quota in counts.items()}
    slots=[{'split':name,'slot':slot,'status':'constructed'if slot<=len(groups[name])else'source_shortage'}
        for name,quota in counts.items()for slot in range(1,quota+1)]
    return {'groups':groups,'shortages':shortages,'slots':slots,'scanned_rows':scanned,
        'rejections':dict(rejected),'status':'ready_for_teachers'if not any(shortages.values())else'insufficient_cohort'}


def verify(path):
    plan=head.read(path)
    if(plan['schema']!=SCHEMA or plan['implementation_sha256']!=head.sha(Path(__file__))
        or plan['counts']!=COUNTS or plan['seed']!=4082085 or plan['source_row_cap']!=500000):
        raise ValueError('Frozen intake protocol differs')
    for item in plan['dependencies']:head.bound(item)
    for key in('source','registry','generalization_protocol','generalization_dataset','generalization_closed'):head.bound(plan[key])
    return plan


def exclusions(plan):
    prior_plan=prior.verify(head.bound(plan['generalization_protocol']))
    old_games,old_boards,audit=prior.exclusions(prior_plan)
    registry=head.read(head.bound(plan['registry']))
    dataset=head.read(head.bound(plan['generalization_dataset']))
    closed=head.read(head.bound(plan['generalization_closed']))
    if closed['status']!='cpu_panel_closed'or closed['files']['dataset.json']!=plan['generalization_dataset']['sha256']:
        raise ValueError('Closed generalization metadata binding differs')
    for row in dataset['groups']['diagnostic']:
        old_games.add(row['game_id']);old_boards.update(row['path_keys'])
    prior.registry_superset(registry,old_games,old_boards,'all prior cohorts plus64generalization games/paths')
    games,boards=set(registry['games']),set(registry['board_keys'])
    if {'games':len(games),'board_keys':len(boards)}!=plan['registry_counts']:raise ValueError('Reserved counts differ')
    return games,boards,audit


def snapshot(out,path,plan,label):
    directory=out/label;directory.mkdir();manifest={}
    for index,source in enumerate([Path(path),Path(__file__)]+[head.bound(item)for item in plan['dependencies']]):
        target=directory/f'{index:02d}-{source.name}';shutil.copyfile(source,target)
        manifest[target.name]={'source':str(source),'sha256':head.sha(target)}
    head.save(directory/'manifest.json',manifest)


def intake(path,out):
    if out.exists():raise ValueError('New create-only intake directory required')
    plan=verify(path);source=head.bound(plan['source']);games,boards,audit=exclusions(plan)
    out.mkdir(parents=True);snapshot(out,path,plan,'intake-sources')
    head.save(out/'initial-exclusions.json',{'games':sorted(games),'board_keys':sorted(boards),'audit':audit})
    head.save(out/'intake-attempt.json',{'status':'started','planned_roots':sum(COUNTS.values()),'protocol_sha256':head.sha(path)})
    try:
        cpu=prior.cpu_guard(out,plan)
        def guard(ordinal):
            if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):raise RuntimeError('Global cutoff')
            cpu(ordinal)
        guard(-1)
        result=select_rows(parquet_rows(source),games,boards,plan['seed'],plan['source_row_cap'],COUNTS,
            lambda row:append(out/'selected-source.jsonl',row),guard)
        result.update(schema=SCHEMA,protocol_sha256=head.sha(path),source_sha256=plan['source']['sha256'])
        head.save(out/'dataset.json',result)
        for rows in result['groups'].values():
            for row in rows:games.add(row['game_id']);boards.update(row['path_keys'])
        head.save(out/'root-reservations.json',{'games':sorted(games),'board_keys':sorted(boards)})
        receipt={'status':result['status'],'dataset_sha256':head.sha(out/'dataset.json'),'shortages':result['shortages'],
            'protocol_sha256':head.sha(path),'engine_calls':0,'model_calls':0,'no_replacement':True}
        head.save(out/'intake-closed.json',receipt);return receipt
    except BaseException as error:
        head.save(out/'intake-failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),
            'planned_roots':1056,'source_journal_retains_actual':True,'no_retry':True});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,default=PROTOCOL)
    parser.add_argument('--out',type=Path,default=OUTPUT);args=parser.parse_args()
    print(json.dumps(intake(args.protocol,args.out)))
