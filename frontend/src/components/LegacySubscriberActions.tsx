import {useState} from 'react';
import type {SubscriberDetailData} from '../lib/api';
import {canChangeLegacy} from '../lib/subscriberActions';
import {useResource} from '../lib/useResource';
import {useTurkeyToday} from '../lib/useTurkeyToday';
import {QuickActions,type QuickAction} from './QuickActions';
import {ResourceState} from './Resource';

export function LegacySubscriberActions({id}:{id:string}){
 const resource=useResource<SubscriberDetailData>('/subscribers/'+encodeURIComponent(id),undefined,['/subscribers']);
 const [action,setAction]=useState<QuickAction|null>(null);
 const today=useTurkeyToday(),detail=resource.data;
 const allowed=!!detail&&!resource.loading&&!resource.error&&canChangeLegacy(detail,id);
 return <><ResourceState {...resource}/>{allowed&&<button className="button-primary" aria-label="Abone hızlı işlemlerini aç" onClick={()=>setAction('EXTEND')}>Hızlı İşlemler</button>}{detail&&!resource.loading&&!resource.error&&!allowed&&<p>İşlemler için kalıcı demo deposu, doğrulanmış kaynak ve abone yönetim yetkisi gerekli.</p>}
 {allowed&&action&&<QuickActions rows={[detail.item]} today={today} initialAction={action} onClose={()=>setAction(null)}/>}</>;
}
