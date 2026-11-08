import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import * as React from 'react';
const require=createRequire(import.meta.url);
let effects=[],calls=[],states=[];
const hooks={...React,useContext:()=>null,useEffect:fn=>effects.push(fn),useRef:()=>({current:{scrollIntoView:()=>calls.push('scroll'),focus:()=>calls.push('focus')}}),useState:value=>[typeof value==='function'?value():value,next=>states.push(next)]};
const result=await build({stdin:{contents:"export {ManagementReport} from './src/screens/ManagementReport';export {OperationDetails} from './src/components/OperationDetails';export {SubscriberDeviceCenter} from './src/components/SubscriberDeviceCenter';",resolveDir:process.cwd(),loader:'tsx'},bundle:true,write:false,loader:{'.css':'empty'},platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'resource',setup(b){b.onResolve({filter:/lib\/useResource$/},()=>({path:'resource',namespace:'test'}));b.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export function useResource(){return globalThis.__navigationResource}',loader:'js'}));}}]});
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
   globalThis.__navigationResource={loading:true};effects=[];states=[];
   module.exports.SubscriberDeviceCenter({id:'s',onBack(){}});
   effects.at(-1)();assert.equal(states.at(-1),expected);
  }
 }finally{globalThis.window=before;delete globalThis.__navigationResource;}
});
