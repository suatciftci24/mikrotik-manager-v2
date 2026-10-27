import { useState } from 'react';
import type { Subscriber } from '../lib/api';
import { expiryDate } from '../lib/expiry';
import { detailText, subscriberObservation } from '../lib/subscriberObservation';
import { subscriberReportPeriods } from '../lib/subscriberReports';
import type { ReportPeriod } from '../lib/subscriberReports';
import { DetailSection, Facts, dateTime } from './Resource';
import { SourceBadge } from './Status';

/** The current subscriber API supplies inventory observations, not telemetry.
 * Keep unavailable measurements absent until a documented subscriber source exists.
 */
export function SubscriberReports({subscriber, today}: {subscriber: Subscriber; today: string}) {
  const [period, setPeriod] = useState<ReportPeriod>('TODAY');
  const observation = subscriberObservation(subscriber);
  const periods = subscriberReportPeriods(today);
  const selected = periods.find(item=>item.id===period)!;
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
        ['Oturum bağlantı durumu','Veri yok'], ['Oturum başlangıcı','Veri yok'],
        ['Oturum bitişi','Veri yok'], ['Bağlantı süresi','Veri yok'],
        ['Demo IP kaydı',observation.ip],
        ['Son görülme (sentetik envanter)',observation.last_seen?dateTime(observation.last_seen):'Veri yok'],
      ]}/>
      <p>Son görülme ve IP dönemden bağımsız envanter bilgileridir; oturum başlangıcı, canlı erişim veya çevrimiçi oturum kanıtı değildir. Hesap etkinliği bağlantı durumu değildir.</p>
      <h3>Seçili dönemde bağlantı geçmişi</h3>
      <p className="missing-data">Veri yok. Aboneye ait oturum başlangıç/bitiş kayıtları mevcut demo API’sinde bulunmuyor; bağlantı sayısı ve süresi hesaplanamaz. Yönetim işlem geçmişi bağlantı geçmişi sayılmaz.</p>
    </DetailSection>
    <DetailSection title="Abone trafik kullanımı">
      <p>Türkiye takvimine göre dönem özeti. Tüm indirme/yükleme/toplam alanları aynı veri birimiyle gösterilir; mevcut API’de aboneye ait bayt ölçümü yoktur.</p>
      <div className="table-scroll"><table className="data-table subscriber-traffic-table">
        <caption>Sentetik abone · trafik ölçümü bulunmuyor · dönemler dahil</caption>
        <thead><tr><th scope="col">DÖNEM</th><th scope="col">İNDİRME</th><th scope="col">YÜKLEME</th><th scope="col">TOPLAM</th></tr></thead>
        <tbody>{periods.map(item=><tr key={item.id} aria-current={item.id===period?'true':undefined}><th scope="row">{item.label}<small className="subscriber-report-range">{expiryDate(item.start)} – {expiryDate(item.end)}{item.id===period?' · Seçili dönem':''}</small></th><td>Veri yok</td><td>Veri yok</td><td>Veri yok</td></tr>)}</tbody>
      </table></div>
      <h3>Seçili dönemde ölçüm geçmişi</h3>
      <p className="missing-data">Veri yok. Zamanlı indirme/yükleme ölçümü veya sayaç kaynağı bulunmadığından {selected.label.toLocaleLowerCase('tr-TR')} için toplam hesaplanamaz. Bu, sıfır kullanım anlamına gelmez.</p>
      <p>Paket hızı, aylık tutar, router toplamları veya genel demo grafiklerinden abone trafiği üretilmez. Eksik ölçümlere birim veya sayısal değer atanmaz.</p>
    </DetailSection>
  </>;
}
