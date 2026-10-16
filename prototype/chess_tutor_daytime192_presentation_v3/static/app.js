"use strict";
const $ = id => document.getElementById(id);
const opening = '1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 *';
const mateFen = '6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1';
const glyphs = {K:'♚',Q:'♛',R:'♜',B:'♝',N:'♞',P:'♟',k:'♚',q:'♛',r:'♜',b:'♝',n:'♞',p:'♟'};
const names = {k:'king',q:'queen',r:'rook',b:'bishop',n:'knight',p:'pawn'};
let result = null, timeline = [], index = 0, flipped = false, selection = null, candidate = 0, preview = null, busy = false, pendingPromotion = null, requestNumber = 0;
let classifierConfigured = false;

function el(tag, text, className) { const node=document.createElement(tag); if(text!==undefined) node.textContent=text; if(className) node.className=className; return node; }
function notice(text, error=false) { $('notice').textContent=text; $('notice').classList.toggle('error',error); }
function fenPieces(fen) { const rows=fen.split(' ')[0].split('/'), pieces={}; rows.forEach((row,i)=>{let file=0; for(const c of row){ if(/[1-8]/.test(c)) file+=Number(c); else pieces[`${String.fromCharCode(97+file++)}${8-i}`]=c; }}); return pieces; }
function syncClassifierControl() {
  if(!classifierConfigured) $('use-model').checked=false;
  $('use-model').disabled=busy||!classifierConfigured;
}
function applyClassifierHealth(health) {
  classifierConfigured=health?.model_configured===true;
  $('use-model').checked=classifierConfigured;syncClassifierControl();
}
function classifierRequested() {return classifierConfigured&&$('use-model').checked;}
function setBusy(value) {
  busy=value; $('load').disabled=value; $('load').textContent=value?'Analyzing…':'Load position';
  for(const id of ['previous','next','reset','sample','promote']) $(id).disabled=value;
  syncClassifierControl();
  if(!value) navigation();
  window.dispatchEvent(new Event('study-position-change'));
}
async function analyze(payload, mode='load', label, targetIndex) {
  if(busy) return;
  const number=++requestNumber;
  setBusy(true); selection=null; preview=null; pendingPromotion=null; $('promotion').hidden=true;
  $('input-error').hidden=true; notice('Checking the position and running the local analysis…');
  try {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),120000);
    let response;
    try { response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,model:classifierRequested()}),signal:controller.signal}); } finally {clearTimeout(timer);}
    const data=await response.json();
    if(!response.ok) throw new Error(data.error||'The position could not be analyzed.');
    if(number!==requestNumber) return;
    if(mode==='load') {timeline=data.history; index=data.selected_ply; $('position-label').textContent=label||(payload.pgn?'SUPPLIED PGN':'SUPPLIED POSITION');}
    else if(mode==='move') {timeline=timeline.slice(0,index+1); timeline.push(data.history.at(-1)); index=timeline.length-1; $('position-label').textContent='EXPLORING A VARIATION';}
    else if(mode==='navigate'&&targetIndex!==undefined) index=targetIndex;
    result=data; candidate=0; render();
    const model=data.model.status==='ok'?'local model compared':data.model.status==='disabled'?'model comparison off':'model needs attention';
    notice(data.engine.status==='error'?'Stockfish could not finish. See the engine evidence below.':`Position checked · ${data.engine.name} · ${model}`,data.engine.status==='error');
  } catch(error) {
    $('input-error').textContent=error.name==='AbortError'?'Analysis timed out. Try again with model comparison off.':error.message;
    $('input-error').hidden=false; notice('The previous position is still available.',true);
  } finally {setBusy(false);}
}

function renderBoard() {
  if(!result) return;
  const oldFocus=document.activeElement?.dataset?.square;
  const board=$('board'), fen=preview?.fen||result.board.fen, pieces=preview?fenPieces(fen):result.board.pieces;
  const files=flipped?'hgfedcba':'abcdefgh', ranks=flipped?'12345678':'87654321';
  const legal=selection&&!preview?result.board.legal_moves.filter(m=>m.uci.startsWith(selection)):[];
  board.replaceChildren();
  for(let row=0;row<8;row++) for(let col=0;col<8;col++) {
    const square=files[col]+ranks[row], piece=pieces[square];
    const dark=(square.charCodeAt(0)-97+Number(square[1])-1)%2===0;
    const button=el('button',undefined,`square${dark?' dark':''}`); button.dataset.square=square;button.setAttribute('role','gridcell');
    button.tabIndex=square===(oldFocus||'e2')?0:-1;
    const label=piece?`${piece===piece.toUpperCase()?'White':'Black'} ${names[piece.toLowerCase()]}`:'empty';
    const destination=legal.some(m=>m.uci.slice(2,4)===square);
    button.setAttribute('aria-label',`${square}, ${label}${selection===square?', selected':''}${destination?', legal destination':''}${preview?', continuation preview':''}`);
    button.setAttribute('aria-selected',String(selection===square));
    if(piece) {const span=el('span',glyphs[piece],`piece ${piece===piece.toUpperCase()?'white':'black'}`);span.setAttribute('aria-hidden','true');button.append(span);}
    if(col===0) {const rank=el('span',ranks[row],'coordinate rank');rank.setAttribute('aria-hidden','true');button.append(rank);}
    if(row===7) {const file=el('span',files[col],'coordinate file');file.setAttribute('aria-hidden','true');button.append(file);}
    if(selection===square) button.classList.add('selected');
    if(destination) button.classList.add('target');
    if(preview?.uci&&(preview.uci.startsWith(square)||preview.uci.slice(2,4)===square)) button.classList.add('preview');
    button.addEventListener('click',()=>squareClick(square));
    button.addEventListener('keydown',event=>{
      const delta={ArrowLeft:-1,ArrowRight:1,ArrowUp:-8,ArrowDown:8}[event.key];
      if(delta!==undefined) {event.preventDefault();const buttons=[...board.children],i=buttons.indexOf(button),target=buttons[Math.min(63,Math.max(0,i+delta))];button.tabIndex=-1;target.tabIndex=0;target.focus();}
      if(event.key==='Escape') {selection=null;renderBoard();board.querySelector(`[data-square="${square}"]`)?.focus();}
    });
    board.append(button);
  }
  const turn=fen.split(' ')[1]==='w'?'White':'Black';
  $('turn').textContent=preview?`${turn} to move · preview`:result.board.terminal?`${result.board.status} · ${result.board.result}`:`${turn} to move${result.board.status==='Check'?' · in check':''}`;
  $('board-hint').textContent=preview?'Stockfish continuation preview. Return to the analyzed position to play.':result.board.terminal?'The game is over. Return to an earlier position to explore.':selection?`Selected ${selection}. Legal destinations: ${[...new Set(legal.map(move=>move.uci.slice(2,4)))].join(', ')||'none'}. Escape clears selection.`:'Select a piece, then a highlighted destination.';
  window.dispatchEvent(new Event('study-position-change'));
}
function squareClick(square) {
  if(!result||busy) return;
  if(preview) {notice('Return to the analyzed position before playing a move.');return;}
  const options=selection?result.board.legal_moves.filter(m=>m.uci.startsWith(selection+square)):[];
  if(options.length) {
    if(options[0].uci.length===5) {pendingPromotion=selection+square; $('promotion').hidden=false; $('promotion-piece').focus(); return;}
    play(options[0].uci);return;
  }
  const piece=result.board.pieces[square];
  if(piece&&(piece===piece.toUpperCase())===(result.board.turn==='white')) selection=selection===square?null:square;
  else selection=null;
  renderBoard(); $('board').querySelector(`[data-square="${square}"]`)?.focus();
}
function linePayload(target=index, extra=[]) {return {fen:timeline[0].fen,moves:[...timeline.slice(1,target+1).map(step=>step.uci),...extra]};}
function play(uci) {analyze(linePayload(index,[uci]),'move');}
function navigation() {
  $('previous').disabled=busy||index<=0; $('next').disabled=busy||index>=timeline.length-1;
  $('move-count').textContent=index===0?'Start position':`Ply ${index} of ${timeline.length-1}`;
}
function renderTimeline() {
  $('timeline').replaceChildren();
  timeline.forEach((move,i)=>{const button=el('button',i===0?'Start':`${i%2===1?Math.ceil(i/2)+'. ':''}${move.san}`,i===index?'current':'');button.setAttribute('aria-label',i===0?'Go to start':`Go to ply ${i}, ${move.san}`);if(i===index)button.setAttribute('aria-current','step');button.addEventListener('click',()=>navigate(i));$('timeline').append(button);});
  navigation();
}
function navigate(target) {if(busy||target<0||target>=timeline.length||target===index)return;analyze(linePayload(target),'navigate',undefined,target);}
function scoreText(score) {
  if(!score||score.value===null)return '—';
  const prefix=score.bound==='lower'?'≥ ':score.bound==='upper'?'≤ ':'';
  if(score.kind==='mate') return `${prefix}${score.value>=0?'Mate in ':'Mated in '}${Math.abs(score.value)}`;
  const value=score.value/100;return prefix+(value>=0?'+':'')+value.toFixed(2);
}
function renderEngine() {
  const engine=result.engine, choices=engine.alternatives||[], chosen=choices[candidate];
  $('engine-state').textContent=engine.status==='ok'?engine.name:engine.status==='terminal'?'Game over':'Unavailable';
  $('best-move').textContent=chosen?.san||(result.board.terminal?result.board.result:'—');
  $('suggestion-label').textContent=candidate===0?'Suggested move':'Alternative move';
  $('score').textContent=scoreText(chosen?.score);
  $('perspective').textContent=chosen?`For ${chosen.score.perspective==='white'?'White':'Black'} · ${chosen.score.kind==='mate'?'mate distance':'pawn units'}`:'No search estimate';
  $('alternatives').replaceChildren(); choices.forEach((choice,i)=>{const button=el('button',choice.san,i===candidate?'active':'');button.setAttribute('aria-pressed',String(i===candidate));button.append(el('span',scoreText(choice.score)));button.addEventListener('click',()=>{candidate=i;preview=null;renderBoard();renderEngine();});$('alternatives').append(button);});
  $('facts').replaceChildren();
  for(const fact of chosen?.facts||[]) $('facts').append(el('li',fact.text));
  if(!chosen) $('facts').append(el('li',engine.error||`${result.board.status}. There is no move to analyze.`));
  $('pv').replaceChildren();
  for(const [i,step] of (chosen?.pv||[]).entries()) {const button=el('button');button.append(el('small',String(i+1)),document.createTextNode(step.san));button.setAttribute('aria-label',`Preview Stockfish ply ${i+1}: ${step.san}`);if(preview?.fen===step.fen)button.classList.add('active');button.addEventListener('click',()=>{preview=step;selection=null;renderBoard();renderEngine();notice(`Previewing Stockfish’s line after ${i+1} ${i===0?'half-move':'half-moves'}. The local model comparison still refers to the analyzed position.`);});$('pv').append(button);}
  $('return-position').hidden=!preview;
  $('engine-detail').textContent=chosen?`${engine.name} · ${engine.budget.threads} CPU threads · search target ${engine.budget.max_nodes.toLocaleString()} nodes or ${engine.budget.max_seconds} seconds. Stockfish can slightly overshoot its node target. Candidate ${chosen.rank}: depth ${chosen.depth??'unreported'}, ${chosen.nodes?.toLocaleString()??'unreported'} nodes. Score bound: ${chosen.score.bound}. Search and startup: ${engine.elapsed_seconds}s.`:(engine.error||'The board is terminal; no engine search is needed.');
}
function renderModel() {
  const model=result.model, box=$('model-result'), raw=$('raw-model');box.replaceChildren();raw.replaceChildren();
  if(model.status==='disabled') {box.append(el('p',model.reason,'model-status'));return;}
  const line=el('div',undefined,'model-line');
  for(const step of model.predictions||[]) {const cell=el('div',undefined,'model-ply');cell.append(el('strong',step.san||step.raw_choice_uci),el('span',`Ply ${step.ply} · ${step.accepted?'legal':'illegal · stopped'}`));line.append(cell);}
  box.append(line);
  const count=(model.predictions||[]).filter(s=>s.accepted).length;
  let text=`${count} raw ${count===1?'move':'moves'} legally replayed.`;
  if(model.stop_reason==='game_over')text+=' The game ends before three plies.';
  if(model.stop_reason==='raw_illegal_move')text+=' The first illegal choice ends the line.';
  if(model.status==='error')text+=' Model inference stopped; see the retained error below.';
  box.append(el('p',text,`model-status${model.status==='error'?' error':''}`));
  if(typeof model.root_raw_matches_engine==='boolean') box.append(el('p',`${model.root_raw_matches_engine?'The first raw choice matches':'The first raw choice differs from'} this Stockfish search. Exact shared prefix: ${model.exact_root_pv_prefix_plies} ${model.exact_root_pv_prefix_plies===1?'half-move':'half-moves'}.`, `model-status${model.root_raw_matches_engine?'':' disagree'}`));
  if(model.error)raw.append(el('p',model.error));
  if(model.identity)raw.append(el('p',`${model.identity.name} · ${model.identity.device} · ${model.elapsed_seconds}s. Weight SHA-256: ${model.identity.weight_sha256}`));
  for(const step of model.predictions||[]) {
    raw.append(el('p',`Ply ${step.ply}. Raw choice: ${step.raw_choice_uci}, ${step.raw_choice_is_legal?'legal':'illegal'}. Rule-filtered choice: ${step.legal_choice_uci||'none'} (shown separately; never substituted).`));
    const table=el('table',undefined,'raw-table'),head=el('tr');for(const name of ['Raw top 3','Legal?','Logit'])head.append(el('th',name));table.append(head);
    for(const row of step.raw_topk) {const tr=el('tr');for(const value of [row.move_uci,row.legal?'Yes':'No',row.logit.toFixed(3)])tr.append(el('td',value));table.append(tr);}raw.append(table);
  }
  raw.append(el('p','Logits are ranking scores, not probabilities or chess evaluations. Legal filtering uses board rules. This move classifier does not produce a strategic explanation.'));
  if(model.comparison_scope)raw.append(el('p',model.comparison_scope));
}
function render(){renderBoard();renderTimeline();renderEngine();renderModel();}
function coachingStudySnapshot(){return result?{position:linePayload(),fen:result.board.fen,terminal:result.board.terminal,preview:!!preview,busy,selectedUci:result.engine.alternatives?.[candidate]?.move_uci}:null;}
function captureCoachingStudy(){return result?{result:structuredClone(result),timeline:structuredClone(timeline),index,candidate,label:$('position-label').textContent,useModel:$('use-model').checked}:null;}
function restoreCoachingStudy(saved){
  if(!saved||busy)return;
  result=structuredClone(saved.result);timeline=structuredClone(saved.timeline);index=saved.index;candidate=saved.candidate;
  preview=null;selection=null;pendingPromotion=null;$('promotion').hidden=true;$('input-error').hidden=true;
  $('position-label').textContent=saved.label;$('use-model').checked=classifierConfigured&&saved.useModel;syncClassifierControl();render();navigation();
  notice('Returned to the retained position and selected move used for this draft.');
}
$('flip').addEventListener('click',()=>{flipped=!flipped;renderBoard();});
$('previous').addEventListener('click',()=>navigate(index-1));$('next').addEventListener('click',()=>navigate(index+1));
$('reset').addEventListener('click',()=>analyze({},'load','START POSITION'));
$('sample').addEventListener('click',()=>{$('position-input').value=mateFen;analyze({fen:mateFen},'load','ILLUSTRATIVE MATE IN ONE');});
$('load').addEventListener('click',()=>{const text=$('position-input').value.trim();if(!text){$('input-error').textContent='Paste a FEN position or one PGN game first.';$('input-error').hidden=false;$('position-input').focus();return;}analyze(text.split(/\s+/).length===6&&/^[prnbqkPRNBQK1-8/]+\s/.test(text)?{fen:text}:{pgn:text});});
$('position-input').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){$('load').click();}});
$('use-model').addEventListener('change',()=>{if(!classifierConfigured){syncClassifierControl();return;}if(result)analyze(linePayload(),'navigate');});
$('return-position').addEventListener('click',()=>{preview=null;renderBoard();renderEngine();notice('Returned to the analyzed position.');});
$('promote').addEventListener('click',()=>{if(pendingPromotion)play(pendingPromotion+$('promotion-piece').value);});
$('cancel-promotion').addEventListener('click',()=>{pendingPromotion=null;$('promotion').hidden=true;});
$('export').addEventListener('click',()=>{if(!result)return;const blob=new Blob([JSON.stringify({...result,session_history:timeline,session_selected_ply:index,session_selected_engine_move:result.engine.alternatives?.[candidate]?.move_uci??null,coaching:window.coachingEvidenceForCurrentPosition?.()??null},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='archit-chess-position-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice('Position evidence saved. This is an exploration record, not an evaluation result.');});
document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT','BUTTON','SUMMARY'].includes(document.activeElement.tagName))return;if(e.key==='ArrowLeft'){e.preventDefault();navigate(index-1);}if(e.key==='ArrowRight'){e.preventDefault();navigate(index+1);}});
(async()=>{try{const response=await fetch('/api/health');const health=await response.json();applyClassifierHealth(health);}catch{applyClassifierHealth({model_configured:false});}await analyze({pgn:opening},'load','ILLUSTRATIVE OPENING');})();
