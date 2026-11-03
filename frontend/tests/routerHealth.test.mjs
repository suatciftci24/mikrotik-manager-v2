import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
const require=createRequire(import.meta.url),module={exports:{}};
const code=buildSync({stdin:{contents:"export * from './src/lib/routerHealth';export * from './src/lib/dashboardV1Health';",resolveDir:process.cwd()},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
new Function('require','module','exports',code)(require,module,module.exports);
const {routerHealth,dashboardV1Health}=module.exports;
const now=Date.parse('2026-11-02T10:00:00Z');
const row={id:'fixture',name:'Fixture',identity:null,model:null,routeros_version:null,status:'NO_DATA',health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'1',sampled_at:new Date(now).toISOString(),cpu_load_percent:0,memory_used_percent:0,connection_status:'NO_DATA',freshness:'STALE'};
const health=(changes={},time=now)=>routerHealth({...row,...changes},time);
test('inclusive CPU/RAM thresholds and zero, either metric can escalate',()=>{
 for(const [cpu,ram,status] of [[0,0,'Normal'],[69.99,79.99,'Normal'],[70,0,'Dikkat'],[0,80,'Dikkat'],[89.99,94.99,'Dikkat'],[90,0,'Kritik'],[0,95,'Kritik'],[100,100,'Kritik']])assert.equal(health({cpu_load_percent:cpu,memory_used_percent:ram}).status,status);
 assert.match(health({cpu_load_percent:90}).reason,/CPU ≥ %90/);
});
test('actual sample age overrides performance and API freshness; exact 10 minutes stays current',()=>{
 assert.equal(health({},now+600000).status,'Normal');
 assert.equal(health({cpu_load_percent:100},now+600001).status,'Eski veri');
 assert.equal(health({freshness:'RECENT'},now+600001).status,'Eski veri');
});
test('missing, invalid, future, timezone-less time and missing provenance never become healthy',()=>{
 for(const change of [{sampled_at:null},{sampled_at:'bad'},{sampled_at:'2026-11-02T10:00:00'},{sampled_at:new Date(now+1).toISOString()},{health_source:null},{health_sample_id:' '},{cpu_load_percent:null},{memory_used_percent:null},{cpu_load_percent:NaN},{memory_used_percent:101}])assert.equal(health(change).status,'Veri yok',JSON.stringify(change));
 assert.equal(health({},NaN).status,'Veri yok');
});
test('summary counts exclusive categories and orders urgent alerts, rejecting demo',()=>{
 const items=[row,{...row,id:'warn',cpu_load_percent:70},{...row,id:'critical',memory_used_percent:95},{...row,id:'old',sampled_at:new Date(now-600001).toISOString(),cpu_load_percent:100},{...row,id:'missing',cpu_load_percent:null}];
 const data={source:'V1_INVENTORY_EXPORT',is_demo:false,availability:'AVAILABLE',items};
 const summary=dashboardV1Health(data,now);
 assert.deepEqual(Object.values(summary.counts),[1,1,1,1,1]);
 assert.deepEqual(summary.alerts.map(i=>i.health.status),['Kritik','Dikkat','Eski veri','Veri yok']);
 assert.throws(()=>dashboardV1Health({...data,is_demo:true},now));
});
