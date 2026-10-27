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
 for(const label of ['Bugün','Dün','Son 7 Gün','İşlem / olay','Filtreleri temizle','SENTETİK','geçmişe ait durum tahmini değildir'])assert.ok(html.includes(label));
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
  const dashboard=renderToStaticMarkup(createElement(Dashboard,{onNavigate(){}}));assert.match(dashboard,/Günlük Yönetim Raporu/);
  globalThis.window.location.hash='#module=dashboard&view=DAILY_REPORT&period=TODAY';
  const report=renderToStaticMarkup(createElement(Dashboard,{onNavigate(){}}));assert.match(report,/Merkezi Günlük Yönetim Raporu/);assert.match(report,/Dashboard’a dön/);
 }finally{globalThis.window=previous;delete globalThis.__dailySummary;delete globalThis.__reportResource;}
});
