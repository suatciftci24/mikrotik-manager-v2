/** Offline-testable diagnostics. Never retain cookies, bodies, query strings or raw stacks. */
import assert from 'node:assert/strict';
const errorNames=new Set(['Error','AssertionError','TypeError','ReferenceError','SyntaxError','RangeError','TimeoutError']);
const knownMessages=new Set(['Failed to fetch','Load failed','NetworkError when attempting to fetch resource.','ResizeObserver loop limit exceeded','ResizeObserver loop completed with undelivered notifications.']);
const resources=new Set(['auth','preferences','routers','subscribers','alarms','router-events','v1-inventory','dashboard','router-workspace','subscriber-workspace','router-registry','system','reports','users','mikajani']);
function apiPath(raw){
 try{
  const path=new URL(raw).pathname;
  if(['/api/health','/api/ready'].includes(path))return path;
  const parts=path.split('/');
  if(parts[1]==='api'&&parts[2]==='v1'&&resources.has(parts[3])){
   if(parts.length===4)return path;
   if(parts[3]==='auth'&&parts.length===5&&['me','login','logout'].includes(parts[4]))return path;
   return '/api/v1/'+parts[3]+'/<redacted>';
  }
 }catch{}
 return '<unrecognized-api-path>';
}
function safeComparison(value){
 if(!value||!/^((dashboard|center)\.row_\d+\.(identity|provenance|numeric_schema|metrics|cpu_load_percent|memory_used_percent|istanbul_time|status|reason)|dashboard\.(five_counts|priority_order)|source\.(real_contract|identities))$/.test(value.name))return undefined;
 const keys=new Set(['cpu','ram','format','Normal','Dikkat','Kritik','Eski veri','Veri yok']);
 const words=new Set(['Normal','Dikkat','Kritik','Eski veri','Veri yok','INVALID_METRICS','INVALID_STATUS']);
 const safe=v=>typeof v==='boolean'||typeof v==='number'&&Number.isFinite(v)||typeof v==='string'&&words.has(v)||v&&typeof v==='object'&&!Array.isArray(v)&&Object.entries(v).every(([k,n])=>keys.has(k)&&(typeof n==='number'&&Number.isFinite(n)||k==='format'&&n==='INVALID_METRICS'));
 if(!safe(value.actual)||!safe(value.expected))return undefined;
 return {name:value.name,expected:value.expected,actual:value.actual,source:'same_browser_inventory_response',snapshot_bound:true};
}
export function acceptanceDiagnostics(){
 let step='browser.setup',assertionMessage;
 const pageErrors=[],httpFailures=[];
 return {
  setStep(value){step=value;assertionMessage=undefined;},
  pageError(error){
   const frame=String(error.stack??'').match(/\/assets\/([A-Za-z0-9_-]+\.js):(\d+):(\d+)/);
   pageErrors.push({step,name:errorNames.has(error.name)?error.name:'Error',
    message:knownMessages.has(error.message)?error.message:'<untrusted message omitted>',
    ...(frame?{location:'/assets/'+frame[1]+':'+frame[2]+':'+frame[3]}:{})});
  },
  httpFailure(url,status){httpFailures.push({step,path:apiPath(url),status});},
  assertRuntimeClean(){
   step='browser.page_errors';assertionMessage=`Expected 0 page errors; observed ${pageErrors.length}.`;
   assert.equal(pageErrors.length,0,assertionMessage);
   step='browser.http_failures';assertionMessage=`Expected 0 HTTP failures; observed ${httpFailures.length}.`;
   assert.equal(httpFailures.length,0,assertionMessage);
   assertionMessage=undefined;
  },
  failure(error){
   const name=errorNames.has(error.name)?error.name:'Error';
   const comparison=safeComparison(error.comparison);
   const assertionFrame=String(error.stack??'').match(/\/v26-browser-acceptance\.mjs:(\d+):(\d+)/);
   return {status:'FAIL',failure:{step,name,...(comparison?{comparison}:{}),...(assertionFrame?{location:'v26-browser-acceptance.mjs:'+assertionFrame[1]+':'+assertionFrame[2]}:{}),...(error.code==='ERR_ASSERTION'?{code:error.code}:{}),
    message:assertionMessage??`${name} at ${step}; untrusted error operands/message omitted.`},
    diagnostics:{pageErrors:[...pageErrors],httpFailures:[...httpFailures]}};
  }
 };
}
