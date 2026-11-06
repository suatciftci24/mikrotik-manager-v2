import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash,randomUUID} from 'node:crypto';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup as html} from 'react-dom/server';
import {overlayFiles,expectedReference,prepareLegacyCandidate} from '../scripts/prepare-v26-legacy.mjs';

const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const root=path.resolve(process.env.V26_FRONTEND_ROOT??frontend);
const require=createRequire(import.meta.url);
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const sha=data=>createHash('sha256').update(data).digest('hex');
const row={id:'demo-sub-fixture',customer_name:'Synthetic Subscriber',username:'synthetic.test',is_demo:true,can_manage_pppoe:true,router_id:'demo-router-001',router_name:'Synthetic Router',source:'LOCAL',plan:'Demo 100',monthly_price:10,status:'PAUSED',expires_on:'2099-11-06',revision:1};
const detail={item:row,is_demo:true,persistence:'local-postgresql-demo',history:[]};
const center={source:'LEGACY_DEMO',is_demo:true,device_connection_started:false,persistence:'local-postgresql-demo',item:{...row,router_source:'STATIC_DEMO',session_status:'UNKNOWN',access_type:'PPPOE'},history:[],connection_history:[]};
const simpleHooks={...React,useEffect(){},useCallback:fn=>fn,useRef:value=>({current:value}),useState:value=>[typeof value==='function'?value():value,()=>{}]};
function bundle(name,hooks=simpleHooks){
 const result=buildSync({entryPoints:[path.join(root,'src',name)],bundle:true,metafile:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']});
 const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(name=>name==='react'?hooks:require(name),module,module.exports);
 return {...module.exports,inputs:Object.keys(result.metafile.inputs)};
}
function dialog(name,options={}){
 const slots=[];let cursor=0;
 const hooks={...simpleHooks,useId:()=>':overlay:',useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{
  const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;
  const value=slots[i];
  if(value?.path)return [{...value,loading:false,data:value.path==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans:[{name:'Demo 200',monthly_price:35}]}},()=>{}];
  return[value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];
 }};
 const component=bundle('components/'+name+'.tsx',hooks)[name];
 return props=>{cursor=0;return component({...options,...props});};
}

test('legacy quick actions do not pull recovery hooks, pending journal or ApiError dependencies into VDS',()=>{
 const {inputs}=bundle('components/QuickActions.tsx');
 assert.ok(inputs.some(p=>p.endsWith('subscriberDependencies.ts')));
 assert.ok(inputs.some(p=>p.endsWith('subscriber-edit-highlight.css')));
 assert.ok(!inputs.some(p=>/useSubscriberSave|pendingSubscriberOperations|subscriberOperationRecovery/.test(p)));
});
test('legacy detail retains all five tabs, router link and VDS disclosure while exposing source-specific actions',()=>{
 const view=bundle('components/SubscriberDeviceCenter.tsx').SubscriberDeviceCenterView;
 for(const tab of ['overview','package','expiry','history','connections']){
  const tree=view({data:center,tab,onTab(){},onEdit(){throw Error('workspace editor must not handle legacy');},legacy:React.createElement('p',null,'VDS reports')});
  assert.equal(nodes(tree).filter(n=>n.props?.role==='tab').length,5);
  assert.ok(nodes(tree).some(n=>typeof n.type==='function'&&n.type.name==='LegacySubscriberActions'));
  assert.ok(html(tree).includes('id='+row.router_id));
  if(tab==='overview')assert.ok(nodes(tree).some(n=>n.type==='details'));
  if(tab==='connections')assert.match(html(tree),/Ölçülmedi/);
 }
});
test('legacy toolbar routes all three actions and fails closed for stale, foreign or unauthorized records',()=>{
 let action=null,data=detail;
 const hooks={...simpleHooks,useState:initial=>initial?.path?[{...initial,loading:false,data},()=>{}]:initial===null?[action,value=>{action=value;}]:[typeof initial==='function'?initial():initial,()=>{}]};
 const component=bundle('components/LegacySubscriberActions.tsx',hooks).LegacySubscriberActions;
 const render=()=>component({id:row.id});
 for(const [label,kind] of [['Abonelik Süresini Uzat','EXTEND'],['Paket değiştir','PLAN'],['Aktif / Pasif','STATUS']]){
  nodes(render()).find(n=>n.type==='button'&&html(n).includes(label)).props.onClick();
  const dialog=nodes(render()).find(n=>typeof n.type==='function'&&n.type.name==='QuickActions');
  assert.equal(dialog.props.initialAction,kind);assert.equal(dialog.props.rows[0].id,row.id);
 }
 for(const patch of [{persistence:'process-memory'},{is_demo:false},{item:{...row,id:'demo-sub-other'}},{item:{...row,source:null}},{item:{...row,router_id:null}},{item:{...row,can_manage_pppoe:false}}]){
  data={...detail,...patch};assert.equal(nodes(render()).filter(n=>n.type==='button').length,0);
  assert.ok(!nodes(render()).some(n=>typeof n.type==='function'&&n.type.name==='QuickActions'));
 }
});
for(const action of ['EXTEND','PLAN','STATUS'])test(`merged legacy ${action}: preview, consent, existing API, revision/source and dependent refresh`,async()=>{
 const render=dialog('QuickActions',{rows:[row],today:'2026-11-06',initialAction:action,onClose(){}});
 const calls=[],events=[],previousFetch=globalThis.fetch,previousWindow=globalThis.window;
 globalThis.window={dispatchEvent:event=>events.push(event)};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return{ok:true,json:async()=>({results:[{item_id:row.id,success:true,result:detail}]})};};
 try{
  let tree=render();
  if(action==='PLAN'){nodes(tree).find(n=>n.type==='select'&&n.props['aria-labelledby']?.endsWith('-plan')).props.onChange({target:{value:'Demo 200'}});tree=render();assert.match(html(tree),/Aylık fark: 25 TL/);}
  nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(calls.length,0);
  tree=render();assert.match(html(tree),/Eski → Yeni/);
  await nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/v1/subscribers/demo-quick');
  assert.equal(calls[0].init.headers['X-V2-Demo-Action'],'expiry');
  const command=JSON.parse(calls[0].init.body).entries[0];assert.equal(command.item_id,row.id);
  assert.equal(command.change.action,action);assert.equal(command.change.expected_revision,row.revision);
  assert.equal(command.change.expected_source,row.source);assert.equal(command.change.router_id,row.router_id);assert.equal(command.change.confirmed,true);
  for(const prefix of ['/subscribers','/subscriber-center','/router-center','/dashboard','/reports'])assert.ok(events[0].detail.includes(prefix));
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});
test('VDS workspace renewal keeps current plan, all durations and preview without mutations',()=>{
 const item={...center.item,id:'demo-managed-sub-fixture',router_id:'demo-managed-router-fixture',router_source:'PERSISTENT_DEMO',access_type:'HOTSPOT'};
 const render=dialog('SubscriberRenewal',{item,onClose(){}});
 const tree=render();assert.match(html(tree),/Demo 100/);
 const options=nodes(tree).filter(n=>n.type==='option').map(n=>n.props.value);
 for(const value of ['7','15','30','60','90','CUSTOM'])assert.ok(options.includes(value));
 nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.match(html(render()),/Eski → Yeni/);
});
test('merged audit keeps package context with changed expiry, actor, Istanbul time and failed result',()=>{
 const view=bundle('components/SubscriberDeviceCenter.tsx').SubscriberDeviceCenterView;
 const data={...center,history:[{operation:'RENEWAL',occurred_at:'2026-11-05T21:30:00Z',actor_id:'synthetic.actor',date_changed:true,previous_expires_on:'2026-11-01',expires_on:'2026-12-06',previous_values:{plan:'Historical Plan'},new_values:{plan:'Historical Plan'},revision:2,result:'APPLIED'},{operation:'STATUS',occurred_at:'2026-11-05T21:31:00Z',actor_id:'synthetic.actor',date_changed:false,revision:2,result:'FAILED',error:'Revision conflict'}]};
 const content=html(view({data,tab:'history',onTab(){}}));
 for(const value of ['Historical Plan','synthetic.actor','00:30','İstanbul','Eski bitiş','Yeni bitiş','Başarısız','Revision conflict'])assert.ok(content.includes(value));
});
test('candidate preparation rejects existing outputs and reference drift without touching source files',()=>{
 const repo=path.dirname(frontend),output=path.join(repo,'.local','v26-legacy-safety-'+randomUUID());
 fs.mkdirSync(output);fs.writeFileSync(path.join(output,'keep'),'operator data');
 try{
  assert.throws(()=>prepareLegacyCandidate({reference:path.join(root,'src'),output}),/NEW_LOCAL_OUTPUT_REQUIRED/);
  assert.equal(fs.readFileSync(path.join(output,'keep'),'utf8'),'operator data');
 }finally{fs.rmSync(output,{recursive:true});}
 const reference=fs.mkdtempSync(path.join(repo,'.local','v26-legacy-reference-'));
 try{
  fs.writeFileSync(path.join(reference,'unexpected.ts'),'reference drift');
  assert.throws(()=>prepareLegacyCandidate({reference,output}),/REFERENCE_DRIFT_STOP/);
  assert.equal(fs.existsSync(output),false);
 }finally{fs.rmSync(reference,{recursive:true});}
});
if(root!==frontend)test('every VDS file outside the 10-file overlay remains byte-identical',()=>{
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'preservation.json'),'utf8'));
 assert.equal(manifest.referenceSourceFiles,109);assert.equal(manifest.unchangedSourceFiles,103);
 assert.equal(Object.keys(expectedReference()).length,109);assert.equal(overlayFiles.length,10);
 for(const [name,hash] of Object.entries(manifest.after))assert.equal(sha(fs.readFileSync(path.join(root,'src',name))),hash,name);
 for(const [name,hash] of Object.entries(manifest.before))if(!overlayFiles.includes(name))assert.equal(manifest.after[name],hash,name);
 assert.equal(sha(fs.readFileSync(path.join(root,'package-lock.json'))),manifest.packageLockSha256);
});
