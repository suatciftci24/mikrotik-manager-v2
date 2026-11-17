export type RouterReadSnapshot={identity:string;model:string;routeros_version:string;cpu_percent:number;memory_percent:number;uptime:string;captured_at:string;interfaces:{'.id':string;name:string;type:string;disabled:boolean;running:boolean}[];default_routes:{'dst-address':string;gateway:string;active:boolean;disabled:boolean}[];wan_ip:string|null;wan_interface?:string|null;pppoe_active_count?:number|null;hotspot_active_count?:number|null;pppoe_count:number|null;pppoe_explicit_count:number;ppp_any_count:number;hotspot_count:number;is_demo:false;read_only:true};
import {linkedCenterHash,centerReturnHash} from './detailLinks.ts';
import {connectionError} from './routerRegistry.ts';
export const routerSectionTabs=[['overview','Genel Bakış'],['interfaces','Ağ Arayüzleri'],['wan','WAN ve İnternet'],['pppoe','PPPoE'],['hotspot','Hotspot'],['events','Olay Geçmişi'],['security','Güvenli Bağlantı']] as const;
export const routerCenterTabs=[['overview','Genel Durum'],['wan','WAN/Bağlantı'],['subscribers','Aboneler'],['events','Geçmiş']] as const;
export type RouterCenterTab=typeof routerSectionTabs[number][0]|'subscribers';
export const routerCenterTabKeys=[...routerCenterTabs.map(([key])=>key),'interfaces','pppoe','hotspot','security'] as const;
export function primaryRouterTab(tab:RouterCenterTab){return tab==='pppoe'||tab==='hotspot'?'subscribers':tab==='interfaces'?'wan':tab==='security'?'overview':tab;}
export function routerSubscriberListHash(id:string,access:'PPPOE'|'HOTSPOT'|'ALL'='PPPOE',fromHash=''){
 const persistent=id.startsWith('demo-managed-router-');
 const params=new URLSearchParams({module:'subscribers',workspace:persistent?'PERSISTENT':'LEGACY',[persistent?'workspace_router':'router_id']:id,...(persistent?{workspace_access:access}:{})});
 if(persistent&&fromHash){
  const current=new URLSearchParams(fromHash.replace(/^#/,''));
  const back=new URLSearchParams((centerReturnHash(fromHash)??'').replace(/^#/,''));
  if(back.get('module')==='subscribers'&&back.get('workspace')==='PERSISTENT')for(const key of ['workspace_query','workspace_status'])if(back.has(key))params.set(key,back.get(key)!);
  if(current.has('router_sub_query'))params.set('workspace_query',current.get('router_sub_query')!);
  if(['ALL','ACTIVE','PAUSED'].includes(current.get('router_sub_status')??''))params.set('workspace_status',current.get('router_sub_status')!);
 }
 return fromHash?linkedCenterHash('#'+params,fromHash):'#'+params;
}
export type RouterCenterData={source:'PERSISTENT_DEMO'|'STATIC_DEMO'|'REGISTERED';is_demo:boolean;device_connection_started:false;
 item:{id:string;name:string;identity:string|null;model:string|null;routeros_version:string|null;management_address:string;site:string|null;inventory_description?:string|null;status:string;last_success_at:string|null;last_seen_at:string|null;cpu_percent:number|null;memory_percent:number|null;uptime:string|null};
 read_snapshot?:RouterReadSnapshot|null;
 sections:Record<typeof routerSectionTabs[number][0],'AVAILABLE'|'UNMEASURED'|'PREPARING'>;
 events:{action:string;occurred_at:string;actor_id:string;revision:number|null}[]};
export const routerCenterPath=(id:string)=>'/router-center/'+encodeURIComponent(id);
export function validRouterCenter(data:RouterCenterData,id:string){return data.item?.id===id&&data.device_connection_started===false&&
 (data.source==='REGISTERED'?id.startsWith('registered-')&&data.is_demo===false:data.is_demo===true&&(data.source==='PERSISTENT_DEMO'?id.startsWith('demo-managed-router-'):data.source==='STATIC_DEMO'&&id.startsWith('demo-router-')));}
export function routerCenterStatus(data:RouterCenterData){
 if(data.is_demo)return data.source==='STATIC_DEMO'?'Sentetik geçmiş örnek · canlı durum ölçülmedi':'Ölçülmedi · sentetik kayıt';
 return ({PENDING_VERIFICATION:'Doğrulama bekliyor · bağlantı izni yok',VERIFIED:'Son kayıtlı kontrol başarılı',STALE:'Kayıtlı kontrol eskimiş',CHECK_FAILED:'Son kayıtlı kontrol başarısız'}[data.item.status]??'Bilinmiyor');
}
export const eventLabel=(action:string)=>({INVENTORY_REGISTERED:'Bağlantısız envanter kaydı oluşturuldu',CREATED:'Sentetik kayıt eklendi',UPDATED:'Sentetik kayıt düzenlendi',DELETED:'Sentetik kayıt silindi',PROBE_REQUESTED:'Geçmiş bağlantı kontrolü istendi',PROBE_VERIFIED:'Geçmiş kontrol doğrulandı',PROBE_FAILED:'Geçmiş kontrol başarısız',ROUTER_REGISTERED:'Cihaz envantere kaydedildi',ROUTER_UPDATED:'Cihaz envanteri güncellendi',PROBE_CANCELLED:'Geçmiş kontrol iptal edildi',READ_ONLY_REQUESTED:'Salt okunur detay okuması istendi',READ_ONLY_SAVED:'Salt okunur detay kaydedildi',READ_ONLY_FAILED:'Salt okunur detay okuması başarısız'}[action]??'Kayıtlı işlem');

export function routerCenterError(message:string){
 if(message==='Not Found')return 'Router Detay Merkezi çalışan backend sürümünde bulunamadı. Yerel V2 servislerini güncelleyin; kayıtlar korunur.';
 if(/^[A-Z][A-Z0-9_:]+$/.test(message))return connectionError(message);
 if(message==='Failed to fetch'||message==='Load failed')return 'Yerel V2 API erişilemiyor. Bağlantıyı kontrol edip tekrar deneyin.';
 return message;
}
