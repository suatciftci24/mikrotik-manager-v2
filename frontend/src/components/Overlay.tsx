import { useEffect, useRef, useState } from 'react';
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
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{node?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};},[]);

 useEffect(()=>{dialog.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({block:'nearest'});},[active,query]);
 return <div className="overlay-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><dialog ref={dialog} className="command-modal" aria-label="Hızlı modül araması" onCancel={e=>{e.preventDefault();onClose();}} onMouseDown={e=>{if(e.target===e.currentTarget){const bounds=e.currentTarget.getBoundingClientRect();if(e.clientX<bounds.left||e.clientX>bounds.right||e.clientY<bounds.top||e.clientY>bounds.bottom)onClose();}}}><div className="command-input"><Search size={18}/><input autoFocus aria-label="Modül veya sayfa ara" role="combobox" aria-expanded="true" aria-controls="command-results" aria-autocomplete="list" aria-activedescendant={filtered[active]?'command-option-'+filtered[active].key:undefined} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();setActive(i=>(i+1)%Math.max(filtered.length,1));}if(event.key==='ArrowUp'){event.preventDefault();setActive(i=>(i-1+Math.max(filtered.length,1))%Math.max(filtered.length,1));}if(event.key==='Enter'&&filtered[active]){event.preventDefault();onNavigate(filtered[active].key);onClose();}}} placeholder="Modül veya sayfa ara..." value={query} onChange={e=>{setQuery(e.target.value);setActive(0);}}/><kbd>ESC</kbd><button className="icon-button" aria-label="Aramayı kapat" onClick={onClose}><X size={17}/></button></div><div className="command-label">HIZLI GEÇİŞ</div><div className="command-results" id="command-results" role="listbox" aria-label="Eşleşen modüller">{filtered.map((choice,index)=><button key={choice.key} id={'command-option-'+choice.key} role="option" aria-selected={active===index} className={active===index?'selected':''} onMouseEnter={()=>setActive(index)} onClick={()=>{onNavigate(choice.key);onClose();}}><span className="command-result-icon"><Command size={15}/></span><span><b>{choice.label}</b><small>{choice.hint}</small></span><ArrowRight size={15}/></button>)}{filtered.length===0&&<div className="command-no-results">Eşleşen bölüm bulunamadı.</div>}</div><div className="command-foot"><span><kbd>↑</kbd><kbd>↓</kbd> gezin</span><span><kbd>↵</kbd> aç</span><span className="command-foot-right">MIKROTIK MANAGER V2</span></div></dialog></div>;
}
