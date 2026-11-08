import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
import {dashboardToday,dashboardCritical,loadDashboardSummary,loadDashboardAlarms} from '../src/lib/dashboardOverview.ts';
import {projectRouterEvents} from '../src/lib/routerEvents.ts';
const now=new Date('2026-11-02T10:00:00Z');
const router={id:'r1',name:'Sentetik router',status:'ONLINE',is_demo:true};
const detail={item:{id:'s1',revision:0,router_id:'r1',customer_name:'Sentetik abone',username:'synthetic',access_type:'PPPOE',source:'LOCAL',status:'ACTIVE',expires_on:'2026-11-05',is_demo:true},is_demo:true,history_available:true,history:[]};
const operation=(id,occurred_at)=>({id,occurred_at,operation:'PLAN_CHANGE',actor_id:'demo',source:'LOCAL',is_demo:true});
test('daily PPPoE summary uses Turkey today, excludes future/untyped, and unavailable history is unknown',()=>{
 const data=buildDailySummary([router],[{...detail,history:[operation('today','2026-11-01T21:00:00Z'),operation('yesterday','2026-11-01T20:59:59Z'),operation('future','2026-11-02T10:00:01Z')]},{...detail,item:{...detail.item,id:'untyped',access_type:null},history:[operation('untyped',now.toISOString())]}],now);
 assert.deepEqual(dashboardToday(data,null,now),{pppoe:1,outages:null,wan:null});
 assert.equal(dashboardToday({...data,history_available:false},null,now).pppoe,null);
 assert.equal(dashboardToday({...data,as_of_date:'2026-11-01'},null,now).pppoe,null);
});
test('event summary counts saved starts once, does not turn recovery or inventory into an outage',()=>{
 const data=buildDailySummary([],[],now);
 const events=projectRouterEvents({available:true,is_demo:true,items:[{id:'down',kind:'INTERNET_DOWN',occurred_at:'2026-11-02T09:00:00Z',router_id:'r1',state:'OPEN',is_demo:true},{id:'up',kind:'INTERNET_UP',down_event_id:'down',occurred_at:'2026-11-02T09:30:00Z',router_id:'r1',is_demo:true},{id:'future',kind:'WAN_CHANGE',occurred_at:'2026-11-02T11:00:00Z',router_id:'r1',is_demo:true}]});
 assert.deepEqual(dashboardToday(data,[...events,events[0]],now),{pppoe:0,outages:1,wan:0});
 assert.throws(()=>dashboardToday(data,[{...events[0],is_demo:false}],now),/doğrulanamadı/);
 assert.deepEqual(dashboardToday(data,[],now),{pppoe:0,outages:0,wan:0});
});
test('zero critical alarms with incomplete coverage is unknown; recorded critical count remains scoped',()=>{
 assert.deepEqual(dashboardCritical({summary:{critical:0},coverage:{connection_available:false,ipsec_available:false}}),{value:null,partial:true});
 assert.deepEqual(dashboardCritical({summary:{critical:2},coverage:{connection_available:true,ipsec_available:false}}),{value:2,partial:true});
 assert.deepEqual(dashboardCritical({summary:{critical:0},coverage:{connection_available:true,ipsec_available:true}}),{value:0,partial:false});
});
test('overview loader preserves can_view endpoints and unavailable history without any admin or real-source reads',async()=>{
 const original=globalThis.fetch,calls=[],controller=new AbortController();
 try{
 globalThis.fetch=async(url,init)=>{calls.push(url);assert.equal(init.credentials,'include');assert.equal(init.signal,controller.signal);const value=url.endsWith('/routers')?{items:[router]}:url.endsWith('/subscribers')?{items:[{id:'s1'}]}:{...detail,item:{...detail.item,expires_on:null},history_available:false};return new Response(JSON.stringify(value));};
 const loaded=await loadDashboardSummary('ignored',{signal:controller.signal});assert.equal(loaded.history_available,false);assert.equal(loaded.within_3,0);assert.equal(loaded.expiry.unknown,1);
 assert.deepEqual(calls.sort(),['/api/v1/routers','/api/v1/subscribers','/api/v1/subscribers/s1']);
 }finally{globalThis.fetch=original;}
});
test('alarm loader rejects real or malformed summaries instead of showing synthetic zero',async()=>{
 const original=globalThis.fetch;
 try{
 for(const data of [{is_demo:false},{is_demo:true,summary:{critical:-1}},{is_demo:true,summary:{critical:0},coverage:{}}]){globalThis.fetch=async()=>new Response(JSON.stringify(data));await assert.rejects(loadDashboardAlarms('/alarms'),/doğrulanamadı/);}
 }finally{globalThis.fetch=original;}
});
