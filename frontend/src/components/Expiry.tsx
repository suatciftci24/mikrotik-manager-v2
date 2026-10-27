import { expiryDate, expiryInfo, expiryLabels, remainingDays } from '../lib/expiry';

export function ExpiryBadge({expiresOn, today}: {expiresOn: string | null; today: string}) {
  const info = expiryInfo(expiresOn, today);
  return <span className={`expiry-badge expiry-${info.status.toLowerCase()}`}>{expiryLabels[info.status]}</span>;
}
export function ExpirySummary({expiresOn, today}: {expiresOn: string | null; today: string}) {
  const info = expiryInfo(expiresOn, today);
  return <div className={`expiry-summary expiry-${info.status.toLowerCase()}`}><strong>{expiryDate(expiresOn)}</strong><ExpiryBadge expiresOn={expiresOn} today={today}/><span>{remainingDays(info.days)}</span><small>Sentetik demo bitiş kaydı · Türkiye takvim günü (Europe/Istanbul)</small></div>;
}
