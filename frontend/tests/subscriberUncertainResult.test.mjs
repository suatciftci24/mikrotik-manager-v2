import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require=createRequire(import.meta.url);
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberDailyActions.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const rows=[{id:'demo-managed-sub-uncertain',username:'synthetic.one',customer_name:'Synthetic One',router_id:'demo-managed-router-uncertain',router_name:'Synthetic Router',router_source:'PERSISTENT_DEMO',access_type:'PPPOE',source:'LOCAL',status:'PAUSED',plan:'Demo 100',expires_on:'2026-11-01',revision:1,router_missing:false,session_status:'UNKNOWN'}];

for(const fault of ['lost-response','truncated-json','wrong-receipt']){
 test(`${fault}: warn, refresh dependent views and retrieve same request without another apply`,async()=>{
  const slots=[];let cursor=0;
  const hooks={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:{items:[]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
  const module={exports:{}};
  new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
  const render=()=>{cursor=0;return module.exports.SubscriberDailyActions({rows,onClose:()=>{}});};
  const previousFetch=globalThis.fetch,previousWindow=globalThis.window;
  const calls=[],events=[],receipts=new Map();let applied=0;
  globalThis.window={dispatchEvent:event=>events.push(event)};
  globalThis.fetch=async(url,init)=>{
   assert.match(url,/\/subscriber-workspace\/management\/execute$/);
   assert.equal(init.method,'POST');
   calls.push(init.body);
   const {entries}=JSON.parse(init.body);
   const results=entries.map(e=>{
    if(!receipts.has(e.request_id)){
     applied++;
     receipts.set(e.request_id,{item_id:e.item_id,request_id:e.request_id,success:true,recorded:true,values:{expires_on:e.value},occurred_at:'2026-11-06T12:00:00Z',error:null});
    }
    return receipts.get(e.request_id);
   });
   if(calls.length===1){
    if(fault==='lost-response')throw new TypeError('Synthetic response lost');
    if(fault==='truncated-json')return {ok:true,json:async()=>{throw new SyntaxError('Synthetic truncated JSON');}};
    return {ok:true,json:async()=>({results:results.map(r=>({...r,item_id:'wrong-synthetic-item'}))})};
   }
   return {ok:true,json:async()=>({results})};
  };
  try{
   let tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
   tree=render();nodes(tree).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
   tree=render();nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();
   await new Promise(setImmediate);
   tree=render();let html=renderToStaticMarkup(tree);
   assert.match(html,/İşlem uygulanmış olabilir/);
   assert.doesNotMatch(html,/Başarılı:|Başarısız:/);
   const refreshes=events.filter(e=>e.type==='v2-resource-change');
   assert.equal(refreshes.length,1);
   for(const prefix of ['/subscriber-workspace','/subscribers','/router-center','/router-workspace/routers'])assert.ok(refreshes[0].detail.includes(prefix));
   assert.equal(calls.length,1,'no automatic retry');
   nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı isteğin kayıtlı sonuçlarını getir').props.onClick();
   await new Promise(setImmediate);
   tree=render();html=renderToStaticMarkup(tree);
   assert.equal(calls.length,2);assert.equal(calls[0],calls[1]);assert.equal(applied,1);
   assert.match(html,/Başarılı: 1/);assert.doesNotMatch(html,/İşlem uygulanmış olabilir/);
   assert.equal(events.filter(e=>e.type==='v2-resource-change').length,2);
  }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
 });
}
