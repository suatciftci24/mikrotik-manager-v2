import type { DemoSession, Subscriber } from './api.ts';
import { buildDailySummary } from './dailySummary.ts';
import { managementRange, reportRouterId, uniqueReportRecords } from './managementReport.ts';
import type { ManagementSource } from './managementReport.ts';
import { subscriberReportData, trafficTotals, measuredBytes } from './subscriberReports.ts';
import { observationTime } from './subscriberObservation.ts';
import { connectionStatus } from './routerReport.ts';

export const internetPeriods={TODAY:'Bugün',YESTERDAY:'Dün',LAST_7:'Son 7 Gün',LAST_30:'Son 30 Gün'} as const;
export type InternetFilter={period:keyof typeof internetPeriods;router:string;subscriber:string};
export function volumeGB(value:number|null){const bytes=measuredBytes(value);return bytes===null?'Veri yok':new Intl.NumberFormat('tr-TR',{maximumFractionDigits:9}).format(bytes/1_000_000_000)+' GB';}
export function internetFilterFromHash(hash:string):InternetFilter{
  const params=new URLSearchParams(hash.replace(/^#/,'')),period=params.get('period')??'TODAY';
  return {period:Object.hasOwn(internetPeriods,period)?period as InternetFilter['period']:'TODAY',router:params.get('router')??'',subscriber:params.get('subscriber')??''};
}
export function internetReportHash(filter:InternetFilter){return '#'+new URLSearchParams({module:'dashboard',view:'INTERNET_REPORT',...filter}).toString();}
export function buildInternetReport(source:ManagementSource,filter:InternetFilter,now=new Date()){
  const range=managementRange(filter.period,now);
  const routers=uniqueReportRecords(source.routers,row=>row.id);
  const details=uniqueReportRecords(source.details,row=>row.item.id);
  buildDailySummary(routers,details,now);
  const owners=new Map<string,string>();
  const normalized=details.map(detail=>{
    const report=detail.item.demo_report;
    const item:Subscriber=report?{...detail.item,demo_report:{...report,sessions:uniqueReportRecords(report.sessions,row=>row.id),traffic:uniqueReportRecords(report.traffic,row=>row.id)}}:detail.item;
    for(const [kind,records] of [['session',item.demo_report?.sessions??[]],['traffic',item.demo_report?.traffic??[]]] as const){
      for(const record of records){const key=kind+':'+record.id;if(owners.has(key)&&owners.get(key)!==item.id)throw new Error('Ölçüm veya oturum kimliği birden fazla aboneye ait.');owners.set(key,item.id);}
    }
    return {item,report:subscriberReportData(item,range.end,now),router_id:reportRouterId(item,routers)};
  });
  const matches=normalized.filter(row=>(!filter.router||row.router_id===filter.router)&&(!filter.subscriber||row.item.id===filter.subscriber));
  const inRange=(value:string|null)=>{const valid=observationTime(value);return valid!==null&&Date.parse(valid)>=range.from&&Date.parse(valid)<range.until&&Date.parse(valid)<=range.cutoff;};
  const overlaps=(session:DemoSession,recordedAt:string|null)=>{
    const start=observationTime(session.started_at),end=observationTime(session.ended_at);
    if(!start||Date.parse(start)>=range.until||Date.parse(start)>range.cutoff)return false;
    if(Date.parse(start)>=range.from)return true;
    if(end)return Date.parse(end)>range.from;
    // An old ACTIVE snapshot does not prove that a session continued into a later day.
    const observed=observationTime(recordedAt);
    return session.state==='ACTIVE'&&observed!==null&&Date.parse(observed)>=range.from;
  };
  const subscribers=matches.map(row=>({...row,totals:trafficTotals(row.report.traffic,range.start,range.end,now),sessions:row.report.sessions.filter(session=>overlaps(session,row.report.recorded_at)),traffic:row.report.traffic.filter(sample=>inRange(sample.measured_at))}));
  const samples=subscribers.flatMap(row=>row.traffic);
  const sessions=subscribers.flatMap(row=>row.sessions.map(session=>({...session,subscriber_id:row.item.id,customer_name:row.item.customer_name,router_id:row.router_id}))).sort((a,b)=>Date.parse(b.started_at!)-Date.parse(a.started_at!));
  const totals=trafficTotals(samples,range.start,range.end,now);
  const allEvents=source.events===null?null:uniqueReportRecords(source.events,event=>event.id);
  const selectedRouterIds=new Set(subscribers.map(row=>row.router_id).filter((id):id is string=>id!==null));
  const selectedRouters=routers.filter(router=>(!filter.router||router.id===filter.router)&&(!filter.subscriber||selectedRouterIds.has(router.id)));
  const routerRows=selectedRouters.map(router=>{
    const events=allEvents?.filter(event=>{if(event.is_demo!==true)throw new Error('Sentetik router olay kaynağı gerekli.');return event.router_id===router.id&&(inRange(event.started_at)||!!(event.recovery_id&&inRange(event.ended_at)));}).sort((a,b)=>Math.max(Date.parse(b.started_at??'')||0,Date.parse(b.ended_at??'')||0)-Math.max(Date.parse(a.started_at??'')||0,Date.parse(a.ended_at??'')||0))??null;
    return {router,status:connectionStatus(router.status),wan_download:null,wan_upload:null,events};
  });
  // A bucket contains recorded deltas, never an estimate for unsampled subscribers/time.
  const count=filter.period==='TODAY'||filter.period==='YESTERDAY'?24:filter.period==='LAST_7'?7:30;
  const hourly=count===24;
  const buckets=Array.from({length:count},(_,index)=>{
    const from=range.from+index*(hourly?3600000:86400000),until=from+(hourly?3600000:86400000);
    const grouped=samples.filter(sample=>Date.parse(sample.measured_at)>=from&&Date.parse(sample.measured_at)<until);
    const label=hourly?String(index).padStart(2,'0')+':00':new Intl.DateTimeFormat('tr-TR',{timeZone:'Europe/Istanbul',day:'2-digit',month:'2-digit'}).format(new Date(from));
    return {from:new Date(from).toISOString(),until:new Date(until).toISOString(),label,samples:grouped.length,...trafficTotals(grouped,range.start,range.end,now)};
  });
  return {range,routers:routerRows,subscribers,sessions,buckets,totals,source_subscribers:subscribers.filter(row=>row.report.recorded_at!==null).length,measured_subscribers:subscribers.filter(row=>row.traffic.length>0).length,session_count:subscribers.some(row=>row.report.recorded_at!==null)?sessions.length:null};
}
