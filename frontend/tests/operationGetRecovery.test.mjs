import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {fileURLToPath} from 'node:url';
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/lib/subscriberOperationRecovery.ts',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text;
const module={exports:{}};new Function('module','exports',code)(module,module.exports);
const {subscriberOperationError,readOperationResults,unknownOperation}=module.exports;
const entry=index=>({request_id:'synthetic-request-'+index,item_id:'demo-managed-sub-'+index,operation:'STATUS',value:'ACTIVE',expected_revision:1,expected_router_id:'demo-managed-router-fixture'});
const receipt=(e,success=true)=>({...unknownOperation(e),actor_id:'synthetic.actor',router_id:e.expected_router_id,previous_router_id:e.expected_router_id,recorded:true,success,revision:2,occurred_at:'2026-11-06T12:00:00Z',values:success?{status:'ACTIVE'}:{},error:success?null:'Synthetic revision conflict'});

test('partial bulk recovery preserves known success/failure and reads only unknown UUIDs',async()=>{
 const entries=[entry(1),entry(2),entry(3)],known=[receipt(entries[0]),receipt(entries[1],false)],calls=[];
 const oldFetch=globalThis.fetch,oldWindow=globalThis.window;globalThis.window={dispatchEvent(){}};
 let step=0;
 globalThis.fetch=async(url,init)=>{
  calls.push(url);assert.equal(init.method,undefined);assert.equal(init.body,undefined);assert.ok(url.endsWith('/'+entries[2].request_id));
  if(step===0)return {ok:true,json:async()=>({request_id:entries[2].request_id,status:'UNKNOWN',response:null})};
  if(step===1)return {ok:false,status:403,json:async()=>({detail:'Denied'})};
  return {ok:true,json:async()=>({request_id:entries[2].request_id,status:'FAILED',response:receipt(entries[2],false)})};
 };
 try{
  let result=await readOperationResults(entries,known,new AbortController().signal);
  assert.deepEqual(result.slice(0,2),known);assert.equal(result[2].recorded,false);
  step++;result=await readOperationResults(entries,result,new AbortController().signal);
  assert.deepEqual(result.slice(0,2),known);assert.equal(result[2].recorded,false);
  step++;result=await readOperationResults(entries,result,new AbortController().signal);
  assert.deepEqual(result.slice(0,2),known);assert.equal(result[2].recorded,true);assert.equal(result[2].success,false);
  await readOperationResults(entries,result,new AbortController().signal);assert.equal(calls.length,3,'resolved records never refetched');
 }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
});
test('malformed/mismatched GET receipts never become saved successes',async()=>{
 const e=entry(1),oldFetch=globalThis.fetch;
 try{
  for(const data of [
   {request_id:'wrong',status:'SUCCESS',response:receipt(e)},
   {request_id:e.request_id,status:'SUCCESS',response:receipt(entry(2))},
   {request_id:e.request_id,status:'FAILED',response:receipt(e)},
   {request_id:e.request_id,status:'SUCCESS',response:{...receipt(e),values:null}},
   {request_id:e.request_id,status:'SUCCESS',response:{...receipt(e),recorded:false}},
   {request_id:e.request_id,status:'SUCCESS',response:{...receipt(e),values:{status:'PAUSED'}}},
   ...[{revision:1},{revision:99},{router_id:'demo-managed-router-other'},{previous_router_id:'demo-managed-router-other'},{actor_id:''},{occurred_at:'invalid'},{error:'Unexpected error'}].map(change=>({request_id:e.request_id,status:'SUCCESS',response:{...receipt(e),...change}}))
  ]){
   globalThis.fetch=async()=>({ok:true,json:async()=>data});
   const result=await readOperationResults([e],[],new AbortController().signal);assert.equal(result[0].recorded,false);
  }
 }finally{globalThis.fetch=oldFetch;}
});
test('GET fanout is capped at five; aborted recovery never starts more work',async()=>{
 const entries=Array.from({length:12},(_,i)=>entry(i)),oldFetch=globalThis.fetch;
 let active=0,max=0,calls=0;
 globalThis.fetch=async(url,init)=>{
  assert.equal(init.method,undefined);calls++;max=Math.max(max,++active);await new Promise(setImmediate);active--;
  const e=entries.find(e=>url.endsWith('/'+e.request_id));return {ok:true,json:async()=>({request_id:e.request_id,status:'SUCCESS',response:receipt(e)})};
 };
 try{
  const result=await readOperationResults(entries,[],new AbortController().signal);
  assert.equal(calls,12);assert.equal(max,5);assert.ok(result.every(r=>r.recorded));
  const controller=new AbortController();controller.abort();
  const unknown=await readOperationResults(entries,[],controller.signal);assert.equal(calls,12);assert.ok(unknown.every(r=>!r.recorded));
 }finally{globalThis.fetch=oldFetch;}
});

test('network and malformed response errors use Turkish instructions without hiding business errors',()=>{
 assert.match(subscriberOperationError(new TypeError('Failed to fetch')),/Bağlantıyı kontrol/);
 assert.match(subscriberOperationError(new SyntaxError('Unexpected token')),/doğrulanabilir işlem yanıtı/);
 assert.equal(subscriberOperationError(new Error('Abone revizyonu değişti.')),'Abone revizyonu değişti.');
});
