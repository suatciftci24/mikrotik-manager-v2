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
test('same twenty canonical fields render expected proof, acceptance, source, TTL, STOP and completion',()=>{
 const html=render(props);assert.match(html,/Aşama 27/);assert.match(html,/Pilot ön koşul kabul ölçütleri/);
 assert.equal(props.preparation.evidence_fields.length,20);assert.equal(props.packet.matrix_links.length,9);assert.equal(props.preparation.groups.length,8);
 for(const row of props.preparation.evidence_fields){for(const key of ['evidence_required','acceptance_criteria','expected_source','completion_method','stop_condition'])assert.ok(html.includes(row[key]),row.field+' '+key);}
 assert.match(html,/Geçerlilik üst sınırı: 300 saniye/);assert.match(html,/CEBECI_EVIDENCE_ACCEPTANCE_V1/);
});
test('explicit live approval and offline report review are distinct and neither is an approval action',()=>{
 const html=render(props);
 for(const text of ['EXPLICIT_APPROVAL_BEFORE_LIVE_VERIFICATION_OR_CHANGE','OFFLINE_REPORT_REVIEW','SEPARATE_EXPLICIT_USER_APPROVAL_AND_EXECUTION_REVIEW','Canlı doğrulama veya değişiklikten önce ayrı açık kullanıcı/operatör onayı','Mevcut offline rapor incelemesi','burada onay verilmez','NOT_RECORDED','DENIED'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/<button|<input|<select|<form/);
});
test('missing or modified criteria stay visible as blocked without fabricating a requirement',()=>{
 const value=structuredClone(props);delete value.preparation.evidence_fields[0].acceptance_criteria;
 value.packet.sources_complete=false;value.packet.integrity_errors=['EVIDENCE_ACCEPTANCE_RULES_INVALID'];
 const html=render(value);assert.match(html,/role="alert"/);assert.match(html,/EVIDENCE_ACCEPTANCE_RULES_INVALID/);assert.match(html,/UNKNOWN \/ BLOCKED/);assert.match(html,/NO_GO/);
});
test('old manual unknown time and closed TLS policy survive the new acceptance guidance',()=>{
 const html=render(props);assert.equal(props.manual.observed_at,null);assert.equal(props.packet.counts.verified,0);
 for(const text of ['UNKNOWN','UNKNOWN zaman STALE yapılmaz','BLOCKED_BY_CURRENT_TLS_CONTRACT','TLS istisnası veya fallback değildir','read,api ROS6 lab kanıtı olmadan yeterli değildir'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/>GO<|>APPROVED<|>CONNECTED</);
});
test('guidance stays inside the one existing decision packet on the actual pilot screen',()=>{
 globalThis.__decisionResource={data:profile,loading:false,retry(){}};
 const html=renderToStaticMarkup(createElement(CebeciPilot));
 assert.equal((html.match(/aria-label="Birleşik pilot karar paketi"/g)||[]).length,1);
 assert.equal((html.match(/aria-label="Pilot ön koşul kabul ölçütleri"/g)||[]).length,1);
 assert.match(html,/SOURCE_FIREWALL/);assert.match(html,/ROLLBACK/);
});
