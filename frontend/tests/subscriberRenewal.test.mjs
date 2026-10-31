import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {turkeyToday} from '../src/lib/expiry.ts';
const require=createRequire(import.meta.url);
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('renewal validates date, previews without writing and retries the identical confirmation',async()=>{
 const slots=[];let cursor=0;const calls=[];
 const hooks={...React,useEffect(){},useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return[slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const code=buildSync({entryPoints:['src/components/SubscriberRenewal.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 const today=turkeyToday(),item={id:'demo-managed-sub-fixture',customer_name:'Sentetik',username:'demo',source:'RADIUS',revision:1,expires_on:today,status:'ACTIVE'};
 const render=()=>{cursor=0;return nodes(module.exports.SubscriberRenewal({item,onClose(){}}));};
 const originalFetch=globalThis.fetch,originalWindow=globalThis.window;globalThis.window={dispatchEvent(){}};
 globalThis.fetch=async(url,init)=>{calls.push({url,body:JSON.parse(init.body)});if(calls.length===1)throw Error('Yanıt kayboldu');return{ok:true,json:async()=>({...item,expires_on:calls[0].body.expires_on})};};
 try{
  let tree=render();tree.find(n=>n.type==='select').props.onChange({target:{value:'CUSTOM'}});
  tree=render();tree.find(n=>n.type==='input').props.onChange({target:{value:today}});
  tree=render();tree.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
  assert.equal(calls.length,0);assert.ok(render().some(n=>n.props?.role==='alert'));
  tree=render();tree.find(n=>n.type==='select').props.onChange({target:{value:'30'}});
  tree=render();tree.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(calls.length,0);
  tree=render();await tree.find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick();await new Promise(resolve=>setImmediate(resolve));
  tree=render();await tree.find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,2);assert.deepEqual(calls[0],calls[1]);assert.equal(calls[0].body.confirmed,true);assert.equal(calls[0].body.expected_source,'RADIUS');
  assert.ok(render().some(n=>n.props?.role==='status'));
 }finally{globalThis.fetch=originalFetch;globalThis.window=originalWindow;}
});
