import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {linkedDetailHash,detailReturnHash} from '../src/lib/detailLinks.ts';
import {validRouterSubscribers} from '../src/lib/routerSubscribersCenter.ts';
import {subscriberRouterHash,safeSubscriberCenter} from '../src/lib/subscriberCenter.ts';
const router='demo-managed-router-fixture';
const account={id:'demo-managed-sub-fixture',customer_name:'Test Abone',username:'test.ev',router_id:router,router_name:'TEST-EV-V2',router_model:'Test model',router_source:'PERSISTENT_DEMO',router_missing:false,access_type:'PPPOE',source:'LOCAL',plan:'Demo 100',status:'ACTIVE',expires_on:'2026-10-01',session_status:'UNKNOWN',revision:1,last_seen_at:null,last_connected_at:null,ip_address:null};
const listing={items:[account],total:1,is_demo:true,source:'PERSISTENT_WORKSPACE',availability:'AVAILABLE',page:1,page_size:25};
test('cross-center links carry bounded return context including router tab/search/page; external targets fail',()=>{
 const from='#module=routers&source=MANAGED_DEMO&id='+router+'&router_tab=pppoe&router_sub_query=test&router_sub_status=ACTIVE&router_sub_page=2';
 const link=linkedDetailHash({module:'subscribers',id:account.id,workspace:'PERSISTENT'},from);const params=new URLSearchParams(link.slice(1));assert.equal(params.get('id'),account.id);assert.equal(params.get('return_to'),from);
 const back=subscriberRouterHash(account,link);const returnContext=new URLSearchParams(back.slice(1)).get('return_to');assert.equal(new URLSearchParams(returnContext.slice(1)).has('return_to'),false);
 assert.equal(detailReturnHash('https://example.com/'),null);assert.equal(detailReturnHash('#module=system&id=x'),null);
});
test('cross-router/type/live source rows fail closed; real count remains unknown',()=>{
 assert.equal(validRouterSubscribers(listing,router,'PPPOE'),true);
 for(const change of [{items:[{...account,router_id:'other'}]},{items:[{...account,access_type:'HOTSPOT'}]},{source:'REGISTERED'},{items:[{...account,session_status:'ONLINE'}]}])assert.equal(validRouterSubscribers({...listing,...change},router,'PPPOE'),false);
 assert.equal(validRouterSubscribers({...listing,items:[],source:'REGISTERED',availability:'PREPARING',is_demo:false,total:null},'registered-fixture','PPPOE'),true);
 const missing={...account,router_missing:true,router_source:'UNKNOWN',router_name:null,router_model:null};assert.equal(subscriberRouterHash(missing),null);
 assert.equal(safeSubscriberCenter({item:missing,is_demo:true,device_connection_started:false,source:'PERSISTENT_WORKSPACE',persistence:'local-postgresql-workspace'},missing.id),true);
});
test('router list renders names, package, expiry, independent account state and safe detail link',()=>{
 const require=createRequire(import.meta.url),hooks={...React,useEffect:()=>{},useRef:value=>({current:value}),useCallback:fn=>fn,useState:initial=>{const value=typeof initial==='function'?initial():initial;return value?.path?[{...value,loading:false,data:listing},()=>{}]:[value,()=>{}];}};
 const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/RouterSubscribers.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 const html=renderToStaticMarkup(module.exports.RouterSubscribers({id:router,access:'PPPOE'}));assert.match(html,/Test Abone/);assert.match(html,/test.ev/);assert.match(html,/Demo 100/);assert.match(html,/Hesap: Aktif/);assert.match(html,/Süresi dolmuş/);assert.match(html,/1 eşleşen PPPoE/);assert.match(html,/module=subscribers/);assert.doesNotMatch(html,/Çevrimiçi/);
});

test('detail Back restores the bounded cross-center hash instead of losing tab/filter state',()=>{
 const require=createRequire(import.meta.url),hooks={...React,useEffect:()=>{},useRef:value=>({current:value}),useState:initial=>[typeof initial==='function'?initial():initial,()=>{}]};
 const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/lib/useDetailNavigation.ts',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',external:['react']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 const back='#module=routers&id='+router+'&router_tab=hotspot&router_sub_query=test&router_sub_page=2';let replaced=null,dispatched=0;
 const previousWindow=globalThis.window,previousHashEvent=globalThis.HashChangeEvent;
 globalThis.HashChangeEvent=class {constructor(type){this.type=type;}};
 globalThis.window={location:{hash:linkedDetailHash({module:'subscribers',id:account.id,workspace:'PERSISTENT'},back),pathname:'/',search:''},history:{replaceState:(_s,_t,url)=>{replaced=url;}},dispatchEvent:()=>{dispatched++;}};
 try{module.exports.useDetailNavigation('subscribers').back();assert.equal(replaced,'/'+back);assert.equal(dispatched,1);}finally{globalThis.window=previousWindow;globalThis.HashChangeEvent=previousHashEvent;}
});
