import {observationAge} from '../lib/routerObservation';
import {percentText} from '../lib/routerReport';
import {linkedCenterHash} from '../lib/detailLinks';
import {PppoeObservations} from './PppoeObservations';
import {RouterSubscribers} from './RouterSubscribers';
import {useListFilter} from '../lib/useListFilter';
import {useEffect,useRef,useState,type KeyboardEvent,type ReactNode} from 'react';
import {useResource} from '../lib/useResource';
import {PageHeading} from './PageHeading';
import {Facts,ResourceState,dateTime} from './Resource';
import {alarmFilter,alarmHash,alarmKinds,alarmSeverityLabels,routerAlarmPath,routerAlarmTarget,type AlarmPage} from '../lib/alarms';
import {routerCenterPath,routerCenterTabs,routerCenterTabKeys,routerSectionTabs,primaryRouterTab,routerSubscriberListHash,validRouterCenter,routerCenterStatus,routerCenterError,eventLabel,type RouterCenterTab,type RouterCenterData} from '../lib/routerCenter';
const tabKeys=routerCenterTabKeys;
const dependencies=['/router-workspace/routers','/router-registry','/routers'] as const;
export function RouterDeviceCenter({id,onBack,actions,legacy,security}:{id:string;onBack:()=>void;actions?:ReactNode;legacy?:ReactNode;security?:ReactNode}){
 const resource=useResource<RouterCenterData>(routerCenterPath(id),undefined,dependencies);
 const [tab,setTab]=useListFilter('routers','router_tab',tabKeys,'overview');const heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{heading.current?.focus();window.scrollTo(0,0);},[id]);
 const data=resource.data;const error=(resource.error?routerCenterError(resource.error):undefined)||(data&&!validRouterCenter(data,id)?'Router kaynağı veya kayıt kimliği doğrulanamadı; detay gösterilmedi.':undefined);
 return <section className="screen-stack router-device-center"><button className="button-secondary detail-back" onClick={onBack}>← Geri dön</button><PageHeading eyebrow="ROUTER YÖNETİMİ · KAYITLI BİLGİLER" title="Router Detay Merkezi" description="Kaydedilmiş bilgiler gösterilir. Bu sayfa cihaz bağlantısı başlatmaz." headingRef={heading}/><ResourceState {...resource} error={error}/>
 {data&&!resource.loading&&!error&&<RouterDeviceCenterView data={data} tab={tab} onTab={setTab} actions={<>{data.source==='STATIC_DEMO'&&<RouterAlarmEntry routerId={data.item.id}/>}{actions}</>} legacy={legacy} security={security}/>}</section>;
}
function RouterAlarmEntry({routerId}:{routerId:string}){
 const resource=useResource<AlarmPage>(routerAlarmPath(routerId),undefined,['/alarms']);
 const data=resource.data,error=resource.error||(data&&data.is_demo!==true?'Sentetik alarm kaynağı doğrulanamadı.':undefined);
 const latest=data&&!resource.loading&&!error?data.items[0]:undefined;
 return <div className="router-alarm-entry" aria-label="Bu router için alarm bağlantıları"><ResourceState {...resource} error={error}/>{latest?<a className="button-secondary" href={routerAlarmTarget(routerId,latest.id)}>{latest.severity} · {alarmSeverityLabels[latest.severity]??'Bilinmiyor'} · {alarmKinds[latest.kind]} olay detayını aç</a>:data&&!resource.loading&&!error?<span>Bu router için kayıtlı alarm yok; ölçüm/veri yokluğu sağlıklı durum kanıtı değildir.</span>:null}{data&&!resource.loading&&!error&&data.total>1&&<a className="button-secondary" href={alarmHash({...alarmFilter(''),router_id:routerId})}>{data.total} router olayının tümünü aç</a>}</div>;
}
function RouterSection({data,tab,legacy,security}:{data:RouterCenterData;tab:Exclude<RouterCenterTab,'subscribers'>;legacy?:ReactNode;security?:ReactNode}){
 const [legacyOpen,setLegacyOpen]=useState(false);
 const r=data.item;const pending=r.status==='PENDING_VERIFICATION';
 return <div className="router-section">
 {tab==='pppoe'&&(data.is_demo?<PppoeObservations routerId={r.id} isDemo/>:<RouterDisclosure label="Mevcut salt okunur PPPoE gözlemleri"><PppoeObservations routerId={r.id} isDemo={false}/></RouterDisclosure>)}
 {tab==='overview'?<><Facts items={[["Veri kaynağı",data.source==='PERSISTENT_DEMO'?'Yerel V2 PostgreSQL · kalıcı sentetik kayıt':data.source==='STATIC_DEMO'?'Etiketli sentetik demo envanteri':pending?'Operatör beyanı · doğrulanmamış envanter':'Kaydedilmiş doğrulanmış cihaz envanteri'],['Konum',r.site||'Veri yok'],...(pending?[["Envanter açıklaması",r.inventory_description||'Veri yok'] as [string,string]]:[]),['Kayıt kimliği',r.id],['Son ölçüm zamanı',r.last_seen_at?dateTime(r.last_seen_at):'Veri yok · ölçüm kaydı yok']]}/><p>Eksik bilgiler tahmin edilmez. Son ölçüm zamanı cihazın şu an çevrimiçi olduğunu kanıtlamaz; son başarılı bağlantı zamanı ayrı gösterilir.</p>{legacy&&<details onToggle={e=>setLegacyOpen(e.currentTarget.open)}><summary>Mevcut demo raporları ve ilişkili aboneler</summary>{legacyOpen&&legacy}</details>}</>
 :data.source==='REGISTERED'&&(tab==='pppoe'||tab==='hotspot')?<><p>GERÇEK CİHAZ · SALT OKUNUR. Hesap değiştirme, silme, uzatma ve toplu işlem kapalıdır.</p>{data.read_snapshot?<><p>{tab==='pppoe'?'PPPoE hesap sayısı':'Hotspot hesap sayısı'}: <strong>{tab==='pppoe'?data.read_snapshot.pppoe_count??'Bilinmiyor (service=any kayıtları var)':data.read_snapshot.hotspot_count}</strong></p>{tab==='pppoe'&&<p>Açık service=pppoe: {data.read_snapshot.pppoe_explicit_count} · Türü any: {data.read_snapshot.ppp_any_count}</p>}<p>Kaydedilmiş okuma: {dateTime(data.read_snapshot.captured_at)}. Bu sayı oturum/çevrimiçi kullanıcı sayısı değildir. Kullanıcı adı ve parolalar alınmaz.</p></>:<p>{pending?'Doğrulama bekleyen envanter: gerçek veri okuması kapalı.':'Veri yok. Genel Durum içindeki mevcut Güvenli Bağlantı akışı ayrı onay gerektirir.'}</p>}</>
 :tab==='pppoe'||tab==='hotspot'?<RouterSubscribers key={r.id+tab} id={r.id} access={tab==='pppoe'?'PPPOE':'HOTSPOT'}/>
 :data.source==='REGISTERED'&&tab==='interfaces'&&data.read_snapshot?<><p>Kaydedilmiş salt okunur örnek: {dateTime(data.read_snapshot.captured_at)}</p><div className="table-scroll"><table className="data-table"><thead><tr><th>ARAYÜZ</th><th>TÜR</th><th>KAYITLI DURUM</th></tr></thead><tbody>{data.read_snapshot.interfaces.map(i=><tr key={i['.id']}><td>{i.name}</td><td>{i.type}</td><td>{i.disabled?'Devre dışı':i.running?'Son okumada running':'Son okumada running değil'}</td></tr>)}</tbody></table></div>{!data.read_snapshot.interfaces.length&&<p>Son okumada arayüz kaydı dönmedi.</p>}</>
 :data.source==='REGISTERED'&&tab==='wan'&&data.read_snapshot?<><p>WAN IP bilinmiyor; yönetim IP’si WAN yerine kullanılmaz. İnternet erişimi ölçülmedi.</p><p>Kaydedilmiş okuma: {dateTime(data.read_snapshot.captured_at)}</p>{data.read_snapshot.default_routes.length?<ul>{data.read_snapshot.default_routes.map((route,index)=><li key={index}>Default route · Gateway: {route.gateway} · {route.active&&!route.disabled?'Son okumada etkin':'Son okumada etkin değil'}</li>)}</ul>:<p>Son okumada default route kaydı dönmedi.</p>}</>
 :tab==='events'?<>{data.events.length?<ol className="registry-history">{data.events.map((event,index)=><li key={index}><strong>{eventLabel(event.action)}</strong><span>{dateTime(event.occurred_at)} · {event.actor_id}</span>{event.revision!==null&&<span>Revizyon {event.revision}</span>}</li>)}</ol>:<p>Kayıtlı olay bulunmuyor. Canlı bağlantı/kopma geçmişi kaynağı bağlı değil.</p>}<p>En fazla son 50 kayıt işlemi gösterilir; bunlar ağ olayları veya trafik ölçümleri değildir.</p></>
 :tab==='security'?<><p>{data.is_demo?'Bu router sentetiktir. Cihaz bağlantısı, parola veya sertifika gerektirmez.':pending?'Doğrulama bekliyor. Bu kayıt bağlantı izni vermez; canlı probe ve gerçek veri okuması kapalıdır.':'Yalnız mevcut envanterin doğrulanmış metadata bilgileri okunur. Gerçek onboarding varsayılan kapalıdır; bu sayfa bağlantı başlatmaz.'}</p><p>Gerçek onboarding ayrı onaylı akışta TLS CA zinciri, IP SAN ve SHA-256 pin denetimlerini kullanır. Parola, kullanıcı adı, CA içeriği ve credential referansı bu detayda gösterilmez.</p>{security}</>
 :<><p className="missing-data">{data.sections[tab]==='PREPARING'?'Veri yok. Hazırlanıyor. Bu modül için bağlı veri kaynağı henüz yok.':'Veri yok. Ölçülmedi. Bu sentetik kayıt için bu bölümde veri kaynağı yok.'}</p><p>{tab==='interfaces'?'Arayüz envanteri ve sayaçları':tab==='wan'?'WAN adresi, internet erişimi ve trafik':tab==='pppoe'?'PPPoE aboneleri ve oturumları':'Hotspot kullanıcıları ve oturumları'} bilinmiyor. Yönetim IP’si WAN IP’si veya abonelik kanıtı olarak kullanılmaz.</p></>}
 </div>;
}

export function RouterDeviceCenterView({data,tab,onTab,actions,legacy,security}:{data:RouterCenterData;tab:RouterCenterTab;onTab:(tab:RouterCenterTab)=>void;actions?:ReactNode;legacy?:ReactNode;security?:ReactNode}){
 const selected=primaryRouterTab(tab),r=data.item;
 const buttons=useRef<(HTMLButtonElement|null)[]>([]);
 function navigate(event:KeyboardEvent,index:number){
  const count=routerCenterTabs.length;
  const next=event.key==='ArrowRight'?(index+1)%count:event.key==='ArrowLeft'?(index+count-1)%count:event.key==='Home'?0:event.key==='End'?count-1:null;
  if(next===null)return;event.preventDefault();onTab(routerCenterTabs[next][0]);buttons.current[next]?.focus();
 }
 const section=(key:Exclude<RouterCenterTab,'subscribers'>)=><RouterSection data={data} tab={key} legacy={key==='overview'?legacy:undefined} security={security}/>;
 const disclosure=(key:Exclude<RouterCenterTab,'subscribers'>)=><RouterDisclosure key={key} initiallyOpen={tab===key} label={routerSectionTabs.find(([value])=>value===key)?.[1]??key}>{section(key)}</RouterDisclosure>;
 return <><div className="panel registry-detail router-device-summary"><div className="page-heading-row"><div><span className="eyebrow">{data.is_demo?'SENTETİK DEMO · CİHAZ BAĞLANTISI YOK':'KAYITLI CİHAZ · CANLI SORGULAMA YOK'}</span><h2>{r.name}</h2><p>{routerCenterStatus(data)}</p></div><div className="heading-actions">{actions}</div></div>
 <Facts items={[
 ['Yönetim IP',r.management_address||'Veri yok'],['Model',r.model||'Veri yok'],['CPU',percentText(r.cpu_percent)],['RAM',percentText(r.memory_percent)],
 ['Son görülme / ölçüm',r.last_seen_at?dateTime(r.last_seen_at):'Veri yok'],['Ölçüm güncelliği',observationAge(r.last_seen_at)],['Son başarılı bağlantı',r.last_success_at?dateTime(r.last_success_at):'Veri yok · bağlantı kanıtı yok']
 ]}/></div>
 <div className="router-device-tabs filter-tabs" role="tablist" aria-label="Router detay bölümleri">{routerCenterTabs.map(([key,label],index)=><button key={key} ref={node=>{buttons.current[index]=node;}} id={'router-tab-'+key} role="tab" aria-selected={selected===key} aria-controls={'router-panel-'+key} tabIndex={selected===key?0:-1} className={selected===key?'selected':''} onClick={()=>onTab(key)} onKeyDown={e=>navigate(e,index)}>{label}</button>)}</div>
 <section className="panel registry-detail router-device-panel" role="tabpanel" id={'router-panel-'+selected} aria-labelledby={'router-tab-'+selected} tabIndex={0}><h2>{routerCenterTabs.find(([key])=>key===selected)?.[1]}</h2>
 {selected==='overview'?<>{section('overview')}<Facts items={[["Router kimliği",r.identity||'Veri yok'],['RouterOS',r.routeros_version||'Veri yok'],['Uptime',r.uptime||'Veri yok']]}/>{disclosure('security')}</>
 :selected==='wan'?<>{section('wan')}{disclosure('interfaces')}</>
 :selected==='subscribers'?<>{data.is_demo&&<a className="button-secondary" href={linkedCenterHash(routerSubscriberListHash(r.id),typeof window==='undefined'?'':window.location.hash)}>Abone Merkezi’nde bu routerı aç</a>}<label className="form-label router-access-filter">Abone türü<select value={tab==='hotspot'?'HOTSPOT':'PPPOE'} onChange={e=>onTab(e.target.value==='HOTSPOT'?'hotspot':'pppoe')}><option value="PPPOE">PPPoE</option><option value="HOTSPOT">Hotspot</option></select></label>{section(tab==='hotspot'?'hotspot':'pppoe')}</>
 :<>{section('events')}{data.source==='STATIC_DEMO'&&<a className="button-secondary" href={alarmHash({...alarmFilter(''),router_id:r.id})}>Bu router’ın alarm ve olaylarını aç</a>}</>}
 </section></>;
}

function RouterDisclosure({label,initiallyOpen=false,children}:{label:string;initiallyOpen?:boolean;children:ReactNode}){
 const [open,setOpen]=useState(initiallyOpen);
 return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>{label}</summary>{open&&children}</details>;
}
