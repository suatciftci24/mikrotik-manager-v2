export type ExpiryStatus = 'EXPIRED' | 'WITHIN_7' | 'WITHIN_30' | 'ACTIVE' | 'UNKNOWN';
export type ExpiryFilter = ExpiryStatus | 'ALL';
export const expiryLabels: Record<ExpiryStatus, string> = {
  EXPIRED: 'Süresi dolmuş', WITHIN_7: '7 gün içinde bitecek', WITHIN_30: '30 gün içinde bitecek',
  ACTIVE: 'Aktif', UNKNOWN: 'Bitiş tarihi bilinmiyor',
};

/** Calendar dates, never elapsed 24-hour periods or the browser's local timezone. */
export function turkeyToday(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en', {timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(now);
  const part = (name: string) => parts.find(p => p.type === name)!.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}
function calendarDay(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date.getTime() / 86400000 : null;
}
export function expiryInfo(expiresOn: string | null | undefined, today = turkeyToday()): {status: ExpiryStatus; days: number | null} {
  const end = expiresOn ? calendarDay(expiresOn) : null;
  const start = calendarDay(today);
  if (end === null || start === null) return {status: 'UNKNOWN', days: null};
  const days = end - start;
  return {days, status: days < 0 ? 'EXPIRED' : days <= 7 ? 'WITHIN_7' : days <= 30 ? 'WITHIN_30' : 'ACTIVE'};
}
export function matchesExpiry(expiresOn: string | null | undefined, filter: ExpiryFilter, today: string): boolean {
  const info = expiryInfo(expiresOn, today);
  if (filter === 'ALL') return true;
  // The 30-day filter includes the urgent 7-day group, but excludes expired accounts.
  if (filter === 'WITHIN_30') return info.days !== null && info.days >= 0 && info.days <= 30;
  return info.status === filter;
}
export function expiryDate(expiresOn: string | null | undefined): string {
  if (!expiresOn || calendarDay(expiresOn) === null) return expiryLabels.UNKNOWN;
  return new Intl.DateTimeFormat('tr-TR', {dateStyle: 'medium', timeZone: 'UTC'}).format(new Date(`${expiresOn}T00:00:00Z`));
}
export function remainingDays(days: number | null): string {
  return days === null ? 'Bitiş tarihi bilinmiyor' : days < 0 ? `${Math.abs(days)} gün önce doldu` : days === 0 ? 'Bugün bitiyor (0 gün)' : `${days} gün kaldı`;
}
