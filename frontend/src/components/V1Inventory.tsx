import {useResource} from '../lib/useResource';
import {ResourceState, dateTime} from './Resource';
type Inventory={source:'V1_INVENTORY_EXPORT';is_demo:false;availability:'AVAILABLE'|'NO_DATA';items:{id:string;name:string;identity:string|null;model:string|null;routeros_version:string|null;status:'NO_DATA';freshness:'RECENT'|'STALE'|'NO_DATA';sampled_at:string|null;cpu_load_percent:number|null;memory_used_percent:number|null}[]};
export function V1Inventory(){
 const resource=useResource<Inventory>('/v1-inventory');
 const data=resource.data;
 const valid=data?.source==='V1_INVENTORY_EXPORT'&&data.is_demo===false&&Array.isArray(data.items);
 return <section className="panel"><h2>Gerçek V1 envanteri · salt okunur aktarım</h2><p>Kaynak: V1_INVENTORY_EXPORT. Geçmiş ölçümler güncel çevrimiçi durum kanıtı değildir. Canlı cihaz bağlantısı yapılmaz.</p><ResourceState {...resource}/>{!resource.loading&&!resource.error&&(valid?<><table className="data-table"><thead><tr><th>Cihaz / kimlik</th><th>Model / RouterOS</th><th>Durum</th><th>CPU / Bellek</th><th>Son veri</th></tr></thead><tbody>{data.items.map(row=><tr key={row.id}><td>{row.name} / {row.identity??'Veri yok'}</td><td>{row.model??'Veri yok'} / {row.routeros_version??'Veri yok'}</td><td>Veri yok</td><td>{row.cpu_load_percent==null?'Veri yok':`${row.cpu_load_percent}%`} / {row.memory_used_percent==null?'Veri yok':`${row.memory_used_percent}%`}</td><td>{dateTime(row.sampled_at)} · {row.freshness==='STALE'?'Eski':row.freshness==='RECENT'?'Yakın tarihli kayıt':'Veri yok'}</td></tr>)}</tbody></table>{data.items.length===0&&<p>Veri yok · güvenilir gerçek envanter aktarımı sağlanmadı.</p>}</>:<p role="alert">Veri yok · kaynak doğrulanamadı.</p>)}</section>;
}
