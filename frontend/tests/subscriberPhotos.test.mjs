import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {assertSubscriberPhotos,subscriberPhotoImagePath,subscriberPhotosPath} from '../src/lib/subscriberPhotos.ts';

const id='demo-sub-photo-fixture',photoId='a'.repeat(32);
const collection={subscriber_id:id,source:'LOCAL',access_type:'PPPOE',is_demo:true,items:[]};
test('photo collection is bound to exact subscriber authority and safe generated image paths',()=>{
 assert.equal(assertSubscriberPhotos(collection,id,'LOCAL','PPPOE'),collection);
 assert.equal(subscriberPhotosPath(id),'/subscriber-center/demo-sub-photo-fixture/photos');
 assert.equal(subscriberPhotoImagePath(id,photoId,'thumbnail'),`${subscriberPhotosPath(id)}/${photoId}?variant=thumbnail`);
 assert.throws(()=>assertSubscriberPhotos({...collection,subscriber_id:'demo-sub-other'},id,'LOCAL','PPPOE'));
 assert.throws(()=>assertSubscriberPhotos({...collection,source:'RADIUS'},id,'LOCAL','PPPOE'));
 assert.throws(()=>subscriberPhotoImagePath(id,'../private','full'));
});

const require=createRequire(import.meta.url);
let state={loading:true};
async function compile(){
 const plugin={name:'photo-test-stubs',setup(build){
  build.onResolve({filter:/\/lib\/useResource(?:\.ts)?$/},()=>({path:'resource-stub',namespace:'photo-test'}));
  build.onResolve({filter:/\/components\/Resource(?:\.tsx?)?$/},()=>({path:'resource-view-stub',namespace:'photo-test'}));
  build.onLoad({filter:/.*/,namespace:'photo-test'},args=>({contents:args.path==='resource-view-stub'?"export function ResourceState({loading,error}){return loading? <p role='status'>Fotoğraflar yükleniyor…</p>:error?<p role='alert'>{error}</p>:null} export function dateTime(){return '08 Kas 2026 12:00'}":args.path==='api-stub'?'export async function api(){return {}};':'export const useResource=()=>globalThis.__photoState;',loader:'jsx'}));
  build.onResolve({filter:/\/lib\/api(?:\.ts)?$/},()=>({path:'api-stub',namespace:'photo-test'}));
  build.onLoad({filter:/.*/,namespace:'photo-test'},args=>({contents:'export async function api(){return {}};',loader:'js'}));
 }};
 const code=(await build({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberPhotos.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[plugin]})).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(require,module,module.exports);return module.exports.SubscriberPhotos;
}
const SubscriberPhotos=await compile();
function render(props={}){globalThis.__photoState=state;return renderToStaticMarkup(React.createElement(SubscriberPhotos,{id,source:'LOCAL',accessType:'PPPOE',canManage:true,...props}));}
test('photo panel distinguishes loading, error, empty and authorized ready states',()=>{
 state={loading:true};let html=render();assert.match(html,/Veriler yükleniyor/);assert.match(html,/aria-label="Kurulum fotoğrafı seç" type="file"[^>]*disabled/);
 state={loading:false,error:'Liste alınamadı'};html=render();assert.match(html,/Liste alınamadı/);assert.match(html,/aria-label="Kurulum fotoğrafı seç" type="file"[^>]*disabled/);
 state={loading:false,data:collection};html=render();assert.match(html,/Henüz bu aboneye ait kurulum fotoğrafı yok/);assert.match(html,/Fotoğraf ekle/);
 html=render({canManage:false});assert.doesNotMatch(html,/Fotoğraf ekle/);assert.doesNotMatch(html,/Fotoğrafı sil/);
});
test('ready photo rendering uses generated thumbnail/full paths and never shows stale content on loading',()=>{
 state={loading:false,data:{...collection,items:[{id:photoId,created_at:'2026-11-08T09:00:00Z',size_bytes:2048,media_type:'image/jpeg'}]}};
 let html=render();assert.match(html,new RegExp(photoId));assert.match(html,/variant=thumbnail/);assert.match(html,/Fotoğrafı tam boyutta görüntüle/);assert.match(html,/Sil/);
 state={loading:true,data:collection};html=render();assert.doesNotMatch(html,/variant=thumbnail|Henüz bu aboneye/);
});
