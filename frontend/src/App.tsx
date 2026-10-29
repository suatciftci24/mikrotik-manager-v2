import {SystemCenter} from './screens/SystemCenter';
import {applyPresentation,presentationSnapshot,presentationDefaults,type Presentation} from './lib/presentation';
import {PermissionContext} from './lib/permissions';
import {invalidateResources} from './lib/resourceEvents';
import { AlarmCenter } from './components/AlarmCenter';
import { screenFromHash } from './lib/useDetailNavigation';
import { useCallback, useEffect, useRef, useState } from 'react';
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
 const [locationHash,setLocationHash]=useState(()=>window.location.hash);
 const [user,setUser]=useState<User|null>(null);const [checking,setChecking]=useState(true);const [active,setActive]=useState<ScreenKey>(()=>screenFromHash(window.location.hash));const [palette,setPalette]=useState(false);const [mobileMenu,setMobileMenu]=useState(false);const [toast,setToast]=useState('');const [notice,setNotice]=useState(false);
 const notify=useCallback((message:string)=>{setToast(message);window.setTimeout(()=>setToast(''),3200);},[]);
 const userRef=useRef<User|null>(null),authGeneration=useRef(0);
 useEffect(()=>{
  let alive=true,busy=false;
  const refresh=()=>{if(busy)return;busy=true;const generation=authGeneration.current;api<User>('/auth/me').then(value=>{
   if(!alive||generation!==authGeneration.current)return;
   const previous=userRef.current;userRef.current=value;setUser(value);
   if(previous&&JSON.stringify(previous)!==JSON.stringify(value))invalidateResources(['/routers','/subscribers','/dashboard','/router-events','/mikajani','/reports','/alarms','/users','/router-registry']);
  }).catch(()=>{if(alive&&generation===authGeneration.current){userRef.current=null;setUser(null);}}).finally(()=>{busy=false;if(alive)setChecking(false);});};
  const changed=(event:Event)=>{if((event as CustomEvent<string[]>).detail?.includes('/users'))refresh();};
  refresh();const timer=window.setInterval(()=>{if(!document.hidden)refresh();},30000);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);window.addEventListener('v2-auth-refresh',refresh);window.addEventListener('v2-resource-change',changed);
  return()=>{alive=false;window.clearInterval(timer);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);window.removeEventListener('v2-auth-refresh',refresh);window.removeEventListener('v2-resource-change',changed);};
 },[]);
 useEffect(()=>{
  if(!user){applyPresentation(presentationDefaults);return;}
  let alive=true;const load=()=>{api<{values:Presentation;is_demo:boolean}>('/preferences').then(data=>{if(alive&&data.is_demo){const changed=JSON.stringify(presentationSnapshot())!==JSON.stringify(data.values);applyPresentation(data.values);if(changed)invalidateResources(['/users','/alarms','/reports','/system/audit']);}}).catch(()=>{});};
  load();const tick=()=>{if(!document.hidden)load();};const timer=window.setInterval(tick,60000);window.addEventListener('focus',tick);window.addEventListener('v2-preferences-change',load);
  return()=>{alive=false;window.clearInterval(timer);window.removeEventListener('focus',tick);window.removeEventListener('v2-preferences-change',load);};
 },[user?.id]);
 useEffect(()=>{const key=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setPalette(value=>!value);}if(event.key==='Escape'){setMobileMenu(false);setNotice(false);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[]);
 const navigate=useCallback((key:ScreenKey,params:Record<string,string>={})=>{const hash=key==='routers'||key==='subscribers'||key==='operations'||key==='mikajani'||key==='system'?'#'+new URLSearchParams({module:key,...params}).toString():'';window.history.replaceState(null,'',window.location.pathname+window.location.search+hash);window.dispatchEvent(new HashChangeEvent('hashchange'));setActive(key);setMobileMenu(false);window.scrollTo({top:0,behavior:'smooth'});},[]);
 useEffect(()=>{const sync=()=>{setLocationHash(window.location.hash);setActive(screenFromHash(window.location.hash));setMobileMenu(false);setNotice(false);};window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const logout=async()=>{authGeneration.current++;userRef.current=null;try{await api('/auth/logout',{method:'POST'});}finally{setUser(null);setActive('dashboard');window.history.replaceState(null,'',window.location.pathname+window.location.search);notify('Yerel demo oturumu kapatıldı.');}};
 if(checking)return <div className="boot-screen"><span className="brand-mark"><ArrowRight size={17}/></span><span className="spinner"/>V2 çalışma alanı açılıyor</div>;
 if(!user)return <Login onLogin={value=>{authGeneration.current++;userRef.current=value;setUser(value);}}/>;
 const routerParams=new URLSearchParams(locationHash.slice(1));const registeredInventory=active==='routers'&&(routerParams.get('source')==='REGISTERED'||routerParams.get('id')?.startsWith('registered-')===true);
 return <PermissionContext.Provider value={user}><div className="app-shell"><div className={`sidebar-container ${mobileMenu?'mobile-open':''}`}><Sidebar active={active} onNavigate={navigate} user={user} onLogout={logout}/><button className="mobile-scrim" onClick={()=>setMobileMenu(false)} aria-label="Menüyü kapat"/></div><main className="main-area"><MobileHeader onMenu={()=>setMobileMenu(true)}/><Header registeredInventory={registeredInventory} active={active} user={user} onOpenSearch={()=>setPalette(true)} onOpenNotifications={()=>setNotice(true)}/><div className="content-area"><DemoBanner registeredInventory={registeredInventory}/>{active==='dashboard'?<Dashboard onNavigate={navigate}/>:active==='routers'?<Routers onToast={notify}/>:active==='subscribers'?<Subscribers onToast={notify}/>:active==='operations'?<Operations onRouter={id=>navigate('routers',{id})}/>:active==='mikajani'?<Mikajani/>:active==='system'?<SystemCenter/>:<ModuleScreen screen={active}/>}<footer className="app-footer"><span>© 2026 MikroTik Manager V2 <i>·</i> Bağımsız geliştirme ortamı</span><span><span className="pulse-dot"/>Otomatik cihaz polling kapalı</span></footer></div></main>
 {palette&&<CommandPalette onClose={()=>setPalette(false)} onNavigate={navigate}/>} {notice&&<div className="notice-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)setNotice(false);}}><section className="notice-popover" role="region" aria-label="Bildirimler" onClickCapture={e=>{if((e.target as Element).closest?.('a[href^="#"]'))setNotice(false);}}><header><strong>Bildirimler</strong><button className="icon-button" aria-label="Bildirimleri kapat" onClick={()=>setNotice(false)}><X size={16}/></button></header><AlarmCenter notifications/></section></div>}{toast&&<div className="toast" role="status" aria-live="polite"><span className="toast-mark"><Bell size={14}/></span>{toast}<button aria-label="Bildirimi kapat" onClick={()=>setToast('')}><X size={14}/></button></div>}</div></PermissionContext.Provider>;
}
