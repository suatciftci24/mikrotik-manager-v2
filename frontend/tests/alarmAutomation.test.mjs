import {test} from 'node:test';
import assert from 'node:assert/strict';
import {projectRouterEvents,activeAlarmCount,alarmCounts,filterAlarmEvents,emptyAlarmFilter} from '../src/lib/routerEvents.ts';
import {buildManagementReport} from '../src/lib/managementReport.ts';
const now=new Date('2026-10-27T09:00:00Z');
const event=(id,kind,time,extra={})=>({id,kind,occurred_at:time,router_id:'demo-router-001',source:'synthetic-observation',source_observation_id:'demo-observation-'+id,is_demo:true,...extra});
const project=items=>projectRouterEvents({items,available:true,is_demo:true});
test('linked automation resolves once and active counts exclude resolved/unknown/future events',()=>{
 const rows=project([event('down','INTERNET_DOWN','2026-10-27T07:00:00Z',{state:'RESOLVED'}),event('up','INTERNET_UP','2026-10-27T08:00:00Z',{down_event_id:'down'}),event('open','INTERNET_DOWN','2026-10-27T08:30:00Z',{state:'OPEN'}),event('unknown','INTERNET_DOWN','2026-10-27T08:40:00Z',{state:'UNKNOWN'}),event('future','INTERNET_DOWN','2026-10-28T09:00:00Z',{state:'OPEN'})]);
 assert.equal(rows.find(row=>row.id==='down').duration_seconds,3600);assert.equal(rows.find(row=>row.id==='down').status,'RESOLVED');assert.equal(activeAlarmCount(rows,now),1);assert.equal(activeAlarmCount(null,now),null);
 assert.equal(filterAlarmEvents(rows,{...emptyAlarmFilter,router:'demo-router-001',status:'OPEN',period:'24H'},now).length,1);
});
test('missing measurement evidence preserves resolved endpoints but never invents a duration',()=>{
 const rows=project([event('down','INTERNET_DOWN','2026-10-27T07:00:00Z',{state:'RESOLVED',duration_verified:false}),event('up','INTERNET_UP','2026-10-27T08:00:00Z',{down_event_id:'down'})]);
 assert.equal(rows.length,1);assert.equal(rows[0].status,'RESOLVED');assert.equal(rows[0].ended_at,'2026-10-27T08:00:00Z');assert.equal(rows[0].duration_seconds,null);
});
test('Turkey calendar report and 24-hour alarm cards share the same lifecycle counts',()=>{
 const rows=project([event('down','INTERNET_DOWN','2026-10-26T21:00:00Z',{state:'OPEN'}),event('wan','WAN_CHANGE','2026-10-27T08:00:00Z',{previous_wan:'wan1 · route1',new_wan:'wan2 · route2'})]);
 const report=buildManagementReport({routers:[{id:'demo-router-001',name:'Sentetik',status:'OFFLINE',is_demo:true}],details:[],events:rows},{period:'TODAY',router:'',kind:'ALL'},now);
 assert.equal(report.counts.outages,alarmCounts(rows,now).outages);assert.equal(report.counts.wan,alarmCounts(rows,now).wan);assert.equal(activeAlarmCount(rows,now),1);
 assert.deepEqual(project([event('down','INTERNET_DOWN','2026-10-26T21:00:00Z',{state:'OPEN'}),event('wan','WAN_CHANGE','2026-10-27T08:00:00Z',{previous_wan:'wan1 · route1',new_wan:'wan2 · route2'})]),rows);
});
