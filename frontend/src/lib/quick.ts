import {expiryInfo} from './expiry.ts';
import type { SubscriberHistoryEvent } from './api.ts';
export function extensionDate(old: string | null, today: string, days: number): string {
  if (!old || expiryInfo(old,today).days===null || !Number.isInteger(days) || days<=0) return '';
  const date = new Date(`${old > today ? old : today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  if (!Number.isFinite(date.getTime())) return '';
  const result=date.toISOString().slice(0,10);
  return /^\d{4}-\d{2}-\d{2}$/.test(result)?result:'';
}
export function operationLabel(event: SubscriberHistoryEvent) {
  return ({CREATE:'Abone oluşturma', PLAN:'Paket değişikliği', STATUS:'Durum değişikliği', EXTEND:'Abonelik uzatma'} as Record<string,string>)[event.action ?? ''] ?? (event.operation==='RENEWAL'?'Yenileme':({CREATE:'PPPoE abonesi oluşturma',PLAN_CHANGE:'Paket/profil değiştirme',STATUS_CHANGE:'Etkinlik durumu değiştirme'} as Record<string,string>)[event.operation]??'Bitiş tarihi düzenleme');
}
