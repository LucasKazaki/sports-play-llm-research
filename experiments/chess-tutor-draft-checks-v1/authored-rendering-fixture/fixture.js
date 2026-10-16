"use strict";
let scenarios=[],job=null,study=null;
const byId=id=>document.getElementById(id);
function resetStudy(){study={position:structuredClone(job.context.position),selectedUci:job.context.selected_uci,preview:false};}
function draw(){
 const matches=coachingContextMatches(job.context,study);
 byId('stale').hidden=matches;
 byId('fixture-state').textContent=matches?'Viewing the authored requested position and selected move.':'Viewing a different authored position or selected move. Export excludes the earlier coaching record.';
 byId('fixture-draft').textContent=job.result.decoded_text;
 byId('fixture-raw').textContent=JSON.stringify(job.result,null,2);
 renderCoachingVerification(byId('verification'),job);
}
byId('scenario').addEventListener('change',()=>{job=structuredClone(scenarios.find(x=>x.id===byId('scenario').value).job);resetStudy();draw();});
byId('change-selected').addEventListener('click',()=>{study.selectedUci=study.selectedUci==='e2e4'?'d2d4':'e2e4';draw();});
byId('change-position').addEventListener('click',()=>{study.position={fen:job.context.position.fen,moves:['d2d4']};study.selectedUci='d7d5';draw();});
byId('return').addEventListener('click',()=>{resetStudy();draw();});
byId('export').addEventListener('click',()=>{
 const value={fixture_only:true,origin:'Authored renderer fixture; no model/engine/production qualification or quality evidence.',study:structuredClone(study),coaching:coachingContextMatches(job.context,study)?job:null};
 const text=JSON.stringify(value,null,2);byId('export-preview').textContent=text;byId('export-details').open=true;
 const url=URL.createObjectURL(new Blob([text],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='archit-authored-ui-fixture.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
fetch('/fixtures.json').then(r=>{if(!r.ok)throw Error('The authored fixture data could not load.');return r.json();}).then(data=>{
 if(data.fixture_only!==true)throw Error('This page requires authored fixture data.');scenarios=data.scenarios;
 for(const item of scenarios){const option=document.createElement('option');option.value=item.id;option.textContent=item.label;byId('scenario').append(option);}
 job=structuredClone(scenarios[0].job);byId('scenario').value=scenarios[0].id;resetStudy();draw();
}).catch(error=>{byId('error').hidden=false;byId('error').textContent=error.message;});

byId('fixture-theme').addEventListener('change',()=>{document.documentElement.dataset.fixtureTheme=byId('fixture-theme').value;});
byId('fixture-text').addEventListener('change',()=>{document.documentElement.dataset.fixtureText=byId('fixture-text').value;});
