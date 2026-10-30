import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {pilotTestPayload} from '../src/lib/cebeciPilot.ts';
const require=createRequire(import.meta.url);
let optionsFixture=null;
const react={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>({current:value}),useState:initial=>{const value=typeof initial==='function'?initial():initial;return [value?.path==='/router-registry/options'&&optionsFixture?{...value,loading:false,data:optionsFixture}:value,()=>{}];}};
function load(path){const code=buildSync({entryPoints:[fileURLToPath(new URL(path,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);return module.exports;}
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('pilot payload fixed, public only and explicit consent required',()=>{
 assert.throws(()=>pilotTestPayload('id',false));const body=pilotTestPayload('id',true);
 assert.equal(body.management_address,'10.250.0.19');assert.equal(body.port,8729);assert.equal(body.credential_alias,'CEBECI_TOWERS_RO');assert.ok(!('password' in body));assert.ok(!('ca_pem' in body));
});
test('pilot initial test and save are disabled; rendering starts no API call',()=>{
 globalThis.window={isSecureContext:true};
 const {CebeciPilotOnboarding}=load('../src/components/CebeciPilotOnboarding.tsx');
 const tree=CebeciPilotOnboarding({onClose(){},onSaved(){}});const buttons=nodes(tree).filter(n=>n.type==='button');
 assert.ok(buttons.filter(n=>['Bağlantıyı Test Et',"Router'ı Kaydet"].includes(n.props.children)).every(n=>n.props.disabled));
 const html=renderToStaticMarkup(tree);assert.match(html,/Gerçek Router/);assert.match(html,/yalnız identity\/resource/);assert.match(html,/v2-cebeci-ro/);assert.doesNotMatch(html,/type="password"/);
});
test('detail read requires its own consent and never runs during render',()=>{
 const {RouterPilotRead}=load('../src/components/RouterPilotRead.tsx');const tree=RouterPilotRead({id:'registered-fixture',revision:1,enabled:true});
 assert.ok(nodes(tree).find(n=>n.type==='button').props.disabled);assert.match(renderToStaticMarkup(tree),/Otomatik polling veya tekrar yoktur/);
});

test('authenticated operator ID is read-only metadata; closed gate stays closed',()=>{
 globalThis.window={isSecureContext:true};
 optionsFixture={connection_enabled:false,operator_authorized:false,operator_candidate:{id:'fixture-existing-operator',revision:2,source:'V2_AUTHENTICATED_SESSION'},source_ip:'10.250.0.1',allowed_networks:['10.250.0.19/32'],allowed_ports:[8729]};
 try{
  const {CebeciPilotOnboarding}=load('../src/components/CebeciPilotOnboarding.tsx');
  const tree=CebeciPilotOnboarding({onClose(){},onSaved(){}});const html=renderToStaticMarkup(tree);
  assert.match(html,/fixture-existing-operator/);assert.match(html,/Bu bilgi yetki vermez/);assert.doesNotMatch(html,/type="password"/);
  for(const button of nodes(tree).filter(node=>node.type==='button'&&['Bağlantıyı Test Et',"Router'ı Kaydet"].includes(node.props.children)))assert.ok(button.props.disabled);
 }finally{optionsFixture=null;}
});
