import {api,type Router} from './api.ts';
import {buildDailySummary} from './dailySummary.ts';
import {expiryInfo} from './expiry.ts';
import type {DashboardSummary} from './dashboardOverview.ts';
import type {CenterSubscriber} from './subscriberCenter.ts';

type WorkspaceRouter={id:string;kind:'DEMO_ROUTER';is_demo:true;device_connected:false;fields:{name:string;management_address:string;site?:string;model:string}};
async function allPages<T>(path:string,init?:RequestInit):Promise<T[]>{
 const items:T[]=[];
 for(let page=1;;page++){
  const data=await api<{items:T[];total:number}>(`${path}?page=${page}&page_size=100`,init);
  if(!Array.isArray(data.items)||!Number.isInteger(data.total)||data.total<0||data.items.length>100)throw new Error('Çalışma alanı listesi doğrulanamadı.');
  items.push(...data.items);
  if(items.length>=data.total){if(items.length!==data.total||new Set(items.map(row=>(row as {id:string}).id)).size!==items.length)throw new Error('Çalışma alanı değişti; özeti yenileyin.');return items;}
  if(!data.items.length)throw new Error('Çalışma alanı sayfası eksik.');
 }
}
export async function loadWorkspaceDashboardSummary(_path:string,init?:RequestInit):Promise<DashboardSummary>{
 const [records,accounts]=await Promise.all([allPages<WorkspaceRouter>('/router-workspace/routers',init),allPages<CenterSubscriber>('/subscriber-workspace',init)]);
 if(records.some(row=>row.kind!=='DEMO_ROUTER'||row.is_demo!==true||row.device_connected!==false))throw new Error('Kalıcı router kaynağı doğrulanamadı.');
 const routers:Router[]=records.map(row=>({id:row.id,...row.fields,site:row.fields.site??'',is_demo:true,status:'UNKNOWN',cpu_percent:null,memory_percent:null,subscriber_count:accounts.filter(account=>account.router_id===row.id).length,routeros_version:'',uptime:'',last_seen:''}));
 const summary=buildDailySummary(routers,[]);
 const subscribers=summary.subscribers;
 let within_3=0,expiry_today=0;
 for(const item of accounts){
  subscribers.total++;
  if(item.status==='ACTIVE')subscribers.active++;else if(item.status==='PAUSED')subscribers.paused++;else if(item.status==='PENDING')subscribers.pending++;else subscribers.unknown_status++;
  if(item.source==='LOCAL')subscribers.local++;else if(item.source==='RADIUS')subscribers.radius++;else subscribers.unknown_source++;
  if(item.access_type==='PPPOE')summary.pppoe.confirmed++;else if(!item.access_type)summary.pppoe.untyped++;
  const info=expiryInfo(item.expires_on,summary.as_of_date);
  if(info.status==='UNKNOWN')summary.expiry.unknown++;else if(info.status==='EXPIRED')summary.expiry.expired++;else if(info.status==='ACTIVE')summary.expiry.active++;
  if(info.days!==null&&info.days>=0){if(info.days===0)expiry_today++;if(info.days<=3)within_3++;if(info.days<=7)summary.expiry.within_7++;if(info.days<=15)summary.expiry.within_15++;if(info.days<=30)summary.expiry.within_30++;}
 }
 // Inventory is not audit history or session evidence.
 return {...summary,within_3,expiry_today,history_available:false};
}

export async function loadWorkspaceRouterSummary(_path:string,init?:RequestInit):Promise<DashboardSummary>{
 const records=await allPages<WorkspaceRouter>('/router-workspace/routers',init);
 if(records.some(row=>row.kind!=='DEMO_ROUTER'||row.is_demo!==true||row.device_connected!==false))throw new Error('Kalıcı router kaynağı doğrulanamadı.');
 const routers:Router[]=records.map(row=>({id:row.id,...row.fields,site:row.fields.site??'',is_demo:true,status:'UNKNOWN',cpu_percent:null,memory_percent:null,subscriber_count:0,routeros_version:'',uptime:'',last_seen:''}));
 return {...buildDailySummary(routers,[]),history_available:false};
}
