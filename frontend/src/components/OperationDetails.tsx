import { useEffect, useRef } from 'react';
import type { DailyOperation } from '../lib/dailySummary';
import { historyValues, operationLabel } from '../lib/subscriberHistory';
import { detailText } from '../lib/subscriberObservation';
import { Facts, dateTime } from './Resource';
import { SourceBadge } from './Status';

export function OperationDetails({event,onClose,onSubscriber}:{event:DailyOperation;onClose:()=>void;onSubscriber:(id:string)=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    const origin=document.activeElement as HTMLElement|null;
    const node=dialog.current;node?.showModal();
    return()=>{node?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};
  },[]);
  const [previous,next]=historyValues(event);
  return <dialog ref={dialog} className="expiry-dialog operation-dialog" aria-labelledby="operation-detail-title" onCancel={e=>{e.preventDefault();onClose();}}>
    <h2 id="operation-detail-title">Demo işlem detayı</h2>
    <p><span className="demo-chip">SENTETİK</span> Kaydedilmiş V2 demo işlemi. Router veya RADIUS üzerinde gerçek işlem yapılmadı.</p>
    <Facts items={[
      ['İşlem',operationLabel(event.operation)],['Abone',detailText(event.customer_name)],
      ['Kullanıcı adı',detailText(event.username)],['Router',detailText(event.router_name)],
      ['Erişim türü',event.access_type==='PPPOE'?'PPPoE (sentetik)':'Veri yok'],
      ['Yetkili kaynak',<SourceBadge source={event.source}/>],['İşlemi yapan',detailText(event.actor_id)],
      ['Zaman (Türkiye)',dateTime(event.occurred_at)],['Önceki değerler',previous],['Yeni değerler',next],
    ]}/>
    <div className="expiry-editor-actions"><button className="button-secondary" onClick={onClose}>Kapat</button><button className="button-primary" onClick={()=>{onClose();onSubscriber(event.subscriber_id);}}>Abone detayını aç</button></div>
  </dialog>;
}
