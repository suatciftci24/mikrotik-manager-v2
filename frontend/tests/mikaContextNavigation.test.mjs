import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {detailReturnHash,centerReturnHash,linkedCenterHash} from '../src/lib/detailLinks.ts';
const require=createRequire(import.meta.url);
const result=await build({stdin:{contents:"export {EventDialog} from './src/screens/Mikajani';export {PermissionContext} from './src/lib/permissions';",resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']});
const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(require,module,module.exports);
const {EventDialog,PermissionContext}=module.exports;
const id='demo-router-a';
const event={id:'demo-event',title:'Sentetik bulgu',priority:'P2',state:'OPEN',reason:'Eksik gözlem',evidence:'Yalnız kayıtlı kanıt',affected_router_ids:[id,'unknown-router'],confidence:'LOW',recommendation:'İnceleyin',opened_at:null,updated_at:null,resolved_at:null,history:[],is_demo:true};
function render(contextLinks,identity){const previous=globalThis.window;globalThis.window={location:{hash:'#module=mikajani&event=demo-event&priority=P2'}};try{return renderToStaticMarkup(createElement(PermissionContext.Provider,{value:identity},createElement(EventDialog,{event,names:{[id]:'Sentetik router'},contextLinks,onClose(){}})));}finally{globalThis.window=previous;}}
test('Mika context links require known router and view permission and preserve event return',()=>{
 const html=render(true,{permissions:{[id]:{can_view:true}}});
 assert.match(html,/Router detayı/);assert.match(html,/Router alarmları/);assert.match(html,/return_to=%23module%3Dmikajani/);
 assert.doesNotMatch(html,/id=unknown-router/);
 assert.doesNotMatch(render(true,null),/Router detayı|Router alarmları/);
});
test('scenario findings cannot navigate to saved routers even with permission',()=>{
 const html=render(false,{permissions:{[id]:{can_view:true}}});
 assert.match(html,/Senaryo bulguları kayıtlı router veya abone bağlantısı değildir/);assert.doesNotMatch(html,/href=/);
});
test('bounded Mika return context strips recursion and rejects external destinations',()=>{
 const from='#module=mikajani&event=demo-event&priority=P2&return_to=evil';
 const target=linkedCenterHash('#module=operations&section=alarms',from);
 assert.equal(centerReturnHash(target),'#module=mikajani&event=demo-event&priority=P2');
 assert.equal(detailReturnHash('https://external.example'),null);assert.equal(detailReturnHash('#module=mikajani&event='+ 'x'.repeat(4000)),null);
});
