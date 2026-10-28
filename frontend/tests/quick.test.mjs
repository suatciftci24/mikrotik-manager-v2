import {test} from 'node:test';
import assert from 'node:assert/strict';
import {extensionDate,operationLabel} from '../src/lib/quick.ts';

test('extension uses existing end date or Turkey today, with calendar rollover',()=>{
  for(const days of [7,15,30]) {
    assert.equal(extensionDate('2026-10-01','2026-10-28',days),new Date(Date.UTC(2026,9,28+days)).toISOString().slice(0,10));
    assert.equal(extensionDate('2026-11-01','2026-10-28',days),new Date(Date.UTC(2026,10,1+days)).toISOString().slice(0,10));
  }
  assert.equal(extensionDate('2028-02-28','2028-02-28',7),'2028-03-06');
  assert.equal(extensionDate('2026-12-31','2026-12-31',7),'2027-01-07');
  assert.equal(extensionDate(null,'2026-10-28',30),'');
});
test('audit labels distinguish all quick operations and legacy expiry operations',()=>{
  for(const [action,label] of Object.entries({CREATE:'Abone oluşturma',PLAN:'Paket değişikliği',STATUS:'Durum değişikliği',EXTEND:'Abonelik uzatma'})) assert.equal(operationLabel({action}),label);
  assert.equal(operationLabel({operation:'RENEWAL'}),'Yenileme');
});
