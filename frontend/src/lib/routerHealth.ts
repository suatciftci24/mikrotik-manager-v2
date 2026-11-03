import type {Inventory} from '../components/V1Inventory';
type Row=Inventory['items'][number];
export const HEALTH_LIMITS={cpuWarning:70,cpuCritical:90,ramWarning:80,ramCritical:95,staleMs:600_000} as const;
export const HEALTH_STATES=['Normal','Dikkat','Kritik','Eski veri','Veri yok'] as const;
export type HealthStatus=typeof HEALTH_STATES[number];
/** UI information only. Requires real health provenance; never uses API read time. */
export function routerHealth(row:Row,now:number):{status:HealthStatus;reason:string;age:string}{
 const time=row.sampled_at&&/(Z|[+-]\d{2}:\d{2})$/.test(row.sampled_at)?Date.parse(row.sampled_at):NaN;
 const missing=(reason:string)=>({status:'Veri yok' as const,reason,age:'Güncellik doğrulanamadı'});
 if(row.health_source!=='V1_ROUTER_HEALTH_SAMPLES'||!row.health_sample_id?.trim())return missing('Doğrulanmış gerçek sağlık ölçümü yok.');
 if(!Number.isFinite(now)||!Number.isFinite(time)||time>now)return missing('Ölçüm zamanı eksik, hatalı veya gelecekte.');
 const elapsed=now-time,age=`${Math.floor(elapsed/60_000)} dk önce`;
 if(elapsed>HEALTH_LIMITS.staleMs)return {status:'Eski veri',reason:'Son gerçek ölçüm 10 dakikadan eski; performans durumu değerlendirilmez.',age};
 const cpu=row.cpu_load_percent,ram=row.memory_used_percent;
 if([cpu,ram].some(n=>n===null||!Number.isFinite(n)||n<0||n>100))return {...missing('CPU veya RAM ölçümü eksik ya da geçersiz; performans durumu doğrulanamadı.'),age};
 const c=cpu!,r=ram!;
 const critical=c>=HEALTH_LIMITS.cpuCritical||r>=HEALTH_LIMITS.ramCritical,warning=c>=HEALTH_LIMITS.cpuWarning||r>=HEALTH_LIMITS.ramWarning;
 const reason=critical?[c>=90?'CPU ≥ %90':null,r>=95?'RAM ≥ %95':null]:warning?[c>=70?'CPU ≥ %70':null,r>=80?'RAM ≥ %80':null]:['CPU < %70 ve RAM < %80'];
 return {status:critical?'Kritik':warning?'Dikkat':'Normal',reason:reason.filter(Boolean).join(' · '),age};
}
export function healthPriority(status:HealthStatus){return ['Kritik','Dikkat','Eski veri','Veri yok','Normal'].indexOf(status);}
