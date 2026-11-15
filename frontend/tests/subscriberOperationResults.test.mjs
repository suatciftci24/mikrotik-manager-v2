import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url),code=buildSync({entryPoints:['src/components/SubscriberOperationResults.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
const mod={exports:{}};new Function('require','module','exports',code)(require,mod,mod.exports);
test('only verified successes count; internal values and raw errors stay in closed technical details',()=>{
 const base={item_id:'demo-managed-sub-test',request_id:'request-uuid',actor_id:'actor-uuid',revision:2,router_id:'router-uuid',operation:'PLAN',success:true,recorded:true,previous:{},values:{plan:'Plan 200',package_id:'demo-package-internal',package_revision:'3'},occurred_at:'2026-11-15T10:00:00Z',error:null};
 const html=renderToStaticMarkup(mod.exports.SubscriberOperationResults({results:[base,{...base,request_id:'failure-uuid',success:false,error:'revision conflict for request-uuid'},{...base,request_id:'unknown-uuid',success:false,recorded:false}],rows:[{id:base.item_id,customer_name:'Abone Adı'}]}));
 const technical=html.match(/<details class="technical-info">[\s\S]*?<\/details>/)[0],visible=html.replace(technical,'');
 for(const text of ['Başarılı: 1','Başarısız: 1','Sonucu doğrulanamayan: 1','Abone Adı','Plan 200','Kayıt değişmiş'])assert.ok(visible.includes(text),text);
 assert.doesNotMatch(visible,/request-uuid|package_id|demo-package-internal|actor-uuid|router-uuid|conflict/);assert.match(technical,/demo-package-internal/);assert.doesNotMatch(technical,/<details[^>]*open/);
});
