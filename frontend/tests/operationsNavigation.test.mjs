import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let effects=[],calls=[],states=[],initialStates=[],selectedEvent=null,identity=null;
const hooks={...React,useCallback:fn=>fn,useContext:()=>identity,useEffect:fn=>effects.push(fn),useRef:()=>({current:{scrollIntoView:()=>calls.push('scroll'),focus:()=>calls.push('focus')}}),useState:value=>{const initial=value===null&&selectedEvent?selectedEvent:typeof value==='function'?value():value;initialStates.push(initial);return [initial,next=>states.push(next)];}};
const result=await build({stdin:{contents:"export {ResourceState} from './src/components/Resource';export {SyntheticSubscriberList} from './src/components/SyntheticSubscribers';export {SubscriberOperationHistory} from './src/components/SubscriberDailyActions';export {OperationReport} from './src/screens/OperationReport';export {ManagementReport} from './src/screens/ManagementReport';export {OperationDetails} from './src/components/OperationDetails';export {SubscriberDeviceCenter} from './src/components/SubscriberDeviceCenter';",resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'resource',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'resource',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){globalThis.__navigationQueries?.push(path);return globalThis.__navigationResources?.[path.split("?")[0]]??globalThis.__navigationResource}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(name=>name==='react'?hooks:require(name),module,module.exports);
function draw(hash,state){
 globalThis.window={location:{hash}};globalThis.__navigationResource=state;effects=[];calls=[];
 const tree=module.exports.ManagementReport({onBack(){}});
 const child=tree.props.children[1];
 if(typeof child.type==='function')child.type(child.props);
 return effects;
}
test('report scroll waits for validated data, handles empty results and avoids V1 and errors',()=>{
 const before=globalThis.window;
 const hash='#module=dashboard&view=DAILY_REPORT&report_source=DEMO&period=LAST_24&kind=PPPOE&section=recent-operations';
 const data={routers:[],details:[],events:[],read_at:new Date().toISOString()};
 try{
  for(const state of [{loading:true},{loading:false,error:'Yetki gerekli'},{loading:false,data:{...data,routers:[{is_demo:false}]}}]){
   draw(hash,state).at(-1)();assert.deepEqual(calls,[]);
  }
  draw(hash,{data,loading:false}).at(-1)();assert.deepEqual(calls,['scroll','focus']);
  draw('#module=dashboard&view=DAILY_REPORT',{data,loading:false}).at(-1)();assert.deepEqual(calls,[]);
  assert.equal(draw(hash.replace('report_source=DEMO','report_source=V1_INVENTORY'),{data,loading:false}).length,1);
 }finally{globalThis.window=before;delete globalThis.__navigationResource;}
});

function nodes(tree){return !tree||typeof tree!=='object'?[]:[tree,...React.Children.toArray(tree.props?.children).flatMap(nodes)];}
test('operation detail closes before opening subscriber, router or existing history',()=>{
 const event={id:'op',subscriber_id:'s & 1',customer_name:'Demo',username:'demo',router_name:'Demo router',operation:'CREATE',source:'LOCAL',occurred_at:new Date().toISOString()};
 for(const [label,target] of [['Abone detayını aç','subscriber'],['Router detayını aç','router'],['İşlem geçmişini aç','history'],['Router alarmlarını aç','alarms'],['İlgili operasyon raporunu aç','report']]){
  const called=[];
  const tree=module.exports.OperationDetails({event,onClose:()=>called.push('close'),onSubscriber:id=>called.push(id),onRouter:()=>called.push('router'),onHistory:()=>called.push('history'),onAlarms:()=>called.push('alarms'),onReport:()=>called.push('report')});
  nodes(tree).find(node=>node.type==='button'&&node.props.children===label).props.onClick();
  assert.deepEqual(called,['close',target==='subscriber'?event.subscriber_id:target]);
 }
 const tree=module.exports.OperationDetails({event,onClose(){},onSubscriber(){}});
 assert.equal(nodes(tree).some(node=>node.type==='button'&&node.props.children==='Router detayını aç'),false);
});

test('subscriber history deep link selects existing tab and rejects unknown tabs',()=>{
 const before=globalThis.window;
 try{
  for(const [value,expected] of [['history','history'],['invalid','overview']]){
   globalThis.window={location:{hash:'#module=subscribers&id=s&tab='+value},scrollTo(){},addEventListener(){},removeEventListener(){}};
   globalThis.__navigationResource={loading:true};effects=[];states=[];initialStates=[];
   module.exports.SubscriberDeviceCenter({id:'s',onBack(){}});
   assert.equal(initialStates[0],expected);
  }
 }finally{globalThis.window=before;delete globalThis.__navigationResource;}
});

test('manual subscriber tab choice persists URL and keeps report return context',()=>{
 const before=globalThis.window,priorEvent=globalThis.HashChangeEvent;
 const back='#module=dashboard&view=DAILY_REPORT&period=LAST_24&kind=PPPOE&section=recent-operations';
 const params=new URLSearchParams({module:'subscribers',id:'demo-sub-test',workspace:'LEGACY',return_to:back});
 let replaced;globalThis.window={location:{hash:'#'+params,pathname:'/',search:''},history:{replaceState(_a,_b,url){replaced=url;}},dispatchEvent(){}};globalThis.HashChangeEvent=class {};
 globalThis.__navigationResource={loading:false,data:{item:{id:'demo-sub-test',session_status:'UNKNOWN'},is_demo:true,source:'LEGACY_DEMO',device_connection_started:false}};
 try{
  const tree=module.exports.SubscriberDeviceCenter({id:'demo-sub-test',onBack(){}});
  const view=nodes(tree).find(node=>typeof node.type==='function'&&node.props.onTab);
  view.props.onTab('history');
  const result=new URLSearchParams(replaced.split('#')[1]);
  assert.equal(result.get('tab'),'history');assert.equal(result.get('return_to'),back);assert.equal(result.get('id'),'demo-sub-test');
 }finally{globalThis.window=before;globalThis.HashChangeEvent=priorEvent;delete globalThis.__navigationResource;}
});

test('operation audit detail exposes router and subscriber history with filtered return, hides stale dialog while loading',()=>{
 const before=globalThis.window;
 globalThis.window={location:{hash:'#module=dashboard&view=OPERATIONS_REPORT&category=AUDIT&page=2&router_id=demo-router-test'}};
 selectedEvent={id:'op',subscriber_id:'demo-sub-test',router_id:'demo-router-test',operation:'CREATE',is_demo:true};
 globalThis.__navigationResource={loading:false};
 try{
  let tree=module.exports.OperationReport();
  const dialog=nodes(tree).find(node=>node.props.event===selectedEvent);
  assert.equal(typeof dialog.props.onRouter,'function');dialog.props.onRouter();
  let params=new URLSearchParams(window.location.hash.slice(1));
  assert.equal(params.get('id'),'demo-router-test');assert.equal(params.get('source'),'DEMO');
  assert.equal(new URLSearchParams(params.get('return_to').slice(1)).get('page'),'2');
  dialog.props.onHistory();params=new URLSearchParams(window.location.hash.slice(1));
  assert.equal(params.get('id'),'demo-sub-test');assert.equal(params.get('tab'),'history');assert.equal(params.get('workspace'),'LEGACY');
  window.location.hash='#module=dashboard&view=OPERATIONS_REPORT&category=AUDIT';
  globalThis.__navigationResource={loading:true};tree=module.exports.OperationReport();
  assert.equal(nodes(tree).some(node=>node.props.event===selectedEvent),false);
 }finally{globalThis.window=before;selectedEvent=null;delete globalThis.__navigationResource;}
});

function fixture(hash,resource){
 const previous=globalThis.window,priorEvent=globalThis.HashChangeEvent;
 globalThis.HashChangeEvent=class {};
 globalThis.window={location:{hash,pathname:'/',search:''},history:{replaceState(_a,_b,url){window.location.hash='#'+url.split('#')[1];}},dispatchEvent(){}};
 globalThis.__navigationQueries=[];globalThis.__navigationResource=resource;
 globalThis.__navigationResources={'/router-workspace/routers':{loading:false,data:{items:[{id:'demo-managed-router-test',fields:{name:'Sentetik router'}}]}}};
 return ()=>{globalThis.window=previous;globalThis.HashChangeEvent=priorEvent;delete globalThis.__navigationResource;delete globalThis.__navigationResources;delete globalThis.__navigationQueries;};
}
const account={id:'demo-managed-sub-test',username:'sentetik.test',customer_name:'Sentetik Abone',access_type:'PPPOE',router_id:'demo-managed-router-test',router_name:'Sentetik router',router_source:'PERSISTENT_DEMO',source:'RADIUS',plan:'Sentetik paket',status:'ACTIVE',expires_on:null,session_status:'UNKNOWN'};
test('persistent list restores encoded query/router/status/page and resets page when searching, without losing return context',()=>{
 const back='#module=dashboard&view=DAILY_REPORT&period=LAST_24';
 const hash='#'+new URLSearchParams({module:'subscribers',workspace:'PERSISTENT',workspace_query:'Ali & Ayşe',workspace_router:account.router_id,workspace_status:'ACTIVE',workspace_access:'PPPOE',workspace_page:'2',return_to:back});
 const cleanup=fixture(hash,{loading:false,data:{items:[account],total:26,is_demo:true}});
 try{
  let opened;const tree=module.exports.SyntheticSubscriberList({onOpen:id=>opened=id,onCreate(){}});
  const params=new URLSearchParams(__navigationQueries[0].split('?')[1]);
  assert.equal(params.get('query'),'Ali & Ayşe');assert.equal(params.get('page'),'2');assert.equal(params.get('router_id'),account.router_id);assert.equal(params.get('status'),'ACTIVE');
  const html=renderToStaticMarkup(tree);assert.match(html,/RADIUS/);assert.match(html,/Bitiş tarihi bilinmiyor/);assert.match(html,/Kalıcı sentetik abone tablosu/);
  nodes(tree).find(node=>node.type==='button'&&node.props.children===account.customer_name).props.onClick();assert.equal(opened,account.id);
  nodes(tree).find(node=>node.type==='input'&&node.props.maxLength===120).props.onChange({target:{value:'yeni arama'}});
  const changed=new URLSearchParams(window.location.hash.slice(1));assert.equal(changed.get('workspace_query'),'yeni arama');assert.equal(changed.get('workspace_page'),null);assert.equal(changed.get('return_to'),back);
  nodes(tree).find(node=>node.type==='button'&&node.props.children==='Filtreleri temizle').props.onClick();
  const reset=new URLSearchParams(window.location.hash.slice(1));for(const key of ['workspace_query','workspace_router','workspace_status','workspace_access','workspace_page'])assert.equal(reset.has(key),false);assert.equal(reset.get('workspace'),'PERSISTENT');
 }finally{cleanup();}
});
test('persistent list separates loading, access errors, invalid source and an empty page after records change',()=>{
 for(const [resource,expected,table] of [
  [{loading:true},/Veriler yükleniyor/,false],
  [{loading:false,error:'API yanıtı: 403'},/görüntüleme yetkiniz yok/,false],
  [{loading:false,error:'Failed to fetch'},/Bağlantıyı kontrol/,false],
  [{loading:false,data:{items:[account],total:1,is_demo:false}},/Sentetik abone kaynağı doğrulanamadı/,false],
  [{loading:false,data:{items:[],total:26,is_demo:true}},/Bu sayfada kayıt yok/,true],
  [{loading:false,data:{items:[],total:0,is_demo:true}},/Filtrelerle eşleşen sentetik abone yok/,true],
 ]){const cleanup=fixture('#module=subscribers&workspace=PERSISTENT&workspace_page=2',resource);try{const html=renderToStaticMarkup(module.exports.SyntheticSubscriberList({onOpen(){},onCreate(){}}));assert.match(html,expected);assert.equal(html.includes('synthetic-subscriber-table'),table);}finally{cleanup();}}
});
test('workspace history keeps source and filters and links exact subscriber/router with a reloadable return context',()=>{
 const hash='#module=subscribers&workspace=HISTORY&history_source=workspace&history_page=2&history_result=FAILED&history_operation=PLAN&history_id=demo-managed-sub-test';
 const receipt={request_id:'fixture',item_id:account.id,router_id:account.router_id,operation:'PLAN',success:false,recorded:true,previous:{plan:'Eski'},values:{},occurred_at:new Date().toISOString(),actor_id:'sentetik',error:'Sentetik işlem reddedildi'};
 const cleanup=fixture(hash,{loading:false,data:{items:[receipt],total:26,is_demo:true}});
 try{const tree=module.exports.SubscriberOperationHistory();const query=new URLSearchParams(__navigationQueries[0].split('?')[1]);assert.match(__navigationQueries[0],/^\/subscriber-workspace\/management\/history/);assert.equal(query.get('page'),'2');assert.equal(query.get('result'),'FAILED');assert.equal(query.get('operation'),'PLAN');assert.equal(query.get('item_id'),account.id);
  const links=nodes(tree).filter(node=>node.type==='a');assert.equal(links.length,2);
  const target=new URLSearchParams(links[0].props.href.slice(1));assert.equal(target.get('id'),account.id);assert.equal(target.get('workspace'),'PERSISTENT');assert.equal(target.get('return_to'),hash);
  assert.match(renderToStaticMarkup(tree),/Başarısız/);
 }finally{cleanup();}
});

test('daily operation context links keep router permission boundaries and recorded report day',()=>{
 const hash='#module=dashboard&view=DAILY_REPORT&period=LAST_24&kind=PPPOE&section=recent-operations';
 const stamp=new Date().toISOString();
 const item={id:'demo-sub-test',customer_name:'Sentetik',username:'sentetik.test',router_id:'demo-router-test',router_name:'Sentetik router',access_type:'PPPOE',source:'LOCAL',status:'ACTIVE',expires_on:null,is_demo:true};
 const event={id:'op',operation:'CREATE',occurred_at:stamp,actor_id:'sentetik',source:'LOCAL',is_demo:true};
 const resource={loading:false,data:{routers:[{id:item.router_id,name:item.router_name,is_demo:true,status:'ONLINE'}],details:[{item,is_demo:true,history:[event]}],events:[]}};
 const cleanup=fixture(hash,resource);selectedEvent={kind:'operation',id:'op'};
 try{
  for(const reportPermission of [false,true]){
   identity={permissions:{[item.router_id]:{can_view:true,can_view_reports:reportPermission}}};window.location.hash=hash;
   const root=module.exports.ManagementReport({onBack(){}}),report=root.props.children[1];
   const tree=report.type(report.props);const dialog=nodes(tree).find(node=>node.props.event?.id==='op');
   assert.equal(typeof dialog.props.onAlarms,'function');assert.equal(typeof dialog.props.onReport,reportPermission?'function':'undefined');
   dialog.props.onAlarms();const alarm=new URLSearchParams(window.location.hash.slice(1));assert.equal(alarm.get('alarm_router'),item.router_id);assert.equal(alarm.get('return_to'),hash);
  }
  identity={permissions:{[item.router_id]:{can_view:false,can_view_reports:true}}};window.location.hash=hash;
  const root=module.exports.ManagementReport({onBack(){}}),report=root.props.children[1];
  const dialog=nodes(report.type(report.props)).find(node=>node.props.event?.id==='op');assert.equal(dialog.props.onAlarms,undefined);assert.equal(dialog.props.onReport,undefined);
 }finally{cleanup();identity=null;selectedEvent=null;}
});

test('operation detail exposes exact UUID, historical revision, router and explicit audit outcome without guessing success',()=>{
 const event={id:'workspace:12345678-1234-4234-8234-123456789abc',request_id:'12345678-1234-4234-8234-123456789abc',workspace:true,revision:3,router_id:'demo-managed-router-test',subscriber_id:'demo-managed-sub-test',customer_name:'Sentetik',username:'synthetic',router_name:'Historical Router',source:'RADIUS',operation:'PLAN_CHANGE',occurred_at:new Date().toISOString(),is_demo:true};
 for(const outcome of ['APPLIED','UNKNOWN']){const html=renderToStaticMarkup(module.exports.OperationDetails({event:{...event,audit_result:outcome},onClose(){},onSubscriber(){}}));
  assert.match(html,/12345678-1234-4234-8234-123456789abc/);assert.doesNotMatch(html,/workspace:12345678/);assert.match(html,/İşlem revizyonu/);assert.match(html,/>3</);assert.match(html,/demo-managed-router-test/);assert.match(html,/RADIUS/);
  if(outcome==='APPLIED')assert.match(html,/Uygulandı · Kaydedilmiş audit/);else{assert.match(html,/başarı varsayılmaz/);assert.doesNotMatch(html,/Uygulandı · Kaydedilmiş audit/);}
 }
});
