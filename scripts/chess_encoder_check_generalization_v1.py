"""CPU-only fresh missing-coverage panel for fixed old encoder check heads.

No model, Torch, engine or feature extraction calls. Labels are evaluator-only
legal-replay facts; inference packets contain just current FEN and selected UCI.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import ctypes
from ctypes import wintypes
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time

import chess
import chess_encoder_check_v1 as head
from chess_fact_sft_intake import board_key,canonical_game_id,parquet_rows

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'experiments/chess-encoder-check-generalization-v1/protocol-v2.json'
OUTPUT=ROOT/'data/private/chess-encoder-check-generalization-v1'
STRATA=('king_mover','pawn_mover','double_check','remaining_discovered_check')
QUOTAS={name:16 for name in STRATA}


def binding(name):
    path=Path(name);return {'path':str(path).replace('\\','/'),'sha256':head.sha(ROOT/path)}


def rows_of(data):
    groups=data.get('groups',data.get('splits',{}))
    return [row for rows in groups.values()for row in rows]


def registry_superset(registry,required_games,required_boards,label):
    games,boards=set(registry['games']),set(registry['board_keys'])
    missing_games=set(required_games)-games;missing_boards=set(required_boards)-boards
    if missing_games or missing_boards:
        raise ValueError(f'Reservation misses {label}: games={len(missing_games)}, boards={len(missing_boards)}')
    return {'games':len(required_games),'board_keys':len(required_boards)}


def exclusions(plan):
    """Consume only frozen registries and root metadata, never coach references."""
    bindings=plan['exclusions'];registry=head.read(head.bound(bindings['coach_reserved']))
    manifest=head.read(head.bound(bindings['coach_manifest']))
    if manifest['reserved_exclusions_sha256']!=bindings['coach_reserved']['sha256']or manifest['reserved_holdout_games']!=512:
        raise ValueError('Full coach reservation binding differs')
    old_plan=head.verify(head.bound(plan['old_head_protocol']))
    old_frozen=head.read(head.bound(bindings['head_frozen']))
    if(old_frozen['protocol_sha256']!=head.sha(head.bound(plan['old_head_protocol']))
        or old_frozen['files_sha256']['dataset.json']!=bindings['head_dataset']['sha256']
        or old_frozen['files_sha256']['initial-exclusions.json']!=bindings['head_initial']['sha256']):
        raise ValueError('Old head cohort/exclusions binding differs')
    required_games=set();required_boards=set();audit={}
    for label in('head_initial','coach_initial'):
        previous=head.read(head.bound(bindings[label]))
        required_games.update(previous['games']);required_boards.update(previous['board_keys'])
        audit[label]=registry_superset(registry,set(previous['games']),set(previous['board_keys']),label)
    for label in('head_dataset','queen_pool','coach_dataset'):
        data=head.read(head.bound(bindings[label]));records=rows_of(data)
        if not records:raise ValueError('Empty frozen metadata cohort: '+label)
        if label=='coach_dataset':
            if data['initial_exclusions_sha256']!=bindings['coach_initial']['sha256']or manifest['dataset_sha256']!=bindings[label]['sha256']:
                raise ValueError('Coach source metadata differs')
            if {name:len(rows)for name,rows in data['splits'].items()}!={'train':1024,'development':32,'holdout':512,'rollout':0}:
                raise ValueError('Coach full reservation root counts differ')
        games,boards=set(),set()
        for row in records:head.add_exclusions(row,games,boards)
        audit[label]=registry_superset(registry,games,boards,label)
        required_games.update(games);required_boards.update(boards)
    if old_plan['source']['sha256']!=plan['source']['sha256']:
        raise ValueError('Original rights-cleared source differs')
    audit['reserved_totals']={'games':len(set(registry['games'])),'board_keys':len(set(registry['board_keys']))}
    if audit['reserved_totals']!=plan['expected_reserved_counts']:
        raise ValueError('Frozen reserved-registry counts differ')
    return set(registry['games']),set(registry['board_keys']),audit


def describe_move(board,move):
    if move not in board.legal_moves:raise ValueError('Selected move is illegal')
    if move.promotion or board.is_castling(move)or board.is_en_passant(move):
        raise ValueError('Special moves excluded by frozen scope')
    piece=board.piece_at(move.from_square);victim=board.piece_at(move.to_square)
    after=board.copy(stack=False);after.push(move)
    checking=after.is_check()
    if checking!=board.gives_check(move):raise RuntimeError('Independent replay check routes disagree')
    checkers=sorted(chess.square_name(square)for square in after.checkers())
    return {'uci':move.uci(),'source':move.from_square,'piece':piece.piece_type,
        'capture':board.is_capture(move),'victim':victim.piece_type if victim else None,
        'gives_check':checking,'checkers':checkers,'double_check':len(checkers)>=2,
        'discovered_check':any(square!=move.to_square for square in after.checkers()),
        'king_mover':piece.piece_type==chess.KING,'pawn_mover':piece.piece_type==chess.PAWN,
        'successor_key':board_key(after.fen())}


def allocation(truth):
    if not truth['gives_check']:return None
    if truth['king_mover']:return 'king_mover'
    if truth['pawn_mover']:return 'pawn_mover'
    if truth['double_check']:return 'double_check'
    if truth['discovered_check']:return 'remaining_discovered_check'
    return None


def cpu_guard(out,plan):
    """Read host counters only. Stop this CPU lane; never query/control GPU."""
    class Info(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD)]+[(name,ctypes.c_size_t)for name in(
            'CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache',
            'KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[
            (name,wintypes.DWORD)for name in('HandleCount','ProcessCount','ThreadCount')]
    api=ctypes.WinDLL('psapi',use_last_error=True).GetPerformanceInfo
    api.argtypes=(ctypes.POINTER(Info),wintypes.DWORD);api.restype=wintypes.BOOL
    last=-math.inf;started=time.monotonic();first=True
    def check(ordinal):
        nonlocal last,first
        now=time.monotonic()
        if(out/'CANCEL').exists():raise RuntimeError('Owned CPU intake cancelled')
        if now-started>plan['maximum_cpu_seconds']:raise RuntimeError('Frozen CPU intake deadline')
        if now-last<1:return
        info=Info();info.cb=ctypes.sizeof(info)
        if not api(ctypes.byref(info),info.cb):raise ctypes.WinError(ctypes.get_last_error())
        physical=info.PhysicalAvailable*info.PageSize;commit=(info.CommitLimit-info.CommitTotal)*info.PageSize
        sample={'at':datetime.now(timezone.utc).isoformat(),'source_ordinal':ordinal,
            'physical_available_bytes':physical,'commit_headroom_bytes':commit}
        with(out/'cpu-resources.jsonl').open('a',encoding='utf-8')as stream:
            stream.write(json.dumps(sample)+'\n');stream.flush();os.fsync(stream.fileno())
        minimum=plan['cpu_start_commit_bytes']if first else plan['cpu_running_commit_bytes']
        if physical<plan['cpu_physical_bytes']or commit<minimum:raise RuntimeError('Owned CPU intake resource reserve')
        last=now;first=False
    return check


def candidate_pair(board,game,seed,forbidden,remaining,before_key,coverage=None):
    """Category-specific matching is frozen before intake; preserve path novelty."""
    if coverage is None:coverage=Counter()
    groups=defaultdict(lambda:{True:[],False:[]})
    for move in sorted(board.legal_moves,key=lambda value:value.uci()):
        if move.promotion or board.is_castling(move)or board.is_en_passant(move):continue
        truth=describe_move(board,move)
        if truth['successor_key']in forbidden:continue
        key=tuple(truth[name]for name in('piece','capture','victim'))
        groups[key][truth['gives_check']].append(truth)
    candidates=[];positive_strata=set();matched_strata=set()
    for group in groups.values():
        for yes in group[True]:
            stratum=allocation(yes)
            if stratum is None:continue
            positive_strata.add(stratum);coverage['legal_novel_positive_moves:'+stratum]+=1
            for no in group[False]:
                same_origin=yes['source']==no['source']
                if same_origin!=(stratum in('king_mover','pawn_mover')):continue
                path=[before_key,board_key(board.fen()),yes['successor_key'],no['successor_key']]
                if len(set(path))!=4:continue
                matched_strata.add(stratum)
                if remaining[stratum]<=0:continue
                digest=hashlib.sha256(f'{seed}:{game}:{yes["uci"]}:{no["uci"]}'.encode()).hexdigest()
                candidates.append((STRATA.index(stratum),digest,stratum,yes,no))
    for name in positive_strata:coverage['positive_root_rows:'+name]+=1
    for name in matched_strata:coverage['matched_root_rows:'+name]+=1
    if not candidates:return None
    _,_,stratum,yes,no=min(candidates,key=lambda row:row[:2])
    return stratum,yes,no


def select_rows(source_rows,games,boards,quotas,seed,cap,record=lambda value:None,check=lambda ordinal:None):
    if quotas!=QUOTAS:raise ValueError('Frozen quotas differ')
    games,boards=set(games),set(boards);counts=Counter();rejected=Counter();coverage=Counter()
    inputs=[];labels=[];metadata=[];seen_puzzles=set();scanned=0;last=None
    check(-1) # The start check precedes even __iter__/next on the source.
    for location,row in source_rows:
        ordinal=location['source_ordinal']
        if ordinal>=cap:break
        if ordinal%512==0:check(ordinal)
        if ordinal!=scanned:raise ValueError('Source prefix ordinals are not consecutive')
        scanned+=1;last=ordinal
        try:
            game=canonical_game_id(row['GameId'])
            if game in games:rejected['excluded_game']+=1;continue
            before=chess.Board(row['FEN'])
            if not before.is_valid()or before.chess960 or before.is_game_over(claim_draw=False):
                rejected['invalid_or_terminal_before']+=1;continue
            before_key=board_key(before.fen())
            if before_key in boards:rejected['excluded_before_board']+=1;continue
            text=row['Moves']
            if not isinstance(text,str):raise ValueError('Source setup is not text')
            # Whitelist the first setup token; never parse source answers/themes.
            setup=chess.Move.from_uci(text.split(maxsplit=1)[0])
            if setup not in before.legal_moves:raise ValueError('Illegal source setup')
            current=before.copy(stack=False);current.push(setup)
            if not current.is_valid()or current.is_game_over(claim_draw=False):
                rejected['invalid_or_terminal_current']+=1;continue
            current_key=board_key(current.fen())
            if current_key in boards:rejected['excluded_current_board']+=1;continue
            selected=candidate_pair(current,game,seed,boards,
                {name:quotas[name]-counts[name]for name in STRATA},before_key,coverage)
            if selected is None:rejected['no_open_matched_target_pair']+=1;continue
            puzzle=row['PuzzleId']
            if not isinstance(puzzle,str)or not puzzle.isalnum()or puzzle in seen_puzzles:
                raise ValueError('Invalid or repeated puzzle ID')
            stratum,yes,no=selected
            pair=sorted((yes,no),key=lambda value:hashlib.sha256(f'{game}:{value["uci"]}'.encode()).hexdigest())
            ids=[]
            for truth in pair:
                identity=f'encoder-generalization-v1-{puzzle}-{truth["uci"]}';ids.append(identity)
                value=head.packet({'fen':current.fen(),'selected_uci':truth['uci']})
                inputs.append({'case_id':identity,**value})
                labels.append({'case_id':identity,'gives_check':truth['gives_check']})
            path=[before_key,current_key,yes['successor_key'],no['successor_key']]
            item={'game_id':game,'puzzle_id':puzzle,'source_before_fen':before.fen(),
                'setup_uci':setup.uci(),'fen':current.fen(),'selected_pair':[value['uci']for value in pair],
                'case_ids':ids,'allocation':stratum,'slot':counts[stratum]+1,'positive':yes,'negative':no,
                'source_square_matched':yes['source']==no['source'],
                'matching_contract':'same_origin'if stratum in('king_mover','pawn_mover')else'different_same_type_instance',
                'path_keys':path,**location}
            metadata.append(item);counts[stratum]+=1;games.add(game);boards.update(path);seen_puzzles.add(puzzle)
            record(item)
            if all(counts[name]==quotas[name]for name in STRATA):break
        except(ValueError,KeyError,TypeError,IndexError):
            rejected['invalid_source_or_pair']+=1
    slots=[]
    for name in STRATA:
        found={row['slot']:row for row in metadata if row['allocation']==name}
        for index in range(1,quotas[name]+1):
            slots.append({'allocation':name,'slot':index,'planned_moves':2,
                'status':'constructed'if index in found else'source_shortage',
                'case_ids':found[index]['case_ids']if index in found else[]})
    return {'inputs':inputs,'labels':labels,'metadata':metadata,'slots':slots,
        'scanned_rows':scanned,'last_source_ordinal':last,'rejections':dict(rejected),
        'candidate_coverage':dict(coverage),
        'constructed_pairs':{name:counts[name]for name in STRATA},
        'shortages':{name:quotas[name]-counts[name]for name in STRATA},
        'terminal_reason':'quotas_filled'if all(counts[name]==quotas[name]for name in STRATA)else'source_cap_or_exhaustion'}


def verify(path):
    plan=head.read(path)
    if(plan['schema']!='chess.encoder-check-generalization-protocol.v2'
        or plan['implementation_sha256']!=head.sha(Path(__file__))or plan['quotas']!=QUOTAS or plan['source_row_cap']!=500000):
        raise ValueError('Frozen CPU protocol differs')
    for item in plan['dependencies']:head.bound(item)
    for item in plan['exclusions'].values():head.bound(item)
    head.bound(plan['old_head_protocol']);head.bound(plan['selected']);head.bound(plan['original_untrained'])
    selection=head.read(head.bound(plan['old_selection']))
    if selection['selected']!=plan['selected']or selection['candidates'][0]!=plan['original_untrained']:
        raise ValueError('Fixed original selected/untrained identities changed')
    return plan


def intake(path,out):
    if out.exists():raise ValueError('CPU intake attempt is create-only')
    plan=verify(path);source=head.bound(plan['source']);games,boards,audit=exclusions(plan)
    out.mkdir(parents=True);sources=out/'sources';sources.mkdir()
    paths=[Path(__file__),Path(path)]+[head.bound(item)for item in plan['dependencies']]
    copied={}
    for index,src in enumerate(paths):
        target=sources/f'{index:02d}-{src.name}';shutil.copyfile(src,target)
        copied[target.name]={'source':str(src),'sha256':head.sha(target)}
    head.save(sources/'manifest.json',copied)
    head.save(out/'initial-exclusions.json',{'games':sorted(games),'board_keys':sorted(boards),'audit':audit})
    head.save(out/'attempt.json',{'status':'started','protocol_sha256':head.sha(path),
        'planned_pairs':64,'planned_move_slots':128,'model_calls':0,'engine_calls':0})
    try:
        with(out/'selected-source-journal.jsonl').open('x',encoding='utf-8')as stream:
            def retained(row):
                stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
            guard=cpu_guard(out,plan);guard(-1)
            result=select_rows(parquet_rows(source),games,boards,plan['quotas'],plan['seed'],plan['source_row_cap'],retained,guard)
        head.validate_labels(result['inputs'],result['labels'])
        head.save(out/'inputs.json',{'rows':result.pop('inputs')});head.save(out/'labels.json',{'rows':result.pop('labels')})
        metadata=result.pop('metadata')
        head.save(out/'dataset.json',{'schema':'chess.encoder-check-generalization.v1','protocol_sha256':head.sha(path),
            'source_sha256':plan['source']['sha256'],'groups':{'diagnostic':metadata},**result})
        for row in metadata:games.add(row['game_id']);boards.update(row['path_keys'])
        head.save(out/'reserved-exclusions.json',{'games':sorted(games),'board_keys':sorted(boards)})
        files={file.name:head.sha(file)for file in out.iterdir()if file.is_file()}
        closed={'status':'cpu_panel_closed','planned_pairs':64,'planned_move_slots':128,
            'constructed_pairs':len(metadata),'constructed_moves':len(metadata)*2,'shortages':result['shortages'],
            'source_scanned_rows':result['scanned_rows'],'protocol_sha256':head.sha(path),'files':files,
            'model_calls':0,'engine_calls':0,'coaching_held_reference_reads':0,
            'scope':'CPU source coverage only. Independent cohort audit and separately frozen root-only inference plan required before scoring.'}
        head.save(out/'closed.json',closed);return closed
    except Exception as error:
        head.save(out/'failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),
            'planned_pairs':64,'planned_move_slots':128,'model_calls':0,'engine_calls':0});raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=PROTOCOL);parser.add_argument('--out',type=Path,default=OUTPUT)
    args=parser.parse_args();print(json.dumps(intake(args.protocol,args.out),allow_nan=False))


if __name__=='__main__':main()
