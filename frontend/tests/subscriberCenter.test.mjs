import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {safeSubscriberCenter,subscriberRouterHash,subscriberCenterTabs} from '../src/lib/subscriberCenter.ts';
const data={source:'PERSISTENT_WORKSPACE',is_demo:true,device_connection_started:false,persistence:'local-postgresql-workspace',item:{id:'demo-managed-sub-fixture',username:'test.ev',customer_name:'Sentetik Abone',router_id:'demo-managed-router-fixture',router_name:'TEST-EV-V2',router_source:'PERSISTENT_DEMO',access_type:'HOTSPOT',source:'LOCAL',plan:'Demo 100',status:'ACTIVE',expires_on:null,revision:1,ip_address:null,last_seen_at:null,last_connected_at:null,session_status:'UNKNOWN'},history:[],connection_history:[]};
const require=createRequire(import.meta.url);
const hooks={...React,useEffect:()=>{},useRef:value=>({current:value}),useState:value=>[typeof value==='function'?value():value,()=>{}]};
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberDeviceCenter.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('five tabs render account and session separately; expire and connection gaps stay unknown',()=>{
 for(const [tab] of subscriberCenterTabs){const tree=module.exports.SubscriberDeviceCenterView({data,tab,onTab:()=>{}});const html=renderToStaticMarkup(tree);assert.match(html,/Sentetik Abone/);assert.match(html,/HOTSPOT/);assert.match(html,/Hesap etkin/);assert.match(html,/canlı oturum ölçülmedi/);assert.match(html,/bağlantı kanıtı yok/);assert.equal((html.match(/role="tab"/g)??[]).length,5);}
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data,tab:'expiry',onTab:()=>{}}));assert.match(html,/bilinmiyor/i);
});
test('tab click and keyboard navigation do not trigger network or mutators',()=>{
 let selected;const tree=module.exports.SubscriberDeviceCenterView({data,tab:'overview',onTab:value=>{selected=value;}});const tabs=nodes(tree).filter(n=>n.props?.role==='tab');tabs[2].props.onClick();assert.equal(selected,'expiry');tabs[0].props.onKeyDown({key:'End',preventDefault:()=>{}});assert.equal(selected,'connections');
});
test('router links use exact ID and source; a matching display name never creates a link',()=>{
 assert.match(subscriberRouterHash(data.item),/source=MANAGED_DEMO/);assert.match(subscriberRouterHash(data.item),/id=demo-managed-router-fixture/);
 assert.equal(subscriberRouterHash({...data.item,router_id:null,router_source:'UNKNOWN'}),null);
 assert.equal(safeSubscriberCenter(data,data.item.id),true);
 for(const change of [{is_demo:false},{source:'LEGACY_DEMO'},{device_connection_started:true},{item:{...data.item,router_id:'registered-fixture'}},{item:{...data.item,session_status:'ONLINE'}}])assert.equal(!!safeSubscriberCenter({...data,...change},data.item.id),false);
});

test('Hotspot edit preserves locked identity and submits only synthetic fields with explicit consent',async()=>{
 const slots=[];let cursor=0;const calls=[];let saved=null;
 const mockReact={...hooks,useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:{items:[{id:data.item.router_id,fields:{name:'TEST-EV-V2'}}]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SyntheticSubscribers.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?mockReact:require(name),module,module.exports);
 const original=globalThis.fetch,originalWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};globalThis.fetch=async(url,init)=>{calls.push({url,init});return {ok:true,json:async()=>data.item};};
 const render=()=>{cursor=0;return module.exports.SyntheticSubscriberEditor({item:data.item,onClose:()=>{},onSaved:id=>{saved=id;}});};
 try{
  let tree=render();const fields=nodes(tree).filter(n=>n.type==='input'||n.type==='select');
  for(const value of [data.item.username,data.item.router_id,'HOTSPOT','LOCAL'])assert.equal(fields.find(n=>n.props.value===value).props.disabled,true);
  nodes(tree).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
  tree=render();await nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/v1/subscriber-workspace/'+data.item.id);
  const payload=JSON.parse(calls[0].init.body);assert.equal(payload.fields.access_type,'HOTSPOT');assert.equal(payload.fields.router_id,data.item.router_id);assert.equal(payload.expected_revision,1);assert.equal(payload.confirmed,true);assert.equal(calls[0].init.headers['X-V2-Demo-Action'],'subscriber-workspace');assert.equal('password' in payload.fields,false);assert.equal(saved,data.item.id);
 }finally{globalThis.fetch=original;globalThis.window=originalWindow;}
});

test('renewal history shows previous/new dates, time and applied result without secrets',()=>{
 const changed={...data,history:[{operation:'RENEWAL',occurred_at:'2026-10-29T12:00:00Z',actor_id:'demo-user',revision:2,previous_expires_on:'2026-10-01',expires_on:'2026-11-28',date_changed:true,result:'APPLIED'}]};
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:changed,tab:'history',onTab:()=>{}}));assert.match(html,/Abonelik uzatıldı/);assert.match(html,/Eski bitiş/);assert.match(html,/Yeni bitiş/);assert.match(html,/Sonuç: Uygulandı/);assert.match(html,/2026/);
});
