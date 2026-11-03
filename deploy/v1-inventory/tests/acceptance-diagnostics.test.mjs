// Pure synthetic events: no browser, network, session file, database or deployment.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {acceptanceDiagnostics} from '../browser/acceptance-diagnostics.mjs';
function failure(d){try{d.assertRuntimeClean();assert.fail('must fail');}catch(e){return d.failure(e);}}
test('pageerror names the exact assertion and retains HTTP evidence even when first assertion fails',()=>{
 const d=acceptanceDiagnostics();d.setStep('router_center.desktop');
 d.pageError({name:'TypeError',message:'Failed to fetch'});
 d.httpFailure('http://127.0.0.1:18996/api/v1/routers',403);
 const r=failure(d);assert.equal(r.failure.step,'browser.page_errors');
 assert.equal(r.failure.code,'ERR_ASSERTION');assert.equal(r.failure.message,'Expected 0 page errors; observed 1.');
 assert.equal(r.diagnostics.pageErrors[0].step,'router_center.desktop');
 assert.deepEqual(r.diagnostics.httpFailures,[{step:'router_center.desktop',path:'/api/v1/routers',status:403}]);
});
test('HTTP-only failure names second assertion, path/status and occurrence phase',()=>{
 const d=acceptanceDiagnostics();d.setStep('dashboard.mobile');
 d.httpFailure('http://127.0.0.1:18996/api/v1/preferences',503);
 const r=failure(d);assert.equal(r.failure.step,'browser.http_failures');
 assert.equal(r.failure.message,'Expected 0 HTTP failures; observed 1.');
 assert.equal(r.diagnostics.httpFailures[0].status,503);
 assert.equal(r.diagnostics.httpFailures[0].step,'dashboard.mobile');
});
test('diagnostics never serialize secret operands, arbitrary page messages, URL credentials or queries',()=>{
 const secret='SYNTHETIC_SECRET_CANARY',d=acceptanceDiagnostics();d.setStep('dashboard.desktop');
 d.pageError({name:'TypeError',message:secret,stack:`TypeError: ${secret}\n at http://user:${secret}@localhost/assets/index-fixture.js:12:34?token=${secret}`});
 d.httpFailure(`http://user:${secret}@localhost/api/v1/routers/${secret}?password=${secret}`,401);
 const e=new Error(secret);e.actual={password:secret};e.expected={token:secret};
 const r=d.failure(e),json=JSON.stringify(r);
 assert.ok(!json.includes(secret));assert.ok(!json.includes('user:'));
 assert.equal(r.diagnostics.pageErrors[0].location,'/assets/index-fixture.js:12:34');
 assert.equal(r.diagnostics.httpFailures[0].path,'/api/v1/routers/<redacted>');
});
test('other assertion failure keeps its step and error code without raw diff; clean lists still pass',()=>{
 const d=acceptanceDiagnostics();d.assertRuntimeClean();d.setStep('dashboard.desktop');
 let error;try{assert.equal(7,8);}catch(e){error=e;}
 const r=d.failure(error);assert.equal(r.failure.step,'dashboard.desktop');assert.equal(r.failure.code,'ERR_ASSERTION');
 assert.match(r.failure.message,/AssertionError at dashboard.desktop/);
 assert.equal(r.status,'FAIL');
});

test('runner assertion location preserves only fixed basename and numeric position',()=>{
 const d=acceptanceDiagnostics(),e=new Error('SYNTHETIC_SECRET');
 e.stack='Error: SYNTHETIC_SECRET\n at inspectDashboard (file:///private/SYNTHETIC_SECRET/v26-browser-acceptance.mjs:74:11)';
 const r=d.failure(e);assert.equal(r.failure.location,'v26-browser-acceptance.mjs:74:11');assert.ok(!JSON.stringify(r).includes('SYNTHETIC_SECRET'));
});
