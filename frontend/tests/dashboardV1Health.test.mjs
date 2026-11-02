import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const bundle=buildSync({stdin:{contents:"export {dashboardV1Health} from './src/lib/dashboardV1Health';export {DashboardV1HealthView} from './src/components/DashboardV1Health';export {Dashboard} from './src/screens/Dashboard';export {PermissionContext} from './src/lib/permissions';export {DemoBanner} from './src/components/Header';",resolveDir:process.cwd()},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:undefined});
const module={exports:{}};new Function('require','module','exports',bundle.outputFiles[0].text)(require,module,module.exports);
const {dashboardV1Health,DashboardV1HealthView,Dashboard,PermissionContext,DemoBanner}=module.exports;
const now=Date.parse('2026-11-02T10:00:00Z');
const row={id:'fixture-real-contract-1',name:'Fixture V1 router',identity:null,model:'Fixture model',routeros_version:'7.fixture',status:'NO_DATA',health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'17',connection_status:'LAST_PROBE_SUCCEEDED',sampled_at:'2026-11-02T09:59:00Z',cpu_load_percent:0,memory_used_percent:35,freshness:'RECENT'};
const data={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:[row]};
const view=(extra={})=>renderToStaticMarkup(createElement(DashboardV1HealthView,{data,loading:false,retry(){},now,lastSuccess:now,...extra}));
test('V2.5 model derives recent/stale/missing from actual health provenance and sample time',()=>{
 const input={...data,items:[row,{...row,id:'old',freshness:'RECENT',sampled_at:'2026-11-02T09:00:00Z'},{...row,id:'inventory-only',health_source:null,health_sample_id:null},{...row,id:'missing',sampled_at:null}]};
 const summary=dashboardV1Health(input,now);assert.deepEqual([summary.total,summary.recent,summary.stale,summary.missing],[4,1,1,2]);
 assert.equal(dashboardV1Health(data,now+240000).recent,1);assert.equal(dashboardV1Health(data,now+240001).stale,1);
 assert.equal(summary.rows[2].measured,false);assert.equal(summary.rows[3].measured,false);
});
test('V2.5 rejects demo, invalid metrics, duplicate identities and contradictory availability',()=>{
 for(const input of [{...data,is_demo:true},{...data,items:[row,row]},{...data,items:[{...row,memory_used_percent:101}]},{...data,availability:'NO_DATA'},{...data,items:[]},null])assert.throws(()=>dashboardV1Health(input,now),/doğrulanamadı/);
 assert.deepEqual(dashboardV1Health({...data,availability:'NO_DATA',items:[]},now).total,0);
});
test('V2.5 view keeps CPU zero, probe uncertainty, Istanbul sample time and unknown snapshot time separate',()=>{
 const html=view();for(const text of ['0% / 35%','Son deneme başarılı','2 Kas 2026 12:59','Son başarılı API yenileme:','Snapshot oluşturma/aktarım zamanı: Veri yok','Bu kaynakta sunulmuyor','PPPoE işlemleri','Router Merkezi’ni aç'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/ONLINE|Aktif oturum: 1|Sentetik abone/);
 assert.match(html,/href="#module=routers&amp;source=V1_INVENTORY"/);
 const inventoryOnly=view({data:{...data,items:[{...row,health_source:null,health_sample_id:null}]}});assert.doesNotMatch(inventoryOnly,/0% \/ 35%|Son deneme başarılı|2 Kas 2026 12:59/);
});
test('V2.5 loading, failure and malformed data hide all retained rows and counters',()=>{
 for(const override of [{loading:true},{error:'Kaynak kapalı'},{data:{...data,is_demo:true}},{data:null}]){const html=view(override);assert.doesNotMatch(html,/Fixture V1 router|0% \/ 35%/);assert.equal((html.match(/<strong>Veri yok<\/strong>/g)??[]).length,5);}
 const empty=view({data:{...data,availability:'NO_DATA',items:[]}});assert.match(empty,/Gerçek envanter aktarımı boş/);assert.doesNotMatch(empty,/<tbody>/);
});
test('V2.5 source deep link mounts real-only UI for admin and denies restricted user without demo fallback',()=>{
 const prior=globalThis.window;globalThis.window={location:{hash:'#module=dashboard&dashboard_source=V1_INVENTORY'}};
 try{
 const html=renderToStaticMarkup(createElement(PermissionContext.Provider,{value:{role_code:'ADMIN',can_manage_users:true}},createElement(Dashboard,{onNavigate(){}})));
 assert.match(html,/GERÇEK V1 · SALT OKUNUR/);assert.match(html,/Bu kaynakta sunulmuyor/);assert.doesNotMatch(html,/overview-status-grid|PPPoE veri kaynağı ve tazelik|Mevcut demo aboneleri/);
 const denied=renderToStaticMarkup(createElement(PermissionContext.Provider,{value:{role_code:'VIEWER'}},createElement(Dashboard,{onNavigate(){}})));assert.match(denied,/merkezi yönetici yetkisi gerekli/);assert.doesNotMatch(denied,/dashboard-real-table|overview-status-grid/);
 }finally{globalThis.window=prior;}
});
test('V2.5 shell labels real data as read-only rather than synthetic demo',()=>{
 const html=renderToStaticMarkup(createElement(DemoBanner,{realInventory:true}));assert.match(html,/Gerçek V1 aktarımı/);assert.doesNotMatch(html,/Veriler sentetiktir/);

});
