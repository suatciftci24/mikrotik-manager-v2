import {test} from 'node:test';
import assert from 'node:assert/strict';
import {subscriberReportPeriods} from '../src/lib/subscriberReports.ts';
import {turkeyToday} from '../src/lib/expiry.ts';

test('today, Monday-to-today and inclusive 30-day periods have explicit calendar boundaries',()=>{
 assert.deepEqual(subscriberReportPeriods('2026-10-27').map(({id,start,end})=>({id,start,end})),[
  {id:'TODAY',start:'2026-10-27',end:'2026-10-27'},
  {id:'WEEK',start:'2026-10-26',end:'2026-10-27'},
  {id:'MONTH',start:'2026-09-28',end:'2026-10-27'},
 ]);
});
test('Monday starts a new week; Sunday stays in the same calendar week',()=>{
 assert.equal(subscriberReportPeriods('2026-10-25')[1].start,'2026-10-19');
 assert.equal(subscriberReportPeriods('2026-10-26')[1].start,'2026-10-26');
});
test('Turkey midnight, leap days and year boundaries do not use browser dates or rolling hours',()=>{
 const before=turkeyToday(new Date('2026-10-25T20:59:59Z'));
 const after=turkeyToday(new Date('2026-10-25T21:00:00Z'));
 assert.equal(subscriberReportPeriods(before)[1].start,'2026-10-19');
 assert.equal(subscriberReportPeriods(after)[1].start,'2026-10-26');
 assert.equal(subscriberReportPeriods('2024-03-01')[2].start,'2024-02-01');
 assert.equal(subscriberReportPeriods('2026-01-01')[1].start,'2025-12-29');
 assert.equal(subscriberReportPeriods('2026-01-01')[2].start,'2025-12-03');
});
test('invalid calendar input fails explicitly instead of presenting a misleading report period',()=>{
 for(const value of ['','2026-02-30','2026-02-29','2026-13-01','27.10.2026'])assert.throws(()=>subscriberReportPeriods(value),/takvim günü/);
});
