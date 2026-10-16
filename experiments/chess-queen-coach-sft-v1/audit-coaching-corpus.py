"""Closed CPU corpus audit. No model/engine call; source solutions are ignored."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

import chess
import pyarrow.parquet as pq

REPO = Path('C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research')
sys.path.insert(0, str(REPO / 'scripts'))
import chess_queen_coach_sft_intake_v1 as intake

OUT = Path(__file__).parent
PRIVATE = REPO / 'data/private/chess-queen-coach-sft-v1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def lines(path): return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x]
def key(fen): return ' '.join(fen.split()[:4])

plan_path = REPO / 'experiments/chess-queen-coach-sft-v1/protocol-v3.json'
plan = intake.protocol(plan_path)
dataset, labels, manifest = [read(PRIVATE / name) for name in ('dataset.json','teachers.json','manifest.json')]
assert manifest['status'] == 'ready_for_training'
assert dataset['protocol_sha256'] == labels['protocol_sha256'] == manifest['protocol_sha256'] == sha(plan_path)
assert labels['dataset_sha256'] == manifest['dataset_sha256'] == sha(PRIVATE / 'dataset.json')
assert manifest['teachers_sha256'] == sha(PRIVATE / 'teachers.json')
assert read(PRIVATE / 'intake-completed.json')['dataset_sha256'] == sha(PRIVATE / 'dataset.json')
assert read(PRIVATE / 'teacher-closed.json')['teachers_sha256'] == sha(PRIVATE / 'teachers.json')
assert labels['statuses'] == {'completed':1568} and labels['all_planned_completed'] is True
registry=read(PRIVATE / 'initial-exclusions.json')
old_games, old_boards = set(registry['games']), set(registry['board_keys'])
computed_games, computed_boards = intake.exclusions(plan)
assert old_games == computed_games and old_boards == computed_boards

seals = {}
for path in PRIVATE.rglob('*'):
    if path.is_file(): seals[str(path)] = sha(path)
games=set();boards={};ids=set();locations={};all_rows=[];old_successor_revisits=0
for split,count in plan['counts'].items():
    rows=dataset['splits'][split];teacher_rows=labels['splits'][split]
    assert len(rows)==len(teacher_rows)==count
    for row,teacher in zip(rows,teacher_rows):
        assert all(teacher[name]==value for name,value in row.items())
        assert teacher['status']=='completed' and row['id'] not in ids
        ids.add(row['id']);all_rows.append((split,row,teacher))
        assert row['game_id'] not in games|old_games
        games.add(row['game_id'])
        assert intake.policy.split_for(row['game_id'],plan['seed'])==split
        for fen in (row['source_before_fen'],row['fen']):
            position=key(fen)
            assert position not in old_boards and position not in boards
            boards[position]=split
        locations[row['source_ordinal']]=row
        before=chess.Board(row['source_before_fen']);before.push_uci(row['setup_uci'])
        assert before.fen()==row['fen'] and before.is_valid() and not before.is_game_over(claim_draw=False)
        board=chess.Board(row['fen'])
        assert 1<=len(teacher['reference_pv'])<=3 and teacher['teacher_move_uci']==teacher['reference_pv'][0]
        for uci in teacher['reference_pv']:
            assert not board.is_game_over(claim_draw=False)
            move=chess.Move.from_uci(uci);assert move in board.legal_moves
            board.push(move)
            old_successor_revisits += key(board.fen()) in old_boards

# Verify every actual retained source location independently, ignoring answer tail.
found=set();ordinal=0
for batch in pq.ParquetFile(REPO / plan['source']['path']).iter_batches(columns=['GameId','PuzzleId','FEN','Moves']):
    values=batch.to_pylist()
    for source in values:
        row=locations.get(ordinal)
        if row is not None:
            assert source['GameId'].split('/')[0].split('#')[0]==row['game_id']
            assert source['PuzzleId']==row['puzzle_id']
            assert chess.Board(source['FEN']).fen()==row['source_before_fen']
            assert source['Moves'].split(maxsplit=1)[0]==row['setup_uci']
            found.add(ordinal)
        ordinal+=1
    if len(found)==len(locations):break
assert found==set(locations)

# Recount complete per-worker pre-call intents and outcomes, and raw bestmove.
tasks=[(split,row) for split,rows in dataset['splits'].items() for row in rows]
teacher_map={row['id']:teacher for _,row,teacher in all_rows}
intents=outcomes=uci_lines=0
for worker in range(3):
    expected={row['id']:row for _,row in tasks[worker::3]}
    events=lines(PRIVATE / f'teacher-journals/worker-{worker}.jsonl')
    seen_intents=set();seen_outcomes=set();raw={identity:[] for identity in expected}
    assert sum(e['event']=='engine_opened' for e in events)==1
    assert not any(e['event']=='worker_failure' for e in events)
    for event in events:
        kind=event['event']
        if kind=='engine_opened':
            assert '19' in event['identity']['name'];continue
        identity=event['id'];assert identity in expected
        if kind=='intent':
            assert identity not in seen_intents
            assert event['fen']==expected[identity]['fen'] and event['nodes']==50000
            seen_intents.add(identity);intents+=1
        elif kind=='uci_line':
            assert identity in seen_intents and identity not in seen_outcomes
            raw[identity].append(event['line']);uci_lines+=1
        elif kind=='outcome':
            assert identity in seen_intents and identity not in seen_outcomes
            assert event['status']=='completed'
            assert all(teacher_map[identity][k]==v for k,v in event.items())
            seen_outcomes.add(identity);outcomes+=1
    assert seen_intents==seen_outcomes==set(expected)
    for identity,raw_lines in raw.items():
        moves=[line.split()[1] for line in raw_lines if line.startswith('bestmove ')]
        assert moves==[teacher_map[identity]['teacher_move_uci']]

# Independent cross-new-split successor audit.
roles=dict(boards)
for split,row,teacher in all_rows:
    replay=chess.Board(row['fen'])
    for uci in teacher['reference_pv']:
        replay.push_uci(uci);position=key(replay.fen())
        assert position not in roles or roles[position]==split
        roles.setdefault(position,split)

held=intake.held_roots(labels['splits']['holdout'])
assert len(held)==16 and [r['game_id'] for r in held]==manifest['held_root_game_ids']
assert dict(Counter(r['stratum'] for r in held))==plan['strata']==manifest['held_strata']
raw_dev=[r['game_id'] for r in labels['splits']['development'] if len(r['reference_pv'])==3][:4]
assert len(raw_dev)==4 and raw_dev==manifest['development_raw_group_ids']
counts={}
for split,source_rows in [('train',labels['splits']['train']),('development',labels['splits']['development']),('heldout',held)]:
    input_name=split+('-inputs' if split=='heldout' else '')+'.jsonl'
    actual_rows=lines(PRIVATE/input_name)
    refs=lines(PRIVATE/f'{split}-references.jsonl') if split!='heldout' else None
    expected_rows=[];expected_refs=[]
    for source in source_rows:
        cases,references=intake.case_rows(source,split!='heldout')
        expected_rows.extend(cases);expected_refs.extend(references)
    assert actual_rows==expected_rows
    if split!='heldout':assert refs==expected_refs
    for row in actual_rows:
        assert set(row['input'])==({'fen'} if row['mode']=='free' else {'fen','selected_uci'})
        assert ('response' in row)==(split!='heldout')
    counts[split]=len(actual_rows)
for name,value in manifest['files'].items():
    assert sha(PRIVATE/name)==value['sha256']
    if name!='heldout-references.jsonl':assert len(lines(PRIVATE/name))==value['rows']
    else:assert value['rows']==32 # Content stays sealed until raw predictions close.
reserved=read(PRIVATE/'reserved-exclusions.json')
assert set(reserved['games'])==old_games|games
assert set(reserved['board_keys'])==old_boards|set(roles)
assert sha(PRIVATE/'reserved-exclusions.json')==manifest['reserved_exclusions_sha256']
for folder in ('executed-sources','teacher-executed-sources'):
    saved=read(PRIVATE/folder/'manifest.json')
    for item in saved.values():assert sha(PRIVATE/folder/item['file'])==item['sha256']
assert all(sha(Path(name))==value for name,value in seals.items())
assert not any(name in sys.modules for name in ('torch','bitsandbytes','peft'))
result={'status':'passed','new_model_calls':0,'new_engine_calls':0,'protocol_sha256':sha(plan_path),
    'dataset_sha256':sha(PRIVATE/'dataset.json'),'teachers_sha256':sha(PRIVATE/'teachers.json'),
    'manifest_sha256':sha(PRIVATE/'manifest.json'),'planned_teacher_outcomes':outcomes,
    'durable_teacher_intents':intents,'raw_uci_lines':uci_lines,'source_rows_checked':len(found),
    'unique_games':len(games),'old_exclusion_games':len(old_games),'old_exclusion_boards':len(old_boards),
    'input_counts':counts,'held_strata':manifest['held_strata'],'fixed_raw_dev_groups':raw_dev,
    'old_board_successor_revisits':old_successor_revisits,
    'historical_scope':'Only new before/current roots are excluded from all historical roles; future teacher successors may revisit older boards.',
    'stable_files':len(seals)}
(OUT/'coaching-corpus-completed-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
