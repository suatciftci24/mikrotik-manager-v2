import {test} from 'node:test';
import assert from 'node:assert/strict';
import {candidatePayload,connectionError,emptyRouterForm,routerForm,registryStatus} from '../src/lib/routerRegistry.ts';
const form={...emptyRouterForm,name:' Lab ',management_address:'10.77.0.2',username:'fixture-ro',password:'SYNTHETIC_PASSWORD_CANARY',ca_pem:'PUBLIC_CA_FIXTURE',leaf_sha256:'a'.repeat(64)};
test('new router uses explicit confirmation and exact input; no password persistence',()=>{
 const payload=candidatePayload(form,'fixture-request');assert.equal(payload.name,'Lab');assert.equal(payload.port,8729);assert.equal(payload.password,form.password);assert.equal(payload.confirmed_read_only,true);assert.equal(payload.router_id,null);
 assert.equal(routerForm().password,'');assert.equal(emptyRouterForm.password,'');
});
test('editing prepopulates safe metadata; blank credentials preserve server materials',()=>{
 const item={id:'registered-fixture',name:'Lab',management_address:'10.77.0.2',port:8729,identity:'LAB',expected_version:'',leaf_sha256:'a'.repeat(64),revision:3};
 const edit=routerForm(item);assert.equal(edit.username,'');assert.equal(edit.password,'');assert.equal(edit.ca_pem,'');
 const payload=candidatePayload(edit,'fixture-request',item);assert.equal(payload.password,null);assert.equal(payload.expected_revision,3);assert.equal(payload.expected_identity,'LAB');
});
test('missing trust, private key, plaintext API and malformed targets rejected',()=>{
 for(const update of [{port:'8728'},{port:'1'},{management_address:'localhost'},{management_address:'10.77.0.999'},{management_address:'010.77.0.2'},{leaf_sha256:''},{password:''},{ca_pem:'-----BEGIN PRIVATE KEY-----'}])assert.throws(()=>candidatePayload({...form,...update},'fixture'));
});
test('ambiguous auth, explicit permission, TLS errors and stale checks stay honest',()=>{
 assert.match(connectionError('AUTHENTICATION_REJECTED:TRAP:CREDENTIAL_OR_ACCOUNT_POLICY:MESSAGE_CODE_6:CATEGORY_NONE'),/Disabled/);
 assert.match(connectionError('AUTHENTICATION_REJECTED:TRAP:PERMISSION_DENIED'),/API yetkisi/);
 assert.match(connectionError('CERTIFICATE_PIN_MISMATCH'),/eşleşmiyor/);
 assert.match(connectionError('REGISTRY_STORAGE_UNAVAILABLE'),/belleğe düşürülmedi/);
 assert.equal(registryStatus('STALE'),'Kontrol eskimiş');assert.equal(registryStatus('ONLINE'),'Bilinmiyor');
 assert.doesNotMatch(connectionError('SYNTHETIC_PASSWORD_CANARY'),/CANARY/);
});

test('invalid text and oversized pasted inputs fail locally with field-specific messages',()=>{
 for(const [update,message] of [[{name:'A'.repeat(121)},/Router adı/],[{name:'Lab\nrouter'},/kontrol karakteri/],[{expected_identity:'X'.repeat(121)},/cihaz kimliği/],[{expected_version:'7'.repeat(41)},/RouterOS/],[{username:'a'.repeat(129)},/kullanıcı adı/],[{ca_pem:'A'.repeat(262145)},/Public CA/]]){
  assert.throws(()=>candidatePayload({...form,...update},'fixture'),message);
 }
});
test('missing records and validation responses give actionable safe messages',()=>{
 assert.match(connectionError('ROUTER_NOT_FOUND'),/Listeyi yenileyip/);
 assert.match(connectionError('VERIFICATION_NOT_FOUND'),/Formu kapatıp/);
 assert.match(connectionError('VERIFICATION_IN_PROGRESS'),/iptal edilemez/);
 assert.match(connectionError('İstek alanları doğrulanamadı.'),/Alan biçimlerini/);
});
