import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
async function compile(path){
 const result=await build({entryPoints:[fileURLToPath(new URL(path,import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'usage-resource',setup(builder){
  builder.onResolve({filter:/lib\/useResource$/},()=>({path:'usage-resource',namespace:'test'}));
  builder.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return globalThis.__usageResource}',loader:'js'}));
 }}]});const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(require,module,module.exports);return module.exports;
}
const {InternetReport}=await compile('../src/screens/InternetReport.tsx');
const {VolumeTrend}=await compile('../src/components/VolumeTrend.tsx');
const {Sidebar}=await compile('../src/components/Sidebar.tsx');
const {Dashboard}=await compile('../src/screens/Dashboard.tsx');
const now=new Date().toISOString();
const item={id:'s & one',router_id:'r & one',router_name:'Sentetik Router',customer_name:'Demo kişi',username:'demo.test',status:'ACTIVE',source:'LOCAL',expires_on:null,is_demo:true,demo_report:{subscriber_id:'s & one',router_id:'r & one',recorded_at:now,is_demo:true,traffic:[{id:'sample',measured_at:now,download_bytes:1_000_000_000,upload_bytes:500_000_000,is_demo:true}],sessions:[]}};
const data={routers:[{id:'r & one',name:'Sentetik Router',status:'ONLINE',is_demo:true}],details:[{item,history:[],is_demo:true}],events:null,read_at:now};
function render(resource){globalThis.__usageResource=resource;try{return renderToStaticMarkup(createElement(InternetReport));}finally{delete globalThis.__usageResource;}}
test('central usage view exposes four periods, named tables and encoded subscriber/router links',()=>{
 const html=render({data,loading:false,retry(){}});
 for(const value of ['Bugün','Dün','Son 7 Gün','Son 30 Gün','PPPoE / demo abone','SENTETİK','GB hacim ile Mbps hız','WAN trafik ölçümü yok'])assert.ok(html.includes(value),value);
 assert.match(html,/href="#module=subscribers&amp;id=s\+%26\+one"/);assert.match(html,/href="#module=routers&amp;id=r\+%26\+one"/);
 assert.match(html,/1,5 GB/);assert.match(html,/aria-label="Abone kullanım raporu tablosu"/);
});
test('missing samples are absent bars, not a fabricated continuous line or measured zero',()=>{
 const html=renderToStaticMarkup(createElement(VolumeTrend,{buckets:[{label:'00:00',download:1000,upload:500,samples:1},{label:'01:00',download:null,upload:null,samples:0},{label:'02:00',download:1000,upload:500,samples:1}]}));
 assert.equal((html.match(/<rect /g)||[]).length,4);assert.doesNotMatch(html,/<path|<polyline/);assert.match(html,/01:00 · İndirme Veri yok/);assert.match(html,/GB hacimdir, Mbps hız değildir/);
 const empty=renderToStaticMarkup(createElement(VolumeTrend,{buckets:[{label:'00:00',download:null,upload:null,samples:0}]}));assert.match(empty,/Veri yok/);assert.doesNotMatch(empty,/<svg/);
});
test('source loading, failure and empty scope remain explicit without success totals',()=>{
 const loading=render({loading:true,retry(){}});assert.match(loading,/Veriler yükleniyor/);assert.doesNotMatch(loading,/Kayıtlı indirme hacmi/);
 const failed=render({loading:false,error:'Sentetik kaynak okunamadı',retry(){}});assert.match(failed,/role="alert"/);assert.doesNotMatch(failed,/Kayıtlı indirme hacmi/);
 const empty=render({data:{routers:[],details:[],events:null},loading:false,retry(){}});assert.match(empty,/Filtrelerle eşleşen router bulunmuyor/);assert.match(empty,/Veri yok/);
});
test('main menu links to the existing Dashboard report view without a new domain module',()=>{
 const html=renderToStaticMarkup(createElement(Sidebar,{active:'dashboard',onNavigate(){},user:{name:'Demo Kullanıcı',role:'Demo'},onLogout(){}}));
 assert.match(html,/href="#module=dashboard&amp;view=INTERNET_REPORT"/);assert.match(html,/İnternet Kullanım ve Bağlantı Raporları/);
});

test('Dashboard report URL opens the central internet screen without another module',()=>{
 const previous=globalThis.window;globalThis.window={location:{hash:'#module=dashboard&view=INTERNET_REPORT'}};globalThis.__usageResource={data,loading:false,retry(){}};
 try{const html=renderToStaticMarkup(createElement(Dashboard,{onNavigate(){}}));assert.match(html,/Merkezi İnternet Kullanım ve Bağlantı Raporları/);assert.match(html,/Abone kullanım özeti/);}
 finally{globalThis.window=previous;delete globalThis.__usageResource;}
});
