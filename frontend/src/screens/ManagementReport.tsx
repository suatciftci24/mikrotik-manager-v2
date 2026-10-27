import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, RefreshCw, Router as RouterIcon, Users, CalendarClock, AlertTriangle } from 'lucide-react';
import { buildManagementReport, loadManagementReport, managementFilterFromHash, managementReportHash, reportKinds, reportPeriods } from '../lib/managementReport';
import type { ManagementFilter } from '../lib/managementReport';
import { useResource } from '../lib/useResource';
import { PageHeading } from '../components/PageHeading';
import { Facts, ResourceState, dateTime } from '../components/Resource';
import { MetricCard } from '../components/Status';
import { OperationDetails } from '../components/OperationDetails';
import { AlarmEventDetails } from '../components/AlarmEvents';
import { operationLabel } from '../lib/subscriberHistory';
import { eventLabels, durationText } from '../lib/routerEvents';
import type { EventKind } from '../lib/routerEvents';
import { expiryDate } from '../lib/expiry';

const dependencies=['/routers','/subscribers','/router-events'] as const;
const number=(value:number|null)=>value===null?'Veri yok':value.toLocaleString('tr-TR');
const link=(kind:'routers'|'subscribers',id:string)=>'#'+new URLSearchParams({module:kind,id}).toString();
export function ManagementReport({onBack}:{onBack:()=>void}){
  const resource=useResource('/management/report',loadManagementReport,dependencies);
  const [filter,setFilter]=useState(()=>managementFilterFromHash(typeof window==='undefined'?'':window.location.hash));
  const [now,setNow]=useState(()=>new Date());
  const [selected,setSelected]=useState<{kind:'operation'|'event';id:string}|null>(null);
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{
    heading.current?.focus();
    const read=()=>setFilter(managementFilterFromHash(window.location.hash));
    const tick=()=>setNow(new Date());
    const timer=window.setInterval(tick,30000);
    window.addEventListener('hashchange',read);window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);
    return()=>{window.clearInterval(timer);window.removeEventListener('hashchange',read);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};
  },[]);
  const change=(next:ManagementFilter)=>{setFilter(next);setSelected(null);window.history.replaceState(null,'',window.location.pathname+window.location.search+managementReportHash(next));};
  let report:ReturnType<typeof buildManagementReport>|undefined,error=resource.error;
  try{if(resource.data)report=buildManagementReport(resource.data,filter,now);}catch(failure){error=failure instanceof Error?failure.message:'Rapor oluşturulamadı.';}
  const names=new Map(resource.data?.routers.map(router=>[router.id,router.name])??[]);
  const operation=selected?.kind==='operation'?report?.operations.find(event=>event.id===selected.id):undefined;
  const event=selected?.kind==='event'?report?.events?.find(event=>event.id===selected.id):undefined;
  return <div className="screen-stack management-report">
    <button className="button-secondary detail-back" onClick={onBack}><ArrowLeft size={16}/>Dashboard’a dön</button>
    <PageHeading title="Merkezi Günlük Yönetim Raporu" eyebrow="SENTETİK DEMO · EUROPE/ISTANBUL" description="Kaydedilmiş V2 envanteri, yönetim işlemleri ve bağlantı olayları. Canlı telemetri değildir." headingRef={heading} actions={<button className="button-secondary" disabled={resource.loading} onClick={()=>{setSelected(null);resource.retry();}}><RefreshCw size={16}/>Raporu yenile</button>}/>
    <section className="panel central-events"><div className="router-report-controls">
      <label className="form-label">Dönem<select value={filter.period} onChange={e=>change({...filter,period:e.target.value as ManagementFilter['period']})}>{Object.entries(reportPeriods).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label className="form-label">Router<select value={filter.router} onChange={e=>change({...filter,router:e.target.value})}><option value="">Tüm routerlar</option>{resource.data?.routers.map(router=><option key={router.id} value={router.id}>{router.name}</option>)}{filter.router&&!names.has(filter.router)&&<option value={filter.router}>{filter.router} · kayıt bulunamadı</option>}</select></label>
      <label className="form-label">İşlem / olay<select value={filter.kind} onChange={e=>change({...filter,kind:e.target.value as ManagementFilter['kind']})}>{Object.entries(reportKinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <button className="button-secondary" onClick={()=>change({period:'TODAY',router:'',kind:'ALL'})}>Filtreleri temizle</button>
    </div><p>Dönem ve olay filtresi yalnız zamanlı işlem/olay listelerine uygulanır. Envanter, hesap ve abonelik sayaçları router filtresi kapsamındaki son kayıtlı durumu gösterir; geçmişe ait durum tahmini değildir.</p></section>
    <ResourceState {...resource} error={error}/>
    {report&&!resource.loading&&!error&&<>
      <p role="status" className="daily-description">{reportPeriods[filter.period]}: {expiryDate(report.range.start)} – {expiryDate(report.range.end)} · Türkiye günleri dahil, gelecek kayıtlar hariç. Veri okuması: {resource.data?.read_at?dateTime(resource.data.read_at):'Veri yok'}.</p>
      <h2>Son kayıtlı envanter ve abonelik durumu</h2>
      <div className="metric-grid">
        <MetricCard title="Toplam router" value={number(report.inventory.router_counts.total)} note={`Online ${number(report.inventory.router_counts.online)} · Offline ${number(report.inventory.router_counts.offline)} · Dikkat ${number(report.inventory.router_counts.degraded)} · Bilinmiyor ${number(report.inventory.router_counts.unknown)}`} icon={<RouterIcon size={18}/>}/>
        <MetricCard title="Toplam abonelik" value={number(report.inventory.subscribers.total)} note={`PPPoE kayıtlı ${number(report.inventory.pppoe.confirmed)} · türü belirtilmemiş ${number(report.inventory.pppoe.untyped)}`} icon={<Users size={18}/>}/>
        <MetricCard title="Aktif / pasif hesap" value={`${number(report.inventory.subscribers.active)} / ${number(report.inventory.subscribers.paused)}`} note={`Bekliyor ${number(report.inventory.subscribers.pending)} · aktif hesap online oturum değildir`} icon={<Users size={18}/>}/>
        <MetricCard title="Süresi dolmuş / yaklaşan" value={`${number(report.inventory.expiry.expired)} / ${number(report.inventory.expiry.within_7)}`} note={`Yaklaşan: bugün dahil 7 gün · 30 günde ${number(report.inventory.expiry.within_30)} · bitiş bilinmiyor ${number(report.inventory.expiry.unknown)}`} icon={<CalendarClock size={18}/>}/>
      </div>
      <section className="panel central-events"><h2>Seçili dönemin işlem ve olay toplamları</h2><Facts items={[
        ['Yönetim işlemleri',number(report.counts.operations)],['Tekil olay kayıtları',number(report.counts.events)],['İnternet kesintileri',number(report.counts.outages)],['Bağlantı geri gelmesi',number(report.counts.recoveries)],['WAN değişiklikleri',number(report.counts.wan)],
      ]}/><p>Kesinti ve geri gelme ayrı kayıt türleridir; aynı kesinti yaşam döngüsü iki kesinti sayılmaz. Kesinti nedeni için Veri yok; doğrulanmış zaman çifti bulunmadığında süre hesaplanmaz.</p>
      {(report.undated.operations>0||(report.undated.events??0)>0)&&<p>Zamanı doğrulanamayan kayıtlar dönem toplamından çıkarıldı: işlem {number(report.undated.operations)}, olay {number(report.undated.events)}.</p>}</section>
      <section className="panel central-events"><h2>Yönetim işlemleri</h2>{report.operations.length?<div className="table-scroll" role="region" tabIndex={0} aria-label="Günlük yönetim işlemleri tablosu"><table className="data-table"><thead><tr><th>İŞLEM</th><th>ABONE</th><th>ROUTER</th><th>ZAMAN · TÜRKİYE</th></tr></thead><tbody>{report.operations.map(item=><tr key={item.id}><td><button className="record-link" onClick={()=>setSelected({kind:'operation',id:item.id})}>{operationLabel(item.operation)}</button></td><td><a className="record-link" href={link('subscribers',item.subscriber_id)}>{item.customer_name||item.username||item.subscriber_id}</a></td><td>{item.router_id?<a className="record-link" href={link('routers',item.router_id)}>{names.get(item.router_id)??item.router_name}</a>:item.router_name||'Veri yok'}</td><td>{dateTime(item.occurred_at)}</td></tr>)}</tbody></table></div>:<p className="missing-data">Veri yok. Filtrelerle eşleşen kayıtlı yönetim işlemi yok.</p>}</section>
      <section className="panel central-events"><h2>Bağlantı, internet ve WAN olayları</h2>{report.events===null?<p className="missing-data">Veri yok. Kaydedilmiş olay kaynağı yok; olay sayısı sıfır kabul edilmez.</p>:report.events.length?<div className="table-scroll" role="region" tabIndex={0} aria-label="Günlük bağlantı olayları tablosu"><table className="data-table"><thead><tr><th>OLAY</th><th>ROUTER</th><th>ZAMAN · TÜRKİYE</th><th>KESİNTİ SÜRESİ</th></tr></thead><tbody>{report.events.map(item=><tr key={item.id}><td><button className="record-link" onClick={()=>setSelected({kind:'event',id:item.id})}>{eventLabels[item.kind as EventKind]} · {item.id}</button></td><td><a className="record-link" href={link('routers',item.router_id)}>{names.get(item.router_id)??item.router_id}</a></td><td>{dateTime(item.occurred_at)}</td><td>{item.kind==='INTERNET_DOWN'||item.kind==='INTERNET_UP'?durationText(item.lifecycle.duration_seconds):'Veri yok'}</td></tr>)}</tbody></table></div>:<p className="missing-data">Veri yok. Filtrelerle eşleşen kayıtlı bağlantı olayı yok.</p>}</section>
      <p className="screen-footnote"><AlertTriangle size={15}/>Özet, eksik ölçümü sıfır veya son görülmeyi aktif bağlantı kanıtı saymaz. Rapor saati: {dateTime(report.generated_at)}.</p>
    </>}
    {operation&&<OperationDetails event={operation} onClose={()=>setSelected(null)} onSubscriber={id=>{window.location.hash=link('subscribers',id);}}/>}
    {event&&<AlarmEventDetails event={event.lifecycle} routerName={names.get(event.router_id)??event.router_id} onClose={()=>setSelected(null)}/>}
  </div>;
}
