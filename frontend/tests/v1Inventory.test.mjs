import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {buildSync} from 'esbuild';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
function load(entry){const code=buildSync({entryPoints:[entry],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;const module={exports:{}};new Function('require','module','exports',code)(require,module,module.exports);return module.exports;}
const ui=load('src/components/V1Inventory.tsx');
const {inventoryRefresh}=load('src/lib/inventoryRefresh.ts');
const row={id:'1',name:'Fixture',model:null,identity:null,routeros_version:null,status:'NO_DATA',sampled_at:'2020-01-01T00:00:00Z',cpu_load_percent:0,memory_used_percent:null,health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'17',connection_status:'LAST_PROBE_SUCCEEDED',freshness:'STALE'};
const data={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:[row]};
const view=(override={})=>renderToStaticMarkup(ui.V1InventoryView({data,loading:false,retry:()=>{},...override}));
test('compact table separates metrics and moves technical data into detail',()=>{
 const html=view();
 for(const text of ['Fixture','0%','Veri yok','Güncel değil','03:00','İstanbul','Son internet denemesi başarılı','canlı çevrimiçi durum kanıtı değildir','data-label="CPU"','data-label="Bellek"'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/V1_ROUTER_HEALTH_SAMPLES|Ölçüm ID|2020-01-01T00:00:00Z|Çevrimiçi|ONLINE|null%|NaN/);
 const detail=view({selectedId:'1'});
 for(const text of ['<dialog','V1_ROUTER_HEALTH_SAMPLES','Ölçüm ID','17','2020-01-01T00:00:00Z','Canlı durum'])assert.ok(detail.includes(text),text);
});
test('loading, errors and synthetic/malformed data hide retained real rows/details',()=>{
 for(const override of [{loading:true},{error:'Envanter yenilenemedi.'},{data:{...data,is_demo:true}},{data:{...data,source:'STATIC_DEMO'}},{data:{...data,items:[null]}},{data:{...data,items:[{...row,cpu_load_percent:NaN}]}}]){
  const html=view({...override,selectedId:'1',lastSuccess:Date.parse('2026-01-01T00:00:00Z')});
  assert.doesNotMatch(html,/Fixture|<dialog/);assert.match(html,/Son başarılı yenileme:.*2026/);
 }
 const html=view({data:{...data,items:[{...row,sampled_at:null,connection_status:'NO_DATA',cpu_load_percent:null}]}});
 assert.doesNotMatch(html,/Son internet denemesi başarılı|Güncel değil/);
});
test('freshness follows measurement time, not API freshness or fetch time',()=>{
 const measured=Date.parse(row.sampled_at);
 assert.equal(ui.freshness({...row,freshness:'STALE'},measured+300_000),'Son bilinen ölçüm');
 assert.equal(ui.freshness({...row,freshness:'RECENT'},measured+300_001),'Güncel değil');
 assert.equal(ui.freshness({...row,sampled_at:null},measured),'Veri yok');
});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function harness(){
 const states=[],pending=[];let tick,cancelled=false,clock=1000;
 const task=inventoryRefresh({load:signal=>new Promise((resolve,reject)=>pending.push({signal,resolve,reject})),publish:s=>states.push(s),
  schedule:(callback,ms)=>{assert.equal(ms,60_000);tick=callback;return 7;},cancel:id=>{assert.equal(id,7);cancelled=true;},now:()=>clock});
 return {task,states,pending,tick:()=>tick(),cancelled:()=>cancelled,setClock:n=>clock=n};
}
test('60s refresh serializes requests and stops/aborts without late updates',async()=>{
 const h=harness();assert.equal(h.pending.length,1);h.tick();h.task.refresh();assert.equal(h.pending.length,1);
 h.pending[0].resolve(data);await settle();assert.equal(h.states.at(-1).lastSuccess,1000);
 h.tick();h.task.refresh();assert.equal(h.pending.length,2);
 const count=h.states.length;h.task.stop();assert.ok(h.cancelled());assert.ok(h.pending[1].signal.aborted);
 h.pending[1].resolve(data);await settle();h.tick();h.task.refresh();assert.equal(h.states.length,count);assert.equal(h.pending.length,2);
});
test('error hides old rows, preserves last success and recovers on next tick',async()=>{
 const h=harness();h.pending[0].resolve(data);await settle();h.setClock(61000);h.tick();assert.equal(h.states.at(-1).data,undefined);
 h.pending[1].reject(new Error('secret upstream error'));await settle();
 const failure=h.states.at(-1);assert.equal(failure.lastSuccess,1000);assert.equal(failure.data,undefined);assert.match(failure.error,/yenilenemedi/);assert.doesNotMatch(failure.error,/secret/);
 h.tick();h.pending[2].resolve(data);await settle();assert.equal(h.states.at(-1).lastSuccess,61000);h.task.stop();
});
test('polling mount keeps ADMIN/source/visible-list guards and mobile containment',()=>{
 assert.ok(readFileSync('src/screens/Routers.tsx','utf8').includes("source==='V1_INVENTORY'&&admin?<>{!navigation.selected&&<V1Inventory/>}</>"));
 const css=readFileSync('src/styles.css','utf8');assert.match(css,/\.inventory-table\{[^}]*table-layout:fixed/);assert.match(css,/@media\(max-width:900px\)[\s\S]*\.inventory-table td::before/);
});
