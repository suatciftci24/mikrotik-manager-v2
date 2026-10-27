import type { Subscriber } from './api.ts';
import { expiryInfo, type ExpiryStatus } from './expiry.ts';

/** Counts the filtered inventory once; cumulative cards must never be added together. */
export function buildSubscriptionAlerts(rows:Subscriber[],today:string) {
  const buckets:Record<ExpiryStatus,number>={EXPIRED:0,TODAY:0,WITHIN_3:0,WITHIN_7:0,WITHIN_30:0,ACTIVE:0,UNKNOWN:0};
  const ids=new Set<string>();
  for (const row of rows) {
    if (row.is_demo!==true || typeof row.id!=='string' || !row.id || ids.has(row.id)) throw new Error('Uyarı özeti için tekil sentetik demo kayıtları gerekli.');
    ids.add(row.id);
    buckets[expiryInfo(row.expires_on,today).status]++;
  }
  const within3=buckets.TODAY+buckets.WITHIN_3;
  const within7=within3+buckets.WITHIN_7;
  return {
    total:rows.length, expired:buckets.EXPIRED, today:buckets.TODAY, within_3:within3, within_7:within7,
    within_30:within7+buckets.WITHIN_30, valid:rows.length-buckets.EXPIRED-buckets.UNKNOWN,
    after_30:buckets.ACTIVE, unknown:buckets.UNKNOWN, warning:buckets.EXPIRED+within7,
  };
}
export type SubscriptionAlertSummary=ReturnType<typeof buildSubscriptionAlerts>;
