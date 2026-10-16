"""Actual frontend functions with authored DOM/API fixtures, never a live model."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_actual_renderer_context_export_and_disclosure_with_authored_fixtures():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the actual frontend fixture')
    source = Path(__file__).resolve().parents[1]/'prototype/chess_tutor_v1/static/coaching.js'
    program = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(process.argv[1],'utf8'),prefix=code.split('(() => {')[0];
class Element {
 constructor(tag='div'){this.tagName=tag;this.children=[];this._text='';this.className='';this.hidden=false;this.disabled=false;this.open=false;this.value='';this.events={};this.replacements=0;}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(x=>x.textContent).join(' ');}
 set innerHTML(value){throw new Error('Untrusted HTML insertion');}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this._text='';this.children=nodes;this.replacements++;}
 addEventListener(name,fn){this.events[name]=fn;}
}
const ids=new Map(),get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id);};
const document={createElement:tag=>new Element(tag),getElementById:get};
const context={document};vm.runInNewContext(prefix+';globalThis.draw=renderCoachingVerification;globalThis.slice=coachingRawSpan;',context);
const rawText='😀 gives check',span={start:2,end:13,unit:'unicode_code_points',sha256:'2'.repeat(64)};
const position={fen:'authored-root',moves:[]};
const job={request_id:'authored-rendering-fixture',status:'completed',fixture:true,context:{position,fen:'authored-current',kind:'selected_move',selected_uci:'e2e4',selected_san:'e4'},result:{status:'completed',raw_text:rawText,decoded_text:'A different displayed draft.',parsed:{retained:true}},verification:{schema:'chess.tutor-draft-checks.v1',status:'checked',request_id:'authored-rendering-fixture',context:{fen:'authored-current',selected_uci:'e2e4'},whole_prose_assessed:false,move_observations:{status:'observed',move_san:'e4',move_uci:'e2e4',gives_check:false,gives_checkmate:false,captures:false},selected_identity:{status:'supported',supplied_uci:'e2e4',reported_uci:'e2e4'},analysis_alignment:{status:'contradicted',selected_uci:'e2e4',analysis_move_uci:'g1f3'},claims:[{kind:'check_or_mate',status:'contradicted',span,exact_raw_text:'gives check',analysis_move_san:'Nf3',analysis_move_uci:'g1f3'}]}};
const before=JSON.stringify(job),mount=new Element();
assert.equal(context.slice(job.result,span),'gives check');
context.draw(mount,job);
assert.match(mount.textContent,/Statement about Nf3 \(g1f3\)/);
assert.match(mount.textContent,/For the reported move e4 \(e2e4\)/);
assert.match(mount.textContent,/Statement move versus supplied move/);
assert.match(mount.textContent,/Contradicted/);
assert.match(mount.textContent,/Other text is unassessed/);
assert.equal(JSON.stringify(job),before);
const bad=structuredClone(job);bad.verification.claims[0].span.start=1;
context.draw(mount,bad);
const list=mount.children.find(x=>x.tagName==='ul');assert.match(list.textContent,/Unassessed/);assert.doesNotMatch(list.textContent,/Contradicted/);
const zero=structuredClone(job);zero.verification.claims=[];zero.verification.reason='No canonical statements. Other text is unassessed.';
context.draw(mount,zero);assert.match(mount.textContent,/No canonical statements/);assert.doesNotMatch(mount.textContent,/Inspect matched statements/);
const unavailable=structuredClone(job);unavailable.verification={status:'unavailable',reason:'Checks unavailable.'};
context.draw(mount,unavailable);assert.match(mount.textContent,/Checks unavailable/);assert.doesNotMatch(mount.textContent,/Supported/);
const staleRecord=structuredClone(job);staleRecord.verification.context.selected_uci='d2d4';
context.draw(mount,staleRecord);assert.match(mount.textContent,/do not match/);assert.doesNotMatch(mount.textContent,/Supported/);
const xss=structuredClone(job);xss.result.raw_text='<script>alert(1)</script>';xss.verification.claims[0].span={...span,start:0,end:25};xss.verification.claims[0].exact_raw_text=xss.result.raw_text;
context.draw(mount,xss);assert.match(mount.textContent,/<script>alert/); // textContent only, never parsed markup.

// Exercise the actual full module, including its cache, stale/return behavior
// and the same evidence getter used by the existing position exporter.
(async()=>{
 let study={position,fen:'authored-current',preview:false,busy:false,terminal:false,selectedUci:'e2e4'};
 const events={},window={addEventListener:(name,fn)=>events[name]=fn};
 get('coach-mode').value='selected';
 const sandbox={document,window,JSON,Array,Set,String,Number,structuredClone,console,
  coachingStudySnapshot:()=>study,captureCoachingStudy:()=>structuredClone(study),
  restoreCoachingStudy:saved=>{study=structuredClone(saved);events['study-position-change']();},
  setTimeout:()=>1,clearTimeout:()=>{},fetch:async(url)=>({ok:true,json:async()=>url==='/api/health'?{coaching:{configured:true,status:'ready',fixture:true}}:structuredClone(job)})};
 vm.runInNewContext(code,sandbox);await new Promise(resolve=>setImmediate(resolve));
 await get('ask-coach').events.click();
 const panel=get('coach-verification'),details=panel.children.find(x=>x.tagName==='details');assert.ok(details);
 details.open=true;const replacements=panel.replacements;
 events['study-position-change']();assert.equal(panel.replacements,replacements);assert.equal(details.open,true);
 const matching=window.coachingEvidenceForCurrentPosition();assert.equal(matching.verification.request_id,job.request_id);
 study={...study,selectedUci:'d2d4'};events['study-position-change']();
 assert.equal(get('coach-stale').hidden,false);assert.equal(window.coachingEvidenceForCurrentPosition(),null);
 await get('coach-return').events.click();
 assert.equal(get('coach-stale').hidden,true);assert.equal(window.coachingEvidenceForCurrentPosition().verification.request_id,job.request_id);
 study={...study,position:{fen:'another-root',moves:[]}};events['study-position-change']();
 assert.equal(window.coachingEvidenceForCurrentPosition(),null);
 assert.equal(JSON.stringify(job),before);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    subprocess.run([node, '-e', program, str(source)], check=True, capture_output=True, text=True)
