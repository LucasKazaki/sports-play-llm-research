#!/usr/bin/env python3
"""Synthetic-only count oracle for a prospective game-disjoint chess holdout.

Real use is blocked. A trusted protected-registry owner must supply complete
full-game trajectory coverage, a durable one-query ledger, and a private
selector before this interface can be adapted to protected data. This module
never reads a manifest, PGN, engine, model, or network resource.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import chess


MIN_FULL_BATCH = 240
MAX_BATCH = 10_000
PROTECTED_SETS = ('training', 'prompt', 'practice', 'development', 'evaluation',
                  'historical_eight', 'cohort_24_including_sealed',
                  'standard_game_development', 'chesscom_practice')
REASONS = ('game_id', 'normalized_uci_trajectory', 'canonical_pre_move_position')
_DIGEST = re.compile(r'[0-9a-f]{64}')
_LICHESS = re.compile(r'(?:lichess:)?([A-Za-z0-9]{8})')
_CHESSCOM = re.compile(r'chesscom:([1-9][0-9]*)')


class OracleError(ValueError):
    """An unsafe, incomplete, or inconsistent synthetic oracle request."""


def _fail(field: str, reason: str) -> None:
    raise OracleError(f'{field}: {reason}')


def _object(value: object, fields: tuple[str, ...], path: str) -> dict:
    if type(value) is not dict or set(value) != set(fields):
        _fail(path, 'field_mismatch')
    return value


def _sha(value: object, path: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None or len(set(value)) < 8:
        _fail(path, 'invalid_sha256')
    return value


def canonical(value: object) -> bytes:
    """Canonical JSON for commitments; rejects non-JSON and nonfinite values."""
    try:
        return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    except (TypeError, ValueError) as error:
        raise OracleError('noncanonical_input') from error


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalized_game_id(value: object) -> str:
    if type(value) is not str:
        _fail('game_id', 'invalid')
    lichess = _LICHESS.fullmatch(value)
    if lichess:
        return f'lichess:{lichess[1]}'
    if _CHESSCOM.fullmatch(value):
        return value
    _fail('game_id', 'invalid')


def canonical_position(board: chess.Board) -> str:
    """Placement, side, castling and *legal* en-passant; never move clocks."""
    return ' '.join(board.fen(en_passant='legal').split()[:4])


def _registry(registry: object) -> tuple[dict, set[str], set[str], set[str]]:
    data = _object(registry, ('schema', 'synthetic', 'protected_sets'), 'registry')
    if data['schema'] != 'synthetic-chess-protected-registry/v1' or data['synthetic'] is not True:
        _fail('registry', 'real_protected_registry_blocked')
    sets = _object(data['protected_sets'], PROTECTED_SETS, 'registry.protected_sets')
    ids: set[str] = set()
    trajectories: set[str] = set()
    positions: set[str] = set()
    for name in PROTECTED_SETS:
        path = f'registry.protected_sets.{name}'
        part = _object(sets[name], ('game_ids', 'trajectory_sha256s',
                       'canonical_positions', 'coverage_receipt_sha256',
                       'full_game_trajectory_coverage', 'pre_move_position_coverage'), path)
        _sha(part['coverage_receipt_sha256'], f'{path}.coverage_receipt_sha256')
        if (part['full_game_trajectory_coverage'] is not True
                or part['pre_move_position_coverage'] is not True):
            _fail(path, 'incomplete_protected_coverage')
        for field in ('game_ids', 'trajectory_sha256s', 'canonical_positions'):
            values = part[field]
            if type(values) is not list or len(values) != len(set(map(str, values))):
                _fail(f'{path}.{field}', 'invalid_or_duplicate_values')
        ids.update(normalized_game_id(value) for value in part['game_ids'])
        trajectories.update(_sha(value, f'{path}.trajectory_sha256s')
                            for value in part['trajectory_sha256s'])
        for value in part['canonical_positions']:
            if type(value) is not str or len(value.split()) != 4:
                _fail(f'{path}.canonical_positions', 'invalid_position_key')
            try:
                board = chess.Board(value + ' 0 1')
            except ValueError:
                board = None
            if board is None:
                _fail(f'{path}.canonical_positions', 'invalid_fen')
            if canonical_position(board) != value:
                _fail(f'{path}.canonical_positions', 'noncanonical_position_key')
            positions.add(value)
    return data, ids, trajectories, positions


def _source(source: object) -> dict:
    data = _object(source, ('schema', 'synthetic', 'intake_receipt_sha256',
                   'source_content_sha256', 'candidate_count', 'candidate_cap',
                   'ranking_state'), 'source')
    if data['schema'] != 'synthetic-source-bound-intake/v1' or data['synthetic'] is not True:
        _fail('source', 'real_source_blocked')
    for field in ('intake_receipt_sha256', 'source_content_sha256'):
        _sha(data[field], f'source.{field}')
    if (type(data['candidate_count']) is not int or not MIN_FULL_BATCH <=
            data['candidate_count'] <= MAX_BATCH):
        _fail('source.candidate_count', 'not_full_batch')
    if (type(data['candidate_cap']) is not int or
            not data['candidate_count'] <= data['candidate_cap'] <= MAX_BATCH):
        _fail('source.candidate_cap', 'invalid_frozen_cap')
    if data['ranking_state'] != 'unranked':
        _fail('source.ranking_state', 'ranking_before_oracle')
    return data


def _candidate_rows(batch: object, source: dict) -> tuple[dict, list[dict]]:
    data = _object(batch, ('schema', 'synthetic', 'source_binding_sha256', 'rows'),
                   'batch')
    if data['schema'] != 'synthetic-legal-candidate-batch/v1' or data['synthetic'] is not True:
        _fail('batch', 'real_candidate_batch_blocked')
    if data['source_binding_sha256'] != digest(canonical(source)):
        _fail('batch.source_binding_sha256', 'source_binding_mismatch')
    rows = data['rows']
    if type(rows) is not list or len(rows) != source['candidate_count']:
        _fail('batch.rows', 'does_not_match_frozen_full_batch')
    seen_case: set[tuple[str, int]] = set()
    game_trajectory: dict[str, str] = {}
    derived = []
    for index, raw in enumerate(rows):
        path = f'batch.rows[{index}]'
        row = _object(raw, ('game_id', 'selected_ply', 'moves_uci'), path)
        game_id = normalized_game_id(row['game_id'])
        if not game_id.startswith('lichess:'):
            _fail(f'{path}.game_id', 'holdout_source_must_be_lichess')
        moves = row['moves_uci']
        ply = row['selected_ply']
        if (type(moves) is not list or not 16 <= len(moves) <= 320
                or any(type(move) is not str for move in moves)
                or type(ply) is not int or not 1 <= ply <= len(moves)):
            _fail(path, 'invalid_move_sequence_or_ply')
        board = chess.Board()
        pre_position = None
        normalized_moves = []
        for move_index, uci in enumerate(moves, start=1):
            try:
                move = chess.Move.from_uci(uci)
            except ValueError as error:
                raise OracleError(f'{path}.moves_uci: invalid_uci') from error
            if move not in board.legal_moves:
                _fail(f'{path}.moves_uci', 'illegal_replay')
            if move_index == ply:
                pre_position = canonical_position(board)
            normalized_moves.append(move.uci())
            board.push(move)
        trajectory = digest('\n'.join(normalized_moves).encode('ascii'))
        if game_id in game_trajectory and game_trajectory[game_id] != trajectory:
            _fail(f'{path}.game_id', 'same_game_id_different_trajectory')
        game_trajectory[game_id] = trajectory
        case = (game_id, ply)
        if case in seen_case:
            _fail(path, 'duplicate_game_ply')
        seen_case.add(case)
        assert pre_position is not None
        derived.append({'game_id': game_id, 'ply': ply, 'trajectory': trajectory,
                        'position': pre_position})
    for key in ('game_id', 'trajectory', 'position'):
        if len({row[key] for row in derived}) < MIN_FULL_BATCH:
            _fail('batch.rows', f'insufficient_distinct_{key}_coverage')
    return data, derived


class SyntheticLedger:
    """Process-local one-query guard; a real run needs an owner-backed ledger."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def claim(self, freeze_card_sha256: str) -> None:
        if freeze_card_sha256 in self._used:
            _fail('ledger', 'query_already_issued_for_freeze')
        self._used.add(freeze_card_sha256)


class PrivateEligibility:
    """Trusted-side handle. Its repr and public receipts expose no rows."""

    def __init__(self, rows: list[dict], receipt_sha256: str, output_dir: Path) -> None:
        self._rows = rows
        self._receipt_sha256 = receipt_sha256
        self._output_dir = output_dir
        self._ranked = False

    def __repr__(self) -> str:
        return '<private synthetic eligibility handle>'

    def rank_once(self, *, oracle_receipt_sha256: str, seed_sha256: str,
                  target: int = MIN_FULL_BATCH) -> dict:
        if self._ranked:
            _fail('ranking', 'already_ranked')
        if _sha(oracle_receipt_sha256, 'ranking.oracle_receipt_sha256') != self._receipt_sha256:
            _fail('ranking.oracle_receipt_sha256', 'stale_oracle_token')
        if digest((self._output_dir / 'receipt.json').read_bytes()) != self._receipt_sha256:
            _fail('ranking.oracle_receipt_sha256', 'receipt_bytes_changed')
        seed = _sha(seed_sha256, 'ranking.seed_sha256')
        if type(target) is not int or target < 1:
            _fail('ranking.target', 'invalid')
        ordered = sorted(self._rows, key=lambda row: (
            digest(f'{seed}|{row["game_id"]}|{row["ply"]}'.encode()),
            row['game_id'], row['ply']))
        seen_games: set[str] = set()
        seen_trajectories: set[str] = set()
        seen_positions: set[str] = set()
        counts = {'duplicate_game': 0, 'duplicate_trajectory': 0,
                  'duplicate_position': 0, 'after_target_cap': 0}
        selected = 0
        for row in ordered:
            if selected == target:
                counts['after_target_cap'] += 1
            elif row['game_id'] in seen_games:
                counts['duplicate_game'] += 1
            elif row['trajectory'] in seen_trajectories:
                counts['duplicate_trajectory'] += 1
            elif row['position'] in seen_positions:
                counts['duplicate_position'] += 1
            else:
                seen_games.add(row['game_id'])
                seen_trajectories.add(row['trajectory'])
                seen_positions.add(row['position'])
                selected += 1
        ranking = {'schema': 'synthetic-chess-oracle-ranking/v1',
                   'status': 'synthetic_count_only',
                   'oracle_receipt_sha256': self._receipt_sha256,
                   'selected_count': selected, 'target': target,
                   'shortfall': max(0, target - selected),
                   'eligible_rows_accounted': len(self._rows),
                   'skipped_by_reason': counts,
                   'protected_case_details_exposed': False}
        path = self._output_dir / 'ranking.json'
        with path.open('xb') as stream:
            stream.write(canonical(ranking))
        self._ranked = True
        return ranking


def issue_synthetic_batch(*, registry: dict, source: dict, batch: dict,
                          expected_registry_sha256: str,
                          expected_source_sha256: str,
                          expected_batch_sha256: str,
                          freeze_card_sha256: str,
                          ledger: SyntheticLedger, output_dir: Path
                          ) -> PrivateEligibility:
    """Issue one full synthetic query, retaining only counts in public files."""
    if type(ledger) is not SyntheticLedger:
        _fail('ledger', 'trusted_owner_ledger_required_for_real_use')
    for field, value, data in (
        ('registry', expected_registry_sha256, registry),
        ('source', expected_source_sha256, source),
        ('batch', expected_batch_sha256, batch),
    ):
        if _sha(value, f'pins.{field}_sha256') != digest(canonical(data)):
            _fail(f'pins.{field}_sha256', 'input_bytes_changed')
    freeze = _sha(freeze_card_sha256, 'pins.freeze_card_sha256')
    _, ids, trajectories, positions = _registry(registry)
    checked_source = _source(source)
    _, rows = _candidate_rows(batch, checked_source)
    if not isinstance(output_dir, Path):
        _fail('output_dir', 'expected_path')
    ledger.claim(freeze)
    output_dir.mkdir(parents=True, exist_ok=False)
    issued = {'schema': 'synthetic-chess-oracle-issuance/v1',
              'status': 'one_full_batch_issued', 'freeze_card_sha256': freeze,
              'registry_sha256': expected_registry_sha256,
              'source_sha256': expected_source_sha256,
              'batch_sha256': expected_batch_sha256,
              'candidate_rows': len(rows), 'minimum_full_batch': MIN_FULL_BATCH,
              'real_one_query_owner_enforced': False}
    (output_dir / 'issued.json').write_bytes(canonical(issued))
    counts = dict.fromkeys(REASONS, 0)
    eligible = []
    for row in rows:
        if row['game_id'] in ids:
            counts['game_id'] += 1
        elif row['trajectory'] in trajectories:
            counts['normalized_uci_trajectory'] += 1
        elif row['position'] in positions:
            counts['canonical_pre_move_position'] += 1
        else:
            eligible.append(row)
    receipt = {'schema': 'synthetic-chess-protected-exclusion-oracle/v1',
               'status': 'synthetic_count_only', 'synthetic': True,
               'freeze_card_sha256': freeze,
               'oracle_code_sha256': digest(Path(__file__).read_bytes()),
               'registry_sha256': expected_registry_sha256,
               'source_sha256': expected_source_sha256,
               'batch_sha256': expected_batch_sha256,
               'protected_sets': list(PROTECTED_SETS),
               'candidate_rows': len(rows), 'excluded_by_reason': counts,
               'eligible_rows': len(eligible), 'before_ranking': True,
               'sealed_details_exposed': False,
               'real_use_blocked': True,
               'real_one_query_owner_enforced': False}
    receipt_raw = canonical(receipt)
    (output_dir / 'receipt.json').write_bytes(receipt_raw)
    return PrivateEligibility(eligible, digest(receipt_raw), output_dir)
