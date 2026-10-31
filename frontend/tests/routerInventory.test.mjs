import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {registryStatus} from '../src/lib/routerRegistry.ts';
import {routerCenterStatus} from '../src/lib/routerCenter.ts';
const require=createRequire(import.meta.url);
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/RouterInventoryOnboarding.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
test('offline form submits inventory only, keeps request ID on retry and navigates after success',async()=>{
 let stateIndex=0,refIndex=0;const states=[{name:'SYNTHETIC_TOWERS',management_address:'10.77.0.3',port:'8729',credential_ref:'11111111-1111-4111-8111-111111111111',description:'Synthetic',site:'Lab',model:'Reported',routeros_version:'7'},true,false,''];const refs=[];
 const hooks={...React,useState:initial=>{const index=stateIndex++;return [states[index]??initial,value=>{states[index]=value;}];},useRef:initial=>{const index=refIndex++;return refs[index]??=({current:initial});}};
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 let opened=null;const render=()=>{stateIndex=0;refIndex=0;return module.exports.RouterInventoryOnboarding({onClose:()=>{},onSaved:id=>{opened=id;}});};
 const requests=[];const originalFetch=globalThis.fetch,originalWindow=globalThis.window;
 globalThis.window=new EventTarget();
 globalThis.fetch=async(path,init)=>{requests.push([path,init]);if(requests.length===1)throw new Error('Failed to fetch');return {ok:true,json:async()=>({item:{id:'registered-synthetic'}})};};
 try{
  const tree=render();const html=renderToStaticMarkup(tree);assert.match(html,/PENDING_VERIFICATION/);assert.doesNotMatch(html,/type="password"/);
  await nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
  // onSubmit schedules save; flush promises before retrying.
  await new Promise(resolve=>setImmediate(resolve));
  nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length,2);assert.equal(opened,'registered-synthetic');
  const [path,init]=requests[0];assert.equal(path,'/api/v1/router-registry/inventory');assert.equal(init.headers['X-V2-Demo-Action'],'router-onboarding');
  const payload=JSON.parse(init.body);assert.equal(payload.port,8729);assert.equal(payload.confirmed,true);assert.equal(payload.credential_ref,states[0].credential_ref);
  assert.equal(payload.request_id,JSON.parse(requests[1][1].body).request_id);
  for(const key of ['password','username','ca_pem','leaf_sha256','status'])assert.equal(key in payload,false);
 }finally{globalThis.fetch=originalFetch;globalThis.window=originalWindow;}
});
test('pending status is explicit in registry and center',()=>{
 assert.equal(registryStatus('PENDING_VERIFICATION'),'Doğrulama bekliyor');
 assert.match(routerCenterStatus({is_demo:false,item:{status:'PENDING_VERIFICATION'}}),/bağlantı izni yok/);
});
