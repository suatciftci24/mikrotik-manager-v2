import { turkeyToday } from './expiry.ts';

export type ReportPeriod = 'TODAY' | 'WEEK' | 'MONTH';

/** Calendar windows in Istanbul; dates are inclusive, not rolling 24-hour windows. */
export function subscriberReportPeriods(today = turkeyToday()) {
  const day = new Date(`${today}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today) || !Number.isFinite(day.getTime()) || day.toISOString().slice(0,10)!==today) {
    throw new Error('Geçerli bir Türkiye takvim günü gerekli.');
  }
  const shift = (days: number) => new Date(day.getTime()+days*86400000).toISOString().slice(0,10);
  return [
    {id:'TODAY' as const, label:'Bugün', start:today, end:today},
    {id:'WEEK' as const, label:'Bu hafta (Pazartesi–bugün)', start:shift(-((day.getUTCDay()+6)%7)), end:today},
    {id:'MONTH' as const, label:'Son 30 gün (bugün dahil)', start:shift(-29), end:today},
  ];
}
