"""Synthetic only: no protected rows, PGN, engine, model or network access."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import traceback

import chess
import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_protected_exclusion_oracle_v1 as oracle


def test_invalid_protected_position_never_appears_in_error_chain(synthetic_inputs, tmp_path):
    registry, source, batch = deepcopy(synthetic_inputs)
    sentinel = 'SECRET_PROTECTED_FEN_MARKER'
    registry['protected_sets']['training']['canonical_positions'] = [sentinel + ' w - -']
    output = tmp_path / 'no-public-receipt'
    with pytest.raises(oracle.OracleError) as caught:
        issue(registry, source, batch, output)
    assert 'invalid_fen' in str(caught.value)
    assert sentinel not in str(caught.value)
    assert sentinel not in ''.join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None
    assert not output.exists()


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def generated_game(index: int) -> list[str]:
    for salt in range(20):
        board = chess.Board()
        moves = []
        for ply in range(18):
            legal = sorted(board.legal_moves, key=lambda move: move.uci())
            if not legal:
                break
            choice = int(sha(f'{index}:{salt}:{ply}')[:8], 16) % len(legal)
            move = legal[choice]
            moves.append(move.uci())
            board.push(move)
        if len(moves) == 18:
            return moves
    raise AssertionError('synthetic generator could not find an 18-ply game')


def features(row: dict) -> tuple[str, str]:
    board = chess.Board()
    position = None
    for ply, uci in enumerate(row['moves_uci'], start=1):
        if ply == row['selected_ply']:
            position = oracle.canonical_position(board)
        board.push_uci(uci)
    assert position is not None
    return oracle.digest('\n'.join(row['moves_uci']).encode()), position


def build_synthetic_inputs():
    rows = [{'game_id': f'lichess:{index:08x}', 'selected_ply': 16,
             'moves_uci': generated_game(index)} for index in range(240)]
    source = {'schema': 'synthetic-source-bound-intake/v1', 'synthetic': True,
              'intake_receipt_sha256': sha('synthetic-intake-receipt'),
              'source_content_sha256': sha('synthetic-source-content'),
              'candidate_count': 240, 'candidate_cap': 240,
              'ranking_state': 'unranked'}
    batch = {'schema': 'synthetic-legal-candidate-batch/v1', 'synthetic': True,
             'source_binding_sha256': oracle.digest(oracle.canonical(source)),
             'rows': rows}
    protected = {
        name: {'game_ids': [], 'trajectory_sha256s': [],
               'canonical_positions': [],
               'coverage_receipt_sha256': sha('coverage-' + name),
               'full_game_trajectory_coverage': True,
               'pre_move_position_coverage': True}
        for name in oracle.PROTECTED_SETS}
    registry = {'schema': 'synthetic-chess-protected-registry/v1',
                'synthetic': True, 'protected_sets': protected}
    return registry, source, batch


@pytest.fixture(scope='module')
def synthetic_inputs():
    return build_synthetic_inputs()


def pins(registry: dict, source: dict, batch: dict) -> dict:
    return {'expected_registry_sha256': oracle.digest(oracle.canonical(registry)),
            'expected_source_sha256': oracle.digest(oracle.canonical(source)),
            'expected_batch_sha256': oracle.digest(oracle.canonical(batch)),
            'freeze_card_sha256': sha('synthetic-frozen-card')}


def issue(registry, source, batch, tmp_path, ledger=None, **override):
    values = pins(registry, source, batch)
    values.update(override)
    return oracle.issue_synthetic_batch(
        registry=registry, source=source, batch=batch,
        ledger=ledger or oracle.SyntheticLedger(), output_dir=tmp_path,
        **values)


def test_full_batch_count_only_priority_and_before_ranking(synthetic_inputs, tmp_path):
    registry, source, batch = deepcopy(synthetic_inputs)
    rows = batch['rows']
    first_trajectory, first_position = features(rows[0])
    second_trajectory, second_position = features(rows[1])
    third_trajectory, third_position = features(rows[2])
    fourth_trajectory, fourth_position = features(rows[3])
    registry['protected_sets']['training']['game_ids'] = [rows[0]['game_id'][8:]]
    registry['protected_sets']['development']['trajectory_sha256s'] = [second_trajectory]
    registry['protected_sets']['practice']['canonical_positions'] = [third_position]
    # Multi-hit counts only as game ID, not again as trajectory or position.
    registry['protected_sets']['chesscom_practice']['game_ids'] = [rows[3]['game_id']]
    registry['protected_sets']['chesscom_practice']['trajectory_sha256s'] = [
        fourth_trajectory]
    registry['protected_sets']['chesscom_practice']['canonical_positions'] = [
        fourth_position]
    registry['protected_sets']['prompt']['game_ids'] = ['SEALED88']
    handle = issue(registry, source, batch, tmp_path / 'run')
    receipt_path = tmp_path / 'run' / 'receipt.json'
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    assert set(receipt) == {'schema', 'status', 'synthetic', 'freeze_card_sha256',
                            'oracle_code_sha256', 'registry_sha256', 'source_sha256',
                            'batch_sha256', 'protected_sets', 'candidate_rows',
                            'excluded_by_reason', 'eligible_rows', 'before_ranking',
                            'sealed_details_exposed', 'real_use_blocked',
                            'real_one_query_owner_enforced'}
    assert receipt['status'] == 'synthetic_count_only'
    assert receipt['candidate_rows'] == 240
    assert receipt['excluded_by_reason'] == {
        'game_id': 2, 'normalized_uci_trajectory': 1,
        'canonical_pre_move_position': 1}
    assert receipt['eligible_rows'] == 236
    assert receipt['before_ranking'] is True
    assert receipt['real_use_blocked'] is True
    assert receipt['real_one_query_owner_enforced'] is False
    assert not (tmp_path / 'run' / 'ranking.json').exists()
    public = ((tmp_path / 'run' / 'issued.json').read_text()
              + receipt_raw.decode() + repr(handle))
    for private_value in ('SEALED88', *[row['game_id'] for row in rows[:4]],
                          first_trajectory, first_position,
                          second_trajectory, second_position,
                          third_trajectory, third_position,
                          fourth_trajectory, fourth_position):
        assert private_value not in public
    receipt_sha = oracle.digest(receipt_raw)
    ranking = handle.rank_once(oracle_receipt_sha256=receipt_sha,
                               seed_sha256=sha('selection-seed'))
    assert ranking['oracle_receipt_sha256'] == receipt_sha
    assert ranking['selected_count'] == 236
    assert ranking['shortfall'] == 4
    assert sum(ranking['skipped_by_reason'].values()) + ranking['selected_count'] == 236
    rank_text = (tmp_path / 'run' / 'ranking.json').read_text()
    assert 'SEALED88' not in rank_text and 'lichess:' not in rank_text
    with pytest.raises(oracle.OracleError, match='already_ranked'):
        handle.rank_once(oracle_receipt_sha256=receipt_sha,
                         seed_sha256=sha('selection-seed'))


def test_one_query_ledger_and_create_only_output(synthetic_inputs, tmp_path):
    registry, source, batch = deepcopy(synthetic_inputs)
    ledger = oracle.SyntheticLedger()
    issue(registry, source, batch, tmp_path / 'first', ledger)
    with pytest.raises(oracle.OracleError, match='query_already_issued'):
        issue(registry, source, batch, tmp_path / 'repeat', ledger)
    assert not (tmp_path / 'repeat').exists()
    changed = deepcopy(batch)
    changed['rows'][0]['selected_ply'] = 15
    with pytest.raises(oracle.OracleError, match='query_already_issued'):
        issue(registry, source, changed, tmp_path / 'altered', ledger)
    assert not (tmp_path / 'altered').exists()
    with pytest.raises(FileExistsError):
        issue(registry, source, batch, tmp_path / 'first')


@pytest.mark.parametrize('change,reason', [
    (lambda registry, source, batch: source.update(candidate_count=239),
     'not_full_batch'),
    (lambda registry, source, batch: source.update(ranking_state='ranked'),
     'ranking_before_oracle'),
    (lambda registry, source, batch: registry['protected_sets']['cohort_24_including_sealed']
        .update(full_game_trajectory_coverage=False), 'incomplete_protected_coverage'),
    (lambda registry, source, batch: registry.update(synthetic=False),
     'real_protected_registry_blocked'),
    (lambda registry, source, batch: batch['rows'][0]['moves_uci'].__setitem__(
        0, 'e2e5'), 'illegal_replay'),
    (lambda registry, source, batch: batch['rows'][1].update(
        game_id=batch['rows'][0]['game_id']), 'same_game_id_different_trajectory'),
    (lambda registry, source, batch: batch['rows'][1].update(
        game_id=batch['rows'][0]['game_id'],
        moves_uci=list(batch['rows'][0]['moves_uci']), selected_ply=16),
     'duplicate_game_ply'),
])
def test_fail_closed_before_issue_and_no_error_leak(
        synthetic_inputs, tmp_path, capsys, change, reason):
    registry, source, batch = deepcopy(synthetic_inputs)
    registry['protected_sets']['prompt']['game_ids'] = ['SEALED88']
    change(registry, source, batch)
    output = tmp_path / 'must-not-issue'
    with pytest.raises(oracle.OracleError, match=reason):
        issue(registry, source, batch, output)
    assert not output.exists()
    output_capture = capsys.readouterr()
    assert 'SEALED88' not in output_capture.out
    assert 'SEALED88' not in output_capture.err


def test_tampered_batch_and_stale_ranking_receipt_reject(synthetic_inputs, tmp_path):
    registry, source, batch = deepcopy(synthetic_inputs)
    old_pins = pins(registry, source, batch)
    batch['rows'][0]['selected_ply'] = 15
    with pytest.raises(oracle.OracleError, match='pins.batch_sha256'):
        issue(registry, source, batch, tmp_path / 'pin-fail',
              expected_batch_sha256=old_pins['expected_batch_sha256'])
    assert not (tmp_path / 'pin-fail').exists()
    handle = issue(registry, source, batch, tmp_path / 'valid')
    with pytest.raises(oracle.OracleError, match='stale_oracle_token'):
        handle.rank_once(oracle_receipt_sha256=sha('wrong-receipt'),
                         seed_sha256=sha('seed'))
    assert not (tmp_path / 'valid' / 'ranking.json').exists()
    receipt_path = tmp_path / 'valid' / 'receipt.json'
    old = receipt_path.read_bytes()
    receipt_path.write_bytes(old + b'tamper')
    with pytest.raises(oracle.OracleError, match='receipt_bytes_changed'):
        handle.rank_once(oracle_receipt_sha256=oracle.digest(old),
                         seed_sha256=sha('seed'))


@pytest.mark.parametrize('field', ('registry', 'source', 'batch'))
def test_each_exact_input_pin_is_checked_before_issuance(synthetic_inputs, tmp_path, field):
    registry, source, batch = deepcopy(synthetic_inputs)
    override = {f'expected_{field}_sha256': sha('stale-' + field)}
    with pytest.raises(oracle.OracleError, match=f'pins.{field}_sha256'):
        issue(registry, source, batch, tmp_path / field, **override)
    assert not (tmp_path / field).exists()


def test_canonical_position_ignores_clocks_and_illegal_ep_but_keeps_legal_rights():
    no_ep = chess.Board('8/8/8/3p4/8/8/8/4K2k w - - 0 1')
    impossible_ep = chess.Board('8/8/8/3p4/8/8/8/4K2k w - d6 52 93')
    assert oracle.canonical_position(no_ep) == oracle.canonical_position(impossible_ep)
    legal_ep = chess.Board('8/8/8/3pP3/8/8/8/4K2k w - d6 0 1')
    same_without_ep = chess.Board('8/8/8/3pP3/8/8/8/4K2k w - - 0 1')
    assert legal_ep.has_legal_en_passant()
    assert oracle.canonical_position(legal_ep) != oracle.canonical_position(same_without_ep)
    start = chess.Board()
    side = chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1')
    castling = chess.Board('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1')
    assert oracle.canonical_position(start) != oracle.canonical_position(side)
    assert oracle.canonical_position(start) != oracle.canonical_position(castling)


def test_rank_deduplicates_games_trajectories_positions_after_oracle(
        synthetic_inputs, tmp_path):
    registry, source, batch = deepcopy(synthetic_inputs)
    rows = batch['rows']
    rows.extend({'game_id': f'lichess:{index:08x}', 'selected_ply': 16,
                 'moves_uci': generated_game(index)} for index in range(240, 244))
    source['candidate_count'] = source['candidate_cap'] = 244
    batch['source_binding_sha256'] = oracle.digest(oracle.canonical(source))
    # Two candidate plies from one game: legal and same complete trajectory.
    rows[1]['game_id'] = rows[0]['game_id']
    rows[1]['moves_uci'] = list(rows[0]['moves_uci'])
    rows[1]['selected_ply'] = 17
    # Different ID, same trajectory.
    rows[2]['moves_uci'] = list(rows[0]['moves_uci'])
    # Different full trajectory, same selected pre-move position.
    rows[3]['moves_uci'] = list(rows[0]['moves_uci'][:16])
    board = chess.Board()
    for uci in rows[3]['moves_uci']:
        board.push_uci(uci)
    alternative_tail = next(move for move in sorted(board.legal_moves,
                             key=lambda move: move.uci())
                            if move.uci() != rows[0]['moves_uci'][16])
    rows[3]['moves_uci'].append(alternative_tail.uci())
    board.push(alternative_tail)
    rows[3]['moves_uci'].append(sorted(board.legal_moves,
                                      key=lambda move: move.uci())[0].uci())
    handle = issue(registry, source, batch, tmp_path / 'run')
    receipt_raw = (tmp_path / 'run' / 'receipt.json').read_bytes()
    ranking = handle.rank_once(oracle_receipt_sha256=oracle.digest(receipt_raw),
                               seed_sha256=sha('rank-duplicate-fixture'))
    assert ranking['selected_count'] <= 241
    assert (ranking['skipped_by_reason']['duplicate_game'] >= 1
            and ranking['skipped_by_reason']['duplicate_trajectory'] >= 1
            and ranking['skipped_by_reason']['duplicate_position'] >= 1)
    assert ranking['selected_count'] + sum(ranking['skipped_by_reason'].values()) == 244


def test_padding_a_batch_with_one_trajectory_cannot_probe_membership(
        synthetic_inputs, tmp_path):
    registry, source, batch = deepcopy(synthetic_inputs)
    repeated = list(batch['rows'][0]['moves_uci'])
    for row in batch['rows']:
        row['moves_uci'] = list(repeated)
    with pytest.raises(oracle.OracleError, match='insufficient_distinct_trajectory'):
        issue(registry, source, batch, tmp_path / 'padded')
    assert not (tmp_path / 'padded').exists()
