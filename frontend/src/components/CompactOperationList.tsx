import {useState} from 'react';
import '../styles/compact-operations.css';

export type CompactOperationRow={id:string;title:string;subject:string;when:string;result:string;searchText?:string};
export function compactOperationTime(value:string|null){
 if(!value||!/(Z|[+-]\d{2}:\d{2})$/.test(value)||!Number.isFinite(Date.parse(value)))return 'Zaman yok';
 return new Intl.DateTimeFormat('tr-TR',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Istanbul'}).format(new Date(value));
}
export function operationSearch(rows:CompactOperationRow[],query:string){
 const key=(value:string)=>value.normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase('tr-TR').replace(/ı/g,'i');
 const terms=key(query.trim()).split(/\s+/).filter(Boolean);
 return rows.filter(row=>{const text=key([row.title,row.subject,row.result,row.searchText??''].join(' '));return terms.every(term=>text.includes(term));});
}
/** A view of existing evidence; selecting a row opens the existing canonical detail. */
export function CompactOperationList({rows,onOpen,label,query='',partial=false}:{rows:CompactOperationRow[];onOpen:(id:string)=>void;label:string;query?:string;partial?:boolean}){
 const [page,setPage]=useState(1),filtered=operationSearch(rows,query),pages=Math.max(1,Math.ceil(filtered.length/5));
 const current=Math.min(page,pages),visible=filtered.slice((current-1)*5,current*5);
 return <div className="compact-operation-list"><ul aria-label={label}>{visible.map(row=><li key={row.id}><button type="button" onClick={()=>onOpen(row.id)} aria-label={row.title+' · '+row.subject+' detayını aç'}>
 <span className="compact-operation-content"><span className="compact-operation-first"><strong>{row.title}</strong><span>{row.result}</span></span><span className="compact-operation-second"><span>{row.subject}</span><span>{row.when}</span></span></span><span className="compact-operation-arrow" aria-hidden="true">›</span>
 </button></li>)}</ul>{!visible.length&&<p className="missing-data">{partial?'Erişilebilen kaynaklarda eşleşen kayıt yok; kapsam eksik.':'Bu kapsamda kayıt yok.'}</p>}
 <nav className="compact-operation-pages" aria-label={label+' sayfaları'}><button type="button" aria-label={label+' önceki sayfa'} disabled={current<=1} onClick={()=>setPage(current-1)}>‹</button><span role="status">{filtered.length} {partial?'erişilen kayıt':'kayıt'} · {current}/{pages}</span><button type="button" aria-label={label+' sonraki sayfa'} disabled={current>=pages} onClick={()=>setPage(current+1)}>›</button></nav>
 </div>;
}
