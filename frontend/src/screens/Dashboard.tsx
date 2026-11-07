import { invalidateResources } from '../lib/resourceEvents';
import { DashboardV1Health } from '../components/DashboardV1Health';
import { OperationReport } from './OperationReport';
import { InternetReport } from './InternetReport';
import { ManagementReport } from './ManagementReport';
import { useListFilter } from '../lib/useListFilter';
import { useEffect, useRef, type ReactNode } from 'react';
import { ArrowRight, RefreshCw, Router as RouterIcon, Users, CalendarClock, AlertTriangle, Activity, WifiOff, Bot, LayoutDashboard } from 'lucide-react';
import type { ScreenKey } from '../components/Sidebar';
import { PageHeading } from '../components/PageHeading';
import { ResourceState, dateTime } from '../components/Resource';
import { useResource } from '../lib/useResource';
import { useTurkeyToday } from '../lib/useTurkeyToday';
import { useIdentity } from '../lib/permissions';
import { loadDashboardSummary, dashboardToday, dashboardCritical, loadDashboardAlarms, dashboardAlarmPath, type DashboardSummary } from '../lib/dashboardOverview';
import { loadRouterEvents } from '../lib/routerEvents';

const DEPENDENCIES = ['/routers', '/subscribers'] as const;
const EVENT_DEPENDENCIES = ['/routers','/subscribers','/router-events'] as const;
const ALARM_DEPENDENCIES = [...EVENT_DEPENDENCIES,'/alarms','/mikajani'] as const;
type Navigate = (screen: ScreenKey, params?: Record<string,string>) => void;
function SummaryTile({title,value,note,icon,onClick,label,disabled=false}: {title:string;value:number|string|null;note:string;icon:ReactNode;onClick:()=>void;label:string;disabled?:boolean}){
  return <button className="metric-card daily-tile" onClick={onClick} aria-label={label} disabled={disabled}><span className="metric-card-top"><span>{title}</span><span className="metric-icon blue">{icon}</span></span><strong className="daily-value">{value===null?'Veri yok':typeof value==='number'?value.toLocaleString('tr-TR'):value}</strong><span className="metric-foot"><span>{note}</span><ArrowRight size={14}/></span></button>;
}
const dashboardViews=['OVERVIEW','DAILY_REPORT','INTERNET_REPORT','OPERATIONS_REPORT'] as const;
export function Dashboard({onNavigate}: {onNavigate: Navigate}) {
  const [view,setView]=useListFilter('dashboard','view',dashboardViews,'OVERVIEW');
  return view==='OPERATIONS_REPORT'?<OperationReport/>:view==='INTERNET_REPORT'?<InternetReport/>:view==='DAILY_REPORT'?<ManagementReport onBack={()=>setView('OVERVIEW')}/>:<DashboardOverview onNavigate={onNavigate} onReport={()=>setView('DAILY_REPORT')} onInternet={()=>setView('INTERNET_REPORT')}/>;
}
const dashboardSources=['DEMO','V1_INVENTORY'] as const;
function DashboardOverview(props:{onNavigate:Navigate;onReport:()=>void;onInternet:()=>void}){
  const [source,setSource]=useListFilter('dashboard','dashboard_source',dashboardSources,'DEMO');
  const identity=useIdentity(),admin=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
  return <div className="dashboard-source-screen"><div className="filter-tabs dashboard-sources" role="group" aria-label="Dashboard veri kaynağı">
    <button aria-pressed={source==='DEMO'} className={source==='DEMO'?'selected':''} onClick={()=>setSource('DEMO')}>V2 Sentetik Demo</button>
    <button aria-pressed={source==='V1_INVENTORY'} className={source==='V1_INVENTORY'?'selected':''} disabled={!admin} onClick={()=>setSource('V1_INVENTORY')}>Gerçek V1 · Salt Okunur</button>
  </div>{source==='DEMO'?<SyntheticDashboardOverview {...props}/>:admin?<DashboardV1Health/>:<section className="panel"><h1>Gerçek V1 · Salt Okunur</h1><p role="status">Bu kaynak için merkezi yönetici yetkisi gerekli. Veri gösterilmiyor.</p></section>}</div>;
}
function SyntheticDashboardOverview({onNavigate,onReport,onInternet}: {onNavigate:Navigate;onReport:()=>void;onInternet:()=>void}) {
  const identity=useIdentity();
  const grants=Object.values(identity?.permissions??{});
  const reports=grants.some(grant=>grant.can_view&&grant.can_view_reports);
  const mika=grants.some(grant=>grant.can_view&&grant.can_use_mikajani);
  const admin=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
  const resource=useResource<DashboardSummary>('/dashboard/summary',loadDashboardSummary,DEPENDENCIES);
  const today=useTurkeyToday(),previousDay=useRef(today);
  useEffect(()=>{if(previousDay.current!==today){previousDay.current=today;resource.retry();}},[today,resource.retry]);
  const refresh=()=>invalidateResources(['/routers','/subscribers','/router-events','/mikajani','/alarms']);
  useEffect(()=>{
    const tick=()=>{if(!document.hidden)invalidateResources(['/routers','/subscribers','/router-events','/mikajani','/alarms']);};
    const timer=window.setInterval(tick,60000);
    window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);
    return()=>{window.clearInterval(timer);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};
  },[]);
  const lastData=useRef<DashboardSummary|undefined>(undefined);
  if(resource.data)lastData.current=resource.data;
  const data=resource.data??(resource.loading?lastData.current:undefined);
  const subscribers=(params:Record<string,string>={})=>onNavigate('subscribers',{workspace:'LEGACY',...params});
  const routers=(params:Record<string,string>={})=>onNavigate('routers',{source:'DEMO',...params});
  const daily=(kind:string)=>{window.location.hash=new URLSearchParams({module:'dashboard',view:'DAILY_REPORT',report_source:'DEMO',period:'TODAY',kind}).toString();};
  const fullDate=data?new Intl.DateTimeFormat('tr-TR',{dateStyle:'full',timeZone:'UTC'}).format(new Date(data.as_of_date+'T00:00:00Z')):'Türkiye takvim günü';
  return <div className="screen-stack dashboard-overview">
    <PageHeading title="Merkezi Dashboard" eyebrow={fullDate} description="V2 sentetik kayıtları · Mevcut demo çalışma alanı" actions={<button className="button-secondary" disabled={resource.loading} onClick={refresh}><RefreshCw size={15}/>Özeti yenile</button>}/>
    <section aria-labelledby="overview-status-title" className="overview-section"><div className="overview-section-heading"><h2 id="overview-status-title">Genel durum</h2><span className="demo-chip">SENTETİK V2</span></div>
      <ResourceState {...resource} retry={refresh}/>
      {data&&resource.loading&&<p role="status" className="daily-description">Önceki özet gösteriliyor; kayıtlar yenileniyor.</p>}
      <div className="overview-status-grid">
      {data&&!resource.error&&<>
        <SummaryTile title="Routerlar" value={data.router_counts.total} note="Son kayıtlı envanter" icon={<RouterIcon size={18}/>} label="Tüm routerları göster" onClick={()=>routers()}/>
        <SummaryTile title="Toplam aboneler" value={data.subscribers.total} note="Mevcut demo aboneleri" icon={<Users size={18}/>} label="Tüm aboneleri göster" onClick={()=>subscribers()}/>
        <SummaryTile title="Süresi dolmuş" value={data.expiry.expired} note="Bitiş tarihi bugünden önce" icon={<AlertTriangle size={18}/>} label="Süresi dolmuş aboneleri göster" onClick={()=>subscribers({expiry:'EXPIRED'})}/>
        <SummaryTile title="Yaklaşan bitişler" value={data.expiry.within_7} note="Bugün dahil · 7 gün" icon={<CalendarClock size={18}/>} label="7 gün içinde bitecek aboneleri göster" onClick={()=>subscribers({expiry:'WITHIN_7'})}/>
      </>}
      <CriticalAlarmTile onNavigate={onNavigate}/>
      </div>
      {data&&!resource.error&&<>
        <div className="overview-router-status" role="group" aria-label="Son kayıtlı router durumları"><span>Son kayıt:</span>{([['ONLINE','Online',data.router_counts.online],['OFFLINE','Offline',data.router_counts.offline],['DEGRADED','Dikkat',data.router_counts.degraded],['UNKNOWN','Bilinmiyor',data.router_counts.unknown]] as const).map(([status,label,count])=><button key={status} className="button-secondary" onClick={()=>routers({status})}>{label} <strong>{count}</strong></button>)}</div>
        {data.router_counts.total===0&&data.subscribers.total===0&&<p className="daily-description">Henüz kayıtlı demo router veya abone yok.</p>}
      </>}
    </section>
    <section aria-labelledby="overview-daily-title" className="overview-section"><div className="overview-section-heading"><h2 id="overview-daily-title">Günlük işlemler</h2><span className="daily-description">Bugün · Türkiye saati</span></div>
      <div className="overview-daily-grid">
        <SummaryTile title="PPPoE işlemleri" value={data&&!resource.error?dashboardToday(data,null).pppoe:null} note={resource.loading?'Özet yenileniyor':reports?'Mevcut demo geçmişi':'Geçmiş için rapor yetkisi gerekli'} icon={<Activity size={18}/>} label="Bugünün PPPoE işlemlerini aç" disabled={!reports} onClick={()=>daily('PPPOE')}/>
        <SummaryTile title="Yaklaşan abonelikler" value={data&&!resource.error?data.within_3??null:null} note="Bugün dahil · 3 gün" icon={<CalendarClock size={18}/>} label="3 gün içinde bitecek aboneleri göster" onClick={()=>subscribers({expiry:'WITHIN_3'})}/>
        {reports?<DailyEventTile data={data} onOpen={()=>daily('ALL')}/>:<SummaryTile title="İnternet / WAN olayları" value={null} note="Rapor yetkisi gerekli" icon={<WifiOff size={18}/>} label="İnternet ve WAN olayları için rapor yetkisi gerekli" disabled onClick={()=>{}}/>}
      </div>
    </section>
    <section aria-labelledby="overview-quick-title" className="overview-section"><div className="overview-section-heading"><h2 id="overview-quick-title">Hızlı erişim</h2></div>
      <div className="overview-quick-grid">
        <button className="button-secondary" onClick={()=>routers()}><RouterIcon size={17}/>Router Merkezi<ArrowRight size={14}/></button>
        <button className="button-secondary" onClick={()=>subscribers()}><Users size={17}/>Abone Merkezi<ArrowRight size={14}/></button>
        <button className="button-secondary" aria-label="Günlük Yönetim Merkezi" disabled={!reports} onClick={onReport}><LayoutDashboard size={17}/>Günlük Yönetim Merkezi<ArrowRight size={14}/></button>
        <button className="button-secondary" disabled={!reports} onClick={()=>{window.location.hash=new URLSearchParams({module:'dashboard',view:'DAILY_REPORT',section:'recent-operations'}).toString();}}><Activity size={17}/>Son 24 saat PPPoE işlemleri<ArrowRight size={14}/></button>
        <button className="button-secondary" onClick={()=>onNavigate('operations')}><AlertTriangle size={17}/>Alarm Merkezi<ArrowRight size={14}/></button>
        <button className="button-secondary" disabled={!mika} onClick={()=>onNavigate('mikajani')}><Bot size={17}/>MikAjanı<ArrowRight size={14}/></button>
      </div>
      <div className="overview-report-links">{reports&&<><button className="record-link" onClick={onInternet}>İnternet Kullanım ve Bağlantı Raporları</button><a className="record-link" href="#module=dashboard&view=OPERATIONS_REPORT">Operasyon ve audit raporları</a></>}{admin&&<a className="record-link" href="#module=routers&source=V1_INVENTORY">Gerçek V1 · Salt okunur Router Merkezi</a>}</div>
    </section>
    <details className="panel overview-info"><summary>Veri kapsamı ve güvenilirlik</summary>
      <p>Yalnız yetkili mevcut sentetik demo envanteri ve geçmişi. Gerçek V1 sağlık snapshot’ları ayrı Router Merkezi’ndedir; bu sayılarla birleştirilmez. Kalıcı sentetik PPPoE işlem geçmişi Günlük Yönetim Merkezi’ndedir.</p>
      <p>Son kayıtlı router durumu canlı bağlantı, hesap etkinliği aktif oturum kanıtı değildir. Güvenilir ölçüm yoksa trafik, oturum veya kesinti üretilmez. Bugünün işlem/olay sayıları gelecek kayıtları içermez.</p>
      <p>Kritik alarmlar kaydedilmiş açık P1/P2 kaynaklarıdır; onaylanan ve iyileşenler dahildir. Kaynak eksikliği sağlıklı sistem sayılmaz. Ayrıntılar, ACK, kanıt ve analizler Alarm Merkezi ile MikAjanı’nda korunur.</p>
      {data&&<><p>Özet okuması: {dateTime(data.generated_at)}. Bitiş tarihi bilinmeyen: {data.expiry.unknown}. PPPoE türü belirtilmemiş: {data.pppoe.untyped}. Gün hesabı Europe/Istanbul; özet mevcut 60 saniye/odak dönüşü akışıyla yenilenir.</p><div className="overview-report-links"><button className="record-link" onClick={()=>subscribers({expiry:'UNKNOWN'})}>Bitişi bilinmeyen aboneler</button><button className="record-link" onClick={()=>subscribers({expiry:'WITHIN_15'})}>15 gün içinde bitecekler</button><button className="record-link" onClick={()=>subscribers({expiry:'WITHIN_30'})}>30 gün içinde bitecekler</button><button className="record-link" onClick={()=>routers({view:'REPORT'})}>Router kullanım ve bağlantı raporu</button></div></>}
    </details>
  </div>;
}
function CriticalAlarmTile({onNavigate}:{onNavigate:Navigate}){
  const resource=useResource(dashboardAlarmPath,loadDashboardAlarms,ALARM_DEPENDENCIES);
  const critical=resource.data&&!resource.loading&&!resource.error?dashboardCritical(resource.data):null;
  return <div className="overview-source-tile"><SummaryTile title="Kritik alarmlar" value={critical?.value??null} note={resource.loading?'Alarmlar yükleniyor':resource.error?'Alarm kaynağı alınamadı':critical?.partial?'Kayıtlı P1/P2 · kaynaklar eksik':'Açık P1/P2 · ACK dahil'} icon={<AlertTriangle size={18}/>} label="Alarm Merkezi’nde açık alarmları göster" onClick={()=>onNavigate('operations',{alarm_state:'ACTIVE',severity:'ALL'})}/><ResourceState {...resource}/></div>;
}
function DailyEventTile({data,onOpen}:{data:DashboardSummary|undefined;onOpen:()=>void}){
  const resource=useResource('/router-events',loadRouterEvents,EVENT_DEPENDENCIES);
  let counts:ReturnType<typeof dashboardToday>|undefined,error=resource.error;
  try{if(data&&!resource.loading&&!error)counts=dashboardToday(data,resource.data??null);}catch(failure){error=failure instanceof Error?failure.message:'Olay özeti doğrulanamadı.';}
  return <div className="overview-source-tile"><SummaryTile title="İnternet / WAN olayları" value={counts?.outages===null||counts?.outages===undefined?null:`${counts.outages} / ${counts.wan}`} note={resource.loading?'Olaylar yükleniyor':'Kesinti / WAN değişikliği · bugün'} icon={<WifiOff size={18}/>} label="Bugünün internet ve WAN olaylarını aç" onClick={onOpen}/><ResourceState {...resource} error={error}/></div>;
}
