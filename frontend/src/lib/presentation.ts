import {useSyncExternalStore} from 'react';
export type Presentation={app_name:string;timezone:'Europe/Istanbul';page_size:10|25|50;theme:'system'|'light'|'dark';notifications_enabled:boolean;notification_levels:string[]};
export const presentationDefaults:Presentation={app_name:'MikroTik Manager V2',timezone:'Europe/Istanbul',page_size:25,theme:'system',notifications_enabled:true,notification_levels:['P1','P2','P3','P4']};
let current=presentationDefaults;
const listeners=new Set<()=>void>();
export const presentationSnapshot=()=>current;
export function applyPresentation(value:Presentation){
 current={...value,notification_levels:[...value.notification_levels]};
 if(typeof document!=='undefined')document.title=value.app_name;
 if(typeof window!=='undefined')window.v2Theme?.setDefaultPreference?.(value.theme);
 listeners.forEach(listener=>listener());
}
export function usePresentation(){return useSyncExternalStore(listener=>{listeners.add(listener);return()=>{listeners.delete(listener);};},presentationSnapshot,()=>presentationDefaults);}
export function preferredPath(path:string){
 const [base,query='']=path.split('?');
 if(!['/users','/users/audit','/alarms','/reports/operations','/system/audit'].includes(base))return path;
 const params=new URLSearchParams(query);if(!params.has('page_size'))params.set('page_size',String(current.page_size));
 return base+'?'+params;
}
