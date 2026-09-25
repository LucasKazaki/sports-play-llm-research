"""Controlled UCI lines exercise the installed parser; no engine or model runs."""
import asyncio
import copy

import chess
import chess.engine
import pytest

from test_chess_counterfactual_evidence import cf, DATA


class RawStream:
    def __init__(self, events, blocked=False):
        self.events = iter(events)
        self.blocked = blocked
        self.stopped = False
        self.finished = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stopped = True

    def would_block(self):
        return self.blocked

    def next(self):
        value = next(self.events, None)
        if value is None:
            self.finished = True
        return value


def parsed_events(board, final_bound='', missing='', early_bound='lowerbound'):
    moves = sorted(board.legal_moves, key=lambda move: move.uci())[:2]
    lines = [f'depth 2 multipv 1 score cp 10 {early_bound} nodes 200 pv {moves[0].uci()}',
             f'depth 3 multipv 2 score cp 9 nodes 300 pv {moves[1].uci()}',
             f'depth 4 multipv 1 score cp 20 {final_bound} nodes 100003 pv {moves[0].uci()}',
             'nodes 100099 string trailing update without a score']
    events = [chess.engine._parse_uci_info(line, board, chess.engine.INFO_ALL) for line in lines]
    if missing:
        events[2].pop(missing)
    return events


async def aggregate(events):
    result = chess.engine.AnalysisResult()
    for event in events:
        result.post(copy.copy(event))
    return copy.deepcopy(result.multipv)


class ParserEngine:
    """Both APIs see the same raw sequence, including the actual aggregation bug."""
    def __init__(self, **event_options):
        self.event_options = event_options
        self.calls = []
        self.streams = []
        self.closed = False

    def configure(self, options):
        assert options == {'Threads': 1, 'Hash': 16}

    def events(self, board, limit, *, multipv, game):
        assert not self.closed
        self.calls.append((board.copy(stack=True), limit.nodes, multipv, game))
        return parsed_events(board, **self.event_options)

    def analyse(self, *args, **kwargs):
        return asyncio.run(aggregate(self.events(*args, **kwargs)))

    def analysis(self, *args, **kwargs):
        stream = RawStream(self.events(*args, **kwargs))
        self.streams.append(stream)
        return stream

    def close(self):
        self.closed = True


def test_installed_parser_aggregate_retains_old_bound_but_raw_event_does_not():
    events = parsed_events(chess.Board())
    merged = asyncio.run(aggregate(events))
    assert merged[0]['lowerbound'] is True
    assert merged[0]['score'].relative.score() == 20
    assert merged[0]['nodes'] == 100099
    assert 'lowerbound' not in events[2]
    assert events[2]['nodes'] == 100003


@pytest.mark.parametrize('early_bound', ['lowerbound', 'upperbound'])
def test_stale_earlier_bound_does_not_invalidate_later_unmarked_score_event(early_bound):
    # This assertion fails against the original collector with the actual installed
    # AnalysisResult aggregation, before any new API or receipt-field assertion.
    engine = ParserEngine(early_bound=early_bound)
    value = cf.collect_receipt(DATA, engine, cf.ENGINE_SHA256)
    assert cf.verify_receipt(DATA, value)['complete'] is True, value['results'][0].get('error')
    assert all(stream.finished and stream.stopped for stream in engine.streams)
    assert len(engine.calls) == 8 and not engine.closed
    assert all(len(board.move_stack) == 1 and nodes == 100000 and multipv == 2
               for board, nodes, multipv, game in engine.calls)
    assert len({game for board, nodes, multipv, game in engine.calls}) == 8
    for row in value['results']:
        first, second = row['candidates']
        assert (first['score']['value'], first['depth'], first['nodes_observed'], first['score_info_sequence']) == (20, 4, 100003, 3)
        assert (second['score']['value'], second['depth'], second['nodes_observed'], second['score_info_sequence']) == (9, 3, 300, 2)


@pytest.mark.parametrize('final_bound', ['lowerbound', 'upperbound'])
def test_actual_latest_bound_stays_failed_even_after_an_unmarked_score(final_bound):
    engine = ParserEngine(early_bound='', final_bound=final_bound)
    value = cf.collect_receipt(DATA, engine, cf.ENGINE_SHA256)
    assert cf.verify_receipt(DATA, value)['failed_positions'] == 8
    assert all(row['candidates'] == [] and row['error']['message'] == 'engine_bound_score_not_supported'
               for row in value['results'])
    assert all(stream.finished and stream.stopped for stream in engine.streams)


@pytest.mark.parametrize('missing', ['pv', 'nodes', 'depth'])
def test_latest_incomplete_score_event_cannot_borrow_fields_from_earlier_event(missing):
    value = cf.collect_receipt(DATA, ParserEngine(early_bound='', missing=missing), cf.ENGINE_SHA256)
    assert cf.verify_receipt(DATA, value)['failed_positions'] == 8
    assert all(row['candidates'] == [] for row in value['results'])


@pytest.mark.parametrize('mode', ['timeout', 'event_budget', 'missing_rank'])
def test_stream_bounds_and_eof_fail_honestly_and_close_unfinished_engine(monkeypatch, mode):
    class BoundedEngine(ParserEngine):
        def analysis(self, *args, **kwargs):
            events = self.events(*args, **kwargs)
            if mode == 'missing_rank':
                events = [events[0]]
            stream = RawStream(events, blocked=mode == 'timeout')
            self.streams.append(stream)
            return stream
    if mode == 'timeout':
        monkeypatch.setattr(cf, 'STREAM_TIMEOUT_SECONDS', 0)
    if mode == 'event_budget':
        monkeypatch.setattr(cf, 'MAX_INFO_EVENTS', 1)
    engine = BoundedEngine()
    value = cf.collect_receipt(DATA, engine, cf.ENGINE_SHA256)
    assert cf.verify_receipt(DATA, value)['failed_positions'] == 8
    assert all(stream.stopped for stream in engine.streams)
    assert engine.closed is (mode != 'missing_rank')
    assert len(engine.calls) == (8 if mode == 'missing_rank' else 1)
    assert all(row['candidates'] == [] for row in value['results'])
