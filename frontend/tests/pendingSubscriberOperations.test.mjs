import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
const code=buildSync({entryPoints:['src/lib/pendingSubscriberOperations.ts'],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text;
function setup(){
 const values={};globalThis.localStorage={getItem:k=>values[k]??null,setItem(k,v){values[k]=v;this[k]=v;},removeItem(k){delete values[k];delete this[k];}};
 globalThis.window={dispatchEvent(){}};
 const mod={exports:{}};new Function('module','exports',code)(mod,mod.exports);return mod.exports;
}
const id='12345678-1234-4234-8234-123456789abc';
const user={id:'actor-a',role_code:'ADMIN',active:true,permissions:{}};
const path='/subscriber-workspace/requests/'+id;
test('minimal metadata survives reopening; all four paths restore with GET only and terminal cleanup',async()=>{
 for(const [kind,path] of [['save','/subscriber-workspace/requests/'],['legacy','/subscribers/demo-requests/'],['renew','/subscriber-workspace/renewals/requests/'],['bulk','/subscriber-workspace/management/requests/']]){
  const m=setup();m.pendingIdentity(user);m.rememberPending(id,path+id);
  const item=m.pendingOperations()[0];assert.deepEqual(Object.keys(item).sort(),['actor','created','id','kind']);assert.equal(item.kind,kind);
  const reopened={exports:{}};new Function('module','exports',code)(reopened,reopened.exports);const n=reopened.exports;n.pendingIdentity(user);
  const calls=[];const result=await n.recoverPending(n.pendingOperations()[0],new AbortController().signal,async(p,init)=>{calls.push(p);assert.equal(init.method,undefined);assert.equal(init.body,undefined);return p==='/auth/me'?user:{request_id:id,status:'SUCCESS',response:kind==='legacy'?{item:{id:'subscriber'}}:kind==='bulk'?{request_id:id,actor_id:user.id,recorded:true,success:true}:{id:'subscriber'}};});
  assert.equal(result,'SUCCESS');assert.deepEqual(calls,['/auth/me',path+id,'/auth/me']);assert.equal(n.pendingOperations().length,0);
 }
});
test('foreign actor, logout and permission loss purge records without querying',async()=>{
 for(const next of [{...user,id:'actor-b'},null,{...user,role_code:'VIEWER'},{...user,active:false}]){
  const m=setup();m.pendingIdentity(user);m.rememberPending(id,path);const item=m.pendingOperations()[0];m.pendingIdentity(next);
  assert.equal(m.pendingOperations().length,0);assert.equal(await m.recoverPending(item,new AbortController().signal,()=>{throw Error('must not query');}),'DENIED');
 }
});
test('current server identity checked before receipt; late response discarded on actor change',async()=>{
 const m=setup();m.pendingIdentity(user);m.rememberPending(id,path);const item=m.pendingOperations()[0];const calls=[];
 assert.equal(await m.recoverPending(item,new AbortController().signal,async p=>{calls.push(p);return {...user,id:'other'};}),'DENIED');assert.deepEqual(calls,['/auth/me']);
 m.pendingIdentity(user);m.rememberPending(id,path);
 assert.equal(await m.recoverPending(m.pendingOperations()[0],new AbortController().signal,async p=>{if(p==='/auth/me')return user;m.pendingIdentity(null);return {request_id:id,status:'SUCCESS',response:{id:'subscriber'}};}),'DENIED');
});
test('malformed, expired, future and extra sensitive fields are removed; disabled storage tolerated',()=>{
 const m=setup();for(const value of ['broken',JSON.stringify({actor:user.id,id,kind:'save',created:0}),JSON.stringify({actor:user.id,id,kind:'save',created:Date.now()+120000}),JSON.stringify({actor:user.id,id,kind:'save',created:Date.now(),password:'forbidden'})]){
 localStorage.setItem(m.pendingPrefix+id,value);assert.deepEqual(m.pendingOperations(),[]);assert.equal(localStorage.getItem(m.pendingPrefix+id),null);
 }
 globalThis.localStorage={getItem(){throw Error();},setItem(){throw Error();},removeItem(){throw Error();}};m.pendingIdentity(user);assert.doesNotThrow(()=>m.rememberPending(id,path));
});
test('unknown and mismatched receipt remain pending; independent tab entries never overwrite or resurrect removed entries',async()=>{
 const m=setup();m.pendingIdentity(user);m.rememberPending(id,path);const second='22345678-1234-4234-8234-123456789abc';m.rememberPending(second,'/subscriber-workspace/requests/'+second);assert.equal(m.pendingOperations().length,2);
 const item=m.pendingOperations()[0];assert.equal(await m.recoverPending(item,new AbortController().signal,async p=>p==='/auth/me'?user:{request_id:second,status:'SUCCESS',response:{id:'subscriber'}}),'UNKNOWN');assert.equal(m.pendingOperations().length,2);
 m.forgetPending(id);assert.deepEqual(m.pendingOperations().map(i=>i.id),[second]);
});
test('router permission changes invalidate pending UUIDs and abort prevents any GET',async()=>{
 const m=setup();const scoped={...user,permissions:{router:{can_manage_pppoe:true}}};m.pendingIdentity(scoped);m.rememberPending(id,path);m.pendingIdentity({...scoped,permissions:{router:{can_manage_pppoe:false}}});assert.equal(m.pendingOperations().length,0);
 m.rememberPending(id,path);const controller=new AbortController();controller.abort();assert.equal(await m.recoverPending(m.pendingOperations()[0],controller.signal,()=>{throw Error('no GET');}),'DENIED');
});
test('save hook journals UUID before POST, retains uncertainty and removes only confirmed outcome',async()=>{
 const {createRequire}=await import('node:module');const require=createRequire(import.meta.url);const React=require('react');
 const source=buildSync({stdin:{contents:"export * from './src/lib/useSubscriberSave';export * from './src/lib/pendingSubscriberOperations';",resolveDir:process.cwd(),loader:'ts'},bundle:true,write:false,platform:'node',format:'cjs',external:['react']}).outputFiles[0].text;
 setup();const slots=[];let cursor=0;const hooks={...React,useEffect(){},useRef:value=>{const i=cursor++;return slots[i]??=( {current:value});},useState:value=>{const i=cursor++;if(!(i in slots))slots[i]=value;return [slots[i],v=>{slots[i]=v;}];}};
 const mod={exports:{}};new Function('require','module','exports',source)(name=>name==='react'?hooks:require(name),mod,mod.exports);const m=mod.exports;m.pendingIdentity(user);
 const saved=[];const render=()=>{cursor=0;return m.useSubscriberSave(v=>saved.push(v));};const calls=[];const oldFetch=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push(init.method??'GET');assert.equal(m.pendingOperations()[0].id,id);if(init.method==='POST')throw Error('lost');return {ok:true,json:async()=>({request_id:id,status:'SUCCESS',response:{id:'subscriber'}})};};
 try{
  const attempt={requestId:id,path:'/subscriber-workspace',resultPath:path,body:JSON.stringify({password:'never-store',customer_name:'private'}),header:'subscriber-workspace',matches:r=>r.id==='subscriber'};
  await render().send(attempt);assert.equal(render().uncertain,true);assert.equal(m.pendingOperations().length,1);assert.ok(!JSON.stringify(m.pendingOperations()).includes('private'));
  await render().send(attempt);assert.deepEqual(calls,['POST','GET']);assert.equal(m.pendingOperations().length,0);assert.equal(saved.length,1);
 }finally{globalThis.fetch=oldFetch;}
});
