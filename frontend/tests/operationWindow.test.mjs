import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildOperationWindow} from '../src/lib/operationWindow.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const now=new Date('2026-10-27T09:00:00Z');
const event=(id,occurred_at,operation='RENEWAL',subscriber_id='a')=>({id,occurred_at,operation,subscriber_id,customer_name:'Sentetik '+subscriber_id,router_name:'Demo router',username:'demo.'+subscriber_id,actor_id:'demo-user',source:'LOCAL',is_demo:true});
test('rolling 24 hours includes both exact boundaries, excludes older and future events',()=>{
 const history=[event('old','2026-10-26T08:59:59.999Z'),event('start','2026-10-26T09:00:00Z'),event('end',now.toISOString()),event('future','2026-10-27T09:00:00.001Z')];
 const window=buildOperationWindow(history,now);
 assert.deepEqual(window.events.map(e=>e.id),['end','start']);assert.equal(window.counts.total,2);
 assert.equal(window.from,'2026-10-26T09:00:00.000Z');assert.equal(window.to,now.toISOString());
 assert.deepEqual(history.map(e=>e.id),['old','start','end','future']);
});
test('operation kinds are counted separately and affected subscribers are unique',()=>{
 const history=['CREATE','PLAN_CHANGE','STATUS_CHANGE','RENEWAL','DATE_EDIT'].map((kind,i)=>event(String(i),'2026-10-27T08:00:00Z',kind,i===4?'b':'a'));
 const window=buildOperationWindow(history,now);
 assert.deepEqual(window.counts,{total:5,create:1,plan:1,status:1,renewal:1,date_edit:1});
 assert.equal(window.affected.length,2);assert.equal(window.affected[0].router_name,'Demo router');
 assert.equal(window.events[0].actor_id,'demo-user');
 assert.equal(buildOperationWindow([],now).events.length,0);
 assert.deepEqual(buildOperationWindow([],now).affected,[]);
});
test('timezone offsets denote the same instant; advancing the window expires saved events',()=>{
 const item=event('a','2026-10-26T12:00:00+03:00');
 assert.equal(buildOperationWindow([item],now).counts.total,1);
 assert.equal(buildOperationWindow([item],new Date(now.getTime()+1)).counts.total,0);
 assert.throws(()=>buildOperationWindow([],new Date('invalid')),/zamanı/);
});
test('summary carries the same saved subscriber/router/event fields after changes',()=>{
 const before={id:'a',username:'demo.a',customer_name:'Sentetik A',router_name:'Sentetik router',source:'LOCAL',status:'ACTIVE',plan:'Fiber 100',expires_on:null,is_demo:true};
 const detail={item:before,history:[],is_demo:true,persistence:'local-postgresql-demo'};
 assert.equal(buildDailySummary([],[detail],now).operation_history.length,0);
 const changed={...detail,item:{...before,plan:'Fiber 500',status:'PAUSED'},history:[{...event('new','2026-10-27T08:30:00Z','PLAN_CHANGE'),previous_values:{plan:'Fiber 100'},new_values:{plan:'Fiber 500'}}]};
 const summary=buildDailySummary([],[changed],now);
 assert.equal(summary.subscribers.paused,1);
 const window=buildOperationWindow(summary.operation_history,now);
 assert.equal(window.counts.plan,1);assert.equal(window.events[0].router_name,before.router_name);
 assert.equal(window.events[0].username,before.username);assert.equal(window.events[0].customer_name,before.customer_name);
 assert.deepEqual(window.events[0].new_values,{plan:'Fiber 500'});
 assert.equal(window.events[0].access_type,null); // Never guess PPPoE for older untyped fixtures.
});
