import {turkeyToday} from './expiry.ts';

export type AuditSource='SUBSCRIBER'|'WORKSPACE'|'USER'|'WAN';
export type AuditFilter={start:string;end:string;source:AuditSource;router_id:string;actor_id:string;operation:string;result:'ALL'|'SUCCESS'|'FAILED'|'UNKNOWN';query:string;page:number};
const SOURCES:AuditSource[]=['SUBSCRIBER','WORKSPACE','USER','WAN'];
export function auditFilter(hash:string,now=new Date()):AuditFilter{
 const p=new URLSearchParams(hash.replace(/^#/,''));
 const source=p.get('audit_source') as AuditSource;
 const result=p.get('audit_result');
 return {start:p.get('start')??turkeyToday(now),end:p.get('end')??turkeyToday(now),source:SOURCES.includes(source)?source:'SUBSCRIBER',router_id:p.get('router_id')??'',actor_id:p.get('actor_id')??'',operation:p.get('operation')??'',result:['ALL','SUCCESS','FAILED','UNKNOWN'].includes(result??'')?result as AuditFilter['result']:'ALL',query:p.get('q')??'',page:Math.min(10000,Math.max(1,Math.floor(Number(p.get('page')))||1))};
}
export function auditQuery(filter:AuditFilter){return new URLSearchParams({start:filter.start,end:filter.end,source:filter.source,router_id:filter.router_id,actor_id:filter.actor_id,operation:filter.operation,result:filter.result,query:filter.query,page:String(filter.page),page_size:'25'}).toString();}
export function auditHash(filter:AuditFilter){return '#module=dashboard&view=AUDIT_CENTER&'+auditQuery(filter).replace('source=','audit_source=').replace('result=','audit_result=').replace('query=','q=');}

export function auditCsv(rows:{occurred_at:string;actor_id:string|null;target_id:string|null;router_id:string|null;operation:string;result:string;source:string;audit_id:string|null;id:string}[]):string{
 const fields=[['occurred_at','İşlem zamanı (Türkiye saati)'],['actor_id','Aktör kimliği'],['target_id','Hedef kimliği'],['router_id','Router kimliği'],['operation','İşlem'],['result','Sonuç'],['source','Kaynak'],['audit_id','Audit UUID'],['id','Kayıt kimliği']] as const;
 return excelCsv(fields.map(([,label])=>label),rows.map(row=>fields.map(([key])=>key==='occurred_at'?auditLocalTime(row.occurred_at):row[key])));
}

export function excelCsv(headers:string[],rows:(string|null|undefined)[][]):string{
 const safe=(value:string|null|undefined)=>{let text=value??'';if(/^(?:\s*[=+\-@＝＋－＠]|[\t\r\n])/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';};
 return '\uFEFF'+[headers,...rows].map(row=>row.map(safe).join(',')).join('\r\n');
}

const auditTime=new Intl.DateTimeFormat('tr-TR',{dateStyle:'medium',timeStyle:'medium',timeZone:'Europe/Istanbul'});
export function auditLocalTime(value:string){
 const date=new Date(value);
 return Number.isNaN(date.getTime())?value:`${auditTime.format(date)} (Europe/Istanbul)`;
}
