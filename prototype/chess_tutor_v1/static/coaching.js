"use strict";
function coachingContextMatches(context,study){
  return !!context&&!!study&&JSON.stringify(context.position)===JSON.stringify(study.position)&&!study.preview&&
    (context.kind!=='selected_move'||context.selected_uci===study.selectedUci);
}
function coachingDraftText(raw){
  const complete=String(raw.decoded_text||raw.raw_text||raw.error||'').replace(/<\|im_end\|>\s*$/,'').trim();
  const analysis=complete.match(/(?:^|\n)ANALYSIS:\s*([\s\S]*?)(?=\n(?:BEST_MOVE|CRITICAL_LINE|PROMISING_MOVES|EVALUATION):|$)/);
  return analysis?analysis[1].trim():complete;
}
(() => {
  const byId=id=>document.getElementById(id), active=new Set(['starting','running','stopping']);
  let available=false, fixture=false, job=null, originalStudy=null, pollTimer=null, sending=false, requestError=null, pollFailures=0, stopRequested=false;
  const snapshot=()=>coachingStudySnapshot();
  const text=(id,value)=>{byId(id).textContent=value;};
  function render(){
    const study=snapshot(), running=job&&active.has(job.status), selected=byId('coach-mode').value==='selected';
    byId('ask-coach').disabled=!available||sending||!!running||!study||study.busy||study.preview||study.terminal||(selected&&!study.selectedUci);
    text('ask-coach',selected?'Explain selected move':'Explain this position');
    byId('coach-mode').disabled=sending||!!running;
    byId('stop-coach').hidden=!running;
    byId('stop-coach').disabled=job?.status==='stopping';
    byId('coach-fixture').hidden=!fixture&&!job?.fixture;
    const stale=job&&!coachingContextMatches(job.context,study);
    byId('coach-stale').hidden=!stale;
    byId('coach-stale-message').textContent=job?.context?.kind==='selected_move'&&!study?.preview&&JSON.stringify(job.context.position)===JSON.stringify(study?.position)&&job.context.selected_uci!==study?.selectedUci?'This draft explains an earlier selected move.':'This response belongs to an earlier position.';
    byId('coach-return').disabled=!!study?.busy;
    if(!job)return;
    const messages={starting:'Starting the local model…',running:'Queen is preparing a draft. You can keep exploring the board.',stopping:'Stopping after the current step…',cancelled:'Coaching stopped. Your position is still available.',busy:'Queen is busy with another local task. You can keep exploring the board.',terminal:'This position is already game over.',completed:'Queen’s draft explanation',partial:'The response stopped before it was complete. The retained text is shown below.',failed:'The model could not finish this request. Your board is still available.'};
    const raw=job.result;
    const resourceFailure=/resource reserve|out of memory|cuda error/i.test(job.error||'');
    text('coach-status',(job.fixture?'Interface fixture · ':'')+(requestError||(resourceFailure?'The model stopped to keep memory available. Its retained response is shown below.':messages[job.status])||'Request status unavailable.'));
    const origin=job.context?.kind==='selected_move'?`${job.context.selected_move_origin==='stockfish_selection'?'Stockfish’s selected move':'The selected move'} ${job.context.selected_san||job.context.selected_uci} was supplied. No score or continuation was sent.`:'Current position and its prior boards only. No Stockfish move, score or continuation supplied.';
    text('coach-scope',origin);
    const content=byId('coach-content');content.replaceChildren();
    if(raw){
      const parsed=raw.parsed||{};
      if(raw.ui_validation_error){const line=document.createElement('p');line.textContent='This response failed the runtime check. Its retained text is shown for inspection.';content.append(line);}
      else if(parsed.raw_choice_uci){const line=document.createElement('p');line.textContent=parsed.accepted_move_uci?`Raw move: ${parsed.raw_choice_uci} · legal in the requested position.`:`Raw move: ${parsed.raw_choice_uci} · ${parsed.raw_choice_is_legal?'legal coordinates, invalid piece description':'illegal in the requested position'}. It has not been replaced.`;content.append(line);}
      else if(!active.has(job.status)&&job.status!=='terminal'){const line=document.createElement('p');line.textContent='Queen did not provide a readable move.';content.append(line);}
      const continuation=parsed.critical_line;
      if(!raw.ui_validation_error&&continuation?.steps?.length){const line=document.createElement('p');line.textContent='Model line: '+continuation.steps.map(step=>step.san||step.raw_uci||'unreadable move').join(' → ')+'. '+(continuation.failure?'The line stops at an invalid move. It has not been replaced.':'Legal move replay only; this does not verify the explanation.');content.append(line);}
      const draft=coachingDraftText(raw),prose=document.createElement('p');
      if(draft.length<=520){prose.textContent=draft;content.append(prose);}
      else {
        const head=draft.slice(0,520),boundary=head.lastIndexOf(' ');
        prose.textContent=head.slice(0,boundary>460?boundary:520).trimEnd()+'…';content.append(prose);
        const full=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('p');
        full.className='coach-explanation';summary.textContent='Read the full explanation';body.textContent=draft;
        full.append(summary,body);full.addEventListener('toggle',()=>{prose.hidden=full.open;summary.textContent=full.open?'Close the full explanation':'Read the full explanation';});content.append(full);
      }
      const settings=raw.settings||{};
      const execution=raw.execution||settings, show=value=>value===undefined||value===null?'unreported':typeof value==='object'?JSON.stringify(value):String(value);
      text('coach-execution',[
        `Candidate: ${show(execution.candidate_id??raw.candidate_id)}`,
        `Actual execution: ${show(execution.backend??settings.backend)}`,
        `Mode: ${show(execution.generation_mode??settings.generation_mode)} · Precision: ${show(execution.precision_profile??settings.precision_profile)}`,
        `Quantization: ${show(execution.quantization)} · Protocol: ${show(execution.protocol_sha256)}`,
        `Canonical provenance: ${show(execution.canonical_provenance)}`,
        `Finish: ${show(raw.finish_reason)} · ${show(raw.elapsed_seconds)} seconds. Model prose has not been verified.`
      ].join('\n'));
      text('coach-raw',JSON.stringify(raw,null,2));
    }
    byId('coach-details').hidden=!raw;
  }
  async function jsonRequest(url,body){
    const response=await fetch(url,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok)throw new Error(data.error||'The coaching request could not finish.');return data;
  }
  async function poll(){
    if(!job||!active.has(job.status))return;
    const identifier=job.request_id,url=job.poll_url;
    try {const data=await jsonRequest(url);if(job?.request_id!==identifier)return;job=data;if(stopRequested&&active.has(job.status))job.status='stopping';requestError=null;pollFailures=0;render();if(active.has(job.status))pollTimer=setTimeout(poll,1000);else {stopRequested=false;if(job.status==='failed')await health();}}
    catch(error){if(job?.request_id!==identifier)return;requestError='The request status could not be read. Its local worker still has a time limit.';render();if(++pollFailures<=5)pollTimer=setTimeout(poll,2000);}
  }
  async function health(){
    try{const data=await jsonRequest('/api/health');available=!!data.coaching?.configured&&data.coaching?.status!=='blocked';fixture=!!data.coaching?.fixture;if(!job)text('coach-status',available?'Choose a position, then ask for an explanation.':'Local coaching is not available in this run. The board remains usable.');}catch{available=false;}
    render();
  }
  byId('ask-coach').addEventListener('click',async()=>{
    const study=snapshot();if(!study||sending||job&&active.has(job.status))return;
    const retainedStudy=captureCoachingStudy();
    const payload={position:study.position};
    if(byId('coach-mode').value==='selected'){payload.selected_uci=study.selectedUci;payload.selected_move_origin='stockfish_selection';}
    sending=true;requestError=null;pollFailures=0;stopRequested=false;render();text('coach-status','Starting the local model…');
    try{job=await jsonRequest('/api/coach',payload);originalStudy=retainedStudy;render();pollTimer=setTimeout(poll,150);}
    catch(error){requestError=error.message;text('coach-status',requestError);}finally{sending=false;render();}
  });
  byId('stop-coach').addEventListener('click',async()=>{
    if(!job||!active.has(job.status))return;
    const identifier=job.request_id,url=job.poll_url;stopRequested=true;job.status='stopping';render();
    try{const data=await jsonRequest(url+'/cancel',{});if(job?.request_id!==identifier)return;job=data;requestError=null;render();clearTimeout(pollTimer);pollTimer=setTimeout(poll,150);}catch(error){if(job?.request_id!==identifier)return;stopRequested=false;requestError=error.message;render();}
  });
  byId('coach-return').addEventListener('click',()=>{if(job&&originalStudy)restoreCoachingStudy(originalStudy);});
  byId('coach-mode').addEventListener('change',render);
  window.addEventListener('study-position-change',render);
  window.coachingEvidenceForCurrentPosition=()=>job&&coachingContextMatches(job.context,snapshot())?job:null;
  window.addEventListener('pagehide',()=>{clearTimeout(pollTimer);if(job&&active.has(job.status))fetch(job.poll_url+'/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',keepalive:true}).catch(()=>{});});
  health();
})();
