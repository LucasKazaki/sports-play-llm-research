"""Software controls for a user-game packet; fixtures are not real chess evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_review_completed_game as previous
import chess_paired_review_v3 as paired
import chess_user_game_no_forward_v1 as user_packet


PGN = '''[Event "Private software fixture"]
[Site "local"]
[White "PrivateName"]
[Black "OtherName"]
[Result "1-0"]

1. e4 $2 {future annotation and forced-win label} e5 2. Nf3 Nc6 1-0
'''


@pytest.fixture
def source_bundle(tmp_path, monkeypatch):
    pgn = tmp_path / 'private.pgn'
    pgn.write_text(PGN, encoding='utf-8')
    game, raw, moves = previous.load_completed_game(pgn)

    class FakeEngine:
        id = {'name': 'Stockfish 19'}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def configure(self, options):
            assert options == {'Threads': 1, 'Hash': 16}

        def analyse(self, board, limit, *, root_moves=None, multipv=None):
            e4 = chess.Move.from_uci('e2e4')
            d4 = chess.Move.from_uci('d2d4')
            if root_moves is None:
                return [{'pv': [d4]}, {'pv': [e4]}]
            assert root_moves == [e4, d4] and multipv == 2
            return [
                {'pv': [d4, chess.Move.from_uci('d7d5')],
                 'score': chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE),
                 'nodes': 600, 'depth': 7},
                {'pv': [e4, chess.Move.from_uci('e7e5')],
                 'score': chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
                 'nodes': 400, 'depth': 7},
            ]

    monkeypatch.setattr(previous, 'engine_ready', lambda: {'status': 'software-fixture'})
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', lambda _: FakeEngine())
    record = paired.analyze(game, raw, moves, 1, 1000)
    review_dir = tmp_path / 'review'
    review_dir.mkdir()
    receipt = review_dir / 'review.json'
    page = review_dir / 'index.html'
    receipt.write_bytes(previous.canonical(record) + b'\n')
    page.write_bytes(paired.render(record))
    return (pgn, review_dir, previous.digest(raw),
            previous.digest(receipt.read_bytes()), previous.digest(page.read_bytes()))


def test_played_packet_excludes_future_annotations_other_move_and_pv(source_bundle):
    packet = user_packet.build_packet(*source_bundle, role='played')
    encoded = user_packet.encode_packet(*source_bundle, role='played', packet=packet)
    assert encoded == cf.canonical(packet)
    assert packet['source']['use_role'] == 'postgame_practice_only'
    assert packet['source']['move_role'] == 'played'
    assert packet['selected_move'] == {'uci': 'e2e4', 'san': 'e4'}
    assert packet['engine_observation']['score']['value'] == 10
    assert packet['engine_observation']['score']['perspective'] == 'side_to_move'
    assert packet['engine_observation']['score']['bound'] == 'exact'
    assert packet['fen'] == chess.STARTING_FEN
    for forbidden in (b'pv_uci', b'fen_after', b'post_move_fen', b'future_moves',
                      b'solution', b'themes', b'annotations', b'PrivateName',
                      b'OtherName', b'future annotation', b'forced-win', b'd2d4'):
        assert forbidden not in encoded


def test_alternative_packet_contains_only_alternative_evidence(source_bundle):
    packet = user_packet.build_packet(*source_bundle, role='alternative')
    encoded = user_packet.encode_packet(*source_bundle, role='alternative', packet=packet)
    assert packet['source']['move_role'] == 'alternative'
    assert packet['selected_move'] == {'uci': 'd2d4', 'san': 'd4'}
    assert packet['engine_observation']['score']['value'] == 25
    assert b'e2e4' not in encoded


@pytest.mark.parametrize('path', [(), ('source',), ('selected_move',),
                                  ('transition',), ('engine_observation',),
                                  ('engine_observation', 'score')])
def test_unknown_fields_rejected_before_bytes(source_bundle, path):
    packet = user_packet.build_packet(*source_bundle, role='played')
    target = packet
    for name in path:
        target = target[name]
    target['pv_uci'] = ['forbidden-future']
    with pytest.raises(ValueError, match='user_game_no_forward_'):
        user_packet.encode_packet(*source_bundle, role='played', packet=packet)


@pytest.mark.parametrize('path,value', [
    (('fen',), chess.Board().copy().fen().replace(' w ', ' b ')),
    (('selected_move', 'uci'), 'd2d4'),
    (('transition', 'capture'), True),
    (('engine_observation', 'score', 'value'), 900),
    (('source', 'move_role'), 'alternative'),
    (('source', 'use_role'), 'heldout'),
])
def test_changed_allowed_values_rejected_before_bytes(source_bundle, path, value):
    packet = user_packet.build_packet(*source_bundle, role='played')
    target = packet
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = value
    with pytest.raises(ValueError, match='user_game_no_forward_'):
        user_packet.encode_packet(*source_bundle, role='played', packet=packet)


def test_pgn_receipt_and_page_drift_rejected(source_bundle, tmp_path):
    pgn, review, pgn_sha, review_sha, page_sha = source_bundle
    altered_pgn = tmp_path / 'altered.pgn'
    altered_pgn.write_bytes(pgn.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='pgn_sha256_changed'):
        user_packet.build_packet(altered_pgn, review, pgn_sha, review_sha, page_sha,
                                 role='played')
    page = review / 'index.html'
    page.write_bytes(page.read_bytes().replace(b'Paired search', b'Proven best move'))
    with pytest.raises(ValueError, match='review_page_sha256_changed'):
        user_packet.build_packet(pgn, review, pgn_sha, review_sha, page_sha,
                                 role='played')
    new_page_sha = previous.digest(page.read_bytes())
    with pytest.raises(ValueError, match='review_page_differs_from_receipt'):
        user_packet.build_packet(pgn, review, pgn_sha, review_sha, new_page_sha,
                                 role='played')


def test_review_receipt_drift_rejected(source_bundle):
    pgn, review, pgn_sha, review_sha, page_sha = source_bundle
    receipt = review / 'review.json'
    receipt.write_bytes(receipt.read_bytes() + b' ')
    with pytest.raises(ValueError, match='review_sha256_changed'):
        user_packet.build_packet(pgn, review, pgn_sha, review_sha, page_sha,
                                 role='played')
    changed_sha = previous.digest(receipt.read_bytes())
    with pytest.raises(ValueError, match='review_receipt_not_canonical'):
        user_packet.build_packet(pgn, review, pgn_sha, changed_sha, page_sha,
                                 role='played')


def test_create_only_build_and_offline_verify(source_bundle, tmp_path):
    pgn, review, pgn_sha, review_sha, page_sha = source_bundle
    output = tmp_path / 'packet.json'
    args = ['--pgn', str(pgn), '--review-dir', str(review),
            '--pgn-sha256', pgn_sha, '--review-sha256', review_sha,
            '--page-sha256', page_sha, '--role', 'played', '--output', str(output)]
    assert user_packet.main(['build', *args]) == 0
    assert user_packet.main(['verify', *args]) == 0
    with pytest.raises(FileExistsError):
        user_packet.main(['build', *args])
    output.write_bytes(output.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='user_game_packet_file_not_canonical'):
        user_packet.main(['verify', *args])


def test_invalid_role_rejected(source_bundle):
    with pytest.raises(ValueError, match='invalid_user_game_move_role'):
        user_packet.build_packet(*source_bundle, role='heldout')
