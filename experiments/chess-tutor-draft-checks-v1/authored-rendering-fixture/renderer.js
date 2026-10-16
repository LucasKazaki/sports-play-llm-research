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
function coachingRawSpan(raw,span){
  const points=Array.from(String(raw.raw_text??''));
  if(!span||span.unit!=='unicode_code_points'||!Number.isInteger(span.start)||!Number.isInteger(span.end)||span.start<0||span.end<=span.start||span.end>points.length||!/^[0-9a-f]{64}$/.test(span.sha256||''))return null;
  return points.slice(span.start,span.end).join('');
}
function renderCoachingVerification(mount,job){
  mount.replaceChildren();mount.hidden=!job?.result||job.status==='terminal';if(mount.hidden)return;
  const add=(tag,value,parent=mount,className='')=>{const node=document.createElement(tag);node.textContent=value;node.className=className;parent.append(node);return node;};
  add('h3','Rule checks for this draft');
  add('p','Only the statements listed here were checked. Other text is unassessed.',mount,'draft-check-scope');
  const record=job.verification,raw=job.result;
  if(!record||record.status==='unavailable'){add('p',record?.reason||'Rule checks are not available for this draft. The original response is still available.');return;}
  if(record.request_id!==job.request_id||record.context&&(record.context.fen!==job.context?.fen||record.context.selected_uci!==(job.context?.selected_uci??null))){add('p','Rule checks do not match this request. The original response is still available.');return;}
  const observation=record.move_observations;
  if(observation?.status==='observed'){
    add('h4',`For the reported move ${observation.move_san} (${observation.move_uci})`);
    add('p',(observation.gives_checkmate?'The move gives checkmate.':observation.gives_check?'The move gives check.':'The move does not give check.')+' '+(observation.captures?`It captures a ${observation.victim.color} ${observation.victim.piece}.`:'It does not capture a piece.'));
    add('p','Board observations only; these do not verify the explanation.',mount,'draft-check-scope');
  }
  const status=(parent,value)=>add('span',({supported:'Supported',contradicted:'Contradicted',unassessed:'Unassessed'})[value]||'Unassessed',parent,'draft-check-status '+value);
  const identity=record.selected_identity;
  if(identity?.supplied_uci){const row=add('p','Selected-move identity: ');status(row,identity.status);add('span',identity.status==='supported'?` The reported move matches supplied ${identity.supplied_uci}.`:identity.status==='contradicted'?` The reported move ${identity.reported_uci} differs from supplied ${identity.supplied_uci}.`:` ${identity.reason||'No unambiguous legal reported move.'}`,row);}
  else if(identity)add('p','No selected move was supplied.',mount,'draft-check-scope');
  add('h4','Statements matched in the draft');
  const claims=record.claims||[];
  if(!claims.length){add('p',record.reason||'No draft statements match the limited checker. Other text is unassessed.');return;}
  const alignment=record.analysis_alignment;
  if(alignment?.selected_uci){const row=add('p','Statement move versus supplied move: ');status(row,alignment.status);add('span',` Statement move ${alignment.analysis_move_uci||'unmapped'}; supplied move ${alignment.selected_uci}.`,row);}
  const list=add('ul','',mount,'draft-check-list'),details=add('details','',mount,'draft-check-details');
  add('summary','Inspect matched statements',details);
  for(const claim of claims){
    const excerpt=coachingRawSpan(raw,claim.span),bound=excerpt!==null&&excerpt===claim.exact_raw_text;
    const row=add('li','',list),ownMove=claim.analysis_move_san&&claim.analysis_move_uci?`${claim.analysis_move_san} (${claim.analysis_move_uci})`:'an unmapped move';
    add('strong',`Statement about ${ownMove}`,row);status(row,bound?claim.status:'unassessed');
    const label=claim.kind==='check_or_mate'?claim.exact_raw_text:claim.expected===null?'does not capture a piece':claim.expected?`captures a ${claim.expected.color} ${claim.expected.piece}`:'capture statement';
    add('p',bound?label:'The exact statement span could not be matched.',row);
    if(claim.reason){const reasons={mover_mismatch:'The stated piece is not on that square.',capture_description_mismatch:'The move description does not match the captured piece.',illegal_move:'The stated move is not legal in the requested position.',promotion_colour_mismatch:'The promotion names the wrong side.',square_out_of_range:'The move names an invalid square.'};add('p',reasons[claim.reason]||'The statement could not be mapped to one legal move.',row,'draft-check-scope');}
    add('p',`Requested position · branch starts before ${ownMove}.`,details);
    add('pre',bound?excerpt:'Unassessed: statement span mismatch.',details);
    add('p',bound?`Raw text code points ${claim.span.start}–${claim.span.end}; ${claim.span.sha256}`:'No statement verdict is shown.',details,'draft-check-scope');
  }
  add('p','Each statement uses its own ANALYSIS move. BEST_MOVE identity is checked separately.',details,'draft-check-scope');
}
