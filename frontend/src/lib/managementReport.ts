import type { Router, SubscriberDetailData } from './api.ts';
import { buildDailySummary, loadDailyInventory } from './dailySummary.ts';
import { turkeyToday } from './expiry.ts';
import { observationTime } from './subscriberObservation.ts';
import { loadRouterEvents } from './routerEvents.ts';
import type { AlarmEvent } from './routerEvents.ts';

export const reportPeriods={TODAY:'Bugün',YESTERDAY:'Dün',LAST_7:'Son 7 Gün'} as const;
export type ManagementPeriod=keyof typeof reportPeriods;
export const reportKinds={ALL:'Tüm işlem ve olaylar',OPERATIONS:'Tüm yönetim işlemleri',CREATE:'Abone oluşturma',PLAN_CHANGE:'Paket/profil değiştirme',STATUS_CHANGE:'Hesap durumu değiştirme',RENEWAL:'Abonelik yenileme',DATE_EDIT:'Bitiş tarihi düzenleme',INTERNET_DOWN:'İnternet kesintisi',INTERNET_UP:'Bağlantı geri gelmesi',WAN_CHANGE:'WAN değişikliği'} as const;
export type ManagementSource={read_at?:string;routers:Router[];details:SubscriberDetailData[];events:AlarmEvent[]|null};
export type ManagementFilter={period:ManagementPeriod;router:string;kind:keyof typeof reportKinds};
export function managementRange(period:ManagementPeriod|'LAST_30',now=new Date()){
  if((!Object.hasOwn(reportPeriods,period)&&period!=='LAST_30')||!Number.isFinite(now.getTime()))throw new Error('Geçerli rapor dönemi ve zamanı gerekli.');
  const today=turkeyToday(now),day=Date.parse(today+'T00:00:00Z');
  const shift=(offset:number)=>new Date(day+offset*86400000).toISOString().slice(0,10);
  const start=period==='YESTERDAY'?shift(-1):period==='LAST_7'?shift(-6):period==='LAST_30'?shift(-29):today;
  const end=period==='YESTERDAY'?shift(-1):today;
  const until=period==='YESTERDAY'?today:shift(1);
  return {start,end,from:Date.parse(start+'T00:00:00+03:00'),until:Date.parse(until+'T00:00:00+03:00'),cutoff:now.getTime()};
}
function stable(value:unknown):string {
  if(Array.isArray(value))return '['+value.map(stable).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>JSON.stringify(key)+':'+stable(item)).join(',')+'}';
  return JSON.stringify(value)??'undefined';
}
/** Identical copies collapse; conflicting payloads never silently choose a winner. */
export function uniqueReportRecords<T>(rows:T[],key:(row:T)=>string):T[]{
  const result=new Map<string,T>();
  for(const row of rows){const id=key(row);if(!id)throw new Error('Rapor kayıt kimliği eksik.');if(result.has(id)&&stable(result.get(id))!==stable(row))throw new Error('Aynı kimlikte çelişkili rapor kayıtları var.');result.set(id,row);}
  return [...result.values()];
}
export function reportRouterId(item:{router_id?:string|null;router_name:string},routers:Router[]):string|null{
  if(item.router_id)return routers.some(router=>router.id===item.router_id)?item.router_id:null;
  const matches=routers.filter(router=>router.name===item.router_name);
  return matches.length===1?matches[0].id:null;
}
export function buildManagementReport(source:ManagementSource,filter:ManagementFilter,now=new Date()){
  const range=managementRange(filter.period,now);
  if(!Object.hasOwn(reportKinds,filter.kind))throw new Error('Rapor olay filtresi geçersiz.');
  const routers=uniqueReportRecords(source.routers,row=>row.id);
  const details=uniqueReportRecords(source.details.map(detail=>({...detail,history:uniqueReportRecords(detail.history,event=>event.id)})),detail=>detail.item.id);
  // Validate all source records before scoping, including hidden conflicting audit IDs.
  buildDailySummary(routers,details,now);
  const scopedRouters=filter.router?routers.filter(router=>router.id===filter.router):routers;
  const scopedDetails=filter.router?details.filter(detail=>reportRouterId(detail.item,routers)===filter.router):details;
  const inventory=buildDailySummary(scopedRouters,scopedDetails,now);
  const inRange=(value:string|null)=>{
    const time=observationTime(value);if(!time)return false;
    const milliseconds=Date.parse(time);return milliseconds>=range.from&&milliseconds<range.until&&milliseconds<=range.cutoff;
  };
  const operations=inventory.operation_history.filter(event=>inRange(event.occurred_at)&&(filter.kind==='ALL'||filter.kind==='OPERATIONS'||event.operation===filter.kind)).map(event=>({...event,router_id:reportRouterId(scopedDetails.find(detail=>detail.item.id===event.subscriber_id)!.item,routers)}));
  const sourceEvents=source.events===null?null:uniqueReportRecords(source.events,event=>event.id);
  const expanded=sourceEvents?.flatMap(event=>{
    if(event.is_demo!==true)throw new Error('Rapor yalnız sentetik olayları destekler.');
    const records=[{id:event.id,kind:event.kind,occurred_at:event.started_at,router_id:event.router_id,lifecycle:event}];
    if(event.recovery_id&&event.ended_at)records.push({id:event.recovery_id,kind:'INTERNET_UP',occurred_at:event.ended_at,router_id:event.router_id,lifecycle:event});
    return records;
  })??null;
  const events=expanded===null?null:uniqueReportRecords(expanded,event=>event.id).filter(event=>(!filter.router||event.router_id===filter.router)&&inRange(event.occurred_at)&&(filter.kind==='ALL'||filter.kind===event.kind)).sort((a,b)=>Date.parse(b.occurred_at!)-Date.parse(a.occurred_at!)||a.id.localeCompare(b.id));
  return {range,inventory,operations,events,generated_at:now.toISOString(),
    counts:{operations:operations.length,events:events?.length??null,outages:events?.filter(event=>event.kind==='INTERNET_DOWN').length??null,recoveries:events?.filter(event=>event.kind==='INTERNET_UP').length??null,wan:events?.filter(event=>event.kind==='WAN_CHANGE').length??null},
    undated:{operations:inventory.operation_history.filter(event=>!observationTime(event.occurred_at)).length,events:sourceEvents?.filter(event=>(!filter.router||event.router_id===filter.router)&&!event.started_at).length??null},
  };
}
export async function loadManagementReport(_path:string,init?:RequestInit):Promise<ManagementSource>{
  const [inventory,events]=await Promise.all([loadDailyInventory(init,true),loadRouterEvents('/router-events',init)]);
  return {...inventory,events,read_at:new Date().toISOString()};
}

export function managementFilterFromHash(hash:string):ManagementFilter{
  const params=new URLSearchParams(hash.replace(/^#/,''));
  const period=params.get('period')??'TODAY',kind=params.get('kind')??'ALL';
  return {period:Object.hasOwn(reportPeriods,period)?period as ManagementPeriod:'TODAY',router:params.get('router')??'',kind:Object.hasOwn(reportKinds,kind)?kind as keyof typeof reportKinds:'ALL'};
}
export function managementReportHash(filter:ManagementFilter){return '#'+new URLSearchParams({module:'dashboard',view:'DAILY_REPORT',...filter}).toString();}
