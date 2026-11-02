/** Bounded CDP requests/events and explicit virtual-clock progress. No API credentials. */
export class BrowserCheckError extends Error {
 constructor(step,expected,actual){super(step);this.report={status:'BLOCKED',step,expected,actual};}
}
export async function connectPage(endpoint,{timeout=5000}={}){
 const response=await fetch(endpoint+'/json/list',{signal:AbortSignal.timeout(timeout)});
 const targets=await response.json();
 const target=targets.find(t=>t.type==='page');
 if(!target)throw new BrowserCheckError('browser.target','page','missing');
 const ws=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{ws.close();reject(new BrowserCheckError('browser.connect','open','timeout'));},timeout);
  ws.onopen=()=>{clearTimeout(timer);resolve();};ws.onerror=()=>{clearTimeout(timer);reject(new BrowserCheckError('browser.connect','open','socket failure'));};
 });
 let id=0;const pending=new Map(),listeners=new Map();
 const rejectAll=()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(new BrowserCheckError('browser.connection','connected','closed'));}pending.clear();};
 ws.onclose=rejectAll;ws.onerror=rejectAll;
 ws.onmessage=event=>{
  const message=JSON.parse(event.data);
  if(message.id){const p=pending.get(message.id);if(!p)return;pending.delete(message.id);clearTimeout(p.timer);
   if(message.error)p.reject(new BrowserCheckError(p.method,'successful CDP command','protocol error'));else p.resolve(message.result);
  }else for(const fn of [...(listeners.get(message.method)||[])])fn(message.params);
 };
 function send(method,params={}){return new Promise((resolve,reject)=>{
  const n=++id;
  const timer=setTimeout(()=>{pending.delete(n);reject(new BrowserCheckError(method,'CDP response','timeout'));},timeout);
  pending.set(n,{resolve,reject,timer,method});ws.send(JSON.stringify({id:n,method,params}));
 });}
 function event(name){
  let cancel;
  const promise=new Promise((resolve,reject)=>{
   const remove=()=>listeners.set(name,(listeners.get(name)||[]).filter(fn=>fn!==done));
   const done=params=>{clearTimeout(timer);remove();resolve(params);};
   const timer=setTimeout(()=>{remove();reject(new BrowserCheckError(name,'CDP event','timeout'));},timeout);
   cancel=()=>{clearTimeout(timer);remove();resolve(undefined);};
   listeners.set(name,[...(listeners.get(name)||[]),done]);
  });
  return {promise,cancel:()=>cancel()};
 }
 async function evaluate(expression){
  const result=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(result.exceptionDetails)throw new BrowserCheckError('browser.evaluate','successful expression','exception');
  return result.result.value;
 }
 async function advance(milliseconds){
  const expired=event('Emulation.virtualTimeBudgetExpired');
  try{
   // Both promises are observed immediately; neither can wait indefinitely.
   await Promise.all([send('Emulation.setVirtualTimePolicy',{policy:'pauseIfNetworkFetchesPending',budget:milliseconds}),expired.promise]);
  }finally{expired.cancel();}
 }
 async function wait(expression,{step='browser.condition',attempts=50,quantum=25}={}){
  for(let i=0;i<attempts;i++){
   if(await evaluate(expression))return;
   // A spent CDP budget pauses browser tasks, including React commits.
   // Wall-clock sleeps alone cannot progress them. Keep each pump far below 60s.
   await advance(quantum);
   await new Promise(resolve=>setTimeout(resolve,10));
  }
  throw new BrowserCheckError(step,true,false);
 }
 return {send,event,evaluate,advance,wait,close:()=>{ws.close();rejectAll();}};
}
