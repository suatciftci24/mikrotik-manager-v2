import {test} from 'node:test';
import assert from 'node:assert/strict';
import {V26_HTTP_API_BASE,requireV26AcceptanceReadiness} from './v26AcceptanceProfile.mjs';

const ready={service:'mikrotik-manager-v2',environment:'v26-acceptance',
 runtime_profile:'v26-isolated-acceptance',api_port:18996,database_checked:false};

test('browser acceptance requires the actual isolated loopback API readiness identity',()=>{
 assert.equal(V26_HTTP_API_BASE,'http://127.0.0.1:18996');
 assert.equal(requireV26AcceptanceReadiness(200,ready),ready);
 for(const [status,payload] of [
  [503,ready],[200,{...ready,runtime_profile:'local-demo'}],
  [200,{...ready,environment:'local-demo'}],[200,{...ready,api_port:8000}],
  [200,{...ready,database_checked:true}],[200,{...ready,service:'other'}],
  [200,null],
 ])assert.throws(()=>requireV26AcceptanceReadiness(status,payload),/BLOCKED/);
});
