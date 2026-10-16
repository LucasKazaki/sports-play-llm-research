"""Ownership-aware fresh evaluation selection. No acquisition, model or engine."""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import json

COUNT = 16
MODES = ('free', 'selected_a', 'selected_b')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def ownership(dataset, teachers, initial, reserved):
    """Keep historical ownership foreign, even when a current path has that key."""
    groups = dataset['groups']
    if {key: len(value) for key, value in groups.items()} != {
        'train': 512, 'development': 32, 'reserve': 512
    }:
        raise ValueError('Exact audited 512/32/512 corpus required')
    expected = [case for roots in groups.values() for root in roots for case in root['case_ids']]
    rows = teachers['rows']
    if len(rows) != 3168 or len(set(expected)) != 3168:
        raise ValueError('Full unique teacher identities required')
    if [row['case_id'] for row in rows] != expected or any(row['status'] != 'completed' for row in rows):
        raise ValueError('Complete ordered teacher corpus required')
    by_case = {row['case_id']: row for row in rows}
    owners = defaultdict(set)
    seen_games = set()
    historical_games = set(initial['games'])
    for key in initial['board_keys']:
        owners[key].add(('historical', None))
    for split, roots in groups.items():
        for root in roots:
            game = root['game_id']
            if game in seen_games or game in historical_games:
                raise ValueError('Repeated or historical game')
            seen_games.add(game)
            if len(root['case_ids']) != 3:
                raise ValueError('Three modes required')
            for key in root['path_keys']:
                owners[key].add((split, game))
            for case, mode in zip(root['case_ids'], MODES):
                row = by_case[case]
                if row['group_id'] != game or row['split'] != split or row['mode'] != mode:
                    raise ValueError('Teacher owner or mode mismatch')
                for key in row['teacher_path_keys']:
                    owners[key].add((split, game))
    if set(reserved['games']) != set(initial['games']) | seen_games:
        raise ValueError('Reserved game union differs')
    if set(reserved['board_keys']) != set(owners):
        raise ValueError('Reserved board union differs')
    return dict(owners), by_case


def choose(roots, by_case, owners, historical_games, spent_games, exposed_keys, full_three):
    """First16 unused eligible groups; own persisted reserve roles are the sole exception."""
    if len(roots) != 512 or len({root['game_id'] for root in roots}) != 512:
        raise ValueError('All512 reserve roots required')
    if len(spent_games) != 16 or not spent_games <= {root['game_id'] for root in roots}:
        raise ValueError('Exact failed16-game scope required')
    selected, ledger = [], []
    for root in sorted(roots, key=lambda row: row['source_ordinal']):
        game = root['game_id']
        paths = set(root['path_keys'])
        for case in root['case_ids']:
            paths.update(by_case[case]['teacher_path_keys'])
        reason = None
        if game in spent_games:
            reason = 'spent_game'
        elif game in historical_games:
            reason = 'historical_game'
        elif paths & exposed_keys:
            reason = 'post_corpus_generated_path_overlap'
        elif any(not owners.get(key) or owners[key] != {('reserve', game)} for key in paths):
            reason = 'foreign_or_unproved_path_owner'
        # Do not visit the spent cohort's PVs or compare any model answer to truth.
        elif not all(full_three(by_case[case]) for case in root['case_ids']):
            reason = 'short_or_invalid_reference'
        take = reason is None and len(selected) < COUNT
        if take:
            selected.append(root)
        ledger.append({'group_id': game, 'source_ordinal': root['source_ordinal'],
            'eligible': reason is None, 'selected': take,
            'reason': reason or ('selected' if take else 'eligible_unused_reserve')})
    status = 'ready_for_export' if len(selected) == COUNT else 'insufficient_cohort'
    return selected, {'status': status, 'planned_reserve': 512, 'planned_selected': COUNT,
        'selected': len(selected), 'unused_before_selection': 496,
        'reason_counts': dict(Counter(row['reason'] for row in ledger)), 'rows': ledger}


def export_rows(roots, by_case, make_cases):
    if len(roots) != COUNT:
        raise ValueError('Never shrink the16-game cohort')
    inputs, references = [], []
    for root in roots:
        values, truth = make_cases(root, by_case, False)
        if len(values) != 3 or len(truth) != 3:
            raise ValueError('Three modes required')
        for row, ref, mode, case in zip(values, truth, MODES, root['case_ids']):
            if (row['group_id'] != root['game_id'] or row['mode'] != mode
                or row['case_id'] != ref['case_id'] or row['case_id'] != case or ref['group_id'] != root['game_id']
                or set(row) != {'case_id', 'group_id', 'mode', 'input'}):
                raise ValueError('Input/reference identity differs')
            expected = {'fen'} if mode == 'free' else {'fen', 'selected_uci'}
            if set(row['input']) != expected:
                raise ValueError('Generator packet contains extra context')
            if row['input']['fen'] != root['fen']:
                raise ValueError('Generator board differs from frozen root')
            if mode != 'free' and row['input']['selected_uci'] != ref['selected_uci']:
                raise ValueError('Given move differs')
            if len(ref['reference_pv_uci']) != 3:
                raise ValueError('Full verified three-ply reference required')
            inputs.append(row)
            references.append(ref)
    if len({row['case_id'] for row in inputs}) != 48:
        raise ValueError('Unique48 inputs required')
    return inputs, references


def legal_generated_keys(raw, native, chess, board_key):
    """Exclusion bookkeeping only: stop at the first invalid or terminal prefix."""
    packet, board = native.input_packet(raw['input'])
    keys = {board_key(board.fen())}
    parsed = native.parse_output(packet, raw.get('raw_text', ''))
    for step in parsed['critical_line']['steps']:
        if not step.get('legal') or board.is_game_over(claim_draw=False):
            break
        move = chess.Move.from_uci(step['raw_uci'])
        if move not in board.legal_moves:
            raise ValueError('Native legal step disagrees with rule replay')
        board.push(move)
        if board.fen() != step['fen_after']:
            raise ValueError('Native successor differs')
        keys.add(board_key(board.fen()))
    return keys


def evidence_digest(owners):
    return hashlib.sha256(canonical({key: sorted(value) for key, value in sorted(owners.items())})).hexdigest()
