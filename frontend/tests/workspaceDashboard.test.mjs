import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadWorkspaceDashboardSummary,loadWorkspaceRouterSummary} from '../src/lib/workspaceDashboard.ts';
const router={id:'demo-managed-router-test',kind:'DEMO_ROUTER',is_demo:true,device_connected:false,fields:{name:'V26 Test Router',model:'Sentetik',management_address:'192.0.2.10'}};
async function withApi(handler,run){const original=globalThis.fetch;globalThis.fetch=async(url,init)=>({ok:true,json:async()=>handler(String(url),init)});try{await run();}finally{globalThis.fetch=original;}}
test('one saved router and zero accounts; no static inventory reads or invented telemetry',async()=>{
 const calls=[];const controller=new AbortController();
 await withApi((url,init)=>{calls.push(url);assert.equal(init.signal,controller.signal);if(url.includes('/router-workspace/routers?'))return {items:[router],total:1};if(url.includes('/subscriber-workspace?'))return {items:[],total:0};throw Error(url);},async()=>{
  const data=await loadWorkspaceDashboardSummary('',{signal:controller.signal});
  assert.equal(data.routers[0].name,'V26 Test Router');assert.deepEqual(data.router_counts,{total:1,online:0,offline:0,degraded:0,unknown:1});assert.equal(data.subscribers.total,0);assert.equal(data.routers[0].cpu_percent,null);assert.equal(data.routers[0].last_seen,'');assert.equal(data.history_available,false);assert.equal(calls.length,3);
 });
});
test('all router pages are read, with account authority and unknown state preserved',async()=>{
 await withApi(url=>url.includes('/router-workspace/')?{items:url.includes('page=1&')?Array.from({length:100},(_,i)=>({...router,id:'r'+i})):[router],total:101}:{items:[{id:'s',router_id:router.id,status:'PAUSED',source:'RADIUS',access_type:'HOTSPOT',expires_on:null}],total:1},async()=>{const data=await loadWorkspaceDashboardSummary('');assert.equal(data.router_counts.total,101);assert.equal(data.subscribers.total,1);assert.equal(data.subscribers.radius,1);assert.equal(data.subscribers.paused,1);assert.equal(data.expiry.unknown,1);});
});
test('workspace errors and non-demo records never fall back to static demo',async()=>{
 await withApi(()=>{throw Error('storage unavailable');},async()=>assert.rejects(loadWorkspaceDashboardSummary(''),/storage unavailable/));
 await withApi(url=>({items:url.includes('/router-workspace/')?[{...router,kind:'TRUST_PROFILE'}]:[],total:url.includes('/router-workspace/')?1:0}),async()=>assert.rejects(loadWorkspaceDashboardSummary(''),/doğrulanamadı/));
});

test('operator dashboard reads scoped workspace routers without admin account or static APIs',async()=>{
 await withApi(url=>{assert.match(url,/router-workspace\/routers/);return {items:[router],total:1};},async()=>{
  const data=await loadWorkspaceRouterSummary('');assert.equal(data.router_counts.total,1);assert.equal(data.routers[0].name,'V26 Test Router');assert.equal(data.history_available,false);
 });
 await withApi(()=>({items:[],total:0}),async()=>assert.equal((await loadWorkspaceRouterSummary('')).router_counts.total,0));
 await withApi(()=>{throw Error('denied');},async()=>assert.rejects(loadWorkspaceRouterSummary(''),/denied/));
});

test('persistent audit feeds the Turkey-day PPPoE count without legacy requests or invented history',async()=>{
 const {dashboardToday}=await import('../src/lib/dashboardOverview.ts');const stamp=new Date().toISOString();
 const account={id:'demo-managed-sub-test',router_id:router.id,source:'LOCAL',access_type:'PPPOE',revision:1,status:'ACTIVE',plan:'P',customer_name:'Test',username:'test',expires_on:null};
 const receipt={request_id:'audit-1',item_id:account.id,source:'LOCAL',router_id:router.id,revision:1,recorded:true,success:true,operation:'CREATE',actor_id:'actor',occurred_at:stamp,previous:{},values:{plan:'P'}};
 let receipts=[receipt],denied=false;const calls=[];
 await withApi(url=>{calls.push(url);if(url.includes('/management/history?report=true&')){if(denied)throw Error('denied');return {items:receipts,total:receipts.length,is_demo:true};}if(url.includes('/router-workspace/'))return {items:[router],total:1};if(url.includes('/subscriber-workspace?'))return {items:[account],total:1};throw Error('unexpected source '+url);},async()=>{
  assert.equal(dashboardToday(await loadWorkspaceDashboardSummary(''),null).pppoe,1);
  receipts=[{...receipt,occurred_at:'2000-01-01T00:00:00Z'}];assert.equal(dashboardToday(await loadWorkspaceDashboardSummary(''),null).pppoe,0);
  receipts=[];assert.equal(dashboardToday(await loadWorkspaceDashboardSummary(''),null).pppoe,null);
  denied=true;assert.equal(dashboardToday(await loadWorkspaceDashboardSummary(''),null).pppoe,null);
  assert.ok(calls.every(url=>!url.includes('/subscribers')&&!url.includes('/router-events')));
 });
});
