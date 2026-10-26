import { useEffect, useState } from 'react';
import { ArrowRight, Command, Search, X } from 'lucide-react';
import type { ScreenKey } from './Sidebar';

const choices:{key:ScreenKey;label:string;hint:string}[]=[
 {key:'dashboard',label:'Genel Bakış',hint:'Çalışma alanı'}, {key:'routers',label:'Router Merkezi',hint:'Envanter'},
 {key:'subscribers',label:'Abone Merkezi',hint:'LOCAL + RADIUS'}, {key:'radius',label:'RADIUS Merkezi',hint:'Entegrasyon'},
 {key:'operations',label:'Operasyon Merkezi',hint:'Olaylar'}, {key:'mikajani',label:'MikAjanı',hint:'Ağ sağlığı'},
 {key:'system',label:'Sistem ve Kullanıcı',hint:'Erişim'},
];
export function CommandPalette({onClose,onNavigate}:{onClose:()=>void;onNavigate:(key:ScreenKey)=>void}){
 const [query,setQuery]=useState(''); const [active,setActive]=useState(0);
 const filtered=choices.filter(x=>`${x.label} ${x.hint}`.toLocaleLowerCase('tr').includes(query.toLocaleLowerCase('tr')));
 useEffect(()=>{const handler=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose();if(event.key==='ArrowDown'){event.preventDefault();setActive(i=>(i+1)%Math.max(filtered.length,1));}if(event.key==='ArrowUp'){event.preventDefault();setActive(i=>(i-1+Math.max(filtered.length,1))%Math.max(filtered.length,1));}if(event.key==='Enter'&&filtered[active]){onNavigate(filtered[active].key);onClose();}};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);},[onClose,onNavigate,filtered,active]);
 return <div className="overlay-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="command-modal"><div className="command-input"><Search size={18}/><input autoFocus placeholder="Modül veya sayfa ara..." value={query} onChange={e=>{setQuery(e.target.value);setActive(0);}}/><kbd>ESC</kbd><button className="icon-button" onClick={onClose}><X size={17}/></button></div><div className="command-label">HIZLI GEÇİŞ</div><div className="command-results">{filtered.map((choice,index)=><button key={choice.key} className={active===index?'selected':''} onMouseEnter={()=>setActive(index)} onClick={()=>{onNavigate(choice.key);onClose();}}><span className="command-result-icon"><Command size={15}/></span><span><b>{choice.label}</b><small>{choice.hint}</small></span><ArrowRight size={15}/></button>)}{filtered.length===0&&<div className="command-no-results">Eşleşen bölüm bulunamadı.</div>}</div><div className="command-foot"><span><kbd>↑</kbd><kbd>↓</kbd> gezin</span><span><kbd>↵</kbd> aç</span><span className="command-foot-right">MIKROTIK MANAGER V2</span></div></div></div>;
}
