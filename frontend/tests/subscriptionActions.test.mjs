import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expiryDate} from '../src/lib/expiry.ts';
const require=createRequire(import.meta.url);
const row={id:'demo-sub-fixture',username:'test.ev',customer_name:'Test User',router_id:'demo-router-001',router_name:'Merkez',source:'LOCAL',plan:'Demo',status:'ACTIVE',expires_on:'2026-10-01',revision:1,is_demo:true,monthly_price:10};
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('quick preview keeps old/new date and success receipt shows server date; completed retry is disabled',async()=>{
 const slots=[];let cursor=0,saves=0;const calls=[];
 const hooks={...React,useId:()=>':quick:',useEffect:()=>{},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:value.path==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans:[]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/QuickActions.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?hooks:require(name),module,module.exports);
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return {ok:true,json:async()=>({results:[{item_id:row.id,success:true,result:{item:{...row,expires_on:'2026-12-01'},history:[],is_demo:true,persistence:'local-postgresql-demo'}}]})};};
 const render=()=>{cursor=0;return module.exports.QuickActions({rows:[row],today:'2026-10-28',onClose:()=>{},onSaved:()=>{saves++;}});};
 try{
  let tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();
  const html=renderToStaticMarkup(tree);assert.ok(html.includes(expiryDate(row.expires_on)));assert.match(html,/Eski → Yeni/);
  await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();tree=render();
  const receipt=renderToStaticMarkup(tree);assert.ok(receipt.includes(expiryDate('2026-12-01')));assert.match(receipt,/Güncel bitiş/);assert.equal(saves,1);
  const completed=nodes(tree).find(n=>n.type==='button'&&n.props.children==='İşlem tamamlandı');assert.equal(completed.props.disabled,true);await completed.props.onClick();assert.equal(calls.length,1);
  const payload=JSON.parse(calls[0].init.body);assert.equal(payload.entries[0].change.expected_expires_on,row.expires_on);assert.equal(payload.entries[0].change.router_id,row.router_id);assert.equal(payload.entries[0].change.action,'EXTEND');assert.equal(payload.entries[0].change.confirmed,true);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});

test('persistent renewal preserves request ID on lost response and shows committed date on retry',async()=>{
 const slots=[];let cursor=0;const calls=[];
 const item={...row,id:'demo-managed-sub-fixture',router_id:'demo-managed-router-fixture',router_source:'PERSISTENT_DEMO',access_type:'HOTSPOT',ip_address:null,last_seen_at:null,last_connected_at:null,session_status:'UNKNOWN'};
 const hooks={...React,useEffect:()=>{},useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberRenewal.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?hooks:require(name),module,module.exports);
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});if(calls.length===1)throw Error('Yanıt kayboldu');return {ok:true,json:async()=>({...item,expires_on:'2027-03-01',revision:2})};};
 const render=()=>{cursor=0;return module.exports.SubscriberRenewal({item,onClose:()=>{}});};
 try{
  let tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();assert.match(renderToStaticMarkup(tree),/Eski → Yeni/);
  await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();await new Promise(setImmediate);tree=render();await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı istekle sonucu getir').props.onClick();await new Promise(setImmediate);tree=render();
  assert.equal(calls.length,2);assert.equal(calls[0].init.body,calls[1].init.body);assert.match(calls[0].url,/subscriber-workspace\/demo-managed-sub-fixture\/renew$/);assert.ok(renderToStaticMarkup(tree).includes(expiryDate('2027-03-01')));assert.equal(nodes(tree).some(n=>n.type==='button'&&n.props.children==='Onayla ve uygula'),false);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});
