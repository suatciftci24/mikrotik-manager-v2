import {test} from 'node:test';
import assert from 'node:assert/strict';
import {historyValues,operationLabel,statusText} from '../src/lib/subscriberHistory.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const base={id:'request',actor_id:'demo-user',source:'LOCAL',is_demo:true,occurred_at:'2026-10-26T21:01:00Z'};
test('mixed operation labels and before/after values retain expiry semantics',()=>{
 const renewal={...base,operation:'RENEWAL',previous_expires_on:'2026-10-27',expires_on:'2026-11-30'};
 assert.match(operationLabel(renewal.operation),/Yenileme/);assert.match(historyValues(renewal)[0],/2026/);
 const plan={...base,operation:'PLAN_CHANGE',previous_values:{plan:'Fiber 100',monthly_price:549.9},new_values:{plan:'Fiber 500',monthly_price:849.9}};
 assert.match(operationLabel(plan.operation),/Paket\/profil/);assert.match(historyValues(plan)[0],/Fiber 100/);assert.match(historyValues(plan)[1],/Fiber 500/);assert.match(historyValues(plan)[1],/849,90/);
 const state={...base,operation:'STATUS_CHANGE',previous_values:{status:'ACTIVE'},new_values:{status:'PAUSED'}};
 assert.match(historyValues(state)[0],/Etkin/);assert.match(historyValues(state)[1],/Devre dışı/);
 const created={...base,operation:'CREATE',previous_values:{},new_values:{username:'demo.new',access_type:'PPPOE',expires_on:null}};
 assert.equal(historyValues(created)[0],'Kayıt yok');assert.match(historyValues(created)[1],/demo.new/);assert.match(operationLabel(created.operation),/PPPoE/);
 assert.equal(statusText('unexpected'),'Veri yok');
});
test('new persistent operations update daily counts and status/source distribution at Turkey midnight',()=>{
 const item={id:'demo-sub-new',username:'demo.new',customer_name:'Sentetik',source:'RADIUS',status:'PAUSED',expires_on:null,is_demo:true};
 const history=['CREATE','PLAN_CHANGE','STATUS_CHANGE'].map((operation,index)=>({...base,id:String(index),source:'RADIUS',operation,previous_values:{},new_values:{}}));
 const summary=buildDailySummary([],[{item,history,is_demo:true,persistence:'local-postgresql-demo'}],new Date('2026-10-26T21:05:00Z'));
 assert.equal(summary.operations.today,3);assert.equal(summary.operations.total,3);assert.equal(summary.subscribers.total,1);
 assert.equal(summary.subscribers.paused,1);assert.equal(summary.subscribers.radius,1);assert.equal(summary.expiry.unknown,1);
 assert.deepEqual(new Set(summary.operations.recent.map(e=>e.operation)),new Set(['CREATE','PLAN_CHANGE','STATUS_CHANGE']));
});
