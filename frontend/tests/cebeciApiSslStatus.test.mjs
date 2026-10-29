import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const root=fileURLToPath(new URL('../../',import.meta.url)),require=createRequire(import.meta.url);
const {stdout}=await promisify(execFile)(root+'.venv/bin/python',['-c',"import json; from unittest.mock import patch; from app.services.identity import public_user,bootstrap; from app.integrations.cebeci_preparation import profile\nwith patch('socket.socket',side_effect=AssertionError('No socket')): result=profile(public_user(bootstrap()))\nprint(json.dumps(result))"],{cwd:root,env:{...process.env,PYTHONPATH:'backend',V2_CEBECI_API_SSL_ENABLED:'true',V2_CEBECI_API_SSL_PASSWORD:'SYNTHETIC_SECRET_CANARY'},encoding:'utf8'});
const profile=JSON.parse(stdout);
const {outputFiles}=await build({stdin:{contents:"export {CebeciPilot} from './src/screens/CebeciPilot'",resolveDir:root+'frontend',loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'offline-resource',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return globalThis.__apiSslResource}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const render=data=>{globalThis.__apiSslResource={data,loading:false,retry(){}};return renderToStaticMarkup(createElement(module.exports.CebeciPilot));};
test('ADMIN pilot screen only reports closed/not-ready API-SSL despite an enable request',()=>{
 const html=render(profile),status=html.match(/<p aria-label="API-SSL adaptör durumu">(.*?)<\/p>/s)?.[1];
 assert.ok(status);assert.match(status,/NOT CONNECTED/);assert.match(status,/NOT READY/);assert.match(status,/Gerçek bağlantı kapalı \/ NO_GO/);
 assert.doesNotMatch(status,/<button|<input|<select|<form/);assert.doesNotMatch(html,/SYNTHETIC_SECRET_CANARY/);
 assert.equal(profile.access_preparation.api_ssl_adapter.execution_enabled,false);
});
test('missing adapter status never fabricates a ready or connected state',()=>{
 const data=structuredClone(profile);delete data.access_preparation.api_ssl_adapter;
 const html=render(data),status=html.match(/<p aria-label="API-SSL adaptör durumu">(.*?)<\/p>/s)?.[1];
 assert.match(status,/NOT CONNECTED/);assert.match(status,/NOT READY/);assert.match(status,/NO_GO/);
});
test('status does not create a second pilot screen or credential input path',()=>{
 const html=render(profile);assert.equal((html.match(/aria-label="CEBECI_TOWERS hazırlık profili"/g)||[]).length,1);
 assert.equal((html.match(/aria-label="API-SSL adaptör durumu"/g)||[]).length,1);
 assert.doesNotMatch(html,/<input|<form|>Bağlan<|>Hesap etkinleştir</);
});
