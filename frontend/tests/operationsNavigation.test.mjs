import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import * as React from 'react';
const require=createRequire(import.meta.url);
let effects=[],calls=[],states=[],initialStates=[],selectedEvent=null;
const hooks={...React,useCallback:fn=>fn,useContext:()=>null,useEffect:fn=>effects.push(fn),useRef:()=>({current:{scrollIntoView:()=>calls.push('scroll'),focus:()=>calls.push('focus')}}),useState:value=>{const initial=value===null&&selectedEvent?selectedEvent:typeof value==='function'?value():value;initialStates.push(initial);return [initial,next=>states.push(next)];}};
const result=await build({stdin:{contents:"export {OperationReport} from './src/screens/OperationReport';export {ManagementReport} from './src/screens/ManagementReport';export {OperationDetails} from './src/components/OperationDetails';export {SubscriberDeviceCenter} from './src/components/SubscriberDeviceCenter';",resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'resource',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'resource',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return globalThis.__navigationResource}',loader:'js'}));}}]});
const module={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(name=>name==='react'?hooks:require(name),module,module.exports);
function draw(hash,state){
 globalThis.window={location:{hash}};globalThis.__navigationResource=state;effects=[];calls=[];
 const tree=module.exports.ManagementReport({onBack(){}});
 const child=tree.props.children[1];
 if(typeof child.type==='function')child.type(child.props);
 return effects;
}
test('report scroll waits for validated data, handles empty results and avoids V1 and errors',()=>{
 const before=globalThis.window;
 const hash='#module=dashboard&view=DAILY_REPORT&report_source=DEMO&period=LAST_24&kind=PPPOE&section=recent-operations';
 const data={routers:[],details:[],events:[],read_at:new Date().toISOString()};
 try{
  for(const state of [{loading:true},{loading:false,error:'Yetki gerekli'},{loading:false,data:{...data,routers:[{is_demo:false}]}}]){
   draw(hash,state).at(-1)();assert.deepEqual(calls,[]);
  }
  draw(hash,{data,loading:false}).at(-1)();assert.deepEqual(calls,['scroll','focus']);
  draw('#module=dashboard&view=DAILY_REPORT',{data,loading:false}).at(-1)();assert.deepEqual(calls,[]);
  assert.equal(draw(hash.replace('report_source=DEMO','report_source=V1_INVENTORY'),{data,loading:false}).length,1);
 }finally{globalThis.window=before;delete globalThis.__navigationResource;}
});

function nodes(tree){return !tree||typeof tree!=='object'?[]:[tree,...React.Children.toArray(tree.props?.children).flatMap(nodes)];}
test('operation detail closes before opening subscriber, router or existing history',()=>{
 const event={id:'op',subscriber_id:'s & 1',customer_name:'Demo',username:'demo',router_name:'Demo router',operation:'CREATE',source:'LOCAL',occurred_at:new Date().toISOString()};
 for(const [label,target] of [['Abone detayını aç','subscriber'],['Router detayını aç','router'],['İşlem geçmişini aç','history']]){
  const called=[];
  const tree=module.exports.OperationDetails({event,onClose:()=>called.push('close'),onSubscriber:id=>called.push(id),onRouter:()=>called.push('router'),onHistory:()=>called.push('history')});
  nodes(tree).find(node=>node.type==='button'&&node.props.children===label).props.onClick();
  assert.deepEqual(called,['close',target==='subscriber'?event.subscriber_id:target]);
 }
 const tree=module.exports.OperationDetails({event,onClose(){},onSubscriber(){}});
 assert.equal(nodes(tree).some(node=>node.type==='button'&&node.props.children==='Router detayını aç'),false);
});

test('subscriber history deep link selects existing tab and rejects unknown tabs',()=>{
 const before=globalThis.window;
 try{
  for(const [value,expected] of [['history','history'],['invalid','overview']]){
   globalThis.window={location:{hash:'#module=subscribers&id=s&tab='+value},scrollTo(){},addEventListener(){},removeEventListener(){}};
   globalThis.__navigationResource={loading:true};effects=[];states=[];initialStates=[];
   module.exports.SubscriberDeviceCenter({id:'s',onBack(){}});
   assert.equal(initialStates[0],expected);
  }
 }finally{globalThis.window=before;delete globalThis.__navigationResource;}
});

test('manual subscriber tab choice persists URL and keeps report return context',()=>{
 const before=globalThis.window,priorEvent=globalThis.HashChangeEvent;
 const back='#module=dashboard&view=DAILY_REPORT&period=LAST_24&kind=PPPOE&section=recent-operations';
 const params=new URLSearchParams({module:'subscribers',id:'demo-sub-test',workspace:'LEGACY',return_to:back});
 let replaced;globalThis.window={location:{hash:'#'+params,pathname:'/',search:''},history:{replaceState(_a,_b,url){replaced=url;}},dispatchEvent(){}};globalThis.HashChangeEvent=class {};
 globalThis.__navigationResource={loading:false,data:{item:{id:'demo-sub-test',session_status:'UNKNOWN'},is_demo:true,source:'LEGACY_DEMO',device_connection_started:false}};
 try{
  const tree=module.exports.SubscriberDeviceCenter({id:'demo-sub-test',onBack(){}});
  const view=nodes(tree).find(node=>typeof node.type==='function'&&node.props.onTab);
  view.props.onTab('history');
  const result=new URLSearchParams(replaced.split('#')[1]);
  assert.equal(result.get('tab'),'history');assert.equal(result.get('return_to'),back);assert.equal(result.get('id'),'demo-sub-test');
 }finally{globalThis.window=before;globalThis.HashChangeEvent=priorEvent;delete globalThis.__navigationResource;}
});

test('operation audit detail exposes router and subscriber history with filtered return, hides stale dialog while loading',()=>{
 const before=globalThis.window;
 globalThis.window={location:{hash:'#module=dashboard&view=OPERATIONS_REPORT&category=AUDIT&page=2&router_id=demo-router-test'}};
 selectedEvent={id:'op',subscriber_id:'demo-sub-test',router_id:'demo-router-test',operation:'CREATE',is_demo:true};
 globalThis.__navigationResource={loading:false};
 try{
  let tree=module.exports.OperationReport();
  const dialog=nodes(tree).find(node=>node.props.event===selectedEvent);
  assert.equal(typeof dialog.props.onRouter,'function');dialog.props.onRouter();
  let params=new URLSearchParams(window.location.hash.slice(1));
  assert.equal(params.get('id'),'demo-router-test');assert.equal(params.get('source'),'DEMO');
  assert.equal(new URLSearchParams(params.get('return_to').slice(1)).get('page'),'2');
  dialog.props.onHistory();params=new URLSearchParams(window.location.hash.slice(1));
  assert.equal(params.get('id'),'demo-sub-test');assert.equal(params.get('tab'),'history');assert.equal(params.get('workspace'),'LEGACY');
  window.location.hash='#module=dashboard&view=OPERATIONS_REPORT&category=AUDIT';
  globalThis.__navigationResource={loading:true};tree=module.exports.OperationReport();
  assert.equal(nodes(tree).some(node=>node.props.event===selectedEvent),false);
 }finally{globalThis.window=before;selectedEvent=null;delete globalThis.__navigationResource;}
});
