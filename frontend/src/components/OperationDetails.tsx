import { useEffect, useRef } from 'react';
import type { DailyOperation } from '../lib/dailySummary';
import { historyValues, operationLabel } from '../lib/subscriberHistory';
import { detailText } from '../lib/subscriberObservation';
import { Facts, dateTime } from './Resource';
import { SourceBadge } from './Status';

export function OperationDetails({event,onClose,onSubscriber,onRouter,onHistory,onAlarms,onReport}:{event:DailyOperation&{workspace?:boolean};onClose:()=>void;onSubscriber:(id:string)=>void;onRouter?:()=>void;onHistory?:()=>void;onAlarms?:()=>void;onReport?:()=>void}) {
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
    {event.workspace&&<p>Kalıcı sentetik çalışma alanı kaydıdır. İşlem geçmişi bu abonenin kendi kaynağında açılır; eski demo audit raporuyla birleştirilmez.</p>}
    <Facts items={[
      ['İşlem UUID / audit kimliği',detailText(event.request_id??(event.workspace?null:event.id))],['İşlem revizyonu',event.revision??'Bu kayıtta belirtilmemiş'],['Audit sonucu',event.audit_result==='APPLIED'?'Uygulandı · Kaydedilmiş audit':event.audit_result==='FAILED'?'Başarısız · Kayıt değiştirilmedi':'Bu kayıtta belirtilmemiş; başarı varsayılmaz'],['İlgili router ID',detailText(event.router_id)],
      ['İşlem',event.operation==='CREATE'&&event.access_type==='HOTSPOT'?'Hotspot abonesi oluşturma (demo)':operationLabel(event.operation)],['Abone',detailText(event.customer_name)],
      ['Kullanıcı adı',detailText(event.username)],['Router',detailText(event.router_name)],
      ['Erişim türü',event.access_type==='PPPOE'?'PPPoE (sentetik)':event.access_type==='HOTSPOT'?'Hotspot (sentetik)':'Veri yok'],
      ['Yetkili kaynak',<SourceBadge source={event.source}/>],['İşlemi yapan',detailText(event.actor_id)],
      ['Zaman (Türkiye)',dateTime(event.occurred_at)],['Önceki değerler',previous],['Yeni değerler',next],
    ]}/>
    <p>Bu bilgiler işlem anına aittir. Güncel abonelik revizyonu ve hesap durumu abone detayında ayrıca okunur; audit kaydı belirsiz bir isteğin uzlaştırılması yerine geçmez.</p>
    <div className="expiry-editor-actions"><button className="button-secondary" onClick={onClose}>Kapat</button><button className="button-primary" onClick={()=>{onClose();onSubscriber(event.subscriber_id);}}>Abone detayını aç</button>{onRouter?<button className="button-secondary" onClick={()=>{onClose();onRouter();}}>Router detayını aç</button>:<span>Router bağlantısı yok: kayıt bağı doğrulanamadı.</span>}{onHistory&&<button className="button-secondary" onClick={()=>{onClose();onHistory();}}>İşlem geçmişini aç</button>}{onAlarms&&<button className="button-secondary" onClick={()=>{onClose();onAlarms();}}>Router alarmlarını aç</button>}{onReport&&<button className="button-secondary" onClick={()=>{onClose();onReport();}}>İlgili operasyon raporunu aç</button>}</div>
  </dialog>;
}
