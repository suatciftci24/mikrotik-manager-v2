import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {routerCenterTabs,validRouterCenter,routerCenterPath,routerCenterStatus,routerCenterError} from '../src/lib/routerCenter.ts';
const data={source:'PERSISTENT_DEMO',is_demo:true,device_connection_started:false,item:{id:'demo-managed-router-fixture',name:'TEST-EV-V2',identity:null,model:'Sentetik model',routeros_version:null,management_address:'192.0.2.10',site:'Ev',status:'UNMEASURED',last_success_at:null,last_seen_at:null,cpu_percent:null,memory_percent:null,uptime:null},sections:Object.fromEntries(routerCenterTabs.map(([key])=>[key,['overview','events','security'].includes(key)?'AVAILABLE':'UNMEASURED'])),events:[{action:'CREATED',actor_id:'demo-user',occurred_at:'2026-10-29T12:00:00Z',revision:1}]};
const require=createRequire(import.meta.url);
const react={...React,useRef:value=>({current:value}),useState:initial=>[initial,()=>{}]};
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/RouterDeviceCenter.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);
const view=(tab,overrides={},onTab=()=>{})=>module.exports.RouterDeviceCenterView({data:{...data,...overrides},tab,onTab});
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('all seven sections render and TEST-EV-V2 keeps unknown measurements and synthetic labels',()=>{
 for(const [tab,label] of routerCenterTabs){
  const html=renderToStaticMarkup(view(tab));assert.match(html,/TEST-EV-V2/);assert.match(html,/SENTETİK DEMO/);assert.match(html,/Ölçülmedi/);assert.equal((html.match(/role="tab"/g)??[]).length,7);assert.ok(html.includes(label));assert.doesNotMatch(html,/undefined%|null%|NaN/);
 }
 assert.match(renderToStaticMarkup(view('events')),/Sentetik kayıt eklendi/);
 assert.match(renderToStaticMarkup(view('security')),/Cihaz bağlantısı, parola veya sertifika gerektirmez/);
});
test('tabs expose selected state, click and keyboard navigation without requests',()=>{
 let selected=null;const tree=view('overview',{},tab=>{selected=tab;});const tabs=nodes(tree).filter(n=>n.props?.role==='tab');
 assert.equal(tabs[0].props['aria-selected'],true);assert.equal(tabs[1].props.tabIndex,-1);
 tabs[3].props.onClick();assert.equal(selected,'pppoe');
 tabs[0].props.onKeyDown({key:'ArrowLeft',preventDefault:()=>{}});assert.equal(selected,'security');
 tabs[0].props.onKeyDown({key:'End',preventDefault:()=>{}});assert.equal(selected,'security');
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
