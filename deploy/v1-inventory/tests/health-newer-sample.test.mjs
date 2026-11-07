import {test} from 'node:test';
import assert from 'node:assert/strict';
import {frameStable,compareHealthFrame,states} from '../browser/health-comparison.mjs';
const now=Date.parse('2026-11-07T12:00:00Z');
function observed(){
 const row={name:'Synthetic',health_source:'V1_ROUTER_HEALTH_SAMPLES',health_sample_id:'synthetic',sampled_at:new Date(now+500).toISOString(),cpu_load_percent:0,memory_used_percent:0};
 return {active:0,readAt:now+600,generation:2,clock:{lower:now,upper:now},
  data:{source:'V1_INVENTORY_EXPORT',is_demo:false,items:[row]},
  rows:[{cells:['Synthetic','','Veri yok','','Veri yok'],status:'Veri yok',reason:'Ölçüm zamanı eksik, hatalı veya gelecekte. · Güncellik doğrulanamadı'}],
  counts:Object.fromEntries(states.map(s=>[s,s==='Veri yok'?'1':'0'])),alerts:[{name:'Synthetic',status:'Veri yok'}],stamps:['fixture-time']};
}
test('same-view response newer than observed health tick waits for the next tick, not a metric agreement',()=>{
 const f=observed();
 assert.equal(frameStable(f),false,'received valid sample is newer than the last actual render clock');
 f.clock={lower:now+1000,upper:now+1000};
 f.rows=[{cells:['Synthetic','','0% / 0%','','fixture-time'],status:'Normal',reason:'CPU < %70 ve RAM < %80 · 0 dk önce'}];
 f.counts=Object.fromEntries(states.map(s=>[s,s==='Normal'?'1':'0']));f.alerts=[];
 assert.equal(frameStable(f),true);assert.equal(compareHealthFrame(f).Normal,1);
 f.rows[0].cells[2]='99% / 0%';
 assert.equal(frameStable(f),true);assert.throws(()=>compareHealthFrame(f),e=>e.comparison.name==='dashboard.row_0.metrics');
});
test('future-invalid, missing or unbound time does not become a retry-to-pass condition',()=>{
 for(const change of [f=>f.readAt=now+100,f=>delete f.readAt,f=>f.data.items[0].sampled_at=null]){
  const f=observed();change(f);assert.equal(frameStable(f),true);assert.throws(()=>compareHealthFrame(f));
 }
});
