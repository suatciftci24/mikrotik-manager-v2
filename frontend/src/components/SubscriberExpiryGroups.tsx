import {expiryLabels,type ExpiryStatus} from '../lib/expiry';
export const subscriberExpiryGroups=['EXPIRED','TODAY','WITHIN_3','WITHIN_7','WITHIN_30','ACTIVE','UNKNOWN'] as const;
export type ExpiryGroup='ALL'|ExpiryStatus;
export function SubscriberExpiryGroups({counts,value,onChange}:{counts:Record<ExpiryStatus,number>;value:ExpiryGroup;onChange:(value:ExpiryGroup)=>void}){
 return <section className="subscriber-expiry-groups" aria-label="Birbirini dışlayan bitiş grupları"><p>Türkiye gününe göre bitiş grupları · Her abone yalnız bir gruptadır.</p><div role="group" aria-label="Bitiş grubu seç"><button type="button" aria-pressed={value==='ALL'} onClick={()=>onChange('ALL')}>Tümü <strong>{subscriberExpiryGroups.reduce((sum,key)=>sum+counts[key],0)}</strong></button>{subscriberExpiryGroups.map(key=><button type="button" key={key} className={'expiry-'+key.toLowerCase()} aria-pressed={value===key} onClick={()=>onChange(key)}>{expiryLabels[key]} <strong>{counts[key]}</strong></button>)}</div></section>;
}
