import {test} from 'node:test';
import assert from 'node:assert/strict';
import {workspaceContext,routerSources,subscriberSources} from '../src/lib/workspaceContext.ts';
import {screenFromHash} from '../src/lib/useDetailNavigation.ts';

test('all existing router and subscriber sources retain distinct selections and access labels',()=>{
 assert.deepEqual(routerSources.map(x=>x.value),['DEMO','MANAGED_DEMO','REGISTERED','V1_INVENTORY']);
 assert.deepEqual(subscriberSources.map(x=>x.value),['LEGACY','PERSISTENT','HISTORY']);
 assert.equal(workspaceContext('routers','#module=routers&source=V1_INVENTORY').access,'Salt okunur');
 assert.match(workspaceContext('routers','#module=routers&source=REGISTERED').access,/ayrıca onaylı/);
 assert.match(workspaceContext('subscribers','#module=subscribers&workspace=PERSISTENT').description,/birleştirilmez/);
});
test('detail identity takes precedence over stale source parameters in environment labels',()=>{
 assert.equal(workspaceContext('routers','#module=routers&id=registered-fixture&source=DEMO').label,'Kayıtlı cihazlar ve pilot');
 assert.equal(workspaceContext('routers','#module=routers&id=demo-managed-router-fixture&source=V1_INVENTORY').label,'Sentetik router yönetimi');
 assert.equal(workspaceContext('subscribers','#module=subscribers&id=demo-sub-fixture&workspace=PERSISTENT').label,'Mevcut demo aboneleri');
 assert.equal(workspaceContext('subscribers','#module=subscribers&id=demo-managed-sub-fixture&workspace=HISTORY').label,'Sentetik PPPoE / Hotspot yönetimi');
});
test('RADIUS is reloadable; operations and analysis never claim live measurement or deployment status',()=>{
 assert.equal(screenFromHash('#module=radius'),'radius');
 assert.equal(workspaceContext('radius','#module=radius').access,'Salt okunur · Bağlantı yok');
 assert.match(workspaceContext('radius','#module=radius').description,/canlı oturum bağlantısı yok/);
 assert.equal(workspaceContext('mikajani','#module=mikajani').access,'Salt okunur');
 for(const screen of ['radius','operations','mikajani','routers','subscribers']){
  const text=JSON.stringify(workspaceContext(screen,'#module='+screen));
  assert.doesNotMatch(text,/Yerel ortam hazır|VDS|LOCAL PREVIEW|Üretim ortamı/);
 }
});
