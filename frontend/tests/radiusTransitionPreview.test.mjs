import {test} from 'node:test';
import assert from 'node:assert/strict';
import {previewLocalRadius,usernameRiskKey} from '../src/lib/radiusTransitionPreview.ts';
import {radiusHash,radiusFiltersFromHash,radiusDetailLink} from '../src/lib/radiusVisibility.ts';
const today='2026-11-11';
const base={id:'demo-sub-a',name:'Sentetik',username:'user@example.test',authority:'LOCAL',access:'PPPOE',routerId:'demo-router-001',routerName:'Demo',plan:'Demo 100',expiresOn:'2026-12-23',status:'PAUSED',revision:0};
const run=rows=>previewLocalRadius(rows,'LEGACY',today);
test('only LOCAL is a candidate; empty/RADIUS/UNKNOWN are a successful zero with no inferred source or type',()=>{
 for(const rows of [[],[{...base,authority:'RADIUS'}],[{...base,authority:'UNKNOWN'}]]){
  const result=run(rows);assert.equal(result.total,0);assert.deepEqual(result.counts,{PRECHECK:0,MISSING:0,CONFLICT:0,LIVE:0});
 }
 const missing=run([{...base,access:'UNKNOWN'}]).candidates[0];assert.equal(missing.classification,'MISSING');
});
test('locally complete data may enter preliminary review but all live gates stay unverified',()=>{
 const input=[{...base}],before=JSON.stringify(input),result=run(input),candidate=result.candidates[0];
 assert.equal(candidate.classification,'PRECHECK');assert.equal(result.counts.PRECHECK,1);
 for(const field of ['Realm / canlı kullanıcı çakışması','NAS / router eşlemesi','AAA profil / süre eşlemesi','Geçiş yetkisi / audit','Merkezi abonelik kimliği'])assert.equal(candidate.checks.find(c=>c.label===field).state,'Doğrulanamadı');
 assert.equal(JSON.stringify(input),before);assert.deepEqual(run(input),result);
});
test('missing router/type/profile/date/identity revision are explained without inventing NAS or package mappings',()=>{
 for(const update of [{routerId:null},{routerName:null},{routerId:'registered-real'},{access:'UNKNOWN'},{plan:''},{expiresOn:null},{expiresOn:'2026-02-30'},{username:''},{username:'bad@@realm'},{revision:-1}]){
  const candidate=run([{...base,...update}]).candidates[0];assert.equal(candidate.classification,'MISSING',JSON.stringify(update));assert.ok(candidate.checks.some(check=>check.state==='Eksik bilgi'));
 }
 assert.throws(()=>previewLocalRadius([base],'LEGACY','invalid'));
});
test('NFKC/case realm collision is a risk hypothesis across visible authorities; originals never change',()=>{
 const a={...base,username:'USER@Example.Test'},b={...base,id:'demo-sub-b',username:'ｕser@example.test',authority:'RADIUS'};
 const before=JSON.stringify([a,b]),candidate=run([a,b]).candidates[0];
 assert.equal(usernameRiskKey(a.username),usernameRiskKey(b.username));assert.equal(candidate.classification,'CONFLICT');assert.equal(candidate.record.username,a.username);assert.equal(JSON.stringify([a,b]),before);assert.match(candidate.reasons.join(' '),/politikaya bağlı/);
});
test('duplicate account ID counts one candidate with a conflict warning; priorities never hide missing checks',()=>{
 const result=run([{...base,plan:''},{...base}]);assert.equal(result.total,1);assert.equal(result.counts.CONFLICT,1);
 assert.ok(result.candidates[0].checks.some(check=>check.state==='Eksik bilgi'));
 assert.match(result.candidates[0].reasons.join(' '),/kimliği birden çok/);
});
test('absent realm, unknown Unicode policy and expired subscriptions require decisions rather than readiness',()=>{
 for(const update of [{username:'user'},{username:'User@example.test'},{username:'şule@example.test'},{expiresOn:'2026-11-10'},{status:'PENDING'}])assert.equal(run([{...base,...update}]).candidates[0].classification,'LIVE');
});
test('PPPoE and Hotspot do not select authority and persistent store IDs/revisions stay isolated',()=>{
 const persistent={...base,id:'demo-managed-sub-a',routerId:'demo-managed-router-a',revision:1,access:'HOTSPOT'};
 assert.equal(previewLocalRadius([persistent],'PERSISTENT',today).candidates[0].classification,'PRECHECK');
 assert.equal(previewLocalRadius([persistent],'LEGACY',today).candidates[0].classification,'MISSING');
 assert.equal(previewLocalRadius([{...persistent,revision:0}],'PERSISTENT',today).candidates[0].classification,'MISSING');
});
test('summary is mutually exclusive and complete; preview navigation retains existing scope/type filters',()=>{
 const rows=[base,{...base,id:'demo-sub-b',username:'two'},{...base,id:'demo-sub-c',username:'three@realm',plan:''},{...base,id:'demo-sub-d',username:'user@example.test'}];
 const result=run(rows);assert.equal(Object.values(result.counts).reduce((sum,n)=>sum+n,0),result.total);
 const filters={scope:'LEGACY',authority:'ALL',access:'PPPOE',query:'user',preview:true};
 assert.deepEqual(radiusFiltersFromHash(radiusHash(filters)),filters);
 assert.equal(new URLSearchParams(radiusDetailLink(base,filters).slice(1)).get('return_to'),radiusHash(filters));
});
