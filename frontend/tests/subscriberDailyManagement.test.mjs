import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {dailyEntries} from '../src/lib/subscriberManagementCenter.ts';
const item={id:'demo-managed-sub-fixture',username:'one.test',customer_name:'One User',router_id:'demo-managed-router-fixture',router_name:'One Router',router_source:'PERSISTENT_DEMO',access_type:'PPPOE',source:'LOCAL',status:'PAUSED',plan:'Demo 100',expires_on:'2026-11-01',revision:1,router_missing:false,session_status:'UNKNOWN'};
const rows=[item,{...item,id:'demo-managed-sub-other',router_id:'demo-managed-router-other',router_name:'Other Router',username:'two.test',access_type:'HOTSPOT'}];
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('shared preview supports 30/60/90, cross-router batches and rejects live/read-only records',()=>{
 for(const days of [30,60,90]){const entries=dailyEntries(rows,'EXTEND','',days,'2026-10-29',()=>crypto.randomUUID());assert.equal(entries.length,2);assert.equal(entries[1].expected_router_id,rows[1].router_id);assert.equal(entries[0].days,days);assert.equal(entries[0].confirmed,true);}
 for(const change of [{id:'registered-test'},{router_source:'UNKNOWN'},{router_missing:true},{source:null}])assert.throws(()=>dailyEntries([{...item,...change}],'STATUS','ACTIVE',30,'2026-10-29',()=>''));
 assert.throws(()=>dailyEntries(rows,'PLAN','New Plan',30,'2026-10-29',()=>''));
 assert.throws(()=>dailyEntries([{...item,expires_on:null}],'EXTEND','',30,'2026-10-29',()=>''));
});
test('bulk preview requires explicit consent and preserves request IDs for mixed-result retries',async()=>{
 const require=createRequire(import.meta.url),slots=[];let cursor=0;const calls=[];
 const hooks={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:{items:[]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberDailyActions.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});const entries=JSON.parse(init.body).entries;return {ok:true,json:async()=>({results:entries.map((e,i)=>({item_id:e.item_id,request_id:e.request_id,success:i===0,recorded:true,values:{expires_on:e.value},occurred_at:'2026-10-29T12:00:00Z',error:i?'Revizyon değişti':null}))})};};
 const render=()=>{cursor=0;return module.exports.SubscriberDailyActions({rows,onClose:()=>{}});};
 try{
  let tree=render();assert.match(renderToStaticMarkup(tree),/2 seçili abone/);nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();assert.equal(calls.length,0);
  let button=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula');assert.equal(button.props.disabled,true);
  nodes(tree).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});tree=render();nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();await new Promise(setImmediate);tree=render();
  assert.match(renderToStaticMarkup(tree),/Başarılı: 1/);assert.match(renderToStaticMarkup(tree),/Başarısız: 1/);assert.match(renderToStaticMarkup(tree),/Revizyon değişti/);
  nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı isteğin kayıtlı sonuçlarını getir').props.onClick();await new Promise(setImmediate);assert.equal(calls.length,2);assert.equal(calls[0].init.body,calls[1].init.body);assert.match(calls[0].url,/management\/execute$/);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});
