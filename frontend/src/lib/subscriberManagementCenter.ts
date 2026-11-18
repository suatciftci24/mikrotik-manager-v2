import {expiryInfo} from './expiry.ts';
import type {CenterSubscriber} from './subscriberCenter';
import {extensionDate} from './quick.ts';
import {canChangeWorkspaceItem} from './subscriberActions.ts';
export type DailyAction='EDIT'|'PLAN'|'STATUS'|'EXPIRE'|'EXTEND'|'ROUTER';
export const maxDailyExtensionDays=365;
export type DailyEntry={request_id:string;item_id:string;expected_revision:number;expected_router_id:string;expected_source:'LOCAL'|'RADIUS';operation:DailyAction;value:string|null;days:number|null;expected_expires_on:string|null;confirmed:true;package_id?:string;package_revision?:number};
export type OperationReceipt={source?:'LOCAL'|'RADIUS'|null;item_id:string;request_id:string;success:boolean;recorded:boolean;operation:string;actor_id:string;router_id:string|null;previous_router_id:string|null;previous:Record<string,string|null>;values:Record<string,string|null>;occurred_at:string;revision:number;error:string|null};
export const dailyLabels:Record<string,string>={EDIT:'Abone bilgisi',PLAN:'Paket / profil',STATUS:'Hesap durumu',EXPIRE:'Bitiş tarihi',EXTEND:'Abonelik uzatma',ROUTER:'Router değişikliği',CREATE:'Sentetik kayıt eklendi',UPDATE:'Sentetik kayıt düzenlendi',RENEWAL:'Abonelik uzatıldı'};
export function dailyEntries(rows:CenterSubscriber[],action:DailyAction,value:string,days:number,today:string,id:()=>string,selection?:{package_id:string;package_revision:number}):DailyEntry[]{
 if(!rows.length||rows.length>100)throw new Error('1–100 sentetik abone seçin.');
 if(new Set(rows.map(row=>row.id)).size!==rows.length)throw new Error('Aynı abone iki kez seçilemez.');
 if(rows.length>1&&!['EXTEND','STATUS'].includes(action))throw new Error('Toplu işlem yalnız uzatma veya hesap durumu içindir.');
 if(!Object.hasOwn(dailyLabels,action)||!['EDIT','PLAN','STATUS','EXPIRE','EXTEND','ROUTER'].includes(action))throw new Error('Desteklenen günlük işlem seçin.');
 if(action==='EXTEND'&&(!Number.isInteger(days)||days<1||days>maxDailyExtensionDays))throw new Error(`Uzatma süresi 1–${maxDailyExtensionDays} arasında tam gün olmalı.`);
 return rows.map(row=>{
  if(!canChangeWorkspaceItem(row,true)||!row.router_id||(row.source!=='LOCAL'&&row.source!=='RADIUS'))throw new Error('Gerçek, kaynağı bilinmeyen, salt-okunur veya router bağı eksik kayıt seçilemez.');
  if(!Number.isInteger(row.revision)||row.revision<1)throw new Error('Abone revizyonu doğrulanamadı; güncel kaydı yeniden açın.');
  const next=action==='EXTEND'?extensionDate(row.expires_on,today,days):value.trim()||null;
  if(action==='EXTEND'){
   if(!row.expires_on||expiryInfo(row.expires_on,today).days===null)throw new Error(`${row.username}: Bitiş tarihi geçersiz veya bilinmiyor. Önce abonenin bitiş tarihini düzeltin.`);
   if(!next||row.started_on&&next<row.started_on)throw new Error(`${row.username}: Seçilen süre geçerli bir yeni bitiş tarihi oluşturmuyor.`);
  }
  if((action==='EDIT'||action==='PLAN')&&next&&(next.length>(action==='PLAN'?120:160)||next.length<(action==='EDIT'?2:1)||/[\x00-\x1f]/.test(next)))throw new Error('Yeni ad veya paket/profil biçimi geçersiz.');
  if(action==='EXPIRE'&&next&&expiryInfo(next,today).status==='UNKNOWN')throw new Error('Geçerli YYYY-MM-DD tarihi seçin.');
  if((action==='EDIT'||action==='PLAN')&&!next)throw new Error('Yeni ad veya paket/profil gerekli.');
  if(action==='STATUS'&&!['ACTIVE','PAUSED'].includes(next??''))throw new Error('Aktif veya Pasif seçin.');
  if(action==='ROUTER'&&!next?.startsWith('demo-managed-router-'))throw new Error('Kalıcı sentetik router seçin.');
  if(rows.length===1&&next===previousDailyValue(row,action)&&!(action==='PLAN'&&selection&&(selection.package_id!==row.package_id||selection.package_revision!==row.package_revision)))throw new Error('Yeni değer mevcut değerden farklı olmalı.');
  return {request_id:id(),item_id:row.id,expected_revision:row.revision,expected_router_id:row.router_id,expected_source:row.source,operation:action,value:next,days:action==='EXTEND'?days:null,expected_expires_on:row.expires_on,confirmed:true,...(action==='PLAN'?selection:{})};
 });
}
export function previousDailyValue(row:CenterSubscriber,action:DailyAction){return ({EDIT:row.customer_name,PLAN:row.plan,STATUS:row.status,EXPIRE:row.expires_on,EXTEND:row.expires_on,ROUTER:row.router_id})[action];}
export const managementDependencies=['/subscriber-workspace','/subscribers','/router-center','/router-workspace/routers'] as const;
