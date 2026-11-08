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
   const value=url.endsWith('/reports/inventory')?{routers,items:[{id:'a'}]}:url.endsWith('/routers')?{items:routers}:url.endsWith('/subscribers')?{items:[{id:'a'}]}:url.endsWith('/router-events')?{items:[],available:false,is_demo:true}:detail('a','r1');
   return new Response(JSON.stringify(value));
  };
  const loaded=await loadManagementReport('ignored',{signal:controller.signal});
  assert.equal(loaded.events,null);assert.equal(loaded.details[0].item.id,'a');
  assert.deepEqual(calls.sort(),['/api/v1/reports/inventory','/api/v1/router-events','/api/v1/subscribers/a']);
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Demo rapor kaynağı okunamadı'}),{status:503});
  await assert.rejects(loadManagementReport('ignored'),/okunamadı/);
 }finally{globalThis.fetch=original;}
});

test('V2.2 thirty Turkey calendar days, expiry lists and links survive URL reload',()=>{
 const range=managementRange('LAST_30',new Date('2024-03-01T21:00:00Z'));
 assert.equal(range.start,'2024-02-02');assert.equal(range.end,'2024-03-02');
 const selection={...filter,period:'LAST_30',expiry:'WITHIN_3',kind:'PPPOE'};
 assert.deepEqual(managementFilterFromHash(managementReportHash(selection)),selection);
 const input=source([detail('today','r1',[],{expires_on:'2026-10-27'}),detail('three','r1',[],{expires_on:'2026-10-30'}),detail('seven','r1',[],{expires_on:'2026-11-03'}),detail('unknown','r1',[],{expires_on:null})]);
 assert.deepEqual(buildManagementReport(input,{...filter,expiry:'WITHIN_3'},now).expiryRows.map(r=>r.id),['today','three']);
 assert.equal(buildManagementReport(input,filter,now).expirySummary.unknown,1);
 assert.equal(buildManagementReport(input,{...filter,period:'YESTERDAY'},now).expiryRows.length,1);
});
test('V2.2 PPPoE scope excludes untyped operations, and unavailable history is never zero',()=>{
 const input=source([detail('typed','r1',[operation('typed',now.toISOString())]),detail('untyped','r1',[operation('untyped',now.toISOString())],{access_type:null})]);
 const all=buildManagementReport(input,filter,now);
 assert.equal(all.pppoeOperations,1);assert.equal(all.untypedOperations,1);
 assert.deepEqual(buildManagementReport(input,{...filter,kind:'PPPOE'},now).operations.map(e=>e.id),['typed']);
 const missing=buildManagementReport(source([{...detail('missing','r1'),history_available:false}]),filter,now);
 assert.equal(missing.counts.operations,null);assert.equal(missing.pppoeOperations,null);assert.equal(missing.untypedOperations,null);
});
test('V2.2 future recovery cannot supply an end or duration in a current outage report',()=>{
 const input=source([],events([event('down','INTERNET_DOWN','2026-10-27T08:00:00Z'),event('future-up','INTERNET_UP','2026-10-27T10:00:00Z',{down_event_id:'down'})]));
 const report=buildManagementReport(input,filter,now);
 assert.equal(report.events.length,1);assert.equal(report.counts.recoveries,0);
 assert.equal(report.events[0].lifecycle.ended_at,null);assert.equal(report.events[0].lifecycle.duration_seconds,null);assert.equal(report.events[0].lifecycle.status,'UNKNOWN');
});

const managedAccount={id:'demo-managed-sub-a',customer_name:'Kalıcı demo',username:'synthetic.a',access_type:'PPPOE',source:'LOCAL',router_id:'demo-managed-router-new'};
const receipt=(request_id,extra={})=>({request_id,item_id:managedAccount.id,success:true,recorded:true,operation:'EXTEND',actor_id:'demo-user',router_id:'demo-managed-router-old',occurred_at:now.toISOString(),previous:{expires_on:'2026-10-27'},values:{expires_on:'2026-11-26'},...extra});
const workspace=(receipts)=>({accounts:[managedAccount],receipts,routers:[{id:'demo-managed-router-old',fields:{name:'Önceki sentetik router'}}]});
test('V2.3 persistent PPPoE receipts retain historical router and values, exclude failed, future and Hotspot',()=>{
 const input={...source([detail('legacy','r1',[operation('legacy-op',now.toISOString())])]),workspace:workspace([receipt('renew'),receipt('failed',{success:false}),receipt('future',{occurred_at:'2026-10-27T10:00:00Z'}),receipt('hotspot',{item_id:'demo-managed-sub-h'})])};
 input.workspace.accounts.push({...managedAccount,id:'demo-managed-sub-h',access_type:'HOTSPOT'});
 const report=buildManagementReport(input,filter,now);
 assert.equal(report.pppoeOperations,2);assert.equal(report.operations.length,2);
 const saved=report.operations.find(row=>row.workspace);assert.equal(saved.router_id,'demo-managed-router-old');assert.equal(saved.router_name,'Önceki sentetik router');assert.equal(saved.previous_expires_on,'2026-10-27');assert.equal(saved.expires_on,'2026-11-26');
 assert.equal(buildManagementReport(input,{...filter,router:'demo-managed-router-old'},now).pppoeOperations,1);
 assert.equal(buildManagementReport(input,{...filter,router:managedAccount.router_id},now).pppoeOperations,0);
 assert.equal(buildManagementReport(input,{...filter,kind:'PLAN_CHANGE'},now).pppoeOperations,0);
 assert.equal(buildManagementReport({...input,workspace:null},filter,now).pppoeOperations,null);
 assert.throws(()=>buildManagementReport({...input,workspace:workspace([receipt('bad',{item_id:'missing'})])},filter,now),/doğrulanamadı/);
 assert.throws(()=>buildManagementReport({...input,workspace:workspace([receipt('same'),receipt('same',{operation:'STATUS'})])},filter,now),/çelişkili/);
});
test('V2.3 audit edit and router operations retain their type rather than inventing a plan change',()=>{
 const input={...source(),workspace:workspace([receipt('edit',{operation:'EDIT',previous:{customer_name:'Önce'},values:{customer_name:'Sonra'}}),receipt('move',{operation:'ROUTER',previous:{router_id:'old'},values:{router_id:'new'}})])};
 assert.deepEqual(buildManagementReport(input,filter,now).operations.map(row=>row.operation),['EDIT','ROUTER']);
 assert.equal(buildManagementReport(input,{...filter,kind:'PLAN_CHANGE'},now).operations.length,0);
});
test('V2.3 admin loader reads all audit pages; incomplete workspace is unavailable; default loader never requests admin APIs',async()=>{
 const original=globalThis.fetch,calls=[];let broken=false,duplicate=false;
 try{
 globalThis.fetch=async(url)=>{
  calls.push(url);let value;
  if(url.includes('/management/history'))value=broken?{items:[],total:2,is_demo:true}:{items:[receipt(url.includes('page=2')&&!duplicate?'second':'first')],total:2,is_demo:true};
  else if(url.includes('/subscriber-workspace'))value={items:[managedAccount],total:1,is_demo:true};
  else if(url.includes('/router-workspace'))value={items:[],total:0,is_demo:true};
  else if(url.endsWith('/reports/inventory'))value={routers,items:[]};
  else value={items:[],available:true,is_demo:true};
  return new Response(JSON.stringify(value));
 };
 const loaded=await loadManagementReport('/management/report?workspace=1');assert.equal(loaded.workspace.receipts.length,2);assert.ok(calls.some(url=>url.endsWith('page=2')));
 broken=true;const missing=await loadManagementReport('/management/report?workspace=1');assert.equal(missing.workspace,null);assert.match(missing.workspaceError,/tamamı doğrulanamadı/);
 broken=false;duplicate=true;const repeated=await loadManagementReport('/management/report?workspace=1');assert.equal(repeated.workspace,null);assert.match(repeated.workspaceError,/tekil değil/);
 calls.length=0;await loadManagementReport('/management/report');assert.ok(calls.every(url=>!url.includes('workspace')));
 }finally{globalThis.fetch=original;}
});

test('rolling 24 hours includes exact lower bound, crosses Turkey midnight and excludes future and untyped operations',()=>{
 const input=source([detail('a','r1',[
  operation('old','2026-10-26T08:59:59.999Z'),operation('lower','2026-10-26T09:00:00Z'),operation('now',now.toISOString()),operation('future','2026-10-27T09:00:00.001Z'),
 ]),detail('b','r1',[operation('untyped',now.toISOString())],{access_type:null})]);
 const rolling={period:'LAST_24',router:'',kind:'PPPOE'};
 assert.deepEqual(managementFilterFromHash(managementReportHash(rolling)),rolling);
 assert.deepEqual(buildManagementReport(input,rolling,now).operations.map(e=>e.id),['now','lower']);
 assert.equal(managementRange('LAST_24',now).from,now.getTime()-86400000);
});
