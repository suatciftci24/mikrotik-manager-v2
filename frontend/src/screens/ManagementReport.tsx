import {observationAge,savedConnectionLabel} from '../lib/routerObservation';
import {percentText} from '../lib/routerReport';
import {QuickActions,type QuickAction} from '../components/QuickActions';
import {LegacySubscriberActions} from '../components/LegacySubscriberActions';
import {SubscriberQuickButtons} from '../components/SubscriberQuickButtons';
import {SubscriberRenewal} from '../components/SubscriberRenewal';
import {SubscriberDailyActions} from '../components/SubscriberDailyActions';
import {canChangeWorkspaceItem,workspaceActionUnavailableReason} from '../lib/subscriberActions';
import type {SubscriberDetailData} from '../lib/api';
import type {CenterSubscriber} from '../lib/subscriberCenter';
import {linkedCenterHash} from '../lib/detailLinks';
import { operationContextHash } from '../lib/operationReport';
import { linkedDetailHash } from '../lib/detailLinks';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, RefreshCw, Activity, CalendarClock, WifiOff, ArrowLeftRight } from 'lucide-react';
import { buildManagementReport, loadManagementReport, managementFilterFromHash, managementReportHash,managementSubscribersHash, reportKinds, reportPeriods, managementSourceFromHash } from '../lib/managementReport';
import type { ManagementFilter } from '../lib/managementReport';
import { useResource } from '../lib/useResource';
import { PageHeading } from '../components/PageHeading';
import { ResourceState, dateTime } from '../components/Resource';
import { MetricCard,SourceBadge } from '../components/Status';
import { OperationDetails } from '../components/OperationDetails';
import { AlarmEventDetails } from '../components/AlarmEvents';
import { operationLabel, historyValues } from '../lib/subscriberHistory';
import { eventLabels, durationText, alarmStatusLabels } from '../lib/routerEvents';
import type { EventKind } from '../lib/routerEvents';
import { can,useIdentity } from '../lib/permissions';
import { V1Inventory } from '../components/V1Inventory';
import { expiryDate, expiryInfo, remainingDays, turkeyToday } from '../lib/expiry';

const dependencies=['/routers','/subscribers','/router-events','/subscriber-workspace','/router-workspace/routers'] as const;
const number=(value:number|null)=>value===null?'Veri yok':value.toLocaleString('tr-TR');
const link=(kind:'routers'|'subscribers',id:string)=>linkedDetailHash({module:kind,id,...(kind==='routers'?{source:id.startsWith('demo-managed-')?'MANAGED_DEMO':'DEMO'}:{workspace:id.startsWith('demo-managed-')?'PERSISTENT':'LEGACY'})},typeof window==='undefined'?'':window.location.hash);
const expiryChoices=[['TODAY','Bugün'],['WITHIN_3','3 gün'],['WITHIN_7','7 gün'],['WITHIN_30','30 gün'],['EXPIRED','Süresi dolmuş'],['UNKNOWN','Bilinmeyen'],['VALID','Geçerli'],['ALL','Tümü']] as const;
export function ManagementReport({onBack}:{onBack:()=>void}){
  const [source,setSource]=useState(()=>managementSourceFromHash(typeof window==='undefined'?'':window.location.hash));
  useEffect(()=>{const read=()=>setSource(managementSourceFromHash(window.location.hash));window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[]);
  const select=(next:typeof source)=>{setSource(next);const params=new URLSearchParams(window.location.hash.slice(1));params.set('module','dashboard');params.set('view','DAILY_REPORT');params.set('report_source',next);window.history.replaceState(null,'',window.location.pathname+window.location.search+'#'+params);};
  return <div className="management-center"><div className="filter-tabs management-sources" role="group" aria-label="Yönetim merkezi veri kaynağı">
    <button aria-pressed={source==='DEMO'} className={source==='DEMO'?'selected':''} onClick={()=>select('DEMO')}>V2 sentetik kayıtları</button>
    <button aria-pressed={source==='V1_INVENTORY'} className={source==='V1_INVENTORY'?'selected':''} onClick={()=>select('V1_INVENTORY')}>Gerçek V1 · Salt okunur</button>
  </div>{source==='DEMO'?<SyntheticManagementReport onBack={onBack}/>:<div className="screen-stack management-report">
    <button className="button-secondary detail-back" onClick={onBack}><ArrowLeft size={16}/>Dashboard’a dön</button>
    <PageHeading title="Günlük Yönetim Merkezi · V2.3" eyebrow="GERÇEK V1 · SALT OKUNUR" description="Mevcut V1 snapshot kaynağı yalnız son router sağlık ölçümünü sağlar. Kaynaklar birleştirilmez."/>
    <div className="metric-grid management-metrics">{['PPPoE işlemleri','Abonelik bitişleri','İnternet kesintileri','WAN değişiklikleri'].map(title=><MetricCard key={title} title={title} value="Veri yok" note="Doğrulanmış geçmiş bağlı değil" icon={<Activity size={18}/>}/>)}</div>
    <details className="panel management-notes"><summary>Veri kapsamı</summary><p>Gerçek işlem geçmişi bağlı değil. Gerçek abone ve olay geçmişi de bağlı değil; son sağlık snapshot’ından dönem toplamı veya kesinti süresi üretilmez.</p></details>
    <V1Inventory/>
    <a className="button-secondary" href="#module=routers&source=V1_INVENTORY">Router Merkezi · Gerçek V1 sağlık verisi</a>
  </div>}</div>;
}
export function SyntheticManagementReport({onBack,center='dashboard'}:{onBack:()=>void;center?:'dashboard'|'operations'}){
  const [quick,setQuick]=useState<{detail:SubscriberDetailData;action:QuickAction}|null>(null);
  const [managed,setManaged]=useState<{item:CenterSubscriber;action:'EXTEND'|'PLAN'|'STATUS'}|null>(null);
  const identity=useIdentity();
  const workspace=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
  const resource=useResource('/management/report'+(workspace?'?workspace=1':''),loadManagementReport,dependencies);
  const [filter,setFilter]=useState(()=>managementFilterFromHash(typeof window==='undefined'?'':window.location.hash));
  const [now,setNow]=useState(()=>new Date());
  const [selected,setSelected]=useState<{kind:'operation'|'event';id:string}|null>(null);
  const heading=useRef<HTMLHeadingElement>(null);
  const operationsSection=useRef<HTMLElement>(null);
  const [hash,setHash]=useState(()=>typeof window==='undefined'?'':window.location.hash);
  useEffect(()=>{
    heading.current?.focus();
    const read=()=>{setFilter(managementFilterFromHash(window.location.hash));setHash(window.location.hash);setSelected(null);};
    const tick=()=>setNow(new Date());
    const timer=window.setInterval(tick,30000);
    window.addEventListener('hashchange',read);window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);
    return()=>{window.clearInterval(timer);window.removeEventListener('hashchange',read);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};
  },[]);
  const change=(next:ManagementFilter)=>{setFilter(next);setSelected(null);setHash(managementReportHash(next,center));window.history.replaceState(null,'',window.location.pathname+window.location.search+managementReportHash(next,center));};
  let report:ReturnType<typeof buildManagementReport>|undefined,error=resource.error;
  try{if(resource.data&&!resource.loading&&!resource.error)report=buildManagementReport(resource.data,filter,now,center==='operations');}catch(failure){error=failure instanceof Error?failure.message:'Rapor oluşturulamadı.';}
  useEffect(()=>{
    if(resource.loading||error||!report||new URLSearchParams(hash.slice(1)).get('section')!=='recent-operations')return;
    operationsSection.current?.scrollIntoView({behavior:'smooth',block:'start'});
    operationsSection.current?.focus({preventScroll:true});
  },[resource.loading,error,!!report,hash]);
  const routerOptions=[...(resource.data?.routers??[]),...(resource.data?.workspace?.routers.map(row=>({id:row.id,name:row.fields.name}))??[])];
  const names=new Map(routerOptions.map(router=>[router.id,router.name]));
  const operation=selected?.kind==='operation'?report?.operations.find(event=>event.id===selected.id):undefined;
  const event=selected?.kind==='event'?report?.events?.find(event=>event.id===selected.id):undefined;
  return <div className="screen-stack management-report">
    <button className="button-secondary detail-back" onClick={onBack}><ArrowLeft size={16}/>Dashboard’a dön</button>
    {quick&&<QuickActions rows={[quick.detail.item]} today={turkeyToday(now)} initialAction={quick.action} onClose={()=>setQuick(null)}/>}
    {managed&&(managed.action==='EXTEND'?<SubscriberRenewal item={managed.item} onClose={()=>setManaged(null)}/>:<SubscriberDailyActions rows={[managed.item]} initialAction={managed.action} onClose={()=>setManaged(null)}/>)}
    <PageHeading title={center==='operations'?'Operasyon Merkezi · Günlük Yönetim':'Günlük Yönetim Merkezi'} eyebrow="SENTETİK DEMO · EUROPE/ISTANBUL" description="Sentetik demo kayıtları · Türkiye saati" headingRef={heading} actions={<button className="button-secondary" disabled={resource.loading} onClick={()=>{setSelected(null);resource.retry();}}><RefreshCw size={16}/>Raporu yenile</button>}/>
    <section className="panel management-filters"><div className="router-report-controls">
      <label className="form-label">Dönem<select aria-label="Dönem" value={filter.period} onChange={e=>change({...filter,period:e.target.value as ManagementFilter['period']})}>{Object.entries(reportPeriods).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label className="form-label">Router<select aria-label="Router" value={filter.router} onChange={e=>change({...filter,router:e.target.value})}><option value="">Tüm routerlar</option>{routerOptions.map(router=><option key={router.id} value={router.id}>{router.name}</option>)}{filter.router&&!names.has(filter.router)&&<option value={filter.router}>{filter.router} · kayıt bulunamadı</option>}</select></label>
      <label className="form-label">Yetkili kaynak<select aria-label="Rapor yetkili kaynak filtresi" value={filter.source??'ALL'} onChange={e=>change({...filter,source:e.target.value as ManagementFilter['source']})}><option value="ALL">Tüm kaynaklar</option><option value="LOCAL">LOCAL</option><option value="RADIUS">RADIUS</option><option value="UNKNOWN">Bilinmiyor</option></select></label>
      <label className="form-label">Güncel paket<select value={filter.plan??''} onChange={e=>change({...filter,plan:e.target.value})}><option value="">Tüm paketler</option>{[...new Set([...(resource.data?.details.map(d=>d.item.plan)??[]),...(resource.data?.workspace?.accounts.map(r=>r.plan)??[]),filter.plan].filter((plan):plan is string=>typeof plan==='string'&&!!plan))].sort().map(plan=><option key={plan} value={plan}>{plan}</option>)}</select></label>
      <label className="form-label">Hesap durumu<select value={filter.account_status??'ALL'} onChange={e=>change({...filter,account_status:e.target.value as ManagementFilter['account_status']})}><option value="ALL">Tümü</option><option value="ACTIVE">Aktif hesap</option><option value="PAUSED">Pasif hesap</option><option value="PENDING">Bekliyor</option></select></label>
      <label className="form-label">İşlem / olay<select aria-label="İşlem / olay" value={filter.kind} onChange={e=>change({...filter,kind:e.target.value as ManagementFilter['kind']})}>{Object.entries(reportKinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <button className="button-secondary" onClick={()=>change({period:center==='operations'?'LAST_24':'TODAY',router:'',kind:'ALL'})}>Filtreleri temizle</button>
    </div></section>
    <p className="daily-description">Kaynak filtresi işlemlerde tarihsel kaynağa, bitişlerde güncel yetkili kaynağa uygulanır. Paket ve hesap durumu güncel kayda aittir. İnternet/WAN olayları router kapsamındadır; LOCAL/RADIUS hesabına aitmiş gibi sınıflandırılmaz.</p>
    <ResourceState {...resource} error={error}/>
    {report?.workspaceError&&<p role="alert">Kalıcı kaynak eksik; özet ve abone sayıları yalnız erişilebilen kayıtları kapsar. {report.workspaceError}</p>}
    {report&&!resource.loading&&!error&&<>
      <div className="metric-grid management-metrics" aria-label="Günlük yönetim özeti">
        <MetricCard title={center==='operations'?'Kayıtlı yönetim işlemleri':'Başarılı PPPoE işlemleri'} value={number(center==='operations'?report.counts.operations:report.pppoeOperations)} note={workspace?'Dönem · demo + kalıcı geçmiş':'Dönem · mevcut demo geçmişi'} icon={<Activity size={18}/>}/>
        <MetricCard title="Abonelik bitişleri" value={String(report.expiryRows.length)} note={`${expiryChoices.find(([key])=>key===(filter.expiry??'TODAY'))?.[1]} · mevcut demo aboneleri`} icon={<CalendarClock size={18}/>}/>
        <MetricCard title="İnternet kesintileri" value={number(report.counts.outages)} note="Seçili dönem · tekil kesinti" icon={<WifiOff size={18}/>}/>
        <MetricCard title="WAN değişiklikleri" value={number(report.counts.wan)} note="Seçili dönem · kayıtlı olay" icon={<ArrowLeftRight size={18}/>}/>
      </div>
      <section className="panel central-events management-expiries"><div className="panel-title"><h2>Abonelik bitişleri</h2><a className="record-link" href={linkedCenterHash(managementSubscribersHash(filter),hash)}>İlgili abone listesini aç</a>{!filter.router&&workspace&&<a className="record-link" href={linkedCenterHash(managementSubscribersHash(filter,'PERSISTENT'),hash)}>Kalıcı abone listesini aç</a>}</div>
        <div className="filter-tabs management-expiry-filters" role="group" aria-label="Abonelik bitiş filtresi">{expiryChoices.map(([key,label])=><button key={key} aria-pressed={(filter.expiry??'TODAY')===key} className={(filter.expiry??'TODAY')===key?'selected':''} onClick={()=>change({...filter,expiry:key})}>{label} · {report.expirySummary[({TODAY:'today',WITHIN_3:'within_3',WITHIN_7:'within_7',WITHIN_30:'within_30',EXPIRED:'expired',UNKNOWN:'unknown',VALID:'valid',ALL:'total'} as const)[key]]}</button>)}</div>
        <p className="daily-description" role="status">Tekil uyarı: {report.expirySummary.warning} (dolmuş veya en fazla 7 gün). Bugün, 3, 7 ve 30 gün aralıkları iç içedir; sayıları toplanmaz. Hesap aktifliği, abonelik geçerliliği ve oturum durumu farklıdır.</p>
        <p className="daily-description">Bugünün Türkiye takvimine göre · erişilebilen demo ve kalıcı aboneler · rapor döneminden bağımsız. Kalıcı abone listesine router/hesap filtresi taşınır; paket, kaynak ve bitiş filtreleri bu ekranda uygulanır.</p>
        {report.expiryRows.length?<div className="table-scroll" role="region" tabIndex={0} aria-label="Abonelik bitişleri tablosu"><table className="data-table"><thead><tr><th>ABONE</th><th>ROUTER</th><th>KAYNAK</th><th>BİTİŞ TARİHİ</th><th>KALAN GÜN / DURUM</th><th>HIZLI İŞLEMLER</th></tr></thead><tbody>{report.expiryRows.map(row=><tr key={row.id}><td><a className="record-link" href={link('subscribers',row.id)}>{row.customer_name||row.username}</a></td><td>{row.router_name}</td><td><SourceBadge source={row.source}/></td><td>{expiryDate(row.expires_on)}</td><td>{remainingDays(expiryInfo(row.expires_on,turkeyToday(now)).days)}</td><td>{row.id.startsWith('demo-managed-sub-')?(()=>{const account=resource.data?.workspace?.accounts.find(a=>a.id===row.id);return account?<SubscriberQuickButtons compact status={account.status} label={account.customer_name} unavailableReason={canChangeWorkspaceItem(account,workspace)?undefined:workspaceActionUnavailableReason(account)} onAction={canChangeWorkspaceItem(account,workspace)?action=>setManaged({item:account,action}):undefined} onHistory={()=>{window.location.hash=link('subscribers',row.id)+'&tab=history';}}/>:null;})():<LegacySubscriberActions id={row.id} onHistory={()=>{window.location.hash=link('subscribers',row.id)+'&tab=history';}} onSelect={(detail,action)=>setQuick({detail,action})}/>}</td></tr>)}</tbody></table></div>:<p className="missing-data">Bu bitiş filtresinde kayıtlı sentetik abone yok.</p>}
      </section>
      <section ref={operationsSection} id="recent-operations" tabIndex={-1} className="panel central-events management-pppoe"><div className="panel-title"><h2>{filter.period==='LAST_24'?'Son 24 saat PPPoE ve yönetim işlemleri':'PPPoE ve yönetim işlemleri'}</h2><button className="record-link" onClick={()=>change({...filter,kind:'PPPOE'})}>Yalnız PPPoE</button></div>
      {report.workspaceError&&<p role="alert">Kalıcı işlem geçmişi alınamadı: {report.workspaceError}. Görünen kayıtlar yalnız erişilebilen sentetik kaynakları kapsar.</p>}
      {!workspace&&<p>Kalıcı işlem geçmişini görüntülemek için merkezi yönetim yetkisi gerekli; mevcut demo geçmişi gösteriliyor.</p>}
      {!report.historyAvailable&&<p className="missing-data">İşlem kaynağı eksik; toplam Veri yok. Yalnız alınabilen kayıtlar gösterilir.</p>}
      <dl className="management-outcomes" aria-label="Seçili dönemin işlem sonuçları">
        <div><dt>Başarılı · kayıtlı audit</dt><dd>{number(report.outcomes.applied)}</dd><small>Doğrulanmış sonuç</small></div>
        <div><dt>Başarısız · kayıtlı audit</dt><dd>{number(report.outcomes.failed)}</dd><small>{report.outcomes.failed===null?'Bu kapsam için başarısızlık kaynağı yok':'Değişiklik uygulanmadı'}</small></div>
        <div><dt>Sonucu belirsiz</dt><dd>Sayım yok</dd><small>UUID kanıtı olmayan istek başarı veya sıfır sayılmaz</small></div>
      </dl>
      {report.operations.length?<div className="table-scroll" role="region" tabIndex={0} aria-label="Günlük yönetim işlemleri tablosu"><table className="data-table"><thead><tr><th>ABONE / ROUTER</th><th>İŞLEM / SONUÇ</th><th>ZAMAN / AKTÖR · TÜRKİYE</th><th>İŞLEM ANINDAKİ KAYNAK</th><th>DEĞİŞEN DEĞERLER</th></tr></thead><tbody>{report.operations.map(item=>{const [previous,next]=historyValues(item);return <tr key={item.id}><td><a className="record-link" href={link('subscribers',item.subscriber_id)}>{item.customer_name||item.username||item.subscriber_id}</a><small>{item.router_id?<a className="record-link" href={link('routers',item.router_id)}>{names.get(item.router_id)??item.router_name}</a>:item.router_name||'Veri yok'}</small></td><td><button className="record-link" onClick={()=>setSelected({kind:'operation',id:item.id})}>{item.label??operationLabel(item.operation)}</button><small>{item.audit_result==='APPLIED'?'Başarılı · Audit kaydedildi':'Başarısız · Değişiklik uygulanmadı'}</small><small>{item.access_type==='PPPOE'?'PPPoE':item.access_type==='HOTSPOT'?'Hotspot':'Tür belirtilmemiş'} · {item.workspace?'Kalıcı çalışma alanı':'Mevcut demo'}</small></td><td>{dateTime(item.occurred_at)}<small>{item.actor_id}</small></td><td><SourceBadge source={item.source}/></td><td className="management-values">{item.audit_result==='FAILED'?'Uygulanmadı; güncel değer abone detayındadır.':<>{previous} → {next}</>}</td></tr>;})}</tbody></table></div>:<p className="missing-data">Veri yok. Filtrelerle eşleşen kayıtlı yönetim işlemi yok.</p>}
      </section>
      {center==='operations'&&<section className="panel router-inventory"><h2>Routerlar · kayıtlı dikkat durumları ve eksik ölçümler</h2><p>Örnekte OFFLINE/DEGRADED/Bilinmiyor veya eksik WAN/CPU/RAM dikkat kapsamındadır. Güncel bağlantı ölçülmedi; eski ONLINE kaydı sağlıklı durum kanıtı değildir.</p><div className="table-scroll" role="region" tabIndex={0} aria-label="Router dikkat kapsamı"><table className="data-table"><thead><tr><th>ROUTER</th><th>KAYITLI DURUM</th><th>WAN</th><th>CPU / RAM</th><th>ÖLÇÜM / YAŞ</th></tr></thead><tbody>{(resource.data?.routers??[]).filter(r=>!filter.router||r.id===filter.router).map(r=><tr key={r.id}><td><a className="record-link" href={link('routers',r.id)}>{r.name}</a><small>{r.site}</small></td><td>{savedConnectionLabel(r.status)}<small>Canlı durum bilinmiyor</small></td><td>{r.wan_snapshot?.ip??'Veri yok'}</td><td>{percentText(r.cpu_percent)} / {percentText(r.memory_percent)}</td><td>{dateTime(r.last_seen)}<small>{observationAge(r.last_seen,now.getTime())}</small></td></tr>)}</tbody></table></div><p>Kalıcı sentetik routerlar için canlı ölçüm kaynağı yok; envanter ve aboneler Router Merkezi'ndedir.</p></section>}
      <section className="panel central-events"><h2>İnternet ve WAN olayları</h2>{report.events===null?<p className="missing-data">Veri yok. Kaydedilmiş olay kaynağı yok; olay sayısı sıfır kabul edilmez.</p>:report.events.length?<div className="table-scroll" role="region" tabIndex={0} aria-label="Günlük bağlantı olayları tablosu"><table className="data-table"><thead><tr><th>OLAY / ROUTER</th><th>ZAMAN · TÜRKİYE</th><th>DOĞRULANMIŞ DURUM</th><th>OLAY BİLGİSİ</th></tr></thead><tbody>{report.events.map(item=><tr key={item.id}><td><button className="record-link" onClick={()=>setSelected({kind:'event',id:item.id})}>{eventLabels[item.kind as EventKind]}</button><small><a className="record-link" href={link('routers',item.router_id)}>{names.get(item.router_id)??item.router_id}</a></small></td><td>{dateTime(item.occurred_at)}</td><td>{alarmStatusLabels[item.lifecycle.status]}{item.lifecycle.ended_at&&<small>Bitiş: {dateTime(item.lifecycle.ended_at)}</small>}</td><td>{item.kind==='WAN_CHANGE'?`${item.lifecycle.previous_wan??'Veri yok'} → ${item.lifecycle.new_wan??'Veri yok'}`:<><span>{durationText(item.lifecycle.duration_seconds)}</span><small>Başlangıç: {dateTime(item.lifecycle.started_at)}</small></>}</td></tr>)}</tbody></table></div>:<p className="missing-data">Veri yok. Filtrelerle eşleşen kayıtlı bağlantı olayı yok.</p>}</section>
      <details className="panel management-notes"><summary>Veri kapsamı ve rapor bilgisi</summary>
        <p>{reportPeriods[filter.period]}: {expiryDate(report.range.start)} – {expiryDate(report.range.end)}. Gelecek ve zamanı doğrulanamayan kayıtlar dönem toplamına alınmaz. Okuma: {dateTime(resource.data?.read_at??null)}.</p>
        <p>Dönem ve olay filtresi işlem/olay listeleri ile kartlarına uygulanır; bitişler router kapsamındaki bugünkü kayıtlardır, geçmişe ait durum tahmini değildir.</p>
        <p>Mevcut demo geçmişi{workspace?' ve kalıcı çalışma alanının başarılı ve başarısız PPPoE audit kayıtları':' (kalıcı çalışma alanı için merkezi yönetici yetkisi gerekir)'}. Türü belirtilmemiş {number(report.untypedOperations)} işlem PPPoE sayılmaz. Hesap işlemi online oturum kanıtı değildir. Kalıcı abonelerin bitişleri de erişilebilen kayıt kapsamına dahildir.</p>
        {report.workspaceError&&<p>Kalıcı geçmiş: {report.workspaceError}</p>}
        <p>Doğrulanmış zaman çifti olmadan kesinti süresi hesaplanmaz. Kesinti ve geri gelme ayrı kayıttır, aynı kesinti iki kez sayılmaz.</p>
        <div className="daily-links"><a className="record-link" href="#module=subscribers&workspace=HISTORY">Merkezi İşlem Geçmişini aç</a><a className="record-link" href={'#'+new URLSearchParams({module:'dashboard',view:'OPERATIONS_REPORT',router_id:filter.router,start:report.range.start,end:report.range.end})}>Operasyon ve audit raporu</a></div>
      </details>
    </>}
    {operation&&<OperationDetails event={operation} onClose={()=>setSelected(null)} onSubscriber={id=>{window.location.hash=link('subscribers',id);}} onRouter={operation.router_id?()=>{window.location.hash=link('routers',operation.router_id!);}:undefined} onHistory={()=>{window.location.hash=link('subscribers',operation.subscriber_id)+'&tab=history';}} onAlarms={can(identity,operation.router_id,'can_view')?()=>{window.location.hash=operationContextHash('alarms',operation,operation.router_id!,window.location.hash);}:undefined} onReport={!operation.workspace&&can(identity,operation.router_id,'can_view_reports')?()=>{window.location.hash=operationContextHash('report',operation,operation.router_id!,window.location.hash);}:undefined}/>}
    {event&&<AlarmEventDetails event={event.lifecycle} routerName={names.get(event.router_id)??event.router_id} onClose={()=>setSelected(null)}/>}
  </div>;
}
