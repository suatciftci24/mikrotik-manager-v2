import {matchesSource,type SourceFilter} from './source.ts';
import type { CenterSubscriber } from './subscriberCenter.ts';
import { dailyLabels, type OperationReceipt } from './subscriberManagementCenter.ts';
import { api, type Router, type SubscriberDetailData } from './api.ts';
import { buildDailySummary, loadDailyInventory, type DailyOperation } from './dailySummary.ts';
import { buildSubscriptionAlerts } from './subscriptionAlerts.ts';
import { matchesExpiry, type ExpiryFilter, turkeyToday } from './expiry.ts';
import { observationTime } from './subscriberObservation.ts';
import { loadRouterEvents } from './routerEvents.ts';
import type { AlarmEvent } from './routerEvents.ts';

export const reportPeriods={LAST_24:'Son 24 saat',TODAY:'Bugün',YESTERDAY:'Dün',LAST_7:'Son 7 Gün',LAST_30:'Son 30 Gün'} as const;
export type ManagementPeriod=keyof typeof reportPeriods;
export const reportKinds={ALL:'Tüm işlem ve olaylar',OPERATIONS:'Tüm yönetim işlemleri',PPPOE:'PPPoE işlemleri',CREATE:'Abone oluşturma',PLAN_CHANGE:'Paket/profil değiştirme',STATUS_CHANGE:'Hesap durumu değiştirme',RENEWAL:'Abonelik yenileme',DATE_EDIT:'Bitiş tarihi düzenleme',INTERNET_DOWN:'İnternet kesintisi',INTERNET_UP:'Bağlantı geri gelmesi',WAN_CHANGE:'WAN değişikliği'} as const;
export type ReportOperation=DailyOperation & {router_id:string|null;workspace?:boolean;label?:string};
export type WorkspaceHistory={accounts:CenterSubscriber[];receipts:OperationReceipt[];routers:{id:string;fields:{name:string}}[]};
export type ManagementSource={workspace?:WorkspaceHistory|null;workspaceError?:string;read_at?:string;routers:Router[];details:SubscriberDetailData[];events:AlarmEvent[]|null};
export type ManagementFilter={query?:string;period:ManagementPeriod;router:string;kind:keyof typeof reportKinds;expiry?:ExpiryFilter;source?:SourceFilter;plan?:string;account_status?:'ALL'|'ACTIVE'|'PAUSED'|'PENDING'};
export const managementExpiryFilters=['ALL','EXPIRED','TODAY','WITHIN_3','WITHIN_7','WITHIN_30','VALID','UNKNOWN'] as const;
export function managementSourceFromHash(hash:string){return new URLSearchParams(hash.replace(/^#/, '')).get('report_source')==='V1_INVENTORY'?'V1_INVENTORY':'DEMO';}
export function managementRange(period:ManagementPeriod|'LAST_30',now=new Date()){
  if((!Object.hasOwn(reportPeriods,period)&&period!=='LAST_30')||!Number.isFinite(now.getTime()))throw new Error('Geçerli rapor dönemi ve zamanı gerekli.');
  if(period==='LAST_24')return {start:turkeyToday(new Date(now.getTime()-86400000)),end:turkeyToday(now),from:now.getTime()-86400000,until:now.getTime()+1,cutoff:now.getTime()};
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
export function buildManagementReport(source:ManagementSource,filter:ManagementFilter,now=new Date(),includeHotspot=false){
  const range=managementRange(filter.period,now);
  if(!Object.hasOwn(reportKinds,filter.kind))throw new Error('Rapor olay filtresi geçersiz.');
  if(!['ALL','LOCAL','RADIUS','UNKNOWN'].includes(filter.source??'ALL'))throw new Error('Yetkili kaynak filtresi geçersiz.');
  const routers=uniqueReportRecords(source.routers,row=>row.id);
  const details=uniqueReportRecords(source.details.map(detail=>({...detail,history:uniqueReportRecords(detail.history,event=>event.id)})),detail=>detail.item.id);
  // Validate all source records before scoping, including hidden conflicting audit IDs.
  const allInventory=buildDailySummary(routers,details,now);
  const scopedRouters=filter.router?routers.filter(router=>router.id===filter.router):routers;
  const currentMatches=(item:{plan:string;status:string})=>(!filter.plan||item.plan===filter.plan)&&(!filter.account_status||filter.account_status==='ALL'||item.status===filter.account_status);
  const scopedDetails=details.filter(detail=>(!filter.router||reportRouterId(detail.item,routers)===filter.router)&&matchesSource(detail.item.source,filter.source??'ALL')&&currentMatches(detail.item));
  const inventory=buildDailySummary(scopedRouters,scopedDetails,now);
  const inRange=(value:string|null)=>{
    const time=observationTime(value);if(!time)return false;
    const milliseconds=Date.parse(time);return milliseconds>=range.from&&milliseconds<range.until&&milliseconds<=range.cutoff;
  };
  const detailById=new Map(details.map(detail=>[detail.item.id,detail]));
  const legacyOperations=allInventory.operation_history.filter(event=>matchesSource(event.source,filter.source??'ALL')&&currentMatches(detailById.get(event.subscriber_id)!.item)&&(!filter.router||(event.router_id??reportRouterId(detailById.get(event.subscriber_id)!.item,routers))===filter.router)&&inRange(event.occurred_at)&&(filter.kind==='ALL'||filter.kind==='OPERATIONS'||filter.kind==='PPPOE'&&event.access_type==='PPPOE'||event.operation===filter.kind)).map(event=>({...event,router_id:event.router_id??reportRouterId(detailById.get(event.subscriber_id)!.item,routers)}));
  const workspaceOperations:ReportOperation[]=[];
  if(source.workspace){
    const accounts=uniqueReportRecords(source.workspace.accounts,row=>row.id);
    const accountById=new Map(accounts.map(account=>[account.id,account]));
    const workspaceRouterById=new Map(uniqueReportRecords(source.workspace.routers,row=>row.id).map(router=>[router.id,router]));
    for(const receipt of uniqueReportRecords(source.workspace.receipts,row=>row.request_id)){
      if(receipt.recorded!==true)continue;
      if(typeof receipt.success!=='boolean')throw new Error('İşlem audit sonucu doğrulanamadı.');
      const account=accountById.get(receipt.item_id);
      if(!account||!account.id.startsWith('demo-managed-sub-')||!['PPPOE','HOTSPOT'].includes(account.access_type??'')||!account.source)throw new Error('Kalıcı işlem abonesi doğrulanamadı.');
      if(!['LOCAL','RADIUS'].includes(account.source)||!Number.isInteger(account.revision)||account.revision<1||!Number.isInteger(receipt.revision)||receipt.revision<(receipt.success?1:0)||receipt.revision>account.revision)throw new Error('Kalıcı işlem ve güncel abone revizyonu doğrulanamadı.');
      if(receipt.success&&receipt.revision===account.revision&&Object.entries(receipt.values).some(([key,value])=>['source','router_id','username','plan','status','expires_on','customer_name','access_type'].includes(key)&&account[key as keyof CenterSubscriber]!==value))throw new Error('İşlem sonucu güncel revizyonla eşleşmedi.');
      if(!includeHotspot&&account.access_type!=='PPPOE')continue;
      if(!matchesSource(receipt.source,filter.source??'ALL')||!currentMatches(account))continue;
      const mapping:Record<string,DailyOperation['operation']>={EDIT:'EDIT',UPDATE:'UPDATE',ROUTER:'ROUTER',CREATE:'CREATE',PLAN:'PLAN_CHANGE',STATUS:'STATUS_CHANGE',EXTEND:'RENEWAL',RENEWAL:'RENEWAL',EXPIRE:'DATE_EDIT'};
      const operation=mapping[receipt.operation];
      if(!operation)throw new Error('Kalıcı işlem türü doğrulanamadı.');
      if(!inRange(receipt.occurred_at)||filter.router&&receipt.router_id!==filter.router)continue;
      if(!['ALL','OPERATIONS',operation].includes(filter.kind)&&!(filter.kind==='PPPOE'&&account.access_type==='PPPOE'))continue;
      workspaceOperations.push({id:'workspace:'+receipt.request_id,request_id:receipt.request_id,revision:receipt.revision,audit_result:receipt.success?'APPLIED':'FAILED',subscriber_id:account.id,customer_name:account.customer_name,username:account.username,router_id:receipt.router_id,router_name:workspaceRouterById.get(receipt.router_id??'')?.fields.name??receipt.router_id??'Veri yok',access_type:account.access_type,source:receipt.source??null,is_demo:true,operation,label:dailyLabels[receipt.operation]??receipt.operation,workspace:true,occurred_at:receipt.occurred_at,actor_id:receipt.actor_id,previous_values:receipt.previous,new_values:receipt.values,...(operation==='RENEWAL'||operation==='DATE_EDIT'?{previous_expires_on:receipt.previous.expires_on,expires_on:receipt.values.expires_on}:{})});
    }
  }
  const operations:ReportOperation[]=[...legacyOperations,...workspaceOperations].sort((a,b)=>Date.parse(b.occurred_at)-Date.parse(a.occurred_at)||a.id.localeCompare(b.id));
  const sourceEvents=source.events===null?null:uniqueReportRecords(source.events,event=>event.id);
  const expanded=sourceEvents?.flatMap(event=>{
    if(event.is_demo!==true)throw new Error('Rapor yalnız sentetik olayları destekler.');
    const end=observationTime(event.ended_at),start=observationTime(event.started_at);
    const verifiedEnd=event.kind==='INTERNET_DOWN'&&event.status==='RESOLVED'&&event.recovery_id&&end&&start&&Date.parse(end)>=Date.parse(start)&&Date.parse(end)<=range.cutoff;
    const lifecycle:AlarmEvent={...event,status:event.kind==='INTERNET_DOWN'&&event.status==='RESOLVED'&&!verifiedEnd?'UNKNOWN':event.status,ended_at:verifiedEnd?end:null,recovery_id:verifiedEnd?event.recovery_id:null,duration_seconds:verifiedEnd&&event.duration_verified!==false?event.duration_seconds:null};
    const records=[{id:event.id,kind:event.kind,occurred_at:event.started_at,router_id:event.router_id,lifecycle}];
    if(lifecycle.recovery_id&&lifecycle.ended_at)records.push({id:lifecycle.recovery_id,kind:'INTERNET_UP',occurred_at:lifecycle.ended_at,router_id:event.router_id,lifecycle});
    return records;
  })??null;
  const events=expanded===null?null:uniqueReportRecords(expanded,event=>event.id).filter(event=>(!filter.router||event.router_id===filter.router)&&inRange(event.occurred_at)&&(filter.kind==='ALL'||filter.kind===event.kind)).sort((a,b)=>Date.parse(b.occurred_at!)-Date.parse(a.occurred_at!)||a.id.localeCompare(b.id));
  const historyAvailable=source.workspace!==null&&scopedDetails.every(detail=>detail.history_available!==false);
  const expiry=filter.expiry??'TODAY';
  if(!managementExpiryFilters.includes(expiry as typeof managementExpiryFilters[number]))throw new Error('Bitiş filtresi geçersiz.');
  const subscribers=[...scopedDetails.map(detail=>detail.item),...uniqueReportRecords(source.workspace?.accounts??[],row=>row.id).filter(row=>(!filter.router||row.router_id===filter.router)&&matchesSource(row.source,filter.source??'ALL')&&currentMatches(row)).map(row=>({...row,is_demo:true as const,router_name:row.router_name??'Veri yok'}))];
  return {range,inventory,operations,events,historyAvailable,workspaceError:source.workspaceError,
    pppoeOperations:historyAvailable?operations.filter(event=>event.access_type==='PPPOE'&&event.audit_result==='APPLIED').length:null,
    untypedOperations:historyAvailable?operations.filter(event=>event.access_type===null).length:null,
    outcomes:{applied:historyAvailable?operations.filter(event=>event.audit_result==='APPLIED').length:null,failed:historyAvailable&&source.workspace?operations.filter(event=>event.audit_result==='FAILED').length:null,unknown:null},
    expirySummary:buildSubscriptionAlerts(subscribers,turkeyToday(now)),
    expiryRows:subscribers.filter(row=>matchesExpiry(row.expires_on,expiry,turkeyToday(now))),
    generated_at:now.toISOString(),
    counts:{operations:historyAvailable?operations.length:null,events:events?.length??null,outages:events?.filter(event=>event.kind==='INTERNET_DOWN').length??null,recoveries:events?.filter(event=>event.kind==='INTERNET_UP').length??null,wan:events?.filter(event=>event.kind==='WAN_CHANGE').length??null},
    undated:{operations:inventory.operation_history.filter(event=>!observationTime(event.occurred_at)).length,events:sourceEvents?.filter(event=>(!filter.router||event.router_id===filter.router)&&!event.started_at).length??null},
  };
}
export async function loadManagementReport(_path:string,init?:RequestInit):Promise<ManagementSource>{
  const [inventory,events]=await Promise.all([loadDailyInventory(init,true),loadRouterEvents('/router-events',init)]);
  let workspace:WorkspaceHistory|null|undefined,workspaceError:string|undefined;
  if(_path.includes('workspace=1')){
    try{
      const [accounts,receipts,routers]=await Promise.all([
        reportPages<CenterSubscriber>('/subscriber-workspace',init),
        reportPages<OperationReceipt>('/subscriber-workspace/management/history',init),
        reportPages<{id:string;fields:{name:string}}>('/router-workspace/routers',init,true),
      ]);
      workspace={accounts,receipts,routers};
    }catch(error){if(init?.signal?.aborted)throw error;workspace=null;workspaceError=error instanceof Error?error.message:'Kalıcı geçmiş okunamadı.';}
  }
  return {...inventory,events,workspace,workspaceError,read_at:new Date().toISOString()};
}

export function managementFilterFromHash(hash:string):ManagementFilter{
  const params=new URLSearchParams(hash.replace(/^#/,''));
  const period=params.get('period')??(params.get('module')==='operations'?'LAST_24':'TODAY'),kind=params.get('kind')??'ALL';
  return {...(params.has('query')?{query:(params.get('query')??'').slice(0,120)}:{}),...(params.has('plan')?{plan:(params.get('plan')??'').slice(0,200)}:{}),...(params.has('account_status')?{account_status:(['ALL','ACTIVE','PAUSED','PENDING'].includes(params.get('account_status')??'')?params.get('account_status'):'ALL') as ManagementFilter['account_status']}:{}),...(params.has('source')?{source:(['ALL','LOCAL','RADIUS','UNKNOWN'].includes(params.get('source')??'')?params.get('source'):'ALL') as SourceFilter}:{}),period:Object.hasOwn(reportPeriods,period)?period as ManagementPeriod:'TODAY',router:params.get('router')??'',kind:Object.hasOwn(reportKinds,kind)?kind as keyof typeof reportKinds:'ALL',...(params.has('expiry')?{expiry:managementExpiryFilters.includes(params.get('expiry') as typeof managementExpiryFilters[number])?params.get('expiry') as ExpiryFilter:'TODAY' as const}:{})};
}
export function managementReportHash(filter:ManagementFilter,center:'dashboard'|'operations'='dashboard'){return '#'+new URLSearchParams({module:center,view:'DAILY_REPORT',...filter}).toString();}

/** Read every page; partial or changing totals must never become a complete counter. */
async function reportPages<T extends {id?:string;request_id?:string}>(path:string,init?:RequestInit,routerWorkspace=false):Promise<T[]>{
  const rows:T[]=[];const ids=new Set<string>();let expected:number|undefined;
  for(let page=1;page<=1000;page++){
    const data=await api<{items:T[];total:number;is_demo?:boolean}>(path+'?page_size=100&page='+page,init);
    // WorkspaceList has no envelope is_demo field; synthetic identity is per record.
    // SubscriberWorkspaceList and OperationHistory require the envelope marker.
    if(!Array.isArray(data.items)||!Number.isInteger(data.total)||data.total<0||(!routerWorkspace&&data.is_demo!==true))throw new Error(`Kalıcı kaynak yanıtı doğrulanamadı (${path}).`);
    if(routerWorkspace&&data.items.some(row=>{
      const record=row as T & {kind?:string;is_demo?:boolean;persistence?:string;device_connected?:boolean};
      return record.kind!=='DEMO_ROUTER'||record.is_demo!==true||record.persistence!=='local-postgresql-workspace'||record.device_connected!==false;
    }))throw new Error('Kalıcı router kaynağının sentetik kimliği doğrulanamadı.');
    if(expected!==undefined&&expected!==data.total)throw new Error('Kalıcı geçmiş kapsamı değişti; raporu yenileyin.');
    expected=data.total;
    for(const row of data.items){const id=row.request_id??row.id;if(!id||ids.has(id))throw new Error('Kalıcı geçmiş sayfaları tekil değil; raporu yenileyin.');ids.add(id);rows.push(row);}
    if(rows.length===expected)return rows;
    if(!data.items.length||rows.length>expected)break;
  }
  throw new Error('Kalıcı geçmişin tamamı doğrulanamadı.');
}

export function managementSubscribersHash(filter:ManagementFilter,target?:'LEGACY'|'PERSISTENT'){
 const persistent=target?target==='PERSISTENT':filter.router.startsWith('demo-managed-router-');
 if(persistent)return '#'+new URLSearchParams({module:'subscribers',workspace:'PERSISTENT',...(filter.router?{workspace_router:filter.router}:{}),...(filter.account_status&&filter.account_status!=='PENDING'?{workspace_status:filter.account_status}:{})});
 return '#'+new URLSearchParams({module:'subscribers',workspace:'LEGACY',expiry:filter.expiry??'TODAY',...(filter.router?{router_id:filter.router}:{}),...(filter.source?{source:filter.source}:{}),...(filter.plan?{plan:filter.plan}:{}),...(filter.account_status?{status:filter.account_status}:{})});
}
