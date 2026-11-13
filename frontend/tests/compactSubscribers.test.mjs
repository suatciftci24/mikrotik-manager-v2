import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
let page=1;
const hooks={...React,useEffect:()=>{},useState:initial=>[typeof initial==='number'?page:initial,value=>{page=value;}]};
const code=buildSync({entryPoints:['src/components/CompactSubscriberList.tsx'],bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
const {CompactSubscriberList,compactPage}=module.exports;
const rows=Array.from({length:11},(_,i)=>({id:'demo-'+i,customer_name:'Abone '+i,plan:'Paket '+i,expires_on:'2026-12-23',status:i%2?'PAUSED':'ACTIVE'}));
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
const props={rows,onOpen(){},selected:()=>false,onSelect(){},canSelect:()=>true};
test('eleven subscribers paginate 5/5/1 without mutating source or losing records',()=>{
 const pages=[1,2,3].map(page=>compactPage(rows,page));
 assert.deepEqual(pages.map(p=>p.length),[5,5,1]);assert.deepEqual(pages.flat(),rows);assert.equal(rows.length,11);
});
test('compact row opens existing detail, selection stays independent, and status is localized',()=>{
 page=1;let opened,selection;
 const tree=CompactSubscriberList({...props,onOpen:id=>opened=id,onSelect:(row,value)=>selection=[row.id,value]});
 const html=renderToStaticMarkup(tree);
 assert.equal(nodes(tree).filter(n=>n.type==='li').length,5);
 assert.match(html,/Aktif/);assert.match(html,/Pasif/);assert.doesNotMatch(html,/ACTIVE|PAUSED/);
 nodes(tree).find(n=>n.props.className==='compact-subscriber-open').props.onClick();assert.equal(opened,rows[0].id);
 nodes(tree).find(n=>n.type==='input').props.onChange({target:{checked:true}});assert.deepEqual(selection,[rows[0].id,true]);
 assert.match(html,/11 sonuç/);assert.match(html,/1\/3/);
});
test('next/previous buttons obey boundaries and a remounted filtered list starts at page one',()=>{
 page=1;let tree=CompactSubscriberList(props);
 const buttons=nodes(tree).filter(n=>n.type==='button'&&n.props['aria-label']?.includes('abone sayfası'));
 assert.equal(buttons[0].props.disabled,true);buttons[1].props.onClick();assert.equal(page,2);
 page=3;tree=CompactSubscriberList(props);assert.equal(nodes(tree).find(n=>n.props['aria-label']==='Sonraki abone sayfası').props.disabled,true);
 // Actual list parent keys include every search/filter so React remounts this state.
 page=1;assert.equal(nodes(CompactSubscriberList({...props,rows:[rows[8]]})).filter(n=>n.type==='li').length,1);
});
test('server-paged persistent list keeps its total, selection policy and page callbacks',()=>{
 let changed;const tree=CompactSubscriberList({...props,rows:rows.slice(5,10),page:2,total:11,onPage:p=>changed=p,canSelect:()=>false});
 assert.equal(nodes(tree).filter(n=>n.type==='li').length,5);
 assert.ok(nodes(tree).filter(n=>n.type==='input').every(n=>n.props.disabled));
 nodes(tree).find(n=>n.props['aria-label']==='Sonraki abone sayfası').props.onClick();assert.equal(changed,3);
});
test('long names remain full text and the empty state disables navigation',()=>{
 page=1;const name='Çok uzun abone adı '.repeat(12);
 assert.ok(renderToStaticMarkup(CompactSubscriberList({...props,rows:[{...rows[0],customer_name:name}]})).includes(name.trim()));
 const tree=CompactSubscriberList({...props,rows:[]});assert.match(renderToStaticMarkup(tree),/eşleşen abone yok/);
 assert.ok(nodes(tree).filter(n=>n.type==='button').every(n=>n.props.disabled));
});

test('mobile subscriber evidence shows authority, router and Turkey-day expiry without inventing a session',()=>{
 page=1;
 const render=row=>renderToStaticMarkup(CompactSubscriberList({...props,today:'2026-12-23',rows:[row]}));
 const html=render({...rows[0],username:'demo.fixture',router_name:'Ofis fixture',source:'RADIUS'});
 for(const value of ['demo.fixture','Ofis fixture','RADIUS','Bugün bitiyor (0 gün)','Oturum: Bilinmiyor'])assert.ok(html.includes(value),value);
 const unknown=render({...rows[0],expires_on:null,source:null});
 assert.match(unknown,/Kaynak: Bilinmiyor/);assert.match(unknown,/Bitiş tarihi bilinmiyor/);assert.doesNotMatch(unknown,/Çevrimiçi|Online/);
});
