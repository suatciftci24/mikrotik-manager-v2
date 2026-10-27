import { api } from './api.ts';
import { observationTime } from './subscriberObservation.ts';

export type EventKind = 'INTERNET_DOWN' | 'INTERNET_UP' | 'WAN_CHANGE';
export type EventStatus = 'OPEN' | 'RESOLVED' | 'RECORDED' | 'UNKNOWN';
export type RouterEvent = {id:string;router_id:string;kind:EventKind;occurred_at:string|null;down_event_id?:string|null;state?:'OPEN'|'UNKNOWN';previous_wan?:string|null;new_wan?:string|null;is_demo:true};
export type EventSource = {items:RouterEvent[];available:boolean;is_demo:true};
export type AlarmEvent = RouterEvent & {started_at:string|null;ended_at:string|null;duration_seconds:number|null;status:EventStatus;recovery_id:string|null};
export const eventLabels: Record<EventKind,string> = {INTERNET_DOWN:'İnternet kesintisi',INTERNET_UP:'Bağlantı geri gelmesi',WAN_CHANGE:'WAN değişikliği'};
export const alarmStatusLabels: Record<EventStatus,string> = {OPEN:'Devam ediyor (kayıt)',RESOLVED:'Çözüldü',RECORDED:'Kaydedildi',UNKNOWN:'Bilinmiyor'};
export function projectRouterEvents(source: EventSource): AlarmEvent[] | null {
  if (source.is_demo!==true || typeof source.available!=='boolean' || !Array.isArray(source.items)) throw new Error('Sentetik olay kaynağı doğrulanamadı.');
  if (!source.available) {
    if(source.items.length) throw new Error('Kullanılamayan olay kaynağı kayıt içeriyor.');
    return null;
  }
  const ids=new Set<string>();
  for(const event of source.items){
    if(event.is_demo!==true || !event.id || !event.router_id || !Object.hasOwn(eventLabels,event.kind) || ids.has(event.id)) throw new Error('Olay kimliği, türü veya sentetik kaynak geçersiz.');
    ids.add(event.id);
  }
  const used=new Set<string>();
  const rows=source.items.map(event=>{
    const start=observationTime(event.occurred_at);
    const references=source.items.filter(up=>up.kind==='INTERNET_UP' && up.down_event_id===event.id);
    const up=event.kind==='INTERNET_DOWN' && references.length===1 ? references[0] : null;
    const end=up?observationTime(up.occurred_at):null;
    const linked=!!(up && up.router_id===event.router_id && start && end && Date.parse(end)>=Date.parse(start));
    if(linked)used.add(up!.id);
    const status:EventStatus=event.kind==='INTERNET_DOWN' ? linked?'RESOLVED':start && event.state==='OPEN' && references.length===0?'OPEN':'UNKNOWN' : start?'RECORDED':'UNKNOWN';
    return {...event,started_at:start,ended_at:linked?end:null,duration_seconds:linked?(Date.parse(end!)-Date.parse(start!))/1000:null,status,recovery_id:linked?up!.id:null};
  });
  return rows.filter(row=>!used.has(row.id)).sort((a,b)=>(Date.parse(b.started_at??'')||0)-(Date.parse(a.started_at??'')||0)||a.id.localeCompare(b.id));
}
export type AlarmFilter={router:string;kind:string;status:string;from:string;to:string;period:string};
export const emptyAlarmFilter:AlarmFilter={router:'',kind:'ALL',status:'ALL',from:'',to:'',period:'ALL'};
function boundary(day:string,end=false){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!observationTime(day+'T00:00:00+03:00'))throw new Error('Geçerli tarih aralığı gerekli.');
  return Date.parse(day+(end?'T23:59:59.999+03:00':'T00:00:00+03:00'));
}
export function filterAlarmEvents(rows:AlarmEvent[],filter:AlarmFilter,now=new Date()){
  if(!Number.isFinite(now.getTime()))throw new Error('Geçerli rapor zamanı gerekli.');
  if((filter.kind!=='ALL'&&!Object.hasOwn(eventLabels,filter.kind))||(filter.status!=='ALL'&&!Object.hasOwn(alarmStatusLabels,filter.status))||!['ALL','24H'].includes(filter.period))throw new Error('Olay filtresi geçersiz.');
  const from=filter.from?boundary(filter.from):-Infinity,to=filter.to?boundary(filter.to,true):Infinity;
  if(from>to)throw new Error('Başlangıç tarihi bitişten sonra olamaz.');
  return rows.filter(row=>{
    const time=row.started_at?Date.parse(row.started_at):null;
    return (!filter.router||row.router_id===filter.router) && (filter.kind==='ALL'||row.kind===filter.kind) && (filter.status==='ALL'||row.status===filter.status)
      && ((!filter.from&&!filter.to)||(time!==null&&time>=from&&time<=to))
      && (filter.period!=='24H'||(time!==null&&time>=now.getTime()-86400000&&time<=now.getTime()));
  });
}
export function alarmCounts(rows:AlarmEvent[]|null,now=new Date()){
  if(rows===null)return {outages:null,wan:null};
  const recent=filterAlarmEvents(rows,{...emptyAlarmFilter,period:'24H'},now);
  return {outages:recent.filter(e=>e.kind==='INTERNET_DOWN').length,wan:recent.filter(e=>e.kind==='WAN_CHANGE').length};
}
export async function loadRouterEvents(path:string,init?:RequestInit){return projectRouterEvents(await api<EventSource>(path,init));}
export function durationText(seconds:number|null){return seconds===null?'Veri yok':`${new Intl.NumberFormat('tr-TR',{maximumFractionDigits:3}).format(seconds)} sn`;}
