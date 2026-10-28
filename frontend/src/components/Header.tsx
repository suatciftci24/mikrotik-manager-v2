import { ThemePicker } from './ThemePicker';
import { Bell, ChevronDown, Command, Search, Sparkles } from 'lucide-react';
import type { ScreenKey, User } from './Sidebar';

const names: Record<ScreenKey, { title: string; crumb: string }> = {
  dashboard: { title: 'Genel Bakış', crumb: 'Workspace' }, routers: { title: 'Router Merkezi', crumb: 'Yönetim' },
  subscribers: { title: 'Abone Merkezi', crumb: 'Yönetim' }, radius: { title: 'RADIUS Merkezi', crumb: 'Yönetim' },
  operations: { title: 'Operasyon Merkezi', crumb: 'İzleme' }, mikajani: { title: 'MikAjanı', crumb: 'İzleme' },
  system: { title: 'Sistem ve Kullanıcı', crumb: 'Sistem' },
};

export function Header({ active, user, onOpenSearch, onOpenNotifications }: {
  active: ScreenKey; user: User; onOpenSearch: () => void; onOpenNotifications: () => void;
}) {
  const current = names[active];
  return <header className="topbar">
    <div className="breadcrumbs"><span>{current.crumb}</span><span className="crumb-slash">/</span><strong>{current.title}</strong></div>
    <div className="topbar-actions"><ThemePicker/>
      <div className="live-pill"><span className="pulse-dot" />Sentetik demo ortamı</div>
      <button className="search-trigger" onClick={onOpenSearch}><Search size={15} /><span>Hızlı ara...</span><kbd>⌘ K</kbd></button>
      <button className="icon-button notification-button" aria-label="Bildirimler" onClick={onOpenNotifications}><Bell size={17} /></button>
      <button className="top-user"><span className="mini-avatar">{user.name.split(' ').map(x => x[0]).join('').slice(0, 2)}</span><ChevronDown size={14} /></button>
    </div>
  </header>;
}

export function DemoBanner() {
  return <div className="demo-banner"><span className="demo-banner-icon"><Sparkles size={14} /></span>
    <span><strong>Demo ortamı</strong> · Veriler sentetiktir. Kalıcı demo işlemleri yalnız V2 yerel geliştirme veritabanında tutulur; canlı sistemlere bağlanılmaz.</span>
    <span className="demo-banner-tag">LOCAL PREVIEW</span>
  </div>;
}
