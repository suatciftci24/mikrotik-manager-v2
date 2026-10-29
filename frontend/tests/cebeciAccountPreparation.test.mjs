import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
async function load(file){const {outputFiles}=await build({entryPoints:[fileURLToPath(new URL('../src/screens/'+file,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']});const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);return module.exports;}
const {CebeciAccountPreparation}=await load('CebeciAccountPreparation.tsx');
const {CebeciAccessSecurity}=await load('CebeciAccessSecurity.tsx');
const data={version:'CEBECI_ACCOUNT_PREPARATION_V1',packet_sha256:'a'.repeat(64),decision:'NO_GO',operator_approval:'NOT_RECORDED',execution_authority:'DENIED',account_status:'NOT_CREATED_NOT_VERIFIED',minimum_privilege_status:'ROS6_LAB_NOT_VERIFIED',synthetic_checklist_complete:false,contract:{policies:['read','api'],account_reuse:'FORBIDDEN',credential_intake:'NONE'},forbidden_policies:['write','policy','sensitive','password','reboot'],groups:[{id:'PILOT_ACCOUNT',label:'Ayrı V2 pilot hesabı',status:'NOT_READY',fields:['ACCOUNT_SEPARATE'],missing_fields:['ACCOUNT_SEPARATE']}],evidence_fields:[{field:'TLS_CHAIN',label:'TLS güven zinciri',status:'MISSING',reason_code:'EVIDENCE_MISSING',evidence_required:'Bağımsız güven zinciri incelemesi',source:'NOT_PROVIDED',observed_at:null,validity_seconds:300}],transport_options:[{id:'A',label:'API-SSL 8729',status:'NO_GO_APPROVAL_AND_LIVE_VERIFICATION_REQUIRED',required_fields:['TLS_CHAIN'],missing_fields:['TLS_CHAIN'],approved:false,connection_allowed:false},{id:'B',label:'API 8728 üzerinden IPsec',status:'BLOCKED_BY_CURRENT_TLS_CONTRACT',required_fields:['IPSEC_AUTH'],missing_fields:['IPSEC_AUTH'],approved:false,connection_allowed:false}],missing_evidence:['TLS_CHAIN','IPSEC_AUTH'],stop_conditions:['TLS_OR_IPSEC_UNVERIFIED','V1_IMPACT']};
const render=value=>renderToStaticMarkup(createElement(CebeciAccountPreparation,{data:value}));
test('account contract renders missing evidence and no creation, credential or connection controls',()=>{
 const html=render(data);for(const value of ['NO_GO','NOT CONNECTED','APPROVAL REQUIRED','NOT_CREATED_NOT_VERIFIED','ROS6_LAB_NOT_VERIFIED','read, api','FORBIDDEN','NONE','write, policy, sensitive, password, reboot','TLS_CHAIN · MISSING · EVIDENCE_MISSING','UNKNOWN','300 saniye','NOT_RECORDED','DENIED'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/<button|<input|<select|<form/);
});
test('synthetic completeness never becomes operator approval or connection readiness',()=>{
 const html=render({...data,synthetic_checklist_complete:true});assert.match(html,/Sentetik kontrol listesi tam; yalnız simülasyon/);assert.match(html,/NO_GO/);assert.match(html,/NOT_RECORDED/);assert.match(html,/DENIED/);
 assert.doesNotMatch(html,/>GO<|>APPROVED<|>CONNECTED</);
});
test('independent evidence states and blocked IPsec API option remain explicit',()=>{
 const html=render({...data,evidence_fields:[{...data.evidence_fields[0],status:'STALE',reason_code:'EVIDENCE_EXPIRED',observed_at:'2026-10-29T10:00:00+00:00'}]});
 for(const value of ['TLS_CHAIN · STALE · EVIDENCE_EXPIRED','2026-10-29T10:00:00+00:00','IPSEC_AUTH','BLOCKED_BY_CURRENT_TLS_CONTRACT','NOT APPROVED','CONNECTION DISABLED','bir alandaki bildirim diğerini doğrulamaz','V1_IMPACT'])assert.ok(html.includes(value),value);
});
test('missing preparation response stays unknown and closed',()=>{const html=render(undefined);assert.match(html,/sözleşmesi alınmadı/);assert.match(html,/UNKNOWN/);assert.match(html,/NO_GO/);assert.doesNotMatch(html,/SYNTHETIC_REVIEW_PASS/);});
test('existing admin security panel passes the new preparation contract through',()=>{
 const html=renderToStaticMarkup(createElement(CebeciAccessSecurity,{data:{account_preparation:data,decision:'NO_GO',plan_defined:true,offline_checklist_complete:false,configuration:{network_enabled:false,transport:'API_SSL',port:8729,tls_minimum:'TLSv1.2'},policy_version:'CEBECI_CLOSED_ACCESS_V1',packet_digest:'a'.repeat(64),checklist:[],blocking_findings:[],read_scope:[],excluded_sources:[],stop_conditions:[],audit_fields:[]}}));
 assert.match(html,/aria-label="Pilot hesap ve bağlantı hazırlığı"/);assert.match(html,/Bağımsız güven zinciri incelemesi/);assert.match(html,/BLOCKED_BY_CURRENT_TLS_CONTRACT/);
});
