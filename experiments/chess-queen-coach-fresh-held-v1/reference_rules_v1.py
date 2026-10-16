"""Exact rule reconstruction of the frozen counterfactual reference schema.

Python chess only. No engine/model, source acquisition or corpus reads. FEN
history semantics match the existing FEN-only teacher; no repetition is inferred.
"""
import chess


def board(fen):
    value=chess.Board(fen)
    if value.chess960 or not value.is_valid() or value.is_game_over(claim_draw=False):
        raise ValueError('A valid nonterminal orthodox root is required')
    return value


def key(fen):return ' '.join(chess.Board(fen).fen().split()[:4])


def validate_root(root):
    before=board(root['source_before_fen']);setup=chess.Move.from_uci(root['setup_uci'])
    if setup not in before.legal_moves:raise ValueError('Root setup is illegal')
    before.push(setup);current=board(root['fen'])
    if before.fen()!=current.fen():raise ValueError('Root current FEN differs from setup')
    paths=[key(root['source_before_fen']),key(root['fen'])]
    for selected in root['pair']:
        move=chess.Move.from_uci(selected['uci'])
        if move not in current.legal_moves:raise ValueError('Root selected move is illegal')
        after=current.copy(stack=False);after.push(move);successor=key(after.fen())
        if selected['successor_key']!=successor:raise ValueError('Selected successor role differs')
        paths.append(successor)
    if root['path_keys']!=paths or len(set(paths))!=4:raise ValueError('Four root roles differ from legal replay')


def fact(current,move):
    if current.is_game_over(claim_draw=False) or move not in current.legal_moves:
        raise ValueError('Reference cannot continue after an illegal or terminal prefix')
    piece=current.piece_at(move.from_square);ep=current.is_en_passant(move)
    victim=chess.Piece(chess.PAWN,not current.turn) if ep else current.piece_at(move.to_square)
    victim_square=(move.to_square-8 if current.turn else move.to_square+8) if ep else move.to_square
    after=current.copy(stack=False);after.push(move)
    squares=list(after.checkers());checkers=[chess.square_name(square) for square in squares]
    return {'mover':chess.piece_name(piece.piece_type),
        'promotion':chess.piece_name(move.promotion) if move.promotion else None,
        'castling':current.is_castling(move),'capture':current.is_capture(move),
        'victim':chess.piece_name(victim.piece_type) if victim else None,
        'victim_color':('white' if victim.color else 'black') if victim else None,
        'victim_square':chess.square_name(victim_square) if victim else None,'en_passant':ep,
        'gives_check':after.is_check(),'checkmate':after.is_checkmate(),'stalemate':after.is_stalemate(),
        'checkers':checkers,'discovered_or_double_check':after.is_check() and (
            len(squares)>1 or any(square!=move.to_square and current.piece_at(square)==after.piece_at(square) for square in squares)),
        'fen_after':after.fen(),'automatic_game_over':after.is_game_over(claim_draw=False)}


def expected_reference(root,task):
    current=board(root['fen']);facts=[];paths=[]
    for text in task['reference_pv']:
        move=chess.Move.from_uci(text);facts.append(fact(current,move));current.push(move);paths.append(key(current.fen()))
    if paths!=task['teacher_path_keys']:raise ValueError('Stored teacher successor paths differ from replay')
    if task['mode']!='free' and task['reference_pv'][0]!=task['selected_uci']:
        raise ValueError('Original selected task differs from teacher PV0')
    return {'case_id':task['case_id'],'group_id':root['game_id'],
        'selected_uci':task['reference_pv'][0],'reference_pv_uci':list(task['reference_pv']),
        'facts':facts[0],'per_ply_facts':facts,
        'check_role':facts[0]['gives_check'] if task['mode']!='free' else None,
        'source_ordinal':root['source_ordinal']}
