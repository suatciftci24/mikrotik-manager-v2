import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {projectRouterEvents} from '../src/lib/routerEvents.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const require=createRequire(import.meta.url);
async function compile(path){
 const result=await build({entryPoints:[fileURLToPath(new URL(path,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'saved-resource',setup(builder){
  builder.onResolve({filter:/lib\/useResource$/},()=>({path:'saved-resource',namespace:'test'}));
  builder.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){return path===\"/dashboard/summary\"?{data:globalThis.__centralSummary,loading:false,retry(){}}:path==="/router-events"?{data:globalThis.__alarmData??null,loading:false,retry(){}}:{loading:true,retry(){}}}',loader:'js'}));
 }}]});
 const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(require,module,module.exports);return module.exports;
}
const {Dashboard}=await compile('../src/screens/Dashboard.tsx');
const {RouterDetails}=await compile('../src/screens/Details.tsx');
const router={id:'r',name:'Sentetik Router',site:'Demo konum',management_address:'192.0.2.11',model:'Demo model',routeros_version:'7.demo',status:'ONLINE',cpu_percent:24,memory_percent:null,uptime:'Demo uptime',subscriber_count:248,last_seen:'2026-10-26T09:42:00Z',is_demo:true};
test('central screen renders unknown/outage scope and existing rolling operation details',()=>{
 globalThis.__centralSummary=buildDailySummary([router],[]);
 try{
  const html=renderToStaticMarkup(createElement(Dashboard,{onNavigate(){}}));
  assert.match(html,/Merkezi Dashboard/);assert.match(html,/Durumu bilinmeyen/);
  assert.match(html,/İnternet kesintileri: Veri yok/);assert.match(html,/WAN değişiklikleri: Veri yok/);
  assert.match(html,/Son 24 saat PPPoE demo yönetim işlemleri/);
  assert.match(html,/PPPoE olarak kayıtlı: 0/);
  assert.match(html,/href="#module=operations&amp;kind=INTERNET_DOWN&amp;period=24H"/);
 }finally{delete globalThis.__centralSummary;}
});
test('router detail keeps WAN unknown, formats valid samples, and links only assigned subscribers',()=>{
 const assigned=[{id:'subscriber & one',customer_name:'Demo kişi',username:'demo.user',router_id:'r',router_name:'Eski ad',source:'RADIUS',status:'ACTIVE',plan:'Demo paket',access_type:'PPPOE'},{id:'wrong',customer_name:'Yanlış abone',router_id:'other',router_name:router.name}];
 const html=renderToStaticMarkup(createElement(RouterDetails,{detail:{item:router,assigned_subscribers:assigned,is_demo:true}}));
 assert.match(html,/WAN IP<\/dt><dd>Veri yok/);assert.match(html,/Default route<\/dt><dd>Veri yok/);
 assert.match(html,/Canlı bağlantı<\/dt><dd>Bilinmiyor/);assert.match(html,/24% \/ Veri yok/);
 assert.match(html,/12:42 \(İstanbul\)/);assert.match(html,/RADIUS/);
 assert.match(html,/Kayıtlı ilişkili abonelik<\/dt><dd>1/);
 assert.match(html,/href="#module=subscribers&amp;id=subscriber\+%26\+one"/);
 assert.doesNotMatch(html,/Yanlış abone/);assert.match(html,/Router kesinti ve WAN olay geçmişi/);
});

const {AlarmEvents,AlarmEventDetails}=await compile('../src/components/AlarmEvents.tsx');
test('same source drives dashboard counts and router-scoped list; detail retains WAN and Turkey time',()=>{
 const occurred_at=new Date().toISOString();
 globalThis.__alarmData=projectRouterEvents({available:true,is_demo:true,items:[
  {id:'wan-r',router_id:'r',kind:'WAN_CHANGE',occurred_at,previous_wan:'wan1 / 192.0.2.1',new_wan:'wan2 / 192.0.2.2',is_demo:true},
  {id:'down-other',router_id:'other',kind:'INTERNET_DOWN',occurred_at,state:'OPEN',is_demo:true},
 ]});
 try{
  const cards=renderToStaticMarkup(createElement(AlarmEvents,{mode:'cards',routers:[router]}));
  assert.match(cards,/İnternet kesintileri: 1/);assert.match(cards,/WAN değişiklikleri: 1/);
  const list=renderToStaticMarkup(createElement(AlarmEvents,{routerId:'r',routers:[router]}));
  assert.match(list,/wan-r/);assert.doesNotMatch(list,/down-other/);
  const detail=renderToStaticMarkup(createElement(AlarmEventDetails,{event:globalThis.__alarmData.find(event=>event.id==='wan-r'),routerName:router.name,onClose(){}}));
  assert.match(detail,/wan1 \/ 192.0.2.1/);assert.match(detail,/wan2 \/ 192.0.2.2/);assert.match(detail,/İstanbul/);assert.match(detail,/Süre<\/dt><dd>Veri yok/);
 }finally{delete globalThis.__alarmData;}
});
test('alarm center exposes intersecting filters even with unavailable event coverage',()=>{
 const html=renderToStaticMarkup(createElement(AlarmEvents,{routers:[router]}));
 for(const label of ['Olay türü','Durum','Başlangıç günü','Bitiş günü','Filtreleri temizle'])assert.ok(html.includes(label));
 assert.match(html,/olay kaynağı bulunmuyor/);assert.doesNotMatch(html,/<tbody>/);
});
