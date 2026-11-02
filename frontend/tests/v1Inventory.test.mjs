import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const code=buildSync({entryPoints:['src/components/V1Inventory.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(require,module,module.exports);
const row={id:'1',name:'Fixture',model:null,identity:null,routeros_version:null,status:'NO_DATA',sampled_at:'2020-01-01T00:00:00Z',cpu_load_percent:0,memory_used_percent:null,health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'17',connection_status:'LAST_PROBE_SUCCEEDED',freshness:'STALE'};
const data={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items:[row]};
const view=(override={})=>renderToStaticMarkup(module.exports.V1InventoryView({data,loading:false,retry:()=>{},...override}));
test('historical health shows Turkey time, source, zero, missing data and no online claim',()=>{
 const html=view();
 for(const text of ['Fixture','0%','Veri yok','Güncel değil','03:00','İstanbul','V1_ROUTER_HEALTH_SAMPLES','17','Son internet denemesi başarılı','Canlı durum: Veri yok'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/Çevrimiçi|ONLINE|null%|NaN/);
});
test('loading, errors and synthetic source never expose retained real rows',()=>{
 for(const override of [{loading:true},{error:'Unavailable'},{data:{...data,is_demo:true}},{data:{...data,source:'STATIC_DEMO'}}])assert.doesNotMatch(view(override),/Fixture/);
 const html=view({data:{...data,items:[{...row,sampled_at:null,connection_status:'NO_DATA',cpu_load_percent:null}]}});
 assert.doesNotMatch(html,/Son internet denemesi başarılı|Güncel değil/);
});
