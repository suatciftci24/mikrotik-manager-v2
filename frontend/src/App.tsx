import {PendingSubscriberOperations} from './components/PendingSubscriberOperations';
import {pendingIdentity,identityStamp} from './lib/pendingSubscriberOperations';
import {workspaceContext} from './lib/workspaceContext';
import {normalizeRuntimeProfile,type RuntimeProfile} from './lib/runtimeProfile';
import {applyPresentation,presentationSnapshot,presentationDefaults,type Presentation} from './lib/presentation';
import {PermissionContext} from './lib/permissions';
import {invalidateResources} from './lib/resourceEvents';
import { screenFromHash } from './lib/useDetailNavigation';
import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ErrorInfo, type ReactNode } from 'react';
import { ArrowRight, Bell, Menu, X } from 'lucide-react';
import { Sidebar, MobileHeader, type ScreenKey, type User } from './components/Sidebar';
import { Header, DemoBanner } from './components/Header';
import { CommandPalette } from './components/Overlay';
import { ModuleScreen } from './screens/Modules';
import { Login } from './screens/Login';
import { api } from './lib/api';
import './styles.css';

function lazyScreens(){return {
 Dashboard:lazy(()=>import('./screens/Dashboard').then(module=>({default:module.Dashboard}))),
 Routers:lazy(()=>import('./screens/Routers').then(module=>({default:module.Routers}))),
 Subscribers:lazy(()=>import('./screens/Subscribers').then(module=>({default:module.Subscribers}))),
 Operations:lazy(()=>import('./screens/Operations').then(module=>({default:module.Operations}))),
 Mikajani:lazy(()=>import('./screens/Mikajani').then(module=>({default:module.Mikajani}))),
 SystemCenter:lazy(()=>import('./screens/SystemCenter').then(module=>({default:module.SystemCenter}))),
 AlarmCenter:lazy(()=>import('./components/AlarmCenter').then(module=>({default:module.AlarmCenter}))),
};}
type BoundaryProps={children:ReactNode;resetKey:string;onRetry:()=>void};
type BoundaryState={error:Error|null};
export class LazyChunkBoundary extends Component<BoundaryProps,BoundaryState>{
 state:BoundaryState={error:null};
 static getDerivedStateFromError(error:Error):BoundaryState{return {error};}
 componentDidCatch(_error:Error,_info:ErrorInfo){}
 componentDidUpdate(previous:BoundaryProps){if(previous.resetKey!==this.props.resetKey&&this.state.error)this.setState({error:null});}
 render(){return this.state.error?<section className="panel" role="alert"><h2>Bölüm yüklenemedi</h2><p>İnternet bağlantınızı kontrol edip bu bölümü yeniden deneyin. Açık ekran ve oturum korunur.</p><button className="button-primary" onClick={this.props.onRetry}>Yeniden dene</button></section>:this.props.children;}
}


export default function App(){
 const [chunkAttempt,setChunkAttempt]=useState(0);
 const [runtimeProfile,setRuntimeProfile]=useState<RuntimeProfile>('local-demo');
 useEffect(()=>{let alive=true;fetch('/api/ready',{credentials:'include'}).then(response=>response.ok?response.json():null).then(data=>{if(alive&&data)setRuntimeProfile(normalizeRuntimeProfile(data.runtime_profile));}).catch(()=>{});return()=>{alive=false;};},[]);
 const screens=useMemo(()=>lazyScreens(),[chunkAttempt]);
 const [locationHash,setLocationHash]=useState(()=>window.location.hash);
 const [user,setUser]=useState<User|null>(null);const [checking,setChecking]=useState(true);const [active,setActive]=useState<ScreenKey>(()=>screenFromHash(window.location.hash));const [palette,setPalette]=useState(false);const [mobileMenu,setMobileMenu]=useState(false);const [toast,setToast]=useState('');const [notice,setNotice]=useState(false);
 const notify=useCallback((message:string)=>{setToast(message);window.setTimeout(()=>setToast(''),3200);},[]);
 const userRef=useRef<User|null>(null),authGeneration=useRef(0);
 useEffect(()=>{
  let alive=true,busy=false;
  const refresh=()=>{if(busy)return;busy=true;const generation=authGeneration.current;api<User>('/auth/me').then(value=>{
   if(!alive||generation!==authGeneration.current)return;
   const previous=userRef.current;userRef.current=value;pendingIdentity(value);setUser(value);
   if(previous&&JSON.stringify(previous)!==JSON.stringify(value))invalidateResources(['/routers','/subscribers','/dashboard','/router-events','/mikajani','/reports','/alarms','/users','/router-registry']);
  }).catch(()=>{if(alive&&generation===authGeneration.current){userRef.current=null;pendingIdentity(null);setUser(null);}}).finally(()=>{busy=false;if(alive)setChecking(false);});};
  const changed=(event:Event)=>{if((event as CustomEvent<string[]>).detail?.includes('/users'))refresh();};
  const ended=(event:StorageEvent)=>{if(event.key==='v2-auth-ended'){authGeneration.current++;userRef.current=null;pendingIdentity(null);setUser(null);refresh();}};window.addEventListener('storage',ended);
  refresh();const timer=window.setInterval(()=>{if(!document.hidden)refresh();},30000);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);window.addEventListener('v2-auth-refresh',refresh);window.addEventListener('v2-resource-change',changed);
  return()=>{alive=false;window.removeEventListener('storage',ended);window.clearInterval(timer);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);window.removeEventListener('v2-auth-refresh',refresh);window.removeEventListener('v2-resource-change',changed);};
 },[]);
 useEffect(()=>{
  if(!user){applyPresentation(presentationDefaults);return;}
  let alive=true;const load=()=>{api<{values:Presentation;is_demo:boolean}>('/preferences').then(data=>{if(alive&&data.is_demo){const changed=JSON.stringify(presentationSnapshot())!==JSON.stringify(data.values);applyPresentation(data.values);if(changed)invalidateResources(['/users','/alarms','/reports','/system/audit']);}}).catch(()=>{});};
  load();const tick=()=>{if(!document.hidden)load();};const timer=window.setInterval(tick,60000);window.addEventListener('focus',tick);window.addEventListener('v2-preferences-change',load);
  return()=>{alive=false;window.clearInterval(timer);window.removeEventListener('focus',tick);window.removeEventListener('v2-preferences-change',load);};
 },[user?.id]);
 useEffect(()=>{const key=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setPalette(value=>!value);}if(event.key==='Escape'){setMobileMenu(false);setNotice(false);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[]);
 const navigate=useCallback((key:ScreenKey,params:Record<string,string>={})=>{const hash=key==='routers'||key==='subscribers'||key==='operations'||key==='mikajani'||key==='system'||key==='radius'?'#'+new URLSearchParams({module:key,...params}).toString():'';window.history.replaceState(null,'',window.location.pathname+window.location.search+hash);window.dispatchEvent(new HashChangeEvent('hashchange'));setActive(key);setMobileMenu(false);window.scrollTo({top:0,behavior:'smooth'});},[]);
 useEffect(()=>{const sync=()=>{setLocationHash(window.location.hash);setActive(screenFromHash(window.location.hash));setMobileMenu(false);setNotice(false);};window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 const logout=async()=>{try{localStorage.setItem('v2-auth-ended',crypto.randomUUID());}catch{}authGeneration.current++;userRef.current=null;pendingIdentity(null);setUser(null);try{await api('/auth/logout',{method:'POST'});}finally{setUser(null);setActive('dashboard');window.history.replaceState(null,'',window.location.pathname+window.location.search);notify('Oturum kapatıldı.');}};
 if(checking)return <div className="boot-screen"><span className="brand-mark"><ArrowRight size={17}/></span><span className="spinner"/>V2 çalışma alanı açılıyor</div>;
 if(!user)return <Login runtimeProfile={runtimeProfile} onLogin={value=>{authGeneration.current++;userRef.current=value;pendingIdentity(value);setUser(value);}}/>;
 const routerParams=new URLSearchParams(locationHash.slice(1));const registeredInventory=active==='routers'&&(routerParams.get('source')==='REGISTERED'||routerParams.get('id')?.startsWith('registered-')===true);
 const realInventory=active==='routers'&&routerParams.get('source')==='V1_INVENTORY'||active==='dashboard'&&(!routerParams.get('view')||routerParams.get('view')==='OVERVIEW')&&routerParams.get('dashboard_source')==='V1_INVENTORY';
 const context=workspaceContext(active,locationHash);
 const panelAddress=window.location.host;
 return <PermissionContext.Provider key={identityStamp(user)} value={user}><div className="app-shell"><div className={`sidebar-container ${mobileMenu?'mobile-open':''}`}><Sidebar context={context} runtimeProfile={runtimeProfile} panelAddress={panelAddress} realInventory={realInventory} active={active} onNavigate={navigate} user={user} onLogout={logout}/><button className="mobile-scrim" onClick={()=>setMobileMenu(false)} aria-label="Menüyü kapat"/></div><main className="main-area"><MobileHeader onMenu={()=>setMobileMenu(true)} runtimeProfile={runtimeProfile}/><Header context={context} runtimeProfile={runtimeProfile} realInventory={realInventory} registeredInventory={registeredInventory} active={active} user={user} onOpenSearch={()=>setPalette(true)} onOpenNotifications={()=>setNotice(true)}/><div className="content-area"><PendingSubscriberOperations/><DemoBanner context={context} runtimeProfile={runtimeProfile} panelAddress={panelAddress} realInventory={realInventory} registeredInventory={registeredInventory}/><LazyChunkBoundary resetKey={`${active}:${chunkAttempt}`} onRetry={()=>setChunkAttempt(value=>value+1)}><Suspense fallback={<div className="resource-state" role="status" aria-live="polite">Bölüm yükleniyor…</div>}>{active==='dashboard'?<screens.Dashboard onNavigate={navigate}/>:active==='routers'?<screens.Routers onToast={notify}/>:active==='subscribers'?<screens.Subscribers onToast={notify}/>:active==='operations'?<screens.Operations onRouter={id=>navigate('routers',{id})}/>:active==='mikajani'?<screens.Mikajani/>:active==='system'?<screens.SystemCenter/>:<ModuleScreen screen={active}/>}</Suspense></LazyChunkBoundary><footer className="app-footer"><span>© 2026 {runtimeProfile==='v26-isolated-acceptance'?'MikroTik Manager V2.6':'MikroTik Manager V2'} <i>·</i> Yönetim paneli</span><span><span className="pulse-dot"/>{runtimeProfile==='v26-isolated-acceptance'?'V2.6 İzole Kabul':'V2 Demo'} · {context.access}</span></footer></div></main>
 {palette&&<CommandPalette onClose={()=>setPalette(false)} onNavigate={navigate}/>} {notice&&<LazyChunkBoundary resetKey={`notice:${chunkAttempt}`} onRetry={()=>setChunkAttempt(value=>value+1)}><Suspense fallback={<div className="notice-scrim" role="status">Bildirimler yükleniyor…</div>}><div className="notice-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)setNotice(false);}}><section className="notice-popover" role="region" aria-label="Bildirimler" onClickCapture={e=>{if((e.target as Element).closest?.('a[href^="#"]'))setNotice(false);}}><header><strong>Bildirimler</strong><button className="icon-button" aria-label="Bildirimleri kapat" onClick={()=>setNotice(false)}><X size={16}/></button></header><screens.AlarmCenter notifications/></section></div></Suspense></LazyChunkBoundary>}{toast&&<div className="toast" role="status" aria-live="polite"><span className="toast-mark"><Bell size={14}/></span>{toast}<button aria-label="Bildirimi kapat" onClick={()=>setToast('')}><X size={14}/></button></div>}</div></PermissionContext.Provider>;
}
