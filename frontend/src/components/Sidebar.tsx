import {
  Activity, ArrowDownUp, ChevronDown, CircleHelp, Command, Gauge, LayoutDashboard,
  LogOut, Network, RadioTower, Router as RouterIcon, Settings2, ShieldCheck, Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type ScreenKey = 'dashboard' | 'routers' | 'subscribers' | 'radius' | 'operations' | 'mikajani' | 'system';
export type User = { id: string; name: string; email: string; role: string; is_demo: boolean };

const nav: { key: ScreenKey; label: string; icon: LucideIcon; group: string }[] = [
  { key: 'dashboard', label: 'Genel Bakış', icon: LayoutDashboard, group: 'WORKSPACE' },
  { key: 'routers', label: 'Router Merkezi', icon: RouterIcon, group: 'YÖNETİM' },
  { key: 'subscribers', label: 'Abone Merkezi', icon: Users, group: 'YÖNETİM' },
  { key: 'radius', label: 'RADIUS Merkezi', icon: RadioTower, group: 'YÖNETİM' },
  { key: 'operations', label: 'Operasyon Merkezi', icon: ArrowDownUp, group: 'İZLEME' },
  { key: 'mikajani', label: 'MikAjanı', icon: Activity, group: 'İZLEME' },
  { key: 'system', label: 'Sistem ve Kullanıcı', icon: Settings2, group: 'SİSTEM' },
];

export function Sidebar({ active, onNavigate, user, onLogout }: {
  active: ScreenKey; onNavigate: (key: ScreenKey) => void; user: User; onLogout: () => void;
}) {
  let group = '';
  return <aside className="sidebar">
    <button className="brand" onClick={() => onNavigate('dashboard')} aria-label="V2 genel bakış">
      <span className="brand-mark"><Network size={19} strokeWidth={2.3} /></span>
      <span className="brand-copy"><strong>mikrotik<span>.</span></strong><small>MANAGER <b>V2</b></small></span>
      <ChevronDown className="brand-caret" size={15} />
    </button>
    <button className="workspace-switch"><span className="workspace-dot" /><span><strong>Demo çalışma alanı</strong><small>Yerel geliştirme</small></span><ChevronDown size={15} /></button>
    <div className="side-label">ÇALIŞMA ALANI</div>
    <div className="nav-list">{nav.map(item => {
      const first = item.group !== group; group = item.group;
      const Icon = item.icon;
      return <div key={item.key}>{first && <div className="nav-group">{item.group}</div>}
        <button className={`nav-item ${active === item.key ? 'active' : ''}`} onClick={() => onNavigate(item.key)}>
          <Icon size={17} strokeWidth={active === item.key ? 2 : 1.75} /><span>{item.label}</span>
          {item.key === 'mikajani' && <i className="nav-spark">✦</i>}
          {item.key === 'routers' && <span className="nav-count">4</span>}
        </button>
      </div>;
    })}</div>
    <div className="sidebar-bottom">
      <div className="system-status"><span className="pulse-dot" /><span><strong>Yerel ortam hazır</strong><small>Harici bağlantılar kapalı</small></span><ShieldCheck size={16} /></div>
      <button className="help-link"><CircleHelp size={16} /><span>Yardım merkezi</span><span className="kbd">?</span></button>
      <div className="profile">
        <div className="avatar">{user.name.split(' ').slice(0, 2).map(x => x[0]).join('')}</div>
        <span className="profile-copy"><strong>{user.name}</strong><small>{user.role}</small></span>
        <button className="icon-button profile-menu" title="Oturumu kapat" onClick={onLogout}><LogOut size={16} /></button>
      </div>
    </div>
    <div className="sidebar-foot"><span>MIKROTIK MANAGER</span><span>0.1.0 · PHASE 01</span></div>
  </aside>;
}

export function MobileHeader({ onMenu }: { onMenu: () => void }) {
  return <div className="mobile-header"><button className="icon-button" onClick={onMenu}><Command size={18} /></button>
    <div className="mobile-brand"><span className="brand-mark"><Network size={16} /></span><strong>mikrotik<span>.</span> <small>V2</small></strong></div>
    <span className="pulse-dot" /></div>;
}
