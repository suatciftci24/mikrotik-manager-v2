import {test} from 'node:test';
import assert from 'node:assert/strict';
import {subscriberSource, matchesSource, sourceDescription} from '../src/lib/source.ts';

test('only exact explicit authority values establish source', () => {
  assert.equal(subscriberSource('LOCAL'), 'LOCAL');
  assert.equal(subscriberSource('RADIUS'), 'RADIUS');
  for (const input of [undefined, null, '', 'local', 'LOCAL/RADIUS', ['LOCAL', 'RADIUS'], {router_name: 'MikroTik'}, 0]) {
    assert.equal(subscriberSource(input), 'UNKNOWN');
    assert.ok(matchesSource(input, 'UNKNOWN'));
    assert.ok(!matchesSource(input, 'LOCAL'));
    assert.ok(!matchesSource(input, 'RADIUS'));
    assert.match(sourceDescription(input), /tahmini yapılmaz/);
  }
});
test('source filter preserves known values and unknown records under All', () => {
  const records = ['LOCAL', 'RADIUS', null, undefined, 'unexpected'];
  assert.equal(records.filter(value => matchesSource(value, 'ALL')).length, 5);
  assert.deepEqual(records.filter(value => matchesSource(value, 'LOCAL')), ['LOCAL']);
  assert.deepEqual(records.filter(value => matchesSource(value, 'RADIUS')), ['RADIUS']);
  assert.equal(records.filter(value => matchesSource(value, 'UNKNOWN')).length, 3);
});
test('known source descriptions explain the designated management authority', () => {
  assert.match(sourceDescription('LOCAL'), /yerel kullanıcı kaydı/);
  assert.match(sourceDescription('RADIUS'), /FreeRADIUS kullanıcı kaydı/);
  assert.match(sourceDescription('RADIUS'), /LOCAL olarak yönetildiği anlamına gelmez/);
});
