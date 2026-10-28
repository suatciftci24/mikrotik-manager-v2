import {api} from './api';
export type Check={status:'UP'|'ERROR'|'UNKNOWN'|'DEGRADED'|'STALE';checked_at:string|null;last_success:string|null;error:string|null};
export type Health={checks:Record<string,Check>;sources:{mode:string;router:string;radius:string;v1:string;evidence:string};is_demo:true;scope:string};
let previous:Record<string,Check>={};
export async function probeClient(fetcher:typeof fetch=fetch,now=new Date(),old:Record<string,Check>=previous){
 const checks:Record<string,Check>={},at=now.toISOString();
 for(const key of ['ui','proxy']){
  try{
   if(key==='ui'){
    const root=await fetcher('/',{credentials:'include',redirect:'error',signal:AbortSignal.timeout(5000)}),client=await fetcher('/@vite/client',{credentials:'include',redirect:'error',signal:AbortSignal.timeout(5000)});
    if(!root.ok||!client.ok||!(await root.text()).includes('/src/main.tsx')||!(await client.text()).toLowerCase().includes('vite'))throw new Error('UI identity');
   }else{
    const response=await fetcher('/api/ready',{credentials:'include',redirect:'error',signal:AbortSignal.timeout(5000)}),value=await response.json();
    if(!response.ok||value.service!=='mikrotik-manager-v2'||value.api_version!=='v1')throw new Error('Proxy identity');
   }
   checks[key]={status:'UP',checked_at:at,last_success:at,error:null};
  }catch{checks[key]={status:'UNKNOWN',checked_at:at,last_success:old[key]?.last_success??null,error:'İstemci kontrolü tamamlanamadı veya V2 kimliği doğrulanamadı.'};}
 }
 return checks;
}
export async function loadSystemHealth(_path:string,init?:RequestInit):Promise<Health>{
 const [health,client]=await Promise.all([api<Health>('/system/health',init),probeClient()]);previous=client;
 return {...health,checks:{...health.checks,...client}};
}
