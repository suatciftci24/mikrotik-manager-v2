import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import * as React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {buildDailySummary} from '../src/lib/dailySummary.ts';
const require=createRequire(import.meta.url),refs=[];let cursor=0;let identity={permissions:{r1:{can_view:true,can_view_reports:true}}};
const hooks={...React,useEffect(){},useCallback:fn=>fn,useContext:()=>identity,useRef:value=>refs[cursor++]??={current:value},useState:value=>[typeof value==='function'?value():value,()=>{}]};
const result=await build({entryPoints:[fileURLToPath(new URL('../src/screens/Dashboard.tsx',import.meta.url))],bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'read-source',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'source',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(path){return path.startsWith("/dashboard/summary")?globalThis.__expiryResource:{loading:true,retry(){}}}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(name=>name==='react'?hooks:require(name),module,module.exports);
const nodes=tree=>!tree||typeof tree!=='object'?[]:[tree,...React.Children.toArray(tree.props?.children).flatMap(nodes)];
test('Dashboard hides previous expiry counts during refresh and preserves Today/3/7/30/unknown and LAST_24 report context',()=>{
 const before=globalThis.window;globalThis.window={location:{hash:'#module=dashboard'}};const links=[];
 const day=buildDailySummary([],[],new Date()).as_of_date;
 const records=[day,null].map((expires_on,index)=>({item:{id:'demo-sub-'+index,revision:1,customer_name:'Sentetik',username:'synthetic'+index,router_name:'Sentetik router',source:'LOCAL',status:'ACTIVE',expires_on,is_demo:true},is_demo:true,history:[]}));
 const data={...buildDailySummary([],records,new Date()),expiry_today:1,within_3:1};
 const draw=resource=>{globalThis.__expiryResource={...resource,retry(){}};cursor=0;const root=module.exports.Dashboard({onNavigate:(module,params)=>links.push({module,params})});const overview=root.type(root.props);const synthetic=overview.props.children[1];return synthetic.type(synthetic.props);};
 try{
  let tree=draw({loading:false,data});assert.match(renderToStaticMarkup(tree),/Bugün: 1/);
  for(const [label,expiry] of [['Bugün: ','TODAY'],['3 gün içinde: ','WITHIN_3'],['7 gün içinde: ','WITHIN_7'],['30 gün içinde: ','WITHIN_30'],['Bitişi bilinmeyen: ','UNKNOWN']]){nodes(tree).find(node=>node.type==='button'&&node.props.children?.[0]===label).props.onClick();assert.deepEqual(links.at(-1),{module:'subscribers',params:{workspace:'LEGACY',expiry}});}
  nodes(tree).find(node=>node.type==='button'&&node.props.children?.includes?.('Son 24 saat yönetim işlemleri')).props.onClick();const reportParams=new URLSearchParams(links.at(-1).params);assert.equal(reportParams.get('period'),'LAST_24');assert.equal(reportParams.get('kind'),'OPERATIONS');assert.equal(reportParams.get('section'),'recent-operations');assert.equal(reportParams.get('report_source'),'DEMO');
  const loading=renderToStaticMarkup(draw({loading:true}));assert.match(loading,/Güncel kayıtlar doğrulanıyor/);assert.doesNotMatch(loading,/aria-label="7 gün içinde bitecek aboneleri göster"|Bugün: 1|30 gün içinde: 1/);
  const failed=renderToStaticMarkup(draw({loading:false,error:'Kaynak doğrulanamadı'}));assert.match(failed,/role="alert"/);assert.doesNotMatch(failed,/Bugün: 1/);
  const current=renderToStaticMarkup(draw({loading:false,data:{...buildDailySummary([],records.map((record,index)=>({...record,item:{...record.item,revision:2,expires_on:index===0?'2099-01-01':null}})),new Date()),expiry_today:0,within_3:0}}));assert.match(current,/Bugün: 0/);assert.match(current,/30 gün içinde: 0/);
 }finally{globalThis.window=before;delete globalThis.__expiryResource;}
});

test('workspace Dashboard prioritizes four unique cards and preserves scoped daily audit navigation',()=>{
 const before=globalThis.window,prior=identity,links=[];
 globalThis.window={location:{hash:'#module=dashboard'}};identity={role_code:'ADMIN',can_manage_users:true,router_inventory_source:'PERSISTENT_WORKSPACE',permissions:{}};
 try{
  const data={...buildDailySummary([],[],new Date()),history_available:true,expiry_today:0,within_3:0};data.operation_history=[{id:'saved-audit',access_type:'PPPOE',occurred_at:new Date().toISOString(),audit_result:'APPLIED'}];
  globalThis.__expiryResource={data,loading:false,retry(){}};cursor=0;
  const root=module.exports.Dashboard({onNavigate:(module,params)=>links.push({module,params})}),overview=root.type(root.props),synthetic=overview.props.children[1],tree=synthetic.type(synthetic.props);
  const grid=nodes(tree).find(n=>n.props?.className==='overview-status-grid'),tiles=nodes(grid).filter(n=>n.type?.name==='SummaryTile');
  assert.deepEqual(tiles.map(n=>n.props.title),['Routerlar','Toplam aboneler','Yaklaşan bitişler','PPPoE işlemleri']);
  assert.equal(tiles[3].props.value,1);tiles[3].props.onClick();assert.equal(new URLSearchParams(links.at(-1).params).get('period'),'TODAY');assert.equal(new URLSearchParams(links.at(-1).params).get('kind'),'PPPOE');
  tiles[2].props.onClick();assert.deepEqual(links.at(-1),{module:'subscribers',params:{workspace:'PERSISTENT',expiry:'WITHIN_7'}});
  assert.equal(nodes(tree).find(n=>n.props?.className==='overview-secondary technical-info').props.open,false);
  assert.equal(nodes(tree).filter(n=>n.type?.name==='SummaryTile'&&n.props.title==='PPPoE işlemleri').length,1);
 }finally{globalThis.window=before;identity=prior;delete globalThis.__expiryResource;}
});
