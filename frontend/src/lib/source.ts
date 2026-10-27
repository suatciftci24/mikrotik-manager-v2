export type SubscriberSource = 'LOCAL' | 'RADIUS' | 'UNKNOWN';
export type SourceFilter = 'ALL' | SubscriberSource;

/** A router assignment, username or plan never establishes authority. */
export function subscriberSource(value: unknown): SubscriberSource {
  return value === 'LOCAL' || value === 'RADIUS' ? value : 'UNKNOWN';
}
export const sourceLabels: Record<SubscriberSource, string> = {LOCAL: 'LOCAL', RADIUS: 'RADIUS', UNKNOWN: 'Bilinmiyor'};
export function sourceDescription(value: unknown): string {
  switch (subscriberSource(value)) {
    case 'LOCAL': return 'Bu hesabın yetkili yönetim kaynağı, atandığı MikroTik router üzerindeki yerel kullanıcı kaydıdır. RADIUS bu hesabın yetkili kaynağı değildir.';
    case 'RADIUS': return 'Bu hesabın yetkili yönetim kaynağı FreeRADIUS kullanıcı kaydıdır. Router ataması, hesabın LOCAL olarak yönetildiği anlamına gelmez.';
    default: return 'Kaynak bilgisi bulunamadı veya doğrulanamadı. Router, kullanıcı adı veya paketten LOCAL/RADIUS tahmini yapılmaz. Kaynak doğrulanmadan değişiklik yapılamaz.';
  }
}
export function matchesSource(value: unknown, filter: SourceFilter): boolean {
  return filter === 'ALL' || subscriberSource(value) === filter;
}
