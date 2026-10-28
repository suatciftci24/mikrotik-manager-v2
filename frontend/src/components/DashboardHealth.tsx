import { api } from '../lib/api';
import { assertMikaAnalysis, filterMikaEvents, mikaStatus, type MikaAnalysis } from '../lib/mikajani';
import { useResource } from '../lib/useResource';
import { ResourceState, dateTime } from './Resource';
const dependencies=['/subscribers','/routers'] as const;
async function load(path:string,init?:RequestInit){return assertMikaAnalysis(await api<MikaAnalysis>(path,init));}
export function DashboardHealth(){
  const resource=useResource<MikaAnalysis>('/mikajani/analysis',load,dependencies);
  return <section className="panel operations-health" aria-label="MikAjanı operasyon özeti"><h2>MikAjanı · ağ operasyonları</h2>
    <p>DEMO / SENTETİK · Salt okunur kayıt analizi. WAN/IPsec sinyalleri canlı telemetri değildir; eksik veya eski gözlem sağlıklı sayılmaz.</p>
    <ResourceState {...resource}/>{resource.data&&!resource.loading&&!resource.error&&<DashboardHealthView data={resource.data}/>}
  </section>;
}
export function DashboardHealthView({data}:{data:MikaAnalysis}){
  const active=filterMikaEvents(data.events,{query:'',priority:'ALL',state:'ACTIVE',router:'',domain:'ALL'});
  const affected=new Set(active.flatMap(event=>event.affected_router_ids));
  return <>
    <p>{data.operational_summary}</p><p>Analiz: {dateTime(data.evaluated_at)} · Yanıt: {dateTime(data.generated_at)} · Kaynak: {data.source}</p>
    <div className="daily-links" aria-label="MikAjanı öncelik filtreleri">{(['P1','P2','P3','P4'] as const).map(priority=><a className="button-secondary" key={priority} href={'#module=mikajani&priority='+priority+'&state=ACTIVE'}>{priority} · {active.filter(event=>event.priority===priority).length}</a>)}</div>
    <p>Açık / güncellenen / iyileşen: {active.length} · Etkilenen router: {affected.size} · Çözülen: {data.events.filter(event=>event.state==='RESOLVED').length}</p>
    <a className="text-link" href="#module=mikajani&state=ACTIVE">MikAjanı açık olaylarını incele</a>
    {active.length>0&&<ol className="daily-operations">{active.slice(0,5).map(event=><li key={event.id}><a className="record-link" href={'#'+new URLSearchParams({module:'mikajani',priority:event.priority,state:'ACTIVE',event:event.id})}>{event.priority} · {event.title}</a><span>{mikaStatus[event.state]} · {dateTime(event.updated_at)}</span></li>)}</ol>}
    <div className="table-scroll" role="region" tabIndex={0} aria-label="Operasyon WAN ve IPsec özeti"><table className="data-table"><thead><tr><th>ROUTER</th><th>WAN</th><th>IPSEC</th><th>VERİ GÜVENİLİRLİĞİ</th><th>SON GÖZLEM</th></tr></thead><tbody>{data.health.map(router=><tr key={router.router_id}><td><a className="record-link" href={'#'+new URLSearchParams({module:'routers',id:router.router_id})}>{router.name}</a>{affected.has(router.router_id)&&<span> · Açık olay</span>}</td><td>{mikaStatus[router.signals.WAN]??'Bilinmiyor'}</td><td>{mikaStatus[router.signals.IPSEC]??'Bilinmiyor'}</td><td>{mikaStatus[router.reliability]??'Bilinmiyor'}</td><td>{dateTime(router.latest_observed_at)}</td></tr>)}</tbody></table></div>
    {data.health.length===0&&<p className="missing-data">Veri yok: router gözlem kaynağı boş.</p>}
    {active.length===0&&<p className="table-empty">Kayıtlı açık MikAjanı olayı yok; eksik veri sağlıklı bağlantı kanıtı değildir.</p>}
    <div className="daily-links" aria-label="Sorunlu routerlara hızlı erişim">{data.health.filter(router=>affected.has(router.router_id)||router.health!=='HEALTHY').map(router=><a key={router.router_id} className="button-secondary" href={'#'+new URLSearchParams({module:'routers',id:router.router_id})}>{router.name} · {mikaStatus[router.health]??'Bilinmiyor'}</a>)}</div>
  </>;
}
