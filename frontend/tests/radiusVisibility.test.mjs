import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadRadiusVisibility,projectRadiusRecord,filterRadiusRecords,radiusFiltersFromHash,radiusHash,radiusDetailLink} from '../src/lib/radiusVisibility.ts';
import {detailReturnHash} from '../src/lib/detailLinks.ts';
const base={id:'demo-sub-fixture',customer_name:'Ayşe Işık',username:'ayse.test',source:'LOCAL',access_type:'PPPOE',router_id:'demo-router-001',router_name:'Kadıköy',plan:'Fiber 100',expires_on:'2026-12-23',status:'PAUSED',revision:2,is_demo:true,password:'SECRET_CANARY'};
const filters={scope:'LEGACY',authority:'ALL',access:'ALL',query:''};
test('authority and access type remain independent; unknown source is never inferred from PPPoE/router/plan',()=>{
 for(const authority of ['LOCAL','RADIUS',null])for(const access of ['PPPOE','HOTSPOT',null]){
  const row=projectRadiusRecord({...base,source:authority,access_type:access},'LEGACY');
  assert.equal(row.authority,authority??'UNKNOWN');assert.equal(row.access,access??'UNKNOWN');assert.equal(JSON.stringify(row).includes('SECRET_CANARY'),false);
 }
 for(const update of [{id:'registered-real'},{is_demo:false},{revision:-1}])assert.throws(()=>projectRadiusRecord({...base,...update},'LEGACY'));
 const rows=[projectRadiusRecord(base,'LEGACY'),projectRadiusRecord({...base,id:'demo-sub-r',source:'RADIUS',access_type:'HOTSPOT'},'LEGACY')];
 assert.equal(filterRadiusRecords(rows,{...filters,authority:'RADIUS',access:'HOTSPOT'}).length,1);
 assert.equal(filterRadiusRecords(rows,{...filters,authority:'LOCAL',access:'HOTSPOT'}).length,0);
 assert.equal(filterRadiusRecords(rows,{...filters,query:'ayse kadikoy'}).length,2);
});
test('legacy reads only existing scoped GET; persistent privilege denial occurs before any request',async()=>{
 const previous=globalThis.fetch,calls=[],controller=new AbortController();
 try{
  globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({items:[base],total:1,is_demo:true}));};
  const result=await loadRadiusVisibility('LEGACY',false,{signal:controller.signal});
  assert.equal(result.length,1);assert.equal(calls[0].url,'/api/v1/subscribers');assert.equal(calls[0].init.credentials,'include');assert.equal(calls[0].init.signal,controller.signal);assert.equal(calls[0].init.method,undefined);
  await assert.rejects(loadRadiusVisibility('PERSISTENT',false),/yetkisi gerekli/);assert.equal(calls.length,1);
 }finally{globalThis.fetch=previous;}
});
test('persistent reads all verified pages; incomplete, changing, duplicate or failed scope never becomes an empty success',async()=>{
 const previous=globalThis.fetch;let mode='ok';
 const a={...base,id:'demo-managed-sub-a',is_demo:undefined},b={...a,id:'demo-managed-sub-b'};
 try{
  globalThis.fetch=async(url,init)=>{
   assert.ok(!init.method||init.method==='GET');
   if(mode==='http')return new Response(JSON.stringify({detail:'Sentetik depo erişilemiyor'}),{status:503});
   const page=new URL('http://local'+url).searchParams.get('page');
   return new Response(JSON.stringify({items:page==='1'?[a]:mode==='missing'?[]:mode==='duplicate'?[a]:[b],total:mode==='changed'&&page==='2'?3:2,is_demo:mode!=='marker'}));
  };
  assert.equal((await loadRadiusVisibility('PERSISTENT',true)).length,2);
  for(mode of ['missing','changed','duplicate','marker','http'])await assert.rejects(loadRadiusVisibility('PERSISTENT',true));
  globalThis.fetch=async()=>new Response(JSON.stringify({items:[],total:0,is_demo:true}));
  assert.deepEqual(await loadRadiusVisibility('PERSISTENT',true),[]);
 }finally{globalThis.fetch=previous;}
});
test('radius links retain exact scope and bounded filters; arbitrary radius pages and real router targets stay rejected',()=>{
 const selected={scope:'PERSISTENT',authority:'RADIUS',access:'HOTSPOT',query:'Test & ad'};
 assert.deepEqual(radiusFiltersFromHash(radiusHash(selected)),selected);
 const row=projectRadiusRecord({...base,id:'demo-managed-sub-fixture',router_id:'demo-managed-router-fixture'},'PERSISTENT');
 const hash=radiusDetailLink(row,selected);const params=new URLSearchParams(hash.slice(1));
 assert.equal(params.get('workspace'),'PERSISTENT');assert.equal(params.get('id'),row.id);assert.equal(params.get('return_to'),radiusHash(selected));
 assert.equal(new URLSearchParams(radiusDetailLink(row,selected,true).slice(1)).get('id'),row.routerId);
 assert.equal(radiusDetailLink({...row,routerId:'registered-fixture'},selected,true),null);
 assert.equal(detailReturnHash('#module=radius&id=x'),null);assert.equal(detailReturnHash('https://other/'),null);
});
