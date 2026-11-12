import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let page=1;
const hooks={...React,useState:initial=>[page,value=>{page=value;}]};
const code=buildSync({entryPoints:['src/components/CompactRouterList.tsx'],bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const {CompactRouterList,savedRouterAge}=module.exports;
const rows=Array.from({length:11},(_,i)=>({id:'demo-router-'+i,name:'Router '+i,status:'Örnekte ONLINE',wan:i?'192.0.2.1':null,measuredAt:null}));
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('eleven saved routers paginate 5/5/1 and navigate by exact identity',()=>{
 const ids=[];let opened;
 for(page=1;page<=3;page++){
  const tree=CompactRouterList({rows,onOpen:id=>opened=id});const entries=nodes(tree).filter(n=>n.type==='li');
  assert.equal(entries.length,page===3?1:5);
  for(const entry of entries){entry.props.children.props.onClick();ids.push(opened);}
 }
 assert.deepEqual(ids,rows.map(row=>row.id));assert.equal(rows.length,11);
});
test('missing WAN/time never borrows management IP or claims live connectivity',()=>{
 page=1;const html=renderToStaticMarkup(CompactRouterList({rows:[rows[0]],onOpen(){}}));
 assert.match(html,/WAN: Veri yok/);assert.match(html,/Ölçüm verisi yok/);assert.match(html,/Örnekte ONLINE/);
 assert.doesNotMatch(html,/192.0.2.1|Canlı ONLINE/);
 const control=renderToStaticMarkup(CompactRouterList({rows:[{...rows[0],measuredAt:null,checkedAt:'2026-11-11T09:00:00Z'}],onOpen(){}}));
 assert.match(control,/Kontrol:/);assert.doesNotMatch(control,/Ölçüm:/);
});
test('measurement age distinguishes fresh, stale, timezone-free and future evidence',()=>{
 const now=Date.parse('2026-11-11T12:00:00Z');
 assert.match(savedRouterAge('2026-11-11T11:59:00Z',now),/1 dk/);
 assert.match(savedRouterAge('2026-11-11T11:00:00Z',now),/Güncel değil/);
 for(const value of [null,'invalid','2026-11-11T12:00:00','2026-11-11T13:00:00Z'])assert.equal(savedRouterAge(value,now),'Güncellik bilinmiyor');
});
test('empty and externally paged lists preserve totals and button bounds',()=>{
 page=1;let tree=CompactRouterList({rows:[],onOpen(){}});assert.match(renderToStaticMarkup(tree),/router kaydı yok/);
 assert.ok(nodes(tree).filter(n=>n.type==='button').every(n=>n.props.disabled));
 let next;tree=CompactRouterList({rows:rows.slice(5,10),total:11,page:2,onPage:p=>next=p,onOpen(){}});
 assert.equal(nodes(tree).filter(n=>n.type==='li').length,5);
 nodes(tree).find(n=>n.props['aria-label']==='Sonraki router sayfası').props.onClick();assert.equal(next,3);
});
