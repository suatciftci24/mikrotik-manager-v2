import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const {outputFiles}=await build({entryPoints:[fileURLToPath(new URL('../src/screens/CebeciPrerequisites.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const render=data=>renderToStaticMarkup(createElement(module.exports.CebeciPrerequisites,{data}));
const data={decision:'NO_GO',technical_suitability:'NOT_VERIFIED',operator_approval:'NOT_RECORDED',execution_authority:'DENIED',approval:'APPROVAL REQUIRED',missing_prerequisites:['CERTIFICATE'],reasons:['EXECUTION_DISABLED'],matrix:[{criterion:'CERTIFICATE',label:'TLS kanıtı',status:'STALE',reason_code:'EVIDENCE_EXPIRED',evidence_type:'Maskeli public kanıt',verification_method:'Bağımsız zincir incelemesi',validity_seconds:300,responsible_role:'SECURITY_REVIEWER',stop_condition:'SAN uyuşmazlığı',reviewed_at:null,expires_at:null,source:'OFFLINE_UNVERIFIED'}]};
test('matrix renders actual evidence status, validity, reviewer, STOP and missing prerequisites',()=>{
 const html=render(data);for(const text of ['EVIDENCE_EXPIRED','STALE','300 saniye','SECURITY_REVIEWER','SAN uyuşmazlığı','Bağımsız zincir incelemesi','UNKNOWN','CERTIFICATE','EXECUTION_DISABLED','NOT_RECORDED','DENIED'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/<button|<input|<form|<select/);
});
test('offline readiness never displays execution approval or live connectivity',()=>{
 const html=render({...data,technical_suitability:'OFFLINE_REVIEW_READY',missing_prerequisites:[]});
 for(const text of ['NO_GO','NOT CONNECTED','APPROVAL REQUIRED','OFFLINE_REVIEW_READY','güncel erişim kanıtı değildir'])assert.ok(html.includes(text));
 assert.doesNotMatch(html,/>GO<|>CONNECTED<|>APPROVED</);
});
test('missing contract fails closed with no fabricated receipt',()=>{
 const html=render(undefined);assert.match(html,/Kanıt matrisi alınmadı/);assert.match(html,/NO_GO/);assert.doesNotMatch(html,/REVIEW_READY|EVIDENCE_EXPIRED/);
});
