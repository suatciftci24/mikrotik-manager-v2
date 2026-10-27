import type { Subscriber } from './api.ts';

export function detailText(value: unknown): string {
  return typeof value==='string' && value.trim() && !['—','-','Veri yok'].includes(value.trim()) ? value.trim() : 'Veri yok';
}

function observationTime(value: unknown): string | null {
  if (typeof value!=='string') return null;
  const iso=/^(\d{4}-\d{2}-\d{2})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.exec(value);
  if (!iso) return null;
  // Date.parse normalizes impossible days (e.g. February 30); reject those first.
  const day=new Date(iso[1]+'T00:00:00Z');
  if (!Number.isFinite(day.getTime()) || day.toISOString().slice(0,10)!==iso[1] || !Number.isFinite(Date.parse(value))) return null;
  return value;
}

/** A saved inventory observation is neither a session start nor proof of connectivity. */
export function subscriberObservation(item: Subscriber) {
  if (item.is_demo!==true) throw new Error('Yalnız sentetik demo gözlem kayıtları gösterilebilir.');
  const seen=observationTime(item.last_seen);
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
