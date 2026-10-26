import { useEffect, useState } from 'react';
import {
  ArrowDownRight, ArrowRight, ArrowUpRight, BellRing, CircleDollarSign, Clock3,
  Download, Gauge, MoreHorizontal, RadioTower, Router as RouterIcon, Sparkles,
  Users, Wifi, Zap,
} from 'lucide-react';
import { api, type DashboardData, type Router } from '../lib/api';
import type { ScreenKey } from '../components/Sidebar';
import { MetricCard, StatusBadge } from '../components/Status';

const money = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 });

function TrafficChart({ values }: { values: number[] }) {
  const points = values.map((value, index) => `${20 + index * 44},${110 - value}`).join(' ');
  const area = `20,116 ${points} 504,116`;
  return <div className="chart-wrap"><div className="chart-y"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div>
    <svg viewBox="0 0 524 128" className="traffic-chart" role="img" aria-label="Sentetik son 12 saat trafik eğilimi" preserveAspectRatio="none">
      <defs><linearGradient id="trafficFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#5e85f7" stopOpacity=".24" /><stop offset="1" stopColor="#5e85f7" stopOpacity="0" /></linearGradient></defs>
      {[20, 43, 66, 89, 112].map(y => <line key={y} x1="20" x2="504" y1={y} y2={y} className="chart-grid" />)}
      <polygon points={area} fill="url(#trafficFill)" /><polyline points={points} className="chart-line" />
      {values.map((value, index) => <circle key={index} cx={20 + index * 44} cy={110 - value} r="2.5" className="chart-point" />)}
    </svg><div className="chart-x"><span>00:00</span><span>02:00</span><span>04:00</span><span>06:00</span><span>08:00</span><span>10:00</span><span>12:00</span></div>
  </div>;
}

export function Dashboard({ onNavigate, onToast }: { onNavigate: (key: ScreenKey) => void; onToast: (message: string) => void }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [routers, setRouters] = useState<Router[]>([]);
  useEffect(() => {
    let alive = true;
    Promise.all([api<DashboardData>('/dashboard/summary'), api<{ items: Router[] }>('/routers')])
      .then(([summary, routerData]) => { if (alive) { setData(summary); setRouters(routerData.items); } })
      .catch(() => { if (alive) onToast('Demo API verisi yüklenemedi. Yerel API durumunu kontrol edin.'); });
    return () => { alive = false; };
  }, [onToast]);
  if (!data) return <div className="loading-state"><span className="spinner" />Demo çalışma alanı yükleniyor...</div>;
  const s = data.summary;
  return <div className="screen-stack">
    <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" />PAZARTESİ, 26 EKİM 2026</div>
      <h1>Günaydın, operatör <span>✳</span></h1><p>Ağınızın genel görünümü bugün sakin. İşte son durum.</p></div>
      <button className="button-secondary" onClick={() => onToast('Demo verisi güncel. Harici sisteme istek gönderilmedi.')}><Clock3 size={15} />26 Ekim, 12:42</button></section>
    <div className="metric-grid">
      <MetricCard title="Toplam Router" value={String(s.router_count)} note={`${s.routers_online} aktif · 1 dikkat`} icon={<RouterIcon size={17} />} tone="blue" change="%8.2" />
      <MetricCard title="Aktif Abone" value={money.format(s.subscribers_total)} note={`${money.format(s.subscribers_online)} çevrimiçi`} icon={<Users size={17} />} tone="violet" change="%12.4" />
      <MetricCard title="RADIUS Hesabı" value={money.format(s.radius_accounts)} note={`${money.format(s.local_accounts)} Local hesap`} icon={<RadioTower size={17} />} tone="teal" change="%4.6" />
      <MetricCard title="Aylık Gelir" value={`₺${money.format(s.monthly_revenue)}`} note="Tahmini toplam · KDV hariç" icon={<CircleDollarSign size={17} />} tone="amber" />
    </div>
    <div className="dashboard-grid">
      <section className="panel traffic-panel"><div className="panel-heading"><div><div className="panel-title"><h2>Ağ trafiği</h2><span className="demo-chip"><span className="pulse-dot" />DEMO</span></div><p>Genel WAN kullanımı · son 12 saat</p></div>
        <button className="select-small" onClick={() => onToast('Gösterilen grafik sentetiktir.')}>Son 12 saat <MoreHorizontal size={15} /></button></div>
        <div className="traffic-summary"><strong>1.84 <small>Gbps</small></strong><span className="positive"><ArrowUpRight size={14} />%8.4</span><span className="traffic-compare">önceki döneme göre</span></div>
        <TrafficChart values={data.traffic} /><div className="chart-legend"><span><i className="legend-blue" />İndirme <b>1.24 Gbps</b></span><span><i className="legend-violet" />Yükleme <b>602 Mbps</b></span><button onClick={() => onToast('Trafik analizi Phase 2 kapsamında.')}>Detaylı rapor <ArrowRight size={14} /></button></div>
      </section>
      <section className="panel attention-panel"><div className="panel-heading"><div><div className="panel-title"><h2>Dikkat gerektiren</h2><span className="attention-count">{s.attention_count}</span></div><p>İzleme gerektiren öğeler</p></div><button className="icon-button"><MoreHorizontal size={17} /></button></div>
        <div className="attention-card"><div className="attention-icon"><Gauge size={18} /></div><div className="attention-content"><strong>{routers.find(r => r.id === data.attention.router_id)?.name}</strong><span>{data.attention.message}</span><div className="attention-meter"><i style={{ width: `${data.attention.value}%` }} /></div><small>CPU {data.attention.value}% <span>· eşik %70</span></small></div><ArrowDownRight className="attention-trend" size={15} /></div>
        <button className="text-link" onClick={() => onNavigate('routers')}>Tüm uyarıları gör <ArrowRight size={14} /></button>
        <div className="ops-note"><Sparkles size={15} /><span>MikAjanı bu router için sağlık özeti hazırlayabilir.</span><button onClick={() => onNavigate('mikajani')}>Aç</button></div>
      </section>
    </div>
    <div className="dashboard-grid bottom-grid">
      <section className="panel router-panel"><div className="panel-heading"><div><div className="panel-title"><h2>Router durumu</h2><span className="soft-count">{routers.length}</span></div><p>Son telemetri özeti <span className="subtle-separator">·</span> <span className="fresh-text"><i /> az önce</span></p></div><button className="text-link" onClick={() => onNavigate('routers')}>Tümünü gör <ArrowRight size={14} /></button></div>
        <div className="router-list">{routers.slice(0, 4).map(router => <div className="router-list-row" key={router.id}><span className={`router-row-icon ${router.status.toLowerCase()}`}><RouterIcon size={16} /></span><span className="router-row-name"><strong>{router.name}</strong><small>{router.site} <i>·</i> {router.model}</small></span><span className="router-load"><Gauge size={13} />{router.cpu_percent}%</span><StatusBadge status={router.status} /></div>)}</div>
      </section>
      <section className="panel activity-panel"><div className="panel-heading"><div><div className="panel-title"><h2>Son aktiviteler</h2><span className="soft-count">3</span></div><p>Çalışma alanındaki son olaylar</p></div><button className="icon-button"><MoreHorizontal size={17} /></button></div>
        <div className="activity-list">{data.activity.map((event, index) => <div className="activity-row" key={event.title}><span className={`activity-icon ${event.kind}`}>{event.kind === 'subscriber' ? <Users size={14} /> : event.kind === 'radius' ? <RadioTower size={14} /> : <Wifi size={14} />}</span><span><strong>{event.title}</strong><small>{event.detail}</small></span><time>{event.time}</time>{index < data.activity.length - 1 && <i className="activity-connector" />}</div>)}</div>
      </section>
    </div>
    <div className="screen-footnote"><span><Download size={13} /> Veriler 26 Ekim 2026 12:42 itibarıyla</span><span><BellRing size={13} /> Bildirim tercihleri <ArrowRight size={13} /></span></div>
  </div>;
}
