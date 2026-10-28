import type { DailyOperation } from './dailySummary';
import type { Router } from './api';
import type { AlarmEvent, RouterEvent } from './routerEvents';
import type { MikaEvent } from './mikajani';
import { turkeyToday } from './expiry.ts';
export type ReportFilter={start:string;end:string;category:'AUDIT'|'CONNECTION'|'MIKA';router_id:string;subscriber_id:string;operation:string;priority:string;state:string;page:number};
export function operationFilter(hash:string,now=new Date()):ReportFilter{
 const p=new URLSearchParams(hash.replace(/^#/,''));
 return {start:p.get('start')??turkeyToday(now),end:p.get('end')??turkeyToday(now),category:['AUDIT','CONNECTION','MIKA'].includes(p.get('category')??'')?p.get('category') as ReportFilter['category']:'AUDIT',router_id:p.get('router_id')??'',subscriber_id:p.get('subscriber_id')??'',operation:p.get('operation')??'',priority:p.get('priority')??'ALL',state:p.get('state')??'ALL',page:Math.min(1000000,Math.max(1,Math.floor(Number(p.get('page')))||1))};
}
export function operationQuery(filter:ReportFilter){return new URLSearchParams({...filter,page:String(filter.page)}).toString();}
export function operationHash(filter:ReportFilter){return '#module=dashboard&view=OPERATIONS_REPORT&'+operationQuery(filter);}
export type ConnectionRecord=RouterEvent&{lifecycle:AlarmEvent};
export type OperationReportData={items:(DailyOperation|ConnectionRecord|MikaEvent)[];routers:Router[];total:number;page:number;page_size:number;read_at:string;from_at:string;until_at:string;connections_available:boolean;is_demo:true;read_only:true;summary:{subscribers:number;active:number;paused:number;activated:number;deactivated:number;operations:number;failures:null;open_events:number;connections:number|null;router_status:Record<string,number>}};
export function operationDetailHash(module:'routers'|'subscribers',id:string,filter:ReportFilter){return '#'+new URLSearchParams({module,id,report_start:filter.start,report_end:filter.end,report_router:filter.router_id});}
export function detailOperationHash(kind:'routers'|'subscribers',id:string,hash:string){
 const p=new URLSearchParams(hash.replace(/^#/,'')),base=operationFilter('');
 return operationHash({...base,start:p.get('report_start')??base.start,end:p.get('report_end')??base.end,router_id:kind==='routers'?id:p.get('report_router')??'',subscriber_id:kind==='subscribers'?id:''});
}
