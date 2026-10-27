import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSubscriptionAlerts} from '../src/lib/subscriptionAlerts.ts';
import {expiryInfo, matchesExpiry, turkeyToday} from '../src/lib/expiry.ts';
import {EMPTY_SUBSCRIBER_FILTERS,filterSubscribers} from '../src/lib/subscriberFilters.ts';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const today='2026-10-27';
const date=offset=>{if(offset===null)return null;const day=new Date(today+'T00:00:00Z');day.setUTCDate(day.getUTCDate()+offset);return day.toISOString().slice(0,10);};
const row=(offset,id=String(offset))=>({id,username:'demo.'+id,customer_name:'Sentetik '+id,router_name:'Demo router',source:'LOCAL',plan:'Fiber 100',status:'ACTIVE',expires_on:date(offset),is_demo:true});
const rows=[-1,0,1,3,4,7,8,30,31,null].map(offset=>row(offset));
test('cumulative cards have a unique warning union and unknown dates stay separate',()=>{
 const summary=buildSubscriptionAlerts(rows,today);
 assert.deepEqual(summary,{total:10,expired:1,today:1,within_3:3,within_7:5,within_30:7,valid:8,after_30:1,unknown:1,warning:6});
 assert.equal(summary.total,summary.expired+summary.valid+summary.unknown);
 assert.equal(summary.warning,summary.expired+summary.within_7);
 assert.notEqual(summary.warning,summary.expired+summary.today+summary.within_3+summary.within_7);
});
test('every warning card and valid/unknown filters match their list count',()=>{
 const summary=buildSubscriptionAlerts(rows,today);
 for(const [filter,field] of [['EXPIRED','expired'],['TODAY','today'],['WITHIN_3','within_3'],['WITHIN_7','within_7'],['WITHIN_30','within_30'],['VALID','valid'],['UNKNOWN','unknown']]){
  assert.equal(filterSubscribers(rows,{...EMPTY_SUBSCRIBER_FILTERS,expiry:filter},today).length,summary[field]);
 }
 assert.equal(expiryInfo(date(0),today).status,'TODAY');
 assert.equal(expiryInfo(date(3),today).status,'WITHIN_3');
 assert.equal(expiryInfo(date(4),today).status,'WITHIN_7');
 assert.equal(expiryInfo(date(8),today).status,'WITHIN_30');
});
test('router/source/plan/status/search scope is retained while a warning filter is selected',()=>{
 const other={...row(0,'other'),router_name:'Other router',source:'RADIUS',plan:'Fiber 500',status:'PAUSED'};
 const input=[...rows,other];
 const scope={...EMPTY_SUBSCRIBER_FILTERS,router:'Other router',source:'RADIUS',plan:'Fiber 500',status:'PAUSED',query:'Sentetik other'};
 const scoped=filterSubscribers(input,scope,today);
 assert.equal(buildSubscriptionAlerts(scoped,today).today,1);
 assert.deepEqual(filterSubscribers(input,{...scope,expiry:'TODAY'},today).map(r=>r.id),['other']);
 assert.equal(filterSubscribers(input,{...scope,expiry:'EXPIRED'},today).length,0);
 assert.equal(filterSubscribers(input,EMPTY_SUBSCRIBER_FILTERS,today).length,input.length);
});
test('unknown and invalid dates never become expired; duplicate/non-demo identities fail closed',()=>{
 const invalid=[row(null,'missing'),{...row(0,'bad'),expires_on:'2026-02-30'}];
 assert.equal(buildSubscriptionAlerts(invalid,today).unknown,2);
 assert.equal(buildSubscriptionAlerts(invalid,today).expired,0);
 assert.equal(buildSubscriptionAlerts(invalid,today).valid,0);
 assert.equal(buildSubscriptionAlerts([],today).total,0);
 assert.throws(()=>buildSubscriptionAlerts([rows[0],rows[0]],today),/tekil/);
 assert.throws(()=>buildSubscriptionAlerts([{...rows[0],is_demo:false}],today),/sentetik/);
});
test('Turkey midnight advances both warning counts and detail status by calendar day',()=>{
 const before=turkeyToday(new Date('2026-10-26T20:59:59Z'));
 const after=turkeyToday(new Date('2026-10-26T21:00:00Z'));
 const input=[row(-1,'end26'),row(0,'end27')];
 assert.equal(buildSubscriptionAlerts(input,before).today,1);
 assert.equal(buildSubscriptionAlerts(input,before).expired,0);
 assert.equal(buildSubscriptionAlerts(input,after).today,1);
 assert.equal(buildSubscriptionAlerts(input,after).expired,1);
 assert.equal(expiryInfo(input[0].expires_on,after).status,'EXPIRED');
 assert.equal(expiryInfo(input[1].expires_on,after).status,'TODAY');
 assert.equal(matchesExpiry(input[1].expires_on,'VALID',after),true);
});
test('re-reading a successful saved renewal updates alerts/list/detail/summary without mutating old data',()=>{
 const old=row(-1,'renewed');
 const changed={...old,expires_on:date(90),revision:1};
 const event={id:'saved-renewal',occurred_at:'2026-10-27T09:00:00Z',operation:'RENEWAL',source:'LOCAL',actor_id:'demo-user',is_demo:true,previous_expires_on:old.expires_on,expires_on:changed.expires_on};
 assert.equal(buildSubscriptionAlerts([old],today).warning,1);
 assert.equal(buildSubscriptionAlerts([changed],today).warning,0);
 assert.equal(filterSubscribers([changed],{...EMPTY_SUBSCRIBER_FILTERS,expiry:'EXPIRED'},today).length,0);
 assert.equal(expiryInfo(changed.expires_on,today).days,90);
 assert.equal(expiryInfo(changed.expires_on,today).status,'ACTIVE');
 const detail={item:changed,history:[event],is_demo:true,persistence:'local-postgresql-demo'};
 const summary=buildDailySummary([],[detail],new Date('2026-10-27T10:00:00Z'));
 assert.equal(summary.expiry.expired,0);assert.equal(summary.expiry.active,1);
 assert.equal(summary.operation_history[0].actor_id,'demo-user');assert.equal(summary.operation_history[0].previous_expires_on,old.expires_on);
 assert.equal(old.expires_on,date(-1));assert.equal(summary.operations.today,1);
});
