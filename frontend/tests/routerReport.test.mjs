import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildRouterReport, connectionStatus, percentText, validPercent} from '../src/lib/routerReport.ts';
const row={id:'demo-router-1',name:'Sentetik router',site:'Demo',status:'ONLINE',cpu_percent:24,memory_percent:61,uptime:'38g 14s',last_seen:'2026-10-26T09:42:00Z',is_demo:true};

test('report uses actual saved status/resource samples and retains source time',()=>{
 const rows=[row,{...row,id:'2',status:'OFFLINE',cpu_percent:38,memory_percent:47},{...row,id:'3',status:'DEGRADED',cpu_percent:72,memory_percent:78},{...row,id:'4',cpu_percent:17,memory_percent:55}];
 const report=buildRouterReport(rows,new Date('2026-10-27T10:00:00Z'));
 assert.deepEqual(report.counts,{total:4,online:2,offline:1,degraded:1,unknown:0});
 assert.deepEqual(report.cpu,{average:37.75,samples:4});assert.deepEqual(report.memory,{average:60.25,samples:4});
 assert.equal(report.rows[0].source_time,row.last_seen);assert.equal(report.rows[0].device_uptime,row.uptime);
 assert.equal(percentText(report.cpu.average),'37,8%');
});
test('missing and invalid percentages are unknown, not zero or clamped',()=>{
 for(const value of [null,undefined,'24',false,-1,101,NaN,Infinity])assert.equal(validPercent(value),null);
 assert.equal(validPercent(0),0);assert.equal(percentText(0),'0%');assert.equal(percentText(null),'Veri yok');
 const report=buildRouterReport([row,{...row,id:'other',cpu_percent:null,memory_percent:101}]);
 assert.deepEqual(report.cpu,{average:24,samples:1});assert.deepEqual(report.memory,{average:61,samples:1});
});
test('unknown status and undated observation never imply offline or fresh measurements',()=>{
 for(const value of [undefined,null,'unreachable','online',''])assert.equal(connectionStatus(value),'UNKNOWN');
 const report=buildRouterReport([{...row,status:null,last_seen:'2026-10-26T09:42:00',uptime:''}]);
 assert.equal(report.counts.offline,0);assert.equal(report.counts.unknown,1);assert.equal(report.rows[0].source_time,null);assert.equal(report.rows[0].device_uptime,null);
});
test('re-reading a snapshot cannot invent connection events, traffic, downtime or availability',()=>{
 const first=buildRouterReport([row],new Date('2026-10-27T10:00:00Z'));
 const again=buildRouterReport([row],new Date('2026-10-27T11:00:00Z'));
 assert.deepEqual(first.rows,again.rows);assert.equal(first.connection_history,null);assert.equal(again.connection_history,null);assert.equal(first.traffic,null);assert.equal(again.traffic,null);assert.notEqual(first.generated_at,again.generated_at);
});
test('empty inventory has no resource average; unsafe or duplicate demo identities fail closed',()=>{
 const empty=buildRouterReport([]);assert.equal(empty.counts.total,0);assert.deepEqual(empty.cpu,{average:null,samples:0});assert.deepEqual(empty.memory,{average:null,samples:0});
 assert.throws(()=>buildRouterReport([{...row,is_demo:false}]),/sentetik/);assert.throws(()=>buildRouterReport([{...row,id:''}]),/kimliği/);assert.throws(()=>buildRouterReport([row,row]),/tekil/);
});
