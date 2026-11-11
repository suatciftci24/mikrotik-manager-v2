import {api} from './api.ts';
import {subscriberSource,type SubscriberSource} from './source.ts';
import {linkedDetailHash} from './detailLinks.ts';

export type RadiusScope='LEGACY'|'PERSISTENT';
export type RadiusFilters={scope:RadiusScope;authority:'ALL'|SubscriberSource;access:'ALL'|'PPPOE'|'HOTSPOT'|'UNKNOWN';query:string};
export type RadiusRecord={id:string;name:string;username:string;authority:SubscriberSource;access:'PPPOE'|'HOTSPOT'|'UNKNOWN';routerId:string|null;routerName:string|null;plan:string;expiresOn:string|null;status:string;revision:number};
export function radiusFiltersFromHash(hash:string):RadiusFilters{
 const p=new URLSearchParams(hash.replace(/^#/,''));
 if(p.get('module')!=='radius')return {scope:'LEGACY',authority:'ALL',access:'ALL',query:''};
 return {scope:p.get('scope')==='PERSISTENT'?'PERSISTENT':'LEGACY',authority:(['LOCAL','RADIUS','UNKNOWN'].includes(p.get('authority')??'')?p.get('authority'):'ALL') as RadiusFilters['authority'],access:(['PPPOE','HOTSPOT','UNKNOWN'].includes(p.get('access')??'')?p.get('access'):'ALL') as RadiusFilters['access'],query:(p.get('q')??'').slice(0,120)};
}
export function radiusHash(filters:RadiusFilters){return '#'+new URLSearchParams({module:'radius',view:'SYNTHETIC_VISIBILITY',scope:filters.scope,authority:filters.authority,access:filters.access,q:filters.query});}
export function radiusDetailLink(row:RadiusRecord,filters:RadiusFilters,router=false){
 if(router&&(!row.routerId||!row.routerId.startsWith(filters.scope==='PERSISTENT'?'demo-managed-router-':'demo-router-')))return null;
 return linkedDetailHash(router?{module:'routers',id:row.routerId!,source:filters.scope==='PERSISTENT'?'MANAGED_DEMO':'DEMO'}:{module:'subscribers',id:row.id,workspace:filters.scope},radiusHash(filters));
}
type Raw={id:string;customer_name:string;username:string;source?:unknown;access_type?:unknown;router_id?:string|null;router_name?:string|null;plan:string;expires_on:string|null;status:string;revision:number;is_demo?:boolean};
/** No provider selection, secret lookup, or RADIUS/network dispatch exists here. */
export function projectRadiusRecord(row:Raw,scope:RadiusScope):RadiusRecord{
 if(!row||!row.id?.startsWith(scope==='PERSISTENT'?'demo-managed-sub-':'demo-sub-')||!Number.isInteger(row.revision)||row.revision<0||row.is_demo===false||(scope==='LEGACY'&&row.is_demo!==true)||typeof row.customer_name!=='string'||typeof row.username!=='string'||typeof row.plan!=='string'||typeof row.status!=='string'||(row.expires_on!==null&&typeof row.expires_on!=='string')||(row.router_id!=null&&typeof row.router_id!=='string')||(row.router_name!=null&&typeof row.router_name!=='string'))throw new Error('Sentetik hesap kimliği veya revizyonu doğrulanamadı.');
 return {id:row.id,name:row.customer_name,username:row.username,authority:subscriberSource(row.source),access:row.access_type==='PPPOE'||row.access_type==='HOTSPOT'?row.access_type:'UNKNOWN',routerId:row.router_id??null,routerName:row.router_name??null,plan:row.plan,expiresOn:row.expires_on,status:row.status,revision:row.revision};
}
export async function loadRadiusVisibility(scope:RadiusScope,centralAdmin:boolean,init?:RequestInit):Promise<RadiusRecord[]>{
 if(!['LEGACY','PERSISTENT'].includes(scope))throw new Error('Kayıt deposu doğrulanamadı.');
 if(scope==='PERSISTENT'&&!centralAdmin)throw new Error('Kalıcı sentetik kayıtlar için merkezi yönetim yetkisi gerekli.');
 const path=scope==='LEGACY'?'/subscribers':'/subscriber-workspace';
 const rows:RadiusRecord[]=[],ids=new Set<string>();let expected:number|undefined;
 for(let page=1;page<=1000;page++){
  const data=await api<{items:Raw[];total:number;is_demo:true}>(scope==='LEGACY'?path:path+'?page_size=100&page='+page,init);
  if(!data||data.is_demo!==true||!Array.isArray(data.items)||!Number.isInteger(data.total)||data.total<0||(expected!==undefined&&expected!==data.total))throw new Error('Sentetik hesap kapsamı doğrulanamadı; yeniden yükleyin.');
  expected=data.total;
  for(const raw of data.items){const row=projectRadiusRecord(raw,scope);if(ids.has(row.id))throw new Error('Hesap sayfaları tekil değil; eksik özet gösterilmedi.');ids.add(row.id);rows.push(row);}
  if(rows.length===expected)return rows;
  if(scope==='LEGACY'||!data.items.length||rows.length>expected)break;
 }
 throw new Error('Hesapların tamamı okunamadı; eksik kaynak sıfır sayılmaz.');
}
export function filterRadiusRecords(rows:RadiusRecord[],filters:RadiusFilters){
 const key=(s:string)=>s.normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase('tr-TR').replace(/ı/g,'i');
 const terms=key(filters.query.trim()).split(/\s+/).filter(Boolean);
 return rows.filter(row=>(filters.authority==='ALL'||row.authority===filters.authority)&&(filters.access==='ALL'||row.access===filters.access)&&terms.every(term=>key([row.name,row.username,row.routerId,row.routerName,row.plan].join(' ')).includes(term)));
}
