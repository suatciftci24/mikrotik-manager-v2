import {test} from 'node:test';
import assert from 'node:assert/strict';
import {projectRouterEvents,filterAlarmEvents,emptyAlarmFilter,alarmCounts,loadRouterEvents} from '../src/lib/routerEvents.ts';
const now=new Date('2026-10-27T09:00:00Z');
const event=(id,kind,occurred_at,extra={})=>({id,kind,occurred_at,router_id:'r',is_demo:true,...extra});
const project=items=>projectRouterEvents({items,available:true,is_demo:true});
test('unavailable source differs from a supported empty source; no snapshot can generate an event',()=>{
 assert.equal(projectRouterEvents({items:[],available:false,is_demo:true}),null);
 assert.deepEqual(alarmCounts(null,now),{outages:null,wan:null});
 assert.deepEqual(alarmCounts(project([]),now),{outages:0,wan:0});
 assert.throws(()=>projectRouterEvents({items:[event('d','INTERNET_DOWN',null)],available:false,is_demo:true}),/kaynağı/);
 assert.throws(()=>project([event('x','INTERNET_DOWN',null),event('x','WAN_CHANGE',null)]),/kimliği/);
 assert.throws(()=>project([event('x','WAN_CHANGE',null,{is_demo:false})]),/sentetik/);
});
test('only an explicit unique same-router recovery with ordered valid times closes a lifecycle',()=>{
 const down=event('d','INTERNET_DOWN','2026-10-27T08:00:00Z');
 const up=event('u','INTERNET_UP','2026-10-27T11:10:00+03:00',{down_event_id:'d'});
 const rows=project([up,down]);assert.equal(rows.length,1);assert.equal(rows[0].status,'RESOLVED');assert.equal(rows[0].duration_seconds,600);assert.equal(rows[0].recovery_id,'u');
 for(const input of [[down,{...up,router_id:'other'}],[down,{...up,down_event_id:null}],[down,{...up,occurred_at:'2026-10-27T07:59:00Z'}],[down,up,{...up,id:'u2'}],[{...down,occurred_at:'2026-02-30T08:00:00Z'},up]]){
  const result=project(input);const row=result.find(e=>e.id==='d');assert.equal(row.status,'UNKNOWN');assert.equal(row.duration_seconds,null);assert.equal(row.ended_at,null);assert.ok(result.some(e=>e.id==='u'));
 }
});
test('missing times and missing recovery never imply ongoing or compute an elapsed duration',()=>{
 assert.equal(project([event('d','INTERNET_DOWN',now.toISOString())])[0].status,'UNKNOWN');
 assert.equal(project([event('d','INTERNET_DOWN',now.toISOString(),{state:'OPEN'})])[0].status,'OPEN');
 for(const time of [null,'bad','2026-10-27T09:00:00','2026-02-30T09:00:00Z']){
  const row=project([event('d','INTERNET_DOWN',time,{state:'OPEN'})])[0];assert.equal(row.status,'UNKNOWN');assert.equal(row.duration_seconds,null);
 }
 const wan=project([event('w','WAN_CHANGE',now.toISOString(),{previous_wan:'wan1 / 192.0.2.1',new_wan:'wan2 / 192.0.2.2'})])[0];
 assert.equal(wan.previous_wan,'wan1 / 192.0.2.1');assert.equal(wan.status,'RECORDED');assert.equal(wan.duration_seconds,null);
});
test('router/type/status/date filters intersect; Istanbul calendar days and rolling boundaries are inclusive',()=>{
 const rows=project([event('a','INTERNET_DOWN','2026-10-26T09:00:00Z',{state:'OPEN'}),event('b','WAN_CHANGE','2026-10-27T09:00:00Z'),event('c','WAN_CHANGE','2026-10-27T09:00:00.001Z'),event('old','INTERNET_DOWN','2026-10-26T08:59:59.999Z'),event('unknown','INTERNET_DOWN',null)]);
 assert.deepEqual(alarmCounts(rows,now),{outages:1,wan:1});
 assert.equal(filterAlarmEvents(rows,{...emptyAlarmFilter,router:'r',kind:'INTERNET_DOWN',status:'OPEN',period:'24H'},now).length,1);
 assert.equal(filterAlarmEvents(rows,{...emptyAlarmFilter,router:'other'},now).length,0);
 const midnight=project([event('before','WAN_CHANGE','2026-10-26T20:59:59.999Z'),event('start','WAN_CHANGE','2026-10-26T21:00:00Z'),event('end','WAN_CHANGE','2026-10-27T20:59:59.999Z'),event('after','WAN_CHANGE','2026-10-27T21:00:00Z')]);
 assert.deepEqual(filterAlarmEvents(midnight,{...emptyAlarmFilter,from:'2026-10-27',to:'2026-10-27'},now).map(e=>e.id),['end','start']);
 assert.throws(()=>filterAlarmEvents(rows,{...emptyAlarmFilter,from:'2026-10-28',to:'2026-10-27'},now),/sonra/);
 assert.throws(()=>filterAlarmEvents(rows,{...emptyAlarmFilter,from:'2026-02-30'},now),/tarih/);
});
test('shared read-only loader preserves unavailable coverage and propagates API failures',async()=>{
 const original=globalThis.fetch;
 try{
  globalThis.fetch=async(url,init)=>{assert.equal(url,'/api/v1/router-events');assert.equal(init.credentials,'include');return new Response(JSON.stringify({items:[],available:false,is_demo:true}));};
  assert.equal(await loadRouterEvents('/router-events'),null);
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Olay kaynağı hatası'}),{status:503});
  await assert.rejects(loadRouterEvents('/router-events'),/Olay kaynağı hatası/);
 }finally{globalThis.fetch=original;}
});
