import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resourceInvalidated} from '../src/lib/resourceEvents.ts';

test('mutation refresh covers paginated subscriber/router lists and histories',()=>{
 for(const path of ['/subscriber-workspace?page=2&page_size=25','/subscriber-workspace?search=one','/subscriber-workspace/management/history?page=1']){
  assert.equal(resourceInvalidated(path,['/subscriber-workspace']),true);
 }
 assert.equal(resourceInvalidated('/router-workspace/routers?page_size=100',['/router-workspace/routers']),true);
 assert.equal(resourceInvalidated('/subscriber-center/demo-managed-sub-one',['/subscriber-workspace'],['/subscriber-workspace?source=LOCAL']),true);
});
test('refresh preserves path boundaries and separate legacy/workspace resources',()=>{
 assert.equal(resourceInvalidated('/subscriber-workspace-other?page=1',['/subscriber-workspace']),false);
 assert.equal(resourceInvalidated('/subscribers?page=1',['/subscriber-workspace']),false);
 assert.equal(resourceInvalidated('/subscriber-workspace?page=1',['/subscribers']),false);
 assert.equal(resourceInvalidated('/reports?source=/subscriber-workspace',['/subscriber-workspace']),false);
 assert.equal(resourceInvalidated('/subscriber-workspace/one-extra',['/subscriber-workspace/one']),false);
});
