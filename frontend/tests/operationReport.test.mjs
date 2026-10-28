import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {operationFilter,operationHash,operationQuery,operationDetailHash,detailOperationHash} from '../src/lib/operationReport.ts';
const require=createRequire(import.meta.url);
const code=(await build({entryPoints:[fileURLToPath(new URL('../src/screens/OperationReport.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'resource',setup(build){build.onResolve({filter:/lib\/useResource$/},()=>({path:'resource',namespace:'test'}));build.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){globalThis.__reportPath=path;return globalThis.__operationReportResource}',loader:'js'}));}}]})).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(require,module,module.exports);
const {OperationReport}=module.exports;
const time='2026-10-28T10:00:00Z';
const data={items:[],routers:[{id:'r & 1',name:'Demo Router'}],total:0,page:1,page_size:25,read_at:time,is_demo:true,read_only:true,connections_available:false,summary:{router_status:{ONLINE:1},subscribers:1,active:1,paused:0,operations:0,activated:0,deactivated:0,open_events:0,connections:null}};
function render(resource,hash=''){const old=globalThis.window;globalThis.window={location:{hash}};globalThis.__operationReportResource=resource;try{return renderToStaticMarkup(createElement(OperationReport));}finally{globalThis.window=old;delete globalThis.__operationReportResource;}}
test('report URL keeps range, router, category and page without loading subscriber detail inventory',()=>{
 const filter={...operationFilter('',new Date(time)),router_id:'r & 1',category:'MIKA',priority:'P2',page:3};
 assert.deepEqual(operationFilter(operationHash(filter)),filter);
 assert.equal(new URLSearchParams(operationQuery(filter)).get('router_id'),'r & 1');
 render({data,loading:false,retry(){}},operationHash(filter));
 assert.match(globalThis.__reportPath,/^\/reports\/operations\?/);assert.match(globalThis.__reportPath,/page=3/);
});
test('read-only report distinguishes loading, failed source, empty and missing connection evidence',()=>{
 assert.match(render({loading:true,retry(){}}),/Veriler yükleniyor/);
 assert.match(render({loading:false,error:'Yetki yok',retry(){}}),/role="alert"/);
 const html=render({data,loading:false,retry(){}});
 assert.match(html,/Seçili filtrelerde kayıt yok/);assert.match(html,/başarısız denemeler kalıcı audit kaynağında tutulmuyor/);
 assert.match(render({data,loading:false,retry(){}},'#category=CONNECTION'),/bağlantı olay kaynağı bulunmuyor/);
});
test('audit report preserves old/new values, result and exact detail destinations',()=>{
 const event={id:'event-1',subscriber_id:'s & 1',customer_name:'Test Abone',router_id:'r & 1',router_name:'Demo Router',operation:'STATUS_CHANGE',occurred_at:time,previous_values:{status:'ACTIVE'},new_values:{status:'PAUSED'},is_demo:true};
 const html=render({data:{...data,items:[event],total:26},loading:false,retry(){}});
 assert.match(html,/module=subscribers&amp;id=s\+%26\+1/);assert.match(html,/module=routers&amp;id=r\+%26\+1/);
 assert.match(html,/Etkin/);assert.match(html,/duraklatıldı/);assert.match(html,/Kaydedildi/);assert.match(html,/Sonraki sayfa/);
});
test('MikAjani report includes priority, domain, all routers and resolved timestamp',()=>{
 const event={id:'mika1',priority:'P2',domain:'WAN',title:'Sentetik WAN',affected_router_ids:['r & 1'],opened_at:time,updated_at:time,resolved_at:time,state:'RESOLVED'};
 const html=render({data:{...data,items:[event],total:1},loading:false,retry(){}},'#category=MIKA');
 assert.match(html,/P2 · WAN/);assert.match(html,/Çözüldü/);assert.match(html,/Çözülme:/);assert.match(html,/module=routers&amp;id=r\+%26\+1/);
});

test('report to detail round trip preserves date range and exact router/subscriber scopes',()=>{
 const filter={...operationFilter(''),start:'2026-10-01',end:'2026-10-28',router_id:'r & 1'};
 const detail=operationDetailHash('subscribers','s & 1',filter);
 const result=operationFilter(detailOperationHash('subscribers','s & 1',detail));
 assert.equal(result.start,filter.start);assert.equal(result.end,filter.end);assert.equal(result.router_id,filter.router_id);assert.equal(result.subscriber_id,'s & 1');
});
