import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url),root=fileURLToPath(new URL('../../',import.meta.url));
// Consume the real offline domain contract instead of copying 9/8/20 models into fixtures.
const {stdout}=await promisify(execFile)(root+'.venv/bin/python',['-c',"import json; from unittest.mock import patch; from app.services.identity import public_user,bootstrap; from app.integrations.cebeci_preparation import profile\nwith patch('socket.socket',side_effect=AssertionError('network forbidden')): result=profile(public_user(bootstrap()))\nprint(json.dumps(result))"],{cwd:root,env:{...process.env,PYTHONPATH:'backend'},encoding:'utf8'});
const profile=JSON.parse(stdout);
const {outputFiles}=await build({stdin:{contents:"export {CebeciDecisionPacket} from './src/screens/CebeciDecisionPacket';export {CebeciPilot} from './src/screens/CebeciPilot';",resolveDir:root+'frontend',loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'offline-resource',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return globalThis.__decisionResource}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const {CebeciDecisionPacket,CebeciPilot}=module.exports;
const source=profile.access_preparation;
const props={packet:source.decision_packet,preparation:source.account_preparation,manual:source.manual_review,prerequisites:source.prerequisites};
const render=data=>renderToStaticMarkup(createElement(CebeciDecisionPacket,data));
test('real offline API contract renders one joined packet with distinct missing/manual/verified/unknown counts',()=>{
 const html=render(props);for(const text of ['Eksik (20)','Manuel (8)','Doğrulanmış (0)','Süresi geçmiş (0)','Zamanı UNKNOWN (28)','NOT_VERIFIED','NOT_RECORDED','DENIED','NO_GO','NOT CONNECTED','APPROVAL REQUIRED'])assert.ok(html.includes(text),text);
 for(const link of props.packet.matrix_links)assert.ok(html.includes(link.criterion+' · '));
 assert.doesNotMatch(html,/<button|<input|<select|<form/);
});
test('stale and manual evidence remain separate axes with actual source time displayed',()=>{
 const value=structuredClone(props),field=value.preparation.evidence_fields[0],ref='field:'+field.field;
 field.status='STALE';field.observed_at='2026-10-29T00:00:00+00:00';
 value.packet.evidence_buckets.expired=[ref];value.packet.evidence_buckets.manual.push(ref);
 const html=render(value);assert.match(html,/Süresi geçmiş \(1\)/);assert.match(html,/Manuel \(9\)/);assert.match(html,/2026-10-29T00:00:00\+00:00/);assert.match(html,/Doğrulanmış \(0\)/);assert.match(html,/UNKNOWN zaman STALE yapılmaz/);
});
test('A/B decision table keeps blocked TLS exception and read-only operator next steps',()=>{
 const html=render(props);
 for(const text of ['Pilot taşıma karar tablosu','API-SSL 8729','API 8728 üzerinden IPsec','BLOCKED_BY_CURRENT_TLS_CONTRACT','TLS istisnası veya fallback değildir','Şifreleme','Kimlik doğrulama','V1 etkisi','Kaynak izolasyonu','Operasyonel risk','Pilot operatör kararları','Pilot güvenli sonraki adımlar'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/<button|<input|<select|<form/);
});
test('missing source or source integrity failure shows explicit closed packet',()=>{
 assert.match(render({...props,manual:undefined}),/Karar kaynakları eksik/);
 const html=render({...props,packet:{...props.packet,sources_complete:false,integrity_errors:['UNSUPPORTED_EVIDENCE_STATE']}});
 assert.match(html,/role="alert"/);assert.match(html,/UNSUPPORTED_EVIDENCE_STATE/);assert.match(html,/NO_GO/);
});
test('actual pilot screen places the unified packet first after data is loaded and does not fabricate it while loading',()=>{
 globalThis.__decisionResource={data:profile,loading:false,retry(){}};
 const html=renderToStaticMarkup(createElement(CebeciPilot));assert.ok(html.indexOf('aria-label="Birleşik pilot karar paketi"')<html.indexOf('Bilinen geçmiş bilgiler'));
 assert.equal((html.match(/aria-label="Birleşik pilot karar paketi"/g)||[]).length,1);
 globalThis.__decisionResource={loading:true,retry(){}};
 assert.doesNotMatch(renderToStaticMarkup(createElement(CebeciPilot)),/aria-label="Birleşik pilot karar paketi"/);
});
