import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {routerCenterTabs,primaryRouterTab,routerSubscriberListHash,validRouterCenter,routerCenterPath,routerCenterStatus,routerCenterError} from '../src/lib/routerCenter.ts';
import {routerAlarmPath,routerAlarmTarget} from '../src/lib/alarms.ts';
const data={source:'PERSISTENT_DEMO',is_demo:true,device_connection_started:false,item:{id:'demo-managed-router-fixture',name:'TEST-EV-V2',identity:null,model:'Sentetik model',routeros_version:null,management_address:'192.0.2.10',site:'Ev',status:'UNMEASURED',last_success_at:null,last_seen_at:null,cpu_percent:null,memory_percent:null,uptime:null},sections:Object.fromEntries(routerCenterTabs.map(([key])=>[key,['overview','events','security'].includes(key)?'AVAILABLE':'UNMEASURED'])),events:[{action:'CREATED',actor_id:'demo-user',occurred_at:'2026-10-29T12:00:00Z',revision:1}]};
const require=createRequire(import.meta.url);
const react={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>({current:value}),useState:initial=>[typeof initial==='function'?initial():initial,()=>{}]};
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/RouterDeviceCenter.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);
const view=(tab,overrides={},onTab=()=>{})=>module.exports.RouterDeviceCenterView({data:{...data,...overrides},tab,onTab});
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('all four sections render and TEST-EV-V2 keeps unknown measurements and synthetic labels',()=>{
 for(const [tab,label] of routerCenterTabs){
  const html=renderToStaticMarkup(view(tab));assert.match(html,/TEST-EV-V2/);assert.match(html,/SENTETİK DEMO/);assert.match(html,/Veri yok/);assert.equal((html.match(/role="tab"/g)??[]).length,4);assert.ok(html.includes(label));assert.doesNotMatch(html,/undefined%|null%|NaN/);
 }
 assert.match(renderToStaticMarkup(view('events')),/Sentetik kayıt eklendi/);
 assert.match(renderToStaticMarkup(view('security')),/Cihaz bağlantısı, parola veya sertifika gerektirmez/);
});
test('tabs expose selected state, click and keyboard navigation without requests',()=>{
 let selected=null;const tree=view('overview',{},tab=>{selected=tab;});const tabs=nodes(tree).filter(n=>n.props?.role==='tab');
 assert.equal(tabs[0].props['aria-selected'],true);assert.equal(tabs[1].props.tabIndex,-1);
 tabs[2].props.onClick();assert.equal(selected,'subscribers');
 tabs[0].props.onKeyDown({key:'ArrowLeft',preventDefault:()=>{}});assert.equal(selected,'events');
 tabs[0].props.onKeyDown({key:'End',preventDefault:()=>{}});assert.equal(selected,'events');
});
test('source mismatch fails closed and saved router missing sections prepare without live claims',()=>{
 assert.equal(validRouterCenter(data,data.item.id),true);
 assert.equal(validRouterCenter({...data,is_demo:false},data.item.id),false);
 assert.equal(validRouterCenter({...data,source:'REGISTERED',is_demo:false},data.item.id),false);
 assert.equal(validRouterCenter({...data,device_connection_started:true},data.item.id),false);
 const live={source:'REGISTERED',is_demo:false,item:{...data.item,id:'registered-fixture',status:'STALE'},sections:{...data.sections,interfaces:'PREPARING'}};
 const html=renderToStaticMarkup(view('interfaces',live));assert.match(html,/Hazırlanıyor/);assert.match(html,/KAYITLI CİHAZ/);assert.match(html,/eskimiş/);assert.doesNotMatch(routerCenterStatus({...data,...live}),/ONLINE/);
 assert.equal(routerCenterPath('a/b'),'/router-center/a%2Fb');
 const zero=renderToStaticMarkup(view('overview',{source:'STATIC_DEMO',item:{...data.item,cpu_percent:0,memory_percent:0}}));assert.match(zero,/0%/);
});

test('router detail separates last successful connection from measurement and marks WAN evidence time',()=>{
 const dated={...data,item:{...data.item,last_success_at:'2026-11-07T08:00:00Z',last_seen_at:'2026-11-07T08:05:00Z'}};
 const overview=renderToStaticMarkup(view('overview',dated));
 assert.match(overview,/Son başarılı bağlantı/);assert.match(overview,/Son ölçüm zamanı/);assert.match(overview,/son başarılı bağlantı zamanı ayrı gösterilir/);
 const snapshot={identity:'R1',model:'Router',routeros_version:'7',cpu_percent:2,memory_percent:3,uptime:'1d',captured_at:'2026-11-07T08:05:00Z',interfaces:[],default_routes:[{'dst-address':'0.0.0.0/0',gateway:'192.0.2.1',active:true,disabled:false}],wan_ip:null,pppoe_count:4,pppoe_explicit_count:4,ppp_any_count:0,hotspot_count:0,is_demo:false,read_only:true};
 const wan=renderToStaticMarkup(view('wan',{source:'REGISTERED',is_demo:false,item:{...data.item,id:'registered-fixture',status:'VERIFIED'},read_snapshot:snapshot}));
 assert.match(wan,/WAN IP bilinmiyor/);assert.match(wan,/192\.0\.2\.1/);assert.match(wan,/Kaydedilmiş okuma/);
});

test('only the static synthetic router links to its exact filtered alarm scope',()=>{
 const staticData={...data,source:'STATIC_DEMO',item:{...data.item,id:'demo-router-001',name:'Test Router'}};
 const html=renderToStaticMarkup(view('events',staticData));
 const href=[...html.matchAll(/href="([^"]+)"/g)].map(match=>match[1].replaceAll('&amp;','&')).find(value=>value.startsWith('#module=operations'));
 assert.ok(href);assert.equal(new URLSearchParams(href.slice(1)).get('alarm_router'),'demo-router-001');
 assert.match(html,/Bu router’ın alarm ve olaylarını aç/);
 const path=new URLSearchParams(routerAlarmPath('demo-router-001').split('?')[1]),target=new URLSearchParams(routerAlarmTarget('demo-router-001','demo-alarm-uuid').slice(1));
 assert.equal(path.get('router_id'),'demo-router-001');assert.equal(path.get('page_size'),'1');
 assert.equal(target.get('alarm_router'),'demo-router-001');assert.equal(target.get('alarm_id'),'demo-alarm-uuid');
 const persistent=renderToStaticMarkup(view('overview',{...data,item:{...data.item,id:'demo-managed-router-fixture'}}));
 assert.doesNotMatch(persistent,/Bu router’ın alarm ve olaylarını aç/);
});

test('managed router list name opens the ID-based center without writing or connecting',()=>{
 let opened=null;
 const hooks={...react,useEffect:()=>{},useCallback:fn=>fn,useState:initial=>{
  const value=typeof initial==='function'?initial():initial;
  return value?.path?[{...value,loading:false,data:{items:[{id:data.item.id,kind:'DEMO_ROUTER',is_demo:true,device_connected:false,revision:1,fields:{name:'TEST-EV-V2',management_address:'192.0.2.10',model:'Test',site:'Ev'}}],total:1}},()=>{}]:[value,()=>{}];
 }};
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/DemoRouterWorkspace.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?hooks:require(name),module,module.exports);
 const tree=module.exports.DemoRouterWorkspace({onOpen:id=>{opened=id;}});
 nodes(tree).find(n=>n.type==='button'&&n.props.children==='TEST-EV-V2').props.onClick();
 assert.equal(opened,data.item.id);
});

test('missing module and denied inventory errors are understandable without hiding missing records',()=>{
 assert.match(routerCenterError('Not Found'),/çalışan backend/);
 assert.match(routerCenterError('ONBOARDING_OPERATOR_NOT_AUTHORIZED'),/yetkilendirilmemiş/);
 assert.equal(routerCenterError('Sentetik router bulunamadı.'),'Sentetik router bulunamadı.');
});

test('legacy section links select their new parent and subscriber center filters by exact identity',()=>{
 for(const [old,parent] of [['security','overview'],['interfaces','wan'],['pppoe','subscribers'],['hotspot','subscribers']])assert.equal(primaryRouterTab(old),parent);
 for(const [id,key,workspace] of [['demo-router-001','router_id','LEGACY'],['demo-managed-router-fixture','workspace_router','PERSISTENT']]){
  const params=new URLSearchParams(routerSubscriberListHash(id).slice(1));assert.equal(params.get(key),id);assert.equal(params.get('workspace'),workspace);assert.equal(params.has('router'),false);
 }
 const html=renderToStaticMarkup(view('subscribers'));assert.match(html,/Abone Merkezi’nde bu routerı aç/);assert.match(html,/workspace_router=demo-managed-router-fixture/);
 const registered=renderToStaticMarkup(view('subscribers',{source:'REGISTERED',is_demo:false,item:{...data.item,id:'registered-fixture',status:'PENDING_VERIFICATION'}}));assert.doesNotMatch(registered,/Abone Merkezi’nde/);assert.match(registered,/gerçek veri okuması kapalı/);assert.doesNotMatch(registered,/API verisi alınamadı/);
});

test('subscriber access selection reuses one scoped list and preserves legacy Hotspot links',()=>{
 let selected=null;const tree=view('subscribers',{},tab=>{selected=tab;});
 const select=nodes(tree).find(node=>node.type==='select');assert.equal(select.props.value,'PPPOE');
 select.props.onChange({target:{value:'HOTSPOT'}});assert.equal(selected,'hotspot');
 const html=renderToStaticMarkup(view('hotspot'));assert.match(html,/Hotspot hesap kayıtları/);assert.doesNotMatch(html,/PPPoE hesap kayıtları/);
});


test('persistent router navigation retains PPPoE or Hotspot subscriber scope',()=>{
 for(const access of ['PPPOE','HOTSPOT']){
  const params=new URLSearchParams(routerSubscriberListHash(data.item.id,access).slice(1));
  assert.equal(params.get('workspace'),'PERSISTENT');
  assert.equal(params.get('workspace_router'),data.item.id);
  assert.equal(params.get('workspace_access'),access);
  const html=renderToStaticMarkup(view(access==='HOTSPOT'?'hotspot':'subscribers'));
  assert.match(html,new RegExp('workspace_access='+access));
 }
 const legacy=new URLSearchParams(routerSubscriberListHash('demo-router-001').slice(1));
 assert.equal(legacy.get('workspace'),'LEGACY');assert.equal(legacy.get('router_id'),'demo-router-001');
 assert.equal(legacy.has('workspace_access'),false);
});
