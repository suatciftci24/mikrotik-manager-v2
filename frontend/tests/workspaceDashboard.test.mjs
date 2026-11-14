import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadWorkspaceDashboardSummary} from '../src/lib/workspaceDashboard.ts';
const router={id:'demo-managed-router-test',kind:'DEMO_ROUTER',is_demo:true,device_connected:false,fields:{name:'V26 Test Router',model:'Sentetik',management_address:'192.0.2.10'}};
async function withApi(handler,run){const original=globalThis.fetch;globalThis.fetch=async(url,init)=>({ok:true,json:async()=>handler(String(url),init)});try{await run();}finally{globalThis.fetch=original;}}
test('one saved router and zero accounts; no static inventory reads or invented telemetry',async()=>{
 const calls=[];const controller=new AbortController();
 await withApi((url,init)=>{calls.push(url);assert.equal(init.signal,controller.signal);if(url.includes('/router-workspace/routers?'))return {items:[router],total:1};if(url.includes('/subscriber-workspace?'))return {items:[],total:0};throw Error(url);},async()=>{
  const data=await loadWorkspaceDashboardSummary('',{signal:controller.signal});
  assert.equal(data.routers[0].name,'V26 Test Router');assert.deepEqual(data.router_counts,{total:1,online:0,offline:0,degraded:0,unknown:1});assert.equal(data.subscribers.total,0);assert.equal(data.routers[0].cpu_percent,null);assert.equal(data.routers[0].last_seen,'');assert.equal(data.history_available,false);assert.equal(calls.length,2);
 });
});
test('all router pages are read, with account authority and unknown state preserved',async()=>{
 await withApi(url=>url.includes('/router-workspace/')?{items:url.includes('page=1&')?Array.from({length:100},(_,i)=>({...router,id:'r'+i})):[router],total:101}:{items:[{id:'s',router_id:router.id,status:'PAUSED',source:'RADIUS',access_type:'HOTSPOT',expires_on:null}],total:1},async()=>{const data=await loadWorkspaceDashboardSummary('');assert.equal(data.router_counts.total,101);assert.equal(data.subscribers.total,1);assert.equal(data.subscribers.radius,1);assert.equal(data.subscribers.paused,1);assert.equal(data.expiry.unknown,1);});
});
test('workspace errors and non-demo records never fall back to static demo',async()=>{
 await withApi(()=>{throw Error('storage unavailable');},async()=>assert.rejects(loadWorkspaceDashboardSummary(''),/storage unavailable/));
 await withApi(url=>({items:url.includes('/router-workspace/')?[{...router,kind:'TRUST_PROFILE'}]:[],total:url.includes('/router-workspace/')?1:0}),async()=>assert.rejects(loadWorkspaceDashboardSummary(''),/doğrulanamadı/));
});
