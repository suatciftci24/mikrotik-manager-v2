import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Download, Upload, Users, Router as RouterIcon } from 'lucide-react';
import { useResource } from '../lib/useResource';
import { loadManagementReport, reportRouterId } from '../lib/managementReport';
import { buildInternetReport, internetFilterFromHash, internetPeriods, internetReportHash, volumeGB } from '../lib/internetReport';
import type { InternetFilter } from '../lib/internetReport';
import { PageHeading } from '../components/PageHeading';
import { ResourceState, dateTime } from '../components/Resource';
import { MetricCard, SourceBadge, StatusBadge } from '../components/Status';
import { VolumeTrend } from '../components/VolumeTrend';
import { AlarmEventDetails } from '../components/AlarmEvents';
import { eventLabels, durationText } from '../lib/routerEvents';
import type { AlarmEvent } from '../lib/routerEvents';
import { expiryDate } from '../lib/expiry';
const dependencies=['/routers','/subscribers','/router-events'] as const;
const detailLink=(kind:'routers'|'subscribers',id:string)=>'#'+new URLSearchParams({module:kind,id}).toString();
export function InternetReport(){
  const resource=useResource('/reports/internet',loadManagementReport,dependencies);
  const [filter,setFilter]=useState(()=>internetFilterFromHash(typeof window==='undefined'?'':window.location.hash));
  const [now,setNow]=useState(()=>new Date());
  const [selected,setSelected]=useState<AlarmEvent|null>(null);
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{
    heading.current?.focus();const tick=()=>setNow(new Date());const read=()=>{setFilter(internetFilterFromHash(window.location.hash));setSelected(null);};
    const timer=window.setInterval(tick,30000);window.addEventListener('hashchange',read);window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);
    return()=>{window.clearInterval(timer);window.removeEventListener('hashchange',read);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};
  },[]);
  const change=(next:InternetFilter)=>{setFilter(next);setSelected(null);window.history.replaceState(null,'',window.location.pathname+window.location.search+internetReportHash(next));};
  let report:ReturnType<typeof buildInternetReport>|undefined,error=resource.error;
  try{if(resource.data)report=buildInternetReport(resource.data,filter,now);}catch(failure){error=failure instanceof Error?failure.message:'Kullanım raporu oluşturulamadı.';}
  const names=new Map(resource.data?.routers.map(router=>[router.id,router.name])??[]);
  const choices=resource.data?.details.filter(detail=>!filter.router||reportRouterId(detail.item,resource.data!.routers)===filter.router)??[];
  return <div className="screen-stack internet-report">
    <PageHeading title="Merkezi İnternet Kullanım ve Bağlantı Raporları" eyebrow="SENTETİK DEMO · EUROPE/ISTANBUL" description="Mevcut V2 kayıtlarından hacim, oturum ve bağlantı olayları; canlı router/RADIUS telemetrisi değildir." headingRef={heading} actions={<button className="button-secondary" disabled={resource.loading} onClick={()=>{setSelected(null);resource.retry();}}><RefreshCw size={16}/>Raporu yenile</button>}/>
    <section className="panel central-events"><div className="router-report-controls">
      <label className="form-label">Dönem<select value={filter.period} onChange={e=>change({...filter,period:e.target.value as InternetFilter['period']})}>{Object.entries(internetPeriods).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label className="form-label">Router<select value={filter.router} onChange={e=>change({...filter,router:e.target.value})}><option value="">Tüm routerlar</option>{resource.data?.routers.map(router=><option key={router.id} value={router.id}>{router.name}</option>)}{filter.router&&!names.has(filter.router)&&<option value={filter.router}>{filter.router} · kayıt bulunamadı</option>}</select></label>
      <label className="form-label">PPPoE / demo abone<select value={filter.subscriber} onChange={e=>change({...filter,subscriber:e.target.value})}><option value="">Tüm aboneler</option>{choices.map(({item})=><option key={item.id} value={item.id}>{item.customer_name} · {item.username}</option>)}{filter.subscriber&&!choices.some(detail=>detail.item.id===filter.subscriber)&&<option value={filter.subscriber}>{filter.subscriber} · seçili router kapsamında yok</option>}</select></label>
      <button className="button-secondary" onClick={()=>change({period:'TODAY',router:'',subscriber:''})}>Filtreleri temizle</button>
    </div><p>Dönem hacimleri yalnız kaydedilmiş bayt örneklerinin toplamıdır; ölçülmeyen abone/zaman için kullanım tahmin edilmez. Router WAN sayacı ile abone örnekleri aynı ölçüm değildir. Hız ölçümü yok; GB hacim ile Mbps hız arasında dönüşüm yapılmaz.</p></section>
    <ResourceState {...resource} error={error}/>
    {report&&!resource.loading&&!error&&<>
      <p role="status" className="daily-description">{internetPeriods[filter.period]} · {expiryDate(report.range.start)} – {expiryDate(report.range.end)} · Türkiye takvim günleri dahil. Veri okuması: {resource.data?.read_at?dateTime(resource.data.read_at):'Veri yok'}.</p>
      <div className="metric-grid">
        <MetricCard title="Kayıtlı indirme hacmi" value={volumeGB(report.totals.download)} note="Yalnız mevcut örnekler · 1 GB = 1.000.000.000 bayt" icon={<Download size={18}/>}/>
        <MetricCard title="Kayıtlı yükleme / toplam" value={volumeGB(report.totals.upload)} note={`Toplam ${volumeGB(report.totals.total)}`} icon={<Upload size={18}/>}/>
        <MetricCard title="Dönem örneği olan abone" value={`${report.measured_subscribers} / ${report.subscribers.length}`} note="Örneği olmayan abonelerin kullanımı bilinmiyor" icon={<Users size={18}/>}/>
        <MetricCard title="Router / oturum kaydı" value={`${report.routers.length} / ${report.session_count===null?'Veri yok':report.session_count}`} note={`Oturum kaynağı ${report.source_subscribers} / ${report.subscribers.length} abone · aktif internet kanıtı değildir`} icon={<RouterIcon size={18}/>}/>
      </div>
      <section className="panel central-events"><h2>Dönemsel indirme ve yükleme eğilimi</h2><p>Seçili abonelerin kayıtlı örnekleri; tam dönem veya tüm ağ/WAN trafiği değildir. Bugün/Dün saatlik, diğer dönemler günlük gruplanır. Kesintisiz çizgi veya boş aralıkta sıfır üretilmez.</p><VolumeTrend buckets={report.buckets}/>
      <details><summary>Grafik verilerini tablo olarak göster</summary><div className="table-scroll" tabIndex={0} role="region" aria-label="Hacim grafiği veri tablosu"><table className="data-table"><thead><tr><th>ARALIK</th><th>İNDİRME · GB</th><th>YÜKLEME · GB</th><th>TOPLAM · GB</th><th>ÖRNEK</th></tr></thead><tbody>{report.buckets.map(bucket=><tr key={bucket.from}><th scope="row">{bucket.label}</th><td>{volumeGB(bucket.download)}</td><td>{volumeGB(bucket.upload)}</td><td>{volumeGB(bucket.total)}</td><td>{bucket.samples||'Veri yok'}</td></tr>)}</tbody></table></div></details></section>
      <section className="panel central-events"><h2>Router WAN ve bağlantı kapsamı</h2><p>Durum son sentetik envanter kaydıdır; son görülme internet erişimini doğrulamaz. Mevcut veri modelinde WAN trafik ölçümü yok; abone örnekleri WAN hacmine dönüştürülmez.</p>{report.routers.length?<div className="table-scroll" tabIndex={0} role="region" aria-label="Router WAN raporu tablosu"><table className="data-table"><thead><tr><th>ROUTER</th><th>SON DURUM KAYDI</th><th>WAN İNDİRME</th><th>WAN YÜKLEME</th><th>DÖNEMİN BAĞLANTI OLAYLARI</th></tr></thead><tbody>{report.routers.map(row=><tr key={row.router.id}><td><a className="record-link" href={detailLink('routers',row.router.id)}>{row.router.name}</a></td><td><StatusBadge status={row.status}/></td><td>{volumeGB(row.wan_download)}</td><td>{volumeGB(row.wan_upload)}</td><td>{row.events===null?'Veri yok':row.events.length?row.events.map(event=><div key={event.id}><button className="record-link" onClick={()=>setSelected(event)}>{eventLabels[event.kind]} · {event.started_at?dateTime(event.started_at):'Veri yok'}{event.recovery_id&&event.ended_at?' → '+dateTime(event.ended_at):''}</button></div>):'Veri yok'}</td></tr>)}</tbody></table></div>:<p className="missing-data">Veri yok. Filtrelerle eşleşen router bulunmuyor.</p>}</section>
      <section className="panel central-events"><h2>Abone kullanım özeti</h2><p>PPPoE olarak kayıtlı ve erişim türü belirtilmemiş eski demo kayıtları ayrı etiketlidir. Ölçümü olmayan aboneye sıfır atanmaz; üstteki hacim yalnız kayıtlı örnekleri kapsar.</p>{report.subscribers.length?<div className="table-scroll" tabIndex={0} role="region" aria-label="Abone kullanım raporu tablosu"><table className="data-table"><thead><tr><th>ABONE</th><th>ROUTER / KAYNAK</th><th>ERİŞİM TÜRÜ</th><th>İNDİRME</th><th>YÜKLEME</th><th>TOPLAM</th></tr></thead><tbody>{report.subscribers.map(row=><tr key={row.item.id}><td><a className="record-link" href={detailLink('subscribers',row.item.id)}>{row.item.customer_name} · {row.item.username}</a></td><td>{row.router_id?<a className="record-link" href={detailLink('routers',row.router_id)}>{names.get(row.router_id)}</a>:row.item.router_name||'Veri yok'} · <SourceBadge source={row.item.source}/></td><td>{row.item.access_type==='PPPOE'?'PPPoE (sentetik)':'Veri yok · eski kayıt'}</td><td>{volumeGB(row.totals.download)}</td><td>{volumeGB(row.totals.upload)}</td><td>{volumeGB(row.totals.total)}</td></tr>)}</tbody></table></div>:<p className="missing-data">Veri yok. Router ve abone filtreleriyle eşleşen kayıt yok.</p>}</section>
      <section className="panel central-events"><h2>Oturum geçmişi</h2><p>Dönemle kesişen kayıtlar gösterilir. Süre tüm kapalı oturumun doğrulanmış başlangıç/bitiş farkıdır; açık oturum veya eksik zamanda süre tahmin edilmez.</p>{report.sessions.length?<div className="table-scroll" tabIndex={0} role="region" aria-label="Abone oturum geçmişi tablosu"><table className="data-table"><thead><tr><th>ABONE</th><th>BAŞLANGIÇ</th><th>BİTİŞ</th><th>TAM OTURUM SÜRESİ</th><th>DEMO DURUM KAYDI</th></tr></thead><tbody>{report.sessions.map(session=><tr key={session.id}><td><a className="record-link" href={detailLink('subscribers',session.subscriber_id)}>{session.customer_name}</a></td><td>{dateTime(session.started_at)}</td><td>{session.ended_at?dateTime(session.ended_at):'Veri yok'}</td><td>{durationText(session.duration)}</td><td>{session.state==='ACTIVE'?'Aktif (sentetik snapshot)':session.state==='CLOSED'?'Kapalı (sentetik)':'Bilinmiyor'}</td></tr>)}</tbody></table></div>:<p className="missing-data">Veri yok. Seçili dönemde gösterilecek oturum kaydı bulunmuyor.</p>}</section>
    </>}
    {selected&&<AlarmEventDetails event={selected} routerName={names.get(selected.router_id)??selected.router_id} onClose={()=>setSelected(null)}/>}
  </div>;
}
