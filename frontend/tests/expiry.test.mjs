import {test} from 'node:test';
import assert from 'node:assert/strict';
import {expiryInfo, matchesExpiry, turkeyToday, remainingDays, expiryDate} from '../src/lib/expiry.ts';

test('expiry thresholds include the full final Turkey calendar day', () => {
  const cases = [
    ['2026-10-26', -1, 'EXPIRED'], ['2026-10-27', 0, 'TODAY'], ['2026-10-28', 1, 'WITHIN_3'], ['2026-10-30', 3, 'WITHIN_3'], ['2026-10-31', 4, 'WITHIN_7'],
    ['2026-11-03', 7, 'WITHIN_7'], ['2026-11-04', 8, 'WITHIN_30'],
    ['2026-11-26', 30, 'WITHIN_30'], ['2026-11-27', 31, 'ACTIVE'],
  ];
  for (const [date, days, status] of cases) assert.deepEqual(expiryInfo(date, '2026-10-27'), {days, status});
});
test('missing or invalid dates remain unknown instead of guessed or normalized', () => {
  for (const date of [null, undefined, '', '2026-02-30', '2026-13-01', '27.10.2026', '2026-10-27T00:00:00Z']) {
    assert.deepEqual(expiryInfo(date, '2026-10-27'), {days: null, status: 'UNKNOWN'});
    assert.equal(expiryDate(date), 'Bitiş tarihi bilinmiyor');
  }
});
test('Turkey day switches at Istanbul midnight independently of browser timezone', () => {
  assert.equal(turkeyToday(new Date('2026-10-26T20:59:59Z')), '2026-10-26');
  assert.equal(turkeyToday(new Date('2026-10-26T21:00:00Z')), '2026-10-27');
  assert.equal(turkeyToday(new Date('2026-12-31T21:00:00Z')), '2027-01-01');
});
test('calendar arithmetic crosses leap day and year boundaries', () => {
  assert.equal(expiryInfo('2028-03-01', '2028-02-28').days, 2);
  assert.equal(expiryInfo('2027-01-01', '2026-12-31').days, 1);
});
test('upcoming filters include urgent dates but exclude expired and unknown records', () => {
  const today = '2026-10-27';
  for (const date of ['2026-10-27', '2026-11-03', '2026-11-26']) assert.ok(matchesExpiry(date, 'WITHIN_30', today));
  for (const date of ['2026-10-26', '2026-11-27', null]) assert.ok(!matchesExpiry(date, 'WITHIN_30', today));
  assert.ok(!matchesExpiry('2026-11-04', 'WITHIN_7', today));
  assert.ok(matchesExpiry(null, 'UNKNOWN', today));
  assert.ok(matchesExpiry('2026-10-26', 'EXPIRED', today));
});
test('remaining-day wording distinguishes today, overdue and unknown', () => {
  assert.equal(remainingDays(0), 'Bugün bitiyor (0 gün)');
  assert.equal(remainingDays(-3), '3 gün önce doldu');
  assert.equal(remainingDays(5), '5 gün kaldı');
  assert.equal(remainingDays(null), 'Bitiş tarihi bilinmiyor');
});
