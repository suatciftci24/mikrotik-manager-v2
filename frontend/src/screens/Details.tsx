import { SubscriberReports } from '../components/SubscriberReports';
import { detailText, monthlyPriceText } from '../lib/subscriberObservation';
import { expiryInfo } from '../lib/expiry';
import { SubscriberEditor } from '../components/SubscriberEditor';
import { historyValues, operationLabel } from '../lib/subscriberHistory';
import { ExpiryEditor } from '../components/ExpiryEditor';
import { invalidateResources } from '../lib/resourceEvents';
import { subscriberSource } from '../lib/source';
import { SourceExplanation } from '../components/SourceExplanation';
import { ExpirySummary } from '../components/Expiry';
import { useTurkeyToday } from '../lib/useTurkeyToday';
import { useEffect, useRef, useState } from 'react';
import { PageHeading } from '../components/PageHeading';
import { ArrowLeft } from 'lucide-react';
import type { Router, Subscriber, SubscriberDetailData } from '../lib/api';
import { useResource } from '../lib/useResource';
import { DetailSection, Facts, MissingData, ResourceState, dateTime } from '../components/Resource';
import { SourceBadge, StatusBadge } from '../components/Status';

type RouterDetail = {item: Router; assigned_subscribers: Subscriber[]; is_demo: true};
type SubscriberDetail = SubscriberDetailData;
export function DetailCenter({kind, id, onBack, backLabel='Listeye dön'}: {kind: 'routers' | 'subscribers'; id: string; onBack: () => void; backLabel?: string}) {
  const resource = useResource<RouterDetail | SubscriberDetail>(`/${kind}/${encodeURIComponent(id)}`);
  const [notice, setNotice] = useState('');
  const error = resource.error || (resource.data && (resource.data.is_demo!==true || resource.data.item?.is_demo!==true) ? 'Sentetik demo kaynağı doğrulanamadı; detay gösterilmedi.' : undefined);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { setNotice('');heading.current?.focus(); window.scrollTo(0, 0); }, [id, kind]);
  return <div className="screen-stack"><button className="button-secondary detail-back" onClick={onBack}><ArrowLeft size={16}/>{backLabel}</button>
    <PageHeading title={kind === 'routers' ? 'Router Detay Merkezi' : 'Abone Detay Merkezi'} description="Demo kayıtları gösteriliyor. Canlı bağlantı veya ölçüm yapılmadı." eyebrow="SENTETİK DEMO · CANLI İŞLEM YOK" headingRef={heading} actions={kind==='subscribers'?<button className="button-secondary" disabled={resource.loading} onClick={()=>{setNotice('');resource.retry();}}>Detayı yenile</button>:undefined}/>
    {notice && <p className="demo-save-notice" role="status">{notice}</p>}
    <ResourceState {...resource} error={error}/>
    {resource.data && !resource.loading && !error && (kind === 'routers' ? <RouterDetails detail={resource.data as RouterDetail}/> : <SubscriberDetails detail={resource.data as SubscriberDetail} onSaved={()=>{setNotice('Demo abone değişikliği ve işlem geçmişi V2 yerel geliştirme veritabanına kaydedildi. Sentetik demo işlemidir.');invalidateResources(['/subscribers','/routers']);}}/>)}
  </div>;
}
function RouterDetails({detail}: {detail: RouterDetail}) {
  const r = detail.item;
  return <div className="detail-grid">
    <DetailSection title={r.name}><Facts items={[["Kayıt", r.id], ["Konum", r.site], ["Yönetim adresi", r.management_address], ["Model", r.model], ["RouterOS", r.routeros_version]]}/></DetailSection>
    <DetailSection title="Bağlantı durumu"><Facts items={[["Demo durum kaydı", <StatusBadge status={r.status}/>], ["Son görülme", dateTime(r.last_seen)], ["Demo çalışma süresi", r.uptime], ["Demo CPU / bellek", `${r.cpu_percent}% / ${r.memory_percent}%`]]}/><MissingData>Canlı RouterOS bağlantı durumu için adaptör bağlı değil.</MissingData></DetailSection>
    <DetailSection title="Bağlantı geçmişi"><p className="missing-data">Veri yok. Envanter yalnız son sentetik durum kaydını sağlıyor; bağlantı/kopma olayları ve kesinti süresi kaynağı bağlı değil.</p></DetailSection>
    <DetailSection title="İnternet ve WAN alarmları"><p className="missing-data">Veri yok. İnternet erişim kontrolü, WAN kimliği ve değişiklik geçmişi kaynağı bağlı değil. Envanter durumu internet erişimini doğrulamaz; yönetim adresi WAN adresi değildir.</p><a className="record-link" href="#module=operations">Operasyon Merkezi’ne dön</a></DetailSection>
    <DetailSection title="Arayüzler"><MissingData>Arayüz envanteri kaynağı bağlı değil.</MissingData></DetailSection>
    <DetailSection title="Trafik"><p className="missing-data">Veri yok. Bu router için indirme/yükleme, arayüz sayacı veya trafik zaman serisi kaynağı bağlı değil.</p></DetailSection>
    <DetailSection title="Bağlı aboneler"><p>Demo envanter sayacı: {r.subscriber_count}. Listede router adına atanmış {detail.assigned_subscribers.length} sentetik kayıt var; bunlar çevrimiçi oturum değildir.</p>{detail.assigned_subscribers.length ? <ul className="assigned-list">{detail.assigned_subscribers.map(s => <li key={s.id}><span><strong>{s.customer_name}</strong><small>{s.username} · {s.plan}</small></span><SourceBadge source={s.source}/><StatusBadge status={s.status}/></li>)}</ul> : <MissingData>Bu router için atanmış abone kaydı yok.</MissingData>}<MissingData>Aktif oturum kaynağı bağlı değil.</MissingData></DetailSection>
  </div>;
}
function SubscriberDetails({detail, onSaved}: {detail: SubscriberDetail; onSaved: () => void}) {
  const [editing, setEditing] = useState(false);
  const [management,setManagement]=useState<'PLAN_CHANGE'|'STATUS_CHANGE'|null>(null);
  const s = detail.item;
  const today = useTurkeyToday();
  const unknownSource = subscriberSource(s.source)==='UNKNOWN';
  const persistent = detail.persistence==='local-postgresql-demo';
  const canChange = !unknownSource && persistent;
  return <div className="detail-grid subscriber-detail">
    <DetailSection title={detailText(s.customer_name)}>
      <p><span className="demo-chip">SENTETİK</span> V2 demo abone kaydı</p>
      <Facts items={[
        ['Kayıt',s.id], ['Kullanıcı adı',detailText(s.username)],
        ['Erişim türü',s.access_type==='PPPOE'?'PPPoE (sentetik)':'Veri yok'],
        ['Router',detailText(s.router_name)], ['Yetkili kaynak',<SourceBadge source={s.source}/>],
        ['Katılım tarihi',detailText(s.joined_at)],
      ]}/>
    </DetailSection>
    <DetailSection title="Paket/profil ve hesap durumu">
      <Facts items={[
        ['Paket/profil',detailText(s.plan)], ['Aylık tutar',monthlyPriceText(s.monthly_price)],
        ['Hesap durumu (demo)',<StatusBadge status={s.status}/>],
      ]}/>
      <p>Hesap etkinliği oturum bağlantı durumu değildir. Devre dışı, mevcut PAUSED (duraklatıldı) durumudur. Paket/profil değişikliği yalnız demo paketi ve aylık tutarı günceller.</p>
      <div className="expiry-editor-actions">
        <button className="button-primary" disabled={!canChange} onClick={()=>setManagement('PLAN_CHANGE')}>Demo paket/profil değiştir</button>
        <button className="button-secondary" disabled={!canChange} onClick={()=>setManagement('STATUS_CHANGE')}>Demo etkinleştir / devre dışı bırak</button>
      </div>
      {unknownSource&&<p>Kaynak bilinmiyor; değişiklik kapalı.</p>}
      {!persistent&&<p>İzole V2 PostgreSQL demo deposu gerekli; geçici belleğe yazılmaz.</p>}
    </DetailSection>
    <DetailSection title="Yetkili yönetim kaynağı"><SourceExplanation source={s.source}/></DetailSection>
    <DetailSection title="Abonelik bitişi ve kalan gün">
      <ExpirySummary expiresOn={s.expires_on} today={today}/>
      {expiryInfo(s.expires_on,today).days===null&&<p className="missing-data">Veri yok. Geçerli bir abonelik bitiş tarihi kaydedilmemiş; kalan gün hesaplanamaz.</p>}
      <p>Türkiye takvim günü kullanılır; bitiş günü dahildir. Yenileme ve tarih değişikliği gerçek router/RADIUS hesabını veya oturumunu değiştirmez.</p>
      <button className="button-primary" disabled={!canChange} onClick={()=>setEditing(true)}>Demo bitiş tarihini düzenle / yenile</button>
      {unknownSource&&<p>Kaynak bilinmiyor; tarih değişikliği kapalı.</p>}
      {!persistent&&<p role="status">Kalıcı demo saklama etkin değil; geçici bellek değişikliği yapılmaz.</p>}
    </DetailSection>
    <SubscriberReports key={s.id} subscriber={s} today={today}/>
    <DetailSection title="İşlem geçmişi">
      <p>{persistent?'V2 yerel geliştirme veritabanındaki sentetik demo işlemleri.':'Bu eski API sürecinin geçmişi geçici bellektedir; kalıcı saklama etkin değil.'} Zamanlar Türkiye saatinde (Europe/Istanbul) gösterilir.</p>
      {detail.history.length ? <ol className="subscriber-history">{detail.history.map(event=>{
        const [previous,next]=historyValues(event);
        return <li key={event.id}>
          <strong>{operationLabel(event.operation)}</strong>
          <time dateTime={event.occurred_at}>{dateTime(event.occurred_at)}</time>
          <Facts items={[
            ['İşlemi yapan',detailText(event.actor_id)], ['Önceki değerler',previous],
            ['Yeni değerler',next], ['Kaynak',<SourceBadge source={event.source}/>],
          ]}/>
        </li>;
      })}</ol> : <p className="missing-data">Veri yok. Henüz kaydedilmiş bir demo işlemi yok.</p>}
    </DetailSection>
    {management&&<SubscriberEditor mode={management} subscriber={s} onClose={()=>setManagement(null)} onSaved={()=>{setManagement(null);onSaved();}}/>}
    {editing&&<ExpiryEditor persistence={detail.persistence} subscriber={s} today={today} onClose={()=>setEditing(false)} onSaved={()=>{setEditing(false);onSaved();}}/>}
  </div>;
}
