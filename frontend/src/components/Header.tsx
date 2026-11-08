import type {WorkspaceContext} from '../lib/workspaceContext';
import {usePresentation} from '../lib/presentation';
import { ThemePicker } from './ThemePicker';
import { Bell, ChevronDown, Command, Search, Sparkles } from 'lucide-react';
import type { ScreenKey, User } from './Sidebar';
import {runtimeIdentity,type RuntimeProfile} from '../lib/runtimeProfile';

const names: Record<ScreenKey, { title: string; crumb: string }> = {
  dashboard: { title: 'Genel Bakış', crumb: 'Workspace' }, routers: { title: 'Router Merkezi', crumb: 'Yönetim' },
  subscribers: { title: 'Abone Merkezi', crumb: 'Yönetim' }, radius: { title: 'RADIUS Merkezi', crumb: 'Yönetim' },
  operations: { title: 'Operasyon Merkezi', crumb: 'İzleme' }, mikajani: { title: 'MikAjanı', crumb: 'İzleme' },
  system: { title: 'Sistem ve Kullanıcı', crumb: 'Sistem' },
};

export function Header({ active, user, onOpenSearch, onOpenNotifications, registeredInventory=false, realInventory=false, context,runtimeProfile='local-demo' }: {
  active: ScreenKey; user: User; context?:WorkspaceContext;runtimeProfile?:RuntimeProfile; registeredInventory?:boolean; realInventory?:boolean; onOpenSearch: () => void; onOpenNotifications: () => void;
}) {
  const current = names[active];
  const presentation=usePresentation();
  return <header className="topbar">
    <div className="breadcrumbs"><span>{presentation.app_name} · {current.crumb}</span><span className="crumb-slash">/</span><strong>{current.title}</strong></div>
    <div className="topbar-actions"><ThemePicker/>
      <div className="live-pill"><span className="pulse-dot" />{runtimeProfile==='v26-isolated-acceptance'?runtimeIdentity(runtimeProfile).workspace:context?.label??(realInventory?'Gerçek V1 · Salt okunur':registeredInventory?'API-SSL cihaz kayıtları':'Sentetik demo ortamı')}</div>
      <button className="search-trigger" onClick={onOpenSearch}><Search size={15} /><span>Hızlı ara...</span><kbd>⌘ K</kbd></button>
      <button className="icon-button notification-button" aria-label="Bildirimler" onClick={onOpenNotifications}><Bell size={17} /></button>
      <button className="top-user"><span className="mini-avatar">{user.name.split(' ').map(x => x[0]).join('').slice(0, 2)}</span><ChevronDown size={14} /></button>
    </div>
  </header>;
}

export function DemoBanner({registeredInventory=false,realInventory=false,context,panelAddress,runtimeProfile='local-demo'}:{registeredInventory?:boolean;realInventory?:boolean;context?:WorkspaceContext;panelAddress?:string;runtimeProfile?:RuntimeProfile}) {
  if(runtimeProfile==='v26-isolated-acceptance')return <div className="demo-banner workspace-context" aria-label="Çalışma ortamı"><span><strong>{runtimeIdentity(runtimeProfile).workspace}</strong> · {runtimeIdentity(runtimeProfile).description}{panelAddress&&<small>Panel adresi: {panelAddress}</small>}</span><span className="demo-banner-tag">{runtimeIdentity(runtimeProfile).tag}</span></div>;
  if(context)return <div className="demo-banner workspace-context" aria-label="Çalışma ortamı"><span><strong>{context.label}</strong> · {context.description}{panelAddress&&<small>Panel adresi: {panelAddress}</small>}</span><span className="demo-banner-tag">{context.access}</span></div>;
  if(realInventory)return <div className="demo-banner"><span className="demo-banner-icon"><Sparkles size={14}/></span><span><strong>Gerçek V1 aktarımı</strong> · Son kayıtlı envanter ve sağlık ölçümleri; canlı bağlantı kanıtı değildir.</span><span className="demo-banner-tag">SALT OKUNUR</span></div>;
  if(registeredInventory)return <div className="demo-banner"><span className="demo-banner-icon"><Sparkles size={14}/></span><span><strong>Kayıtlı cihazlar</strong> · Sentetik demo envanterinden ayrıdır. Bağlantılar yalnız açık operatör onayı ve sunucu güvenlik politikasıyla yapılır; otomatik polling kapalıdır.</span><span className="demo-banner-tag">API-SSL / SALT OKUNUR</span></div>;
  return <div className="demo-banner"><span className="demo-banner-icon"><Sparkles size={14} /></span>
    <span><strong>Demo ortamı</strong> · Veriler sentetiktir. Kalıcı demo işlemleri yalnız V2 yerel geliştirme veritabanında tutulur; canlı sistemlere bağlanılmaz.</span>
    <span className="demo-banner-tag">YEREL V2 DEMO</span>
  </div>;
}
