import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {dailyEntries} from '../src/lib/subscriberManagementCenter.ts';
const item={id:'demo-managed-sub-fixture',username:'one.test',customer_name:'One User',router_id:'demo-managed-router-fixture',router_name:'One Router',router_source:'PERSISTENT_DEMO',access_type:'PPPOE',source:'LOCAL',status:'PAUSED',plan:'Demo 100',expires_on:'2026-11-01',revision:1,router_missing:false,session_status:'UNKNOWN'};
const rows=[item,{...item,id:'demo-managed-sub-other',router_id:'demo-managed-router-other',router_name:'Other Router',username:'two.test',access_type:'HOTSPOT'}];
const nodes=e=>e&&typeof e==='object'?[e,...React.Children.toArray(e.props?.children).flatMap(nodes)]:[];
test('shared preview supports 30/60/90, cross-router batches and rejects live/read-only records',()=>{
 for(const days of [30,60,90]){const entries=dailyEntries(rows,'EXTEND','',days,'2026-10-29',()=>crypto.randomUUID());assert.equal(entries.length,2);assert.equal(entries[1].expected_router_id,rows[1].router_id);assert.equal(entries[0].days,days);assert.equal(entries[0].confirmed,true);}
 for(const change of [{id:'registered-test'},{router_source:'UNKNOWN'},{router_missing:true},{source:null}])assert.throws(()=>dailyEntries([{...item,...change}],'STATUS','ACTIVE',30,'2026-10-29',()=>''));
 assert.throws(()=>dailyEntries(rows,'PLAN','New Plan',30,'2026-10-29',()=>''));
 assert.throws(()=>dailyEntries([{...item,expires_on:null}],'EXTEND','',30,'2026-10-29',()=>''));
});
test('preview rejects unsupported authority, router, revision, dates and unchanged single-record edits before creating commands',()=>{
 let ids=0;const id=()=>{ids++;return 'synthetic-request';};
 for(const change of [{source:'UNKNOWN'},{source:'other'},{router_id:'registered-router'},
  {access_type:'UNKNOWN'},{revision:0},{revision:-1},{revision:1.5},{revision:undefined}]){
  assert.throws(()=>dailyEntries([{...item,...change}],'STATUS','ACTIVE',30,'2026-10-29',id));
 }
 assert.equal(ids,0);
 for(const [action,value,days] of [['EXTEND','',0],['EXTEND','',366],['EXTEND','',1.5],['PLAN',item.plan,30],['STATUS','UNKNOWN',30],
  ['EDIT',item.customer_name,30],['ROUTER',item.router_id,30],['EXPIRE',item.expires_on,30],
  ['EXPIRE','2026-02-30',30],['EDIT','\u0000bad',30],['DELETE','',30]]){
  assert.throws(()=>dailyEntries([item],action,value,days,'2026-10-29',id));
 }
 assert.equal(ids,0);
 for(const authority of ['LOCAL','RADIUS']){
  const command=dailyEntries([{...item,source:authority}],'PLAN','Demo 800',30,'2026-10-29',id)[0];
  assert.equal(command.expected_source,authority);assert.equal(command.expected_revision,item.revision);
  assert.equal(command.expected_router_id,item.router_id);assert.equal(command.value,'Demo 800');
 }
 // The server still receives every account, including expected skips.
 assert.equal(dailyEntries(rows,'STATUS','PAUSED',30,'2026-10-29',id).length,2);
});
function dailyDialog(props){
 const require=createRequire(import.meta.url),slots=[];let cursor=0;const calls=[];
 const hooks={...React,useContext:()=>({role_code:'ADMIN',can_manage_users:true}),useEffect:()=>{},useCallback:fn=>fn,useRef:value=>{const i=cursor++;slots[i]??={current:value};return slots[i];},useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;const value=slots[i];if(value?.path)return [{...value,loading:false,data:{items:[]}},()=>{}];return [value,next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];}};
 const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/components/SubscriberDailyActions.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 return ()=>{cursor=0;return module.exports.SubscriberDailyActions(props);};
}
test('bulk preview requires explicit consent and does not resend resolved mixed-result requests',async()=>{
 const calls=[];
 const previousFetch=globalThis.fetch,previousWindow=globalThis.window;globalThis.window={dispatchEvent:()=>{}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});const entries=JSON.parse(init.body).entries;return {ok:true,json:async()=>({results:entries.map((e,i)=>({item_id:e.item_id,request_id:e.request_id,operation:e.operation,actor_id:'synthetic.actor',router_id:e.expected_router_id,previous_router_id:e.expected_router_id,revision:2,previous:{},success:i===0,recorded:true,values:{expires_on:e.value},occurred_at:'2026-10-29T12:00:00Z',error:i?'Revizyon değişti':null}))})};};
 const pppoeRows=[item,{...rows[1],access_type:'PPPOE',source:'RADIUS',expires_on:'9998-01-01'}];
 const render=dailyDialog({rows:pppoeRows,onClose:()=>{}});
 try{
  let tree=render();assert.match(renderToStaticMarkup(tree),/2 seçili abone/);
  nodes(tree).find(n=>n.type==='select'&&n.props.value==='30').props.onChange({target:{value:'CUSTOM'}});
  tree=render();nodes(tree).find(n=>n.type==='input'&&n.props.type==='number').props.onChange({target:{value:'17'}});
  tree=render();nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault:()=>{}});tree=render();assert.equal(calls.length,0);
  assert.match(renderToStaticMarkup(tree),/17 gün/);
  assert.match(renderToStaticMarkup(tree),/1 Oca 9998 → 18 Oca 9998/);
  let button=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula');assert.equal(button.props.disabled,true);
  nodes(tree).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});tree=render();nodes(tree).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();await new Promise(setImmediate);tree=render();
  assert.match(renderToStaticMarkup(tree),/Başarılı: 1/);assert.match(renderToStaticMarkup(tree),/Başarısız: 1/);assert.match(renderToStaticMarkup(tree),/Revizyon değişti/);
  const resolved=nodes(tree).find(n=>n.type==='button'&&n.props.children==='Aynı UUID ile sonuçları sorgula');assert.equal(resolved,undefined);await new Promise(setImmediate);assert.equal(calls.length,1);assert.match(calls[0].url,/management\/execute$/);
  assert.deepEqual(JSON.parse(calls[0].init.body).entries.map(({days,expected_source})=>[days,expected_source]),[[17,'LOCAL'],[17,'RADIUS']]);
 }finally{globalThis.fetch=previousFetch;globalThis.window=previousWindow;}
});

for(const target of ['ACTIVE','PAUSED']){
 test(`bulk ${target} previews every PPPoE account and confirms the server outcome for every account`,async t=>{
  const opposite=target==='ACTIVE'?'PAUSED':'ACTIVE';
  const selected=[
   {...item,status:opposite},
   {...item,id:'demo-managed-sub-failure',customer_name:'Conflict User',source:'RADIUS',status:opposite},
   {...item,id:'demo-managed-sub-skip',customer_name:'Skipped User',status:target},
  ];
  const render=dailyDialog({rows:selected,initialAction:'STATUS',onClose(){}});
  const originalWindow=globalThis.window;
  globalThis.window={dispatchEvent(){}};
  t.after(()=>{globalThis.window=originalWindow;});
  const fetch=t.mock.method(globalThis,'fetch',async (_url,init)=>{
   const {entries}=JSON.parse(init.body);
   return {ok:true,json:async()=>({results:entries.map((entry,index)=>({
    item_id:entry.item_id,request_id:entry.request_id,operation:'STATUS',
    actor_id:'actor',router_id:entry.expected_router_id,previous_router_id:entry.expected_router_id,
    source:entry.expected_source,revision:index===2?1:2,previous:{status:index===2?target:opposite},values:{status:target},
    recorded:index!==2,skipped:index===2,success:index===0,
    occurred_at:'2026-11-18T12:00:00Z',error:index===1?'Revizyon değişti':null,
   }))})};
  });
  nodes(render()).find(n=>n.type==='select'&&n.props.value==='').props.onChange({target:{value:target}});
  nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
  const preview=renderToStaticMarkup(render());
  assert.match(preview,target==='ACTIVE'?/Pasif hesap → Aktif hesap/:/Aktif hesap → Pasif hesap/);
  assert.match(preview,/Değişiklik beklenen: <strong>2<\/strong> · Atlanması beklenen: <strong>1/);
  assert.match(preview,/Skipped User[\s\S]*Atlanması bekleniyor[\s\S]*Önizlemede zaten hedef durumda/);
  selected[0]={...selected[0],customer_name:'Refreshed name',status:target,revision:99};
  assert.doesNotMatch(renderToStaticMarkup(render()),/Refreshed name/);
  const apply=()=>nodes(render()).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula');
  assert.equal(apply().props.disabled,true);
  apply().props.onClick();
  assert.equal(fetch.mock.callCount(),0);
  nodes(render()).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
  apply().props.onClick();
  await new Promise(setImmediate);
  assert.equal(fetch.mock.callCount(),1);
  const {entries}=JSON.parse(fetch.mock.calls[0].arguments[1].body);
  assert.deepEqual(entries.map(e=>[e.item_id,e.expected_source,e.value,e.expected_expires_on,e.expected_status]),selected.map((row,index)=>[row.id,row.source,target,row.expires_on,index===0?opposite:row.status]));
  const result=renderToStaticMarkup(render());
  assert.match(result,/Başarılı: 1/);
  assert.match(result,/Başarısız: 1/);
  assert.match(result,/Atlandı: 1/);
  assert.match(result,/Skipped User.*Atlandı · Hesap zaten hedef durumda/s);
 });
}
test('an all-unchanged status batch settles without a recovery query',async t=>{
 const originalWindow=globalThis.window;
 globalThis.window={dispatchEvent(){}};
 t.after(()=>{globalThis.window=originalWindow;});
 const fetch=t.mock.method(globalThis,'fetch',async (_url,init)=>{
  const {entries}=JSON.parse(init.body);
  return {ok:true,json:async()=>({results:entries.map(entry=>({
   item_id:entry.item_id,request_id:entry.request_id,operation:'STATUS',actor_id:'actor',
   router_id:entry.expected_router_id,previous_router_id:entry.expected_router_id,source:entry.expected_source,
   revision:entry.expected_revision,previous:{status:entry.value},values:{status:entry.value},
   recorded:false,skipped:true,success:false,occurred_at:'2026-11-18T12:00:00Z',error:null,
  }))})};
 });
 const render=dailyDialog({rows:[item,{...item,id:'demo-managed-sub-same'}],initialAction:'STATUS',onClose(){}});
 nodes(render()).find(n=>n.type==='select'&&n.props.value==='').props.onChange({target:{value:'PAUSED'}});
 nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
 assert.match(renderToStaticMarkup(render()),/Değişiklik beklenen: <strong>0<\/strong> · Atlanması beklenen: <strong>2/);
 assert.equal(fetch.mock.callCount(),0);
 nodes(render()).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
 nodes(render()).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();
 await new Promise(setImmediate);
 assert.match(renderToStaticMarkup(render()),/Başarılı: 0.*Atlandı: 2.*Başarısız: 0/s);
 assert.doesNotMatch(renderToStaticMarkup(render()),/Aynı UUID ile sonuçları sorgula/);
 assert.equal(fetch.mock.callCount(),1);
});

test('a duplicate UUID conflict directs the operator to history and leaves the approval closed',async t=>{
 const originalWindow=globalThis.window;
 globalThis.window={dispatchEvent(){}};
 t.after(()=>{globalThis.window=originalWindow;});
 const fetch=t.mock.method(globalThis,'fetch',async ()=>({
  ok:false,status:409,json:async()=>({detail:'İstek kimliği başka bir işlem grubuna ait.'}),
 }));
 const render=dailyDialog({rows:[item],fixedAction:'STATUS',onClose(){}});
 nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
 nodes(render()).find(n=>n.type==='input'&&n.props.type==='checkbox').props.onChange({target:{checked:true}});
 nodes(render()).find(n=>n.type==='button'&&n.props.children==='Onayla ve uygula').props.onClick();
 await new Promise(setImmediate);
 const html=renderToStaticMarkup(render());
 assert.match(html,/İşlem geçmişini kontrol edin/);
 assert.doesNotMatch(html,/Onayla ve uygula|Aynı UUID ile sonuçları sorgula/);
 assert.equal(fetch.mock.callCount(),1);
});
