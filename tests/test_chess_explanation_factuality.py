import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from scripts.chess_explanation_factuality import check_moving_piece

def packet(fen, move):
    return {"position_id":"case","fen":fen,"move_uci":move,"source":{"source_id":"real-source"}}

class MovingPieceFactTests(unittest.TestCase):
    def test_accepts_true_pawn_motion(self):
        report = check_moving_piece(packet("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e4"), {"move_summary":"The move is advancing a pawn.","primary_concepts":[]})
        self.assertTrue(report["passed"])
    def test_rejects_knight_described_as_pawn_motion(self):
        report = check_moving_piece(packet("r5rk/1ppqb1pp/2bpNp2/p3nP2/P3P3/2N3B1/1PP1Q1PP/3R1RK1 b - - 4 19", "e5f7"), {"move_summary":"The move e5f7 is advancing a pawn.","primary_concepts":[]})
        self.assertFalse(report["passed"])
        self.assertEqual(report["findings"][0]["actual_piece"], "knight")
    def test_does_not_treat_an_attacked_pawn_as_mover_claim(self):
        report = check_moving_piece(packet("r5rk/1ppqb1pp/2bpNp2/p3nP2/P3P3/2N3B1/1PP1Q1PP/3R1RK1 b - - 4 19", "e5f7"), {"move_summary":"The knight attacks a pawn.","primary_concepts":[]})
        self.assertTrue(report["passed"])

if __name__ == "__main__": unittest.main()
