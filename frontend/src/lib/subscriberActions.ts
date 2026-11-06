import type {SubscriberDetailData} from './api';
import {safeSubscriberCenter,type SubscriberCenterData} from './subscriberCenter';

// Source routing and eligibility are shared by detail surfaces; server authorization remains authoritative.
export function canChangeLegacy(detail:SubscriberDetailData,id=detail.item.id){
 const s=detail.item;
 return s.id===id&&id.startsWith('demo-sub-')&&detail.is_demo===true&&s.is_demo===true&&detail.persistence==='local-postgresql-demo'&&s.can_manage_pppoe===true&&!!s.router_id&&['LOCAL','RADIUS'].includes(s.source??'');
}
export function canChangeWorkspace(data:SubscriberCenterData,centralAdmin:boolean){
 const s=data.item;
 return centralAdmin&&safeSubscriberCenter(data,s.id)&&data.source==='PERSISTENT_WORKSPACE'&&!s.router_missing&&s.router_source==='PERSISTENT_DEMO'&&['LOCAL','RADIUS'].includes(s.source??'')&&['PPPOE','HOTSPOT'].includes(s.access_type??'');
}
