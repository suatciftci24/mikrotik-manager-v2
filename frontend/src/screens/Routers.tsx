import {CompactRouterList} from '../components/CompactRouterList';
import {SubscriberDisclosure} from '../components/CompactSubscriberList';
import {useSubscriberTextFilter} from '../lib/useSubscriberTextFilter';
import {observationAge,savedConnectionLabel} from '../lib/routerObservation';
import {SourcePicker} from '../components/SourcePicker';
import {routerSources} from '../lib/workspaceContext';
import {V1Inventory} from '../components/V1Inventory';
import {RouterInventoryOnboarding} from '../components/RouterInventoryOnboarding';
import {invalidateResources} from '../lib/resourceEvents';
import type {RegisteredRouter} from '../lib/routerRegistry';
import {useIdentity} from '../lib/permissions';
import { RouterReport } from '../components/RouterReport';
import { buildRouterReport, connectionStatus, percentText } from '../lib/routerReport';
import { useListFilter } from '../lib/useListFilter';
import { DetailCenter } from './Details';
import { ResourceState, dateTime } from '../components/Resource';
import { useResource } from '../lib/useResource';
import { useDetailNavigation } from '../lib/useDetailNavigation';
import { lazy, Suspense, useCallback, useMemo, useState, useEffect } from 'react';
import { Cpu, HardDrive, Plus, RefreshCw, Router as RouterIcon, Search } from 'lucide-react';
import { api, type Router } from '../lib/api';

const RegisteredRouterCenter=lazy(()=>import('../components/RouterOnboarding').then(module=>({default:module.RegisteredRouterCenter})));
const RouterDeviceCenter=lazy(()=>import('../components/RouterDeviceCenter').then(module=>({default:module.RouterDeviceCenter})));
const CebeciPilotOnboarding=lazy(()=>import('../components/CebeciPilotOnboarding').then(module=>({default:module.CebeciPilotOnboarding})));
const RouterOnboarding=lazy(()=>import('../components/RouterOnboarding').then(module=>({default:module.RouterOnboarding})));

const RouterRegistryList=lazy(()=>import('../components/RouterRegistryList').then(module=>({default:module.RouterRegistryList})));
const DemoRouterWorkspace=lazy(()=>import('../components/DemoRouterWorkspace').then(module=>({default:module.DemoRouterWorkspace})));
const ROUTER_SOURCES=['DEMO','MANAGED_DEMO','REGISTERED','V1_INVENTORY'] as const;
const ROUTER_FILTERS = ['ALL','ONLINE','OFFLINE','DEGRADED','UNKNOWN'] as const;
const ROUTER_VIEWS = ['LIST','REPORT'] as const;
export function Routers({ onToast }: { onToast: (message: string) => void }) {
  const identity=useIdentity();const admin=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
  const [source,setSource]=useListFilter('routers','source',ROUTER_SOURCES,'DEMO');
  const [pilot,setPilot]=useState(false);
  const [inventory,setInventory]=useState(false);
  const [onboarding,setOnboarding]=useState<{item?:RegisteredRouter}|null>(null);
  const [view,setView]=useListFilter('routers','view',ROUTER_VIEWS,'LIST');
  const navigation = useDetailNavigation('routers');
  useEffect(()=>{const id=navigation.selected;if(id?.startsWith('demo-managed-router-')&&source!=='MANAGED_DEMO')setSource('MANAGED_DEMO');else if(id?.startsWith('registered-')&&source!=='REGISTERED')setSource('REGISTERED');},[navigation.selected,source,setSource]);
  // Each source owns its reads. Real inventory must never fetch demo routers.
  const loadDemoRouters=useCallback((path:string,init?:RequestInit)=>source==='DEMO'?api<{items:Router[]}>(path,init):Promise.resolve({items:[]}),[source]);
  const resource = useResource<{items: Router[]}>('/routers',loadDemoRouters);
  const routers = resource.data?.items ?? [];
  const [query, setQuery] = useSubscriberTextFilter('query','routers'); const [filter, setFilter] = useListFilter('routers','status',ROUTER_FILTERS,'ALL');
  const filtered = useMemo(() => routers.filter(router => (filter === 'ALL' || connectionStatus(router.status) === filter) && `${router.name} ${router.site} ${router.model} ${router.management_address} ${router.wan_snapshot?.ip??''}`.toLocaleLowerCase('tr-TR').includes(query.trim().toLocaleLowerCase('tr-TR'))), [routers, filter, query]);
  const inventorySummary=useMemo(()=>{try{return buildRouterReport(routers);}catch{return null;}},[routers]);
  const online = routers.filter(router => router.status === 'ONLINE').length;
  return <Suspense fallback={<p role="status">Router Merkezi yükleniyor…</p>}><><div className="router-center-list" hidden={!!navigation.selected}><div className="screen-stack"><section className="page-heading-row"><div><div className="eyebrow"><span className="eyebrow-line" />NETWORK INVENTORY</div><h1>Router Merkezi</h1><p>Envanter, güvenli cihaz kaydı ve bağlantı doğrulaması tek merkezde.</p></div><div className="heading-actions"><button className="button-secondary" hidden={source!=='DEMO'} onClick={()=>setView(view==='REPORT'?'LIST':'REPORT')}>{view==='REPORT'?'Router listesine dön':'Kullanım ve bağlantı raporu'}</button><button className="button-secondary" hidden={source!=='DEMO'} onClick={()=>invalidateResources(['/routers','/router-registry','/router-workspace/routers','/v1-inventory'])}><RefreshCw size={15} />Yenile</button>{admin&&source==='REGISTERED'&&<button className="button-primary" onClick={()=>setOnboarding({})}><Plus size={16} />Gerçek router formu</button>}</div></section>
    <p className="subscriber-mobile-note">{source==='DEMO'||source==='MANAGED_DEMO'?'SENTETİK · Canlı durum ölçülmüyor.':'KAYITLI VERİ · Canlı durum bilinmiyor.'}</p><SourcePicker value={source} options={admin?routerSources:routerSources.filter(option=>option.value==='DEMO')} onChange={value=>setSource(value as typeof source)}>
      {admin&&source==='REGISTERED'&&<details className="source-actions"><summary>Kayıt ve pilot işlemleri</summary><div><button className="button-secondary" onClick={()=>setInventory(true)}>Bağlantısız envanter kaydı</button><button className="button-secondary" onClick={()=>setPilot(true)}>Salt okunur pilot hazırlığı</button></div></details>}
    </SourcePicker>
    {!admin&&source!=='DEMO'?<p role="alert">Bu veri kaynağı için merkezi yönetim yetkisi gerekli.</p>:source==='V1_INVENTORY'&&admin?<>{!navigation.selected&&<V1Inventory/>}</>:source==='MANAGED_DEMO'&&admin?<DemoRouterWorkspace onOpen={navigation.open}/>:source==='REGISTERED'&&admin?<RouterRegistryList onOpen={navigation.open}/>:view==='REPORT'?<RouterReport items={filtered} total={routers.length} loading={resource.loading} error={resource.error} retry={resource.retry} query={query} onQuery={setQuery} filter={filter} onFilter={value=>setFilter(value as typeof filter)} onOpen={navigation.open}/>:<>
    <SubscriberDisclosure label="Özet ve veri kapsamı">    <div className="router-stats" hidden={resource.loading || !!resource.error}><div><span>Toplam router</span><strong>{routers.length}<small> cihaz</small></strong></div><div><span>Örnekte ONLINE</span><strong>{online}<small> / {routers.length}</small></strong></div><div><span>Sentetik abone sayacı</span><strong>{routers.reduce((n,r)=>n+r.subscriber_count,0).toLocaleString('tr-TR')}</strong></div><div><span>Ortalama CPU</span><strong>{percentText(inventorySummary?.cpu.average)}</strong></div></div>
    <p className="expiry-context">Durum, WAN, CPU ve bellek son kaydedilmiş örnektir; canlı ölçüm değildir. Ölçüm zamanı ve son başarılı bağlantı detayda ayrı gösterilir.</p>
</SubscriberDisclosure>
    <section className="panel router-inventory"><div className="inventory-toolbar"><SubscriberDisclosure><div className="filter-tabs"><button className={filter==='ALL'?'selected':''} onClick={()=>setFilter('ALL')}>Tümü <b>{routers.length}</b></button><button className={filter==='ONLINE'?'selected':''} onClick={()=>setFilter('ONLINE')}>Örnekte ONLINE <b>{online}</b></button><button className={filter==='DEGRADED'?'selected':''} onClick={()=>setFilter('DEGRADED')}>Dikkat <b>{routers.filter(r=>r.status==='DEGRADED').length}</b></button><button className={filter==='OFFLINE'?'selected':''} onClick={()=>setFilter('OFFLINE')}>Örnekte OFFLINE <b>{routers.filter(r=>r.status==='OFFLINE').length}</b></button><button className={filter==='UNKNOWN'?'selected':''} onClick={()=>setFilter('UNKNOWN')}>Bilinmiyor <b>{routers.filter(r=>connectionStatus(r.status)==='UNKNOWN').length}</b></button></div></SubscriberDisclosure><label className="table-search"><Search size={15}/><input aria-label="Router adı, konumu, modeli veya IP adresine göre ara" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Router ara..." /></label></div>
      <ResourceState {...resource}/>{!resource.loading&&!resource.error&&<CompactRouterList key={JSON.stringify([query,filter])} rows={filtered.map(router=>({id:router.id,name:router.name,status:savedConnectionLabel(router.status),wan:router.wan_snapshot?.ip,measuredAt:router.last_seen}))} onOpen={navigation.open}/>}<div className="table-scroll" tabIndex={0} role="region" aria-label="Router envanter tablosu" hidden={resource.loading || !!resource.error}><table className="data-table"><thead><tr><th>ROUTER</th><th>DURUM KAYDI</th><th>WAN</th><th>CPU / RAM</th><th>ABONE</th><th>SON GÖRÜLME / ÖLÇÜM</th><th>VERİ KAYNAĞI</th></tr></thead><tbody>{filtered.map(router=><tr key={router.id} onClick={()=>navigation.open(router.id)} className="clickable-row"><td><span className="table-router-icon"><RouterIcon size={16}/></span><span className="table-main"><strong><button className="record-link" onClick={e=>{e.stopPropagation();navigation.open(router.id);}}>{router.name}</button></strong><small>{router.management_address} <i>·</i> {router.model}</small></span></td><td><span className="saved-router-status">{savedConnectionLabel(router.status)}</span><small className="registry-table-error">Canlı durum bilinmiyor</small></td><td><span className="wan-cell">{router.wan_snapshot?.ip||'Veri yok'}{router.wan_snapshot?.interface&&<small>{router.wan_snapshot.interface}{router.wan_snapshot.gateway?` · Ağ geçidi ${router.wan_snapshot.gateway}`:''}</small>}</span></td><td><span className="resource-cell"><span><Cpu size={13}/>{percentText(router.cpu_percent)}</span><span><HardDrive size={13}/>{percentText(router.memory_percent)}</span></span></td><td><span className="subscriber-total">{router.subscriber_count}</span></td><td><span className="seen-cell">{dateTime(router.last_seen)}<small>{observationAge(router.last_seen)}</small></span></td><td>Sentetik demo · kayıtlı örnek</td></tr>)}</tbody></table>{!resource.loading&&!resource.error&&filtered.length===0&&<div className="table-empty">Aramanızla eşleşen router bulunamadı.</div>}</div>
      <div className="table-footer" hidden={resource.loading || !!resource.error}><span>{filtered.length} router gösteriliyor</span></div></section>

    </>}
  </div></div>{navigation.selected&&(navigation.selected.startsWith('demo-managed-router-')?(admin?<DemoRouterWorkspace key={navigation.selected} detailId={navigation.selected} onOpen={navigation.open} onBack={navigation.back}/>:<p role="alert">Sentetik kayıt detayı için merkezi yönetim yetkisi gerekli.</p>):navigation.selected.startsWith('registered-')?(admin?<RegisteredRouterCenter key={navigation.selected} id={navigation.selected} onBack={navigation.back} onEdit={item=>setOnboarding({item})}/>:<p role="alert">Kayıtlı cihazlar için merkezi yönetim yetkisi gerekli.</p>):<RouterDeviceCenter key={navigation.selected} id={navigation.selected} onBack={navigation.back} legacy={<DetailCenter kind="routers" backLabel={view==='REPORT'?'Rapora dön':'Listeye dön'} id={navigation.selected} onBack={navigation.back}/>}/>)}{inventory&&admin&&<RouterInventoryOnboarding onClose={()=>setInventory(false)} onSaved={id=>{setInventory(false);setSource('REGISTERED');onToast('Envanter kaydedildi · doğrulama bekliyor.');navigation.open(id);}}/>}{pilot&&admin&&<CebeciPilotOnboarding pilotIdentity={identity?.pilot_identity} onClose={()=>setPilot(false)} onSaved={id=>{setPilot(false);setSource('REGISTERED');onToast('Gerçek salt okunur pilot V2 envanterine kaydedildi.');navigation.open(id);}}/>}{onboarding&&admin&&<RouterOnboarding key={onboarding.item?.id??'new'} item={onboarding.item} onPilot={()=>{setOnboarding(null);setPilot(true);}} onClose={()=>setOnboarding(null)} onSaved={id=>{setOnboarding(null);setSource('REGISTERED');onToast('Doğrulanmış router kaydı kaydedildi.');navigation.open(id);}}/>}</></Suspense>;
}
