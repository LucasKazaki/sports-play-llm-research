"""Post-generation, root-only rule checks. No model, engine or prose repair.

Exact spans address response.raw_text in Unicode code points, not translated
display text or response-file bytes. Other prose is always unassessed.
"""
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import chess

SCHEMA = 'chess.tutor-draft-checks.v1'
NATIVE_SHA256 = 'e8f1c2d9d9fb1270e49288d9e39732cf5c2f521fe2e07962015fc776e8bb7ea0'
QUALIFICATION_SHA256 = '0a17fcaa72bef97eec28e4bec0e245c4c42a28219dcf5da6d8c06f807278188d'
MAX_BYTES = 1_048_576
ROOT = Path(__file__).resolve().parents[2]


class BindingError(ValueError):
    pass


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise BindingError('Expected bounded JSON bytes.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BindingError('Duplicate JSON field.')
            result[key] = value
        return result
    def nonfinite(_):
        raise BindingError('Nonfinite JSON value.')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
        if type(result) is not dict:
            raise BindingError('Expected a JSON object.')
        return result
    except (ValueError, UnicodeError) as error:
        raise BindingError('Invalid or ambiguous JSON.') from error


@lru_cache(maxsize=1)
def _load_parser(path):
    spec = importlib.util.spec_from_file_location('_tutor_draft_native_parser_v1', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parser():
    path = ROOT / 'scripts/chess_queen_adapter.py'
    if digest(path.read_bytes()) != NATIVE_SHA256:
        raise BindingError('The pinned move parser changed.')
    return _load_parser(str(path))


def span(text, start, end):
    return {'start': start, 'end': end, 'unit': 'unicode_code_points',
            'sha256': digest(text[start:end].encode('utf-8'))}


def unavailable(reason):
    return {'schema': SCHEMA, 'status': 'unavailable', 'reason': reason,
            'whole_prose_assessed': False, 'claims': [], 'unassessed_regions': []}


def original_profile(result, worker, fixture, qualification_name):
    execution = result.get('execution', {})
    return (not fixture and qualification_name == 'queen-runtime.json'
            and execution.get('qualification_sha256') == QUALIFICATION_SHA256
            and execution.get('canonical_provenance', {}).get('response_binding_verified') is True
            and not result.get('ui_validation_error')
            and worker.get('status') == 'completed' and worker.get('exit_code') == 0
            and worker.get('child_exited_before_lease_release') is True)


def _victim(board, move):
    piece = chess.Piece(chess.PAWN, not board.turn) if board.is_en_passant(move) else board.piece_at(move.to_square)
    return None if piece is None else {'color': chess.COLOR_NAMES[piece.color], 'piece': chess.piece_name(piece.piece_type)}


def _move_record(board, move):
    victim = _victim(board, move)
    after = board.copy(stack=True)
    san = board.san(move)
    after.push(move)
    return after, {'move_uci': move.uci(), 'move_san': san, 'gives_check': after.is_check(),
                   'gives_checkmate': after.is_checkmate(), 'captures': victim is not None,
                   'victim': victim, 'branch_uci': [], 'turn': chess.COLOR_NAMES[board.turn],
                   'scope': 'Immediate legal replay only; no forced reply, bestness or prose-quality verdict.'}


def audit_bytes(response_bytes, input_bytes, input_sha256, packet, context, base_result, *, qualified):
    """Hard reject binding failures; never turn them into supported statements."""
    if digest(input_bytes) != input_sha256:
        raise BindingError('The saved request bytes changed.')
    saved = decode(input_bytes)
    response = decode(response_bytes)
    if saved != packet or response.get('input') != packet or response != base_result:
        raise BindingError('The draft no longer matches its original request or result.')
    text = response.get('raw_text')
    if type(text) is not str or len(text) > 100_000:
        raise BindingError('The exact raw draft is unavailable or too large.')
    try:
        text_hash = digest(text.encode('utf-8'))
    except UnicodeError as error:
        raise BindingError('The draft text is not valid Unicode.') from error
    out = {'schema': SCHEMA, 'status': 'unassessed',
           'response_sha256': digest(response_bytes), 'raw_text_sha256': text_hash,
           'input_sha256': input_sha256, 'verifier_sha256': digest(Path(__file__).read_bytes()),
           'parser_sha256': NATIVE_SHA256, 'whole_prose_assessed': False,
           'claims': [], 'unassessed_regions': [], 'engine_calls': 0, 'generator_repairs': 0,
           'mapping_scope': 'Exact canonical grammar at the requested root only; other prose is unassessed.'}
    if not qualified or response.get('status') != 'completed' or response.get('finish_reason') != 'eos':
        out['reason'] = 'These checks apply only to complete drafts from the original manual model. Other text is unassessed.'
        return out
    native = parser()
    try:
        _, board = native.input_packet(packet)
    except (ValueError, TypeError) as error:
        raise BindingError('Invalid original request.') from error
    if context.get('fen') != board.fen() or context.get('selected_uci') != packet.get('selected_uci'):
        raise BindingError('The requested board or selected move changed.')
    out['context'] = {'fen': board.fen(), 'selected_uci': packet.get('selected_uci'),
                      'branch_uci': [], 'turn': chess.COLOR_NAMES[board.turn]}
    if board.is_game_over(claim_draw=False):
        out['reason'] = 'The requested game was already over.'
        return out
    # History was validated above. Parsing the same current root needs no second history walk.
    parsed = native.parse_output({'fen': board.fen()}, text)
    fields = list(native.FIELDS.finditer(text))
    best_fields = [row for row in fields if row['name'] == 'BEST_MOVE']
    best_span = span(text, best_fields[0].start('body'), best_fields[0].end('body')) if len(best_fields) == 1 else None
    best = parsed['accepted_move_uci']
    selected = packet.get('selected_uci')
    identity = {'status': 'unassessed', 'supplied_uci': selected, 'reported_uci': best,
                'span': best_span, 'scope': 'Structured BEST_MOVE identity only, not a prose claim.'}
    if selected is None:
        identity['reason'] = 'No selected move was supplied.'
    elif best is None:
        identity['reason'] = 'The reported move is illegal, malformed or ambiguous.'
    else:
        identity['status'] = 'supported' if best == selected else 'contradicted'
    out['selected_identity'] = identity
    if best:
        _, observation = _move_record(board, chess.Move.from_uci(best))
        out['move_observations'] = {'status': 'observed', **observation}
    else:
        out['move_observations'] = {'status': 'unassessed', 'reason': parsed['move_rejection']}
    analyses = [row for row in fields if row['name'] == 'ANALYSIS']
    # A conditional prefix outside FIELDS would otherwise be silently ignored.
    root_framing = (best is not None and len(best_fields) == 1 and len(analyses) == 1
                    and fields[0] is analyses[0] and not text[:analyses[0].start()].strip())
    pattern = re.compile(r'\s*The move\s+(?P<move>' + native.MOVE.pattern
                         + r')\s+(?P<check_claim>gives checkmate|gives check|does not give check)\.'
                         + r'\s+(?P<capture_claim>It captures\s+<PIECE_(?P<cap_side>[MO])(?P<cap_piece>[PNBRQK])>\.|It does not capture a piece\.)\s*')
    match = pattern.fullmatch(analyses[0]['body']) if root_framing else None
    if match is None:
        out['reason'] = 'No draft statements match the limited checker. Other text is unassessed.'
        out['unassessed_regions'] = [span(text, row.start('body'), row.end('body')) for row in analyses]
        return out
    analysis = analyses[0]
    move, error = native.parse_atom(match, board, board.turn)
    after, move_info = _move_record(board, move) if move is not None and error is None else (None, None)
    for kind, group in (('check_or_mate', 'check_claim'), ('capture', 'capture_claim')):
        row = {'kind': kind, 'span': span(text, analysis.start('body') + match.start(group),
                                         analysis.start('body') + match.end(group)),
               'exact_raw_text': match[group], 'branch_uci': [], 'turn': chess.COLOR_NAMES[board.turn],
               'analysis_move_uci': move.uci() if move else None,
               'analysis_move_san': move_info['move_san'] if move_info else None,
               'status': 'unassessed'}
        if after is None:
            row['reason'] = error or 'No legal root move was mapped.'
        else:
            if kind == 'check_or_mate':
                phrase = match[group]
                expected = True
                observed = after.is_checkmate() if phrase == 'gives checkmate' else after.is_check() if phrase == 'gives check' else not after.is_check()
            else:
                expected = None if match['cap_piece'] is None else {
                    'color': chess.COLOR_NAMES[board.turn if match['cap_side'] == 'M' else not board.turn],
                    'piece': chess.piece_name(native.PIECES[match['cap_piece']])}
                observed = move_info['victim']
            row.update(expected=expected, observed=observed,
                       status='supported' if expected == observed else 'contradicted')
        out['claims'].append(row)
    out['analysis_alignment'] = {'analysis_move_uci': move.uci() if move else None,
        'selected_uci': selected, 'status': 'unassessed' if after is None or selected is None else 'supported' if move.uci() == selected else 'contradicted',
        'scope': 'ANALYSIS move versus supplied move; independent of BEST_MOVE identity.'}
    out['status'] = 'checked'
    return out
