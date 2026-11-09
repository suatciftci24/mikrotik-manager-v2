import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {turkeyToday} from '../src/lib/expiry.ts';
const require=createRequire(import.meta.url),quiet=()=>{};
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const row={id:'demo-sub-fast',customer_name:'Sentetik Abone',username:'fast.test',router_id:'demo-router-fast',router_name:'Sentetik Router',source:'LOCAL',plan:'Paket 100',status:'ACTIVE',expires_on:'2099-01-01',revision:1,is_demo:true,can_manage_pppoe:true,monthly_price:100,ip_address:null,last_seen:null,joined_at:null};
const workspace={...row,id:'demo-managed-sub-fast',router_id:'demo-managed-router-fast',router_source:'PERSISTENT_DEMO',access_type:'PPPOE',session_status:'UNKNOWN'};
const detail={item:row,is_demo:true,persistence:'local-postgresql-demo',history:[]};
function harness(path,resource=()=>undefined,identity){
 const slots=[];let cursor=0;
 const hooks={...React,useId:()=>':fast:',useContext:()=>identity,useEffect(){},useMemo:fn=>fn(),useCallback:fn=>fn,
  useRef(value){const i=cursor++;slots[i]??={current:value};return slots[i];},
  useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;
   if(slots[i]?.path)return [{...slots[i],loading:false,...resource(slots[i].path)},()=>{}];
   return [slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const code=buildSync({entryPoints:[path],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],loader:{'.css':'empty'}}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 return {exports:module.exports,render(name,props){cursor=0;return module.exports[name](props);}};
}
const {canSelectLegacyAction,canChangeWorkspaceItem}=harness('src/lib/subscriberActions.ts').exports;
function stubGlobals(t){
 const before={window:globalThis.window,document:globalThis.document,fetch:globalThis.fetch,HashChangeEvent:globalThis.HashChangeEvent};t.after(()=>Object.assign(globalThis,before));
 const location={hash:'#module=subscribers&workspace=LEGACY&query=test&status=ACTIVE',pathname:'/',search:''};
 globalThis.window={location,history:{replaceState(_s,_t,url){location.hash=url.slice(url.indexOf('#'));}},dispatchEvent(){},scrollY:0};
 globalThis.HashChangeEvent=class extends Event {};
 globalThis.document={activeElement:null};globalThis.fetch=()=>{throw new Error('Unexpected network request');};return location;
}
test('compact actions restore focus, stop row navigation and support Escape',()=>{
 const h=harness('src/components/SubscriberQuickButtons.tsx'),calls=[];let stopped=false,focused=false,closed=false;
 const menu={removeAttribute(name){assert.equal(name,'open');closed=true;},querySelector(){return {focus(){focused=true;}};}};
 const tree=h.exports.SubscriberQuickButtons({compact:true,status:'ACTIVE',label:row.customer_name,onAction:a=>calls.push(a),onHistory:()=>calls.push('history')});
 tree.props.onClick({stopPropagation(){stopped=true;}});assert.ok(stopped);assert.match(renderToStaticMarkup(tree),/aria-label="Sentetik Abone işlemleri"/);
 for(const [text,action] of [['Abonelik Uzat','EXTEND'],['Paket Değiştir','PLAN'],['Hesabı Kapat','STATUS'],['İşlem Geçmişi','history']]){nodes(tree).find(n=>n.type==='button'&&n.props.children===text).props.onClick({currentTarget:{closest:()=>menu}});assert.equal(calls.at(-1),action);assert.ok(focused&&closed);}
 tree.props.onKeyDown({key:'Escape',currentTarget:menu});
 const readOnly=renderToStaticMarkup(h.exports.SubscriberQuickButtons({status:'PAUSED',onHistory:quiet}));assert.doesNotMatch(readOnly,/Abonelik Uzat|Paket Değiştir|Hesabı Aç/);assert.match(readOnly,/İşlem Geçmişi/);
});
test('legacy row action opens a canonical preset loader without losing filters or opening detail',t=>{
 const location=stubGlobals(t),before=location.hash;
 const h=harness('src/screens/Subscribers.tsx',path=>path==='/subscribers'?{data:{items:[row],is_demo:true}}:undefined,{role_code:'ADMIN',can_manage_users:true,permissions:{}}),props={onToast:quiet};
 let tree=h.render('Subscribers',props);const surface=nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons'&&n.props.compact);assert.ok(surface);
 surface.props.onAction('PLAN');assert.equal(location.hash,before);tree=h.render('Subscribers',props);
 const modal=nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='LegacySubscriberActions');assert.equal(modal.props.id,row.id);assert.equal(modal.props.initialAction,'PLAN');modal.props.onClose();
 assert.equal(nodes(h.render('Subscribers',props)).some(n=>typeof n.type==='function'&&n.type.name==='LegacySubscriberActions'),false);
 surface.props.onHistory();const params=new URLSearchParams(location.hash.slice(1));assert.equal(params.get('id'),row.id);assert.equal(params.get('tab'),'history');assert.equal(params.get('query'),'test');assert.equal(params.get('status'),'ACTIVE');
});
test('workspace row forwards each action and denies unknown source/router bindings',t=>{
 stubGlobals(t);const calls=[],h=harness('src/components/SyntheticSubscribers.tsx',path=>path.startsWith('/subscriber-workspace?')?{data:{items:[workspace],total:1,is_demo:true}}:{data:{items:[]}});
 const tree=h.render('SyntheticSubscriberList',{onOpen:id=>calls.push(['detail',id]),onCreate:quiet,onQuick:(r,a)=>calls.push([r,a]),onHistory:id=>calls.push(['history',id])});
 const surface=nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons');assert.ok(surface);
 for(const action of ['EXTEND','PLAN','STATUS']){surface.props.onAction(action);assert.deepEqual(calls.at(-1),[workspace,action]);}surface.props.onHistory();assert.deepEqual(calls.at(-1),['history',workspace.id]);
 for(const patch of [{source:null},{router_missing:true},{router_source:'UNKNOWN'},{id:'registered-live'}])assert.equal(canChangeWorkspaceItem({...workspace,...patch},true),false);
 for(const patch of [{source:null},{can_manage_pppoe:false},{is_demo:false},{router_id:null},{id:'registered-live'}])assert.equal(canSelectLegacyAction({...row,...patch}),false);
});
test('canonical modal retains its frozen revision across background refresh and denies nonpersistent records',t=>{
 stubGlobals(t);let state={data:detail};const h=harness('src/components/LegacySubscriberActions.tsx',()=>state),props={id:row.id,initialAction:'STATUS',onClose:quiet};
 const modal=tree=>nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='QuickActions');
 assert.equal(modal(h.render('LegacySubscriberActions',props)).props.rows[0].revision,1);
 state={data:detail,loading:true};assert.ok(modal(h.render('LegacySubscriberActions',props)));
 state={data:{...detail,item:{...row,revision:2,status:'PAUSED'}}};const selected=modal(h.render('LegacySubscriberActions',props));assert.equal(selected.props.rows[0].revision,1);assert.equal(selected.props.rows[0].status,'ACTIVE');
 const denied=harness('src/components/LegacySubscriberActions.tsx',()=>({data:{...detail,persistence:'process-memory'}}));assert.equal(modal(denied.render('LegacySubscriberActions',props)),undefined);
});
test('legacy and workspace status modals preset the opposite saved state without writing',t=>{
 stubGlobals(t);
 for(const [status,next] of [['ACTIVE','PAUSED'],['PAUSED','ACTIVE'],['PENDING','ACTIVE']]){
  const h=harness('src/components/QuickActions.tsx',path=>({data:path==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans:[]}}));
  const tree=h.render('QuickActions',{rows:[{...row,status}],initialAction:'STATUS',today:turkeyToday(),onClose:quiet});assert.ok(nodes(tree).some(n=>n.type==='select'&&n.props.value==='STATUS'));assert.ok(nodes(tree).some(n=>n.type==='select'&&n.props.value===next));
  const daily=harness('src/components/SubscriberDailyActions.tsx',()=>({data:{items:[]}}));assert.ok(nodes(daily.render('SubscriberDailyActions',{rows:[{...workspace,status}],initialAction:'STATUS',onClose:quiet})).some(n=>n.type==='select'&&n.props.value===next));
 }
});
test('renewal modals provide 30/90/custom selectors before preview without any write',t=>{
 stubGlobals(t);
 for(const [path,name,props] of [['src/components/QuickActions.tsx','QuickActions',{rows:[row],initialAction:'EXTEND',today:turkeyToday(),onClose:quiet}],['src/components/SubscriberRenewal.tsx','SubscriberRenewal',{item:workspace,onClose:quiet}]]){
  const h=harness(path,resource=>({data:resource==='/routers'?{items:[{id:row.router_id,name:row.router_name}]}:{plans:[]}}));
  for(const [label,value] of [['30 gün','30'],['90 gün','90'],['Özel tarih','CUSTOM']]){let tree=h.render(name,props);const button=nodes(tree).find(n=>n.type==='button'&&n.props.children===label);assert.ok(button);button.props.onClick();tree=h.render(name,props);assert.ok(nodes(tree).some(n=>n.type==='select'&&n.props.value===value));if(value==='CUSTOM')assert.ok(nodes(tree).some(n=>n.type==='input'&&n.props.type==='date'));}
 }
});
test('workspace PLAN preset compares old and typed package and still requires explicit consent',t=>{
 stubGlobals(t);const h=harness('src/components/SubscriberDailyActions.tsx',()=>({data:{items:[]}})),props={rows:[workspace],initialAction:'PLAN',onClose:quiet};let tree=h.render('SubscriberDailyActions',props);
 assert.ok(nodes(tree).some(n=>n.type==='select'&&n.props.value==='PLAN'));nodes(tree).find(n=>n.type==='input'&&n.props.type==='text').props.onChange({target:{value:'Paket 200'}});
 tree=h.render('SubscriberDailyActions',props);const html=renderToStaticMarkup(tree);assert.match(html,/Mevcut paket/);assert.match(html,/Paket 100/);assert.match(html,/Yeni paket: Paket 200/);
 nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:quiet});tree=h.render('SubscriberDailyActions',props);const confirm=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula');assert.equal(confirm.props.disabled,true);assert.match(renderToStaticMarkup(tree),/Eski: Paket 100 → Yeni: Paket 200/);
});

test('a double click posts once, keeps the current page and refreshes detail/list/Dashboard/history',async t=>{
 const location=stubGlobals(t),before=location.hash;const calls=[],refreshes=[];let release;
 globalThis.window.dispatchEvent=event=>{if(event.type==='v2-resource-change')refreshes.push(event.detail);};
 globalThis.fetch=(url,init)=>{calls.push({url,init});return new Promise(resolve=>{release=()=>{const entry=JSON.parse(init.body).entries[0];resolve({ok:true,json:async()=>({results:[{item_id:entry.item_id,request_id:entry.request_id,operation:entry.operation,actor_id:'synthetic.test',router_id:entry.expected_router_id,previous_router_id:entry.expected_router_id,revision:entry.expected_revision+1,previous:{status:'ACTIVE'},values:{status:entry.value},success:true,recorded:true,occurred_at:'2026-11-09T09:00:00Z',error:null}]})});};});};
 const h=harness('src/components/SubscriberDailyActions.tsx',()=>({data:{items:[]}})),props={rows:[workspace],initialAction:'STATUS',onClose:quiet};
 let tree=h.render('SubscriberDailyActions',props);nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:quiet});assert.equal(calls.length,0);
 tree=h.render('SubscriberDailyActions',props);nodes(tree).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
 tree=h.render('SubscriberDailyActions',props);const save=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula');
 save.props.onClick();save.props.onClick();assert.equal(calls.length,1);assert.equal(JSON.parse(calls[0].init.body).entries[0].value,'PAUSED');
 release();await new Promise(setImmediate);tree=h.render('SubscriberDailyActions',props);assert.match(renderToStaticMarkup(tree),/Başarılı: 1/);
 assert.equal(nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı UUID ile sonuçları sorgula').props.disabled,true);
 for(const path of ['/subscribers','/subscriber-workspace','/subscriber-center','/dashboard','/reports'])assert.ok(refreshes.some(paths=>paths.includes(path)),path);
 assert.equal(location.hash,before);
});

test('detail keeps the selected canonical modal mounted while its center refreshes',t=>{
 stubGlobals(t);
 const center={is_demo:true,source:'LEGACY_DEMO',persistence:'local-postgresql-demo',device_connection_started:false,history:[],connection_history:[],item:{...row,access_type:'PPPOE',router_source:'STATIC_DEMO',session_status:'UNKNOWN'}};
 let resource={data:center};const h=harness('src/components/SubscriberDeviceCenter.tsx',()=>resource),props={id:row.id,onBack:quiet};
 let tree=h.render('SubscriberDeviceCenter',props);
 const view=nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberDeviceCenterView');assert.ok(view);
 view.props.onLegacyAction(detail,'PLAN');tree=h.render('SubscriberDeviceCenter',props);
 const modal=tree=>nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='QuickActions');
 assert.equal(modal(tree).props.initialAction,'PLAN');assert.equal(modal(tree).props.rows[0],row);
 resource={data:center,loading:true};tree=h.render('SubscriberDeviceCenter',props);assert.ok(modal(tree));assert.equal(nodes(tree).some(n=>typeof n.type==='function'&&n.type.name==='SubscriberDeviceCenterView'),false);
 resource={data:{...center,item:{...center.item,revision:2}}};tree=h.render('SubscriberDeviceCenter',props);assert.equal(modal(tree).props.rows[0].revision,1);
 modal(tree).props.onClose();assert.equal(modal(h.render('SubscriberDeviceCenter',props)),undefined);
});

test('legacy detail delegates only the canonical authorized snapshot to its stable modal host',t=>{
 stubGlobals(t);const calls=[],h=harness('src/components/LegacySubscriberActions.tsx',()=>({data:detail}));
 const tree=h.render('LegacySubscriberActions',{id:row.id,onSelect:(d,a)=>calls.push([d,a])});
 const surface=nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons');
 surface.props.onAction('STATUS');assert.deepEqual(calls,[[detail,'STATUS']]);
 assert.equal(nodes(tree).some(n=>typeof n.type==='function'&&n.type.name==='QuickActions'),false);
});
