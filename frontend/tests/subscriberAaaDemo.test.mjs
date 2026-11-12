import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const hooks={...React,useState:value=>[value,()=>{}]};
const code=buildSync({entryPoints:['src/components/SubscriberAaaDemo.tsx'],bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const data={mode:'SYNTHETIC_FIXTURE_ONLY',scenario:'PLAN',account_id:'demo-sub-aaa-memory',history_persistence:'DISPOSABLE_MEMORY',request_id:'request-fixture',correlation_id:'correlation-fixture',fingerprint:'f'.repeat(64),result:{label:'Sentetik simülasyon başarılı',outcome:'PASS',live_ready:false,external_writes:false,simulated_final_authority:'RADIUS',simulated_final_revision:4,blockers:[]},events:[{revision:1,state:'RESERVED',at:'2026-11-11T09:00:00Z',correlation_id:'correlation-fixture',actor_id:'aaa-memory-actor'}]};
const renderResult=(value=data,scenario='PLAN')=>renderToStaticMarkup(React.createElement(module.exports.AaaDemoResult,{data:value,scenario}));
test('authority is explicit for LOCAL RADIUS and unknown; demo is opt-in and never a source mutation',()=>{
 for(const source of ['LOCAL','RADIUS',null,'invalid']){
  const html=renderToStaticMarkup(React.createElement(module.exports.SubscriberAaaDemo,{source}));
  assert.match(html,new RegExp(source==='LOCAL'||source==='RADIUS'?source:'BELİRSİZ'));
  assert.match(html,/seçili aboneye ait değildir/);assert.match(html,/aria-expanded="false"/);
  assert.doesNotMatch(html,/<form|type="submit"|İstek UUID/);
 }
});
test('fixture history carries correlation, actor, separate revisions and explicit synthetic provenance',()=>{
 const html=renderResult();
 for(const value of ['Örnek AAA işlem geçmişi','correlation-fixture','request-fixture','aaa-memory-actor','İşlem revizyonu 1','Model hesap revizyonu','kalıcı audit','Canlı hazırlık doğrulanmadı'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/<form|<button|type="submit"/);
});
test('live claims, wrong fixture or stale scenario fail closed; blockers are visible',()=>{
 for(const value of [{...data,mode:'LIVE'},{...data,account_id:'existing-account'},{...data,result:{...data.result,external_writes:true}},{...data,result:{...data.result,live_ready:true}},{...data,history_persistence:'POSTGRESQL'}]){
  const html=renderResult(value);assert.match(html,/role="alert"/);assert.doesNotMatch(html,/request-fixture/);
 }
 assert.match(renderResult(data,'COMPENSATION'),/sözleşmesi doğrulanamadı/);
 assert.match(renderResult({...data,result:{...data.result,blockers:['READ_ONLY_RECONCILIATION_REQUIRED']}}),/READ_ONLY_RECONCILIATION_REQUIRED/);
});
test('AAA transport sends exact versioned GET for each scenario without a body and parses JSON',async()=>{
 const original=globalThis.fetch,calls=[];
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return {ok:true,json:async()=>data};};
 try{
  const controller=new AbortController();
  for(const scenario of ['PLAN','COMPENSATION','RECONCILIATION']){
   assert.deepEqual(await module.exports.loadAaaDemoPreview('/aaa-demo/preview?scenario='+scenario,{signal:controller.signal}),data);
   const call=calls.at(-1);assert.equal(call.url,'/api/v1/aaa-demo/preview?scenario='+scenario);
   assert.equal(call.init.method,'GET');assert.equal(call.init.body,undefined);assert.equal(call.init.credentials,'include');assert.equal(call.init.signal,controller.signal);
  }
 }finally{globalThis.fetch=original;}
});
test('AAA Not Found explains unavailable endpoint without asserting stale backend or fabricating success',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>({ok:false,status:404,json:async()=>({detail:'Not Found'})});
 try{
  await assert.rejects(module.exports.loadAaaDemoPreview('/aaa-demo/preview?scenario=PLAN'),error=>{
   assert.equal(error.status,404);assert.match(error.message,/GET \/api\/v1\/aaa-demo\/preview/);
   assert.match(error.message,/checkout ve Vite proxy/);assert.match(error.message,/tek başına eski backend kanıtı değildir/);assert.match(error.message,/Önizleme çalıştırılmadı/);return true;
  });
 }finally{globalThis.fetch=original;}
});
test('AAA auth errors and server errors retain their status and are not reclassified as missing endpoints',async()=>{
 const original=globalThis.fetch;
 try{
  for(const status of [401,403,500]){
   globalThis.fetch=async()=>({ok:false,status,json:async()=>({detail:'Original failure'})});
   await assert.rejects(module.exports.loadAaaDemoPreview('/aaa-demo/preview?scenario=PLAN'),error=>error.status===status&&error.message==='Original failure');
  }
 }finally{globalThis.fetch=original;}
});
