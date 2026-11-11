import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
const hooks={...React,useEffect:()=>{},useCallback:fn=>fn,useContext:()=>globalThis.__radiusUser,useState:initial=>[typeof initial==='function'?initial():initial,()=>{}]};
const code=(await build({entryPoints:['src/screens/RadiusCenter.tsx'],bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'resource',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'resource',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return globalThis.__radiusResource}',loader:'js'}));}}]})).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
function render(resource,admin=false){globalThis.__radiusResource={retry(){},...resource};globalThis.__radiusUser=admin?{role_code:'ADMIN',can_manage_users:true}:{role_code:'VIEWER'};globalThis.window={location:{hash:'#module=radius'}};return renderToStaticMarkup(module.exports.RadiusCenter());}
test('loading and error remain explicit; successful empty source has zero counts only after a verified read',()=>{
 const before=globalThis.window;
 try{
  const loading=render({loading:true});assert.match(loading,/Veriler yükleniyor/);assert.doesNotMatch(loading,/0 erişilebilir hesap/);
  const failed=render({loading:false,error:'Yetki gerekli'});assert.match(failed,/role="alert"/);assert.match(failed,/Yetki gerekli/);assert.doesNotMatch(failed,/0 erişilebilir hesap/);
  const empty=render({loading:false,data:[]});assert.match(empty,/0 erişilebilir hesap/);assert.match(empty,/sentetik hesap yok/);assert.match(empty,/FreeRADIUS bağlantısı ve canlı AAA ölçümü yok/);
 }finally{globalThis.window=before;delete globalThis.__radiusUser;delete globalThis.__radiusResource;}
});
test('visible records stay readonly, show unknown authority separately from Hotspot, and keep admin-only store choice',()=>{
 const before=globalThis.window;
 try{
  const row={id:'demo-sub-fixture',name:'Sentetik',username:'synthetic',authority:'UNKNOWN',access:'HOTSPOT',routerId:null,routerName:null,plan:'Demo',expiresOn:null,status:'PAUSED',revision:3};
  const html=render({loading:false,data:[row]});
  for(const text of [/Bilinmiyor/,/HOTSPOT/,/Revizyon 3/,/Duraklatıldı/,/Router bağı doğrulanamadı/])assert.match(html,text);
  assert.doesNotMatch(html,/value="PERSISTENT"|<form|type="submit"/);
  const admin=render({loading:false,data:[row]},true);assert.match(admin,/value="PERSISTENT"/);
 }finally{globalThis.window=before;delete globalThis.__radiusUser;delete globalThis.__radiusResource;}
});
