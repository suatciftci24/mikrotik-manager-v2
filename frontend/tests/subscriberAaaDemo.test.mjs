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
