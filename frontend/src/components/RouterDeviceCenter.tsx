import {RouterSubscribers} from './RouterSubscribers';
import {useListFilter} from '../lib/useListFilter';
import {useEffect,useRef,useState,type KeyboardEvent,type ReactNode} from 'react';
import {useResource} from '../lib/useResource';
import {PageHeading} from './PageHeading';
import {Facts,ResourceState,dateTime} from './Resource';
import {routerCenterPath,routerCenterTabs,validRouterCenter,routerCenterStatus,routerCenterError,eventLabel,type RouterCenterTab,type RouterCenterData} from '../lib/routerCenter';
const tabKeys=routerCenterTabs.map(([key])=>key);
const dependencies=['/router-workspace/routers','/router-registry','/routers'] as const;
export function RouterDeviceCenter({id,onBack,actions,legacy,security}:{id:string;onBack:()=>void;actions?:ReactNode;legacy?:ReactNode;security?:ReactNode}){
 const resource=useResource<RouterCenterData>(routerCenterPath(id),undefined,dependencies);
 const [tab,setTab]=useListFilter('routers','router_tab',tabKeys,'overview');const heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{heading.current?.focus();window.scrollTo(0,0);},[id]);
 const data=resource.data;const error=(resource.error?routerCenterError(resource.error):undefined)||(data&&!validRouterCenter(data,id)?'Router kaynağı veya kayıt kimliği doğrulanamadı; detay gösterilmedi.':undefined);
 return <section className="screen-stack router-device-center"><button className="button-secondary detail-back" onClick={onBack}>← Router listesine dön</button><PageHeading eyebrow="ROUTER YÖNETİMİ · KAYITLI BİLGİLER" title="Router Detay Merkezi" description="Kaydedilmiş bilgiler gösterilir. Bu sayfa cihaz bağlantısı başlatmaz." headingRef={heading}/><ResourceState {...resource} error={error}/>
 {data&&!resource.loading&&!error&&<RouterDeviceCenterView data={data} tab={tab} onTab={setTab} actions={actions} legacy={legacy} security={security}/>}</section>;
}
export function RouterDeviceCenterView({data,tab,onTab,actions,legacy,security}:{data:RouterCenterData;tab:RouterCenterTab;onTab:(tab:RouterCenterTab)=>void;actions?:ReactNode;legacy?:ReactNode;security?:ReactNode}){
 const [legacyOpen,setLegacyOpen]=useState(false);
 const r=data.item;const prefix=data.is_demo?'Sentetik örnek':'Kayıtlı değer';
 const buttons=useRef<(HTMLButtonElement|null)[]>([]);
 function navigate(event:KeyboardEvent,index:number){
  let next=index;if(event.key==='ArrowRight')next=(index+1)%routerCenterTabs.length;else if(event.key==='ArrowLeft')next=(index+routerCenterTabs.length-1)%routerCenterTabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=routerCenterTabs.length-1;else return;
  event.preventDefault();onTab(routerCenterTabs[next][0]);buttons.current[next]?.focus();
 }
 return <><div className="panel registry-detail router-device-summary"><div className="page-heading-row"><div><span className="eyebrow">{data.is_demo?'SENTETİK DEMO · CİHAZ BAĞLANTISI YOK':'KAYITLI CİHAZ · CANLI SORGULAMA YOK'}</span><h2>{r.name}</h2><p>{routerCenterStatus(data)}</p></div>{actions}</div><Facts items={[
 ['Router kimliği',r.identity??'Bilinmiyor'],['Model',r.model??'Bilinmiyor'],['RouterOS',r.routeros_version??'Bilinmiyor'],['Yönetim IP',r.management_address],
 ['Son başarılı bağlantı',r.last_success_at?dateTime(r.last_success_at):'Bilinmiyor · bağlantı kanıtı yok'],
 [`${prefix} CPU`,r.cpu_percent===null?'Ölçülmedi':`${r.cpu_percent}%`],[`${prefix} RAM`,r.memory_percent===null?'Ölçülmedi':`${r.memory_percent}%`],[`${prefix} uptime`,r.uptime??'Ölçülmedi']
 ]}/></div>
 <div className="router-device-tabs filter-tabs" role="tablist" aria-label="Router detay bölümleri">{routerCenterTabs.map(([key,label],index)=><button key={key} ref={node=>{buttons.current[index]=node;}} id={`router-tab-${key}`} role="tab" aria-selected={tab===key} aria-controls={`router-panel-${key}`} tabIndex={tab===key?0:-1} className={tab===key?'selected':''} onClick={()=>onTab(key)} onKeyDown={e=>navigate(e,index)}>{label}</button>)}</div>
 <section className="panel registry-detail router-device-panel" role="tabpanel" id={`router-panel-${tab}`} aria-labelledby={`router-tab-${tab}`} tabIndex={0}>
 <h2>{routerCenterTabs.find(([key])=>key===tab)?.[1]}</h2>
 {tab==='overview'?<><Facts items={[["Veri kaynağı",data.source==='PERSISTENT_DEMO'?'Yerel V2 PostgreSQL · kalıcı sentetik kayıt':data.source==='STATIC_DEMO'?'Etiketli sentetik demo envanteri':'Kaydedilmiş doğrulanmış cihaz envanteri'],['Konum',r.site||'Belirtilmemiş'],['Kayıt kimliği',r.id],['Geçmiş örnek zamanı',r.last_seen_at?dateTime(r.last_seen_at):'Bilinmiyor']]}/><p>Eksik bilgiler tahmin edilmez. Geçmiş bir kontrol veya sentetik örnek, cihazın şu an çevrimiçi olduğunu kanıtlamaz.</p>{legacy&&<details onToggle={e=>setLegacyOpen(e.currentTarget.open)}><summary>Mevcut demo raporları ve ilişkili aboneler</summary>{legacyOpen&&legacy}</details>}</>
 :data.source==='REGISTERED'&&(tab==='pppoe'||tab==='hotspot')?<><p>GERÇEK CİHAZ · SALT OKUNUR. Hesap değiştirme, silme, uzatma ve toplu işlem kapalıdır.</p>{data.read_snapshot?<><p>{tab==='pppoe'?'PPPoE hesap sayısı':'Hotspot hesap sayısı'}: <strong>{tab==='pppoe'?data.read_snapshot.pppoe_count??'Bilinmiyor (service=any kayıtları var)':data.read_snapshot.hotspot_count}</strong></p>{tab==='pppoe'&&<p>Açık service=pppoe: {data.read_snapshot.pppoe_explicit_count} · Türü any: {data.read_snapshot.ppp_any_count}</p>}<p>Kaydedilmiş okuma: {dateTime(data.read_snapshot.captured_at)}. Bu sayı oturum/çevrimiçi kullanıcı sayısı değildir. Kullanıcı adı ve parolalar alınmaz.</p></>:<p>Hazırlanıyor. Güvenli Bağlantı sekmesinden ayrı onayla salt okunur detay okuması gerekir.</p>}</>
 :tab==='pppoe'||tab==='hotspot'?<RouterSubscribers key={r.id+tab} id={r.id} access={tab==='pppoe'?'PPPOE':'HOTSPOT'}/>
 :data.source==='REGISTERED'&&tab==='interfaces'&&data.read_snapshot?<><p>Kaydedilmiş salt okunur örnek: {dateTime(data.read_snapshot.captured_at)}</p><div className="table-scroll"><table className="data-table"><thead><tr><th>ARAYÜZ</th><th>TÜR</th><th>KAYITLI DURUM</th></tr></thead><tbody>{data.read_snapshot.interfaces.map(i=><tr key={i['.id']}><td>{i.name}</td><td>{i.type}</td><td>{i.disabled?'Devre dışı':i.running?'Son okumada running':'Son okumada running değil'}</td></tr>)}</tbody></table></div>{!data.read_snapshot.interfaces.length&&<p>Son okumada arayüz kaydı dönmedi.</p>}</>
 :data.source==='REGISTERED'&&tab==='wan'&&data.read_snapshot?<><p>WAN IP bilinmiyor; yönetim IP’si WAN yerine kullanılmaz. İnternet erişimi ölçülmedi.</p><p>Kaydedilmiş okuma: {dateTime(data.read_snapshot.captured_at)}</p>{data.read_snapshot.default_routes.length?<ul>{data.read_snapshot.default_routes.map((route,index)=><li key={index}>Default route · Gateway: {route.gateway} · {route.active&&!route.disabled?'Son okumada etkin':'Son okumada etkin değil'}</li>)}</ul>:<p>Son okumada default route kaydı dönmedi.</p>}</>
 :tab==='events'?<>{data.events.length?<ol className="registry-history">{data.events.map((event,index)=><li key={index}><strong>{eventLabel(event.action)}</strong><span>{dateTime(event.occurred_at)} · {event.actor_id}</span>{event.revision!==null&&<span>Revizyon {event.revision}</span>}</li>)}</ol>:<p>Kayıtlı olay bulunmuyor. Canlı bağlantı/kopma geçmişi kaynağı bağlı değil.</p>}<p>En fazla son 50 kayıt işlemi gösterilir; bunlar ağ olayları veya trafik ölçümleri değildir.</p></>
 :tab==='security'?<><p>{data.is_demo?'Bu router sentetiktir. Cihaz bağlantısı, parola veya sertifika gerektirmez.':'Yalnız mevcut envanterin doğrulanmış metadata bilgileri okunur. Gerçek onboarding varsayılan kapalıdır; bu sayfa bağlantı başlatmaz.'}</p><p>Gerçek onboarding ayrı onaylı akışta TLS CA zinciri, IP SAN ve SHA-256 pin denetimlerini kullanır. Parola, kullanıcı adı, CA içeriği ve credential referansı bu detayda gösterilmez.</p>{security}</>
 :<><p className="missing-data">{data.sections[tab]==='PREPARING'?'Hazırlanıyor. Bu modül için bağlı veri kaynağı henüz yok.':'Ölçülmedi. Bu sentetik kayıt için bu bölümde veri kaynağı yok.'}</p><p>{tab==='interfaces'?'Arayüz envanteri ve sayaçları':tab==='wan'?'WAN adresi, internet erişimi ve trafik':tab==='pppoe'?'PPPoE aboneleri ve oturumları':'Hotspot kullanıcıları ve oturumları'} bilinmiyor. Yönetim IP’si WAN IP’si veya abonelik kanıtı olarak kullanılmaz.</p></>}
 </section></>;
}
