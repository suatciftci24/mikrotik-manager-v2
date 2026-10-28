import { screenFromHash } from './lib/useDetailNavigation';
import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, Bell, Menu, X } from 'lucide-react';
import { Sidebar, MobileHeader, type ScreenKey, type User } from './components/Sidebar';
import { Header, DemoBanner } from './components/Header';
import { CommandPalette } from './components/Overlay';
import { Dashboard } from './screens/Dashboard';
import { Routers } from './screens/Routers';
import { Subscribers } from './screens/Subscribers';
import { ModuleScreen } from './screens/Modules';
import { Operations } from './screens/Operations';
import { Mikajani } from './screens/Mikajani';
import { Login } from './screens/Login';
import { api } from './lib/api';
import './styles.css';

export default function App(){
 const [user,setUser]=useState<User|null>(null);const [checking,setChecking]=useState(true);const [active,setActive]=useState<ScreenKey>(()=>screenFromHash(window.location.hash));const [palette,setPalette]=useState(false);const [mobileMenu,setMobileMenu]=useState(false);const [toast,setToast]=useState('');const [notice,setNotice]=useState(false);
 const notify=useCallback((message:string)=>{setToast(message);window.setTimeout(()=>setToast(''),3200);},[]);
 useEffect(()=>{let alive=true;api<User>('/auth/me').then(value=>{if(alive)setUser(value);}).catch(()=>{}).finally(()=>{if(alive)setChecking(false);});return()=>{alive=false;};},[]);
 useEffect(()=>{const key=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setPalette(value=>!value);}if(event.key==='Escape'){setMobileMenu(false);setNotice(false);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[]);
 const navigate=useCallback((key:ScreenKey,params:Record<string,string>={})=>{const hash=key==='routers'||key==='subscribers'||key==='operations'||key==='mikajani'?'#'+new URLSearchParams({module:key,...params}).toString():'';window.history.replaceState(null,'',window.location.pathname+window.location.search+hash);window.dispatchEvent(new HashChangeEvent('hashchange'));setActive(key);setMobileMenu(false);window.scrollTo({top:0,behavior:'smooth'});},[]);
 useEffect(()=>{const sync=()=>{setActive(screenFromHash(window.location.hash));setMobileMenu(false);};window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const logout=async()=>{try{await api('/auth/logout',{method:'POST'});}finally{setUser(null);setActive('dashboard');window.history.replaceState(null,'',window.location.pathname+window.location.search);notify('Yerel demo oturumu kapatıldı.');}};
 if(checking)return <div className="boot-screen"><span className="brand-mark"><ArrowRight size={17}/></span><span className="spinner"/>V2 çalışma alanı açılıyor</div>;
 if(!user)return <Login onLogin={setUser}/>;
 return <div className="app-shell"><div className={`sidebar-container ${mobileMenu?'mobile-open':''}`}><Sidebar active={active} onNavigate={navigate} user={user} onLogout={logout}/><button className="mobile-scrim" onClick={()=>setMobileMenu(false)} aria-label="Menüyü kapat"/></div><main className="main-area"><MobileHeader onMenu={()=>setMobileMenu(true)}/><Header active={active} user={user} onOpenSearch={()=>setPalette(true)} onOpenNotifications={()=>setNotice(true)}/><div className="content-area"><DemoBanner/>{active==='dashboard'?<Dashboard onNavigate={navigate}/>:active==='routers'?<Routers onToast={notify}/>:active==='subscribers'?<Subscribers onToast={notify}/>:active==='operations'?<Operations onRouter={id=>navigate('routers',{id})}/>:active==='mikajani'?<Mikajani/>:<ModuleScreen screen={active}/>}<footer className="app-footer"><span>© 2026 MikroTik Manager V2 <i>·</i> Bağımsız geliştirme ortamı</span><span><span className="pulse-dot"/>Harici bağlantı kurulmadı</span></footer></div></main>
 {palette&&<CommandPalette onClose={()=>setPalette(false)} onNavigate={navigate}/>} {notice&&<div className="notice-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)setNotice(false);}}><section className="notice-popover" role="region" aria-label="Bildirimler"><header><strong>Bildirimler</strong><button className="icon-button" aria-label="Bildirimleri kapat" onClick={()=>setNotice(false)}><X size={16}/></button></header><div><Bell size={17}/><span><b>Demo alarm merkezi</b><small>Kaydedilmiş sentetik internet ve WAN olaylarını inceleyin.</small></span></div><button className="notice-link" onClick={()=>{setNotice(false);navigate('operations');}}>Operasyon merkezine git <ArrowRight size={14}/></button></section></div>}{toast&&<div className="toast" role="status" aria-live="polite"><span className="toast-mark"><Bell size={14}/></span>{toast}<button aria-label="Bildirimi kapat" onClick={()=>setToast('')}><X size={14}/></button></div>}</div>;
}
