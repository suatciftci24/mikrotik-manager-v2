import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let effects=0;
const hooks={...React,useEffect:()=>{effects++;},useCallback:f=>f,useState:v=>[typeof v==='function'?v():v,()=>{}]};
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/PppoeObservations.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const {PppoeObservations,PppoeObservationState,validPppoeSnapshot}=module.exports;
const data={router_id:'registered-fixture',availability:'AVAILABLE',items:[{account_id:'a',source:'LOCAL',connected:null,ip_address:null},{account_id:'b',source:'RADIUS',connected:false,ip_address:'192.0.2.2'}],error:null,is_demo:false,read_only:true};
const view=props=>renderToStaticMarkup(React.createElement(PppoeObservationState,{routerId:data.router_id,data,loading:false,retry:()=>{},...props}));
test('demo and missing router never mount request lifecycle; observation time stays unknown',()=>{
 for(const props of [{isDemo:true,routerId:'demo-router-fixture'},{isDemo:false}]){
  const html=renderToStaticMarkup(React.createElement(PppoeObservations,props));assert.match(html,/Son veri zamanı: Bilinmiyor/);
 }
 assert.equal(effects,0);
});
test('authority and unknown session are shown independently with account filtering',()=>{
 const html=view({});assert.match(html,/LOCAL/);assert.match(html,/RADIUS/);assert.match(html,/Bilinmiyor/);assert.match(html,/Bağlı değil/);
 const scoped=view({accountId:'a',source:'LOCAL'});assert.doesNotMatch(scoped,/192.0.2.2|RADIUS/);
 assert.match(view({accountId:'a',source:'RADIUS'}),/eşleşmiyor/);
 assert.match(view({accountId:'missing',source:'LOCAL'}),/Bu hesap için/);
});
test('loading, empty, transport and disabled states hide stale rows and raw errors',()=>{
 assert.match(view({loading:true}),/yükleniyor/);assert.doesNotMatch(view({loading:true}),/192.0.2.2/);
 assert.match(view({data:{...data,items:[]}}),/listesi boş/);
 const error=view({error:'secret raw failure'});assert.match(error,/role="alert"/);assert.doesNotMatch(error,/secret|192.0.2.2/);
 for(const code of ['DISABLED','DEMO_ISOLATED','TIMEOUT','CONNECTION_FAILED','INVALID_DATA','AUTHORITY_MISMATCH']){
  const html=view({data:{...data,items:[],availability:'UNAVAILABLE',error:code}});assert.doesNotMatch(html,/undefined|192.0.2.2/);assert.match(html,/role="status"/);
 }
});
test('wrong router, demo, write flag and invalid authority fail closed',()=>{
 for(const patch of [{router_id:'other'},{is_demo:true},{read_only:false},{items:[{...data.items[0],source:'UNKNOWN'}]},{items:[data.items[0],data.items[0]]}]){
  assert.equal(validPppoeSnapshot({...data,...patch},data.router_id),false);
  assert.match(view({data:{...data,...patch}}),/yanıtı doğrulanamadı/);
 }
});
