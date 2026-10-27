import { useEffect, useRef } from 'react';
import { PageHeading } from '../components/PageHeading';
import { ArrowLeft } from 'lucide-react';
import type { Router, Subscriber } from '../lib/api';
import { useResource } from '../lib/useResource';
import { DetailSection, Facts, MissingData, ResourceState, dateTime } from '../components/Resource';
import { SourceBadge, StatusBadge } from '../components/Status';

type RouterDetail = {item: Router; assigned_subscribers: Subscriber[]; is_demo: true};
type SubscriberDetail = {item: Subscriber; is_demo: true};
export function DetailCenter({kind, id, onBack}: {kind: 'routers' | 'subscribers'; id: string; onBack: () => void}) {
  const resource = useResource<RouterDetail | SubscriberDetail>(`/${kind}/${encodeURIComponent(id)}`);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); window.scrollTo(0, 0); }, [id, kind]);
  return <div className="screen-stack"><button className="button-secondary detail-back" onClick={onBack}><ArrowLeft size={16}/>Listeye dön</button>
    <PageHeading title={kind === 'routers' ? 'Router Detay Merkezi' : 'Abone Detay Merkezi'} description="Demo kayıtları gösteriliyor. Canlı bağlantı veya ölçüm yapılmadı." eyebrow="SALT OKUNUR · SENTETİK DEMO" headingRef={heading}/>
    <ResourceState {...resource}/>
    {resource.data && !resource.loading && !resource.error && (kind === 'routers' ? <RouterDetails detail={resource.data as RouterDetail}/> : <SubscriberDetails detail={resource.data as SubscriberDetail}/>)}
  </div>;
}
function RouterDetails({detail}: {detail: RouterDetail}) {
  const r = detail.item;
  return <div className="detail-grid">
    <DetailSection title={r.name}><Facts items={[["Kayıt", r.id], ["Konum", r.site], ["Yönetim adresi", r.management_address], ["Model", r.model], ["RouterOS", r.routeros_version]]}/></DetailSection>
    <DetailSection title="Bağlantı durumu"><Facts items={[["Demo durum kaydı", <StatusBadge status={r.status}/>], ["Son görülme", dateTime(r.last_seen)], ["Demo çalışma süresi", r.uptime], ["Demo CPU / bellek", `${r.cpu_percent}% / ${r.memory_percent}%`]]}/><MissingData>Canlı RouterOS bağlantı durumu için adaptör bağlı değil.</MissingData></DetailSection>
    <DetailSection title="Arayüzler"><MissingData>Arayüz envanteri kaynağı bağlı değil.</MissingData></DetailSection>
    <DetailSection title="Trafik"><MissingData>Bu router için trafik ölçümü veya zaman serisi yok.</MissingData></DetailSection>
    <DetailSection title="Bağlı aboneler"><p>Demo envanter sayacı: {r.subscriber_count}. Listede router adına atanmış {detail.assigned_subscribers.length} sentetik kayıt var; bunlar çevrimiçi oturum değildir.</p>{detail.assigned_subscribers.length ? <ul className="assigned-list">{detail.assigned_subscribers.map(s => <li key={s.id}><span><strong>{s.customer_name}</strong><small>{s.username} · {s.plan}</small></span><SourceBadge source={s.source}/><StatusBadge status={s.status}/></li>)}</ul> : <MissingData>Bu router için atanmış abone kaydı yok.</MissingData>}<MissingData>Aktif oturum kaynağı bağlı değil.</MissingData></DetailSection>
  </div>;
}
function SubscriberDetails({detail}: {detail: SubscriberDetail}) {
  const s = detail.item;
  return <div className="detail-grid">
    <DetailSection title={s.customer_name}><Facts items={[["Kayıt", s.id], ["Kullanıcı adı", s.username], ["Paket", s.plan], ["Yetkili kaynak", <SourceBadge source={s.source}/>], ["Abonelik durumu (demo)", <StatusBadge status={s.status}/>], ["Router", s.router_name], ["Aylık tutar", new Intl.NumberFormat('tr-TR', {style: 'currency', currency: 'TRY'}).format(s.monthly_price)]]}/></DetailSection>
    <DetailSection title="Bağlantı durumu"><Facts items={[["Demo IP kaydı", s.ip_address], ["Son görülme", dateTime(s.last_seen)]]}/><MissingData>Oturum kaynağı bağlı değil; aktif abonelik çevrimiçi bağlantı anlamına gelmez.</MissingData></DetailSection>
    <DetailSection title="Süre ve bitiş"><Facts items={[["Katılım tarihi", s.joined_at]]}/><MissingData>Bitiş tarihi, kalan süre ve oturum süresi kaynağı yok; sınırsız veya otomatik yenilenen abonelik varsayılmadı.</MissingData></DetailSection>
    <DetailSection title="Trafik"><MissingData>Bu abone için indirme, yükleme veya kota ölçümü yok.</MissingData></DetailSection>
    <DetailSection title="İşlem geçmişi"><MissingData>Bu aboneliğe ait doğrulanmış işlem veya audit kaydı sağlanmıyor.</MissingData></DetailSection>
  </div>;
}
