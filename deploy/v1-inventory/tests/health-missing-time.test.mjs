import {test} from 'node:test';
import assert from 'node:assert/strict';
import {frameStable,compareHealthFrame,states} from '../browser/health-comparison.mjs';
import {acceptanceDiagnostics} from '../browser/acceptance-diagnostics.mjs';

const now=Date.parse('2026-11-07T12:00:00Z');
function missingFrame(){
 return {active:0,clock:{lower:now,upper:now+1},
  data:{source:'V1_INVENTORY_EXPORT',is_demo:false,items:[{name:'SYNTHETIC',health_source:null,health_sample_id:null,sampled_at:null,cpu_load_percent:null,memory_used_percent:null}]},
  rows:[{cells:['SYNTHETIC','','Veri yok','','Veri yok'],status:'Veri yok',reason:'Doğrulanmış gerçek sağlık ölçümü yok. · Güncellik doğrulanamadı'}],
  counts:Object.fromEntries(states.map(s=>[s,s==='Veri yok'?'1':'0'])),alerts:[{name:'SYNTHETIC',status:'Veri yok'}],stamps:[null]};
}
test('missing measurement time settles instead of looping on NaN; strict measured-data gate still fails',()=>{
 const f=missingFrame();
 assert.equal(frameStable(f),true);
 assert.throws(()=>compareHealthFrame(f),error=>{
  const result=acceptanceDiagnostics().failure(error);
  assert.equal(result.failure.comparison.name,'dashboard.row_0.numeric_schema');
  assert.equal(result.failure.comparison.expected,true);
  assert.equal(result.failure.comparison.actual,false);
  return true;
 });
 assert.equal(frameStable({...f,active:1}),false);
 assert.equal(frameStable({...f,rows:[]}),false);
});
test('missing-time fix does not waive genuine age or health transitions or retry a stable mismatch',()=>{
 const f=missingFrame(),row=f.data.items[0];
 Object.assign(row,{health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'synthetic-sample',sampled_at:new Date(now-600000).toISOString(),cpu_load_percent:0,memory_used_percent:0});
 assert.equal(frameStable(f),false); // Exact 10-minute class transition.
 f.clock={lower:now+1,upper:now+2};
 assert.equal(frameStable(f),true);
 assert.throws(()=>compareHealthFrame(f)); // Deliberately wrong DOM must fail, never retry-to-PASS.
 row.sampled_at=new Date(now-60000).toISOString();f.clock={lower:now-1,upper:now};
 assert.equal(frameStable(f),false); // Minute-age text transition also stays guarded.
});
