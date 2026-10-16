"""Offline, evaluator-only checks of manually mapped Queen text spans.

No NLP, model, engine, generator repair, or legacy fixture dependencies. Text
binding proves provenance, not that a human's predicate/branch matches the prose.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re

import chess

SCHEMA = 'chess.queen-claim-audit.v1'
ANNOTATION_SCHEMA = 'chess.queen-claim-annotations.v1'
PROTOCOL_SCHEMA = 'chess.queen-claim-audit-protocol.v1'
MAX_BYTES = 2 * 1024 * 1024
MAX_CLAIMS = 256
MAX_PLIES = 64
PIECES = ('pawn', 'knight', 'bishop', 'rook', 'queen', 'king')
COLORS = {'white': chess.WHITE, 'black': chess.BLACK}
UCI = re.compile(r'[a-h][1-8][a-h][1-8][qrbn]?')
HEX = re.compile(r'[0-9a-f]{64}')
CONTRACT = {
    'span_indexing': 'Python Unicode code points; zero-based [start,end); SHA-256 of exact UTF-8 substring',
    'root': 'response.input.fen only; no annotator replacement FEN',
    'context': 'Explicit legal branch replay and expected side to move; ambiguous or invalid context is unassessed',
    'mapping': 'Human semantic correspondence is required separately; hashes do not establish it',
    'material': 'Counts of pawn/knight/bishop/rook/queen by one side; not piece values or advantage',
    'geometry': 'Occupancy-aware attack geometry includes pinned pieces; never legal recapture or tactical success',
    'variation': 'Explicit asserted line only; no engine attribution or whole-prose inference',
    'history': 'Standalone current FEN and explicit branch only; prior repetition is not inferred',
    'purpose': 'Evaluator only; never generator input, repair, training target or current heldout metric',
}


class BindingError(ValueError):
    """Exact source/span binding failed: no claim verdict may be accepted."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _utf8(text):
    try:
        return text.encode('utf-8')
    except UnicodeError as exc:
        raise BindingError('Text is not valid UTF-8.') from exc


def decode_json(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise BindingError('Expected a nonempty bounded JSON byte string.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BindingError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise BindingError('Nonfinite JSON value: ' + value)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise BindingError('Invalid or ambiguous JSON: ' + str(exc)) from exc


def _hash(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def _keys(value, required):
    return type(value) is dict and set(value) == set(required)


def _moves(value, allow_empty=False):
    return (type(value) is list and (0 if allow_empty else 1) <= len(value) <= MAX_PLIES
            and all(type(move) is str and UCI.fullmatch(move) and move[:2] != move[2:4] for move in value))


def _root(response):
    packet = response.get('input')
    if type(packet) is not dict or 'fen' not in packet or set(packet) - {'fen', 'history', 'selected_uci'}:
        return None
    fen = packet['fen']
    if type(fen) is not str or len(fen) > 200 or len(fen.split()) != 6:
        return None
    if re.fullmatch(r'-|K?Q?k?q?', fen.split()[2]) is None:
        return None
    try:
        board = chess.Board(fen, chess960=False)
        return board if board.is_valid() else None
    except ValueError:
        return None


def replay(board, moves):
    """Return legal prefix evidence; never push an illegal move or skip a ply."""
    current = board.copy(stack=True)
    for index, text in enumerate(moves):
        move = chess.Move.from_uci(text)
        reason = 'game_over' if current.is_game_over(claim_draw=False) else 'move_not_legal' if move not in current.legal_moves else None
        if reason:
            return None, {'legal': False, 'failed_ply': index + 1, 'uci': text,
                          'reason': reason, 'turn': chess.COLOR_NAMES[current.turn],
                          'fen_before_failure': current.fen(), 'legal_prefix_uci': moves[:index]}
        current.push(move)
    return current, {'legal': True, 'plies': len(moves), 'fen_after': current.fen()}


def _context(root, context):
    if not _keys(context, ('resolution', 'branch_uci', 'expected_turn')):
        return None, {'reason': 'unsupported_context_fields'}
    if context['resolution'] != 'explicit':
        return None, {'reason': 'ambiguous_or_unresolved_context'}
    if not _moves(context['branch_uci'], allow_empty=True) or context['expected_turn'] not in ('white', 'black'):
        return None, {'reason': 'invalid_context_branch_or_turn'}
    board, evidence = replay(root, context['branch_uci'])
    if board is None:
        return None, {'reason': 'illegal_context_prefix', 'prefix_failure': evidence}
    if chess.COLOR_NAMES[board.turn] != context['expected_turn']:
        return None, {'reason': 'context_turn_mismatch', 'actual_turn': chess.COLOR_NAMES[board.turn]}
    return board, {'branch_uci': list(context['branch_uci']), 'turn': context['expected_turn'], 'fen': board.fen()}


def _unassessed(reason, **evidence):
    return {'status': 'unassessed', 'reason': reason, **evidence}


def _judged(expected, observed, **evidence):
    return {'status': 'supported' if expected == observed else 'contradicted',
            'expected': expected, 'observed': observed, **evidence}


def _predicate(board, claim):
    if type(claim) is not dict:
        return _unassessed('unsupported_claim_shape')
    kind = claim.get('kind')
    if kind == 'piece_count':
        if (not _keys(claim, ('kind', 'color', 'piece_type', 'expected'))
                or claim['color'] not in ('white', 'black') or claim['piece_type'] not in PIECES
                or type(claim['expected']) is not int or not 0 <= claim['expected'] <= 16):
            return _unassessed('unsupported_piece_count')
        observed = len(board.pieces(PIECES.index(claim['piece_type']) + 1, COLORS[claim['color']]))
        return _judged(claim['expected'], observed, scope='Literal current-board count only.')
    if kind == 'material_count':
        expected = claim.get('expected')
        if (not _keys(claim, ('kind', 'color', 'expected')) or claim['color'] not in ('white', 'black')
                or not _keys(expected, PIECES[:5])
                or any(type(v) is not int or not 0 <= v <= 16 for v in expected.values())):
            return _unassessed('unsupported_material_count')
        observed = {name: len(board.pieces(index + 1, COLORS[claim['color']])) for index, name in enumerate(PIECES[:5])}
        return _judged(expected, observed, scope='Non-king piece counts only; no point score, advantage or evaluation.')
    if kind == 'geometric_attacks_square':
        if (not _keys(claim, ('kind', 'piece', 'from_square', 'target_square', 'expected'))
                or not _keys(claim['piece'], ('color', 'type'))
                or claim['piece']['color'] not in ('white', 'black') or claim['piece']['type'] not in PIECES
                or type(claim['expected']) is not bool
                or any(type(claim[s]) is not str or re.fullmatch(r'[a-h][1-8]', claim[s]) is None for s in ('from_square', 'target_square'))):
            return _unassessed('unsupported_geometric_attack')
        start, target = chess.parse_square(claim['from_square']), chess.parse_square(claim['target_square'])
        piece = board.piece_at(start)
        if piece is None or {'color': chess.COLOR_NAMES[piece.color], 'type': chess.piece_name(piece.piece_type)} != claim['piece']:
            return _unassessed('attacker_identity_not_present')
        victim = board.piece_at(target)
        return _judged(claim['expected'], target in board.attacks(start),
                       attacker_is_pinned=board.is_pinned(piece.color, start),
                       target_occupant=chess.piece_symbol(victim.piece_type) if victim else None,
                       scope='Occupancy-aware geometric attack, including pinned pieces and friendly occupied targets. Not legal capture/recapture, defense success or king safety.')
    if kind == 'legal_variation':
        if not _keys(claim, ('kind', 'moves_uci', 'expected')) or type(claim['expected']) is not bool or not _moves(claim['moves_uci']):
            return _unassessed('unsupported_legal_variation')
        _, evidence = replay(board, claim['moves_uci'])
        return _judged(claim['expected'], evidence['legal'], variation=evidence,
                       scope='This explicitly annotated variation only. No forcedness, quality, engine attribution or whole-prose validity.')
    return _unassessed('unsupported_claim_kind')


def audit_response(response_bytes, annotations):
    """Validate every source/span binding before producing any claim verdict."""
    response = decode_json(response_bytes)
    if type(response) is not dict or type(response.get('raw_text')) is not str:
        raise BindingError('A response object with exact raw_text is required.')
    if not _keys(annotations, ('schema', 'response_sha256', 'raw_text_sha256', 'claims')) or annotations['schema'] != ANNOTATION_SCHEMA:
        raise BindingError('Unsupported annotation envelope.')
    raw_text = response['raw_text']
    if not _hash(annotations['response_sha256']) or digest(response_bytes) != annotations['response_sha256']:
        raise BindingError('Raw response byte hash mismatch.')
    if not _hash(annotations['raw_text_sha256']) or digest(_utf8(raw_text)) != annotations['raw_text_sha256']:
        raise BindingError('raw_text hash mismatch.')
    claims = annotations['claims']
    if type(claims) is not list or len(claims) > MAX_CLAIMS:
        raise BindingError('Expected at most 256 annotated claims.')
    identifiers = set()
    for row in claims:
        if not _keys(row, ('claim_id', 'span', 'context', 'claim')):
            raise BindingError('Malformed annotation row.')
        identifier, span = row['claim_id'], row['span']
        if type(identifier) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier) or identifier in identifiers:
            raise BindingError('Missing, invalid or duplicate claim ID.')
        identifiers.add(identifier)
        if (not _keys(span, ('start', 'end', 'sha256')) or type(span['start']) is not int or type(span['end']) is not int
                or not 0 <= span['start'] < span['end'] <= len(raw_text) or not _hash(span['sha256'])
                or digest(_utf8(raw_text[span['start']:span['end']])) != span['sha256']):
            raise BindingError('Exact raw_text span/hash mismatch for ' + identifier)
    root, results = _root(response), []
    for row in claims:
        if root is None:
            verdict = _unassessed('invalid_or_unsupported_response_input')
        else:
            board, context = _context(root, row['context'])
            verdict = _unassessed(**context) if board is None else {**_predicate(board, row['claim']), 'context': context}
        span = row['span']
        results.append({'claim_id': row['claim_id'], 'span': dict(span),
                        'exact_raw_text': raw_text[span['start']:span['end']], 'claim': row['claim'], **verdict})
    counts = Counter(row['status'] for row in results)
    assessed = counts['supported'] + counts['contradicted']
    return {'schema': SCHEMA, 'evaluation_only': True, 'response_sha256': digest(response_bytes),
            'raw_text_sha256': digest(_utf8(raw_text)), 'response_status': response.get('status'),
            'root_fen': root.fen() if root else None, 'claims': results,
            'summary': {'annotated': len(results), 'supported': counts['supported'], 'contradicted': counts['contradicted'],
                        'unassessed': counts['unassessed'], 'assessed_annotation_fraction': assessed / len(results) if results else None,
                        'supported_fraction_among_assessed': counts['supported'] / assessed if assessed else None},
            'semantic_mapping_automatically_verified': False, 'whole_prose_coverage_established': False,
            'limitations': list(CONTRACT.values())}


def verify_protocol(raw, expected_sha256):
    if not _hash(expected_sha256) or digest(raw) != expected_sha256:
        raise BindingError('Protocol byte hash mismatch.')
    plan = decode_json(raw)
    if (type(plan) is not dict or plan.get('schema') != PROTOCOL_SCHEMA or plan.get('contract') != CONTRACT
            or plan.get('implementation_sha256') != digest(Path(__file__).read_bytes())
            or plan.get('manual_semantic_review_before_authored_measurement') is not True):
        raise BindingError('Protocol/source/contract mismatch.')
    pool = plan.get('response_pool', {}).get('responses') if type(plan.get('response_pool')) is dict else None
    if (type(pool) is not list or not 1 <= len(pool) <= MAX_CLAIMS
            or any(not _keys(row, ('index', 'path', 'sha256')) or type(row['index']) is not int or row['index'] < 0
                   or type(row['path']) is not str or not row['path'] or not _hash(row['sha256']) for row in pool)
            or len({row['index'] for row in pool}) != len(pool)
            or len({row['sha256'] for row in pool}) != len(pool)):
        raise BindingError('Protocol needs a unique exact response pool.')
    return plan


def read_bounded(path):
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if not 0 < len(raw) <= MAX_BYTES:
        raise BindingError('JSON file exceeds the bounded input limit.')
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('response', 'annotations', 'protocol', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    args = parser.parse_args()
    protocol_bytes = read_bounded(args.protocol)
    plan = verify_protocol(protocol_bytes, args.protocol_sha256)
    response_bytes = read_bounded(args.response)
    pool_row = next((row for row in plan['response_pool']['responses'] if row['sha256'] == digest(response_bytes)), None)
    if pool_row is None:
        raise BindingError('Response bytes are outside the frozen protocol pool.')
    annotation_bytes = read_bounded(args.annotations)
    result = audit_response(response_bytes, decode_json(annotation_bytes))
    result.update(implementation_sha256=digest(Path(__file__).read_bytes()),
                  protocol_sha256=digest(protocol_bytes), annotations_sha256=digest(annotation_bytes),
                  response_pool_index=pool_row['index'])
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with args.out.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
