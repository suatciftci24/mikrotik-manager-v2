import {SourceBadge} from './Status';
import {legacyActionUnavailableReason} from '../lib/subscriberActions';
import {useRef,useState} from 'react';
import type {SubscriberDetailData} from '../lib/api';
import {canChangeLegacy} from '../lib/subscriberActions';
import {useResource} from '../lib/useResource';
import {useTurkeyToday} from '../lib/useTurkeyToday';
import {QuickActions,type QuickAction} from './QuickActions';
import {SubscriberQuickButtons} from './SubscriberQuickButtons';
import {ResourceState} from './Resource';

export function LegacySubscriberActions({id,initialAction,onClose,onHistory,onSelect}:{id:string;initialAction?:QuickAction;onClose?:()=>void;onHistory?:()=>void;onSelect?:(detail:SubscriberDetailData,action:QuickAction)=>void}){
 const resource=useResource<SubscriberDetailData>('/subscribers/'+encodeURIComponent(id),undefined,['/subscribers']);
 const [action,setAction]=useState<QuickAction|null>(initialAction??null);
 const today=useTurkeyToday(),detail=resource.data;
 const selected=useRef<SubscriberDetailData|null>(null);
 const allowed=!!detail&&!resource.loading&&!resource.error&&canChangeLegacy(detail,id);
 if(allowed&&action&&!selected.current)selected.current=detail;
 function open(next:QuickAction){if(!allowed)return;if(onSelect)onSelect(detail,next);else setAction(next);}
 function close(){selected.current=null;setAction(null);onClose?.();}
 return <><ResourceState {...resource}/>{detail&&!resource.loading&&!resource.error&&<p>Güncel yetkili kaynak: <SourceBadge source={detail.item.source}/></p>}{!onClose&&<SubscriberQuickButtons status={detail?.item.status??'UNKNOWN'} onAction={allowed?open:undefined} onHistory={onHistory}/>}{detail&&!resource.loading&&!resource.error&&!allowed&&<p>{legacyActionUnavailableReason(detail.item)??'İşlemler için kalıcı demo deposu, doğrulanmış kaynak ve abone yönetim yetkisi gerekli.'}</p>}
 {selected.current&&action&&<QuickActions rows={[selected.current.item]} today={today} initialAction={action} onClose={close}/>} {onClose&&!allowed&&<button className="button-secondary" onClick={onClose}>Kapat</button>}</>;
}
