import { useState } from 'react';
import type { Subscriber } from '../lib/api';
import { expiryDate, turkeyToday } from '../lib/expiry';
import { detailText, subscriberObservation } from '../lib/subscriberObservation';
import { subscriberReportData, bytesText } from '../lib/subscriberReports';
import type { ReportPeriod } from '../lib/subscriberReports';
import { DetailSection, Facts, dateTime } from './Resource';
import { SourceBadge } from './Status';

/** Only persisted synthetic report samples supply usage and session evidence. */
export function SubscriberReports({subscriber,today}: {subscriber:Subscriber;today:string}) {
  try { subscriberReportData(subscriber,today); }
  catch(error){return <DetailSection title="Kullanım ve bağlantı raporları"><p role="alert">{error instanceof Error?error.message:'Demo raporu okunamadı.'}</p></DetailSection>;}
  return <SubscriberReportContent subscriber={subscriber} today={today}/>;
}
function SubscriberReportContent({subscriber, today}: {subscriber: Subscriber; today: string}) {
  const [period, setPeriod] = useState<ReportPeriod>('TODAY');
  const observation = subscriberObservation(subscriber);
  const report = subscriberReportData(subscriber,today);
  const periods = report.periods;
  const latest = [...report.sessions].filter(session=>session.started_at).sort((a,b)=>Date.parse(b.started_at!)-Date.parse(a.started_at!))[0];
  const selected = periods.find(item=>item.id===period)!;
  const history = report.sessions.filter(session=>session.started_at && turkeyToday(new Date(session.started_at))>=selected.start && turkeyToday(new Date(session.started_at))<=selected.end);
  const range = `${expiryDate(selected.start)} – ${expiryDate(selected.end)}`;
  return <>
    <DetailSection title="Kullanım ve bağlantı raporları">
      <p><span className="demo-chip">SENTETİK</span> Mevcut V2 demo kayıtları · canlı router/RADIUS telemetrisi değildir.</p>
      <Facts items={[
        ['Abone',`${detailText(subscriber.customer_name)} · ${detailText(subscriber.username)}`],
        ['Router',detailText(subscriber.router_name)], ['Yetkili kaynak',<SourceBadge source={subscriber.source}/>],
      ]}/>
      <div className="subscriber-report-periods" role="group" aria-label="Rapor dönemi">
        {periods.map(item=><button key={item.id} type="button" className={period===item.id?'button-primary':'button-secondary'} aria-pressed={period===item.id} onClick={()=>setPeriod(item.id)}>{item.label}</button>)}
      </div>
      <p role="status">Seçili dönem: {selected.label} · {range}. Europe/Istanbul; başlangıç ve bitiş günleri dahil, bugün şu ana kadar.</p>
      <h3>Bağlantı özeti</h3>
      <Facts items={[
        ['Oturum bağlantı durumu',latest?latest.state==='ACTIVE'?'Aktif (sentetik kayıt)':latest.state==='CLOSED'?'Kapalı (sentetik kayıt)':'Bilinmiyor':'Veri yok'], ['Oturum başlangıcı',latest?.started_at?dateTime(latest.started_at):'Veri yok'],
        ['Oturum bitişi',latest?.ended_at?dateTime(latest.ended_at):'Veri yok'], ['Bağlantı süresi',latest?.duration!==null&&latest?.duration!==undefined?`${latest.duration} sn`:'Veri yok'],
        ['Demo IP kaydı',observation.ip],
        ['Son görülme (sentetik envanter)',observation.last_seen?dateTime(observation.last_seen):'Veri yok'],
      ]}/>
      <p>Son görülme ve IP dönemden bağımsız envanter bilgileridir; oturum başlangıcı, canlı erişim veya çevrimiçi oturum kanıtı değildir. Hesap etkinliği bağlantı durumu değildir.</p>
      <h3>Seçili dönemde bağlantı geçmişi</h3>
      {history.length>0&&<ul className="subscriber-history">{history.map(session=><li key={session.id}><strong>{session.state==='ACTIVE'?'Aktif demo oturum kaydı':session.state==='CLOSED'?'Kapalı demo oturum kaydı':'Bilinmiyor'}</strong><span>{dateTime(session.started_at)} → {session.ended_at?dateTime(session.ended_at):'Veri yok'} · {session.duration===null?'Veri yok':session.duration+' sn'}</span></li>)}</ul>}
      {!history.length&&<p className="missing-data">Veri yok. Aboneye ait oturum başlangıç/bitiş kayıtları mevcut demo API’sinde bulunmuyor; bağlantı sayısı ve süresi hesaplanamaz. Yönetim işlem geçmişi bağlantı geçmişi sayılmaz.</p>}
    </DetailSection>
    <DetailSection title="Abone trafik kullanımı">
      <p>Türkiye takvimine göre dönem özeti. Tüm indirme/yükleme/toplam alanları aynı veri birimiyle gösterilir; yalnız kaydedilmiş sentetik bayt ölçümleri toplanır. Rakamlar dönem içindeki mevcut örneklerin toplamıdır; tam dönem kapsaması veya canlı kullanım iddiası değildir.</p>
      <div className="table-scroll"><table className="data-table subscriber-traffic-table">
        <caption>Sentetik abone · kayıtlı trafik örnekleri · MiB (1 MiB = 1.048.576 bayt)</caption>
        <thead><tr><th scope="col">DÖNEM</th><th scope="col">İNDİRME</th><th scope="col">YÜKLEME</th><th scope="col">TOPLAM</th></tr></thead>
        <tbody>{periods.map(item=><tr key={item.id} aria-current={item.id===period?'true':undefined}><th scope="row">{item.label}<small className="subscriber-report-range">{expiryDate(item.start)} – {expiryDate(item.end)}{item.id===period?' · Seçili dönem':''}</small></th><td>{bytesText(item.download)}</td><td>{bytesText(item.upload)}</td><td>{bytesText(item.total)}</td></tr>)}</tbody>
      </table></div>
      <h3>Seçili dönemde ölçüm geçmişi</h3>
      {report.traffic.filter(sample=>{const day=turkeyToday(new Date(sample.measured_at));return day>=selected.start&&day<=selected.end;}).map(sample=><p key={sample.id}>{dateTime(sample.measured_at)} · İndirme {bytesText(sample.download_bytes)} · Yükleme {bytesText(sample.upload_bytes)}</p>)}
      {selected.total===null&&<p className="missing-data">Veri yok. Zamanlı indirme/yükleme ölçümü veya sayaç kaynağı bulunmadığından {selected.label.toLocaleLowerCase('tr-TR')} için toplam hesaplanamaz. Bu, sıfır kullanım anlamına gelmez.</p>}
      <p>Rapor kayıt zamanı: {report.recorded_at?dateTime(report.recorded_at):'Veri yok'}. Aktif demo kaydı canlı bağlantı kanıtı değildir.</p>
      <p>Paket hızı, aylık tutar, router toplamları veya genel demo grafiklerinden abone trafiği üretilmez. Eksik ölçümlere birim veya sayısal değer atanmaz.</p>
    </DetailSection>
  </>;
}
