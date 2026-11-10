import {test} from 'node:test';
import assert from 'node:assert/strict';
import {observationAge,savedConnectionLabel} from '../src/lib/routerObservation.ts';
import {subscriberTextContext} from '../src/lib/detailCenter.ts';
const now=Date.parse('2026-11-10T12:00:00Z');
test('missing, invalid, unzoned and future times never claim freshness',()=>{
 for(const value of [null,undefined,'bad','2026-11-10T11:00:00','2026-11-10T13:00:00Z'])assert.equal(observationAge(value,now),'Güncellik bilinmiyor');
 assert.equal(observationAge('2026-11-10T11:00:00Z',NaN),'Güncellik bilinmiyor');
});
test('observation age uses saved source time without inferring online',()=>{
 for(const [value,label] of [['2026-11-10T12:00:00Z','1 dakikadan yeni kayıt'],['2026-11-10T11:58:00Z','2 dk önce kaydedildi'],['2026-11-10T14:00:00+03:00','1 sa önce kaydedildi'],['2026-11-07T12:00:00Z','3 gün önce kaydedildi']])assert.equal(observationAge(value,now),label);
 assert.equal(savedConnectionLabel('ONLINE'),'Örnekte ONLINE');assert.equal(savedConnectionLabel('OFFLINE'),'Örnekte OFFLINE');assert.equal(savedConnectionLabel(null),'Bilinmiyor');
});
test('router search survives URL return context without mixing subscriber queries',()=>{
 assert.equal(subscriberTextContext('#module=routers&query=Ofis','query','routers'),'Ofis');
 assert.equal(subscriberTextContext('#module=subscribers&query=Abone','query','routers'),'');
 assert.equal(subscriberTextContext('#module=subscribers&query=Abone','query'),'Abone');
 assert.equal(subscriberTextContext('#module=routers&query='+('x'.repeat(250)),'query','routers').length,200);
});
