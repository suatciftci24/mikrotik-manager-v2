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
const hooks={...React,useId:()=>':center:',useContext:()=>undefined,useEffect:()=>{},useRef:value=>({current:value}),useState:value=>[typeof value==='function'?value():value,()=>{}]};
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberDeviceCenter.tsx',import.meta.url))],bundle:true,loader:{'.css':'empty'},write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('four tabs keep the compact summary while connection evidence stays in its own panel',()=>{
 assert.deepEqual(subscriberCenterTabs.map(([,label])=>label),['Abonelik','İşlemler','Geçmiş','Bağlantı']);
 for(const [tab] of subscriberCenterTabs){
  const tree=module.exports.SubscriberDeviceCenterView({data,tab,onTab:()=>{}});const html=renderToStaticMarkup(tree);
  for(const text of ['Sentetik Abone','HOTSPOT','Hesap etkin','test.ev','Demo 100','Bitiş tarihi','Kalan gün'])assert.ok(html.includes(text),text);
  assert.equal((html.match(/role="tab"/g)??[]).length,4);
  assert.equal((html.match(/aria-selected="true"/g)??[]).length,1);
  if(tab==='connections'){assert.match(html,/canlı oturum ölçülmedi/);assert.match(html,/bağlantı kanıtı yok/);}
  else assert.doesNotMatch(html,/Son bağlantı|Sentetik kayıt IP adresi/);
 }
 for(const tab of ['package','expiry']){
  const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data,tab,onTab(){}}));
  assert.match(html,/id="subscriber-panel-overview"/);assert.match(html,/Veri yok/);
 }
});
test('installation photos are an opt-in disclosure without a fifth tab and require a verified subscriber binding',()=>{
 const tree=module.exports.SubscriberDeviceCenterView({data,tab:'photos',onTab(){},photosEnabled:true});
 assert.equal(nodes(tree).filter(node=>node.props?.role==='tab').length,4);
 const photos=nodes(tree).find(node=>typeof node.type==='function'&&node.type.name==='SubscriberPhotos');assert.ok(photos);
 assert.equal(photos.props.id,data.item.id);assert.equal(photos.props.source,'LOCAL');assert.equal(photos.props.canManage,false);
 const denied=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,item:{...data.item,source:null}},tab:'photos',onTab(){},photosEnabled:true}));
 assert.match(denied,/doğrulanmış LOCAL\/RADIUS kaynağı/);assert.doesNotMatch(denied,/subscriber-photo-grid/);
 assert.equal(nodes(module.exports.SubscriberDeviceCenterView({data,tab:'overview',onTab(){}})).filter(node=>node.props?.role==='tab').length,4);
});
test('tab click and keyboard navigation do not trigger network or mutators',()=>{
 let selected;const tree=module.exports.SubscriberDeviceCenterView({data,tab:'overview',onTab:value=>{selected=value;}});const tabs=nodes(tree).filter(n=>n.props?.role==='tab');tabs[2].props.onClick();assert.equal(selected,'history');tabs[0].props.onKeyDown({key:'End',preventDefault:()=>{}});assert.equal(selected,'connections');
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
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SyntheticSubscribers.tsx',import.meta.url))],bundle:true,loader:{'.css':'empty'},write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?mockReact:require(name),module,module.exports);
 const original=globalThis.fetch,originalWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};globalThis.fetch=async(url,init)=>{calls.push({url,init});return {ok:true,json:async()=>({...data.item,...JSON.parse(init.body).fields,revision:data.item.revision+1})};};
 const render=()=>{cursor=0;return module.exports.SyntheticSubscriberEditor({item:data.item,onClose:()=>{},onSaved:id=>{saved=id;}});};
 try{
  let tree=render();const fields=nodes(tree).filter(n=>n.type==='input'||n.type==='select');
  for(const value of [data.item.username,data.item.router_id,'HOTSPOT','LOCAL'])assert.equal(fields.find(n=>n.props.value===value).props.disabled,true);
  fields.find(n=>n.props.value===data.item.plan).props.onChange({target:{value:'Demo 200'}});
  tree=render();await nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();assert.match(renderToStaticMarkup(tree),/Önceki → Yeni/);assert.equal(calls.length,0);
  nodes(tree).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
  tree=render();await nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/v1/subscriber-workspace/'+data.item.id);
  const payload=JSON.parse(calls[0].init.body);assert.equal(payload.fields.plan,'Demo 200');assert.equal(payload.fields.access_type,'HOTSPOT');assert.equal(payload.fields.router_id,data.item.router_id);assert.equal(payload.expected_revision,1);assert.equal(payload.confirmed,true);assert.equal(calls[0].init.headers['X-V2-Demo-Action'],'subscriber-workspace');assert.equal('password' in payload.fields,false);assert.equal(saved,data.item.id);
 }finally{globalThis.fetch=original;globalThis.window=originalWindow;}
});

test('renewal history shows previous/new dates, time and applied result without secrets',()=>{
 const changed={...data,history:[{operation:'RENEWAL',occurred_at:'2026-10-29T12:00:00Z',actor_id:'demo-user',revision:2,previous_expires_on:'2026-10-01',expires_on:'2026-11-28',date_changed:true,result:'APPLIED'}]};
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:changed,tab:'history',onTab:()=>{}}));assert.match(html,/Abonelik uzatıldı/);assert.match(html,/Eski bitiş/);assert.match(html,/Yeni bitiş/);assert.match(html,/Sonuç: Uygulandı/);assert.match(html,/2026/);
});

test('missing router keeps subscriber detail and renders no invented router link',()=>{
 const missing={...data,item:{...data.item,router_name:null,router_model:null,router_missing:true,router_source:'UNKNOWN'}};
 assert.equal(safeSubscriberCenter(missing,missing.item.id),true);
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:missing,tab:'connections',onTab:()=>{}}));
 assert.match(html,/Router kaydı bulunamadı/);assert.match(html,/demo-managed-router-fixture/);assert.doesNotMatch(html,/href="#module=routers/);
});

test('failed per-record audit stays failed and never claims the business value changed',()=>{
 const changed={...data,history:[{operation:'STATUS',occurred_at:'2026-10-29T12:00:00Z',actor_id:'demo-user',revision:1,previous_expires_on:null,expires_on:null,date_changed:false,result:'FAILED',error:'Revizyon değişti',router_id:data.item.router_id,previous_values:{},new_values:{}}]};
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:changed,tab:'history',onTab:()=>{}}));assert.match(html,/Başarısız · Kayıt değiştirilmedi/);assert.match(html,/Revizyon değişti/);assert.doesNotMatch(html,/Sonuç: Uygulandı/);
});


test('history shows package context together with changed expiry and Istanbul actor time',()=>{
 const history=[{operation:'RENEWAL',occurred_at:'2026-11-05T21:30:00Z',actor_id:'synthetic.operator',revision:2,date_changed:true,previous_expires_on:'2026-11-01',expires_on:'2026-12-06',previous_values:{plan:'Historical 100',expires_on:'2026-11-01'},new_values:{plan:'Historical 100',expires_on:'2026-12-06'},result:'APPLIED'}];
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,history},tab:'history',onTab(){}}));
 assert.match(html,/Historical 100/);assert.match(html,/synthetic.operator/);assert.match(html,/6 Kas 2026/);assert.match(html,/00:30/);assert.match(html,/İstanbul/);assert.match(html,/Eski bitiş:/);assert.match(html,/Yeni bitiş:/);
});

const policyCode=buildSync({entryPoints:[fileURLToPath(new URL('../src/lib/subscriberActions.ts',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text;
const policy={exports:{}};new Function('module','exports',policyCode)(policy,policy.exports);
test('shared action policy rejects wrong source, permission, persistence and router bindings',()=>{
 const detail={is_demo:true,persistence:'local-postgresql-demo',item:{...data.item,id:'demo-sub-fixture',is_demo:true,can_manage_pppoe:true}};
 assert.equal(policy.exports.canChangeLegacy(detail),true);
 for(const patch of [{persistence:'process-memory'},{is_demo:false},{item:{...detail.item,source:null}},{item:{...detail.item,can_manage_pppoe:false}},{item:{...detail.item,router_id:null}},{item:{...detail.item,is_demo:false}}])assert.equal(policy.exports.canChangeLegacy({...detail,...patch}),false);
 assert.equal(policy.exports.canChangeLegacy(detail,'demo-sub-other'),false);
 assert.equal(policy.exports.canChangeWorkspace(data,true),true);
 assert.equal(policy.exports.canChangeWorkspace(data,false),false);
 for(const patch of [{source:null},{router_missing:true},{router_source:'UNKNOWN'},{access_type:null}])assert.equal(!!policy.exports.canChangeWorkspace({...data,item:{...data.item,...patch}},true),false);
});
test('workspace actions keep direct preset callbacks and history navigation in the current center',()=>{
 const calls=[];let selected;
 const props={data,onTab(value){selected=value;},onEdit:r=>calls.push(['edit',r]),onRenew:r=>calls.push(['renew',r]),onManage:(r,action)=>calls.push(['manage',r,action])};
 const tree=module.exports.SubscriberDeviceCenterView({...props,tab:'actions'});
 const menu=nodes(tree).find(n=>n.props?.className==='subscriber-actions-menu');assert.ok(menu);
 const shared=nodes(menu).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons');assert.ok(shared);
 const buttons=nodes(shared.type(shared.props)).filter(n=>n.type==='button');
 const event={currentTarget:{closest:()=>null}};
 for(const [label,expected] of [['Abonelik Uzat',['renew',data.item]],['Paket Değiştir',['manage',data.item,'PLAN']],['Hesabı Kapat',['manage',data.item,'STATUS']]]){
  const button=buttons.find(n=>n.props.children===label);assert.ok(button);button.props.onClick(event);assert.deepEqual(calls.at(-1),expected);
 }
 buttons.find(n=>n.props.children==='İşlem Geçmişi').props.onClick(event);assert.equal(selected,'history');
 nodes(menu).find(n=>n.type==='button'&&n.props.children==='Abone bilgilerini düzenle').props.onClick();assert.deepEqual(calls.at(-1),['edit',data.item]);
 for(const tab of ['overview','history','connections'])assert.equal(nodes(module.exports.SubscriberDeviceCenterView({...props,tab})).some(n=>n.props?.className==='subscriber-actions-menu'),false);
 for(const patch of [{source:null},{router_missing:true},{router_source:'UNKNOWN'}]){
  const denied=module.exports.SubscriberDeviceCenterView({...props,data:{...data,item:{...data.item,...patch}},tab:'actions'});
  const surface=nodes(denied).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons');
  assert.equal(surface.props.onAction,undefined);assert.deepEqual(nodes(surface.type(surface.props)).filter(n=>n.type==='button').map(n=>n.props.children),['İşlem Geçmişi']);
 }
});
test('legacy detail exposes existing quick action surface without hiding it in demo disclosure',()=>{
 const legacy={...data,source:'LEGACY_DEMO',persistence:'local-postgresql-demo',item:{...data.item,id:'demo-sub-fixture',router_id:'demo-router-fixture',router_source:'STATIC_DEMO'}};
 const tree=module.exports.SubscriberDeviceCenterView({data:legacy,tab:'actions',onTab(){}});
 const surface=nodes(tree).find(n=>typeof n.type==='function'&&n.type.name==='LegacySubscriberActions');
 assert.ok(surface);assert.equal(surface.props.id,legacy.item.id);
});

test('legacy direct buttons select the existing modal action and deny unauthorized records',()=>{
 const built=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/LegacySubscriberActions.tsx',import.meta.url))],bundle:true,loader:{'.css':'empty'},write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 let action=null,allowed=true;
 const detail={is_demo:true,persistence:'local-postgresql-demo',item:{...data.item,id:'demo-sub-fixture',is_demo:true,can_manage_pppoe:true}};
 const mock={...hooks,useCallback:fn=>fn,useState:initial=>{
  if(initial?.path)return [{...initial,loading:false,data:{...detail,item:{...detail.item,can_manage_pppoe:allowed}}},()=>{}];
  if(initial===null)return [action,value=>{action=value;}];
  return [initial,()=>{}];
 }};
 const mod={exports:{}};new Function('require','module','exports',built)(name=>name==='react'?mock:require(name),mod,mod.exports);
 const render=()=>mod.exports.LegacySubscriberActions({id:detail.item.id});
 for(const value of ['EXTEND','PLAN','STATUS']){
  const surface=nodes(render()).find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons');assert.ok(surface);surface.props.onAction(value);
  const dialog=nodes(render()).find(n=>typeof n.type==='function'&&n.type.name==='QuickActions');assert.ok(dialog);assert.equal(dialog.props.initialAction,value);assert.equal(dialog.props.rows[0].id,detail.item.id);dialog.props.onClose();
 }
 allowed=false;const denied=nodes(render());assert.equal(denied.find(n=>typeof n.type==='function'&&n.type.name==='SubscriberQuickButtons').props.onAction,undefined);assert.equal(denied.some(n=>typeof n.type==='function'&&n.type.name==='QuickActions'),false);
});

test('history shows UUID and historical/current revisions separately and retains return filters in links',()=>{
 const before=globalThis.window,hash='#module=subscribers&workspace=PERSISTENT&id='+data.item.id+'&tab=history&workspace_page=2';globalThis.window={location:{hash}};
 try{
  const event={request_id:'12345678-1234-4234-8234-123456789abc',source:'LOCAL',operation:'PLAN',occurred_at:'2026-11-08T10:00:00Z',actor_id:'synthetic',revision:2,result:'FAILED',error:'Revizyon değişti.',router_id:data.item.router_id,date_changed:false};
  const tree=module.exports.SubscriberDeviceCenterView({data:{...data,item:{...data.item,revision:7},history:[event]},tab:'history',onTab(){}}),html=renderToStaticMarkup(tree);
  assert.match(html,/İşlem UUID: 12345678/);assert.match(html,/İşlem revizyonu: 2/);assert.match(html,/Güncel abonelik revizyonu: 7/);assert.match(html,/Başarısız · Kayıt değiştirilmedi/);assert.match(html,/Yetkili kaynak: LOCAL/);
  const links=nodes(tree).filter(node=>node.type==='a'&&node.props.href?.includes('return_to='));
  assert.ok(links.some(node=>new URLSearchParams(node.props.href.slice(1)).get('module')==='routers'));
  for(const link of links)assert.equal(new URLSearchParams(link.props.href.slice(1)).get('return_to'),hash);
  assert.doesNotMatch(html,/Uygulandı · Sentetik kayıt/);
 }finally{globalThis.window=before;}
});


test('summary preserves exact account values and keeps expiry independent of account activity',()=>{
 const item={...data.item,customer_name:'Örnek Abone',username:'pppoe.example',plan:'Paket 200',status:'PAUSED',expires_on:'2099-12-31'};
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,item},tab:'overview',onTab(){}}));
 for(const value of ['Örnek Abone','pppoe.example','Paket 200','Hesap pasif','31 Ara 2099','gün kaldı'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/canlı oturum ölçülmedi|Oturum durumu|subscriber-actions-menu/);
});

test('connection panel labels saved IP and times as synthetic and never infers a session',()=>{
 const item={...data.item,status:'ACTIVE',ip_address:'192.0.2.19',last_seen_at:'2026-11-05T21:30:00Z',last_connected_at:'2026-11-05T21:00:00Z'};
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,item},tab:'connections',onTab(){}}));
 for(const value of ['Sentetik kayıt IP adresi','192.0.2.19','Son sentetik örnek','Kaydedilmiş bağlantı zamanı (sentetik)','6 Kas 2026','00:30','Bilinmiyor · canlı oturum ölçülmedi','Bilinmiyor · bağlantı kanıtı yok'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/Çevrimiçi|Oturum açık|Bağlı oturum/);
 const empty=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,item:{...data.item,ip_address:'—',last_seen_at:'invalid'}},tab:'connections',onTab(){}}));
 assert.match(empty,/Ölçülmedi/);assert.doesNotMatch(empty,/Geçersiz tarih|>—</);
});

test('history preserves both sides and all missing fields have explicit empty states',()=>{
 const history=[{operation:'STATUS',occurred_at:'2026-11-05T21:30:00Z',actor_id:'test.operator',revision:2,result:'APPLIED',date_changed:false,previous_values:{status:'ACTIVE',plan:'Eski Paket'},new_values:{status:'PAUSED',plan:'Yeni Paket'}}];
 const html=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,history},tab:'history',onTab(){}}));
 for(const value of ['Önceki değerler','Yeni değerler','Eski Paket','Yeni Paket','Etkin','Devre dışı','test.operator','6 Kas 2026','00:30'])assert.ok(html.includes(value),value);
 const missing=renderToStaticMarkup(module.exports.SubscriberDeviceCenterView({data:{...data,history:[{operation:'',occurred_at:'invalid',actor_id:'',revision:null,date_changed:false}]},tab:'history',onTab(){}}));
 assert.match(missing,/Veri yok/);assert.doesNotMatch(missing,/undefined|null|Geçersiz tarih|Uygulandı/);
});

test('supplement is routed by active section and cannot introduce a duplicate audit panel',()=>{
 const seen=[];
 for(const tab of ['overview','actions','history','connections']){
  const tree=module.exports.SubscriberDeviceCenterView({data,tab,onTab(){},legacy:active=>{seen.push(active);return React.createElement('aside',null,'extra details');}});
  const html=renderToStaticMarkup(tree);
  assert.equal(html.includes('extra details'),tab!=='history');
 }
 assert.deepEqual(seen,['overview','actions','history','connections']);
});
