"""Typed UCI score observations, retaining qualification and explicit perspective.

Bounds follow python-chess Score ordering, including mate ordering. They are not
centipawn intervals or statistical confidence. No engine truth is inferred here.
"""
import chess.engine


def typed_score_bound(info, turn):
    if not isinstance(info, dict) or type(turn) is not bool:
        raise ValueError('info must be a dictionary and turn a boolean')
    score = info.get('score')
    if not isinstance(score, chess.engine.PovScore) or type(score.turn) is not bool:
        raise ValueError('score must be a PovScore with a boolean source perspective')
    lower, upper = info.get('lowerbound', False), info.get('upperbound', False)
    if type(lower) is not bool or type(upper) is not bool or (lower and upper):
        raise ValueError('score qualifiers must be booleans and cannot both hold')
    original = score.relative
    if not isinstance(original, chess.engine.Score):
        raise ValueError('original score must have an engine Score type')
    original_value = original.mate() if original.is_mate() else original.score()
    if type(original_value) is not int:
        raise ValueError('original score must be an integer before perspective conversion')
    converted = score.pov(turn)
    kind = 'mate' if converted.is_mate() else 'cp'
    value = converted.mate() if kind == 'mate' else converted.score()
    if type(value) is not int:
        raise ValueError('score value must be an integer, not a coerced value')
    bound = 'lower' if lower else 'upper' if upper else 'exact'
    if turn != score.turn:
        bound = {'lower': 'upper', 'upper': 'lower', 'exact': 'exact'}[bound]
    result = {'type': kind, 'value': value, 'perspective': 'side_to_move',
              'side_to_move': 'white' if turn else 'black', 'bound': bound, 'order': 'engine_score'}
    if kind == 'mate' and value == 0:
        result['mate_zero'] = 'delivered' if converted == chess.engine.MateGiven else 'received'
    return result
