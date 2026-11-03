import {routerHealth} from '../lib/routerHealth';
import {useEffect,useRef,useState,type ReactNode} from 'react';
import {api} from '../lib/api';
import {inventoryRefresh} from '../lib/inventoryRefresh';
import {ResourceState,dateTime,Facts} from './Resource';
export type Inventory={source:'V1_INVENTORY_EXPORT';is_demo:false;availability:'AVAILABLE'|'NO_DATA';items:{id:string;name:string;identity:string|null;model:string|null;routeros_version:string|null;status:'NO_DATA';health_source:'V1_ROUTER_HEALTH_SAMPLES'|null;health_sample_id:string|null;connection_status:'NO_DATA'|'LAST_PROBE_SUCCEEDED'|'LAST_PROBE_FAILED';freshness:'RECENT'|'STALE'|'NO_DATA';sampled_at:string|null;cpu_load_percent:number|null;memory_used_percent:number|null}[]};
type Row=Inventory['items'][number];
export type InventoryState={data?:Inventory|null;loading:boolean;error?:string;lastSuccess?:number|null};
const percent=(n:number|null)=>n==null?'Veri yok':`${n}%`;
const probe=(row:Row)=>row.connection_status==='LAST_PROBE_SUCCEEDED'?'Son internet denemesi başarılı':row.connection_status==='LAST_PROBE_FAILED'?'Son internet denemesi başarısız':'Veri yok';
export function freshness(row:Row,now:number){
 const time=row.sampled_at?Date.parse(row.sampled_at):NaN;
 return !Number.isFinite(time)||time>now?'Veri yok':now-time>300_000?'Güncel değil':'Son bilinen ölçüm';
}
export function validInventory(data:unknown):data is Inventory{
 if(!data||typeof data!=='object')return false;
 const value=data as Inventory;
 if(value.source!=='V1_INVENTORY_EXPORT'||value.is_demo!==false||!['AVAILABLE','NO_DATA'].includes(value.availability)||!Array.isArray(value.items))return false;
 const nullableString=(s:unknown)=>s===null||typeof s==='string';
 const metric=(n:unknown)=>n===null||typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=100;
 return value.items.every(row=>row&&typeof row==='object'&&typeof row.id==='string'&&typeof row.name==='string'&&
  [row.identity,row.model,row.routeros_version,row.health_sample_id].every(nullableString)&&row.status==='NO_DATA'&&
  [null,'V1_ROUTER_HEALTH_SAMPLES'].includes(row.health_source)&&['NO_DATA','LAST_PROBE_SUCCEEDED','LAST_PROBE_FAILED'].includes(row.connection_status)&&
  [row.cpu_load_percent,row.memory_used_percent].every(metric)&&
  (row.sampled_at===null||typeof row.sampled_at==='string'&&/(Z|[+-]\d{2}:\d{2})$/.test(row.sampled_at)&&Number.isFinite(Date.parse(row.sampled_at))&&Date.parse(row.sampled_at)<=Date.now()))&&
  new Set(value.items.map(row=>row.id)).size===value.items.length;
}
type Renderer=(resource:InventoryState&{retry:()=>void;now:number})=>ReactNode;
export function V1Inventory({render}:{render?:Renderer}={}){
 const [state,setState]=useState<InventoryState>({loading:true});
 const refresh=useRef(()=>{});
 useEffect(()=>{
  const task=inventoryRefresh<Inventory>({load:async signal=>{
   const data=await api<unknown>('/v1-inventory',{signal});
   if(!validInventory(data))throw new Error('Invalid inventory');
   return data;
  },publish:setState});
  refresh.current=task.refresh;
  const changed=(event:Event)=>{if((event as CustomEvent<string[]>).detail?.includes('/v1-inventory'))task.refresh();};
  window.addEventListener('v2-resource-change',changed);
  return()=>{refresh.current=()=>{};window.removeEventListener('v2-resource-change',changed);task.stop();};
 },[]);
 return <V1InventoryLiveView {...state} retry={()=>refresh.current()} render={render}/>;
}
function V1InventoryLiveView(props:InventoryState&{retry:()=>void;render?:Renderer}){
 const [now,setNow]=useState(Date.now);
 const [selected,setSelected]=useState<string|null>(null);
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
 if(props.render)return props.render({...props,now});
 return <V1InventoryView {...props} now={now} selectedId={selected} onSelect={setSelected}/>;
}
export function InventoryDetail({row,onClose}:{row:Row;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{node?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};},[]);
 return <dialog ref={dialog} className="expiry-dialog inventory-dialog" aria-labelledby="inventory-detail-title" onCancel={event=>{event.preventDefault();onClose();}}>
  <h2 id="inventory-detail-title">{row.name} · Router detayı</h2>
  <p>Salt okunur aktarım. Son internet denemesi canlı çevrimiçi durum kanıtı değildir.</p>
  <Facts items={[
   ['Router ID',row.id],['Kimlik',row.identity],['Model',row.model],['RouterOS',row.routeros_version],
   ['CPU',percent(row.cpu_load_percent)],['Bellek',percent(row.memory_used_percent)],['Son internet denemesi',probe(row)],
   ['Ölçüm zamanı · İstanbul',dateTime(row.sampled_at)],['Tam zaman damgası',row.sampled_at],
   ['Envanter kaynağı','V1_INVENTORY_EXPORT'],['Sağlık kaynağı',row.health_source],['Ölçüm ID',row.health_sample_id],['Canlı durum','Veri yok']
  ]}/><button autoFocus className="button-secondary" onClick={onClose}>Kapat</button>
 </dialog>;
}
export function V1InventoryView(resource:InventoryState&{retry:()=>void;now?:number;selectedId?:string|null;onSelect?:(id:string|null)=>void}){
 const data=resource.data,valid=validInventory(data),now=resource.now??Date.now();
 const visible=!resource.loading&&!resource.error&&valid;
 const selected=visible?data.items.find(row=>row.id===resource.selectedId):undefined;
 const headers=['Router','Model / RouterOS','Son bağlantı denemesi','CPU','Bellek','Son ölçüm · İstanbul','Sağlık / güncellik'];
 return <section className="panel v1-inventory"><div className="inventory-heading"><h2>Gerçek V1 envanteri</h2><button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Şimdi yenile</button></div>
  <p>Salt okunur · Bu sekme açıkken API her 60 saniyede yenilenir. Son internet denemesi canlı çevrimiçi durum kanıtı değildir.</p>
  <p className="inventory-refresh-time">Son başarılı yenileme: {resource.lastSuccess?dateTime(new Date(resource.lastSuccess).toISOString()):'Veri yok'}. Bu zaman ölçüm zamanı değildir.</p>
  <p>V2.6 başlangıç eşikleri: Dikkat CPU ≥ %70 / RAM ≥ %80; Kritik CPU ≥ %90 / RAM ≥ %95 (herhangi biri). Eski veri: 10 dakikadan eski. Yalnız arayüz bilgilendirmesi.</p>
  <ResourceState {...resource}/>
  {visible?<><table className="data-table inventory-table"><caption>Gerçek router sağlık ölçümleri</caption><thead><tr>{headers.map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{data.items.map(row=><tr key={row.id}>
   <td data-label={headers[0]}><button className="record-link" aria-label={`${row.name} router detayını aç`} onClick={()=>resource.onSelect?.(row.id)}>{row.name}</button></td>
   <td data-label={headers[1]}><span>{row.model??'Veri yok'}<small>RouterOS {row.routeros_version??'Veri yok'}</small></span></td>
   <td data-label={headers[2]}>{probe(row)}</td>
   <td data-label={headers[3]}>{percent(row.cpu_load_percent)}</td><td data-label={headers[4]}>{percent(row.memory_used_percent)}</td>
   <td data-label={headers[5]}>{row.sampled_at?dateTime(row.sampled_at).replace(' (İstanbul)',''):'Veri yok'}</td>
   <td data-label={headers[6]}><span><strong className={routerHealth(row,now).status!=='Normal'?'inventory-stale':''}>{routerHealth(row,now).status}</strong><small>{routerHealth(row,now).reason} · {routerHealth(row,now).age}</small></span></td>
  </tr>)}</tbody></table>{data.items.length===0&&<p>Veri yok · güvenilir gerçek envanter aktarımı sağlanmadı.</p>}</>:!resource.loading&&!resource.error?<p role="alert">Veri yok · kaynak doğrulanamadı.</p>:null}
  {selected&&<InventoryDetail row={selected} onClose={()=>resource.onSelect?.(null)}/>}
 </section>;
}
