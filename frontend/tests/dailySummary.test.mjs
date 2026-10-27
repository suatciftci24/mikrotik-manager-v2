import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildDailySummary, loadDailySummary} from '../src/lib/dailySummary.ts';

const now = new Date('2026-10-26T21:05:00Z');
const router = {id:'demo-router-1',name:'Sentetik Router',site:'Demo',status:'ONLINE',last_seen:'2026-10-26T09:42:00Z',subscriber_count:649,is_demo:true};
const date = days => {const d = new Date('2026-10-27T00:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10)};
function detail(id, offset, source='LOCAL', status='ACTIVE', history=[]) {
  return {item:{id,username:id,customer_name:'Sentetik '+id,source,status,expires_on:offset===null?null:date(offset),is_demo:true},history,is_demo:true,persistence:'local-postgresql-demo'};
}
const event = (id,time) => ({id,occurred_at:time,operation:'RENEWAL',previous_expires_on:'2026-10-01',expires_on:'2026-11-30',source:'LOCAL',is_demo:true});

test('summary counts actual inventory and expiry boundaries, not router aggregate counters',()=>{
  const details=[detail('a',-1),detail('b',0),detail('c',7),detail('d',8,'RADIUS'),detail('e',30,'RADIUS'),detail('f',31,'RADIUS','PAUSED'),detail('g',null,null,'PENDING')];
  const summary=buildDailySummary([router,{...router,id:'r2',status:'OFFLINE'},{...router,id:'r3',status:'DEGRADED'}],details,now);
  assert.equal(summary.as_of_date,'2026-10-27');
  assert.equal(summary.subscribers.total,7);
  assert.deepEqual(summary.router_counts,{total:3,online:1,offline:1,degraded:1,unknown:0});
  assert.deepEqual(summary.expiry,{expired:1,within_7:2,within_30:4,active:1,unknown:1});
  assert.deepEqual(summary.subscribers,{total:7,active:5,paused:1,pending:1,unknown_status:0,local:3,radius:3,unknown_source:1});
});
test('today operations use Turkey midnight and real saved events sorted newest first',()=>{
  const earlier=event('one','2026-10-26T20:59:59Z'),current=event('two','2026-10-26T21:00:00Z');
  const summary=buildDailySummary([], [detail('a',7,'LOCAL','ACTIVE',[earlier,current])],now);
  assert.equal(summary.operations.today,1);assert.equal(summary.operations.total,2);
  assert.deepEqual(summary.operations.recent.map(e=>e.id),['two','one']);
  assert.equal(summary.operations.recent[0].subscriber_id,'a');
});
test('empty inventories and history produce supported zeros without invented activity',()=>{
  const summary=buildDailySummary([],[],now);
  assert.equal(summary.subscribers.total,0);assert.equal(summary.router_counts.total,0);
  assert.deepEqual(summary.operations,{today:0,total:0,recent:[]});
});
test('non-demo, incomplete, duplicate or undated history cannot masquerade as a valid summary',()=>{
  assert.throws(()=>buildDailySummary([{...router,is_demo:false}],[],now),/sentetik/);
  assert.throws(()=>buildDailySummary([],[{...detail('a',null),history:undefined}],now),/geçmişi/);
  assert.throws(()=>buildDailySummary([],[detail('a',1),detail('a',1)],now),/tekil/);
  assert.throws(()=>buildDailySummary([],[detail('a',1,'LOCAL','ACTIVE',[event('bad','2026-10-27T12:00:00')])],now),/zaman/);
  assert.throws(()=>buildDailySummary([],[detail('a',1,'LOCAL','ACTIVE',[event('x',now.toISOString()),event('x',now.toISOString())])],now),/tekil/);
});
test('loader reads existing authenticated API details and propagates failures instead of zero totals',async()=>{
  const original=globalThis.fetch;const calls=[];const controller=new AbortController();
  try{
    globalThis.fetch=async(url,init)=>{
      calls.push(url);assert.equal(init.credentials,'include');assert.equal(init.signal,controller.signal);
      const data=url.endsWith('/routers')?{items:[router]}:url.endsWith('/subscribers')?{items:[{id:'a',expires_on:'stale-list-value'}]}:detail('a',7);
      return new Response(JSON.stringify(data),{status:200});
    };
    const summary=await loadDailySummary('/dashboard/summary',{signal:controller.signal});
    assert.equal(summary.subscribers.total,1);assert.equal(summary.operations.total,0);
    assert.deepEqual(calls.sort(),['/api/v1/routers','/api/v1/subscribers','/api/v1/subscribers/a']);
    globalThis.fetch=async url=>new Response(JSON.stringify(url.endsWith('/routers')?{items:[]} : url.endsWith('/subscribers')?{items:[{id:'a'}]} : {detail:'Demo geçmişi alınamadı'}),{status:url.endsWith('/subscribers/a')?503:200});
    await assert.rejects(loadDailySummary('/dashboard/summary'),/Demo geçmişi alınamadı/);
  }finally{globalThis.fetch=original;}
});
