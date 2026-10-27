import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildConnectionAlarms} from '../src/lib/connectionAlarms.ts';
const row={id:'demo-router-1',name:'Sentetik router',site:'Demo',status:'ONLINE',management_address:'192.0.2.1',last_seen:'2026-10-26T09:42:00Z',is_demo:true};
test('all inventory states retain identity/time without implying internet or WAN alarms',()=>{
 for(const status of ['ONLINE','OFFLINE','DEGRADED',null]){
  const data=buildConnectionAlarms([{...row,status}]);
  assert.equal(data.rows[0].id,row.id);assert.equal(data.rows[0].source_time,row.last_seen);
  assert.equal(data.rows[0].inventory_status,status??'UNKNOWN');
  assert.equal(data.rows[0].internet_status,null);assert.equal(data.rows[0].wan,null);
  assert.equal(data.internet_outages,null);assert.equal(data.wan_changes,null);assert.equal(data.history,null);
  assert.equal(data.is_demo,true);
 }
});
test('repeated reads, changed address/status or missing dates cannot synthesize history',()=>{
 const first=buildConnectionAlarms([row]);
 assert.deepEqual(buildConnectionAlarms([row]),first);
 const changed=buildConnectionAlarms([{...row,status:'OFFLINE',management_address:'192.0.2.2',last_seen:null}]);
 assert.equal(changed.history,null);assert.equal(changed.wan_changes,null);assert.equal(changed.internet_outages,null);assert.equal(changed.rows[0].source_time,null);
});
test('empty data is unknown alarm coverage; invalid or non-demo inventory fails closed',()=>{
 const empty=buildConnectionAlarms([]);assert.deepEqual(empty.rows,[]);assert.equal(empty.history,null);assert.equal(empty.internet_outages,null);
 assert.throws(()=>buildConnectionAlarms([{...row,is_demo:false}]),/sentetik/);
 assert.throws(()=>buildConnectionAlarms([row,row]),/tekil/);
 assert.throws(()=>buildConnectionAlarms(undefined));
});
