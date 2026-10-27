import { buildConnectionAlarms } from '../lib/connectionAlarms';
import { RecentOperations } from '../components/RecentOperations';
import { useEffect, useRef } from 'react';
import { ArrowRight, Clock3, RefreshCw, Router as RouterIcon, Users, CalendarClock, AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';
import type { ScreenKey } from '../components/Sidebar';
import { StatusBadge } from '../components/Status';
import { PageHeading } from '../components/PageHeading';
import { ResourceState, dateTime } from '../components/Resource';
import { useResource } from '../lib/useResource';
import { useTurkeyToday } from '../lib/useTurkeyToday';
import { loadDailySummary, type DailySummary } from '../lib/dailySummary';

const DEPENDENCIES = ['/routers', '/subscribers'] as const;
type Navigate = (screen: ScreenKey, params?: Record<string,string>) => void;
function DailyTile({title, value, note, icon, tone, onClick, label}: {title:string; value:number; note:string; icon:ReactNode; tone:string; onClick:()=>void; label:string}) {
  return <button className="metric-card daily-tile" onClick={onClick} aria-label={label}><span className="metric-card-top"><span>{title}</span><span className={`metric-icon ${tone}`}>{icon}</span></span><strong className="daily-value">{value.toLocaleString('tr-TR')}</strong><span className="metric-foot">{note}<ArrowRight size={14}/></span></button>;
}
export function Dashboard({onNavigate}: {onNavigate: Navigate}) {
  const resource = useResource<DailySummary>('/dashboard/summary', loadDailySummary, DEPENDENCIES);
  const today = useTurkeyToday();
  const previousDay = useRef(today);
  useEffect(() => {
    if (previousDay.current !== today) {previousDay.current = today;resource.retry();}
  }, [today, resource.retry]);
  const data = resource.data;
  const alarms = data ? buildConnectionAlarms(data.routers) : null;
  const goSubscribers = (params: Record<string,string> = {}) => onNavigate('subscribers', params);
  const goRouters = (params: Record<string,string> = {}) => onNavigate('routers', params);
  const fullDate = data ? new Intl.DateTimeFormat('tr-TR', {dateStyle:'full', timeZone:'UTC'}).format(new Date(data.as_of_date+'T00:00:00Z')) : 'Türkiye takvim günü · Europe/Istanbul';
  return <div className="screen-stack">
    <PageHeading title="Merkezi Dashboard" eyebrow={fullDate} description="Sentetik demo envanteri ve kaydedilmiş abonelik işlemleri. Canlı sistem durumu değildir. PPPoE yönetimi kapsamındaki eski abonelerde erişim türü belirtilmemiş olabilir." actions={<button className="button-secondary" disabled={resource.loading} onClick={resource.retry}><RefreshCw size={15}/>Özeti yenile</button>}/>
    <ResourceState {...resource}/>
    {data && !resource.loading && !resource.error && <>
      <div className="metric-grid">
        <DailyTile title="Toplam router" value={data.router_counts.total} note="Sentetik envanter kayıtları" icon={<RouterIcon size={17}/>} tone="blue" label="Tüm routerları göster" onClick={()=>goRouters()}/>
        <DailyTile title="Online kaydı" value={data.router_counts.online} note="Son sentetik envanter durumu" icon={<RouterIcon size={17}/>} tone="teal" label="Online kayıtlı routerları göster" onClick={()=>goRouters({status:'ONLINE'})}/>
        <DailyTile title="Offline kaydı" value={data.router_counts.offline} note="İnternet kesintisi kanıtı değildir" icon={<RouterIcon size={17}/>} tone="amber" label="Offline kayıtlı routerları göster" onClick={()=>goRouters({status:'OFFLINE'})}/>
        <DailyTile title="Durumu bilinmeyen" value={data.router_counts.unknown} note="Durum kaydı doğrulanamayan router" icon={<RouterIcon size={17}/>} tone="violet" label="Durumu bilinmeyen routerları göster" onClick={()=>goRouters({status:'UNKNOWN'})}/>
        <DailyTile title="Toplam abonelik" value={data.subscribers.total} note="Kayıtlı demo abonelikleri" icon={<Users size={17}/>} tone="violet" label="Tüm aboneleri göster" onClick={()=>goSubscribers()}/>
        <DailyTile title="Süresi dolmuş" value={data.expiry.expired} note="Bitiş tarihi bugünden önce" icon={<AlertTriangle size={17}/>} tone="amber" label="Süresi dolmuş aboneleri göster" onClick={()=>goSubscribers({expiry:'EXPIRED'})}/>
        <DailyTile title="30 gün içinde bitecek" value={data.expiry.within_30} note={`İlk 7 gün: ${data.expiry.within_7} · bugün dahil`} icon={<CalendarClock size={17}/>} tone="teal" label="30 gün içinde bitecek aboneleri göster" onClick={()=>goSubscribers({expiry:'WITHIN_30'})}/>
      </div>
      <div className="dashboard-grid">
        <section className="panel"><div className="panel-title"><h2>Abonelik dağılımı</h2><span className="demo-chip">SENTETİK</span></div><p className="daily-description">PPPoE olarak kayıtlı: {data.pppoe.confirmed} · erişim türü belirtilmemiş: {data.pppoe.untyped}. Hesap durumu, bitiş durumu ve yetkili kaynak ayrı bilgilerdir; aktif hesap çevrimiçi oturum anlamına gelmez.</p>
          <div className="daily-links" aria-label="Abonelik özeti filtreleri">
            <button onClick={()=>goSubscribers({status:'ACTIVE'})}>Aktif hesap <strong>{data.subscribers.active}</strong></button>
            <button onClick={()=>goSubscribers({status:'PAUSED'})}>Duraklatıldı <strong>{data.subscribers.paused}</strong></button>
            <button onClick={()=>goSubscribers({status:'PENDING'})}>Bekliyor <strong>{data.subscribers.pending}</strong></button>
            <button onClick={()=>goSubscribers({expiry:'WITHIN_7'})}>7 gün içinde bitecek <strong>{data.expiry.within_7}</strong></button>
            <button onClick={()=>goSubscribers({expiry:'UNKNOWN'})}>Bitiş tarihi bilinmiyor <strong>{data.expiry.unknown}</strong></button>
            <button onClick={()=>goSubscribers({expiry:'ACTIVE'})}>Bitişine 30 günden fazla <strong>{data.expiry.active}</strong></button>
            <button onClick={()=>goSubscribers({source:'LOCAL'})}>LOCAL kaynak <strong>{data.subscribers.local}</strong></button>
            <button onClick={()=>goSubscribers({source:'RADIUS'})}>RADIUS kaynak <strong>{data.subscribers.radius}</strong></button>
            <button onClick={()=>goSubscribers({source:'UNKNOWN'})}>Kaynak bilinmiyor <strong>{data.subscribers.unknown_source}</strong></button>
          </div>{data.subscribers.unknown_status>0&&<p className="daily-description">Hesap durumu bilinmeyen: {data.subscribers.unknown_status}</p>}{data.subscribers.total===0&&<p className="table-empty">Henüz kayıtlı demo abonelik yok.</p>}
        </section>
        <section className="panel"><div className="panel-title"><h2>Router durum özeti</h2></div><p className="daily-description">Envanterdeki son sentetik durum kaydı esas alınır; cihaz sorgusu veya canlı sağlık kontrolü yapılmaz.</p><div className="daily-links">
          <button onClick={()=>goRouters({status:'ONLINE'})}>Çevrimiçi kaydı <strong>{data.router_counts.online}</strong></button>
          <button onClick={()=>goRouters({status:'OFFLINE'})}>Çevrimdışı kaydı <strong>{data.router_counts.offline}</strong></button>
          <button onClick={()=>goRouters({status:'DEGRADED'})}>Dikkat gerektiren <strong>{data.router_counts.degraded}</strong></button>
        <button onClick={()=>goRouters({status:'UNKNOWN'})}>Bilinmiyor <strong>{data.router_counts.unknown}</strong></button></div><p className="missing-data">Veri yok: canlı router bağlantısı, çevrimiçi abone oturumu, ölçülmüş trafik ve günlük tahsilat kaynağı bağlı değil.</p></section>
      </div>
      <section className="panel central-events"><div className="panel-title"><h2>Son 24 saat internet ve WAN olayları</h2><span className="demo-chip">SENTETİK</span></div>
        <p>İnternet kesintileri: {alarms?.internet_outages===null?'Veri yok':'Bilinmiyor'} · WAN değişiklikleri: {alarms?.wan_changes===null?'Veri yok':'Bilinmiyor'}</p>
        <p className="missing-data">Veri yok. Kaydedilmiş router olayları, internet kontrolü ve WAN değişiklik geçmişi kaynağı bulunmuyor. Son görülmeden kesinti veya olay üretilmez; eksik olay sayısı sıfır sayılmaz.</p>
        <a className="button-secondary" href="#module=operations">İnternet ve WAN kapsamını aç</a>
      </section>
      <div className="dashboard-grid bottom-grid">
        <section className="panel router-panel"><button className="button-secondary report-entry" onClick={()=>goRouters({view:'REPORT'})}>Kullanım ve bağlantı raporu <ArrowRight size={14}/></button><div className="panel-heading"><div><div className="panel-title"><h2>Router envanteri</h2><span className="soft-count">{data.routers.length}</span></div><p>Sentetik kayıt · kaynak zamanı aşağıda gösterilir</p></div><button className="text-link" onClick={()=>goRouters()}>Tümünü gör <ArrowRight size={14}/></button></div>
          {data.routers.length ? <div className="router-list">{data.routers.map(router=><div className="router-list-row" key={router.id}><span className={`router-row-icon ${router.status?.toLowerCase()}`}><RouterIcon size={16}/></span><span className="router-row-name daily-router-name"><strong><button className="record-link" onClick={()=>goRouters({id:router.id})}>{router.name}</button></strong><small>Kaynak zamanı: {dateTime(router.last_seen)}</small></span><StatusBadge status={['ONLINE','OFFLINE','DEGRADED'].includes(router.status)?router.status:'UNKNOWN'}/></div>)}</div> : <p className="table-empty">Router envanteri için veri yok.</p>}
        </section>
        <RecentOperations data={data} onSubscriber={id=>goSubscribers({id})}/>
      </div>
      <p className="screen-footnote daily-updated"><span><Clock3 size={14}/>Özet güncellendi: {dateTime(data.generated_at)} · Gün hesabı: Europe/Istanbul</span></p>
    </>}
  </div>;
}
