import {useEffect,useState} from 'react';
import {Search,ShieldCheck} from 'lucide-react';
import {api} from '../lib/api';
import {useResource} from '../lib/useResource';
import {connectionError,registryStatus,type RegisteredRouter} from '../lib/routerRegistry';
import {dateTime} from './Resource';

const REGISTRY_DEPENDENCIES=['/router-registry'] as const;
export function RouterRegistryList({onOpen}:{onOpen:(id:string)=>void}){
 const [query,setQuery]=useState(''),[search,setSearch]=useState(''),[status,setStatus]=useState('ALL'),[page,setPage]=useState(1);
 useEffect(()=>{const timer=window.setTimeout(()=>{setSearch(query);setPage(1);},250);return()=>window.clearTimeout(timer);},[query]);
 const resource=useResource<{items:RegisteredRouter[];total:number}>(`/router-registry?${new URLSearchParams({query:search,status,page:String(page),page_size:'25'})}`,api,REGISTRY_DEPENDENCIES);
 return <section className="panel router-inventory registry-inventory" aria-label="Kayıtlı routerlar">
  <div className="registry-section-title"><ShieldCheck size={20}/><div><h2>Kayıtlı cihazlar</h2><p>Yalnız başarılı API-SSL doğrulamasıyla kaydedilen cihazlar. Sentetik envanter ve pilot secret dosyaları paylaşılmaz.</p></div></div>
  <div className="inventory-toolbar"><label className="table-search"><Search size={15}/><input aria-label="Kayıtlı router ara" placeholder="Ad, IP, kimlik, model veya sürüm…" value={query} onChange={e=>setQuery(e.target.value)}/></label><label className="form-label">Son kontrol durumu<select value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="ALL">Tümü</option><option value="VERIFIED">Son kontrol başarılı</option><option value="STALE">Kontrol eskimiş</option><option value="CHECK_FAILED">Son kontrol başarısız</option></select></label><button className="button-secondary" onClick={resource.retry}>Listeyi yenile</button></div>
  {resource.loading&&<p role="status" className="registry-message">Kayıtlı cihazlar yükleniyor…</p>}
  {resource.error&&<div role="alert" className="registry-message form-error"><p>{connectionError(resource.error)}</p><button className="button-secondary" onClick={resource.retry}>Listeyi yeniden yükle</button></div>}
  {!resource.loading&&!resource.error&&resource.data&&<><div className="table-scroll" role="region" tabIndex={0} aria-label="Kayıtlı router envanteri"><table className="data-table"><thead><tr><th>ROUTER / YÖNETİM IP</th><th>MODEL / ROUTEROS</th><th>SON KONTROL</th><th>SON BAŞARILI KONTROL</th><th/></tr></thead><tbody>{resource.data.items.map(item=><tr key={item.id}><td><span className="table-main"><strong><button className="record-link" onClick={()=>onOpen(item.id)}>{item.name}</button></strong><small>{item.management_address}:{item.port} · {item.identity}</small></span></td><td><span className="table-main"><strong>{item.model}</strong><small>{item.routeros_version}</small></span></td><td><span className={`registry-status ${item.status.toLowerCase()}`}>{registryStatus(item.status)}</span>{item.last_error&&<small className="registry-table-error">{connectionError(item.last_error)}</small>}</td><td>{dateTime(item.last_success_at)}</td><td><button className="button-secondary" onClick={()=>onOpen(item.id)}>Detay</button></td></tr>)}</tbody></table></div>{resource.data.total===0&&<div className="table-empty">{search||status!=='ALL'?'Filtrelerle eşleşen kayıt yok.':'Henüz kayıtlı cihaz yok. Router ekle ile güvenli doğrulamayı başlatın.'}</div>}<div className="table-footer"><span>{resource.data.total} kayıt · Sürekli izleme kapalı</span><div><button className="button-secondary" disabled={page===1} onClick={()=>setPage(value=>value-1)}>Önceki</button><span> {page} </span><button className="button-secondary" disabled={page*25>=resource.data.total} onClick={()=>setPage(value=>value+1)}>Sonraki</button></div></div></>}
 </section>;
}
