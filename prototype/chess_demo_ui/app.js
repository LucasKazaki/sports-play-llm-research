/* Inspection only: never executes receipt text, makes a model call, or validates chess claims. */
(function (root) {
  'use strict';
  const MAX_BYTES = 8 * 1024 * 1024;
  const PIECES = { k: ['♚', 'king'], q: ['♛', 'queen'], r: ['♜', 'rook'], b: ['♝', 'bishop'], n: ['♞', 'knight'], p: ['♟', 'pawn'] };
  const text = (value, fallback = 'Not recorded') => value === undefined || value === null || value === '' ? fallback : String(value);
  const array = value => Array.isArray(value) ? value : [];
  const moveValid = value => typeof value === 'string' && /^[a-h][1-8][a-h][1-8][qrbn]?$/.test(value);

  function parseFen(fen) {
    if (typeof fen !== 'string') return null;
    const fields = fen.trim().split(/\s+/), ranks = fields[0].split('/');
    if (fields.length !== 6 || ranks.length !== 8 || !/^[wb]$/.test(fields[1])) return null;
    const cells = [];
    for (const rank of ranks) {
      const row = [];
      for (const symbol of rank) {
        if (/^[1-8]$/.test(symbol)) row.push(...Array(Number(symbol)).fill('.'));
        else if (/^[prnbqkPRNBQK]$/.test(symbol)) row.push(symbol);
        else return null;
      }
      if (row.length !== 8) return null;
      cells.push(...row);
    }
    return { cells, side: fields[1] === 'w' ? 'White' : 'Black' };
  }

  function safeSourceUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && url.hostname === 'lichess.org' && !url.username && !url.password ? url.href : null;
    } catch (_) { return null; }
  }

  function scoreLabel(candidate) {
    const score = candidate.score;
    if (score && typeof score === 'object') {
      const prefix = score.bound === 'lower' ? '≥ ' : score.bound === 'upper' ? '≤ ' : '';
      if (score.type === 'mate' && Number.isInteger(score.value)) return `${prefix}Mate ${score.value > 0 ? '+' : ''}${score.value}`;
      if (score.type === 'cp' && Number.isInteger(score.value)) return `${prefix}${score.value > 0 ? '+' : ''}${score.value} cp`;
      return 'Score type not supported';
    }
    return Number.isInteger(candidate.score_cp) ? `${candidate.score_cp > 0 ? '+' : ''}${candidate.score_cp} cp · untyped` : 'No score recorded';
  }

  function reportedRegressions(baseline, trained) {
    if (!Number.isInteger(baseline?.count) || baseline.count < 1 || baseline.count !== trained?.count) return [];
    return [['raw_legal_count', 'legal moves'], ['top1_match_count', 'teacher matches']]
      .filter(([key]) => Number.isInteger(baseline[key]) && Number.isInteger(trained[key]) && trained[key] < baseline[key])
      .map(([, label]) => label);
  }

  function candidateFrom(value, index) {
    return { ...value, id: text(value.evidence_id || value.id, `candidate-${index + 1}`), move: moveValid(value.move_uci) ? value.move_uci : null,
      after: value.transition?.fen_after || value.facts?.fen_after || null };
  }

  function evaluationRows(value) {
    const groups = Array.isArray(value?.records) ? [['evaluation', value]] : Object.entries(value || {});
    const rows = groups.flatMap(([split, result]) => array(result?.records).map(row => ({ ...row, recordedSplit: split })));
    if (rows.length > 5000) throw new Error('This preview supports up to 5,000 positions per evaluation condition.');
    return rows;
  }

  function normalize(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Choose a supported JSON object, such as a development projection or retained result receipt.');
    const schema = data.schema || data.schema_version;
    let positions = [], kind, label;
    if (schema === 'chess-dev-source-projection/v1') {
      kind = 'source'; label = 'Real development source';
      positions = array(data.items).map(row => ({ id: row.position_id, fen: row.fen, game: row.game_id, url: row.game_url, split: row.split,
        sourceKind: row.provenance_kind, license: data.license, status: 'source_only', candidates: [] }));
    } else if (schema === 'chess-typed-position-evidence/v1') {
      kind = 'typed'; label = 'Retained engine evidence';
      positions = array(data.positions).map(row => ({ id: row.position_id, fen: row.fen, game: row.game_id, url: row.source_url,
        split: row.split, status: row.status, error: row.error, candidates: array(row.engine_evidence).map(candidateFrom) }));
    } else if (schema === 'chess.stockfish-distillation.v1' || schema === 'chess.stockfish-distillation.v2') {
      kind = 'distillation'; label = 'Local training receipt';
      const baseline = evaluationRows(data.evaluation?.baseline), trained = evaluationRows(data.evaluation?.trained);
      const identity = row => `${row.recordedSplit}\n${row.id}\n${row.fen}`;
      const indexed = rows => {
        const map = new Map();
        rows.forEach(row => { const key = identity(row); if (map.has(key)) throw new Error('The receipt contains duplicate position identities within an evaluation condition.'); map.set(key, row); });
        return map;
      };
      const baselineMap = indexed(baseline), trainedMap = indexed(trained);
      const keys = new Set([...baselineMap.keys(), ...trainedMap.keys()]);
      positions = [...keys].map(key => {
        const before = baselineMap.get(key), after = trainedMap.get(key), row = after || before;
        return { id: row.id, fen: row.fen, split: row.recordedSplit, status: 'reported', baseline: before, trained: after,
          sourceKind: 'Imported training receipt', candidates: [], teacherMove: row.teacher_move_uci };
      });
    } else if (schema === 'chess-concept-demo/v1') {
      kind = 'legacy'; label = 'Fixed preview packet';
      if (array(data.board_before).length === 8) positions = [{ id: data.source?.source_id || 'fixed-preview', rows: data.board_before,
        move: data.move_uci, sourceKind: data.source?.source_id, license: data.source?.license, status: data.reason,
        candidates: array(data.engine_candidates).map(candidateFrom), replayHash: data.legal_replay_hash }];
    } else {
      throw new Error(`Unsupported schema: ${text(schema)}. Open a chess development projection, typed evidence packet, distillation receipt, or fixed preview result.`);
    }
    if (positions.length > 5000) throw new Error('This preview supports up to 5,000 positions. Open a bounded evaluation receipt.');
    const ids = new Set();
    positions.forEach((row, index) => {
      row.id = text(row.id, `Position ${index + 1}`);
      const key = `${row.split}\n${row.id}\n${row.fen || ''}`;
      if (ids.has(key)) throw new Error('The receipt contains duplicate position identities. Resolve the duplicate before inspection.');
      ids.add(key);
      if (row.fen && !parseFen(row.fen)) row.boardError = 'The retained FEN has an unsupported board layout. Inspect the raw record.';
      row.candidates = row.candidates || [];
    });
    return { data, schema, kind, label, positions, limitations: [...array(data.limitations), ...array(data.boundaries), ...array(data.source_boundaries)] };
  }

  const api = { parseFen, safeSourceUrl, scoreLabel, reportedRegressions, normalize, moveValid, MAX_BYTES };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (!root.document) return;
  const $ = id => document.getElementById(id);
  const state = { bundle: null, index: 0, candidate: 0, flipped: false, after: false, loading: false };
  function el(tag, className, value) { const node = document.createElement(tag); if (className) node.className = className; if (value !== undefined) node.textContent = value; return node; }
  function error(message) { $('error').textContent = message; $('error').hidden = !message; }
  function fact(list, name, value) { list.append(el('dt', '', name), el('dd', '', text(value))); }
  function block(title, description) { const node = el('section', 'evidence-block'); node.append(el('h3', '', title)); if (description) node.append(el('p', '', description)); return node; }
  function empty(title, description) { const node = el('div', 'evidence-empty'); node.append(el('strong', '', title), el('p', '', description)); return node; }
  function announce(title, description) { $('noticeTitle').textContent = title; $('noticeText').textContent = description; }
  function setBusy(busy) { state.loading = busy; $('loadDevelopment').disabled = busy; $('fileInput').disabled = busy; $('workspace').setAttribute('aria-busy', String(busy)); }
  function load(data, filename, imported = false) {
    const bundle = normalize(data);
    state.bundle = bundle; state.index = 0; state.candidate = 0; state.after = false;
    $('payload').textContent = JSON.stringify(data, null, 2); $('rawSection').hidden = false;
    $('workspace').hidden = bundle.positions.length === 0;
    $('positionCount').textContent = bundle.positions.length;
    $('datasetLabel').textContent = filename;
    const notes = [...bundle.limitations,
      'This screen displays retained records. It does not verify hashes, replay move legality, or run an engine or model.',
      'A move match or legal output does not establish explanation quality, chess strength, or sports competence.'];
    $('limitations').replaceChildren(...[...new Set(notes)].map(note => el('li', '', text(note))));
    $('limitationsSection').hidden = false;
    if (imported) announce('Imported JSON · claims remain unverified', 'The file stays in this browser. Scores, legality, training, and source claims are reported by the file.');
    else if (bundle.kind === 'source') announce(`${bundle.positions.length} historical development positions · source only`, 'Solutions, themes, and test items are omitted. No new model or engine result is shown.');
    else announce('Fixed packet · no generator call', data.reason === 'local_generator_not_configured' ? 'The retained result is an abstention. Engine candidates do not supply a learned explanation.' : `Evidence unavailable: ${text(data.reason)}. Open the development set to inspect source boards.`);
    renderPositionList();
    if (bundle.positions.length) render();
    error('');
  }

  function renderPositionList() {
    const options = [], buttons = [];
    state.bundle.positions.forEach((row, index) => {
      const option = el('option', '', row.id); option.value = index; options.push(option);
      const button = el('button'); button.type = 'button'; button.dataset.index = index;
      button.append(el('strong', '', row.id.replace('lichess-puzzle-', 'Puzzle ')), el('span', '', text(row.split, state.bundle.label)));
      button.addEventListener('click', () => selectPosition(index)); buttons.push(button);
    });
    $('positionSelect').replaceChildren(...options); $('positionButtons').replaceChildren(...buttons);
  }
  function selectPosition(index) { state.index = index; state.candidate = 0; state.after = false; render(); }
  function currentCandidate(row) { return row.candidates[state.candidate] || {}; }
  function renderBoard(row) {
    const candidate = currentCandidate(row), retainedAfter = candidate.after;
    if (state.after && !parseFen(retainedAfter)) state.after = false;
    const fen = state.after ? retainedAfter : row.fen;
    let parsed = parseFen(fen), cells = parsed?.cells;
    if (!cells && row.rows) {
      const raw = row.rows.flatMap(rank => typeof rank === 'string' ? rank.trim().split(/\s+/) : []);
      if (raw.length === 64 && raw.every(piece => piece === '.' || /^[prnbqkPRNBQK]$/.test(piece))) cells = raw;
    }
    const board = $('board'); board.replaceChildren();
    if (!cells) { board.append(el('p', 'evidence-empty', row.boardError || 'No supported board was retained.')); board.setAttribute('aria-label', 'Board unavailable'); }
    else {
      const move = candidate.move || row.move || (row.trained?.legal === true && moveValid(row.trained.move_uci) ? row.trained.move_uci : null);
      const squares = Array.from({ length: 64 }, (_, index) => index);
      if (state.flipped) squares.reverse();
      const descriptions = [];
      squares.forEach((index, displayIndex) => {
        const rank = 8 - Math.floor(index / 8), file = 'abcdefgh'[index % 8], squareName = `${file}${rank}`, value = cells[index];
        const square = el('span', `square${(Math.floor(index / 8) + index % 8) % 2 ? ' dark' : ''}${move && [move.slice(0, 2), move.slice(2, 4)].includes(squareName) ? ' highlight' : ''}`);
        square.setAttribute('aria-hidden', 'true');
        if (value !== '.') {
          const white = value === value.toUpperCase(), piece = PIECES[value.toLowerCase()];
          square.append(el('span', `piece${white ? ' white' : ''}`, piece[0]));
          descriptions.push(`${white ? 'White' : 'Black'} ${piece[1]} ${squareName}`);
        }
        if (displayIndex % 8 === 0) square.append(el('span', 'coordinate rank-coordinate', rank));
        if (Math.floor(displayIndex / 8) === 7) square.append(el('span', 'coordinate', file));
        board.append(square);
      });
      board.setAttribute('aria-label', `${state.after ? 'Retained after-board' : 'Pre-move board'}, ${state.flipped ? 'Black' : 'White'} at bottom. ${descriptions.join('; ')}.`);
    }
    $('sideToMove').textContent = parsed ? `${parsed.side} to move` : 'Side to move not retained';
    $('boardState').textContent = state.after ? 'Retained after-board' : 'Before the selected move';
    $('showAfter').disabled = !parseFen(retainedAfter); $('showAfter').setAttribute('aria-pressed', String(state.after)); $('showBefore').setAttribute('aria-pressed', String(!state.after));
    $('fenValue').textContent = text(fen, 'This legacy preview retained board rows only.'); $('copyFen').disabled = !fen;
    $('copyStatus').textContent = '';
    const move = candidate.move || row.move;
    $('moveSummary').textContent = move ? `${text(candidate.transition?.san, move)} · ${move.slice(0, 2)} → ${move.slice(2, 4)}. Highlighted squares identify the retained move.` : 'No selected move is recorded for this source board.';
    if (state.bundle.kind === 'distillation') $('moveSummary').textContent = 'The board is the recorded evaluation input. Raw model outputs are shown alongside it.';
  }

  function renderCandidateEvidence(row, body) {
    if (!row.candidates.length) { body.append(empty('No engine comparison loaded', row.status === 'failed' ? `Recorded failure: ${text(row.error?.message || row.error)}` : 'Open a typed evidence packet to compare retained candidates. The source position alone does not provide a recommended move.')); return; }
    const section = block('Retained move candidates', 'Select a candidate to highlight its move. Score perspective and qualification are kept visible.');
    const list = el('div', 'candidate-list');
    row.candidates.forEach((candidate, index) => {
      const button = el('button', 'candidate'); button.type = 'button'; button.setAttribute('aria-pressed', String(state.candidate === index));
      const line = el('span', 'candidate-line'); line.append(el('span', 'candidate-move', candidate.transition?.san || candidate.move || 'Unsupported move'), el('span', 'candidate-score', scoreLabel(candidate)));
      const score = candidate.score;
      const perspective = score ? `${text(score.perspective)}${score.side_to_move ? ` · ${score.side_to_move}` : ''} · ${text(score.bound, 'bound not retained')}` : 'Score perspective and bound were not retained';
      button.append(line, el('span', 'candidate-meta', perspective));
      button.addEventListener('click', () => { state.candidate = index; state.after = false; render(); $('evidenceBody').querySelectorAll('.candidate')[index]?.focus({ preventScroll: true }); }); list.append(button);
    });
    section.append(list);
    const candidate = currentCandidate(row), details = el('dl', 'facts');
    fact(details, 'Evidence ID', candidate.id); if (candidate.depth !== undefined) fact(details, 'Depth', candidate.depth);
    if (candidate.nodes_observed !== undefined) fact(details, 'Observed nodes', candidate.nodes_observed);
    section.append(details);
    if (candidate.transition) {
      const transition = block('Recorded board facts', 'These fields come from the receipt. This browser does not independently replay them.');
      const facts = el('dl', 'facts');
      ['moving_piece', 'capture', 'captured_piece', 'gives_check', 'checkmate', 'promotion'].forEach(key => { if (candidate.transition[key] !== undefined) fact(facts, key.replaceAll('_', ' '), candidate.transition[key]); });
      transition.append(facts); section.append(transition);
    }
    body.append(section);
    body.append(empty('No learned explanation in this packet', 'Engine observations and deterministic board facts are evidence. Strategic rationale and teaching quality need separate evaluation.'));
  }

  function outputCard(name, result) {
    const card = el('section', 'output-card'); card.append(el('h3', '', name));
    if (!result) { card.append(el('p', 'muted', 'No record retained. This case remains missing.')); return card; }
    const facts = el('dl', 'facts');
    fact(facts, 'Reported move', result.move_uci); fact(facts, 'Reported legal', result.legal === true ? 'Yes' : result.legal === false ? 'No' : 'Not recorded');
    fact(facts, 'Teacher match', result.match === true ? 'Yes' : result.match === false ? 'No' : 'Not recorded');
    card.append(facts, el('pre', '', text(result.raw_output, 'No raw output retained.'))); return card;
  }
  function renderTraining(row, body) {
    const data = state.bundle.data, summary = block('Reported training run', 'Imported experiment record; values below have not been independently checked by this viewer.');
    const condition = name => { const value = data.evaluation?.[name]; return value?.records ? value : value?.[row.split]; };
    const baseline = condition('baseline'), trained = condition('trained');
    const regressions = reportedRegressions(baseline, trained);
    if (regressions.length) {
      body.append(empty('Reported regression · checkpoint remains experimental', `This split reports fewer ${regressions.join(' and fewer ')} after training. A lower training loss did not establish a stronger chess model.`));
    }
    const facts = el('dl', 'facts');
    fact(facts, 'Model', data.model?.source); fact(facts, 'Device', data.runtime?.device || data.training?.device); fact(facts, 'Examples seen', data.training?.examples_seen ?? data.training?.examples); fact(facts, 'Training steps', data.training?.steps);
    fact(facts, 'Evaluation split', row.split);
    fact(facts, 'Teacher move', row.teacherMove); summary.append(facts); body.append(summary);
    const evaluation = block('Evaluation counts', 'Counts include all requested cases. Teacher agreement is distinct from move legality and chess strength.');
    const counts = el('dl', 'facts');
    for (const [key, title] of [['baseline', 'Before training'], ['trained', 'After training']]) {
      const result = condition(key);
      fact(counts, title, result ? `${text(result.top1_match_count, '?')}/${text(result.count, '?')} teacher matches · ${text(result.raw_legal_count, '?')}/${text(result.count, '?')} reported legal` : 'Not recorded');
    }
    evaluation.append(counts); body.append(evaluation, outputCard('Before training · raw output', row.baseline), outputCard('After training · raw output', row.trained));
  }

  function render() {
    const bundle = state.bundle, row = bundle.positions[state.index];
    $('positionTitle').textContent = row.id; $('positionContext').textContent = text(row.split, bundle.label);
    $('positionSelect').value = state.index;
    [...$('positionButtons').children].forEach((button, index) => { button.setAttribute('aria-current', String(index === state.index)); button.tabIndex = index === state.index ? 0 : -1; });
    $('evidenceKind').textContent = bundle.kind === 'distillation' ? 'Receipt-reported' : bundle.kind === 'source' ? 'Source only' : 'Retained evidence';
    renderBoard(row);
    const body = $('evidenceBody'); body.replaceChildren();
    if (bundle.kind === 'distillation') renderTraining(row, body); else renderCandidateEvidence(row, body);
    const source = $('sourceFacts'); source.replaceChildren(); fact(source, 'Position', row.id); if (row.game) fact(source, 'Game', row.game);
    fact(source, 'Split', row.split); if (row.license) fact(source, 'License', row.license); if (row.sourceKind) fact(source, 'Source kind', row.sourceKind);
    if (row.replayHash) fact(source, 'Replay hash', row.replayHash);
    if (bundle.kind === 'distillation') fact(source, 'Checkpoint hash', bundle.data.model?.checkpoint_sha256);
    const url = safeSourceUrl(row.url); $('gameLink').hidden = !url;
    if (url) $('gameLink').href = url; else $('gameLink').removeAttribute('href');
  }

  $('loadDevelopment').addEventListener('click', async () => {
    if (state.loading) return;
    setBusy(true); error('');
    try { const response = await fetch('/api/development', { cache: 'no-store' }); if (!response.ok) throw new Error('Development source is unavailable in this checkout. Open its JSON file instead.'); load(await response.json(), 'Lichess · historical development projection'); }
    catch (failure) { error(failure.message); } finally { setBusy(false); }
  });
  $('fileInput').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try { if (file.size > MAX_BYTES) throw new Error('Choose a JSON file smaller than 8 MB.'); load(JSON.parse(await file.text()), file.name, true); }
    catch (failure) { error(failure instanceof SyntaxError ? 'The file is not valid JSON. Choose an intact result receipt.' : failure.message); }
    finally { event.target.value = ''; }
  });
  $('positionSelect').addEventListener('change', event => selectPosition(Number(event.target.value)));
  $('positionButtons').addEventListener('keydown', event => {
    if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); const last = state.bundle.positions.length - 1;
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? last : Math.max(0, Math.min(last, state.index + (event.key === 'ArrowDown' ? 1 : -1)));
    selectPosition(index); $('positionButtons').children[index].focus();
  });
  $('flipBoard').addEventListener('click', () => { state.flipped = !state.flipped; $('flipBoard').setAttribute('aria-pressed', String(state.flipped)); renderBoard(state.bundle.positions[state.index]); });
  $('showBefore').addEventListener('click', () => { state.after = false; renderBoard(state.bundle.positions[state.index]); });
  $('showAfter').addEventListener('click', () => { state.after = true; renderBoard(state.bundle.positions[state.index]); });
  $('copyFen').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('fenValue').textContent); $('copyStatus').textContent = 'Copied.'; }
    catch (_) { $('copyStatus').textContent = 'Select and copy the FEN text above.'; }
  });
  setBusy(true);
  fetch('/api/review', { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error('The fixed preview is unavailable. Open a result JSON to continue.'); load(await response.json(), 'Server-selected fixed packet'); })
    .catch(failure => { announce('Preview not loaded', 'Open a local result JSON to inspect retained evidence.'); error(failure.message); }).finally(() => setBusy(false));
})(typeof globalThis !== 'undefined' ? globalThis : this);
