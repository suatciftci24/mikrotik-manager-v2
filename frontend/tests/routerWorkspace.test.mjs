import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {applyTrustProfile} from '../src/lib/routerTrustProfiles.ts';
import {emptyRouterForm} from '../src/lib/routerRegistry.ts';

test('trust profile fills only matching target certificate material; no credentials or flags',()=>{
 const profile={id:'trust-profile-fixture',fields:{name:'Lab CA',management_address:'10.77.0.2',port:8729,ca_pem:'PUBLIC_CA',leaf_sha256:'a'.repeat(64)}};
 const form={...emptyRouterForm,username:'private-user',password:'PRIVATE_CANARY'};
 const value=applyTrustProfile(form,profile);
 assert.equal(value.management_address,profile.fields.management_address);assert.equal(value.ca_pem,'PUBLIC_CA');assert.equal(value.leaf_sha256,profile.fields.leaf_sha256);
 assert.equal(value.username,'private-user');assert.equal(value.password,'PRIVATE_CANARY');assert.equal('verify' in value,false);
 assert.throws(()=>applyTrustProfile({...form,management_address:'10.77.0.3'},profile),/farklı bir IP/);
});

test('synthetic form saves only workspace fields with explicit CSRF; delete requires confirmation',async()=>{
 const require=createRequire(import.meta.url),slots=[];let cursor=0;
 const react={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>{
  const index=cursor++;slots[index]??={current:value};return slots[index];
 },useState:initial=>{
  const index=cursor++;if(!(index in slots))slots[index]=typeof initial==='function'?initial():initial;
  const value=slots[index];
  if(value?.path)return [{...value,loading:false,data:{items:[],total:0}},()=>{}];
  return [value,next=>{slots[index]=typeof next==='function'?next(slots[index]):next;}];
 }};
 const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/DemoRouterWorkspace.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);
 const originalWindow=globalThis.window,originalFetch=globalThis.fetch;
 const calls=[];globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});const payload=JSON.parse(init.body);return {ok:true,json:async()=>({id:'demo-managed-router-fixture',revision:1,fields:payload.fields,kind:'DEMO_ROUTER',is_demo:true,device_connected:false})};};
 const render=()=>{cursor=0;return module.exports.DemoRouterWorkspace({});};
 const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
 const button=(tree,label)=>nodes(tree).find(n=>n.type==='button'&&n.props.children===label);
 try{
  let tree=render();assert.match(renderToStaticMarkup(tree),/SENTETİK DEMO/);button(tree,'Sentetik router ekle').props.onClick();
  tree=render();const inputs=nodes(nodes(tree).find(n=>n.type==='form')).filter(n=>n.type==='input');inputs.find(n=>n.props.value==='').props.onChange({target:{value:'Sentetik Test'}});
  tree=render();await nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/v1/router-workspace/routers');
  const payload=JSON.parse(calls[0].init.body);assert.equal(payload.confirmed,true);assert.equal(payload.fields.name,'Sentetik Test');assert.equal(payload.fields.management_address,'192.0.2.10');assert.equal(calls[0].init.headers['X-V2-Demo-Action'],'router-workspace');
  assert.equal('password' in payload.fields,false);assert.equal('ca_pem' in payload.fields,false);
  tree=render();assert.equal(button(tree,'Sentetik kaydı sil').props.disabled,true);
  assert.match(renderToStaticMarkup(tree),/Cihaz doğrulanmadı/);
 }finally{globalThis.window=originalWindow;globalThis.fetch=originalFetch;}
});
