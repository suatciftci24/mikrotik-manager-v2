import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {packageEnd,loadPackageChoices} from '../src/lib/packages.ts';
import {dailyEntries} from '../src/lib/subscriberManagementCenter.ts';

const require=createRequire(import.meta.url);
const recovery={exports:{}};new Function('require','module','exports',buildSync({entryPoints:[fileURLToPath(new URL('../src/lib/subscriberOperationRecovery.ts',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text)(require,recovery,recovery.exports);
const {operationReceiptMatches}=recovery.exports;
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/screens/PackageManagement.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes),...nodes(e.props?.actions)]:[];
function harness(identity){
 const slots=[];let cursor=0;
 const react={...React,useContext:()=>identity,useEffect(){},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];return [value?.path?{...value,loading:false,data:{items:[],total:0}}:value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const mod={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?react:require(name),mod,mod.exports);
 return ()=>{cursor=0;const root=mod.exports.PackageManagement();return typeof root.type==='function'?root.type(root.props):root;};
}
test('ADMIN catalog is discoverable, empty, and distinguishes business package from profile label',()=>{
 for(const identity of [null,{role_code:'OPERATOR'},{role_code:'VIEWER'},{role_code:'ADMIN',can_manage_users:false}])assert.match(renderToStaticMarkup(harness(identity)()),/ADMIN yetkisi/);
 const html=renderToStaticMarkup(harness({role_code:'ADMIN',can_manage_users:true})());assert.match(html,/Paket oluştur/);assert.match(html,/Henüz kayıtlı paket yok/);assert.match(html,/MikroTik profil adı yalnız eşleme etiketidir/);
});
test('package creation previews fields and repeats identical UUID after lost response',async()=>{
 const render=harness({role_code:'ADMIN',can_manage_users:true});const button=(tree,text)=>nodes(tree).find(n=>n.type==='button'&&n.props.children===text);
 button(render(),'Paket oluştur').props.onClick();nodes(render()).find(n=>n.type==='input'&&n.props.maxLength===120).props.onChange({target:{value:'Business 100'}});
 nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
 const calls=[],oldFetch=globalThis.fetch,oldWindow=globalThis.window;globalThis.window={dispatchEvent(){}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});if(calls.length===1)throw Error('lost response');return {ok:true,json:async()=>({id:'demo-package-fixture',revision:1,fields:JSON.parse(init.body).fields,is_demo:true})};};
 try{
  button(render(),'Onayla ve kaydet').props.onClick();await new Promise(resolve=>setImmediate(resolve));assert.match(renderToStaticMarkup(render()),/Sonuç belirsiz/);assert.equal(button(render(),'Düzenlemeye dön').props.disabled,true);
  button(render(),'Onayla ve kaydet').props.onClick();await new Promise(resolve=>setImmediate(resolve));assert.equal(calls.length,2);assert.equal(calls[0].init.body,calls[1].init.body);assert.equal(calls[0].url,'/api/v1/packages');assert.equal(calls[0].init.headers['X-V2-Demo-Action'],'package-workspace');
  const payload=JSON.parse(calls[0].init.body);assert.equal(payload.fields.name,'Business 100');assert.equal(payload.fields.duration_days,30);assert.equal(payload.confirmed,true);
 }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
});
test('inclusive duration, invalid/overflow dates and complete package pagination',async()=>{
 assert.equal(packageEnd('2030-01-01',30),'2030-01-30');assert.equal(packageEnd('2030-01-01',1),'2030-01-01');assert.equal(packageEnd('2030-02-31',30),'');assert.equal(packageEnd('9999-12-31',30),'');assert.equal(packageEnd('2030-01-01',0),'');
 const original=globalThis.fetch;globalThis.fetch=async url=>({ok:true,json:async()=>({items:String(url).includes('page=1&')?Array.from({length:100},(_,i)=>({id:'p'+i})):[{id:'p100'}],total:101})});
 try{assert.equal((await loadPackageChoices('')).items.length,101);}finally{globalThis.fetch=original;}
});
test('same-name version upgrade is actionable and receipt must match package ID/revision',()=>{
 const item={id:'demo-managed-sub-fixture',router_id:'demo-managed-router-fixture',router_source:'PERSISTENT_DEMO',can_manage:true,source:'LOCAL',access_type:'PPPOE',revision:2,plan:'Business 100',package_id:'demo-package-one',package_revision:1,expires_on:'2030-01-01'};
 const entry=dailyEntries([item],'PLAN','Business 100',30,'2026-11-14',()=>crypto.randomUUID(),{package_id:item.package_id,package_revision:2})[0];assert.equal(entry.package_revision,2);
 const receipt={...entry,recorded:true,success:true,actor_id:'fixture',revision:3,previous_router_id:item.router_id,router_id:item.router_id,error:null,occurred_at:'2026-11-14T00:00:00Z',previous:{},values:{plan:entry.value,package_id:entry.package_id,package_revision:'2'}};
 assert.equal(operationReceiptMatches(entry,receipt),true);assert.equal(operationReceiptMatches(entry,{...receipt,values:{...receipt.values,package_revision:'1'}}),false);
});
