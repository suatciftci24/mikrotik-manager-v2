import type { Subscriber } from './api.ts';

export function detailText(value: unknown): string {
  return typeof value==='string' && value.trim() && !['—','-','Veri yok'].includes(value.trim()) ? value.trim() : 'Veri yok';
}

/** A saved inventory observation is neither a session start nor proof of connectivity. */
export function subscriberObservation(item: Subscriber) {
  if (item.is_demo!==true) throw new Error('Yalnız sentetik demo gözlem kayıtları gösterilebilir.');
  const value=item.last_seen;
  const seen=typeof value==='string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)) ? value : null;
  return {
    ip:detailText(item.ip_address),
    last_seen:seen,
    // The V2 subscriber contract has no session or per-subscriber byte-counter source.
    session_status:null, last_connection:null, session_duration:null,
  };
}

export function monthlyPriceText(value: unknown): string {
  return typeof value==='number' && Number.isFinite(value) && value>=0
    ? new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY'}).format(value)
    : 'Veri yok';
}
