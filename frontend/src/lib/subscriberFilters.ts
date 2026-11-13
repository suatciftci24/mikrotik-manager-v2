import type { Subscriber } from './api.ts';
import { expiryInfo, matchesExpiry, type ExpiryFilter } from './expiry.ts';
import { matchesSource, type SourceFilter } from './source.ts';

export type SubscriberFilters = {
  query:string; router:string;router_id?:string; plan:string; source:SourceFilter; access?:'ALL'|'PPPOE'|'HOTSPOT'|'UNKNOWN';
  status:'ALL'|'ACTIVE'|'PAUSED'|'PENDING'; expiry:ExpiryFilter;
};
export const EMPTY_SUBSCRIBER_FILTERS:SubscriberFilters={query:'',router:'',plan:'',source:'ALL',status:'ALL',expiry:'ALL'};
function searchKey(value:string) {
  return value.normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase('tr-TR').replace(/ı/g,'i');
}
export function filterSubscribers(rows:Subscriber[],filters:SubscriberFilters,today:string) {
  const terms=searchKey(filters.query.trim()).split(/\s+/).filter(Boolean);
  return rows.filter(row=>{
    const text=searchKey(`${row.username??''} ${row.customer_name??''} ${row.router_name??''} ${row.plan??''} ${row.ip_address??''} ${row.id}`);
    return terms.every(term=>text.includes(term))
      && (!filters.router||row.router_name===filters.router)
      && (!filters.router_id||row.router_id===filters.router_id)
      && (!filters.plan||row.plan===filters.plan)
      && matchesSource(row.source,filters.source)
      && (!filters.access||filters.access==='ALL'||(filters.access==='UNKNOWN'?!['PPPOE','HOTSPOT'].includes(row.access_type??''):row.access_type===filters.access))
      && (filters.status==='ALL'||row.status===filters.status)
      && matchesExpiry(row.expires_on,filters.expiry,today);
  });
}
export function subscriberFilterOptions(rows:Subscriber[],field:'router_name'|'plan',selected='') {
  // Retain a selected value after the last matching record is edited: show zero, not all.
  return [...new Set([...rows.map(row=>row[field]),selected].filter(value=>typeof value==='string'&&value.trim()))].sort((a,b)=>a.localeCompare(b,'tr'));
}

export type SubscriberSort = 'NAME'|'EXPIRY'|'EXPIRY_DESC';
/** Sort a copy; unknown dates always follow known dates in either direction. */
export function sortSubscribers<T extends Pick<Subscriber,'id'|'customer_name'|'expires_on'>>(rows:T[],sort:SubscriberSort,today:string):T[] {
  return [...rows].sort((a,b)=>{
    if(sort!=='NAME'){
      const first=expiryInfo(a.expires_on,today).days,second=expiryInfo(b.expires_on,today).days;
      if(first===null&&second!==null)return 1;
      if(second===null&&first!==null)return -1;
      if(first!==null&&second!==null&&first!==second)return sort==='EXPIRY'?first-second:second-first;
    }
    return (a.customer_name??'').localeCompare(b.customer_name??'','tr')||a.id.localeCompare(b.id);
  });
}
