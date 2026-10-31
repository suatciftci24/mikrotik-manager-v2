import {useEffect, useState} from 'react';
import {useResource} from '../lib/useResource';
import {ResourceState} from './Resource';
import {SourceBadge} from './Status';

export type PppoeSnapshot={router_id:string;availability:'AVAILABLE'|'UNAVAILABLE';items:{account_id:string;source:'LOCAL'|'RADIUS';connected:boolean|null;ip_address:string|null;observed_at:string|null;source_status:'FRESH'|'STALE'|'UNKNOWN'}[];error:string|null;is_demo:boolean;read_only:true};
type Props={routerId?:string|null;isDemo:boolean;accountId?:string;source?:'LOCAL'|'RADIUS'|null};
const messages:Record<string,string>={DISABLED:'PPPoE veri kaynağı kapalı; bağlantı başlatılmadı.',DEMO_ISOLATED:'Demo izolasyonu etkin; gerçek PPPoE verisi sorgulanmaz.',INVALID_DATA:'PPPoE verisi doğrulanamadı.',TIMEOUT:'PPPoE verisi alınırken zaman aşımı oluştu.',CONNECTION_FAILED:'PPPoE verisi alınamadı.',AUTHORITY_MISMATCH:'Hesap kimliği veya LOCAL/RADIUS yetkili kaynağı eşleşmiyor; veri gösterilmedi.'};
const sourceStates={FRESH:'Güncel',STALE:'Eski',UNKNOWN:'Bilinmiyor'};
function validTime(i:PppoeSnapshot['items'][number]){
 return i.observed_at===null?i.source_status==='UNKNOWN':typeof i.observed_at==='string'&&/(Z|[+-]\d{2}:\d{2})$/.test(i.observed_at)&&Number.isFinite(Date.parse(i.observed_at))&&Date.parse(i.observed_at)<=Date.now()&&(i.source_status==='FRESH'||i.source_status==='STALE');
}
function observationTime(value:string|null){return value===null?'Bilinmiyor':new Intl.DateTimeFormat('tr-TR',{dateStyle:'medium',timeStyle:'medium',timeZone:'Europe/Istanbul'}).format(new Date(value))+' (Europe/Istanbul)';}
export function validPppoeSnapshot(value:unknown,id:string):value is PppoeSnapshot{
 if(!value||typeof value!=='object')return false;
 const data=value as PppoeSnapshot;
 return data.router_id===id&&data.is_demo===false&&data.read_only===true&&Array.isArray(data.items)&&
 (data.availability==='AVAILABLE'?data.error===null&&data.items.every(i=>i!==null&&typeof i==='object'&&validTime(i)&&typeof i.account_id==='string'&&!!i.account_id&&(i.source==='LOCAL'||i.source==='RADIUS')&&(i.connected===null||typeof i.connected==='boolean')&&(i.ip_address===null||typeof i.ip_address==='string'))&&new Set(data.items.map(i=>i.account_id)).size===data.items.length:data.availability==='UNAVAILABLE'&&data.items.length===0&&Object.hasOwn(messages,data.error??''));
}
export function PppoeObservations(props:Props){
 return <section aria-label="Salt okunur PPPoE gözlemleri"><h3>PPPoE · Salt okunur API</h3><p>Veri zamanı her gözlemde ayrı gösterilir; bilinmeyen zaman: Bilinmiyor. Hesap etkinliği çevrimiçi oturum kanıtı değildir. Güncellik eşiği 5 dakikadır.</p>
 {props.isDemo?<p role="status">Demo izolasyonu etkin; gerçek PPPoE verisi sorgulanmaz. LOCAL/RADIUS yalnız demo hesabının yetkili kaynağıdır.</p>:!props.routerId?<p role="status">Veri yok. Kayıtlı router kimliği bulunmuyor; ad üzerinden eşleştirme yapılmaz.</p>:<PppoeResource key={props.routerId} {...props} routerId={props.routerId}/>}</section>;
}
function PppoeResource(props:Props&{routerId:string}){
 const resource=useResource<PppoeSnapshot>(`/router-center/${encodeURIComponent(props.routerId)}/pppoe-observations`);
 return <PppoeObservationState {...props} {...resource}/>;
}
export function PppoeObservationState({routerId,accountId,source,data,loading,error,retry}:{routerId:string;accountId?:string;source?:'LOCAL'|'RADIUS'|null;data?:PppoeSnapshot;loading:boolean;error?:string;retry:()=>void}){
 const [,setClock]=useState(0);
 const invalid=data!==undefined&&!validPppoeSnapshot(data,routerId);
 // Expire displayed freshness locally; never fetch or poll the API.
 useEffect(()=>{
  if(loading||error||invalid||!data)return;
  const now=Date.now();
  const deadlines=data.items.filter(i=>i.source_status==='FRESH'&&i.observed_at!==null)
   .map(i=>Date.parse(i.observed_at!)+300001).filter(time=>time>now);
  if(!deadlines.length)return;
  const timer=setTimeout(()=>setClock(value=>value+1),Math.min(...deadlines)-now);
  return()=>clearTimeout(timer);
 });
 const items=data&&!invalid?data.items.filter(i=>!accountId||i.account_id===accountId):[];
 const mismatch=accountId&&items.some(i=>i.source!==source);
 const problem=error?'PPPoE API verisi alınamadı. Oturum ve yetkili kaynak doğrulanamadı.':invalid?'PPPoE API yanıtı doğrulanamadı; veri gösterilmedi.':mismatch?messages.AUTHORITY_MISMATCH:undefined;
 return <><ResourceState loading={loading} error={problem} retry={retry}/>{!loading&&!problem&&data&&(data.availability==='UNAVAILABLE'?<p role="status">{messages[data.error??'']}</p>:!items.length?<p role="status">Veri yok. {accountId?'Bu hesap için PPPoE gözlemi bulunmuyor.':'PPPoE gözlem listesi boş.'} Oturum durumu bilinmiyor.</p>:<div className="table-scroll"><table className="data-table"><thead><tr><th>Hesap kimliği</th><th>Yetkili kaynak</th><th>Son gözlemde oturum</th><th>IP adresi</th><th>Veri zamanı</th><th>Kaynak durumu</th></tr></thead><tbody>{items.map(i=><tr key={i.account_id}><td>{i.account_id}</td><td><SourceBadge source={i.source}/></td><td>{i.connected===null?'Bilinmiyor':i.connected?'Bağlı':'Bağlı değil'}</td><td>{i.ip_address??'Bilinmiyor'}</td><td>{observationTime(i.observed_at)}</td><td>{i.source_status==='FRESH'&&i.observed_at&&Date.now()-Date.parse(i.observed_at)>300000?sourceStates.STALE:sourceStates[i.source_status]}</td></tr>)}</tbody></table></div>)}</>;
}
