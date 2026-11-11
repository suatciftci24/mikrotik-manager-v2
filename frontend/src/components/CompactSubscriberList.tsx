import {useEffect,useState,type ReactNode} from 'react';
import {expiryDate} from '../lib/expiry';
import '../styles/compact-subscribers.css';

export function useCompactSubscribers(){
 const [compact,setCompact]=useState(false);
 useEffect(()=>{const media=window.matchMedia('(max-width: 600px)');const change=()=>setCompact(media.matches);change();media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 return compact;
}
/** One set of controls and IDs; desktop stays expanded, mobile opens on demand. */
export function SubscriberDisclosure({children,label='Filtreler',className=''}:{children:ReactNode;label?:string;className?:string}){
 const compact=useCompactSubscribers(),[expanded,setExpanded]=useState(false);
 return <details className={'subscriber-disclosure '+className} open={!compact||expanded} onToggle={e=>{if(compact)setExpanded(e.currentTarget.open);}}><summary>{label}</summary>{children}</details>;
}
type Row={id:string;customer_name:string;plan:string;expires_on:string|null;status:string};
export function compactPage<T>(rows:T[],page:number){return rows.slice((page-1)*5,page*5);}
export function CompactSubscriberList<T extends Row>({rows,onOpen,selected,onSelect,canSelect,page:externalPage,onPage,total=rows.length}:{rows:T[];onOpen:(id:string)=>void;selected:(id:string)=>boolean;onSelect:(row:T,checked:boolean)=>void;canSelect:(row:T)=>boolean;page?:number;onPage?:(page:number)=>void;total?:number}){
 const [localPage,setLocalPage]=useState(1);
 const pages=Math.max(1,Math.ceil(total/5)),page=Math.min(externalPage??localPage,pages);
 const visible=onPage?rows:compactPage(rows,page),setPage=onPage??setLocalPage;
 return <div className="compact-subscribers">
 <ul aria-label="Kompakt abone listesi">{visible.map(row=><li key={row.id}>
 <label className="compact-subscriber-select"><input type="checkbox" aria-label={row.customer_name+' seç'} checked={selected(row.id)} disabled={!canSelect(row)} onChange={e=>onSelect(row,e.target.checked)}/></label>
 <button type="button" className="compact-subscriber-open" onClick={()=>onOpen(row.id)} aria-label={row.customer_name+' detayını aç'}>
 <span className="compact-subscriber-content"><span className="compact-subscriber-first"><strong>{row.customer_name}</strong><span className="compact-subscriber-status">{row.status==='ACTIVE'?'Aktif':row.status==='PAUSED'?'Pasif':row.status==='PENDING'?'Bekliyor':'Bilinmiyor'}</span></span><span className="compact-subscriber-second"><span>{row.plan}</span><time>{expiryDate(row.expires_on)}</time></span></span><span aria-hidden="true" className="compact-subscriber-arrow">›</span>
 </button></li>)}</ul>
 {!visible.length&&<p className="table-empty">Filtrelerle eşleşen abone yok.</p>}
 <nav className="compact-subscriber-pages" aria-label="Mobil abone sayfaları"><button type="button" disabled={page<=1} onClick={()=>setPage(page-1)} aria-label="Önceki abone sayfası">‹</button><span role="status">{total} sonuç · {page}/{pages}</span><button type="button" disabled={page>=pages} onClick={()=>setPage(page+1)} aria-label="Sonraki abone sayfası">›</button></nav>
 </div>;
}
