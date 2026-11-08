import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const compile=name=>buildSync({entryPoints:[fileURLToPath(new URL('../src/'+name,import.meta.url))],bundle:true,loader:{'.css':'empty'},write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const codes={workspace:compile('components/SyntheticSubscribers.tsx'),legacy:compile('components/SubscriberEditor.tsx'),hook:compile('lib/useSubscriberSave.ts')};
const router='demo-managed-router-11111111-1111-4111-8111-111111111111';
function harness(kind,mode){
 const slots=[];let cursor=0;const events=[],saved=[];
 const options={routers:[{id:'demo-router-one',name:'Synthetic Router'}],plans:[{name:'Old',monthly_price:100},{name:'New',monthly_price:200}],persistence:'local-postgresql-demo',is_demo:true};
 const hooks={...React,useEffect(){},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:value.path.includes('demo-options')?options:{items:[{id:router,fields:{name:'Synthetic Router'}}]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const module={exports:{}};new Function('require','module','exports',codes[kind])(name=>name==='react'?hooks:require(name),module,module.exports);
 const original={id:kind==='workspace'?'demo-managed-sub-existing':'demo-sub-existing',customer_name:'Synthetic User',username:'synthetic.test',router_id:kind==='workspace'?router:'demo-router-one',router_name:'Synthetic Router',access_type:'PPPOE',source:'LOCAL',plan:'Old',status:'PAUSED',expires_on:null,revision:3,monthly_price:100,is_demo:true};
 let item={...original};
 const render=()=>{cursor=0;return kind==='hook'?module.exports.useSubscriberSave(value=>saved.push(value)):kind==='workspace'?module.exports.SyntheticSubscriberEditor({item:mode==='edit'?item:undefined,onClose(){},onSaved:id=>saved.push(id)}):module.exports.SubscriberEditor({mode:mode==='edit'?'PLAN_CHANGE':'CREATE',subscriber:mode==='edit'?item:undefined,onClose(){},onSaved:id=>saved.push(id)});};
 const control=(predicate,value)=>{const node=nodes(render()).find(predicate);assert.ok(node,'control exists');node.props.onChange({target:{value,checked:value}});};
 const prepare=()=>{
  if(kind==='workspace'){
   if(mode==='create'){
    control(n=>n.type==='input'&&n.props.maxLength===160,'Synthetic User');
    control(n=>n.type==='input'&&n.props.maxLength===96,'synthetic.test');
    control(n=>n.type==='select'&&nodes(n).some(o=>o.type==='option'&&o.props.value===router),router);
   }
   control(n=>n.type==='input'&&n.props.maxLength===120,'New');
  }else{
   if(mode==='create'){
    control(n=>n.type==='input'&&n.props.maxLength===160,'Synthetic User');
    control(n=>n.type==='input'&&n.props.maxLength===96,'synthetic.test');
    control(n=>n.type==='select'&&nodes(n).some(o=>o.type==='option'&&o.props.value==='demo-router-one'),'demo-router-one');
   }
   control(n=>n.type==='select'&&nodes(n).some(o=>o.type==='option'&&o.props.value==='New'),'New');
  }
  nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
  if(kind==='workspace')control(n=>n.type==='input'&&n.props.type==='checkbox',true);
 };
 const send=()=>kind==='workspace'?nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}}):nodes(render()).find(n=>n.type==='button'&&n.props.className==='button-primary').props.onClick();
 return {render,prepare,send,saved,events,original,refreshProps(){item={...item,revision:99,plan:'Later'};}};
}
const tick=()=>new Promise(setImmediate);
for(const kind of ['workspace','legacy'])for(const mode of ['create','edit'])for(const fault of ['lost-response','truncated-json','wrong-response','wrong-router','wrong-source','wrong-expiry','wrong-status',...(kind==='legacy'?['wrong-price']:[])]){
 test(`${kind} ${mode} ${fault}: one POST, frozen UUID, read-only recovery and dependent refresh`,async()=>{
  const h=harness(kind,mode),calls=[];let receipt;
  const oldFetch=globalThis.fetch,oldWindow=globalThis.window;
  globalThis.window={dispatchEvent:e=>h.events.push(e)};
  globalThis.fetch=async(url,init={})=>{
   calls.push({url,method:init.method??'GET',body:init.body});
   if(init.method==='POST'){
    const command=JSON.parse(init.body),request=command.request_id;
    const item=kind==='workspace'?{...command.fields,id:mode==='create'?'demo-managed-sub-'+request:h.original.id,revision:command.expected_revision+1}:{...h.original,...(mode==='create'?{...command,monthly_price:200}:{plan:command.value,monthly_price:200}),id:mode==='create'?'demo-sub-'+request:h.original.id,revision:mode==='create'?1:h.original.revision+1};
    const response=kind==='workspace'?item:{item,is_demo:true,persistence:'local-postgresql-demo',history:[]};
    receipt={request_id:request,status:'SUCCESS',response};
    if(fault==='lost-response')throw new TypeError('Synthetic lost response');
    if(fault==='truncated-json')return {ok:true,json:async()=>{throw new SyntaxError('Synthetic JSON failure');}};
    const wrong={'wrong-response':{id:'wrong'},'wrong-router':{router_id:'other'},'wrong-source':{source:'RADIUS'},'wrong-expiry':{expires_on:'2000-01-01'},'wrong-status':{status:'ACTIVE'},'wrong-price':{monthly_price:999}}[fault];return {ok:true,json:async()=>kind==='workspace'?{...item,...wrong}:{...response,item:{...item,...wrong}}};
   }
   assert.ok(url.endsWith('/'+receipt.request_id));
   assert.equal(init.body,undefined);return {ok:true,json:async()=>receipt};
  };
  try{
   h.prepare();assert.equal(calls.length,0);h.send();h.send();await tick();
   assert.equal(calls.length,1);assert.equal(h.saved.length,0);
   assert.match(renderToStaticMarkup(h.render()),/Sonuç belirsiz/);
   const correction=nodes(h.render()).find(n=>n.type==='button'&&['Formu düzelt','Düzelt'].includes(n.props.children));assert.equal(correction.props.disabled,true);
   h.refreshProps();h.send();await tick();
   assert.equal(calls.length,2);assert.equal(calls[0].method,'POST');assert.equal(calls[1].method,'GET');
   assert.equal(h.saved.length,1);assert.equal(h.saved[0],kind==='workspace'?receipt.response.id:receipt.response.item.id);
   for(const prefix of ['/subscriber-center','/subscriber-workspace','/subscribers','/dashboard','/reports'])assert.ok(h.events.filter(e=>e.type==='v2-resource-change').at(-1).detail.includes(prefix));
   h.send();await tick();assert.equal(calls.length,2,'successful operation cannot send again');
  }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
 });
}

test('unknown/denied result lookup stays uncertain and never repeats the POST',async()=>{
 const h=harness('hook'),oldFetch=globalThis.fetch,oldWindow=globalThis.window;
 const calls=[];globalThis.window={dispatchEvent(){}};
 const input={requestId:'synthetic-uuid',path:'/subscriber-workspace',resultPath:'/subscriber-workspace/requests/synthetic-uuid',body:'{"frozen":true}',header:'subscriber-workspace',matches:r=>r?.id==='saved'};
 globalThis.fetch=async(url,init={})=>{calls.push(init.method??'GET');if(init.method==='POST')throw Error('Lost');if(calls.length===2)return {ok:true,json:async()=>({request_id:input.requestId,status:'UNKNOWN',response:null})};return {ok:false,status:403,json:async()=>({detail:'Denied'})};};
 try{
  await h.render().send(input);await h.render().send({...input,body:'changed'});
  assert.equal(h.render().state,'UNCERTAIN');assert.match(h.render().error,/uygulanmadığını kanıtlamaz/);
  await h.render().send(input);assert.equal(h.render().state,'UNCERTAIN');assert.deepEqual(calls,['POST','GET','GET']);
 }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
});

test('definitive POST rejection is FAILED and permits a corrected new attempt',async()=>{
 const h=harness('hook'),oldFetch=globalThis.fetch,oldWindow=globalThis.window;globalThis.window={dispatchEvent(){}};
 globalThis.fetch=async()=>({ok:false,status:422,json:async()=>({detail:'Invalid input'})});
 try{
  await h.render().send({requestId:'id',path:'/subscriber-workspace',resultPath:'/result/id',body:'{}',header:'subscriber-workspace',matches:()=>true});
  assert.equal(h.render().state,'FAILED');assert.equal(h.render().locked,false);assert.equal(h.saved.length,0);
  h.render().reset();assert.equal(h.render().state,'IDLE');
 }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
});

test('timeout aborts the POST but only a later GET resolves its result',async()=>{
 const h=harness('hook'),oldFetch=globalThis.fetch,oldWindow=globalThis.window,oldTimer=globalThis.setTimeout,oldClear=globalThis.clearTimeout;
 globalThis.window={dispatchEvent(){}};let expire;const calls=[];
 globalThis.setTimeout=fn=>{expire=fn;return 1;};globalThis.clearTimeout=()=>{};
 globalThis.fetch=async(url,init={})=>{calls.push(init.method??'GET');if(init.method==='POST')return new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new Error('Timeout')),{once:true}));return {ok:true,json:async()=>({request_id:'id',status:'SUCCESS',response:{id:'saved'}})};};
 const input={requestId:'id',path:'/subscriber-workspace',resultPath:'/result/id',body:'{}',header:'subscriber-workspace',matches:r=>r?.id==='saved'};
 try{
  const pending=h.render().send(input);expire();await pending;
  assert.equal(h.render().state,'UNCERTAIN');await h.render().send(input);
  assert.deepEqual(calls,['POST','GET']);assert.equal(h.saved.length,1);
 }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;globalThis.setTimeout=oldTimer;globalThis.clearTimeout=oldClear;}
});
