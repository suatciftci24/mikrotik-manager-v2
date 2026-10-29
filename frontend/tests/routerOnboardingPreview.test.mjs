import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {offlineRouterPreview,syntheticRouterPreview} from '../src/lib/routerOnboardingPreview.ts';
import {routerConnectionProfiles,connectionProfile} from '../src/lib/routerConnectionProfiles.ts';
import {emptyRouterForm} from '../src/lib/routerRegistry.ts';
const form={...emptyRouterForm,name:'Lab',management_address:'192.0.2.10',username:'test-ro',password:'PASSWORD_CANARY',ca_pem:'-----BEGIN CERTIFICATE-----\nQUJD\n-----END CERTIFICATE-----',leaf_sha256:'a'.repeat(64)};

test('offline preview checks form but creates no device proof, credentials or persisted record',()=>{
 const preview=offlineRouterPreview(form);
 assert.equal(preview.is_demo,true);assert.equal(preview.persisted,false);assert.equal(preview.device_connected,false);
 for(const key of ['verification_id','saved_router_id','password','username','ca_pem','credential_ref'])assert.equal(key in preview,false);
 assert.doesNotMatch(JSON.stringify(preview),/PASSWORD_CANARY|test-ro|BEGIN CERTIFICATE/);
 assert.match(preview.trust,/yalnız gerçek bağlantıda/);assert.match(preview.identity,/okunmadı/);
 assert.equal(syntheticRouterPreview().endpoint,'192.0.2.10:8729');
 assert.match(offlineRouterPreview({...form,ca_pem:form.ca_pem+'\n'+form.ca_pem}).certificate,/biçimi uygun/);
});
test('missing certificate, malformed PEM, private keys, missing pin and insecure port fail offline',()=>{
 for(const update of [{ca_pem:''},{ca_pem:'DER_OR_OTHER_TEXT'},{ca_pem:'-----BEGIN PRIVATE KEY-----'},{leaf_sha256:''},{port:'8728'}])assert.throws(()=>offlineRouterPreview({...form,...update}));
 const item={id:'registered-test',revision:1};
 assert.match(offlineRouterPreview({...form,username:'',password:'',ca_pem:''},item).certificate,/korunacak/);
});
test('profiles are immutable secret-free defaults with mandatory TLS/SAN/pin',()=>{
 assert.equal(routerConnectionProfiles.length,3);
 for(const profile of routerConnectionProfiles){
  assert.equal(profile.verifyChain,true);assert.equal(profile.verifyIpSan,true);assert.equal(profile.requireLeafPin,true);assert.equal(profile.readOnly,true);assert.equal(profile.transport,'API_SSL');
  assert.equal(Object.isFrozen(profile),true);
  for(const key of ['username','password','ca_pem','leaf_sha256','management_address'])assert.equal(key in profile,false);
 }
 assert.throws(()=>connectionProfile('insecure'));
});
test('closed policy UI permits local preview without verification, save or network writes',()=>{
 const require=createRequire(import.meta.url),states=[];
 const react={...React,useEffect:()=>{},useCallback:fn=>fn,useRef:value=>({current:value}),useState:initial=>{
  const value=typeof initial==='function'?initial():initial;
  if(value?.path==='/router-registry/options')return [{...value,loading:false,data:{connection_enabled:false,operator_authorized:false,allowed_ports:[8729]}},()=>{}];
  return [value,next=>states.push(next)];
 }};
 const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/RouterOnboarding.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),module,module.exports);
 const previousWindow=globalThis.window,previousFetch=globalThis.fetch;let writes=0;
 globalThis.window={isSecureContext:true};globalThis.fetch=()=>{writes++;throw new Error('network forbidden');};
 try{
  const element=module.exports.RouterOnboarding({onClose:()=>{},onSaved:()=>{throw Error('save forbidden');}});
  const html=renderToStaticMarkup(element);
  assert.match(html,/Zorunlu/);assert.match(html,/İsteğe bağlı/);assert.match(html,/PEM dosyası yükleyin/);assert.match(html,/Canlı onboarding sunucu yapılandırmasında kapalı/);
  const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
  const buttons=nodes(element).filter(e=>e.type==='button');
  assert.equal(buttons.find(e=>e.props.children==='Gerçek bağlantı kapalı · Yalnız form kontrolü ve önizleme').props.disabled,true);
  const synthetic=buttons.find(e=>e.props.children==='Sentetik örneği önizle');assert.equal(synthetic.props.type,'button');synthetic.props.onClick();
  assert.equal(states.at(-1).is_demo,true);assert.equal(states.at(-1).device_connected,false);
  buttons.find(e=>e.props.children==='Formu bağlantısız kontrol et').props.onClick();
  assert.equal(states.at(-1),'Router adı gerekli.');assert.equal(writes,0);
 }finally{globalThis.window=previousWindow;globalThis.fetch=previousFetch;}
});
