import type { SubscriberHistoryEvent } from './api.ts';
export function extensionDate(old: string | null, today: string, days: number): string {
  if (!old) return '';
  const date = new Date(`${old > today ? old : today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0,10);
}
export function operationLabel(event: SubscriberHistoryEvent) {
  return ({CREATE:'Abone oluşturma', PLAN:'Paket değişikliği', STATUS:'Durum değişikliği', EXTEND:'Abonelik uzatma'} as Record<string,string>)[event.action ?? ''] ?? (event.operation==='RENEWAL'?'Yenileme':({CREATE:'PPPoE abonesi oluşturma',PLAN_CHANGE:'Paket/profil değiştirme',STATUS_CHANGE:'Etkinlik durumu değiştirme'} as Record<string,string>)[event.operation]??'Bitiş tarihi düzenleme');
}
