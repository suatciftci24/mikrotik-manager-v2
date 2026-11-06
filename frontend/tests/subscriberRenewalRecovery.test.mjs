import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {turkeyToday} from '../src/lib/expiry.ts';

const require=createRequire(import.meta.url);
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberRenewal.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
for(const fault of ['lost-response','truncated-json','wrong-account','wrong-expiry','wrong-source','wrong-revision']){
 test(`renewal ${fault}: uncertain until matching result, identical retry after props refresh`,async()=>{
  const slots=[];let cursor=0;
  const hooks={...React,useEffect(){},useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return[slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
  const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
  const original={id:'demo-managed-sub-recovery',customer_name:'Synthetic',username:'synthetic.test',source:'RADIUS',plan:'Demo',revision:4,expires_on:turkeyToday(),status:'ACTIVE'};
  let item={...original};const calls=[],events=[],receipts=new Map();let applies=0;
  const render=()=>{cursor=0;return module.exports.SubscriberRenewal({item,onClose(){}});};
  const oldFetch=globalThis.fetch,oldWindow=globalThis.window;
  globalThis.window={dispatchEvent:event=>events.push(event)};
  globalThis.fetch=async(url,init)=>{
   assert.equal(url,'/api/v1/subscriber-workspace/'+original.id+'/renew');
   assert.equal(init.method,'POST');
   calls.push(init.body);const command=JSON.parse(init.body);
   if(!receipts.has(command.request_id)){
    applies++;receipts.set(command.request_id,{...original,revision:original.revision+1,expires_on:command.expires_on});
   }
   const saved=receipts.get(command.request_id);
   if(calls.length===1){
    if(fault==='lost-response')throw new TypeError('Synthetic response lost');
    if(fault==='truncated-json')return {ok:true,json:async()=>{throw new SyntaxError('Synthetic JSON failure');}};
    const field={'wrong-account':{id:'demo-managed-sub-other'},'wrong-expiry':{expires_on:original.expires_on},'wrong-source':{source:'LOCAL'},'wrong-revision':{revision:original.revision}}[fault];
    return {ok:true,json:async()=>({...saved,...field})};
   }
   return {ok:true,json:async()=>saved};
  };
  try{
   let tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
   assert.equal(calls.length,0);
   tree=render();const apply=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula');
   apply.props.onClick();apply.props.onClick();await new Promise(setImmediate);
   tree=render();let html=renderToStaticMarkup(tree);
   assert.match(html,/İşlem uygulanmış olabilir/);assert.doesNotMatch(html,/Kaydedildi · Güncel bitiş/);
   assert.equal(calls.length,1,'no automatic or concurrent duplicate request');
   assert.equal(events.filter(e=>e.type==='v2-resource-change').length,1);
   for(const prefix of ['/subscriber-workspace','/subscribers','/router-center','/router-workspace/routers'])assert.ok(events[0].detail.includes(prefix));
   item={...original,revision:9,source:'LOCAL',expires_on:'2099-12-31'};
   tree=render();nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı istekle sonucu getir').props.onClick();await new Promise(setImmediate);
   tree=render();html=renderToStaticMarkup(tree);
   assert.equal(calls.length,2);assert.equal(calls[0],calls[1]);assert.equal(applies,1);
   assert.equal(JSON.parse(calls[1]).expected_revision,original.revision);
   assert.equal(JSON.parse(calls[1]).expected_source,original.source);
   assert.match(html,/Kaydedildi · Güncel bitiş/);assert.doesNotMatch(html,/İşlem uygulanmış olabilir/);
   assert.equal(events.filter(e=>e.type==='v2-resource-change').length,2);
   assert.equal(nodes(tree).some(n=>n.type==='button'&&n.props.className==='button-primary'),false);
  }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
 });
}
