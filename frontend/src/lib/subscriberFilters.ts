import type { Subscriber } from './api.ts';
import { matchesExpiry, type ExpiryFilter } from './expiry.ts';
import { matchesSource, type SourceFilter } from './source.ts';

export type SubscriberFilters = {
  query:string; router:string; plan:string; source:SourceFilter;
  status:'ALL'|'ACTIVE'|'PAUSED'|'PENDING'; expiry:ExpiryFilter;
};
export const EMPTY_SUBSCRIBER_FILTERS:SubscriberFilters={query:'',router:'',plan:'',source:'ALL',status:'ALL',expiry:'ALL'};
function searchKey(value:string) {
  return value.normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase('tr-TR').replace(/ı/g,'i');
}
export function filterSubscribers(rows:Subscriber[],filters:SubscriberFilters,today:string) {
  const terms=searchKey(filters.query.trim()).split(/\s+/).filter(Boolean);
  return rows.filter(row=>{
    const text=searchKey(`${row.username} ${row.customer_name} ${row.router_name} ${row.plan}`);
    return terms.every(term=>text.includes(term))
      && (!filters.router||row.router_name===filters.router)
      && (!filters.plan||row.plan===filters.plan)
      && matchesSource(row.source,filters.source)
      && (filters.status==='ALL'||row.status===filters.status)
      && matchesExpiry(row.expires_on,filters.expiry,today);
  });
}
export function subscriberFilterOptions(rows:Subscriber[],field:'router_name'|'plan',selected='') {
  // Retain a selected value after the last matching record is edited: show zero, not all.
  return [...new Set([...rows.map(row=>row[field]),selected].filter(value=>typeof value==='string'&&value.trim()))].sort((a,b)=>a.localeCompare(b,'tr'));
}
