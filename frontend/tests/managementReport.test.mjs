import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildManagementReport,managementRange,loadManagementReport,managementFilterFromHash,managementReportHash} from '../src/lib/managementReport.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
import {buildSubscriptionAlerts} from '../src/lib/subscriptionAlerts.ts';
import {projectRouterEvents} from '../src/lib/routerEvents.ts';
const now=new Date('2026-10-27T09:00:00Z');
const filter={period:'TODAY',router:'',kind:'ALL'};
const routers=[{id:'r1',name:'Demo bir',status:'ONLINE',is_demo:true},{id:'r2',name:'Demo iki',status:'OFFLINE',is_demo:true}];
const operation=(id,time,kind='RENEWAL')=>({id,occurred_at:time,operation:kind,source:'LOCAL',actor_id:'demo-user',is_demo:true});
const detail=(id,router_id,history=[],extra={})=>({item:{id,router_id,router_name:routers.find(r=>r.id===router_id)?.name??'Veri yok',customer_name:'Demo '+id,username:'demo.'+id,status:'ACTIVE',source:'LOCAL',access_type:'PPPOE',expires_on:'2026-10-30',is_demo:true,...extra},history,is_demo:true,persistence:'local-postgresql-demo'});
const source=(details=[],events=[])=>({routers,details,events});
const event=(id,kind,time,extra={})=>({id,kind,router_id:'r1',occurred_at:time,is_demo:true,...extra});
const events=items=>projectRouterEvents({items,available:true,is_demo:true});
test('Turkey calendar boundaries separate Today and Yesterday, include now and exclude the future',()=>{
 const input=source([detail('a','r1',[
  operation('prev','2026-10-26T20:59:59.999Z'),operation('start','2026-10-26T21:00:00Z'),operation('end',now.toISOString()),operation('future','2026-10-27T09:00:00.001Z'),
 ])]);
 assert.deepEqual(buildManagementReport(input,filter,now).operations.map(e=>e.id),['end','start']);
 assert.deepEqual(buildManagementReport(input,{...filter,period:'YESTERDAY'},now).operations.map(e=>e.id),['prev']);
 assert.equal(managementRange('TODAY',new Date('2026-10-26T20:59:59Z')).start,'2026-10-26');
 assert.equal(managementRange('TODAY',new Date('2026-10-26T21:00:00Z')).start,'2026-10-27');
});
test('last seven calendar days include six preceding days across leap days and year boundaries',()=>{
 assert.equal(managementRange('LAST_7',new Date('2024-03-01T09:00:00Z')).start,'2024-02-24');
 assert.equal(managementRange('LAST_7',new Date('2027-01-01T09:00:00Z')).start,'2026-12-26');
 const input=source([detail('a','r1',[operation('before','2026-10-20T20:59:59.999Z'),operation('start','2026-10-20T21:00:00Z')])]);
 assert.deepEqual(buildManagementReport(input,{...filter,period:'LAST_7'},now).operations.map(e=>e.id),['start']);
});
test('snapshot counts agree with existing centers and never pretend to be yesterday inventory',()=>{
 const details=[detail('a','r1',[],{expires_on:'2026-10-26'}),detail('b','r2',[],{status:'PAUSED',expires_on:null}),detail('c','r1')];
 const report=buildManagementReport(source(details),filter,now);
 assert.deepEqual(report.inventory,buildDailySummary(routers,details,now));
 const alerts=buildSubscriptionAlerts(details.map(d=>d.item),'2026-10-27');
 assert.equal(report.inventory.expiry.expired,alerts.expired);assert.equal(report.inventory.expiry.within_7,alerts.within_7);
 assert.deepEqual(buildManagementReport(source(details),{...filter,period:'YESTERDAY'},now).inventory,report.inventory);
 const scoped=buildManagementReport(source(details),{...filter,router:'r1'},now);
 assert.equal(scoped.inventory.subscribers.total,2);assert.equal(scoped.inventory.router_counts.total,1);
});
test('identical copies count once, conflicting IDs fail closed, and input remains untouched',()=>{
 const audit=operation('a1',now.toISOString()),record=detail('a','r1',[audit,audit]);
 const lifecycle=events([event('wan','WAN_CHANGE',now.toISOString())])[0];
 const input={routers:[routers[0],routers[0]],details:[record,structuredClone(record)],events:[lifecycle,lifecycle]};
 const before=JSON.stringify(input);const report=buildManagementReport(input,filter,now);
 assert.equal(report.counts.operations,1);assert.equal(report.counts.events,1);assert.equal(report.inventory.subscribers.total,1);assert.equal(JSON.stringify(input),before);
 assert.throws(()=>buildManagementReport({...input,events:[lifecycle,{...lifecycle,new_wan:'different'}]},filter,now),/çelişkili/);
 assert.throws(()=>buildManagementReport(source([detail('a','r1',[audit]),detail('b','r2',[audit])]),filter,now),/tekil/);
});
test('linked recovery uses its own recorded time while one outage lifecycle is counted once',()=>{
 const records=events([event('down','INTERNET_DOWN','2026-10-26T20:55:00Z'),event('up','INTERNET_UP','2026-10-26T21:10:00Z',{down_event_id:'down'}),event('wan','WAN_CHANGE',now.toISOString())]);
 const today=buildManagementReport(source([],records),filter,now);
 assert.deepEqual(today.counts,{operations:0,events:2,outages:0,recoveries:1,wan:1});
 const recovery=today.events.find(e=>e.id==='up');assert.equal(recovery.lifecycle.duration_seconds,900);assert.equal(recovery.lifecycle.id,'down');
 const yesterday=buildManagementReport(source([],records),{...filter,period:'YESTERDAY'},now);
 assert.equal(yesterday.counts.outages,1);assert.equal(yesterday.counts.recoveries,0);
});
test('router and type filters intersect without discarding unknown coverage or inventing durations',()=>{
 const input=source([detail('a','r1',[operation('plan',now.toISOString(),'PLAN_CHANGE')],{router_name:'Eski ad'}),detail('b','r2',[operation('renew',now.toISOString())])],events([event('open','INTERNET_DOWN',now.toISOString(),{state:'OPEN'}),event('undated','WAN_CHANGE',null)]));
 const scoped=buildManagementReport(input,{...filter,router:'r1',kind:'PLAN_CHANGE'},now);
 assert.deepEqual(scoped.operations.map(e=>e.id),['plan']);assert.equal(scoped.operations[0].router_id,'r1');assert.equal(scoped.counts.events,0);
 const all=buildManagementReport(input,filter,now);assert.equal(all.undated.events,1);assert.equal(all.events[0].lifecycle.duration_seconds,null);
 const unknown=buildManagementReport({...input,events:null},filter,now);
 assert.equal(unknown.counts.events,null);assert.equal(unknown.counts.outages,null);
});
test('reloadable report links preserve validated period, router and kind selections',()=>{
 const selected={period:'YESTERDAY',router:'demo & router',kind:'WAN_CHANGE'};
 assert.deepEqual(managementFilterFromHash(managementReportHash(selected)),selected);
 assert.deepEqual(managementFilterFromHash('#period=bogus&kind=bogus'),filter);
 assert.throws(()=>managementRange('bogus',now),/dönemi/);
 assert.throws(()=>buildManagementReport(source(),{...filter,kind:'bogus'},now),/filtresi/);
});
test('loader reuses authenticated versioned inventory/details/events and propagates failures',async()=>{
 const original=globalThis.fetch,calls=[];const controller=new AbortController();
 try{
  globalThis.fetch=async(url,init)=>{
   calls.push(url);assert.equal(init.credentials,'include');assert.equal(init.signal,controller.signal);
   const value=url.endsWith('/routers')?{items:routers}:url.endsWith('/subscribers')?{items:[{id:'a'}]}:url.endsWith('/router-events')?{items:[],available:false,is_demo:true}:detail('a','r1');
   return new Response(JSON.stringify(value));
  };
  const loaded=await loadManagementReport('ignored',{signal:controller.signal});
  assert.equal(loaded.events,null);assert.equal(loaded.details[0].item.id,'a');
  assert.deepEqual(calls.sort(),['/api/v1/router-events','/api/v1/routers','/api/v1/subscribers','/api/v1/subscribers/a']);
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Demo rapor kaynağı okunamadı'}),{status:503});
  await assert.rejects(loadManagementReport('ignored'),/okunamadı/);
 }finally{globalThis.fetch=original;}
});
