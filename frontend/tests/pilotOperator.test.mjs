import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pilotOperatorView} from '../src/lib/pilotOperator.ts';

test('only a verified eligible session exposes its candidate ID',()=>{
 const candidate={id:'fixture-existing-operator',revision:0,source:'V2_AUTHENTICATED_SESSION'};
 assert.equal(pilotOperatorView({state:'ELIGIBLE',candidate}).id,candidate.id);
 for(const state of ['BOOTSTRAP_DEMO','NOT_ADMIN','INSUFFICIENT_SCOPE','INACTIVE','UNVERIFIED'])assert.equal(pilotOperatorView({state,candidate}).id,null);
 for(const change of [{id:'demo-user'},{id:'demo-user '},{id:'bad\x7fid'},{source:'ENVIRONMENT'},{revision:-1},{id:''}])assert.equal(pilotOperatorView({state:'ELIGIBLE',candidate:{...candidate,...change}}).id,null);
});
test('missing or old session responses explain the absence and never infer an ID',()=>{
 assert.equal(pilotOperatorView().id,null);assert.match(pilotOperatorView().message,/Doğrulanmış operatör durumu alınamadı/);
 assert.match(pilotOperatorView({state:'BOOTSTRAP_DEMO',candidate:null}).message,/varsayılan Demo Operatör/);
 assert.match(pilotOperatorView({state:'INSUFFICIENT_SCOPE',candidate:null}).message,/Rol adı tek başına/);
});
