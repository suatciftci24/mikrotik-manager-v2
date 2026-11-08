import {test} from 'node:test';
import assert from 'node:assert/strict';
import {buildSync} from 'esbuild';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),React=require('react');
const code=buildSync({entryPoints:[fileURLToPath(new URL('../src/lib/useResource.ts',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',external:['react']}).outputFiles[0].text;
const equal=(a,b)=>a&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
function harness(path,loader,dependencies){
 const slots=[],effects=[];let cursor=0;
 const hooks={...React,useRef(value){const i=cursor++;return slots[i]??={current:value};},useState(value){const i=cursor++;if(!(i in slots))slots[i]=value;return [slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next;}];},useCallback(fn,deps){const i=cursor++;if(!slots[i]||!equal(slots[i].deps,deps))slots[i]={fn,deps};return slots[i].fn;},useEffect(fn,deps){const i=cursor++;if(!slots[i]||!equal(slots[i].deps,deps))effects.push(()=>{slots[i]?.cleanup?.();slots[i]={deps,cleanup:fn()};});}};
 const module={exports:{}};new Function('require','module','exports',code)(name=>name==='react'?hooks:require(name),module,module.exports);
 return {render(){cursor=0;return module.exports.useResource(path,loader,dependencies);},commit(){effects.splice(0).forEach(fn=>fn());}};
}
const tick=()=>new Promise(setImmediate);
test('reconciliation hides old state immediately in all four views and ignores late pre-reconciliation reads',async()=>{
 const before=globalThis.window,listeners=new Set();globalThis.window={addEventListener(_e,fn){listeners.add(fn);},removeEventListener(_e,fn){listeners.delete(fn);}};
 try{
  const pending=[],loader=(_path,init)=>new Promise(resolve=>pending.push({resolve,signal:init.signal}));
  const views=[['/subscribers',[]],['/subscriber-center/demo-sub-test',[]],['/management/report',['/subscribers']],['/dashboard/summary',['/subscribers']]].map(([path,deps])=>harness(path,loader,deps));
  views.forEach(view=>{view.render();view.commit();});pending.splice(0).forEach(req=>req.resolve({revision:1,status:'PAUSED'}));await tick();
  views.forEach(view=>assert.equal(view.render().data.revision,1));
  // Start older reads before a confirmed mutation; these may ignore abort on the transport.
  views.forEach(view=>{view.render().retry();view.render();view.commit();});const old=pending.splice(0);
  for(const changed of listeners)changed({detail:['/subscribers','/subscriber-center','/dashboard','/reports']});
  assert.ok(old.every(req=>req.signal.aborted),'cancel before effects commit');
  views.forEach(view=>{const state=view.render();assert.equal(state.loading,true);assert.equal(state.data,undefined);view.commit();});
  pending.splice(0).forEach(req=>req.resolve({revision:2,status:'ACTIVE'}));await tick();views.forEach(view=>assert.equal(view.render().data.revision,2));
  old.forEach(req=>req.resolve({revision:1,status:'PAUSED'}));await tick();views.forEach(view=>assert.equal(view.render().data.revision,2));
 }finally{globalThis.window=before;}
});
