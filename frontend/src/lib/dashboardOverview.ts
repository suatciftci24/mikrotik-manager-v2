import {api} from './api.ts';
import {buildDailySummary,loadDailyInventory,type DailySummary} from './dailySummary.ts';
import {buildSubscriptionAlerts} from './subscriptionAlerts.ts';
import {turkeyToday} from './expiry.ts';
import {managementRange,uniqueReportRecords} from './managementReport.ts';
import type {AlarmEvent} from './routerEvents.ts';
import type {AlarmPage} from './alarms.ts';
import {observationTime} from './subscriberObservation.ts';
import type {Router} from './api.ts';

export type DashboardSummary=DailySummary & {history_available?:boolean;within_3?:number;expiry_today?:number};
export function latestRouterObservation(routers:Router[],now=new Date()){
  const cutoff=now.getTime();if(!Number.isFinite(cutoff))return null;
  const times=routers.flatMap(router=>{const time=typeof router.last_seen==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(router.last_seen)?Date.parse(router.last_seen):NaN;return Number.isFinite(time)&&time<=cutoff?[time]:[];});
  return times.length?new Date(Math.max(...times)).toISOString():null;
}
/** Preserve the existing can_view inventory scope; report history stays server-authorized. */
export async function loadDashboardSummary(_path:string,init?:RequestInit):Promise<DashboardSummary>{
  const {routers,details}=await loadDailyInventory(init);
  const summary=buildDailySummary(routers,details);
  const alerts=buildSubscriptionAlerts(details.map(row=>row.item),summary.as_of_date);
  return {...summary,expiry_today:alerts.today,within_3:alerts.within_3,history_available:details.every(row=>row.history_available!==false)};
}
export function dashboardToday(data:DashboardSummary,events:AlarmEvent[]|null,now=new Date()){
  const range=managementRange('TODAY',now);
  const inRange=(value:string|null)=>{const time=observationTime(value);return time!==null&&Date.parse(time)>=range.from&&Date.parse(time)<range.until&&Date.parse(time)<=range.cutoff;};
  const history=data.history_available!==false&&data.as_of_date===turkeyToday(now);
  const rows=events===null?null:uniqueReportRecords(events,row=>row.id);
  if(rows?.some(row=>row.is_demo!==true))throw new Error('Sentetik olay kaynağı doğrulanamadı.');
  return {
    pppoe:history?data.operation_history.filter(row=>row.access_type==='PPPOE'&&inRange(row.occurred_at)).length:null,
    outages:rows?.filter(row=>row.kind==='INTERNET_DOWN'&&inRange(row.started_at)).length??null,
    wan:rows?.filter(row=>row.kind==='WAN_CHANGE'&&inRange(row.started_at)).length??null,
  };
}
export const dashboardAlarmPath='/alarms?state=ACTIVE&page_size=1';
export async function loadDashboardAlarms(path:string,init?:RequestInit){
  const data=await api<AlarmPage>(path,init);
  if(data.is_demo!==true||!Number.isInteger(data.summary?.critical)||data.summary.critical<0||typeof data.coverage?.connection_available!=='boolean'||typeof data.coverage?.ipsec_available!=='boolean')throw new Error('Sentetik alarm özeti doğrulanamadı.');
  return data;
}
export function dashboardCritical(data:AlarmPage){
  const complete=data.coverage.connection_available&&data.coverage.ipsec_available;
  return {value:data.summary.critical===0&&!complete?null:data.summary.critical,partial:!complete};
}
