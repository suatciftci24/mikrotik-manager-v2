import type {PilotReadSnapshot} from './cebeciPilot';
import {connectionError} from './routerRegistry.ts';
export const routerCenterTabs=[['overview','Genel Bakış'],['interfaces','Ağ Arayüzleri'],['wan','WAN ve İnternet'],['pppoe','PPPoE'],['hotspot','Hotspot'],['events','Olay Geçmişi'],['security','Güvenli Bağlantı']] as const;
export type RouterCenterTab=typeof routerCenterTabs[number][0];
export type RouterCenterData={source:'PERSISTENT_DEMO'|'STATIC_DEMO'|'REGISTERED';is_demo:boolean;device_connection_started:false;
 item:{id:string;name:string;identity:string|null;model:string|null;routeros_version:string|null;management_address:string;site:string|null;status:string;last_success_at:string|null;last_seen_at:string|null;cpu_percent:number|null;memory_percent:number|null;uptime:string|null};
 sections:Record<RouterCenterTab,'AVAILABLE'|'UNMEASURED'|'PREPARING'>;
 read_snapshot?:PilotReadSnapshot|null;
 events:{action:string;occurred_at:string;actor_id:string;revision:number|null}[]};
export const routerCenterPath=(id:string)=>'/router-center/'+encodeURIComponent(id);
export function validRouterCenter(data:RouterCenterData,id:string){return data.item?.id===id&&data.device_connection_started===false&&
 (data.source==='REGISTERED'?id.startsWith('registered-')&&data.is_demo===false:data.is_demo===true&&(data.source==='PERSISTENT_DEMO'?id.startsWith('demo-managed-router-'):data.source==='STATIC_DEMO'&&id.startsWith('demo-router-')));}
export function routerCenterStatus(data:RouterCenterData){
 if(data.is_demo)return data.source==='STATIC_DEMO'?'Sentetik geçmiş örnek · canlı durum ölçülmedi':'Ölçülmedi · sentetik kayıt';
 return ({VERIFIED:'Son kayıtlı kontrol başarılı',STALE:'Kayıtlı kontrol eskimiş',CHECK_FAILED:'Son kayıtlı kontrol başarısız'}[data.item.status]??'Bilinmiyor');
}
export const eventLabel=(action:string)=>({CREATED:'Sentetik kayıt eklendi',UPDATED:'Sentetik kayıt düzenlendi',DELETED:'Sentetik kayıt silindi',PROBE_REQUESTED:'Geçmiş bağlantı kontrolü istendi',PROBE_VERIFIED:'Geçmiş kontrol doğrulandı',PROBE_FAILED:'Geçmiş kontrol başarısız',ROUTER_REGISTERED:'Cihaz envantere kaydedildi',ROUTER_UPDATED:'Cihaz envanteri güncellendi',PROBE_CANCELLED:'Geçmiş kontrol iptal edildi',READ_ONLY_REQUESTED:'Salt okunur detay okuması istendi',READ_ONLY_SAVED:'Salt okunur detay kaydedildi',READ_ONLY_FAILED:'Salt okunur detay okuması başarısız'}[action]??'Kayıtlı işlem');

export function routerCenterError(message:string){
 if(message==='Not Found')return 'Router Detay Merkezi çalışan backend sürümünde bulunamadı. Yerel V2 servislerini güncelleyin; kayıtlar korunur.';
 if(/^[A-Z][A-Z0-9_:]+$/.test(message))return connectionError(message);
 if(message==='Failed to fetch'||message==='Load failed')return 'Yerel V2 API erişilemiyor. Bağlantıyı kontrol edip tekrar deneyin.';
 return message;
}
