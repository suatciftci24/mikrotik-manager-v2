import { AlarmEvents } from '../components/AlarmEvents';
import { api } from '../lib/api';
import { useCallback } from 'react';
import { buildRouterReport, percentText } from '../lib/routerReport';
import { buildDailySummary } from '../lib/dailySummary';
import { assignedToRouter } from '../lib/routerSubscribers';
import { RecentOperations } from '../components/RecentOperations';
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
    <PageHeading title={kind === 'routers' ? 'Router Detay Merkezi' : 'Abone Detay Merkezi'} description="Demo kayıtları gösteriliyor. Canlı bağlantı veya ölçüm yapılmadı." eyebrow="SENTETİK DEMO · CANLI İŞLEM YOK" headingRef={heading} actions={<button className="button-secondary" disabled={resource.loading} onClick={()=>{setNotice('');resource.retry();}}>Detayı yenile</button>}/>
    {notice && <p className="demo-save-notice" role="status">{notice}</p>}
    <ResourceState {...resource} error={error}/>
    {resource.data && !resource.loading && !error && (kind === 'routers' ? <RouterDetails detail={resource.data as RouterDetail}/> : <SubscriberDetails detail={resource.data as SubscriberDetail} onSaved={()=>{setNotice('Demo abone değişikliği ve işlem geçmişi V2 yerel geliştirme veritabanına kaydedildi. Sentetik demo işlemidir.');invalidateResources(['/subscribers','/routers']);}}/>)}
  </div>;
}
export function RouterDetails({detail}: {detail: RouterDetail}) {
  const r = detail.item;
  const report = buildRouterReport([r]).rows[0];
  const assigned = detail.assigned_subscribers.filter(item=>assignedToRouter(item,r));
  const pppoe = assigned.filter(item=>item.access_type==='PPPOE').length;
  return <div className="detail-grid">
    <DetailSection title={r.name}><Facts items={[["Kayıt", r.id], ["Konum", r.site], ["Yönetim adresi", r.management_address], ["Model", r.model], ["RouterOS", detailText(r.routeros_version)], ["Veri kaynağı", "Sentetik V2 envanteri"], ["Yönetim kaynağı", "Bilinmiyor (router için LOCAL/RADIUS alanı yok)"]]}/></DetailSection>
    <DetailSection title="Bağlantı durumu"><Facts items={[["Son sentetik durum kaydı", <StatusBadge status={report.status}/>], ["Son görülme", report.source_time?dateTime(report.source_time):'Veri yok'], ["Canlı bağlantı", 'Bilinmiyor'], ["Demo çalışma süresi", report.device_uptime??'Veri yok'], ["Demo CPU / RAM", `${percentText(report.cpu)} / ${percentText(report.memory)}`]]}/><p>Son görülme aktif bağlantı kanıtı değildir. CPU/RAM son sentetik örneklerdir; uptime bağlantı süresi değildir.</p></DetailSection>
    <DetailSection title="Bağlantı geçmişi"><p className="missing-data">Veri yok. Envanter yalnız son sentetik durum kaydını sağlıyor; bağlantı/kopma olayları ve kesinti süresi kaynağı bağlı değil.</p></DetailSection>
    <DetailSection title="İnternet ve WAN"><Facts items={[
      ['WAN arayüzü','Veri yok'], ['WAN IP','Veri yok'], ['Gateway','Veri yok'], ['Default route','Veri yok'], ['İnternet durumu','Bilinmiyor'],
    ]}/><p className="missing-data">Veri yok. WAN değişiklik geçmişi ve internet kesintisi kaynağı bağlı değil. Yönetim IP’si WAN IP olarak kullanılamaz.</p><a className="record-link" href="#module=operations">Operasyon Merkezi’ni aç</a></DetailSection>
    <DetailSection title="Arayüzler"><MissingData>Arayüz envanteri kaynağı bağlı değil.</MissingData></DetailSection>
    <DetailSection title="Trafik"><p className="missing-data">Veri yok. Bu router için indirme/yükleme, arayüz sayacı veya trafik zaman serisi kaynağı bağlı değil.</p></DetailSection>
    <DetailSection title="İlişkili aboneler">
      <Facts items={[
        ['Kayıtlı ilişkili abonelik',assigned.length], ['Erişim türü PPPoE olarak kayıtlı',pppoe],
        ['Erişim türü belirtilmemiş eski kayıt',assigned.length-pppoe], ['Eski sentetik envanter sayacı',r.subscriber_count],
      ]}/>
      <p>İlişkili kayıtlar V2 abone deposundan gelir; eski envanter sayacı ayrı bir demo değeridir. Abonelik sayıları çevrimiçi oturum sayısı değildir.</p>
      {assigned.length ? <ul className="assigned-list">{assigned.map(s => <li key={s.id}><span><strong><a className="record-link" href={'#'+new URLSearchParams({module:'subscribers',id:s.id}).toString()}>{s.customer_name}</a></strong><small>{s.username} · {s.plan}</small></span><SourceBadge source={s.source}/><StatusBadge status={s.status}/></li>)}</ul> : <p className="missing-data">Veri yok. İlişkili abone kaydı bulunmuyor.</p>}
    </DetailSection>
    <AlarmEvents routerId={r.id} routers={[r]}/>
    <RouterManagementOperations router={r} subscribers={assigned}/>

  </div>;
}
function RouterManagementOperations({router,subscribers}: {router: Router; subscribers: Subscriber[]}) {
  const ids = JSON.stringify(subscribers.map(item=>item.id));
  const load = useCallback(async (_path: string, init?: RequestInit) => {
    const details = await Promise.all((JSON.parse(ids) as string[]).map(id=>api<SubscriberDetailData>(`/subscribers/${encodeURIComponent(id)}`,init)));
    if (details.some(detail=>!assignedToRouter(detail.item,router))) throw new Error('Abone router ataması değişti; router detayını yenileyin.');
    return buildDailySummary([router],details);
  },[ids,router]);
  const resource=useResource(`/routers/${encodeURIComponent(router.id)}/management-summary`,load);
  return <div className="router-management-events"><ResourceState {...resource}/>{resource.data&&!resource.loading&&!resource.error&&<RecentOperations data={resource.data} onSubscriber={id=>{window.location.hash=new URLSearchParams({module:'subscribers',id}).toString();}}/>}</div>;
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
