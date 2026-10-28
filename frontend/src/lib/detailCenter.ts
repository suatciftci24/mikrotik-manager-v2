import type { Router, Subscriber } from './api.ts';
import { assignedToRouter } from './routerSubscribers.ts';
import { buildSubscriptionAlerts } from './subscriptionAlerts.ts';
import { expiryInfo } from './expiry.ts';
import { detailText } from './subscriberObservation.ts';
import { subscriberSource } from './source.ts';

export function routerDetailSummary(router:Router,subscribers:Subscriber[],today:string) {
  if(router.is_demo!==true || subscribers.some(s=>s.is_demo!==true)) throw new Error('Detay özeti yalnız sentetik kayıtları destekler.');
  const assigned=subscribers.filter(s=>assignedToRouter(s,router));
  if(new Set(assigned.map(s=>s.id)).size!==assigned.length)throw new Error('İlişkili abone kimlikleri tekil değil.');
  return {total:assigned.length,pppoe:assigned.filter(s=>s.access_type==='PPPOE').length,
    active:assigned.filter(s=>s.status==='ACTIVE').length,paused:assigned.filter(s=>s.status==='PAUSED').length,
    pending:assigned.filter(s=>s.status==='PENDING').length,alerts:buildSubscriptionAlerts(assigned,today)};
}
export function subscriberWarnings(s:Subscriber,today:string) {
  const warnings:string[]=[];const expiry=expiryInfo(s.expires_on,today);
  if(subscriberSource(s.source)==='UNKNOWN')warnings.push('Yetkili kaynak bilinmiyor; değişiklik yapılamaz.');
  if(expiry.days===null)warnings.push('Bitiş tarihi bilinmiyor; kalan gün hesaplanamaz.');
  else if(expiry.days<0)warnings.push(`Abonelik ${-expiry.days} gün önce doldu.`);
  else if(expiry.days===0)warnings.push('Abonelik bugün bitiyor.');
  else if(expiry.days<=7)warnings.push(`Abonelik ${expiry.days} gün içinde bitiyor.`);
  if(s.status==='PAUSED')warnings.push('Hesap devre dışı (duraklatıldı); bu durum oturum kanıtı değildir.');
  if(s.status==='PENDING')warnings.push('Hesap bekliyor; yetkili kaynak ve kayıt bilgilerini inceleyin.');
  return warnings;
}
export function assignedRouter(s:Subscriber,routers:Router[]) {
  if(s.router_id)return routers.find(r=>r.id===s.router_id);
  const matches=routers.filter(r=>r.name===s.router_name);
  return matches.length===1?matches[0]:undefined;
}
export function routerSubscribersHash(routerName:string) {
  return '#'+new URLSearchParams({module:'subscribers',router:routerName,bulk:'1'}).toString();
}
export function subscriberTextContext(hash:string,key:string) {
  const params=new URLSearchParams(hash.replace(/^#/,''));
  return params.get('module')==='subscribers'?(params.get(key)??'').slice(0,200):'';
}

export function unknownDetail(value:unknown){const text=detailText(value);return text==='Veri yok'?'Bilinmiyor':text;}
