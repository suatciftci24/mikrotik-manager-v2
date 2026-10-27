import { buildRouterReport } from './routerReport.ts';
import { api, type Router, type SubscriberDetailData, type SubscriberHistoryEvent } from './api.ts';
import { expiryInfo, turkeyToday } from './expiry.ts';
import { subscriberSource } from './source.ts';

export type DailyOperation = SubscriberHistoryEvent & {subscriber_id: string; customer_name: string; router_name:string; username:string; access_type:'PPPOE'|null};
export type DailySummary = {
  generated_at: string; as_of_date: string; is_demo: true;
  routers: Router[];
  router_counts: {total: number; online: number; offline: number; degraded: number; unknown: number};
  subscribers: {total: number; active: number; paused: number; pending: number; unknown_status: number; local: number; radius: number; unknown_source: number};
  expiry: {expired: number; within_7: number; within_30: number; active: number; unknown: number};
  pppoe: {confirmed: number; untyped: number};
  operation_history: DailyOperation[];
  operations: {today: number; total: number; recent: DailyOperation[]};
};

/** Read projection of existing versioned API records; never uses aggregate demo counters. */
export function buildDailySummary(routers: Router[], details: SubscriberDetailData[], now = new Date()): DailySummary {
  if (routers.some(r=>r.is_demo!==true) || details.some(d=>d.is_demo!==true || d.item.is_demo!==true)) throw new Error('Günlük özet yalnız sentetik demo kayıtlarını destekler.');
  const routerReport = buildRouterReport(routers, now);
  const today = turkeyToday(now);
  const items = details.map(d=>d.item);
  if (new Set(items.map(s=>s.id)).size !== items.length) throw new Error('Abone kayıtları tekil değil; özet oluşturulamadı.');
  const expiry = {expired: 0, within_7: 0, within_30: 0, active: 0, unknown: 0};
  const operations: DailyOperation[] = [];
  for (const detail of details) {
    const info = expiryInfo(detail.item.expires_on, today);
    if (info.status === 'UNKNOWN') expiry.unknown++;
    else if (info.status === 'EXPIRED') expiry.expired++;
    else if (info.status === 'ACTIVE') expiry.active++;
    if (info.days !== null && info.days >= 0 && info.days <= 7) expiry.within_7++;
    if (info.days !== null && info.days >= 0 && info.days <= 30) expiry.within_30++;
    if (!Array.isArray(detail.history)) throw new Error('Abonelik işlem geçmişi alınamadı.');
    for (const event of detail.history) {
      if (event.is_demo !== true || !/(?:Z|[+-]\d{2}:\d{2})$/.test(event.occurred_at) || !Number.isFinite(Date.parse(event.occurred_at))) throw new Error('İşlem geçmişinin kaynak veya zaman bilgisi doğrulanamadı.');
      operations.push({...event, subscriber_id: detail.item.id, customer_name: detail.item.customer_name, router_name:detail.item.router_name||'Veri yok', username:detail.item.username||'Veri yok', access_type:detail.item.access_type??null});
    }
  }
  if (new Set(operations.map(event=>event.id)).size !== operations.length) throw new Error('İşlem geçmişi tekil değil; özet oluşturulamadı.');
  operations.sort((a,b)=>Date.parse(b.occurred_at)-Date.parse(a.occurred_at) || a.id.localeCompare(b.id));
  return {
    generated_at: now.toISOString(), as_of_date: today, is_demo: true, routers,
    router_counts: routerReport.counts,
    subscribers: {total: items.length, active: items.filter(s=>s.status==='ACTIVE').length, paused: items.filter(s=>s.status==='PAUSED').length, pending: items.filter(s=>s.status==='PENDING').length, unknown_status: items.filter(s=>!['ACTIVE','PAUSED','PENDING'].includes(s.status)).length, local: items.filter(s=>subscriberSource(s.source)==='LOCAL').length, radius: items.filter(s=>subscriberSource(s.source)==='RADIUS').length, unknown_source: items.filter(s=>subscriberSource(s.source)==='UNKNOWN').length},
    pppoe: {confirmed:items.filter(item=>item.access_type==='PPPOE').length, untyped:items.filter(item=>!item.access_type).length},
    expiry, operation_history:operations, operations: {today: operations.filter(event=>turkeyToday(new Date(event.occurred_at))===today).length, total: operations.length, recent: operations.slice(0,5)},
  };
}

/** Existing demo inventory is small; each authenticated detail provides a consistent item/history pair. */
export async function loadDailySummary(_path: string, init: RequestInit = {}): Promise<DailySummary> {
  const [routers, subscribers] = await Promise.all([api<{items: Router[]}>('/routers', init), api<{items: {id: string}[]}>('/subscribers', init)]);
  const details = await Promise.all(subscribers.items.map(s=>api<SubscriberDetailData>(`/subscribers/${encodeURIComponent(s.id)}`, init)));
  return buildDailySummary(routers.items, details);
}
