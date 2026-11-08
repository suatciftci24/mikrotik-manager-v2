import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {alarmFilter,alarmHash,alarmQuery} from '../src/lib/alarms.ts';
const require=createRequire(import.meta.url);
const {outputFiles}=await build({stdin:{contents:"export {AlarmCenter} from './src/components/AlarmCenter';export {PermissionContext} from './src/lib/permissions';",resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'source',setup(build){build.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));build.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){globalThis.__alarmQueries.push(path);return path==="/preferences"?{loading:false,data:{personal:{theme:null,page_size:null,notifications_enabled:null,notification_levels:null},values:{notification_levels:["P1","P2","P3","P4"]},storage_ready:true},retry(){}}:path.startsWith("/alarms/demo-alarm-")?{data:{item:globalThis.__alarmItem,can_ack:globalThis.__alarmResource.data?.detail_can_ack??globalThis.__alarmResource.data?.can_ack},loading:false,retry(){}}:globalThis.__alarmResource}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',outputFiles[0].text)(require,module,module.exports);
const {AlarmCenter}=module.exports;
const alarm={id:'demo-alarm-test',occurrence_id:'demo-source',router_id:'r & 1',subscriber_id:'s & 1',kind:'WAN_DOWN',severity:'P2',title:'Kaydedilmiş WAN',state:'OPEN',source_state:'OPEN',source_available:true,first_seen:null,last_seen:null,repeat_count:1,evidence:'Sentetik kanıt',source:'router-events',source_id:'demo-source',acknowledgement:null,notification_read:false,action_history:[]};
const data={items:[alarm],total:1,page:1,page_size:25,is_demo:true,routers:[{id:'r & 1',name:'Demo Router'}],summary:{active:1,critical:1,unread:1},generated_at:'2026-10-28T09:00:00Z',coverage:{connection_available:false,ipsec_available:false,note:'Kaynak kapsamı'},storage_ready:true,can_ack:true};
function render(resource,props={},hash='',identity=null){
 const previous=globalThis.window;globalThis.window={location:{hash}};globalThis.__alarmResource=resource;globalThis.__alarmItem=alarm;globalThis.__alarmQueries=[];
 try{return renderToStaticMarkup(createElement(module.exports.PermissionContext.Provider,{value:identity},createElement(AlarmCenter,props)));}finally{globalThis.window=previous;}
}
test('alarm filters round trip without overwriting legacy internet event filters',()=>{
 const filter={...alarmFilter(''),router_id:'r & 1',severity:'P2',state:'ACKNOWLEDGED',kind:'WAN_DOWN',start:'2026-10-01',end:'2026-10-28',page:3};
 assert.deepEqual(alarmFilter(alarmHash(filter)),filter);
 assert.equal(new URLSearchParams(alarmQuery(filter)).get('router_id'),'r & 1');
 assert.equal(alarmFilter('#kind=INTERNET_DOWN&status=OPEN').kind,'ALL');
});
test('center distinguishes unavailable source, missing timestamps and separate read and ACK states',()=>{
 const html=render({data,loading:false,retry(){}});
 assert.match(html,/internet\/WAN olay kaynağı bağlı değil/);assert.match(html,/IPsec gözlemi: Veri yok/);
 assert.match(html,/Açık · Okunmadı/);assert.match(html,/Veri yok \/ Veri yok/);
 assert.match(html,/Alarm router filtresi/);assert.match(html,/Alarm tür filtresi/);assert.match(html,/Sonraki alarm sayfası/);
});
test('loading, failed source and empty supported inventory stay distinct',()=>{
 assert.match(render({loading:true,retry(){}}),/Veriler yükleniyor/);
 assert.match(render({loading:false,error:'Yetki gerekli',retry(){}}),/role="alert"/);
 assert.match(render({data:{...data,items:[],total:0},loading:false,retry(){}}),/Bu kapsamda kaynak alarmı yok/);
});
test('ACK controls use server permission; detail links retain exact record IDs',()=>{
 const hash=alarmHash(alarmFilter(''),alarm.id);
 const readonly=render({data:{...data,can_ack:false},loading:false,retry(){}},{},hash);
 assert.doesNotMatch(readonly,/>Alarmı onayla<\/button>/);
 const restricted=render({data:{...data,detail_can_ack:false},loading:false,retry(){}},{},hash);
 assert.doesNotMatch(restricted,/>Alarmı onayla<\/button>/);
 const admin=render({data,loading:false,retry(){}},{},hash);
 assert.match(admin,/>Alarmı onayla<\/button>/);assert.match(admin,/Bildirimi okundu işaretle/);
 assert.match(admin,/module=routers&amp;id=r\+%26\+1/);assert.match(admin,/module=subscribers&amp;id=s\+%26\+1/);
 assert.match(admin,/Operasyon raporu için yetkiniz yok/);assert.match(admin,/MikAjanı için yetkiniz yok/);assert.match(admin,/ACK yalnız operatör onayıdır/);
});
test('notification and dashboard summaries use latest global scope without inheriting page filters',()=>{
 render({data,loading:false,retry(){}},{notifications:true},'#alarm_router=foreign&alarm_state=ACKNOWLEDGED');
 const params=new URLSearchParams(globalThis.__alarmQueries[0].split('?')[1]);
 assert.equal(params.get('router_id'),'');assert.equal(params.get('state'),'ALL');assert.equal(params.get('order'),'LATEST');assert.equal(params.get('page_size'),'5');
 render({data,loading:false,retry(){}},{compact:true});
 assert.equal(new URLSearchParams(globalThis.__alarmQueries[0].split('?')[1]).get('state'),'ACTIVE');
});

test('authorized alarm targets preserve source, IDs and report category without inventing timestamps',()=>{
 const user={permissions:{[alarm.router_id]:{can_view:true,can_use_mikajani:true,can_view_reports:true}}};
 const html=render({data,loading:false,retry(){}},{},alarmHash(alarmFilter(''),alarm.id),user);
 assert.match(html,/source=DEMO/);assert.match(html,/workspace=LEGACY/);
 assert.match(html,/module=mikajani/);assert.match(html,/category=CONNECTION/);assert.match(html,/router_id=r\+%26\+1/);
 assert.doesNotMatch(html,/start=|event=undefined|id=undefined/);
 for(const module of ['routers','subscribers']){const href=[...html.matchAll(/href="([^"]+)"/g)].map(match=>match[1].replaceAll('&amp;','&')).find(value=>value.startsWith('#module='+module));assert.equal(new URLSearchParams(href.slice(1)).get('return_to'),alarmHash(alarmFilter(''),alarm.id));}
});
