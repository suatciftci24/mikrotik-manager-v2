/** Saved observations never establish current reachability, regardless of their age. */
export function observationAge(value:unknown,now=Date.now()):string {
 if(typeof value!=='string'||!/(Z|[+-]\d{2}:\d{2})$/.test(value))return 'Güncellik bilinmiyor';
 const time=Date.parse(value);
 if(!Number.isFinite(time)||!Number.isFinite(now)||time>now)return 'Güncellik bilinmiyor';
 const minutes=Math.floor((now-time)/60_000);
 if(minutes<1)return '1 dakikadan yeni kayıt';
 if(minutes<60)return `${minutes} dk önce kaydedildi`;
 if(minutes<1440)return `${Math.floor(minutes/60)} sa önce kaydedildi`;
 return `${Math.floor(minutes/1440)} gün önce kaydedildi`;
}
export function savedConnectionLabel(status:unknown):string {
 return ({ONLINE:'Örnekte ONLINE',OFFLINE:'Örnekte OFFLINE',DEGRADED:'Örnekte dikkat'}[String(status)]??'Bilinmiyor');
}
