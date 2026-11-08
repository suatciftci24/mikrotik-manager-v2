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
function proof(kind){
 const account={is_demo:true,id:kind==='legacy'?'demo-sub-fixture':'demo-managed-sub-fixture',revision:1,source:'LOCAL',router_id:'demo-managed-router-fixture',router_source:'PERSISTENT_DEMO',username:'synthetic',plan:'Plan',status:'ACTIVE',expires_on:'2027-01-01',session_status:'UNKNOWN'};
 const audit={id,actor_id:user.id,is_demo:true,source:'LOCAL',operation:kind==='renew'?'RENEWAL':kind==='bulk'?'STATUS':'CREATE',occurred_at:'2026-11-08T12:00:00Z',revision:1,result:'APPLIED'};
 const legacy={is_demo:true,persistence:'local-postgresql-demo',item:account,history:[audit]};
 const center={is_demo:true,persistence:'local-postgresql-workspace',source:'PERSISTENT_WORKSPACE',device_connection_started:false,item:account,history:[audit]};
 return {audit:{request_id:id,item_id:account.id,actor_id:user.id,router_id:account.router_id,source:account.source,revision:account.revision,operation:audit.operation,occurred_at:audit.occurred_at,success:true,storage:'PERSISTENT_WORKSPACE',is_demo:true},response:kind==='legacy'?legacy:kind==='bulk'?{request_id:id,item_id:account.id,router_id:account.router_id,actor_id:user.id,recorded:true,success:true,revision:1,operation:'STATUS',values:{status:'ACTIVE'},occurred_at:audit.occurred_at}:account,current:structuredClone(kind==='legacy'?legacy:center),detailPath:(kind==='legacy'?'/subscribers/':'/subscriber-center/')+account.id};
}
test('minimal metadata survives reopening; all four paths restore with GET only and terminal cleanup',async()=>{
 for(const [kind,path] of [['save','/subscriber-workspace/requests/'],['legacy','/subscribers/demo-requests/'],['renew','/subscriber-workspace/renewals/requests/'],['bulk','/subscriber-workspace/management/requests/']]){
  const m=setup();m.pendingIdentity(user);m.rememberPending(id,path+id);
  const item=m.pendingOperations()[0];assert.deepEqual(Object.keys(item).sort(),['actor','created','id','kind']);assert.equal(item.kind,kind);
  const reopened={exports:{}};new Function('module','exports',code)(reopened,reopened.exports);const n=reopened.exports;n.pendingIdentity(user);
  const calls=[],evidence=proof(kind);const result=await n.recoverPending(n.pendingOperations()[0],new AbortController().signal,async(p,init)=>{calls.push(p);assert.equal(init.method,undefined);assert.equal(init.body,undefined);return p==='/auth/me'?user:p===evidence.detailPath?evidence.current:{request_id:id,status:'SUCCESS',response:evidence.response,audit:evidence.audit};});
  assert.equal(result,'SUCCESS',kind);assert.deepEqual(calls,['/auth/me',path+id,evidence.detailPath,'/auth/me']);assert.equal(n.pendingOperations().length,0);
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

test('reload reconciliation rejects malformed receipts, missing audit and stale current revision; never writes',async()=>{
 for(const kind of ['save','renew','legacy','bulk'])for(const fault of ['malformed','missing-audit','wrong-actor','older-current','same-revision-drift']){
  const m=setup();m.pendingIdentity(user);const prefix={save:'/subscriber-workspace/requests/',renew:'/subscriber-workspace/renewals/requests/',legacy:'/subscribers/demo-requests/',bulk:'/subscriber-workspace/management/requests/'}[kind];m.rememberPending(id,prefix+id);
  const evidence=proof(kind);if(fault==='malformed')evidence.response={id:'anything'};
  if(fault==='missing-audit'){if(kind==='legacy')evidence.response.history=[];else delete evidence.audit;}
  if(fault==='wrong-actor'){if(kind==='legacy')evidence.response.history[0].actor_id='other';else evidence.audit.actor_id='other';}
  if(fault==='older-current')evidence.current.item={...evidence.current.item,revision:0};
  if(fault==='same-revision-drift')evidence.current.item={...evidence.current.item,status:'PAUSED'};
  const result=await m.recoverPending(m.pendingOperations()[0],new AbortController().signal,async(p,init)=>{assert.equal(init.method,undefined);assert.equal(init.body,undefined);return p==='/auth/me'?user:p===evidence.detailPath?evidence.current:{request_id:id,status:'SUCCESS',response:evidence.response,audit:evidence.audit};});
  assert.equal(result,'UNKNOWN',kind+' '+fault);assert.equal(m.pendingOperations().length,1);
 }
});
test('a later current revision can reconcile historical receipt without overwriting it',async()=>{
 const m=setup();m.pendingIdentity(user);m.rememberPending(id,path);const evidence=proof('save');
 evidence.current.item={...evidence.current.item,revision:60,plan:'Later plan'};evidence.current.history=Array.from({length:50},(_,index)=>({revision:index+11,actor_id:'later',operation:'UPDATE',result:'APPLIED'}));
 const result=await m.recoverPending(m.pendingOperations()[0],new AbortController().signal,async(p,init)=>{assert.equal(init.method,undefined);return p==='/auth/me'?user:p===evidence.detailPath?evidence.current:{request_id:id,status:'SUCCESS',response:evidence.response,audit:evidence.audit};});
 assert.equal(result,'SUCCESS');assert.equal(evidence.current.item.plan,'Later plan');assert.equal(m.pendingOperations().length,0);
});

test('exact UUID audit proof replaces last-50 history scanning and rejects every mismatched proof',async()=>{
 for(const kind of ['save','renew','bulk'])for(const [field,value] of [['request_id','wrong'],['item_id','other'],['router_id','demo-managed-router-other'],['source','RADIUS'],['revision',99],['storage','V1'],['is_demo',false]]){
  const m=setup();m.pendingIdentity(user);const prefix={save:'/subscriber-workspace/requests/',renew:'/subscriber-workspace/renewals/requests/',bulk:'/subscriber-workspace/management/requests/'}[kind];m.rememberPending(id,prefix+id);
  const evidence=proof(kind);evidence.audit[field]=value;evidence.current.history=[];
  const status=await m.recoverPending(m.pendingOperations()[0],new AbortController().signal,async(p,init)=>{assert.equal(init.method,undefined);return p==='/auth/me'?user:p===evidence.detailPath?evidence.current:{request_id:id,status:'SUCCESS',response:evidence.response,audit:evidence.audit};});
  assert.equal(status,'UNKNOWN',kind+' '+field);assert.equal(m.pendingOperations().length,1);
 }
 for(const kind of ['save','renew','bulk']){
  const m=setup();m.pendingIdentity(user);const prefix={save:'/subscriber-workspace/requests/',renew:'/subscriber-workspace/renewals/requests/',bulk:'/subscriber-workspace/management/requests/'}[kind];m.rememberPending(id,prefix+id);const evidence=proof(kind);evidence.current.item.revision=60;evidence.current.history=[];const calls=[];
  assert.equal(await m.recoverPending(m.pendingOperations()[0],new AbortController().signal,async(p,init)=>{calls.push(p);assert.equal(init.method,undefined);return p==='/auth/me'?user:p===evidence.detailPath?evidence.current:{request_id:id,status:'SUCCESS',response:evidence.response,audit:evidence.audit};}),'SUCCESS');
  assert.equal(calls.length,4);assert.equal(m.pendingOperations().length,0);
 }
});
test('missing or expired server receipt remains UNKNOWN with no re-execution',async()=>{
 const m=setup();m.pendingIdentity(user);m.rememberPending(id,path);const calls=[];
 assert.equal(await m.recoverPending(m.pendingOperations()[0],new AbortController().signal,async(p,init)=>{calls.push(p);assert.equal(init.method,undefined);assert.equal(init.body,undefined);return p==='/auth/me'?user:{request_id:id,status:'UNKNOWN',response:null,audit:null};}),'UNKNOWN');
 assert.equal(m.pendingOperations().length,1);assert.equal(calls.length,2);
});

test('expired tracking stays visibly UNKNOWN for this session, removes persisted metadata and never queries or posts',async()=>{
 const m=setup();m.pendingIdentity(user);localStorage.setItem(m.pendingPrefix+id,JSON.stringify({actor:user.id,id,kind:'save',created:Date.now()-m.pendingTTL-1}));
 const expired=m.pendingOperations()[0];assert.equal(expired.expired,true);assert.equal(localStorage.getItem(m.pendingPrefix+id),null);
 assert.equal(await m.recoverPending(expired,new AbortController().signal,()=>{throw Error('expired requests must not query');}),'UNKNOWN');assert.equal(m.pendingOperations().length,1);
 m.pendingIdentity(null);assert.equal(m.pendingOperations().length,0);
});
