import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const {outputFiles}=await build({entryPoints:[fileURLToPath(new URL('../src/screens/CebeciAccessSecurity.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const {CebeciAccessSecurity}=module.exports;
const data={policy_version:'CEBECI_CLOSED_ACCESS_V1',decision:'NO_GO',plan_defined:true,offline_checklist_complete:false,security_status:'SECURITY NOT VERIFIED',connection_allowed:false,network_enabled:false,packet_digest:'a'.repeat(64),configuration:{network_enabled:false,reviewed_management_pin:null,reviewed_source_cidr:null,public_certificate_sha256:null,transport:'API_SSL',port:8729,verify_tls:true,verify_hostname:true,tls_minimum:'TLSv1.2'},
 checklist:[{criterion:'TLS',label:'TLS protokol/istemci',status:'UNKNOWN',reason_code:'TLS_UNKNOWN',evidence_required:'Doğrulanmış TLS kanıtı gerekli',source:'OFFLINE_UNVERIFIED'},{criterion:'EXPLICIT_EXECUTION_APPROVAL',label:'Ayrı gerçek bağlantı onayı',status:'BLOCKED',reason_code:'EXECUTION_NOT_AUTHORIZED',evidence_required:'Ayrı açık kullanıcı onayı gerekir',source:'SERVER_CLOSED_POLICY'}],
 blocking_findings:[{criterion:'TLS',status:'UNKNOWN',code:'TLS_UNKNOWN'},{criterion:'EXPLICIT_EXECUTION_APPROVAL',status:'BLOCKED',code:'EXECUTION_NOT_AUTHORIZED'}],read_scope:[{menu:'/system/identity',properties:['name'],operation:'print',live_access:false}],excluded_sources:['/ppp/secret','/ip/ipsec/installed-sa','/ip/ipsec/active-peers'],stop_conditions:['UNEXPECTED_WRITE_ATTEMPT','V1_IMPACT'],audit_fields:['candidate_id','fixed_reason_code']};
const render=value=>renderToStaticMarkup(createElement(CebeciAccessSecurity,{data:value}));
test('closed security contract renders missing evidence, safe defaults and no execution controls',()=>{
 const html=render(data);
 for(const text of ['NO_GO','NOT CONNECTED','APPROVAL REQUIRED','SECURITY NOT VERIFIED','network_enabled','false','UNASSIGNED / UNKNOWN','TLS_UNKNOWN','EXECUTION_NOT_AUTHORIZED','Doğrulanmış TLS','Ayrı açık kullanıcı onayı','read,api','lab kanıtı','V1_IMPACT'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/<button|<input|<select|<form/);
 assert.match(html,/credential\/PSK\/özel anahtar/);assert.match(html,/LIVE ACCESS DISABLED/);
});
test('a complete offline packet is never presented as approved or connected',()=>{
 const html=render({...data,offline_checklist_complete:true});
 assert.match(html,/yalnız incelemeye hazır/);assert.match(html,/gerçek bağlantı izni değildir/);
 assert.match(html,/NO_GO/);assert.match(html,/SECURITY NOT VERIFIED/);
 assert.doesNotMatch(html,/>GO<|>CONNECTED<|Bağlan<\/button>/);
});
test('status and evidence requirement come from protected API data, not hardcoded PASS',()=>{
 const html=render({...data,checklist:[{...data.checklist[0],status:'BLOCKED',reason_code:'CERTIFICATE_NAME_BLOCKED',evidence_required:'Fixture SAN uyuşmazlık kanıtı'}]});
 assert.match(html,/BLOCKED · TLS/);assert.match(html,/CERTIFICATE_NAME_BLOCKED/);assert.match(html,/Fixture SAN uyuşmazlık kanıtı/);
 assert.doesNotMatch(html,/PASS · TLS/);
});
test('missing security response remains explicit unverified NO_GO without fabricated checklist',()=>{
 const html=render(undefined);assert.match(html,/SECURITY NOT VERIFIED/);assert.match(html,/NO_GO/);assert.doesNotMatch(html,/Pilot güvenlik kontrol listesi|>PASS</);
});
