"""Product checks for the offline, real-data chess review page."""
import copy
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_real_evidence_interface as interface


def test_build_is_source_bound_and_create_only(tmp_path):
    output = tmp_path / 'review.html'
    assert interface.main(['build', '--output', str(output)]) == 0
    page = output.read_text(encoding='utf-8')
    assert page.count('class="case" id="case-') == 8
    assert page.count('<svg ') == 16
    assert page.count('Open source game ↗') == 8
    assert page.count('Strategic explanation withheld') == 8
    assert 'Eight positions from real public games' in page
    assert 'No new model or engine call is made by this page' in page
    assert '0</strong><span>Admitted model explanations' in page
    assert interface.main(['verify', '--output', str(output)]) == 0
    with pytest.raises(FileExistsError):
        interface.main(['build', '--output', str(output)])
    output.write_text(page.replace('Eight positions', 'Nine positions'), encoding='utf-8')
    with pytest.raises(ValueError, match='interface_output_differs'):
        interface.main(['verify', '--output', str(output)])


def test_boards_keep_original_player_at_bottom(monkeypatch):
    typed = json.loads(interface.TYPED.read_text(encoding='utf-8'))
    black_row = next(row for row in typed['positions'] if chess.Board(row['fen']).turn == chess.BLACK)
    white_row = next(row for row in typed['positions'] if chess.Board(row['fen']).turn == chess.WHITE)
    calls = []
    real_renderer = interface.chess.svg.board

    def spy(board, **kwargs):
        calls.append((board.fen(), kwargs['orientation']))
        return real_renderer(board, **kwargs)

    monkeypatch.setattr(interface.chess.svg, 'board', spy)
    for row in (black_row, white_row):
        page = interface.render_case(row, None, 0)
        assert 'Before move' in page and 'After ' in page
        assert calls[-2][1] == chess.Board(row['fen']).turn
        assert calls[-1][1] == chess.Board(row['fen']).turn
        assert calls[-2][0] == row['fen']
        assert calls[-1][0] != row['fen']


def test_failed_case_is_visible_without_false_engine_claims():
    typed = json.loads(interface.TYPED.read_text(encoding='utf-8'))
    row = copy.deepcopy(typed['positions'][0])
    row['status'] = 'failed'
    row['error'] = {'message': '<script>not available</script>'}
    page = interface.render_case(row, None, 0)
    assert 'Evidence unavailable' in page
    assert '&lt;script&gt;not available&lt;/script&gt;' in page
    assert '<script>' not in page
    assert '<svg' not in page
    assert 'No move or engine claim is displayed' in page


def test_source_link_and_transition_tampering_fail_closed():
    typed = json.loads(interface.TYPED.read_text(encoding='utf-8'))
    row = copy.deepcopy(typed['positions'][0])
    row['source_url'] = 'https://example.invalid/other'
    with pytest.raises(ValueError, match='unexpected_source_game_url'):
        interface.render_case(row, None, 0)
    row = copy.deepcopy(typed['positions'][0])
    row['engine_evidence'][0]['transition']['fen_after'] = row['fen']
    with pytest.raises(ValueError, match='candidate_transition_not_replayed'):
        interface.render_case(row, None, 0)
