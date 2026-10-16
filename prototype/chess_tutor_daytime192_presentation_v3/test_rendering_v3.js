"use strict";
// Authored DOM/metadata only. No browser, HTTP, engine, runtime, or retained raw answer.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=__dirname;
function node(tag='div'){
  return {tag,textContent:'',children:[],hidden:false,disabled:false,checked:false,className:'',
    classList:{toggle(){}},append(...values){this.children.push(...values);},replaceChildren(...values){this.children=[...values];}};
}
function flatten(value){return String(value.textContent||'')+value.children.map(flatten).join(' ');}
function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node};
const app=fs.readFileSync(path.join(root,'static/app.js'),'utf8');
const appContext=vm.createContext({document,window:{dispatchEvent(){}},Event:class{},structuredClone});
vm.runInContext(app.slice(0,app.indexOf("$('flip').addEventListener")),appContext);
vm.runInContext("applyClassifierHealth({model_configured:false});setBusy(true);setBusy(false);render=()=>{};restoreCoachingStudy({result:{},timeline:[],index:0,candidate:0,label:'authored',useModel:true});",appContext);
assert.equal(nodes.get('use-model').checked,false);assert.equal(nodes.get('use-model').disabled,true);
nodes.get('use-model').checked=true;assert.equal(vm.runInContext('classifierRequested()',appContext),false);
vm.runInContext('applyClassifierHealth({model_configured:true});setBusy(true);',appContext);
assert.equal(nodes.get('use-model').disabled,true);
vm.runInContext('setBusy(false);',appContext);assert.equal(nodes.get('use-model').disabled,false);
nodes.get('use-model').checked=false;vm.runInContext('setBusy(true);setBusy(false);',appContext);
assert.equal(nodes.get('use-model').checked,false); // Preserve the person's opt-out.

const coaching=fs.readFileSync(path.join(root,'static/coaching.js'),'utf8');
const context=vm.createContext({document});vm.runInContext(coaching.slice(0,coaching.indexOf('(() => {')),context);
const profile='queen-daytime192-research-preview.v1';
const raw=freeze({ui_provenance:{profile_id:profile,response_binding_verified:true},
  settings:{backend:'cuda',generation_mode:'no_cache',precision_profile:'math_sdpa_fp32_reduction'},
  quantization:{requested:{load_in_4bit:true,bnb_4bit_quant_type:'nf4',bnb_4bit_compute_dtype:'bfloat16',bnb_4bit_use_double_quant:true},
    actual_lora_dtype:'float32',actual_decoder_inventory:Array(252).fill('LAYER_DUMP_NOT_FOR_SUMMARY')},
  entrypoint_envelope:{entrypoint:{protocol_sha256:'a'.repeat(64)}},nf4_protocol_sha256:'b'.repeat(64),finish_reason:'eos'});
const original=JSON.stringify(raw);context.authored=raw;
let mount=node();context.mount=mount;context.job={status:'completed',request_id:'authored',result:raw,
  verification:{status:'unavailable',reason:'Legacy candidate hash mismatch'}};
vm.runInContext('renderCoachingVerification(mount,job)',context);
assert.match(flatten(mount),/Automatic checks unavailable/);assert.match(flatten(mount),/explanation is unassessed/);
assert.doesNotMatch(flatten(mount),/hash mismatch/);
for(const changed of [{ui_validation_error:'real binding error'},
  {ui_provenance:{profile_id:profile,response_binding_verified:false}},
  {ui_provenance:{profile_id:'other-profile',response_binding_verified:true}}]){
  mount=node();context.mount=mount;context.job={status:'completed',result:{...raw,...changed},verification:{status:'unavailable',reason:'real binding error'}};
  vm.runInContext('renderCoachingVerification(mount,job)',context);
  assert.match(flatten(mount),/real binding error/);assert.doesNotMatch(flatten(mount),/Automatic checks unavailable/);
}
const summary=vm.runInContext('coachingExecutionSummary(authored)',context);
assert.match(summary,/4-bit · NF4/);assert.match(summary,/Actual LoRA dtype: float32/);
assert.match(summary,new RegExp('Request protocol: '+'a'.repeat(64)));
assert.match(summary,new RegExp('NF4 protocol: '+'b'.repeat(64)));
assert.doesNotMatch(summary,/LAYER_DUMP/);assert.equal(JSON.stringify(raw),original);
context.generic={execution:{backend:'legacy',quantization:'BF16',protocol_sha256:'legacy-protocol'},settings:{generation_mode:'no_cache'}};
assert.match(vm.runInContext('coachingExecutionSummary(generic)',context),/BF16 · Request protocol: legacy-protocol/);
assert.match(vm.runInContext('coachingOrigin({},authored)',context),/Current FEN only/);
assert.match(vm.runInContext('coachingOrigin({},null)',context),/Current FEN only/); // Pending job: fixed192 handler, no response yet.
assert.match(vm.runInContext("coachingOrigin({kind:'selected_move',selected_uci:'e2e4'},null)",context),/Current FEN and the supplied selected move/);
assert.doesNotMatch(vm.runInContext('coachingOrigin({},authored)',context),/and its prior boards/);
assert.match(vm.runInContext("coachingOrigin({kind:'selected_move',selected_uci:'e2e4'},authored)",context),/Current FEN and the supplied selected move/);
assert.match(vm.runInContext('coachingOrigin({},generic)',context),/and its prior boards/);
console.log('Authored classifier state, binding-error, immutable metadata, origin and compact summary checks passed.');
