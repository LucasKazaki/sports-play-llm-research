"""Deterministic score-type regressions; no real-data or engine-quality claims."""
import copy
import chess
import chess.engine as ce
import pytest
from scripts.chess_score_bounds import typed_score_bound


@pytest.mark.parametrize('turn,source_turn,score,value,kind,zero', [
    (True, True, ce.Cp(83), 83, 'cp', None),
    (False, True, ce.Cp(83), -83, 'cp', None),
    (False, False, ce.Cp(-54), -54, 'cp', None),
    (True, False, ce.Cp(0), 0, 'cp', None),
    (True, True, ce.Mate(3), 3, 'mate', None),
    (False, True, ce.Mate(3), -3, 'mate', None),
    (True, True, ce.Mate(0), 0, 'mate', 'received'),
    (False, True, ce.Mate(0), 0, 'mate', 'delivered'),
    (True, True, ce.MateGiven, 0, 'mate', 'delivered'),
    (False, True, ce.MateGiven, 0, 'mate', 'received'),
])
@pytest.mark.parametrize('flags,bound', [({}, 'exact'), ({'lowerbound': True}, 'lower'),
    ({'upperbound': True}, 'upper'), ({'lowerbound': False, 'upperbound': False}, 'exact')])
def test_score_perspective_and_bound_order(turn, source_turn, score, value, kind, zero, flags, bound):
    info = {'score': ce.PovScore(score, source_turn), **flags}
    before = copy.deepcopy(info)
    expected_bound = {'lower': 'upper', 'upper': 'lower', 'exact': 'exact'}[bound] if turn != source_turn else bound
    expected = {'type': kind, 'value': value, 'perspective': 'side_to_move',
        'side_to_move': 'white' if turn else 'black', 'bound': expected_bound, 'order': 'engine_score'}
    if zero:
        expected['mate_zero'] = zero
    assert typed_score_bound(info, turn) == expected
    assert info == before


@pytest.mark.parametrize('flags', [
    {'lowerbound': True, 'upperbound': True}, {'lowerbound': 1}, {'upperbound': 0},
    {'lowerbound': None}, {'upperbound': 'false'},
])
def test_invalid_qualifiers_fail(flags):
    with pytest.raises(ValueError):
        typed_score_bound({'score': ce.PovScore(ce.Cp(1), True), **flags}, True)


@pytest.mark.parametrize('info,turn', [({}, True), ({'score': 1}, True),
    ({'score': ce.PovScore(ce.Cp(1), True)}, 1), (None, True),
    ({'score': ce.PovScore(ce.Cp(1), 1)}, True),
    ({'score': ce.PovScore(ce.Cp(1.5), True)}, True),
    ({'score': ce.PovScore(ce.Cp(True), True)}, True)])
def test_invalid_score_types_fail(info, turn):
    with pytest.raises(ValueError):
        typed_score_bound(info, turn)


@pytest.mark.parametrize('score', [ce.Cp(True), ce.Cp(False), ce.Mate(True), ce.Mate(False)])
@pytest.mark.parametrize('turn', [True, False])
def test_boolean_original_score_cannot_be_hidden_by_perspective_conversion(score, turn):
    with pytest.raises(ValueError):
        typed_score_bound({'score': ce.PovScore(score, True)}, turn)
