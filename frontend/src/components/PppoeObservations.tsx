import {useResource} from '../lib/useResource';
import {ResourceState} from './Resource';
import {SourceBadge} from './Status';

export type PppoeSnapshot={router_id:string;availability:'AVAILABLE'|'UNAVAILABLE';items:{account_id:string;source:'LOCAL'|'RADIUS';connected:boolean|null;ip_address:string|null}[];error:string|null;is_demo:boolean;read_only:true};
type Props={routerId?:string|null;isDemo:boolean;accountId?:string;source?:'LOCAL'|'RADIUS'|null};
const messages:Record<string,string>={DISABLED:'PPPoE veri kaynağı kapalı; bağlantı başlatılmadı.',DEMO_ISOLATED:'Demo izolasyonu etkin; gerçek PPPoE verisi sorgulanmaz.',INVALID_DATA:'PPPoE verisi doğrulanamadı.',TIMEOUT:'PPPoE verisi alınırken zaman aşımı oluştu.',CONNECTION_FAILED:'PPPoE verisi alınamadı.',AUTHORITY_MISMATCH:'Hesap kimliği veya LOCAL/RADIUS yetkili kaynağı eşleşmiyor; veri gösterilmedi.'};
export function validPppoeSnapshot(data:PppoeSnapshot,id:string){
 return data.router_id===id&&data.is_demo===false&&data.read_only===true&&Array.isArray(data.items)&&
 (data.availability==='AVAILABLE'?data.error===null&&new Set(data.items.map(i=>i.account_id)).size===data.items.length&&data.items.every(i=>typeof i.account_id==='string'&&!!i.account_id&&(i.source==='LOCAL'||i.source==='RADIUS')&&(i.connected===null||typeof i.connected==='boolean')&&(i.ip_address===null||typeof i.ip_address==='string')):data.availability==='UNAVAILABLE'&&data.items.length===0&&Object.hasOwn(messages,data.error??''));
}
export function PppoeObservations(props:Props){
 return <section aria-label="Salt okunur PPPoE gözlemleri"><h3>PPPoE · Salt okunur API</h3><p>Son veri zamanı: Bilinmiyor · API gözlem zamanı sağlamıyor. Hesap etkinliği çevrimiçi oturum kanıtı değildir.</p>
 {props.isDemo?<p role="status">Demo izolasyonu etkin; gerçek PPPoE verisi sorgulanmaz. LOCAL/RADIUS yalnız demo hesabının yetkili kaynağıdır.</p>:!props.routerId?<p role="status">Veri yok. Kayıtlı router kimliği bulunmuyor; ad üzerinden eşleştirme yapılmaz.</p>:<PppoeResource key={props.routerId} {...props} routerId={props.routerId}/>}</section>;
}
function PppoeResource(props:Props&{routerId:string}){
 const resource=useResource<PppoeSnapshot>(`/router-center/${encodeURIComponent(props.routerId)}/pppoe-observations`);
 return <PppoeObservationState {...props} {...resource}/>;
}
export function PppoeObservationState({routerId,accountId,source,data,loading,error,retry}:{routerId:string;accountId?:string;source?:'LOCAL'|'RADIUS'|null;data?:PppoeSnapshot;loading:boolean;error?:string;retry:()=>void}){
 const invalid=data&&!validPppoeSnapshot(data,routerId);
 const items=data&&!invalid?data.items.filter(i=>!accountId||i.account_id===accountId):[];
 const mismatch=accountId&&items.some(i=>i.source!==source);
 const problem=error?'PPPoE API verisi alınamadı. Oturum ve yetkili kaynak doğrulanamadı.':invalid?'PPPoE API yanıtı doğrulanamadı; veri gösterilmedi.':mismatch?messages.AUTHORITY_MISMATCH:undefined;
 return <><ResourceState loading={loading} error={problem} retry={retry}/>{!loading&&!problem&&data&&(data.availability==='UNAVAILABLE'?<p role="status">{messages[data.error??'']}</p>:!items.length?<p role="status">Veri yok. {accountId?'Bu hesap için PPPoE gözlemi bulunmuyor.':'PPPoE gözlem listesi boş.'} Oturum durumu bilinmiyor.</p>:<div className="table-scroll"><table className="data-table"><thead><tr><th>Hesap kimliği</th><th>Yetkili kaynak</th><th>Son gözlemde oturum</th><th>IP adresi</th></tr></thead><tbody>{items.map(i=><tr key={i.account_id}><td>{i.account_id}</td><td><SourceBadge source={i.source}/></td><td>{i.connected===null?'Bilinmiyor':i.connected?'Bağlı':'Bağlı değil'}</td><td>{i.ip_address??'Bilinmiyor'}</td></tr>)}</tbody></table></div>)}</>;
}
