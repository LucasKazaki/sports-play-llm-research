const assert = require('node:assert/strict');
const { test } = require('node:test');
const { normalize, parseFen, scoreLabel, safeSourceUrl, reportedRegressions } = require('../prototype/chess_demo_ui/app.js');
const fen = '5rk1/1p3ppp/pq1Q1b2/8/8/1P3N2/P4PPP/3R2K1 b - - 3 27';

test('board orientation uses FEN rank eight first, with explicit side to move', () => {
  const board = parseFen(fen);
  assert.equal(board.cells.length, 64);
  assert.equal(board.cells[5], 'r'); // f8
  assert.equal(board.cells[6], 'k'); // g8
  assert.equal(board.cells[56 + 3], 'R'); // d1
  assert.equal(board.side, 'Black');
  for (const malformed of ['8/8/8 w - - 0 1', '9/8/8/8/8/8/8/8 w - - 0 1', fen.replace(' b ', ' x '), fen.replace('5rk1', '5<x1')]) assert.equal(parseFen(malformed), null);
});

test('mate, centipawns, perspective and bounds are never flattened into a winning percentage', () => {
  assert.equal(scoreLabel({ score: { type: 'mate', value: -3, bound: 'upper' } }), '≤ Mate -3');
  assert.equal(scoreLabel({ score: { type: 'cp', value: 0, bound: 'lower' } }), '≥ 0 cp');
  assert.equal(scoreLabel({ score_cp: 20 }), '+20 cp · untyped');
  assert.equal(scoreLabel({ score: { type: 'probability', value: 99 } }), 'Score type not supported');
});

test('game links allow only HTTPS Lichess sources and exclude executable or credential-bearing URLs', () => {
  assert.equal(safeSourceUrl('https://lichess.org/F8M8OS71#53'), 'https://lichess.org/F8M8OS71#53');
  for (const url of ['javascript:alert(1)', 'https://lichess.org.evil.example/game', 'https://user:secret@lichess.org/game', 'file:///C:/secret.json', 'http://lichess.org/game']) assert.equal(safeSourceUrl(url), null);
});

test('source-only boards stay separate from retained engine candidates', () => {
  const result = normalize({ schema: 'chess-dev-source-projection/v1', license: 'CC0-1.0', items: [{ position_id: 'real-1', fen, split: 'dev' }] });
  assert.equal(result.kind, 'source');
  assert.equal(result.positions[0].candidates.length, 0);
  assert.equal(result.positions[0].status, 'source_only');
  const typed = normalize({ schema: 'chess-typed-position-evidence/v1', positions: [{ position_id: 'failed', fen, status: 'failed', error: { message: 'timeout' }, engine_evidence: [] }] });
  assert.equal(typed.positions[0].error.message, 'timeout');
  assert.equal(typed.positions.length, 1);
});

test('training comparison retains missing cases, raw untrusted output, and mismatched boards', () => {
  const result = normalize({ schema: 'chess.stockfish-distillation.v1', evaluation: {
    baseline: { records: [{ id: 'one', fen, raw_output: '<img onerror=alert(1)>', legal: false }, { id: 'two', fen }] },
    trained: { records: [{ id: 'one', fen, raw_output: 'f8d8', legal: true }, { id: 'one', fen: fen.replace(' b ', ' w ') }] }
  } });
  assert.equal(result.positions.length, 3);
  assert.equal(result.positions[0].baseline.raw_output, '<img onerror=alert(1)>');
  assert.equal(result.positions[1].trained, undefined);
  assert.equal(result.positions[2].baseline, undefined);
});

test('unsupported schemas and repeated position identities fail visibly', () => {
  assert.throws(() => normalize({ schema: 'marketing', positions: [] }), /Unsupported schema/);
  assert.throws(() => normalize({ schema: 'chess-dev-source-projection/v1', items: [{ position_id: 'a', fen }, { position_id: 'a', fen }] }), /duplicate/);
  const legacy = normalize({ schema_version: 'chess-concept-demo/v1', abstain: true, reason: 'invalid_position_evidence' });
  assert.equal(legacy.positions.length, 0);
});

test('actual distillation split groups preserve development and holdout identities separately', () => {
  const record = { id: 'same-id', fen, raw_output: 'f8d8', legal: true };
  const result = normalize({ schema: 'chess.stockfish-distillation.v1', evaluation: {
    baseline: { development: { count: 1, records: [record] }, holdout: { count: 1, records: [record] } },
    trained: { development: { count: 1, records: [record] }, holdout: { count: 1, records: [record] } }
  } });
  assert.equal(result.positions.length, 2);
  assert.equal(result.positions[0].split, 'development');
  assert.equal(result.positions[1].split, 'holdout');
  assert.equal(result.positions[1].baseline.raw_output, 'f8d8');
  assert.throws(() => normalize({ schema: 'chess.stockfish-distillation.v1', evaluation: {
    baseline: { development: { records: [record, record] } }
  } }), /duplicate/);
});

test('separately versioned v2 receipts use the same inspection contract without claiming validation', () => {
  const record = { id: 'new-game', fen, raw_output: 'M: f8d8', legal: false };
  const result = normalize({ schema: 'chess.stockfish-distillation.v2', evaluation: {
    baseline: { development: { count: 1, records: [record] } },
    trained: { development: { count: 1, records: [record] } }
  } });
  assert.equal(result.schema, 'chess.stockfish-distillation.v2');
  assert.equal(result.positions.length, 1);
  assert.equal(result.positions[0].trained.legal, false);
});

test('unchanged legality does not hide lower teacher agreement on equal denominators', () => {
  assert.deepEqual(reportedRegressions({ count: 128, raw_legal_count: 127, top1_match_count: 33 },
    { count: 128, raw_legal_count: 127, top1_match_count: 27 }), ['teacher matches']);
  assert.deepEqual(reportedRegressions({ count: 128, raw_legal_count: 128, top1_match_count: 24 },
    { count: 128, raw_legal_count: 127, top1_match_count: 21 }), ['legal moves', 'teacher matches']);
  assert.deepEqual(reportedRegressions({ count: 64, raw_legal_count: 64, top1_match_count: 33 },
    { count: 128, raw_legal_count: 64, top1_match_count: 27 }), []);
});
