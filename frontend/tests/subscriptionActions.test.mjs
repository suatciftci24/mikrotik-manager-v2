import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expiryDate} from '../src/lib/expiry.ts';
const require=createRequire(import.meta.url);
const row={id:'demo-sub-fixture',username:'test.ev',customer_name:'Test User',router_id:'demo-router-001',router_name:'Merkez',source:'LOCAL',plan:'Demo',status:'ACTIVE',expires_on:'2026-10-01',revision:1,is_demo:true,can_manage_pppoe:true,monthly_price:10};
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('quick preview keeps old/new date and success receipt shows server date; completed retry is disabled',async()=>{
 const slots=[];let cursor=0,saves=0;const calls=[];
 const hooks={...React,useId:()=>':quick:',useEffect:()=>{},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:value.path==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans:[]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/QuickActions.tsx',import.meta.url))],bundle:true,loader:{'.css':'empty'},write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?hooks:require(name),module,module.exports);
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});const requested=JSON.parse(init.body).entries[0].change;return {ok:true,json:async()=>({results:[{item_id:row.id,success:true,result:{item:{...row,revision:row.revision+1,expires_on:requested.expires_on},history:[{id:requested.request_id,actor_id:'actor',is_demo:true,source:row.source,operation:'RENEWAL',occurred_at:new Date().toISOString()}],is_demo:true,persistence:'local-postgresql-demo'}}]})};};
 const render=()=>{cursor=0;return module.exports.QuickActions({rows:[row],today:'2026-10-28',onClose:()=>{},onSaved:()=>{saves++;}});};
 try{
  let tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();
  const html=renderToStaticMarkup(tree);assert.ok(html.includes(expiryDate(row.expires_on)));assert.match(html,/Eski → Yeni/);
  await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();tree=render();
  const receipt=renderToStaticMarkup(tree);assert.ok(receipt.includes(expiryDate(JSON.parse(calls[0].init.body).entries[0].change.expires_on)));assert.match(receipt,/İşlemde kaydedilen bitiş/);assert.equal(saves,1);
  const completed=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Sonuçlar doğrulandı');assert.equal(completed.props.disabled,true);await completed.props.onClick();assert.equal(calls.length,1);
  const payload=JSON.parse(calls[0].init.body);assert.equal(payload.entries[0].change.expected_expires_on,row.expires_on);assert.equal(payload.entries[0].change.router_id,row.router_id);assert.equal(payload.entries[0].change.action,'EXTEND');assert.equal(payload.entries[0].change.confirmed,true);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});

test('persistent renewal preserves request ID and reads the committed receipt without a second POST',async()=>{
 const slots=[];let cursor=0;const calls=[];
 const item={...row,id:'demo-managed-sub-fixture',router_id:'demo-managed-router-fixture',router_source:'PERSISTENT_DEMO',access_type:'HOTSPOT',ip_address:null,last_seen_at:null,last_connected_at:null,session_status:'UNKNOWN'};
 const hooks={...React,useEffect:()=>{},useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberRenewal.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?hooks:require(name),module,module.exports);
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});if(calls.length===1)throw Error('Yanıt kayboldu');const command=JSON.parse(calls[0].init.body);return {ok:true,json:async()=>({request_id:command.request_id,status:'SUCCESS',response:{...item,expires_on:command.expires_on,revision:2}})};};
 const render=()=>{cursor=0;return module.exports.SubscriberRenewal({item,onClose:()=>{}});};
 try{
  let tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();assert.match(renderToStaticMarkup(tree),/Eski → Yeni/);
  await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();await new Promise(setImmediate);tree=render();await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı UUID ile sonucu sorgula').props.onClick();await new Promise(setImmediate);tree=render();
  const command=JSON.parse(calls[0].init.body);assert.equal(calls.length,2);assert.equal(calls[0].init.method,'POST');assert.equal(calls[1].init.method,undefined);assert.equal(calls[1].init.body,undefined);assert.equal(calls[1].url,'/api/v1/subscriber-workspace/renewals/requests/'+command.request_id);assert.match(calls[0].url,/subscriber-workspace\/demo-managed-sub-fixture\/renew$/);assert.ok(renderToStaticMarkup(tree).includes(expiryDate(command.expires_on)));assert.equal(nodes(tree).some(n=>n.type==='button'&&n.props.children==='Onayla ve uygula'),false);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});

const validationCode=buildSync({stdin:{contents:"export {QuickActions} from './src/components/QuickActions';export {pendingQuickActionRequests} from './src/lib/quickActionRequests';",resolveDir:process.cwd(),loader:'tsx'},bundle:true,loader:{'.css':'empty'},write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
for(const action of ['EXTEND','PLAN','STATUS','CREATE'])test(`${action}: mismatched success never notifies; same frozen command recovers once`,async()=>{
 const slots=[];let cursor=0,notifications=0;const calls=[];
 const plans=[{name:'Demo',monthly_price:10},{name:'New',monthly_price:20}];
 const hooks={...React,useId:()=>':validation:',useEffect(){},useCallback:fn=>fn,useRef:value=>{const i=cursor++;return slots[i]??={current:value};},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:value.path==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans}},()=>{}];return[value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const module={exports:{}};new Function('require','module','exports',validationCode)(name=>name==='react'?hooks:require(name),module,module.exports);
 const render=()=>{cursor=0;return module.exports.QuickActions({rows:action==='CREATE'?[]:[row],today:'2026-10-28',initialAction:action,onClose(){},onSaved(){notifications++;}});};
 const change=(predicate,value)=>nodes(render()).find(predicate).props.onChange({target:{value}});
 if(action==='PLAN'||action==='CREATE')change(n=>n.type==='select'&&n.props['aria-labelledby']?.endsWith('-plan'),'New');
 if(action==='STATUS')change(n=>n.type==='select'&&n.props['aria-labelledby']?.endsWith('-status'),'PAUSED');
 if(action==='CREATE'){
  change(n=>n.type==='select'&&nodes(n).some(o=>o.type==='option'&&o.props.children===row.router_name),row.router_name);
  change(n=>n.type==='input'&&n.props.maxLength===80,'new.synthetic');change(n=>n.type==='input'&&n.props.maxLength===120,'New Synthetic');change(n=>n.type==='input'&&n.props.type==='date','2026-12-01');
 }
 nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
 let saved;const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent(){}};
 const faults=[{revision:99},{router_id:'other'},{source:'RADIUS'},{expires_on:'2000-01-01'},{plan:'Unexpected'},{status:'PENDING'},{monthly_price:999},{is_demo:false},{username:'other'}];let faultIndex=0;
 let entry,command;
 globalThis.fetch=async(url,init)=>{calls.push({body:init.body,method:init.method??'GET'});
  if(init.method==='POST'){entry=JSON.parse(init.body).entries[0];command=entry.change;}
  saved={...row,id:entry.item_id,revision:command.expected_revision+1,router_id:command.router_id,source:command.expected_source,expires_on:command.expires_on,...(action==='CREATE'?{username:command.username,customer_name:command.customer_name}:{}),...(['PLAN','CREATE'].includes(action)?{plan:'New',monthly_price:20}:{}),...(['STATUS','CREATE'].includes(action)?{status:command.status}:{})};
  const data={is_demo:true,persistence:'local-postgresql-demo',history:[{id:command.request_id,actor_id:'actor',is_demo:true,source:saved.source,operation:{EXTEND:'RENEWAL',PLAN:'PLAN_CHANGE',STATUS:'STATUS_CHANGE',CREATE:'CREATE'}[action],occurred_at:new Date().toISOString()}],item:faultIndex<faults.length?{...saved,...faults[faultIndex]}:saved};
  return {ok:true,json:async()=>init.method==='POST'?{results:[{item_id:entry.item_id,success:true,result:data}]}:{request_id:command.request_id,status:'SUCCESS',response:data}};
 };
 try{
  for(;faultIndex<faults.length;faultIndex++){
   const click=nodes(render()).find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick;await Promise.all([click(),click()]);assert.equal(calls.length,faultIndex+1,'concurrent confirmation never starts another POST');
   assert.equal(notifications,0);const html=renderToStaticMarkup(render());assert.match(html,/doğrulanamadı/);assert.doesNotMatch(html,/Kaydedildi · Güncel/);
  }
  await nodes(render()).find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick();
  assert.equal(notifications,1);assert.equal(calls.filter(c=>c.method==='POST').length,1);assert.ok(calls.slice(1).every(c=>c.method==='GET'&&c.body===undefined));assert.match(renderToStaticMarkup(render()),/Sonuçlar doğrulandı/);
  await nodes(render()).find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick();assert.equal(calls.length,faults.length+1);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});

for(const scenario of ['timeout','rejected'])test(`quick ${scenario}: persisted UUID reconciles by GET, with terminal failure separate from uncertainty`,async()=>{
 const slots=[];let cursor=0,saved=0,timeout;const calls=[],events=[];
 const hooks={...React,useId:()=>':reconcile:',useEffect(){},useCallback:fn=>fn,useRef:value=>{const i=cursor++;return slots[i]??={current:value};},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:value.path==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans:[]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const module={exports:{}};new Function('require','module','exports',validationCode)(name=>name==='react'?hooks:require(name),module,module.exports);
 const before={fetch:globalThis.fetch,window:globalThis.window,localStorage:globalThis.localStorage,setTimeout:globalThis.setTimeout,clearTimeout:globalThis.clearTimeout};
 const values={};globalThis.localStorage={getItem:k=>values[k]??null,setItem(k,v){values[k]=v;this[k]=v;},removeItem(k){delete values[k];delete this[k];}};globalThis.window={dispatchEvent:event=>events.push(event)};
 globalThis.setTimeout=fn=>{timeout=fn;return 1;};globalThis.clearTimeout=()=>{};
 let entry;globalThis.fetch=async(url,init)=>{calls.push(init.method??'GET');
  if(init.method==='POST'){entry=JSON.parse(init.body).entries[0];if(scenario==='rejected')return {ok:true,json:async()=>({results:[{item_id:row.id,success:false,status:409,error:'Kayıt revizyonu değişti.'}]})};return new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new DOMException('Timeout','AbortError'))));}
  assert.equal(init.body,undefined);assert.ok(url.endsWith(entry.change.request_id));if(calls.length===2)return {ok:true,json:async()=>({request_id:entry.change.request_id,status:'UNKNOWN',response:null})};
  return {ok:true,json:async()=>({request_id:entry.change.request_id,status:'SUCCESS',response:{is_demo:true,persistence:'local-postgresql-demo',item:{...row,revision:row.revision+1,expires_on:entry.change.expires_on},history:[{id:entry.change.request_id,actor_id:'actor',source:row.source,is_demo:true,operation:'RENEWAL',occurred_at:new Date().toISOString()}]}})};
 };
 const render=()=>{cursor=0;return module.exports.QuickActions({rows:[row],today:'2026-10-28',onClose(){},onSaved(){saved++;}});};
 const click=()=>nodes(render()).find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick();
 try{
  nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});const request=click();if(scenario==='timeout')timeout();await request;
  assert.equal(saved,0);assert.equal(calls.length,1);
  if(scenario==='rejected'){assert.equal(module.exports.pendingQuickActionRequests().length,0);assert.match(renderToStaticMarkup(render()),/1 başarısız \/ 0 belirsiz/);await click();assert.equal(calls.length,1);}
  else{assert.equal(module.exports.pendingQuickActionRequests().length,1);assert.deepEqual(Object.keys(module.exports.pendingQuickActionRequests()[0]).sort(),['action','itemId','requestId']);await click();assert.equal(saved,0);assert.equal(module.exports.pendingQuickActionRequests().length,1);assert.match(renderToStaticMarkup(render()),/0 başarısız \/ 1 belirsiz/);await click();assert.equal(saved,1);assert.equal(module.exports.pendingQuickActionRequests().length,0);assert.deepEqual(calls,['POST','GET','GET']);for(const prefix of ['/subscribers','/subscriber-center','/dashboard','/reports'])assert.ok(events.filter(e=>e.type==='v2-resource-change').at(-1).detail.includes(prefix));}
 }finally{Object.assign(globalThis,before);}
});
