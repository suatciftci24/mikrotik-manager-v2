import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {managementFilterFromHash,managementReportHash} from '../src/lib/managementReport.ts';
const require=createRequire(import.meta.url);
let page=1;
const hooks={...React,useState:()=>[page,next=>{page=next;}]};
const code=buildSync({entryPoints:['src/components/CompactOperationList.tsx'],bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const {CompactOperationList,operationSearch,compactOperationTime}=module.exports;
const rows=Array.from({length:11},(_,i)=>({id:'audit-'+i,title:'Paket değişikliği',subject:'Abone '+i,when:'11 Kas 15:00',result:i%2?'Başarısız':'Başarılı',searchText:i%2?'RADIUS HOTSPOT actor-b':'LOCAL PPPOE actor-a'}));
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const props={rows,label:'Son işlemler',onOpen(){}};
test('eleven operations show 5/5/1 and every arrow opens its original audit ID',()=>{
 const visited=[];
 for(page=1;page<=3;page++){
  const tree=CompactOperationList({...props,onOpen:id=>visited.push(id)});
  const records=nodes(tree).filter(n=>n.type==='li');assert.equal(records.length,page===3?1:5);
  for(const record of records)record.props.children.props.onClick();
 }
 assert.deepEqual(visited,rows.map(row=>row.id));assert.equal(rows.length,11);
});
test('search intersects terms without guessing authority or dropping failed records',()=>{
 assert.equal(operationSearch(rows,'radius hotspot actor-b').length,5);
 assert.equal(operationSearch(rows,'LOCAL HOTSPOT').length,0);
 assert.equal(operationSearch(rows,'Paket Abone 10')[0].id,'audit-10');
 assert.equal(operationSearch(rows,'Başarısız').length,5);
});
test('zero available records stays empty while partial scope remains explicitly incomplete',()=>{
 page=1;
 const empty=renderToStaticMarkup(CompactOperationList({...props,rows:[]}));
 assert.match(empty,/0 kayıt/);assert.match(empty,/Bu kapsamda kayıt yok/);assert.doesNotMatch(empty,/kapsam eksik/);
 const partial=renderToStaticMarkup(CompactOperationList({...props,rows:[],partial:true}));
 assert.match(partial,/kapsam eksik/);assert.match(partial,/erişilen kayıt/);
});
test('paging is bounded and a changed keyed filter begins with its first five records',()=>{
 page=1;let tree=CompactOperationList(props);
 assert.equal(nodes(tree).find(n=>n.props['aria-label']==='Son işlemler önceki sayfa').props.disabled,true);
 nodes(tree).find(n=>n.props['aria-label']==='Son işlemler sonraki sayfa').props.onClick();assert.equal(page,2);
 page=3;tree=CompactOperationList(props);
 assert.equal(nodes(tree).find(n=>n.props['aria-label']==='Son işlemler sonraki sayfa').props.disabled,true);
 page=1;tree=CompactOperationList({...props,query:'RADIUS'});assert.equal(nodes(tree).filter(n=>n.type==='li').length,5);
});
test('mobile timestamps are Turkey time and invalid or timezone-free evidence is not invented',()=>{
 assert.match(compactOperationTime('2026-11-11T12:00:00Z'),/15:00/);
 for(const value of [null,'invalid','2026-11-11T12:00:00'])assert.equal(compactOperationTime(value),'Zaman yok');
});
test('reloadable operation filter retains search plus source/router/type context',()=>{
 const filter={query:'Abone RADIUS',period:'LAST_24',router:'demo-router-001',kind:'PPPOE',source:'RADIUS'};
 assert.deepEqual(managementFilterFromHash(managementReportHash(filter,'operations')),filter);
 assert.equal(managementFilterFromHash('#module=operations&query='+('a'.repeat(200))).query.length,120);
});
