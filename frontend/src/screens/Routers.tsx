import { RouterReport } from '../components/RouterReport';
import { buildRouterReport, connectionStatus, percentText } from '../lib/routerReport';
import { useListFilter } from '../lib/useListFilter';
import { DetailCenter } from './Details';
import { ResourceState, dateTime } from '../components/Resource';
import { useResource } from '../lib/useResource';
import { useDetailNavigation } from '../lib/useDetailNavigation';
import { useMemo, useState } from 'react';
import { Cpu, HardDrive, MoreHorizontal, Plus, RefreshCw, Router as RouterIcon, Search } from 'lucide-react';
import { type Router } from '../lib/api';
import { StatusBadge } from '../components/Status';

const ROUTER_FILTERS = ['ALL','ONLINE','OFFLINE','DEGRADED','UNKNOWN'] as const;
const ROUTER_VIEWS = ['LIST','REPORT'] as const;
export function Routers({ onToast }: { onToast: (message: string) => void }) {
  const [view,setView]=useListFilter('routers','view',ROUTER_VIEWS,'LIST');
  const navigation = useDetailNavigation('routers');
  const resource = useResource<{items: Router[]}>('/routers');
  const routers = resource.data?.items ?? [];
  const [query, setQuery] = useState(''); const [filter, setFilter] = useListFilter('routers','status',ROUTER_FILTERS,'ALL');
  const filtered = useMemo(() => routers.filter(router => (filter === 'ALL' || connectionStatus(router.status) === filter) && `${router.name} ${router.site} ${router.model}`.toLowerCase().includes(query.toLowerCase())), [routers, filter, query]);
  const inventorySummary=useMemo(()=>{try{return buildRouterReport(routers);}catch{return null;}},[routers]);
  const online = routers.filter(router => router.status === 'ONLINE').length;
  return <><div hidden={!!navigation.selected}><div className="screen-stack"><section className="page-heading-row"><div><div className="eyebrow"><span className="eyebrow-line" />NETWORK INVENTORY</div><h1>Router Merkezi</h1><p>Router envanterini ve ağ sağlığını tek yerden görüntüleyin.</p></div><div className="heading-actions"><button className="button-secondary" onClick={()=>setView(view==='REPORT'?'LIST':'REPORT')}>{view==='REPORT'?'Router listesine dön':'Kullanım ve bağlantı raporu'}</button><button className="button-secondary" onClick={resource.retry}><RefreshCw size={15} />Yenile</button><button className="button-primary" onClick={() => onToast('Router ekleme Phase 2 kapsamında.')}><Plus size={16} />Router ekle</button></div></section>
    {view==='REPORT'?<RouterReport items={filtered} total={routers.length} loading={resource.loading} error={resource.error} retry={resource.retry} query={query} onQuery={setQuery} filter={filter} onFilter={value=>setFilter(value as typeof filter)} onOpen={navigation.open}/>:<>
    <div className="router-stats" hidden={resource.loading || !!resource.error}><div><span>Toplam router</span><strong>{routers.length}<small> cihaz</small></strong></div><div><span>Online envanter kaydı</span><strong className="green-value">{online}<small> / {routers.length}</small></strong></div><div><span>Sentetik abone sayacı</span><strong>{routers.reduce((n,r)=>n+r.subscriber_count,0).toLocaleString('tr-TR')}</strong></div><div><span>Ortalama CPU</span><strong>{percentText(inventorySummary?.cpu.average)}</strong></div></div>
    <p className="expiry-context">Son sentetik envanter durumlarıdır; son görülme aktif bağlantı veya internet erişimi kanıtı değildir.</p>
    <section className="panel router-inventory"><div className="inventory-toolbar"><div className="filter-tabs"><button className={filter==='ALL'?'selected':''} onClick={()=>setFilter('ALL')}>Tümü <b>{routers.length}</b></button><button className={filter==='ONLINE'?'selected':''} onClick={()=>setFilter('ONLINE')}>Çevrimiçi <b>{online}</b></button><button className={filter==='DEGRADED'?'selected':''} onClick={()=>setFilter('DEGRADED')}>Dikkat <b>{routers.filter(r=>r.status==='DEGRADED').length}</b></button><button className={filter==='OFFLINE'?'selected':''} onClick={()=>setFilter('OFFLINE')}>Çevrimdışı <b>{routers.filter(r=>r.status==='OFFLINE').length}</b></button><button className={filter==='UNKNOWN'?'selected':''} onClick={()=>setFilter('UNKNOWN')}>Bilinmiyor <b>{routers.filter(r=>connectionStatus(r.status)==='UNKNOWN').length}</b></button></div><label className="table-search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Router ara..." /></label><button className="icon-button"><MoreHorizontal size={17}/></button></div>
      <ResourceState {...resource}/><div className="table-scroll" hidden={resource.loading || !!resource.error}><table className="data-table"><thead><tr><th>ROUTER</th><th>DURUM</th><th>CPU / BELLEK</th><th>ABONE</th><th>SON GÖRÜLME</th><th /></tr></thead><tbody>{filtered.map(router=><tr key={router.id} onClick={()=>navigation.open(router.id)} className="clickable-row"><td><span className={`table-router-icon ${connectionStatus(router.status).toLowerCase()}`}><RouterIcon size={16}/></span><span className="table-main"><strong><button className="record-link" onClick={e=>{e.stopPropagation();navigation.open(router.id);}}>{router.name}</button></strong><small>{router.management_address} <i>·</i> {router.model}</small></span></td><td><StatusBadge status={connectionStatus(router.status)}/></td><td><span className="resource-cell"><span><Cpu size={13}/>{percentText(router.cpu_percent)}</span><span><HardDrive size={13}/>{percentText(router.memory_percent)}</span></span></td><td><span className="subscriber-total">{router.subscriber_count}</span></td><td><span className="seen-cell"><span className="fresh-dot"/> {dateTime(router.last_seen)}</span></td><td><button className="icon-button row-menu" aria-label={`${router.name} detayını aç`} onClick={e=>{e.stopPropagation();navigation.open(router.id);}}><MoreHorizontal size={17}/></button></td></tr>)}</tbody></table>{!resource.loading&&!resource.error&&filtered.length===0&&<div className="table-empty">Aramanızla eşleşen router bulunamadı.</div>}</div>
      <div className="table-footer" hidden={resource.loading || !!resource.error}><span>{filtered.length} router gösteriliyor <i>·</i> <b>Sentetik demo verisi</b></span><span>1–{filtered.length} <button disabled>‹</button><button disabled>›</button></span></div></section>

    </>}
  </div></div>{navigation.selected&&<DetailCenter kind="routers" backLabel={view==='REPORT'?'Rapora dön':'Listeye dön'} id={navigation.selected} onBack={navigation.back}/>}</>;
}
