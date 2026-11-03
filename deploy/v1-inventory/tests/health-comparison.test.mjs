import {test} from 'node:test';
import assert from 'node:assert/strict';
import {expectedHealth,frameStable,compareHealthFrame,compareV25DashboardFrame,states} from '../browser/health-comparison.mjs';
import {acceptanceDiagnostics} from '../browser/acceptance-diagnostics.mjs';
const now=Date.parse('2026-11-03T10:00:00Z');
const row={id:'synthetic-1',name:'SYNTHETIC',health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'synthetic-sample',sampled_at:new Date(now-60000).toISOString(),cpu_load_percent:13,memory_used_percent:4.7};
function frame(){return {active:0,clock:{lower:now,upper:now},data:{source:'V1_INVENTORY_EXPORT',is_demo:false,items:[{...row}]},rows:[{cells:['SYNTHETIC','Fixture model','13% / 4.7%','probe','3 Kas 2026 12:59'],status:'Normal',reason:'CPU < %70 ve RAM < %80 · 1 dk önce'}],counts:Object.fromEntries(states.map(s=>[s,s==='Normal'?'1':'0'])),alerts:[],stamps:['3 Kas 2026 12:59']};}
test('independent oracle covers both metrics, exact age boundary, missing provenance and zero',()=>{
 for(const [cpu,ram,status] of [[0,0,'Normal'],[70,0,'Dikkat'],[0,80,'Dikkat'],[90,80,'Kritik'],[70,95,'Kritik']])assert.equal(expectedHealth({...row,cpu_load_percent:cpu,memory_used_percent:ram},now).status,status);
 const old={...row,sampled_at:new Date(now-600000).toISOString()};assert.equal(expectedHealth(old,now).status,'Normal');assert.equal(expectedHealth(old,now+1).status,'Eski veri');assert.equal(expectedHealth({...row,health_source:null},now).status,'Veri yok');
});
test('observation waits for in-flight reads and a clock boundary, never for values to agree',()=>{
 const f=frame();assert.equal(frameStable(f),true);assert.equal(frameStable({...f,active:1}),false);
 f.data.items[0].sampled_at=new Date(now-600000).toISOString();f.clock.upper=now+1;assert.equal(frameStable(f),false);
 f.clock={lower:now+1,upper:now+1};assert.equal(frameStable(f),true);
 assert.throws(()=>compareHealthFrame(f),/status/); // A stable bad render fails immediately.
});
test('specific metric column and typed operands reject swapped, stale and misplaced percentages',()=>{
 const f=frame();assert.equal(compareHealthFrame(f).Normal,1);
 f.rows[0].cells[2]='13% /\n 4.7%';assert.equal(compareHealthFrame(f).Normal,1); // Layout whitespace only.
 f.data.items[0].cpu_load_percent=1e-7;f.rows[0].cells[2]='1e-7% / 4.7%';assert.equal(compareHealthFrame(f).Normal,1);
 f.data.items[0].cpu_load_percent=13;f.rows[0].cells[2]='4.7% / 13%';f.rows[0].cells[1]='13% / 4.7%';
 let e;try{compareHealthFrame(f);}catch(err){e=err;}
 assert.equal(e.comparison.name,'dashboard.row_0.metrics');assert.deepEqual(e.comparison.expected,{cpu:13,ram:4.7});assert.deepEqual(e.comparison.actual,{cpu:4.7,ram:13});
 const result=acceptanceDiagnostics().failure(e);assert.deepEqual(result.failure.comparison,e.comparison);
});
test('wrong counts/status/reason, mixed snapshots and demo contract fail without conditional PASS',()=>{
 for(const change of [f=>f.counts.Normal='0',f=>f.rows[0].status='Kritik',f=>f.rows[0].reason='CPU ≥ %90',f=>f.data.items[0].cpu_load_percent=90,f=>f.data.is_demo=true,f=>f.data.source='DEMO']){
  const f=frame();change(f);assert.throws(()=>compareHealthFrame(f));
 }
});
test('unsafe operands, raw DOM and arbitrary data never enter diagnostic comparison receipt',()=>{
 const e=new Error('SYNTHETIC_SECRET');e.comparison={name:'dashboard.row_0.metrics',actual:'SYNTHETIC_SECRET',expected:{cpu:13,ram:4.7}};
 const r=acceptanceDiagnostics().failure(e);assert.equal(r.failure.comparison,undefined);assert.ok(!JSON.stringify(r).includes('SYNTHETIC_SECRET'));
 const f=frame();f.rows[0].cells[2]='SYNTHETIC_SECRET';try{compareHealthFrame(f);}catch(err){const r=acceptanceDiagnostics().failure(err);assert.ok(!JSON.stringify(r).includes('SYNTHETIC_SECRET'));assert.deepEqual(r.failure.comparison.actual,{format:'INVALID_METRICS'});}
});

function v25Frame(){
 const f=frame();f.rows[0].cells[5]='Son bilinen ölçüm';f.counts={'Routerlar':'1','Son 5 dk ölçüm':'1','Eski ölçümler':'0','Ölçüm yok':'0'};return f;
}
test('V2.5 adapter enforces its own four counters and 5-minute boundary, rejects V2.6 contract',()=>{
 const f=v25Frame();f.data.items[0].sampled_at=new Date(now-300000).toISOString();assert.equal(compareV25DashboardFrame(f)['Son 5 dk ölçüm'],1);
 f.clock={lower:now+1,upper:now+1};f.rows[0].cells[5]='Güncel değil';f.counts['Son 5 dk ölçüm']='0';f.counts['Eski ölçümler']='1';assert.equal(compareV25DashboardFrame(f)['Eski ölçümler'],1);
 assert.throws(()=>compareV25DashboardFrame(frame()));assert.throws(()=>compareHealthFrame(v25Frame()));
});
test('V2.5 failure retains exact safe numeric operands, frame comparison never retries bad metrics',()=>{
 const f=v25Frame();f.rows[0].cells[2]='12% / 4.7%';let error;try{compareV25DashboardFrame(f);}catch(e){error=e;}
 const failure=acceptanceDiagnostics().failure(error).failure;
 const legacy=new Error();legacy.comparison={name:'dashboard.row_0.v25_legacy_metric_match',expected:true,actual:false};
 assert.deepEqual(acceptanceDiagnostics().failure(legacy).failure.comparison,{...legacy.comparison,source:'same_browser_inventory_response',snapshot_bound:true});
 assert.equal(failure.comparison.name,'dashboard.row_0.metrics');assert.deepEqual(failure.comparison.expected,{cpu:13,ram:4.7});assert.deepEqual(failure.comparison.actual,{cpu:12,ram:4.7});
 f.rows[0].cells[2]='13% / 4.7%';f.counts['Routerlar']='0';assert.throws(()=>compareV25DashboardFrame(f),e=>acceptanceDiagnostics().failure(e).failure.comparison.name==='dashboard.v25_counts');
});
