import {api,ApiError} from './api';
import type {DailyEntry,OperationReceipt} from './subscriberManagementCenter';
export {subscriberOperationError} from './subscriberOperationError';
export {legacySavedReceipt} from './legacySubscriberReceipt';

export function operationReceiptMatches(entry:DailyEntry,receipt:OperationReceipt){
 const valid=!!receipt&&receipt.request_id===entry.request_id&&receipt.item_id===entry.item_id&&receipt.operation===entry.operation&&typeof receipt.recorded==='boolean'&&typeof receipt.success==='boolean'&&(!receipt.success||receipt.recorded)&&!!receipt.previous&&typeof receipt.previous==='object'&&!Array.isArray(receipt.previous)&&!!receipt.values&&typeof receipt.values==='object'&&!Array.isArray(receipt.values)&&typeof receipt.occurred_at==='string'&&typeof receipt.actor_id==='string'&&Number.isInteger(receipt.revision);
 if(!valid)return false;
 if(receipt.recorded&&(!receipt.actor_id.trim()||!/(?:Z|[+-]\d{2}:\d{2})$/.test(receipt.occurred_at)||!Number.isFinite(Date.parse(receipt.occurred_at))))return false;
 if(!receipt.success)return true;
 if(receipt.revision!==entry.expected_revision+1||receipt.previous_router_id!==entry.expected_router_id||receipt.router_id!==(entry.operation==='ROUTER'?entry.value:entry.expected_router_id)||receipt.error!==null)return false;
 const field={EDIT:'customer_name',PLAN:'plan',STATUS:'status',EXPIRE:'expires_on',EXTEND:'expires_on',ROUTER:'router_id'}[entry.operation];
 return receipt.values[field]===entry.value;
}
export function unknownOperation(entry:DailyEntry):OperationReceipt{
 return {item_id:entry.item_id,request_id:entry.request_id,operation:entry.operation,success:false,recorded:false,actor_id:'',router_id:null,previous_router_id:null,previous:{},values:{},occurred_at:'',revision:0,error:'Kalıcı sonuç henüz doğrulanamadı; bu kayıt için aynı UUID ile sorgulayın.'};
}
export async function readOperationResults(entries:DailyEntry[],known:OperationReceipt[],signal:AbortSignal){
 const results=entries.map(entry=>known.find(r=>r.recorded&&operationReceiptMatches(entry,r))??unknownOperation(entry));
 let cursor=0;
 async function worker(){
  while(cursor<entries.length&&!signal.aborted){
   const index=cursor++;if(results[index].recorded)continue;
   const entry=entries[index];
   try{
    const result=await api<{request_id:string;status:'SUCCESS'|'FAILED'|'UNKNOWN';response:OperationReceipt|null}>('/subscriber-workspace/management/requests/'+encodeURIComponent(entry.request_id),{signal});
    if(result?.request_id===entry.request_id&&result.status!=='UNKNOWN'&&result.response?.recorded===true&&operationReceiptMatches(entry,result.response)&&((result.status==='SUCCESS'&&result.response.success)||(result.status==='FAILED'&&!result.response.success)))results[index]=result.response;
   }catch{/* A failed GET cannot determine the original write's outcome. */}
  }
 }
 await Promise.all(Array.from({length:Math.min(5,entries.length)},worker));
 return results;
}

