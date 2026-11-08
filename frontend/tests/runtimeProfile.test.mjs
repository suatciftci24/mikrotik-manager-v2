import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeRuntimeProfile,runtimeIdentity} from '../src/lib/runtimeProfile.ts';

test('only the explicit isolated acceptance runtime receives V2.6 identity',()=>{
 assert.equal(normalizeRuntimeProfile('v26-isolated-acceptance'),'v26-isolated-acceptance');
 for(const value of [undefined,null,'local-demo','V2.6','localhost','v26-isolated'])assert.equal(normalizeRuntimeProfile(value),'local-demo');
 assert.deepEqual(runtimeIdentity(normalizeRuntimeProfile('v26-isolated-acceptance')),{manager:'MANAGER V2.6',workspace:'V2.6 İzole Kabul Ortamı',tag:'V2.6 İZOLE KABUL',description:'Ayrı V2.6 kabul profili · sentetik veriler · canlı sistem bağlantısı yok.'});
 assert.deepEqual(runtimeIdentity(normalizeRuntimeProfile('local-demo')),{manager:'MANAGER V2',workspace:'Demo çalışma alanı',tag:'YEREL V2 DEMO',description:'Sentetik veriler · yerel V2 demo ortamı · canlı sistem bağlantısı yok.'});
});
