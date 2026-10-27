import type { ReactNode } from 'react';

export function ResourceState({loading, error, retry}: {loading: boolean; error?: string; retry: () => void}) {
  if (loading) return <div className="loading-state" role="status" aria-busy="true"><span className="spinner"/>Veriler yükleniyor…</div>;
  if (error) return <div className="resource-error" role="alert"><p>{error}</p><button className="button-secondary" onClick={retry}>Tekrar dene</button></div>;
  return null;
}
export function DetailSection({title, children}: {title: string; children: ReactNode}) {
  return <section className="panel detail-section"><h2>{title}</h2>{children}</section>;
}
export function MissingData({children}: {children: ReactNode}) {
  return <p className="missing-data">Veri yok. {children}</p>;
}
export function Facts({items}: {items: [string, ReactNode][]}) {
  return <dl className="detail-facts">{items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 'Veri yok'}</dd></div>)}</dl>;
}
export function dateTime(value: string | null) {
  if (!value) return 'Veri yok';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Geçersiz tarih' : new Intl.DateTimeFormat('tr-TR', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Istanbul'}).format(date) + ' (İstanbul)';
}
