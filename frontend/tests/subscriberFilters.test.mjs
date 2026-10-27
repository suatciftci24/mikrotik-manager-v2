import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EMPTY_SUBSCRIBER_FILTERS,filterSubscribers,subscriberFilterOptions} from '../src/lib/subscriberFilters.ts';
const today='2026-10-27';
const base={id:'one',username:'ayse.isik',customer_name:'Ayşe Işık',router_name:'Kadıköy',plan:'Fiber 100',source:'LOCAL',status:'ACTIVE',expires_on:'2026-10-30',is_demo:true};
const rows=[base,{...base,id:'two',username:'MERT.ISP',customer_name:'Mert İleri',source:'RADIUS',status:'PAUSED',router_name:'Ataşehir',plan:'Fiber 500',expires_on:'2026-11-30'},
 {...base,id:'three',username:'eda',customer_name:'Eda Öz',source:null,status:'PENDING',expires_on:null},
 {...base,id:'four',username:'eski',customer_name:'Eski Demo',expires_on:'2026-10-26'}];
const filter=changes=>filterSubscribers(rows,{...EMPTY_SUBSCRIBER_FILTERS,...changes},today).map(r=>r.id);
test('name and username search supports Turkish letters, case, whitespace and combined words',()=>{
 assert.deepEqual(filter({query:' AYŞE IŞIK '}),['one']);
 assert.deepEqual(filter({query:'ayse isik'}),['one']);
 assert.deepEqual(filter({query:'mert.isp'}),['two']);
 assert.deepEqual(filter({query:'EDA ÖZ'}),['three']);
 assert.deepEqual(filter({query:'not a subscriber'}),[]);
});
test('all six filter dimensions intersect on the same saved row',()=>{
 const combined={query:'ayse',router:'Kadıköy',plan:'Fiber 100',source:'LOCAL',status:'ACTIVE',expiry:'WITHIN_7'};
 assert.deepEqual(filter(combined),['one']);
 for(const changes of [{router:'Ataşehir'},{plan:'Fiber 500'},{source:'RADIUS'},{status:'PAUSED'},{expiry:'EXPIRED'}])assert.deepEqual(filter({...combined,...changes}),[]);
 assert.deepEqual(filter({router:'Ataşehir',plan:'Fiber 500',source:'RADIUS',status:'PAUSED',expiry:'ACTIVE'}),['two']);
});
test('unknown source and unknown expiry are independent; reset restores every row',()=>{
 assert.deepEqual(filter({source:'UNKNOWN',expiry:'UNKNOWN'}),['three']);
 assert.deepEqual(filter({expiry:'EXPIRED'}),['four']);
 assert.deepEqual(filter({}),['one','two','three','four']);
 assert.deepEqual(filterSubscribers([],EMPTY_SUBSCRIBER_FILTERS,today),[]);
 assert.equal(rows[0].status,'ACTIVE');
});
test('options come from real saved values and retain a no-longer-matching selection',()=>{
 assert.deepEqual(subscriberFilterOptions(rows,'plan'),['Fiber 100','Fiber 500']);
 assert.deepEqual(subscriberFilterOptions([],'plan','Eski paket'),['Eski paket']);
 assert.deepEqual(subscriberFilterOptions([],'router_name'),[]);
 assert.deepEqual(filter({plan:'Eski paket'}),[]);
});
