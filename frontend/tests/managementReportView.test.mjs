import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const require=createRequire(import.meta.url);
async function compile(path){
 const result=await build({entryPoints:[fileURLToPath(new URL(path,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'saved-report-source',setup(builder){
  builder.onResolve({filter:/lib\/useResource$/},()=>({path:'report-resource',namespace:'test'}));
  builder.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){return path==="/dashboard/summary"?{data:globalThis.__dailySummary,loading:false,retry(){}}:path==="/management/report"?globalThis.__reportResource:{data:null,loading:false,retry(){}}}',loader:'js'}));
 }}]});
 const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(require,module,module.exports);return module.exports;
}
const {ManagementReport}=await compile('../src/screens/ManagementReport.tsx');
const {Dashboard}=await compile('../src/screens/Dashboard.tsx');
const now=new Date().toISOString();
const routers=[{id:'r & 1',name:'Sentetik router',status:'ONLINE',is_demo:true}];
const details=[{item:{id:'s & 1',customer_name:'Demo kişi',username:'demo.test',router_id:'r & 1',router_name:'Sentetik router',source:'LOCAL',status:'ACTIVE',expires_on:null,is_demo:true},is_demo:true,history:[{id:'op1',occurred_at:now,operation:'RENEWAL',actor_id:'demo-user',is_demo:true,source:'LOCAL'}]}];
const data={routers,details,events:null,read_at:now};
function render(resource){globalThis.__reportResource=resource;try{return renderToStaticMarkup(createElement(ManagementReport,{onBack(){}}));}finally{delete globalThis.__reportResource;}}
test('report renders named filters, synthetic labels, current-state scope and encoded detail links',()=>{
 const html=render({data,loading:false,retry(){}});
 for(const label of ['Bugün','Dün','Son 7 Gün','Son 30 Gün','İşlem / olay','Filtreleri temizle','SENTETİK','geçmişe ait durum tahmini değildir'])assert.ok(html.includes(label));
 assert.match(html,/href="#module=subscribers&amp;id=s\+%26\+1"/);assert.match(html,/href="#module=routers&amp;id=r\+%26\+1"/);
 assert.match(html,/Kaydedilmiş olay kaynağı yok/);assert.match(html,/aria-label="Günlük yönetim işlemleri tablosu"/);
 assert.doesNotMatch(html,/href="#module=routers&amp;id=undefined"/);
});
test('loading and failed sources never render success counters or a fake empty report',()=>{
 const loading=render({loading:true,retry(){}});assert.match(loading,/Veriler yükleniyor/);assert.doesNotMatch(loading,/Son kayıtlı envanter ve abonelik durumu/);
 const failed=render({loading:false,error:'Demo kaynağa erişilemiyor',retry(){}});assert.match(failed,/role="alert"/);assert.match(failed,/Tekrar dene/);assert.doesNotMatch(failed,/Seçili dönemin işlem ve olay toplamları/);
 const empty=render({data:{routers:[],details:[],events:[],read_at:now},loading:false,retry(){}});assert.match(empty,/Filtrelerle eşleşen kayıtlı yönetim işlemi yok/);assert.match(empty,/Filtrelerle eşleşen kayıtlı bağlantı olayı yok/);
});
test('Dashboard opens the report in its existing module and direct report links reload correctly',()=>{
 const previous=globalThis.window;globalThis.__dailySummary=buildDailySummary(routers,details);globalThis.__reportResource={data,loading:false,retry(){}};
 try{
  globalThis.window={location:{hash:''}};
  const dashboard=renderToStaticMarkup(createElement(Dashboard,{onNavigate(){}}));assert.match(dashboard,/Günlük Yönetim Merkezi/);
  globalThis.window.location.hash='#module=dashboard&view=DAILY_REPORT&period=TODAY';
  const report=renderToStaticMarkup(createElement(Dashboard,{onNavigate(){}}));assert.match(report,/Günlük Yönetim Merkezi · V2.3/);assert.match(report,/Dashboard’a dön/);
 }finally{globalThis.window=previous;delete globalThis.__dailySummary;delete globalThis.__reportResource;}
});

test('V2.3 expiry navigation and missing histories are explicit',()=>{
 const html=render({data:{...data,details:details.map(d=>({...d,history_available:false}))},loading:false,retry(){}});
 for(const text of ['İşlem kaynağı eksik; toplam Veri yok','3 gün','7 gün','30 gün','İlgili abone listesini aç','Merkezi İşlem Geçmişini aç','Kalıcı abonelerin bitişleri'])assert.ok(html.includes(text),text);
 assert.match(html,/workspace=LEGACY&amp;expiry=TODAY/);
 assert.equal((html.match(/class="metric-card"/g)??[]).length,4);
 assert.match(html,/<details class="panel management-notes"><summary>Veri kapsamı/);
 assert.doesNotMatch(html,/Abonelik Takip ve Uyarı Merkezi|Toplam router/);
});
test('V2.3 real source never substitutes synthetic operations or fabricated history totals',()=>{
 const previous=globalThis.window;
 try{
  globalThis.window={location:{hash:'#module=dashboard&view=DAILY_REPORT&report_source=V1_INVENTORY'}};
  const html=render({data,loading:false,retry(){}});
  assert.match(html,/GERÇEK V1 · SALT OKUNUR/);
  assert.match(html,/Gerçek işlem geçmişi bağlı değil/);
  assert.doesNotMatch(html,/Seçili dönemin işlem ve olay toplamları|Demo kişi|PPPoE işlem detayları:/);
 }finally{globalThis.window=previous;}
});

test('V2.3 compact event row keeps kind, router, time, status and WAN values without technical IDs',()=>{
 const html=render({data:{...data,events:[{id:'technical-audit-identifier',kind:'WAN_CHANGE',router_id:routers[0].id,started_at:now,occurred_at:now,status:'RECORDED',ended_at:null,recovery_id:null,duration_seconds:null,previous_wan:'Sentetik önce',new_wan:'Sentetik sonra',is_demo:true}]},loading:false,retry(){}});
 for(const text of ['WAN değişikliği','Kaydedildi','Sentetik önce','Sentetik sonra','Günlük bağlantı olayları tablosu'])assert.ok(html.includes(text));
 assert.doesNotMatch(html,/technical-audit-identifier/);
});
