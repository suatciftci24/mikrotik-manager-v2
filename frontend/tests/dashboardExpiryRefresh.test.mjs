import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const require=createRequire(import.meta.url),refs=[];let cursor=0;
const hooks={...React,useEffect(){},useCallback:fn=>fn,useContext:()=>({permissions:{r1:{can_view:true,can_view_reports:true}}}),useRef:value=>refs[cursor++]??={current:value},useState:value=>[typeof value==='function'?value():value,()=>{}]};
const result=await build({entryPoints:[fileURLToPath(new URL('../src/screens/Dashboard.tsx',import.meta.url))],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'read-source',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){return path==="/dashboard/summary"?globalThis.__expiryResource:{loading:true,retry(){}}}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(name=>name==='react'?hooks:require(name),module,module.exports);
const nodes=tree=>!tree||typeof tree!=='object'?[]:[tree,...React.Children.toArray(tree.props?.children).flatMap(nodes)];
test('Dashboard hides previous expiry counts during refresh and preserves legacy filtered links for Today/30/unknown',()=>{
 const before=globalThis.window;globalThis.window={location:{hash:'#module=dashboard'}};const links=[];
 const day=buildDailySummary([],[],new Date()).as_of_date;
 const records=[day,null].map((expires_on,index)=>({item:{id:'demo-sub-'+index,revision:1,customer_name:'Sentetik',username:'synthetic'+index,router_name:'Sentetik router',source:'LOCAL',status:'ACTIVE',expires_on,is_demo:true},is_demo:true,history:[]}));
 const data={...buildDailySummary([],records,new Date()),expiry_today:1,within_3:1};
 const draw=resource=>{globalThis.__expiryResource={...resource,retry(){}};cursor=0;const root=module.exports.Dashboard({onNavigate:(module,params)=>links.push({module,params})});const overview=root.type(root.props);const synthetic=overview.props.children[1];return synthetic.type(synthetic.props);};
 try{
  let tree=draw({loading:false,data});assert.match(renderToStaticMarkup(tree),/Bugün: 1/);
  for(const [label,expiry] of [['Bugün: ','TODAY'],['30 gün içinde: ','WITHIN_30'],['Bitişi bilinmeyen: ','UNKNOWN']]){nodes(tree).find(node=>node.type==='button'&&node.props.children?.[0]===label).props.onClick();assert.deepEqual(links.at(-1),{module:'subscribers',params:{workspace:'LEGACY',expiry}});}
  const loading=renderToStaticMarkup(draw({loading:true}));assert.match(loading,/Güncel kayıtlar doğrulanıyor/);assert.doesNotMatch(loading,/aria-label="7 gün içinde bitecek aboneleri göster"|Bugün: 1|30 gün içinde: 1/);
  const failed=renderToStaticMarkup(draw({loading:false,error:'Kaynak doğrulanamadı'}));assert.match(failed,/role="alert"/);assert.doesNotMatch(failed,/Bugün: 1/);
  const current=renderToStaticMarkup(draw({loading:false,data:{...buildDailySummary([],records.map((record,index)=>({...record,item:{...record.item,revision:2,expires_on:index===0?'2099-01-01':null}})),new Date()),expiry_today:0,within_3:0}}));assert.match(current,/Bugün: 0/);assert.match(current,/30 gün içinde: 0/);
 }finally{globalThis.window=before;delete globalThis.__expiryResource;}
});
