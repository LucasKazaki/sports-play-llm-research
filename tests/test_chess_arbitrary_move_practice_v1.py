"""Synthetic source and engine tests; no Stockfish or model process is started."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import chess
import chess.engine
import chess.pgn
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import chess_arbitrary_move_practice_v1 as practice  # noqa: E402


def fixture(tmp_path):
    game = chess.pgn.Game()
    game.headers['Event'] = 'Synthetic one-game practice'
    game.headers['Link'] = 'https://example.invalid/synthetic-game'
    game.headers['Result'] = '1-0'
    node = game
    for uci in ('e2e4', 'e7e5', 'g1f3'):
        node = node.add_variation(chess.Move.from_uci(uci))
    pgn = tmp_path / 'source.pgn'
    raw = (str(game) + '\n').encode('utf-8')
    pgn.write_bytes(raw)
    engine = tmp_path / 'synthetic-engine.exe'
    binary = b'synthetic engine bytes; never executed'
    engine.write_bytes(binary)
    board = chess.Board()
    board.push_uci('e2e4')
    board.push_uci('e7e5')
    pins = practice.PracticePins(
        game_id='synthetic:one', link=game.headers['Link'],
        pgn_sha256=sha256(raw).hexdigest(),
        engine_sha256=sha256(binary).hexdigest(),
        ply=3, played_uci='g1f3', fen_before=board.fen())
    return pgn, engine, pins


class FakeStream:
    def __init__(self, events):
        self.events = iter(events)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def would_block(self):
        return False

    def next(self):
        return next(self.events, None)


class FakeEngine:
    id = {'name': 'Stockfish 19'}

    def __init__(self):
        self.calls = []
        self.closed = False

    def analysis(self, board, limit, *, multipv, root_moves, options, game):
        roots = ['d2d4', 'g1f3'] if root_moves is None else [move.uci() for move in root_moves]
        self.calls.append({'fen': board.fen(), 'stack': list(board.move_stack),
                           'nodes': limit.nodes, 'roots': roots, 'multipv': multipv})
        assert multipv == 2
        assert len(roots) == 2
        values = {'d2d4': 200, 'g1f3': 0}
        events = [
            {'multipv': rank, 'pv': [chess.Move.from_uci(root)],
             'score': chess.engine.PovScore(chess.engine.Cp(values[root]), board.turn),
             'nodes': limit.nodes, 'depth': 17}
            for rank, root in enumerate(roots, 1)
        ]
        return FakeStream(events)

    def quit(self):
        self.closed = True


def test_chesscom_practice_moves_are_legal_on_one_pinned_preboard():
    board = chess.Board(practice.PINS.fen_before)
    assert board.san(chess.Move.from_uci('c2c3')) == 'Qc3'
    assert board.san(chess.Move.from_uci('c2e4')) == 'Qe4'
    assert practice.PINS.ply == 39
    assert practice.PINS.pgn_sha256 == '684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075'


def test_same_source_board_accepts_played_and_alternative_with_distinct_receipts(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    played = practice.prepare(pgn, engine, 'g1f3', pins=pins)
    alternative = practice.prepare(pgn, engine, 'd2d4', pins=pins)
    assert played.board.fen() == alternative.board.fen() == pins.fen_before
    assert played.board.move_stack == alternative.board.move_stack
    assert played.source['played_uci'] == alternative.source['played_uci'] == 'g1f3'
    assert played.source['selected_san'] == 'Nf3'
    assert alternative.source['selected_san'] == 'd4'
    assert played.source['position_sha256'] != alternative.source['position_sha256']
    assert played.source['prior_uci_sha256'] == alternative.source['prior_uci_sha256']
    assert played.source['prior_uci_sha256'] == sha256(
        practice._canonical(['e2e4', 'e7e5'])).hexdigest()
    assert sha256(played.source_bytes).hexdigest() != pins.pgn_sha256


def test_run_fake_engine_create_only_and_offline_verify(tmp_path):
    pgn, binary, pins = fixture(tmp_path)
    output = tmp_path / 'review'
    fake = FakeEngine()
    launches = []

    def factory(path):
        launches.append(path)
        assert Path(path).read_bytes() == binary.read_bytes()
        assert (output / 'source.json').is_file()
        assert (output / 'attempt.json').is_file()
        assert not (output / 'result.json').exists()
        return fake

    result = practice.run(pgn, binary, 'g1f3', output, pins=pins, engine_factory=factory)
    assert len(launches) == 1
    assert [call['nodes'] for call in fake.calls] == [100_000, 30_000, 100_000]
    assert [call['fen'] for call in fake.calls] == [pins.fen_before] * 3
    assert [len(call['stack']) for call in fake.calls] == [2] * 3
    assert fake.closed
    assert result['status'] == 'observed'
    assert result['evaluation']['comparison']['status'] == 'observed_inferior_in_pair'
    assert result['evaluation']['comparison']['observed_loss_cp'] == 200
    assert result['source_receipt_sha256'] != pins.pgn_sha256
    assert result['engine_cleanup'] == 'closed'
    assert result['model_calls'] == result['browser_calls'] == 0
    assert 'pv_uci' not in json.dumps(result)
    verified = practice.verify(pgn, binary, output, pins=pins)
    assert verified['status'] == 'verified_local_evidence'
    assert verified['engine_calls'] == verified['model_calls'] == 0
    assert verified['result_sha256'] == sha256((output / 'result.json').read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        practice.run(pgn, binary, 'g1f3', output, pins=pins, engine_factory=factory)
    assert len(launches) == 1


@pytest.mark.parametrize('selected', ['g1f3', 'd2d4'])
def test_selected_move_is_an_arbitrary_legal_root(tmp_path, selected):
    pgn, binary, pins = fixture(tmp_path)
    fake = FakeEngine()
    result = practice.run(pgn, binary, selected, tmp_path / selected,
                          pins=pins, engine_factory=lambda _: fake)
    assert result['evaluation']['selected_uci'] == selected
    assert fake.calls[1]['roots'][0] == selected
    assert result['status'] == 'observed'


@pytest.mark.parametrize('tamper', ['pgn', 'engine', 'illegal_move', 'wrong_board'])
def test_prelaunch_failures_do_not_create_output_or_start_engine(tmp_path, tamper):
    pgn, engine, pins = fixture(tmp_path)
    selected = 'g1f3'
    if tamper == 'pgn':
        pgn.write_bytes(pgn.read_bytes() + b'\n')
    elif tamper == 'engine':
        engine.write_bytes(b'changed')
    elif tamper == 'illegal_move':
        selected = 'g1g3'
    else:
        pins = practice.PracticePins(**{**pins.__dict__, 'fen_before': chess.STARTING_FEN})
    launches = []
    with pytest.raises(ValueError):
        practice.run(pgn, engine, selected, tmp_path / 'no-review',
                     pins=pins, engine_factory=lambda path: launches.append(path))
    assert not (tmp_path / 'no-review').exists()
    assert launches == []


def test_launch_failure_keeps_reserved_attempt_and_unresolved_result(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'launch-failure'

    def fail_launch(_):
        raise OSError('synthetic executable failure')

    result = practice.run(pgn, engine, 'g1f3', output,
                          pins=pins, engine_factory=fail_launch)
    assert result['status'] == 'unresolved'
    assert result['reason'] == 'engine_launch_failed'
    assert result['failure_codes'] == ['engine_launch_failed']
    assert result['engine_launch_attempted'] is True
    assert result['evaluation'] is None
    assert (output / 'attempt.json').is_file()
    verified = practice.verify(pgn, engine, output, pins=pins)
    assert verified['comparison_status'] == 'unresolved'
    assert verified['run_status'] == 'unresolved'
    assert verified['reason'] == 'engine_launch_failed'


def test_evaluator_exception_keeps_unresolved_result_and_closes_engine(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'evaluator-failure'
    fake = FakeEngine()

    def fail_evaluator(*_, **__):
        raise RuntimeError('synthetic evaluator failure')

    result = practice.run(pgn, engine, 'g1f3', output, pins=pins,
                          engine_factory=lambda _: fake, evaluator=fail_evaluator)
    assert result['status'] == 'unresolved'
    assert result['reason'] == 'evaluator_failed_or_rejected'
    assert result['failure_codes'] == ['evaluator_failed_or_rejected']
    assert result['evaluation'] is None
    assert result['engine_cleanup'] == 'closed'
    assert fake.closed
    assert practice.verify(pgn, engine, output, pins=pins)['comparison_status'] == 'unresolved'


def test_failed_search_retains_all_phase_states_and_verifies_as_unresolved(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'failed-search'

    class FailedSearchEngine(FakeEngine):
        def analysis(self, *args, **kwargs):
            raise RuntimeError('synthetic search failure')

    fake = FailedSearchEngine()
    result = practice.run(pgn, engine, 'g1f3', output, pins=pins,
                          engine_factory=lambda _: fake)
    assert result['status'] == 'unresolved'
    assert result['reason'] == 'engine_exception'
    assert [item['status'] for item in result['evaluation']['attempts']] == [
        'failed', 'not_run', 'not_run']
    assert result['evaluation']['comparison']['observed_loss_cp'] is None
    assert result['engine_cleanup'] == 'closed'
    assert fake.closed
    assert practice.verify(pgn, engine, output, pins=pins)['comparison_status'] == 'unresolved'


def test_evaluator_and_cleanup_failures_are_both_retained(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'dual-failure'

    class FailingQuit(FakeEngine):
        def quit(self):
            raise OSError('synthetic quit failure')

    def fail_evaluator(*_, **__):
        raise RuntimeError('synthetic evaluator failure')

    result = practice.run(pgn, engine, 'g1f3', output, pins=pins,
                          engine_factory=lambda _: FailingQuit(), evaluator=fail_evaluator)
    assert result['status'] == 'unresolved'
    assert result['reason'] == 'engine_cleanup_failed'
    assert result['failure_codes'] == ['evaluator_failed_or_rejected', 'engine_cleanup_failed']
    assert practice.verify(pgn, engine, output, pins=pins)['run_status'] == 'unresolved'


def test_bad_evaluator_record_cannot_forward_a_pv(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'bad-evaluator'
    prepared = practice.prepare(pgn, engine, 'g1f3', pins=pins)

    def leak(*_, **kwargs):
        return {'schema': practice.contrast.SCHEMA,
                'source_receipt_sha256': kwargs['source_receipt_sha256'],
                'position_sha256': prepared.position_sha256,
                'fen_before': prepared.board.fen(),
                'selected_uci': 'g1f3', 'engine_sha256': pins.engine_sha256,
                'pv_uci': ['g1f3', 'b8c6'], 'attempts': [],
                'comparison': {'status': 'unresolved'}}

    result = practice.run(pgn, engine, 'g1f3', output, pins=pins,
                          engine_factory=lambda _: FakeEngine(), evaluator=leak)
    assert result['status'] == 'unresolved'
    assert result['reason'] == 'evaluator_failed_or_rejected'
    assert 'pv_uci' not in (output / 'result.json').read_text()


def test_verifier_rejects_result_tampering_and_missing_result(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'review'
    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: FakeEngine())
    result_path = output / 'result.json'
    raw = result_path.read_bytes()
    result_path.write_bytes(raw.replace(b'"g1f3"', b'"d2d4"', 1))
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)
    result_path.unlink()
    with pytest.raises(FileNotFoundError):
        practice.verify(pgn, engine, output, pins=pins)


def test_verifier_rejects_coherently_resealed_failure_as_observation(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'failed-launch'
    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: (_ for _ in ()).throw(OSError('synthetic failure')))
    result_path = output / 'result.json'
    result = json.loads(result_path.read_bytes())
    result['status'] = 'observed'
    result_path.write_bytes(practice._canonical(result))
    seal_path = output / 'seal.json'
    seal = json.loads(seal_path.read_bytes())
    seal['result_sha256'] = sha256(result_path.read_bytes()).hexdigest()
    seal_path.write_bytes(practice._canonical(seal))
    with pytest.raises(ValueError, match='result_state_mismatch'):
        practice.verify(pgn, engine, output, pins=pins)


def reseal_result(output, result):
    raw = practice._canonical(result)
    (output / 'result.json').write_bytes(raw)
    seal_path = output / 'seal.json'
    seal = json.loads(seal_path.read_bytes())
    seal['result_sha256'] = sha256(raw).hexdigest()
    seal_path.write_bytes(practice._canonical(seal))


def test_run_rejects_empty_observations_disguised_as_measured_loss(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'empty-observations'
    prepared = practice.prepare(pgn, engine, 'g1f3', pins=pins)
    source_sha = sha256(prepared.source_bytes).hexdigest()
    good = practice.contrast.evaluate(
        prepared.board, 'g1f3', source_receipt_sha256=source_sha,
        expected_position_sha256=prepared.position_sha256,
        engine_sha256=pins.engine_sha256, engine=FakeEngine())
    for attempt in good['attempts']:
        attempt['observations'] = []
    result = practice.run(pgn, engine, 'g1f3', output, pins=pins,
                          engine_factory=lambda _: FakeEngine(),
                          evaluator=lambda *_, **__: good)
    assert result['status'] == 'unresolved'
    assert result['reason'] == 'evaluator_failed_or_rejected'
    assert result['evaluation'] is None


def test_verify_rejects_coherently_resealed_loss_without_scores(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'tampered-observations'
    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: FakeEngine())
    result = json.loads((output / 'result.json').read_bytes())
    for attempt in result['evaluation']['attempts']:
        attempt['observations'] = []
    reseal_result(output, result)
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)


def test_verify_rejects_coherently_resealed_numeric_and_settings_tampering(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'tampered-score'
    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: FakeEngine())
    original = json.loads((output / 'result.json').read_bytes())
    changed = json.loads(json.dumps(original))
    changed['evaluation']['comparison']['observed_loss_cp'] = 999
    reseal_result(output, changed)
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)
    changed = json.loads(json.dumps(original))
    changed['evaluation']['settings']['node_budgets'] = [1, 1]
    changed['evaluation']['settings_sha256'] = practice.contrast._digest(
        practice.contrast._canonical(changed['evaluation']['settings']))
    reseal_result(output, changed)
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)


def test_run_and_verify_bind_driver_and_evaluator_source_bytes(tmp_path, monkeypatch):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'source-hashes'
    result = practice.run(pgn, engine, 'g1f3', output, pins=pins,
                          engine_factory=lambda _: FakeEngine())
    source = json.loads((output / 'source.json').read_bytes())
    attempt = json.loads((output / 'attempt.json').read_bytes())
    assert source['implementation_sha256'] == attempt['implementation_sha256'] == result['implementation_sha256']
    assert source['implementation_sha256']['driver'] == sha256(
        Path(practice.__file__).read_bytes()).hexdigest()
    assert source['implementation_sha256']['evaluator'] == sha256(
        Path(practice.contrast.__file__).read_bytes()).hexdigest()
    original_hashes = practice._implementation_hashes
    monkeypatch.setattr(practice, '_implementation_hashes',
                        lambda: {**original_hashes(), 'evaluator': '0' * 64})
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)


def test_verify_rejects_resealed_failed_discovery_request_tamper(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'failed-discovery-request'

    class FailedSearchEngine(FakeEngine):
        def analysis(self, *args, **kwargs):
            raise RuntimeError('synthetic search failure')

    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: FailedSearchEngine())
    result = json.loads((output / 'result.json').read_bytes())
    result['evaluation']['attempts'][0]['request_sha256'] = '0' * 64
    reseal_result(output, result)
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)


def test_verify_requires_boolean_evaluator_only(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'typed-flag'
    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: FakeEngine())
    result = json.loads((output / 'result.json').read_bytes())
    result['evaluation']['evaluator_only'] = 1
    reseal_result(output, result)
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)


def test_verify_keeps_skipped_high_phase_after_low_search_failure(tmp_path):
    pgn, engine, pins = fixture(tmp_path)
    output = tmp_path / 'failed-low'

    class FailedLowEngine(FakeEngine):
        requests = 0

        def analysis(self, *args, **kwargs):
            self.requests += 1
            if self.requests == 2:
                raise RuntimeError('synthetic low search failure')
            return super().analysis(*args, **kwargs)

    practice.run(pgn, engine, 'g1f3', output, pins=pins,
                 engine_factory=lambda _: FailedLowEngine())
    result = json.loads((output / 'result.json').read_bytes())
    assert result['evaluation']['attempts'][2]['reason'] == 'earlier_stage'
    result['evaluation']['attempts'][2]['reason'] = 'pretend_high_budget_completed'
    reseal_result(output, result)
    with pytest.raises(ValueError):
        practice.verify(pgn, engine, output, pins=pins)
