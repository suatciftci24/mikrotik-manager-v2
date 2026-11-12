import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let opened=false,scenario='PLAN',aaaResource,reads=[],selected;
const row={id:'demo-sub-one',name:'Örnek hesap',username:'example',authority:'LOCAL',access:'PPPOE',routerId:null,routerName:null,plan:'Örnek',expiresOn:null,status:'PAUSED',revision:1};
const hooks={...React,useEffect:()=>{},useCallback:fn=>fn,useContext:()=>({role_code:'VIEWER'}),useState:initial=>[initial===false?opened:initial==='PLAN'?scenario:typeof initial==='function'?initial():initial,value=>{selected=value;}]};
globalThis.__aaaManagementRead=path=>{
 reads.push(path);
 return path.startsWith('/aaa-demo/')?{retry(){},...aaaResource}:{loading:false,retry(){},data:[row,{...row,id:'demo-sub-two',authority:'RADIUS'},{...row,id:'demo-sub-three',authority:'UNKNOWN'}]};
};
const compiled=await build({stdin:{contents:"export {RadiusCenter} from './src/screens/RadiusCenter'; export {AaaDemoScenarios,loadAaaDemoPreview} from './src/components/SubscriberAaaDemo';",resolveDir:process.cwd()},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',loader:{'.css':'empty'},external:['react','react/jsx-runtime'],plugins:[{name:'read-model',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'read',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path,loader){ globalThis.__aaaLoader=loader; return globalThis.__aaaManagementRead(path); }',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',compiled.outputFiles[0].text)(name=>name==='react'?hooks:require(name),module,module.exports);
function fixture(key){return {mode:'SYNTHETIC_FIXTURE_ONLY',scenario:key,account_id:'demo-sub-aaa-memory',history_persistence:'DISPOSABLE_MEMORY',request_id:'request-technical-only',correlation_id:'correlation-technical-only',fingerprint:'hash-technical-only',result:{label:'Sentetik örnek',outcome:key==='PLAN'?'PASS':'BLOCKED',live_ready:false,external_writes:false,simulated_final_authority:key==='COMPENSATION'?'LOCAL':'RADIUS',simulated_final_revision:key==='COMPENSATION'?5:4,blockers:key==='PLAN'?[]:['MODELED_FAILURE']},events:[{revision:3,state:key==='PLAN'?'MODELED':key==='COMPENSATION'?'COMPENSATED':'RECONCILIATION',at:'2026-11-11T09:00:00Z',correlation_id:'correlation-technical-only',actor_id:'fixture-actor'}]};}
function render({open=false,key='PLAN',resource}={}){
 opened=open;scenario=key;aaaResource=resource??{loading:false,data:fixture(key)};reads=[];
 const before=globalThis.window;globalThis.window={location:{hash:'#module=radius'}};
 try{return renderToStaticMarkup(React.createElement(module.exports.RadiusCenter));}finally{globalThis.window=before;}
}
test('RADIUS center integrates a single optional AAA area and keeps LOCAL RADIUS BELİRSİZ read visibility',()=>{
 const html=render();
 assert.equal((html.match(/aria-label="Merkezi AAA yönetimi"/g)??[]).length,1);
 for(const text of ['Hesap görünürlüğü','Geçiş önizlemesi','LOCAL','RADIUS','BELİRSİZ','Sentetik senaryoları incele','Gerçek AAA işlemleri bağlı değil','seçili depo, arama ve kaynak filtrelerinden bağımsızdır'])assert.ok(html.includes(text),text);
 assert.match(html,/aria-label="Yetkili kaynak: BELİRSİZ"/);
 assert.equal(reads.some(path=>path.startsWith('/aaa-demo/')),false);
 assert.doesNotMatch(html,/<form|type="submit"/);
});
test('new management summaries explain targets risks outcomes and intervention, with identifiers only in closed details',()=>{
 for(const key of ['PLAN','COMPENSATION','RECONCILIATION']){
  const html=render({open:true,key});
  assert.ok(reads.includes('/aaa-demo/preview?scenario='+key));
  const technical=html.match(/<details class="aaa-technical">[\s\S]*?<\/details>/)?.[0];assert.ok(technical);assert.doesNotMatch(technical,/<details[^>]*\bopen\b/);
  for(const value of ['request-technical-only','correlation-technical-only','hash-technical-only']){assert.ok(technical.includes(value));assert.ok(!html.replace(technical,'').includes(value));}
  for(const text of ['Başlangıç durumu','Hedef durum','Son bilinen model durumu','Risk','Gerekli kullanıcı müdahalesi','Gerçek işlem yapılmadı'])assert.ok(html.includes(text),text);
  if(key==='PLAN')assert.match(html,/Örnek geçiş planı oluşturuldu/);
  if(key==='COMPENSATION')assert.match(html,/telafi modellendi; geçiş başarılı sayılmadı/);
  if(key==='RECONCILIATION'){assert.match(html,/model durdu; uzlaştırma gerekiyor/);assert.match(html,/otomatik tekrar yapmayın/);}
 }
});
test('scenario selection uses shared GET loader and preserves explicit loading and error states',()=>{
 render({open:true,resource:{loading:true}});assert.equal(globalThis.__aaaLoader,module.exports.loadAaaDemoPreview);
 const tree=module.exports.AaaDemoScenarios();
 const label=React.Children.toArray(tree.props.children).find(node=>node.type==='label');
 const select=React.Children.toArray(label.props.children).find(node=>node.type==='select');
 select.props.onChange({target:{value:'RECONCILIATION'}});assert.equal(selected,'RECONCILIATION');
 const loading=render({open:true,resource:{loading:true}});assert.match(loading,/Veriler yükleniyor/);assert.doesNotMatch(loading,/Örnek geçiş planı oluşturuldu/);
 const failed=render({open:true,resource:{loading:false,error:'AAA okunamadı'}});assert.match(failed,/role="alert"/);assert.match(failed,/AAA okunamadı/);assert.doesNotMatch(failed,/Örnek geçiş planı oluşturuldu/);
});
