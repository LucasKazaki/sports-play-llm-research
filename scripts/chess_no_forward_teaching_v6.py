"""Evaluator-only queen-defense contrast for the unchanged v5 proposal.

The model receives v5's exact pre-move projection and returns v5's exact
proposal or abstention shape. This module inspects replies and later moves
only after generation. A contrast is one legal conditional illustration, not
an explanation of an engine score, a move ranking, or a teaching-quality vote.
"""
from __future__ import annotations

from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v4 as witness_v4
import chess_no_forward_teaching_v5 as proposal_v5
import chess_tactical_hypothesis_v2 as tactical


RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v6'
FOCUS_SCHEMA = 'chess-no-forward-teaching-focus/v1'
MAX_COMMON_REPLIES = witness_v4.MAX_COMMON_REPLIES
MAX_OPTIONS_EXAMINED = witness_v4.MAX_OPTIONS_EXAMINED

# Do not create a v6 generator: the existing v5 wire contract is deliberate.
INPUT_SCHEMA = proposal_v5.INPUT_SCHEMA
CLAIM_SCHEMA = proposal_v5.CLAIM_SCHEMA
CLAIM_KIND = proposal_v5.CLAIM_KIND
build_generator_input = proposal_v5.build_generator_input
generator_messages = proposal_v5.generator_messages


def _capture_with_check(board: chess.Board, move: chess.Move,
                        queen_origin: chess.Square) -> dict | None:
    """Describe a legal queen capture that checks the opposing king."""
    if move.from_square != queen_origin or move not in board.legal_moves:
        return None
    queen = board.piece_at(queen_origin)
    captured = board.piece_at(move.to_square)
    if (queen != chess.Piece(chess.QUEEN, board.turn) or
            captured is None or captured.color == board.turn or
            not board.is_capture(move)):
        return None
    san = board.san(move)
    after = board.copy(stack=False)
    after.push(move)
    if not after.is_check() or after.piece_at(move.to_square) != queen:
        return None
    defenders = []
    for square in sorted(after.attackers(queen.color, move.to_square)):
        if square == move.to_square:
            continue
        piece = after.piece_at(square)
        if piece is None or piece.color != queen.color:
            continue
        defenders.append({'square': chess.square_name(square),
                          'piece': chess.piece_name(piece.piece_type)})
    replies = sorted(after.legal_moves, key=lambda candidate: candidate.uci())
    king_square = after.king(after.turn)
    king_capture = None
    if king_square is not None:
        if (abs(chess.square_file(king_square) - chess.square_file(move.to_square)) <= 1 and
                abs(chess.square_rank(king_square) - chess.square_rank(move.to_square)) <= 1):
            king_capture = chess.Move(king_square, move.to_square)
    return {
        'uci': move.uci(), 'san': san,
        'destination': chess.square_name(move.to_square),
        'captured_piece': chess.piece_name(captured.piece_type),
        'defenders': defenders,
        'legal_opponent_replies': [
            {'uci': reply.uci(), 'san': after.san(reply)} for reply in replies],
        'king_capture_uci': king_capture.uci() if king_capture else None,
        'king_capture_legal': king_capture in after.legal_moves if king_capture else False,
    }


def _checked_focus(focus_reply: dict | None, packet_sha256: str) -> dict | None:
    """Bind a caller-supplied evaluator-only reply to this source packet.

    A packet binding does not prove when the caller chose the reply. A future
    capture must retain that separate timing evidence before a model call.
    """
    if focus_reply is None:
        return None
    tactical._exact(focus_reply,
                    ('schema', 'source_packet_sha256', 'reply_uci',
                     'reply_san'),
                    'invalid_focus_shape')
    if (focus_reply['schema'] != FOCUS_SCHEMA or
            focus_reply['source_packet_sha256'] != packet_sha256 or
            type(focus_reply['reply_uci']) is not str or
            type(focus_reply['reply_san']) is not str or
            not focus_reply['reply_san']):
        raise tactical.ClaimRejected('invalid_focus_binding')
    try:
        chess.Move.from_uci(focus_reply['reply_uci'])
    except ValueError as error:
        raise tactical.ClaimRejected('invalid_focus_reply_uci') from error
    return dict(focus_reply)


def _sole_bishop_causes_king_capture_to_fail(board: chess.Board,
                                             capture: chess.Move,
                                             detail: dict) -> str | None:
    """Test the one defender on a copy; never alter the observed position."""
    if (len(detail['defenders']) != 1 or
            detail['defenders'][0]['piece'] != 'bishop' or
            detail['king_capture_uci'] is None or detail['king_capture_legal']):
        return None
    after = board.copy(stack=False)
    after.push(capture)
    defender_square = chess.parse_square(detail['defenders'][0]['square'])
    if after.piece_at(defender_square) != chess.Piece(chess.BISHOP, not after.turn):
        return None
    counterfactual = after.copy(stack=False)
    counterfactual.remove_piece_at(defender_square)
    if not counterfactual.is_valid():
        return None
    king_capture = chess.Move.from_uci(detail['king_capture_uci'])
    if king_capture not in counterfactual.legal_moves:
        return None
    return counterfactual.san(king_capture)


def _checked_pair(selected_board: chess.Board, alternative_board: chess.Board,
                  selected_option: chess.Move, alternative_option: chess.Move,
                  reply_uci: str, reply_san: str, *,
                  selected_detail: dict | None = None,
                  alternative_detail: dict | None = None) -> dict | None:
    """Require matching captures, immediate king-recapture contrast and cause."""
    selected = selected_detail or _capture_with_check(
        selected_board, selected_option, selected_option.from_square)
    alternative = alternative_detail or _capture_with_check(
        alternative_board, alternative_option, alternative_option.from_square)
    if (selected is None or alternative is None or
            selected['captured_piece'] != alternative['captured_piece'] or
            selected['defenders'] or
            not selected['king_capture_legal']):
        return None
    counterfactual_san = _sole_bishop_causes_king_capture_to_fail(
        alternative_board, alternative_option, alternative)
    if counterfactual_san is None:
        return None
    return {
        'reply_uci': reply_uci, 'reply_san': reply_san,
        'selected_capture': selected,
        'alternative_capture': alternative,
        'bishop_removal_makes_king_capture_legal': True,
        'bishop_removal_king_capture_san': counterfactual_san,
    }


def _common_reply_boards(board: chess.Board, selected: chess.Move,
                         alternative: chess.Move, *,
                         focus_reply: dict | None = None) -> tuple[list[tuple], dict]:
    """Use v4's same-UCI and identical-SAN boundary before later replay."""
    selected_after = board.copy(stack=False)
    alternative_after = board.copy(stack=False)
    selected_after.push(selected)
    alternative_after.push(alternative)
    selected_replies = {move.uci(): move for move in selected_after.legal_moves}
    alternative_replies = {move.uci(): move for move in alternative_after.legal_moves}
    common = sorted(set(selected_replies) & set(alternative_replies))
    if len(common) > MAX_COMMON_REPLIES:
        raise tactical.ClaimRejected('reply_search_budget_exceeded')
    counts = {'common_reply_uci_count': len(common), 'same_san_reply_count': 0,
              'comparable_moved_piece_reply_count': 0,
              'capture_with_check_options_examined': 0,
              'qualified_defense_pair_count': 0,
              'focus_reply_match_count': 0}
    positions = []
    for reply_uci in common:
        selected_reply = selected_replies[reply_uci]
        alternative_reply = alternative_replies[reply_uci]
        selected_san = selected_after.san(selected_reply)
        alternative_san = alternative_after.san(alternative_reply)
        if selected_san != alternative_san:
            continue
        counts['same_san_reply_count'] += 1
        if focus_reply is not None:
            if (reply_uci != focus_reply['reply_uci'] or
                    selected_san != focus_reply['reply_san']):
                continue
            counts['focus_reply_match_count'] += 1
        selected_board = selected_after.copy(stack=False)
        alternative_board = alternative_after.copy(stack=False)
        selected_board.push(selected_reply)
        alternative_board.push(alternative_reply)
        selected_piece = selected_board.piece_at(selected.to_square)
        alternative_piece = alternative_board.piece_at(alternative.to_square)
        if (selected_piece != chess.Piece(chess.QUEEN, board.turn) or
                alternative_piece != selected_piece):
            continue
        counts['comparable_moved_piece_reply_count'] += 1
        positions.append((reply_uci, selected_san,
                          selected_board, alternative_board))
    return positions, counts


def _defense_contrasts(board: chess.Board, selected: chess.Move,
                       alternative: chess.Move, *,
                       focus_reply: dict | None = None) -> tuple[list[dict], dict]:
    positions, counts = _common_reply_boards(
        board, selected, alternative, focus_reply=focus_reply)
    qualified = []
    for reply_uci, reply_san, selected_board, alternative_board in positions:
        selected_options = sorted((move for move in selected_board.legal_moves
                                   if move.from_square == selected.to_square),
                                  key=lambda move: move.uci())
        alternative_options = sorted((move for move in alternative_board.legal_moves
                                      if move.from_square == alternative.to_square),
                                     key=lambda move: move.uci())
        counts['capture_with_check_options_examined'] += (
            len(selected_options) + len(alternative_options))
        if counts['capture_with_check_options_examined'] > MAX_OPTIONS_EXAMINED:
            raise tactical.ClaimRejected('option_search_budget_exceeded')
        selected_checks = [
            (option, detail) for option in selected_options
            if (detail := _capture_with_check(selected_board, option,
                                              selected.to_square)) is not None]
        alternative_checks = [
            (option, detail) for option in alternative_options
            if (detail := _capture_with_check(alternative_board, option,
                                              alternative.to_square)) is not None]
        for selected_option, selected_detail in selected_checks:
            for alternative_option, alternative_detail in alternative_checks:
                pair = _checked_pair(selected_board, alternative_board,
                                     selected_option, alternative_option,
                                     reply_uci, reply_san,
                                     selected_detail=selected_detail,
                                     alternative_detail=alternative_detail)
                if pair is not None:
                    qualified.append(pair)
    counts['qualified_defense_pair_count'] = len(qualified)
    return qualified, counts


def _teaching_text(board: chess.Board, selected: chess.Move,
                   alternative: chess.Move, contrast: dict) -> str:
    opponent = 'Black' if board.turn == chess.WHITE else 'White'
    selected_san, alternative_san = board.san(selected), board.san(alternative)
    selected_capture = contrast['selected_capture']
    alternative_capture = contrast['alternative_capture']
    bishop_square = alternative_capture['defenders'][0]['square']
    selected_reply = selected_capture['king_capture_uci']
    alternative_reply = contrast['bishop_removal_king_capture_san']
    selected_king_san = next(
        item['san'] for item in selected_capture['legal_opponent_replies']
        if item['uci'] == selected_reply)
    text = (
        f'If {opponent} replies {contrast["reply_san"]}, {alternative_san} '
        f'leaves {alternative_capture["san"]} available. The bishop on '
        f'{bishop_square} protects {alternative_capture["destination"]}; '
        f'without that bishop, {alternative_reply} would become a legal king '
        f'capture, but it is illegal in this position. After {selected_san} '
        f'and the same reply, {selected_capture["san"]} has no defender on '
        f'{selected_capture["destination"]}, and {selected_king_san} legally '
        'takes the queen.'
    )
    if len(alternative_capture['legal_opponent_replies']) == 1:
        text += (f' After {alternative_capture["san"]}, {opponent}\'s only '
                 f'legal reply is '
                 f'{alternative_capture["legal_opponent_replies"][0]["san"]}.')
    if len(selected_capture['legal_opponent_replies']) == 1:
        text += (f' After {selected_capture["san"]}, {opponent}\'s only '
                 f'legal reply is {selected_king_san}.')
    return (text + ' This compares two choices after one reply; other replies, '
            'move quality, and the engine\'s reasoning remain unchecked.')


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict,
             focus_reply: dict | None = None) -> dict:
    """Prefer one proved defense contrast; suppress out-of-scope fallback."""
    # Check the scope before parsing the model response. This checks packet
    # identity and board facts, not when the caller selected the focus reply.
    focus = _checked_focus(focus_reply, packet_sha256)
    prior = proposal_v5.evaluate(packet_bytes, packet_sha256, raw_response,
                                 source_binding=source_binding)
    result = {**prior,
              'schema': RESULT_SCHEMA,
              'evaluator_sha256': cf.file_digest(Path(__file__)),
              'v5_evaluator_sha256': cf.file_digest(Path(proposal_v5.__file__)),
              'v4_witness_dependency_sha256': cf.file_digest(Path(witness_v4.__file__)),
              'v5_evaluation_sha256': cf.digest(cf.canonical(prior)),
              'v5_decision': prior['decision'],
              'generic_witness': prior['witness'] if focus is None else None,
              'caller_supplied_focus_reply': focus,
              'focus_reply_sha256': cf.digest(cf.canonical(focus)) if focus else None,
              'defense_comparison_scope': ('one_caller_supplied_shared_reply' if focus else
                                           'all_shared_replies'),
              'defense_contrast': None,
              'defense_search_counts': None,
              'defense_contrast_status': 'not_evaluated'}
    if prior['decision'] not in ('verified_conditional_option',
                                 'evaluator_abstention'):
        return result
    if focus is not None:
        # v5 searches all replies. Its chosen witness may concern a different
        # reply, so never publish it as the focused evaluation's lesson.
        result.update(decision='evaluator_abstention',
                      reason='no_verified_focused_contrast',
                      witness=None, witness_search_counts=None,
                      teaching_text=None)
    _, board, selected = proposal_v5._verified(packet_bytes, packet_sha256,
                                                source_binding)
    alternative = chess.Move.from_uci(prior['model_alternative_uci'])
    try:
        contrasts, counts = _defense_contrasts(
            board, selected, alternative, focus_reply=focus)
    except tactical.ClaimRejected as error:
        result['defense_contrast_status'] = str(error)
        if focus is not None:
            result['reason'] = str(error)
        return result
    result['defense_search_counts'] = counts
    if focus and counts['focus_reply_match_count'] != 1:
        result['defense_contrast_status'] = 'focused_reply_not_comparable'
        result['reason'] = 'focused_reply_not_comparable'
        return result
    if len(contrasts) != 1:
        result['defense_contrast_status'] = (
            'ambiguous' if contrasts else 'no_qualified_pair')
        if focus is not None:
            result['reason'] = result['defense_contrast_status']
        return result
    contrast = contrasts[0]
    result.update(decision='verified_queen_defense_contrast', reason=None,
                  witness=contrast, defense_contrast=contrast,
                  defense_contrast_status='verified_unique_pair',
                  teaching_text=_teaching_text(board, selected, alternative,
                                               contrast))
    return result
