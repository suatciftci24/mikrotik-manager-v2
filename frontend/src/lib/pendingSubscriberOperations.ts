import {legacySavedReceipt} from './subscriberOperationRecovery';
import {safeSubscriberCenter,type SubscriberCenterData} from './subscriberCenter';
import type {SubscriberDetailData} from './api';
import type {User} from '../components/Sidebar';
export const pendingPrefix='v2.pending-subscriber.v1.';
export const pendingTTL=7*24*60*60*1000;
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const paths={legacy:'/subscribers/demo-requests/',save:'/subscriber-workspace/requests/',renew:'/subscriber-workspace/renewals/requests/',bulk:'/subscriber-workspace/management/requests/'};
export type PendingOperation={actor:string;id:string;kind:keyof typeof paths;created:number};
let identity:User|null=null;
let generation=0;
export const identityStamp=(user:User|null)=>JSON.stringify(user?[user.id,user.role_code,user.active,user.revision,user.permissions]:null);
export function pendingIdentity(user:User|null){
 const changed=identity!==null&&identityStamp(identity)!==identityStamp(user);
 if(identityStamp(identity)!==identityStamp(user)){generation++;identity=user;}
 for(const item of pendingOperations())if(changed||!user||user.active===false||user.role_code!=='ADMIN'||item.actor!==user.id)forgetPending(item.id);
}
export function pendingOperations():PendingOperation[]{
 const result:PendingOperation[]=[];
 try{
  for(const key of Object.keys(localStorage).filter(k=>k.startsWith(pendingPrefix))){
   try{
    const value=JSON.parse(localStorage.getItem(key)??'null');
    if(!value||Object.keys(value).sort().join()!=='actor,created,id,kind'||typeof value.actor!=='string'||!value.actor||value.actor.length>200||!uuid.test(value.id)||key!==pendingPrefix+value.id||!Object.hasOwn(paths,value.kind)||!Number.isFinite(value.created)||value.created>Date.now()+60000||Date.now()-value.created>pendingTTL)throw Error();
    result.push(value);
   }catch{localStorage.removeItem(key);}
  }
 }catch{/* Storage may be disabled; never persist payload as a fallback. */}
 return result;
}
export function forgetPending(id:string){try{const existed=localStorage.getItem(pendingPrefix+id)!==null;localStorage.removeItem(pendingPrefix+id);if(existed)window.dispatchEvent(new Event('v2-pending-change'));}catch{} }
export function rememberPending(id:string,resultPath:string){
 if(!identity||identity.role_code!=='ADMIN'||identity.active===false||!uuid.test(id))return;
 const kind=(Object.keys(paths) as (keyof typeof paths)[]).find(k=>resultPath===paths[k]+id);
 if(!kind)return;
 try{localStorage.setItem(pendingPrefix+id,JSON.stringify({actor:identity.id,id,kind,created:Date.now()}));window.dispatchEvent(new Event('v2-pending-change'));}catch{}
}
export async function recoverPending(item:PendingOperation,signal:AbortSignal,request:<T>(path:string,init?:RequestInit)=>Promise<T>):Promise<'SUCCESS'|'FAILED'|'UNKNOWN'|'DENIED'>{
 const stamp=generation,actor=identity;
 const valid=()=>!signal.aborted&&stamp===generation&&actor?.id===item.actor&&actor.role_code==='ADMIN'&&actor.active!==false&&identity?.id===item.actor;
 if(!valid())return 'DENIED';
 const current=await request<User>('/auth/me',{signal});
 if(identityStamp(current)!==identityStamp(actor)){pendingIdentity(current);return 'DENIED';}
 if(!valid())return 'DENIED';
 const result=await request<{request_id:string;status:string;response:unknown}>(paths[item.kind]+item.id,{signal});
 if(!valid())return 'DENIED';
 if(result?.request_id!==item.id||!['SUCCESS','FAILED'].includes(result.status)||!result.response||typeof result.response!=='object')return 'UNKNOWN';
 const response=result.response as Record<string,unknown>;
 if(item.kind==='bulk'&&(response.request_id!==item.id||response.actor_id!==item.actor||response.recorded!==true||response.success!==(result.status==='SUCCESS')))return 'UNKNOWN';
 let saved:Record<string,unknown>;
 if(item.kind==='legacy'){
  if(result.status!=='SUCCESS'||!legacySavedReceipt(item.id,response,item.actor))return 'UNKNOWN';
  saved=response.item as Record<string,unknown>;
 }else if(item.kind==='bulk'){
  if(typeof response.item_id!=='string'||!response.item_id.startsWith('demo-managed-sub-')||!Number.isInteger(response.revision)||typeof response.occurred_at!=='string'||!Number.isFinite(Date.parse(response.occurred_at)))return 'UNKNOWN';
  saved={id:response.item_id,revision:response.revision};
 }else{
  if(result.status!=='SUCCESS'||typeof response.id!=='string'||!response.id.startsWith('demo-managed-sub-')||!['LOCAL','RADIUS'].includes(String(response.source))||!Number.isInteger(response.revision)||Number(response.revision)<1||response.router_source!=='PERSISTENT_DEMO')return 'UNKNOWN';
  saved=response;
 }
 // A historical receipt is not the current account. Read it without writing/merging stale fields.
 if(result.status==='SUCCESS'){
  const id=String(saved.id);
  if(item.kind==='legacy'){
   const detail=await request<SubscriberDetailData>('/subscribers/'+encodeURIComponent(id),{signal});
   if(!valid())return 'DENIED';
   if(!detail||detail.is_demo!==true||detail.persistence!=='local-postgresql-demo'||detail.item?.id!==id||detail.item.is_demo!==true||detail.item.source!==saved.source||!Number.isInteger(detail.item.revision)||detail.item.revision<Number(saved.revision)||!detail.history?.some(event=>event.id===item.id&&event.actor_id===item.actor&&event.is_demo===true))return 'UNKNOWN';
   if(detail.item.revision===saved.revision&&['source','router_id','username','plan','status','expires_on'].some(key=>(detail.item as unknown as Record<string,unknown>)[key]!==saved[key]))return 'UNKNOWN';
  }else{
   const detail=await request<SubscriberCenterData>('/subscriber-center/'+encodeURIComponent(id),{signal});
   if(!valid())return 'DENIED';
   if(!detail||!Array.isArray(detail.history)||!safeSubscriberCenter(detail,id)||detail.source!=='PERSISTENT_WORKSPACE'||!['LOCAL','RADIUS'].includes(detail.item.source??'')||!Number.isInteger(detail.item.revision)||detail.item.revision<Number(saved.revision))return 'UNKNOWN';
   if(item.kind!=='bulk'&&detail.item.source!==saved.source)return 'UNKNOWN';
   if(detail.item.revision===saved.revision){const values=item.kind==='bulk'?(response.values as Record<string,unknown>):saved;if(!values||['source','router_id','username','plan','status','expires_on'].some(key=>Object.hasOwn(values,key)&&(detail.item as unknown as Record<string,unknown>)[key]!==values[key]))return 'UNKNOWN';}
   if(!detail.history.some(event=>event.revision===saved.revision&&event.actor_id===item.actor&&event.result==='APPLIED'&&(item.kind==='renew'?event.operation==='RENEWAL':item.kind==='save'?['CREATE','UPDATE'].includes(event.operation):event.operation===response.operation)))return 'UNKNOWN';
  }
 }
 const verified=await request<User>('/auth/me',{signal});
 if(!valid()||identityStamp(verified)!==identityStamp(actor)){pendingIdentity(verified);return 'DENIED';}
 forgetPending(item.id);
 return result.status as 'SUCCESS'|'FAILED';
}
