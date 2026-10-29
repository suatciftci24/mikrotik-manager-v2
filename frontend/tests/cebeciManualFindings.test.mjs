import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
async function load(file){const {outputFiles}=await build({entryPoints:[fileURLToPath(new URL('../src/screens/'+file,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']});const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);return module.exports;}
const {CebeciManualFindings}=await load('CebeciManualFindings.tsx');
const {CebeciAccessSecurity}=await load('CebeciAccessSecurity.tsx');
const option=id=>({id,label:id==='A'?'Doğrulanmış TLS ile API-SSL':'Doğrulanmış IPsec yolu üzerinden API 8728',status:id==='A'?'BLOCKED_REPORTED':'BLOCKED_BY_CURRENT_CONTRACT',current_contract:'SEPARATE_REVIEW_REQUIRED',approved:false,encryption:'Şifreleme kanıtı gerekli',authentication:'Ayrı kimlik kanıtı',source_isolation:'Tek /32 kaynak',ros6_limits:'Lab gerekli',v1_impact:'V1 etkisi UNKNOWN',operational_risk:'Fallback yok'});
const data={source:'OPERATOR_REPORTED_MANUAL',verification_type:'MANUAL_OBSERVATION',observed_at:null,freshness:'UNKNOWN',identity_match_reported:true,decision:'NO_GO',connection:'NOT CONNECTED',approval:'APPROVAL REQUIRED',technical_suitability:'NOT_VERIFIED',operator_approval:'NOT_RECORDED',execution_authority:'DENIED',
 findings:[{id:'TLS',label:'API-SSL / sertifika',summary:'API-SSL kapalı; certificate=none; TLS NOT VERIFIED.',source:'OPERATOR_REPORTED_MANUAL',verification_type:'MANUAL_OBSERVATION',observed_at:null,freshness:'UNKNOWN'}],
 matrix:[{criterion:'CERTIFICATE',label:'API-SSL zincir',status:'MISSING',manual_status:'BLOCKED_REPORTED',manual_reason:'Sertifika yok bildirimi',manual_freshness:'UNKNOWN',observation_ids:['TLS'],evidence_type:'Bağımsız zincir/SAN kanıtı',validity_seconds:300,stop_condition:'TLS doğrulanmadı'}],critical_risks:['EXISTING_ACCOUNT_WRITE_TEST_NOT_READ_ONLY'],remaining_evidence:['CERTIFICATE'],access_options:[option('A'),option('B')],account_plan:{policies:['read','api'],status:'LAB_VERIFICATION_REQUIRED',existing_accounts_unchanged:true}};
const render=value=>renderToStaticMarkup(createElement(CebeciManualFindings,{data:value}));
test('manual provenance, unknown date and report match stay distinct from current verification',()=>{
 const html=render(data);for(const text of ['MANUAL OBSERVATION','OPERATOR_REPORTED_MANUAL','Gözlem tarihi: UNKNOWN','MANUAL MATCH REPORTED','bağımsız canlı doğrulama yok','NOT_VERIFIED','NOT_RECORDED','DENIED','BLOCKED_REPORTED','MISSING','TLS NOT VERIFIED'])assert.ok(html.includes(text),text);
 assert.match(html,/güncel veya eskimiş olduğu varsayılmaz/);assert.doesNotMatch(html,/>GO<|>CONNECTED<|<button|<input|<form|<select/);
});
test('stale evidence and identity conflict render from API without turning it into approval',()=>{
 const html=render({...data,observed_at:'2026-10-29T10:00:00+00:00',freshness:'STALE',identity_match_reported:false,matrix:[{...data.matrix[0],manual_freshness:'STALE'}]});
 assert.match(html,/CONFLICT \/ STOP/);assert.match(html,/Kanıt güncelliği: STALE/);assert.match(html,/NO_GO/);assert.doesNotMatch(html,/Tarih bilinmediği için/);
});
test('both comparison options cover security dimensions but B cannot bypass TLS contract',()=>{
 const html=render(data);for(const text of ['A) Doğrulanmış TLS','B) Doğrulanmış IPsec','BLOCKED_BY_CURRENT_CONTRACT','NOT APPROVED','Şifreleme','Kimlik doğrulama','Kaynak izolasyonu','RouterOS 6 sınırları','V1 etkisi','Operasyonel risk','fallback değildir','read, api','LAB_VERIFICATION_REQUIRED','yalnız doküman planıdır'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/<button|<input|<form|<select/);
});
test('missing manual response is explicit UNKNOWN and closed',()=>{const html=render(undefined);assert.match(html,/Manuel inceleme alınmadı/);assert.match(html,/NO_GO/);assert.doesNotMatch(html,/MANUAL MATCH REPORTED/);});
test('existing protected security panel passes manual API data to the new section',()=>{
 const html=renderToStaticMarkup(createElement(CebeciAccessSecurity,{data:{manual_review:data,decision:'NO_GO',plan_defined:true,offline_checklist_complete:false,configuration:{network_enabled:false,transport:'API_SSL',port:8729,tls_minimum:'TLSv1.2',reviewed_management_pin:null,reviewed_source_cidr:null,public_certificate_sha256:null},policy_version:'CEBECI_CLOSED_ACCESS_V1',packet_digest:'a'.repeat(64),checklist:[],blocking_findings:[],read_scope:[],excluded_sources:[],stop_conditions:[],audit_fields:[]}}));
 assert.match(html,/aria-label="Manuel pilot karar merkezi"/);assert.match(html,/Sertifika yok bildirimi/);assert.match(html,/TLS NOT VERIFIED/);
});
