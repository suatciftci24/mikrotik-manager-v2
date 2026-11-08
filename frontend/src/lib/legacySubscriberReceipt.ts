/** Validate the legacy demo endpoint's atomic receipt for one request. */
export function legacySavedReceipt(requestId:string,value:unknown,actor?:string){
 const data=value as import('./api').SubscriberDetailData|undefined;
 const item=data?.item;
 return !!item&&data?.is_demo===true&&data.persistence==='local-postgresql-demo'&&item.is_demo===true&&typeof item.id==='string'&&item.id.startsWith('demo-sub-')&&Number.isInteger(item.revision)&&item.revision>0&&['LOCAL','RADIUS'].includes(item.source??'')&&Array.isArray(data.history)&&data.history.some(event=>event.id===requestId&&event.is_demo===true&&typeof event.actor_id==='string'&&!!event.actor_id&&(!actor||event.actor_id===actor)&&event.source===item.source&&['CREATE','PLAN_CHANGE','STATUS_CHANGE','RENEWAL','DATE_EDIT'].includes(event.operation)&&/(?:Z|[+-]\d{2}:\d{2})$/.test(event.occurred_at)&&Number.isFinite(Date.parse(event.occurred_at)));
}
