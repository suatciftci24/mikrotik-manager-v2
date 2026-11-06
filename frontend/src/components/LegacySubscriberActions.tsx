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
 return <><ResourceState {...resource}/>{allowed&&<div className="expiry-editor-actions" aria-label="Mevcut demo abone işlemleri">
 <button className="button-primary" onClick={()=>setAction('EXTEND')}>Abonelik Süresini Uzat</button>
 <button className="button-secondary" onClick={()=>setAction('PLAN')}>Paket değiştir</button>
 <button className="button-secondary" onClick={()=>setAction('STATUS')}>Aktif / Pasif</button>
 </div>}{detail&&!resource.loading&&!resource.error&&!allowed&&<p>İşlemler için kalıcı demo deposu, doğrulanmış kaynak ve abone yönetim yetkisi gerekli.</p>}
 {allowed&&action&&<QuickActions rows={[detail.item]} today={today} initialAction={action} onClose={()=>setAction(null)}/>}</>;
}
