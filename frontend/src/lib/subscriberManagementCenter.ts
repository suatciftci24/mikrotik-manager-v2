import {expiryInfo} from './expiry.ts';
import type {CenterSubscriber} from './subscriberCenter';
import {extensionDate} from './quick.ts';
export type DailyAction='EDIT'|'PLAN'|'STATUS'|'EXPIRE'|'EXTEND'|'ROUTER';
export type DailyEntry={request_id:string;item_id:string;expected_revision:number;expected_router_id:string;expected_source:'LOCAL'|'RADIUS';operation:DailyAction;value:string|null;days:30|60|90|null;expected_expires_on:string|null;confirmed:true};
export type OperationReceipt={item_id:string;request_id:string;success:boolean;recorded:boolean;operation:string;actor_id:string;router_id:string|null;previous_router_id:string|null;previous:Record<string,string|null>;values:Record<string,string|null>;occurred_at:string;revision:number;error:string|null};
export const dailyLabels:Record<string,string>={EDIT:'Abone bilgisi',PLAN:'Paket / profil',STATUS:'Hesap durumu',EXPIRE:'Bitiş tarihi',EXTEND:'Abonelik uzatma',ROUTER:'Router değişikliği',CREATE:'Sentetik kayıt eklendi',UPDATE:'Sentetik kayıt düzenlendi',RENEWAL:'Abonelik uzatıldı'};
export function dailyEntries(rows:CenterSubscriber[],action:DailyAction,value:string,days:30|60|90,today:string,id:()=>string):DailyEntry[]{
 if(!rows.length||rows.length>100)throw new Error('1–100 sentetik abone seçin.');
 if(new Set(rows.map(row=>row.id)).size!==rows.length)throw new Error('Aynı abone iki kez seçilemez.');
 if(rows.length>1&&!['EXTEND','STATUS'].includes(action))throw new Error('Toplu işlem yalnız uzatma veya hesap durumu içindir.');
 return rows.map(row=>{
  if(!row.id.startsWith('demo-managed-sub-')||row.router_source!=='PERSISTENT_DEMO'||row.router_missing||!row.router_id||!row.source)throw new Error('Gerçek, salt-okunur veya router bağı eksik kayıt seçilemez.');
  const next=action==='EXTEND'?extensionDate(row.expires_on,today,days):value.trim()||null;
  if(action==='EXTEND'&&!next)throw new Error(`${row.username}: Bitiş tarihi bilinmiyor; önce özel tarih belirleyin.`);
  if((action==='EDIT'||action==='PLAN')&&next&&(next.length>(action==='PLAN'?120:160)||next.length<(action==='EDIT'?2:1)||/[\x00-\x1f]/.test(next)))throw new Error('Yeni ad veya paket/profil biçimi geçersiz.');
  if(action==='EXPIRE'&&next&&expiryInfo(next,today).status==='UNKNOWN')throw new Error('Geçerli YYYY-MM-DD tarihi seçin.');
  if((action==='EDIT'||action==='PLAN')&&!next)throw new Error('Yeni ad veya paket/profil gerekli.');
  if(action==='STATUS'&&!['ACTIVE','PAUSED'].includes(next??''))throw new Error('Aktif veya Pasif seçin.');
  if(action==='ROUTER'&&!next?.startsWith('demo-managed-router-'))throw new Error('Kalıcı sentetik router seçin.');
  return {request_id:id(),item_id:row.id,expected_revision:row.revision,expected_router_id:row.router_id,expected_source:row.source,operation:action,value:next,days:action==='EXTEND'?days:null,expected_expires_on:row.expires_on,confirmed:true};
 });
}
export function previousDailyValue(row:CenterSubscriber,action:DailyAction){return ({EDIT:row.customer_name,PLAN:row.plan,STATUS:row.status,EXPIRE:row.expires_on,EXTEND:row.expires_on,ROUTER:row.router_id})[action];}
export const managementDependencies=['/subscriber-workspace','/subscribers','/router-center','/router-workspace/routers'] as const;
