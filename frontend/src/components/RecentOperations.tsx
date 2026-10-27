import { useEffect, useMemo, useState } from 'react';
import type { DailySummary } from '../lib/dailySummary';
import { buildOperationWindow } from '../lib/operationWindow';
import { operationLabel } from '../lib/subscriberHistory';
import { dateTime } from './Resource';
import { OperationDetails } from './OperationDetails';

export function RecentOperations({data,onSubscriber}:{data:DailySummary;onSubscriber:(id:string)=>void}) {
  const [now,setNow]=useState(()=>new Date());
  const [selected,setSelected]=useState<string|null>(null);
  useEffect(()=>{
    const tick=()=>setNow(new Date());
    const timer=window.setInterval(tick,30000);
    window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);
    return()=>{window.clearInterval(timer);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};
  },[]);
  const windowData=useMemo(()=>buildOperationWindow(data.operation_history,now),[data.operation_history,now]);
  // Look up the current saved event, even if it ages out of the rolling window while open.
  const event=selected?data.operation_history.find(item=>item.id===selected):undefined;
  return <section className="panel recent-operations" aria-labelledby="recent-operations-title">
    <div className="panel-title"><h2 id="recent-operations-title">Son 24 saat PPPoE demo yönetim işlemleri</h2><span className="demo-chip">SENTETİK</span></div>
    <p className="daily-description">Mevcut demo abone işlem geçmişi esas alınır; erişim türü belirtilmemiş eski kayıtlar dahildir. Takvim günü sayımı ayrıdır: bugün (Türkiye) {data.operations.today} işlem.</p>
    <p className="daily-description">Aralık: {dateTime(windowData.from)} → {dateTime(windowData.to)} (başlangıç dahil). Son kayıt okuması: {dateTime(data.generated_at)}.</p>
    <dl className="operation-counts">
      {([['Oluşturma',windowData.counts.create],['Paket/profil değiştirme',windowData.counts.plan],['Durum değiştirme',windowData.counts.status],['Abonelik yenileme',windowData.counts.renewal]] as const).map(([label,count])=><div key={label}><dt>{label}</dt><dd>{count}</dd></div>)}
    </dl>
    <p className="daily-description">Toplam {windowData.counts.total} işlem · {windowData.affected.length} etkilenen abone · Bitiş tarihi düzenleme: {windowData.counts.date_edit} (yenilemeden ayrı).</p>
    {windowData.events.length?<>
      <div className="affected-subscribers" aria-label="Son 24 saatte etkilenen aboneler">{windowData.affected.map(item=><button key={item.id} className="button-secondary" onClick={()=>onSubscriber(item.id)}>{item.name} · {item.router_name}</button>)}</div>
      <ol className="daily-operations rolling-operations">{windowData.events.map(item=><li key={item.id}>
        <button className="record-link" onClick={()=>setSelected(item.id)} aria-label={`${item.customer_name} · ${operationLabel(item.operation)} işlem detayını aç`}>{item.customer_name} · {operationLabel(item.operation)}</button>
        <span>{item.router_name} · İşlemi yapan: {item.actor_id||'Veri yok'}</span>
        <time dateTime={item.occurred_at}>{dateTime(item.occurred_at)}</time>
      </li>)}</ol>
    </>:<p className="missing-data">Veri yok. Son 24 saatte kaydedilmiş demo abone işlemi bulunmuyor.</p>}
    {event&&<OperationDetails event={event} onClose={()=>setSelected(null)} onSubscriber={onSubscriber}/>}
  </section>;
}
