import {test} from 'node:test';
import assert from 'node:assert/strict';
import {detailText, monthlyPriceText, subscriberObservation} from '../src/lib/subscriberObservation.ts';
const subscriber={is_demo:true,ip_address:'100.64.12.41',last_seen:'2026-10-26T09:42:00Z',status:'ACTIVE',plan:'Fiber 100',monthly_price:549.9};
test('inventory time and IP are retained without implying session state or connection time',()=>{
 for(const status of ['ACTIVE','PAUSED','PENDING']){
  const record=subscriberObservation({...subscriber,status});
  assert.equal(record.last_seen,subscriber.last_seen);assert.equal(record.ip,subscriber.ip_address);
  assert.equal(record.session_status,null);assert.equal(record.last_connection,null);assert.equal(record.session_duration,null);
 }
 assert.deepEqual(subscriberObservation(subscriber),subscriberObservation(subscriber));
});
test('missing, naive or invalid observation timestamps are unknown',()=>{
 for(const last_seen of [null,undefined,'','bad','2026-10-26T09:42:00'])assert.equal(subscriberObservation({...subscriber,last_seen}).last_seen,null);
 assert.equal(subscriberObservation({...subscriber,last_seen:'2026-10-26T12:42:00+03:00'}).last_seen,'2026-10-26T12:42:00+03:00');
 assert.throws(()=>subscriberObservation({...subscriber,is_demo:false}),/sentetik/);
});
test('placeholder text and invalid prices are unavailable, but measured zero is not missing',()=>{
 for(const value of [null,undefined,'',' ','—','-','Veri yok'])assert.equal(detailText(value),'Veri yok');
 assert.equal(subscriberObservation({...subscriber,ip_address:'—'}).ip,'Veri yok');
 assert.equal(detailText(' Demo '),'Demo');
 for(const value of [null,undefined,-1,NaN,Infinity,'549.9'])assert.equal(monthlyPriceText(value),'Veri yok');
 assert.match(monthlyPriceText(0),/0,00/);assert.match(monthlyPriceText(549.9),/549,90/);
});
