import { Check, Clock3, RadioTower, Router as RouterIcon, Users } from 'lucide-react';
import type { ReactNode } from 'react';

export function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = { ONLINE: 'Çevrimiçi', DEGRADED: 'Dikkat', OFFLINE: 'Çevrimdışı', ACTIVE: 'Aktif', PAUSED: 'Duraklatıldı', PENDING: 'Bekliyor' };
  return <span className={`status-badge ${status.toLowerCase()}`}><i />{labels[status] ?? status}</span>;
}

export function SourceBadge({ source }: { source: 'LOCAL' | 'RADIUS' }) {
  return <span className={`source-badge ${source.toLowerCase()}`}>{source === 'LOCAL' ? <RouterIcon size={12} /> : <RadioTower size={12} />}{source}</span>;
}

export function MetricCard({ title, value, note, icon, tone = 'blue', change }: {
  title: string; value: string; note: string; icon: ReactNode; tone?: string; change?: string;
}) {
  return <article className="metric-card"><div className="metric-card-top"><span>{title}</span><span className={`metric-icon ${tone}`}>{icon}</span></div>
    <div className="metric-value-row"><strong>{value}</strong>{change && <span className="metric-change">↗ {change}</span>}</div>
    <div className="metric-foot"><span>{note}</span>{title.includes('Router') ? <RouterIcon size={13} /> : title.includes('Abone') ? <Users size={13} /> : title.includes('RADIUS') ? <RadioTower size={13} /> : <Clock3 size={13} />}</div>
  </article>;
}

export function EmptyModule({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  return <div className="module-empty"><div className="empty-orbit"><span>{icon}<Check className="orbit-check" size={15} /></span></div>
    <span className="eyebrow">MODÜL İSKELETİ HAZIR</span><h2>{title}</h2><p>{description}</p>
    <div className="empty-status"><span className="pulse-dot" />Faz 1 kapsamında bağlantılar kapalı</div></div>;
}
