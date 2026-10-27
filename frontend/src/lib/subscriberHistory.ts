import type { SubscriberHistoryEvent } from './api.ts';
import { expiryDate } from './expiry.ts';

export function operationLabel(operation: SubscriberHistoryEvent['operation']) {
  return ({RENEWAL:'Yenileme (demo)', DATE_EDIT:'Bitiş tarihi düzenleme (demo)', CREATE:'PPPoE abonesi oluşturma (demo)', PLAN_CHANGE:'Paket/profil değiştirme (demo)', STATUS_CHANGE:'Etkinlik durumu değiştirme (demo)'})[operation] ?? 'Bilinmeyen demo işlemi';
}
export function statusText(value: unknown): string {
  return value==='ACTIVE'?'Etkin':value==='PAUSED'?'Devre dışı (duraklatıldı)':value==='PENDING'?'Bekliyor':'Veri yok';
}
const fields: Record<string,string> = {username:'Kullanıcı adı', customer_name:'Abone adı', router_name:'Router', source:'Yetkili kaynak', plan:'Paket/profil', monthly_price:'Aylık tutar', status:'Durum', expires_on:'Bitiş', access_type:'Erişim türü'};
export function valuesText(values: Record<string,string|number|null> | undefined) {
  if (!values || Object.keys(values).length===0) return 'Kayıt yok';
  return Object.entries(values).map(([key,value])=>{
    const text = key==='status' ? statusText(value) : key==='expires_on' ? expiryDate(typeof value==='string'?value:null) : key==='monthly_price'&&typeof value==='number' ? new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY'}).format(value) : value===null?'Veri yok':String(value);
    return `${fields[key]??key}: ${text}`;
  }).join(' · ');
}
export function historyValues(event: SubscriberHistoryEvent) {
  return event.operation==='RENEWAL'||event.operation==='DATE_EDIT'
    ? [expiryDate(event.previous_expires_on??null), expiryDate(event.expires_on??null)]
    : [valuesText(event.previous_values), valuesText(event.new_values)];
}
