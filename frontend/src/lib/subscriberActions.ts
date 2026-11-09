import type {Subscriber} from './api';
import type {CenterSubscriber} from './subscriberCenter';
import type {SubscriberDetailData} from './api';
import {safeSubscriberCenter,type SubscriberCenterData} from './subscriberCenter';

// Source routing and eligibility are shared by detail surfaces; server authorization remains authoritative.
export function canChangeLegacy(detail:SubscriberDetailData,id=detail.item.id){
 const s=detail.item;
 return s.id===id&&id.startsWith('demo-sub-')&&detail.is_demo===true&&s.is_demo===true&&detail.persistence==='local-postgresql-demo'&&s.can_manage_pppoe===true&&!!s.router_id&&['LOCAL','RADIUS'].includes(s.source??'');
}
export function canChangeWorkspace(data:SubscriberCenterData,centralAdmin:boolean){
 const s=data.item;
 return safeSubscriberCenter(data,s.id)&&data.source==='PERSISTENT_WORKSPACE'&&canChangeWorkspaceItem(s,centralAdmin);
}

export type SubscriberQuickAction='EXTEND'|'PLAN'|'STATUS';
export function nextAccountStatus(status:string){return status==='ACTIVE'?'PAUSED':'ACTIVE';}
export function accountActionLabel(status:string){return status==='ACTIVE'?'Hesabı Kapat':'Hesabı Aç';}

// List selection is provisional; the canonical legacy detail is checked before opening a modal.
export function canSelectLegacyAction(s:Subscriber){return s.is_demo===true&&s.id.startsWith('demo-sub-')&&s.can_manage_pppoe===true&&!!s.router_id&&['LOCAL','RADIUS'].includes(s.source??'');}
export function canChangeWorkspaceItem(s:CenterSubscriber,centralAdmin:boolean){return centralAdmin&&s.id.startsWith('demo-managed-sub-')&&!!s.router_id?.startsWith('demo-managed-router-')&&!s.router_missing&&s.router_source==='PERSISTENT_DEMO'&&['LOCAL','RADIUS'].includes(s.source??'')&&['PPPOE','HOTSPOT'].includes(s.access_type??'');}
