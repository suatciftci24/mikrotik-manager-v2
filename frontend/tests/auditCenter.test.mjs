import test from 'node:test';
import assert from 'node:assert/strict';
import {auditCsv,auditFilter,auditHash,auditQuery} from '../src/lib/auditCenter.ts';

test('report center filters are bounded, normalized and retained in the route',()=>{
 const filter=auditFilter('#module=dashboard&view=AUDIT_CENTER&audit_source=USER&start=2026-11-01&end=2026-11-03&router_id=r1&audit_actor=operator&audit_result=FAILED&audit_operation=UPDATE&q=alice&page=9999999',new Date('2026-11-08T08:00:00Z'));
 assert.equal(filter.source,'USER');assert.equal(filter.result,'FAILED');assert.equal(filter.page,10000);assert.equal(filter.query,'alice');
 const query=new URLSearchParams(auditQuery(filter));assert.equal(query.get('page_size'),'25');assert.equal(query.get('router_id'),'r1');
 const hash=auditHash(filter);assert.match(hash,/audit_source=USER/);assert.match(hash,/audit_result=FAILED/);assert.match(hash,/q=alice/);
});

test('unknown source and result values fail closed to explicit defaults',()=>{
 const filter=auditFilter('#audit_source=SYSTEM&audit_result=OK&page=-10',new Date('2026-11-08T08:00:00Z'));
 assert.equal(filter.source,'SUBSCRIBER');assert.equal(filter.result,'ALL');assert.equal(filter.page,1);
 assert.match(auditHash(filter),/audit_source=SUBSCRIBER/);
});

test('CSV quotes cells and neutralizes formula prefixes using only the export allowlist',()=>{
 const csv=auditCsv([{occurred_at:'2026-11-08T10:00:00Z',actor_id:'=HYPERLINK("x")',target_id:'@cmd',router_id:null,operation:'UPDATE',result:'FAILED',source:'USER_AUDIT',audit_id:'uuid',id:'uuid',details:{password:'never-export'}}]);
 assert.match(csv,/"'=HYPERLINK\(""x""\)"/);assert.match(csv,/"'@cmd"/);assert.doesNotMatch(csv,/never-export|password/);
});
