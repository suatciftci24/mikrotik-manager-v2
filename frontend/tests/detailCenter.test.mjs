import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {routerDetailSummary,subscriberWarnings,assignedRouter,routerSubscribersHash,subscriberTextContext,unknownDetail} from '../src/lib/detailCenter.ts';
const require=createRequire(import.meta.url);
function compile(path,react=React){
 const code=buildSync({entryPoints:[fileURLToPath(new URL(path,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);return module.exports;
}
const router={id:'demo-router-001',name:'Demo · Router',model:'Demo model',routeros_version:'7.demo',management_address:'192.0.2.1',site:'Demo',status:'ONLINE',cpu_percent:0,memory_percent:10,subscriber_count:649,last_seen:'2026-10-28T09:00:00Z',uptime:'1g',is_demo:true};
const subscriber={can_manage_pppoe:true,id:'demo-sub-test',router_id:router.id,router_name:router.name,username:'demo.test',customer_name:'Test Abone',source:'LOCAL',access_type:'PPPOE',plan:'Fiber 100',monthly_price:549.9,status:'PAUSED',expires_on:'2026-10-30',revision:1,last_seen:null,joined_at:'2026-10-28',ip_address:'—',is_demo:true};
const detail={item:subscriber,is_demo:true,persistence:'local-postgresql-demo',history:[{id:'demo-event-id',operation:'CREATE',actor_id:'demo-user',occurred_at:'2026-10-28T09:00:00Z',previous_values:{},new_values:{plan:'Fiber 100'},source:'LOCAL',is_demo:true}]};
function nodes(element){return element&&typeof element==='object'?[element,...React.Children.toArray(element.props?.children).flatMap(nodes)]:[];}

test('router summary uses explicit assignment, real record counts and independent expiry warnings',()=>{
 const rows=[subscriber,{...subscriber,id:'expired',status:'ACTIVE',expires_on:'2026-10-27'},
  {...subscriber,id:'foreign',router_id:'other',router_name:router.name},
  {...subscriber,id:'legacy',router_id:null,access_type:null,expires_on:null}];
 const summary=routerDetailSummary(router,rows,'2026-10-28');
 assert.equal(summary.total,3);assert.equal(summary.pppoe,2);assert.equal(summary.active,1);assert.equal(summary.paused,2);
 assert.equal(summary.alerts.expired,1);assert.equal(summary.alerts.within_7,1);assert.equal(summary.alerts.unknown,1);
 assert.notEqual(summary.total,router.subscriber_count);
 assert.throws(()=>routerDetailSummary(router,[subscriber,subscriber],'2026-10-28'),/tekil/);
 assert.throws(()=>routerDetailSummary({...router,is_demo:false},[],'2026-10-28'),/sentetik/);
});
test('unknown detail fields stay explicit while recorded text is preserved',()=>{
 for(const value of [null,undefined,'','—','Veri yok'])assert.equal(unknownDetail(value),'Bilinmiyor');
 assert.equal(unknownDetail('7.demo'),'7.demo');
});
test('subscriber warnings never equate active account with online session',()=>{
 assert.deepEqual(subscriberWarnings({...subscriber,status:'ACTIVE',expires_on:'2026-12-31'},'2026-10-28'),[]);
 assert.match(subscriberWarnings({...subscriber,source:null,expires_on:null},'2026-10-28').join(' '),/Yetkili kaynak bilinmiyor/);
 assert.match(subscriberWarnings({...subscriber,expires_on:'2026-10-28'},'2026-10-28').join(' '),/bugün bitiyor/);
 assert.match(subscriberWarnings({...subscriber,expires_on:'2026-10-27'},'2026-10-28').join(' '),/1 gün önce/);
});
test('router links prefer ID, reject ambiguous fallback and preserve encoded filter context',()=>{
 assert.equal(assignedRouter(subscriber,[router]),router);
 assert.equal(assignedRouter({...subscriber,router_id:'missing'},[router]),undefined);
 assert.equal(assignedRouter({...subscriber,router_id:null},[router,{...router,id:'other'}]),undefined);
 const hash=routerSubscribersHash('İstanbul & Merkez');
 assert.equal(subscriberTextContext(hash,'router'),'İstanbul & Merkez');
 assert.equal(subscriberTextContext('#module=routers&query=abc','query'),'');
 assert.equal(subscriberTextContext('#module=subscribers&query=demo&router=x&id=a','query'),'demo');
 assert.equal(new URLSearchParams(hash.slice(1)).has('id'),false);
});
test('actual router detail renders evidence boundaries and never manufactures traffic/IPsec',()=>{
 const {RouterDetails}=compile('../src/screens/Details.tsx');
 const html=renderToStaticMarkup(React.createElement(RouterDetails,{detail:{item:router,assigned_subscribers:[subscriber],is_demo:true}}));
 for(const text of ['Router yönetim özeti','Demo model','7.demo','WAN / IPsec','Router trafik ölçümleri','İndirme','Bilinmiyor','toplu uzatmaya git'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/0 (?:GB|MiB|Mbps)/);
 assert.match(html,/Canlı oturum sayımı değildir/);
});
test('subscriber details expose shared quick operations, audit identity and blocked unknown authority',()=>{
 const {SubscriberDetails}=compile('../src/screens/Details.tsx');
 const html=renderToStaticMarkup(React.createElement(SubscriberDetails,{detail,onQuick(){}}));
 for(const text of ['Abonelik uyarıları','Demo paket/profil değiştir','7 / 15 / 30 gün uzat veya özel tarih','Aynı routerda toplu uzatmaya git','demo-event-id','demo-user'])assert.ok(html.includes(text),text);
 const blocked=renderToStaticMarkup(React.createElement(SubscriberDetails,{detail:{...detail,item:{...subscriber,source:null}},onQuick(){}}));
 assert.match(blocked,/Kaynak bilinmiyor/);
 assert.equal((blocked.match(/<button[^>]*disabled=""/g)||[]).length,3);
});
test('detail quick modal stays mounted with same subscriber snapshot during loading and error',()=>{
 let states=[],index=0;
 let resource={path:'/subscribers/'+subscriber.id,data:detail,loading:false};
 const hooks={...React,useRef:()=>({current:null}),useEffect(){},useCallback:fn=>fn,
  useState(initial){const i=index++;if(initial&&typeof initial==='object'&&'path'in initial)return[resource,()=>{}];
   if(!(i in states))states[i]=typeof initial==='function'?initial():initial;
   return[states[i],value=>{states[i]=typeof value==='function'?value(states[i]):value;}];}};
 const {DetailCenter}=compile('../src/screens/Details.tsx',hooks);
 const render=()=>{index=0;return nodes(DetailCenter({kind:'subscribers',id:subscriber.id,onBack(){}}));};
 let tree=render();tree.find(n=>n.type?.name==='SubscriberDetails').props.onQuick('EXTEND');
 tree=render();const first=tree.find(n=>n.props?.initialAction==='EXTEND');assert.ok(first);
 for(const next of [{...resource,loading:true},{path:resource.path,loading:false,error:'HTTP failure'}]){
  resource=next;tree=render();const modal=tree.find(n=>n.props?.initialAction==='EXTEND');
  assert.ok(modal);assert.equal(modal.props.rows[0],first.props.rows[0]);
 }
});

test('quick preview cannot run before router/catalog data are ready',()=>{
 const {QuickActions}=compile('../src/components/QuickActions.tsx');
 const html=renderToStaticMarkup(React.createElement(QuickActions,{rows:[subscriber],today:'2026-10-28',initialAction:'PLAN',onClose(){}}));
 assert.match(html,/Router\/paket bilgileri yükleniyor/);
 assert.match(html,/<button[^>]*disabled=""[^>]*>Önizle ve gözden geçir<\/button>/);
});


test('quick action select labels exclude option text and catalog errors',()=>{
 const {QuickActions}=compile('../src/components/QuickActions.tsx');
 for(const [initialAction,label,key] of [['PLAN','Yeni paket','plan'],['STATUS','Yeni durum','status'],['EXTEND','Uzatma','extension']]){
  const html=renderToStaticMarkup(React.createElement(QuickActions,{rows:[subscriber],today:'2026-10-28',initialAction,onClose(){}}));
  const match=html.match(new RegExp(`<span id="([^"]+-${key})">${label}</span><select[^>]*aria-labelledby="([^"]+)"`));
  assert.ok(match,`${initialAction}: select references a text-only label`);
  assert.equal(match[1],match[2]);
  assert.ok(html.includes('<option'),`${initialAction}: real selection options remain rendered`);
 }
});
