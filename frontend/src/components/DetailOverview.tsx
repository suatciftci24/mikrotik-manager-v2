import type { Router, Subscriber } from '../lib/api';
import { useResource } from '../lib/useResource';
import { api } from '../lib/api';
import { assertMikaAnalysis, mikaStatus, type MikaAnalysis } from '../lib/mikajani';
import { assignedRouter, routerDetailSummary, routerSubscribersHash, subscriberWarnings } from '../lib/detailCenter';
import { DetailSection, Facts, ResourceState, dateTime } from './Resource';
const dependencies=['/routers','/subscribers','/router-events'] as const;
async function loadHealth(path:string,init?:RequestInit){return assertMikaAnalysis(await api<MikaAnalysis>(path,init));}

export function RouterOverview({router,subscribers,today}:{router:Router;subscribers:Subscriber[];today:string}) {
  let summary;
  try{summary=routerDetailSummary(router,subscribers,today);}catch(error){return <DetailSection title="Router yönetim özeti"><p role="alert">{error instanceof Error?error.message:'Özet hesaplanamadı.'}</p></DetailSection>;}
  return <section className="panel detail-overview" aria-label="Router yönetim özeti"><div><span className="demo-chip">SENTETİK</span><h2>{router.name}</h2><p>{router.id} · Kalıcı V2 aboneleri · Canlı oturum sayımı değildir.</p></div><div className="detail-metrics"><span>İlişkili <strong>{summary.total}</strong></span><span>PPPoE <strong>{summary.pppoe}</strong></span><span>Etkin hesap <strong>{summary.active}</strong></span><span>Pasif hesap <strong>{summary.paused}</strong></span><span>Süresi dolmuş <strong>{summary.alerts.expired}</strong></span><span>7 günde bitecek <strong>{summary.alerts.within_7}</strong></span></div><a className="button-secondary" href={routerSubscribersHash(router.name)}>Bu router abonelerinde toplu uzatmaya git</a></section>;
}
export function RouterSignals({router}:{router:Router}) {
  const resource=useResource<MikaAnalysis>('/mikajani/analysis',loadHealth,dependencies);
  const health=resource.data?.health.find(h=>h.router_id===router.id);
  return <DetailSection title="WAN / IPsec ve izleme güvenilirliği"><p>Mevcut MikAjanı kayıtlı kaynak analizi; canlı ölçüm değildir. IPsec kaydı yoksa Bilinmiyor gösterilir.</p><ResourceState {...resource}/>{!resource.loading&&!resource.error&&<><Facts items={[
    ['WAN / internet gözlemi',mikaStatus[health?.signals.WAN??'UNKNOWN']],['IPsec bağlantısı',mikaStatus[health?.signals.IPSEC??'UNKNOWN']],
    ['İzleme kanıtı',mikaStatus[health?.signals.MONITOR??'UNKNOWN']],['Veri güncelliği',mikaStatus[health?.reliability??'MISSING']],
    ['Son kaynak gözlemi',dateTime(health?.latest_observed_at??null)],
  ]}/><a className="record-link" href="#module=mikajani">MikAjanı analizini aç</a></>}</DetailSection>;
}
export function SubscriberWarnings({subscriber,today}:{subscriber:Subscriber;today:string}) {
  const warnings=subscriberWarnings(subscriber,today);
  return <section className="panel detail-overview detail-warnings" aria-label="Abonelik uyarıları"><h2>Abonelik uyarıları</h2><div role="status" aria-live="polite">{warnings.length?<ul>{warnings.map(text=><li key={text}>{text}</li>)}</ul>:<p>Kayıtlı bitiş ve hesap durumu için uyarı yok. Bu sonuç canlı bağlantı sağlığı anlamına gelmez.</p>}</div></section>;
}
export function SubscriberRouterLinks({subscriber}:{subscriber:Subscriber}) {
  const resource=useResource<{items:Router[]}>('/routers');const router=assignedRouter(subscriber,resource.data?.items??[]);
  return <div className="detail-links"><a className="button-secondary" href={routerSubscribersHash(subscriber.router_name)}>Aynı routerda toplu uzatmaya git</a>{router&&<a className="button-secondary" href={'#'+new URLSearchParams({module:'routers',id:router.id})}>Router detayını aç</a>}{resource.error&&<p role="alert">Router bağlantısı doğrulanamadı: {resource.error}</p>}</div>;
}
