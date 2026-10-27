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

import type { Subscriber, DemoSession, DemoTraffic } from './api.ts';
import { observationTime } from './subscriberObservation.ts';
import { turkeyToday as dayOf } from './expiry.ts';
export function measuredBytes(value:unknown):number|null{return typeof value==='number'&&Number.isSafeInteger(value)&&value>=0?value:null;}
export function bytesText(value:number|null){const bytes=measuredBytes(value);return bytes===null?'Veri yok':new Intl.NumberFormat('tr-TR',{maximumFractionDigits:3}).format(bytes/1048576)+' MiB';}
export function subscriberReportData(item:Subscriber,today:string,now=new Date()){
  const report=item.demo_report;
  const periods=subscriberReportPeriods(today);
  if(item.is_demo!==true)throw new Error('Sentetik abone kaynağı gerekli.');
  if(!report)return {sessions:[] as (DemoSession&{duration:number|null})[],traffic:[] as DemoTraffic[],periods:periods.map(p=>({...p,download:null as number|null,upload:null as number|null,total:null as number|null})),recorded_at:null};
  if(report.is_demo!==true||report.subscriber_id!==item.id||report.router_id!==item.router_id||!observationTime(report.recorded_at))throw new Error('Demo rapor kimliği veya kaynağı doğrulanamadı.');
  for(const records of [report.sessions,report.traffic]){
    if(!Array.isArray(records)||new Set(records.map(r=>r.id)).size!==records.length||records.some(r=>r.is_demo!==true))throw new Error('Demo rapor kayıtları tekil veya sentetik değil.');
  }
  const sessions=report.sessions.map(session=>{
    const rawStart=observationTime(session.started_at),rawEnd=observationTime(session.ended_at);
    const start=rawStart&&Date.parse(rawStart)<=now.getTime()?rawStart:null,end=rawEnd&&Date.parse(rawEnd)<=now.getTime()?rawEnd:null;
    const state:DemoSession['state'] = start && (session.state==='ACTIVE'&&!end || session.state==='CLOSED'&&end&&Date.parse(end)>=Date.parse(start)) ? session.state : 'UNKNOWN';
    return {...session,state,started_at:start,ended_at:end,duration:start&&end&&Date.parse(end)>=Date.parse(start)?(Date.parse(end)-Date.parse(start))/1000:null};
  });
  const traffic=report.traffic.filter(sample=>observationTime(sample.measured_at)&&Date.parse(sample.measured_at)<=now.getTime());
  const sums=periods.map(period=>({...period,...trafficTotals(traffic,period.start,period.end,now)}));
  return {sessions,traffic,periods:sums,recorded_at:report.recorded_at};
}

/** Recorded byte deltas only; missing directions and empty buckets remain unknown. */
export function trafficTotals(samples:DemoTraffic[],start:string,end:string,now=new Date()){
  const selected=samples.filter(sample=>{if(!observationTime(sample.measured_at)||Date.parse(sample.measured_at)>now.getTime())return false;const day=dayOf(new Date(sample.measured_at));return day>=start&&day<=end;});
  const sum=(field:'download_bytes'|'upload_bytes')=>{
    if(!selected.length||selected.some(sample=>measuredBytes(sample[field])===null))return null;
    const value=selected.reduce((n,sample)=>n+sample[field]!,0);return Number.isSafeInteger(value)?value:null;
  };
  const download=sum('download_bytes'),upload=sum('upload_bytes');
  return {download,upload,total:download!==null&&upload!==null&&Number.isSafeInteger(download+upload)?download+upload:null};
}
