import {useState} from 'react';
import {observationAge} from '../lib/routerObservation';
import '../styles/compact-routers.css';

export type CompactRouter={id:string;name:string;status:string;wan?:string|null;measuredAt?:string|null;checkedAt?:string|null};
export function savedRouterAge(value:string|null|undefined,now=Date.now()){
 const age=observationAge(value,now);
 const time=typeof value==='string'?Date.parse(value):NaN;
 return age!=='Güncellik bilinmiyor'&&now-time>600_000?'Güncel değil · '+age:age;
}
export function CompactRouterList({rows,onOpen,page:externalPage,onPage,total=rows.length}:{rows:CompactRouter[];onOpen:(id:string)=>void;page?:number;onPage?:(page:number)=>void;total?:number}){
 const [localPage,setLocalPage]=useState(1),pages=Math.max(1,Math.ceil(total/5));
 // Preserve out-of-range server pages so Previous can recover after deletion/filter changes.
 const page=onPage?(externalPage??1):Math.min(localPage,pages),setPage=onPage??setLocalPage;
 const visible=onPage?rows:rows.slice((page-1)*5,page*5);
 return <div className="compact-routers"><ul aria-label="Kompakt router listesi">{visible.map(row=><li key={row.id}><button type="button" onClick={()=>onOpen(row.id)} aria-label={row.name+' detayını aç'}>
 <span className="compact-router-content"><span className="compact-router-first"><strong>{row.name}</strong><span>{row.status}</span></span><span className="compact-router-second"><span>WAN: {row.wan||'Veri yok'}</span><span>{row.measuredAt?'Ölçüm: '+savedRouterAge(row.measuredAt):row.checkedAt?'Kontrol: '+observationAge(row.checkedAt):'Ölçüm verisi yok'}</span></span></span><span className="compact-router-arrow" aria-hidden="true">›</span>
 </button></li>)}</ul>{!visible.length&&<p className="table-empty">Bu kapsamda router kaydı yok.</p>}
 <nav aria-label="Mobil router sayfaları" className="compact-router-pages"><button type="button" disabled={page<=1} onClick={()=>setPage(page-1)} aria-label="Önceki router sayfası">‹</button><span role="status">{total} sonuç · {page}/{pages}</span><button type="button" disabled={page>=pages} onClick={()=>setPage(page+1)} aria-label="Sonraki router sayfası">›</button></nav>
 </div>;
}
