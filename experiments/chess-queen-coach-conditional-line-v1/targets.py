"""Legal conditional output facts only; never generator features or engine calls."""
import hashlib
import json
from pathlib import Path
import sys
import chess
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/'scripts'))
import chess_queen_adapter as native

# These three local authored helpers are AST-identical to the pinned original intake.
def piece_atom(piece,pov):return '<PIECE_'+('M' if piece.color==pov else 'O')+piece.symbol().upper()+'>'


def move_atom(board,move,pov):
    if move not in board.legal_moves or board.is_game_over(claim_draw=False):raise ValueError('target move is illegal or terminal')
    square=lambda value:f'<SQUARE_{(value if pov else value^56)+1}>'
    piece=board.piece_at(move.from_square)
    victim=chess.Piece(chess.PAWN,not board.turn) if board.is_en_passant(move) else board.piece_at(move.to_square)
    atom=piece_atom(piece,pov)+square(move.from_square)+(piece_atom(victim,pov) if victim else '')+square(move.to_square)
    return atom+(piece_atom(chess.Piece(move.promotion,piece.color),pov) if move.promotion else '')


def move_facts(board,move):
    if move not in board.legal_moves or board.is_game_over(claim_draw=False):raise ValueError('facts need legal nonterminal board')
    piece=board.piece_at(move.from_square);ep=board.is_en_passant(move)
    victim=chess.Piece(chess.PAWN,not board.turn) if ep else board.piece_at(move.to_square)
    victim_square=(move.to_square-8 if board.turn else move.to_square+8) if ep else move.to_square
    after=board.copy(stack=False);after.push(move);checker_squares=list(after.checkers());checkers=[chess.square_name(s) for s in checker_squares]
    return {'mover':chess.piece_name(piece.piece_type),'promotion':chess.piece_name(move.promotion) if move.promotion else None,
      'castling':board.is_castling(move),'capture':board.is_capture(move),
      'victim':chess.piece_name(victim.piece_type) if victim else None,
      'victim_color':('white' if victim.color else 'black') if victim else None,
      'victim_square':chess.square_name(victim_square) if victim else None,'en_passant':ep,
      'gives_check':after.is_check(),'checkmate':after.is_checkmate(),'stalemate':after.is_stalemate(),
      'checkers':checkers,'discovered_or_double_check':after.is_check() and (len(checkers)>1 or any(s!=move.to_square and board.piece_at(s)==after.piece_at(s) for s in checker_squares)),
      'fen_after':after.fen(),'automatic_game_over':after.is_game_over(claim_draw=False)}


def check_words(facts):
    return 'gives checkmate' if facts['checkmate'] else 'gives check' if facts['gives_check'] else 'does not give check'


def capture_words(facts, pov):
    if not facts['capture']: return 'captures no piece'
    victim = chess.Piece(chess.PIECE_NAMES.index(facts['victim']), facts['victim_color'] == 'white')
    square = chess.parse_square(facts['victim_square']); index = (square if pov else square^56)+1
    return f'captures {piece_atom(victim,pov)} on <SQUARE_{index}>'


def target(fen, pv):
    board = native.board_for(fen); pov = board.turn; atoms = []; facts = []
    if type(pv) is not list or not 1 <= len(pv) <= 3: raise ValueError('Stored1..3ply line required')
    for text in pv:
        move = chess.Move.from_uci(text); atoms.append(move_atom(board, move, pov))
        facts.append(move_facts(board, move)); board.push(move)
    first = facts[0]
    root_capture = ('It '+capture_words(first,pov).split(' on ')[0]+'.') if first['capture'] else 'It does not capture a piece.'
    root = f'The move {atoms[0]} {check_words(first)}. {root_capture}'
    clauses = []
    if len(atoms) >= 2:
        clauses.append(f'Conditional line: If {atoms[0]} is played, the opponent can reply {atoms[1]}; that reply {capture_words(facts[1],pov)} and {check_words(facts[1])}.')
    if len(atoms) == 3:
        clauses.append(f'If that reply is played, the mover can play {atoms[2]}; that move {capture_words(facts[2],pov)} and {check_words(facts[2])}.')
    evaluation = 'Checkmate' if first['checkmate'] else 'Draw' if first['automatic_game_over'] else 'Not assessed'
    fields = f'\nBEST_MOVE: {atoms[0]}\nCRITICAL_LINE: '+ ' '.join(atoms)+f'\nPROMISING_MOVES: {atoms[0]}\nEVALUATION: {evaluation}'
    immediate = 'ANALYSIS: '+root+fields
    enriched = 'ANALYSIS: '+root+(' '+' '.join(clauses) if clauses else '')+fields
    for packet in ({'fen':fen},{'fen':fen,'selected_uci':pv[0]}):
        parsed = native.parse_output(packet, enriched)
        if (parsed['accepted_move_uci'] != pv[0] or parsed['critical_line']['failure']
            or [step['raw_uci'] for step in parsed['critical_line']['steps']] != pv):
            raise ValueError('Native target roundtrip differs')
    return enriched, immediate, facts


def input_hash(packet): return hashlib.sha256(json.dumps(packet,sort_keys=True).encode()).hexdigest()


def transform_case(case, reference):
    if set(case) != {'case_id','group_id','mode','input','response'}: raise ValueError('Exact old TRAIN/DEV row schema required')
    if (reference['case_id'] != case['case_id'] or reference['group_id'] != case['group_id']
        or case['mode'] not in ('free','selected_a','selected_b')): raise ValueError('Case/group/mode mismatch')
    packet = case['input']; expected = {'fen'} if case['mode']=='free' else {'fen','selected_uci'}
    if type(packet) is not dict or set(packet) != expected: raise ValueError('Current-only model input required')
    pv = reference['reference_pv_uci']
    if type(pv) is not list or not 1 <= len(pv) <= 3: raise ValueError('Stored1..3ply line required')
    if case['mode'] != 'free' and packet['selected_uci'] != pv[0]: raise ValueError('Given move/PV differs')
    enriched, immediate, facts = target(packet['fen'], pv)
    if case['response'] != immediate: raise ValueError('Old target text differs from independently replayed target')
    if facts != reference['per_ply_facts'] or facts[0] != reference['facts']: raise ValueError('Stored per-ply facts incoherent')
    updated = {**case, 'response':enriched}
    if input_hash(updated['input']) != input_hash(packet): raise AssertionError('Input changed')
    return updated
