import type {CenterSubscriber} from './subscriberCenter';
export type RouterSubscriberData={items:CenterSubscriber[];total:number|null;page:number;page_size:number;is_demo:boolean;source:'PERSISTENT_WORKSPACE'|'LEGACY_DEMO'|'REGISTERED';availability:'AVAILABLE'|'PREPARING'};
export function validRouterSubscribers(data:RouterSubscriberData,id:string,access:'PPPOE'|'HOTSPOT'){
 if(id.startsWith('registered-'))return data.source==='REGISTERED'&&data.is_demo===false&&data.availability==='PREPARING'&&data.total===null&&data.items.length===0;
 const persistent=id.startsWith('demo-managed-router-');
 return data.is_demo===true&&data.availability==='AVAILABLE'&&data.source===(persistent?'PERSISTENT_WORKSPACE':'LEGACY_DEMO')&&Number.isInteger(data.total)&&typeof data.total==='number'&&data.total>=0&&data.items.every(item=>item.router_id===id&&item.access_type===access&&item.session_status==='UNKNOWN'&&item.router_source===(persistent?'PERSISTENT_DEMO':'STATIC_DEMO'));
}
