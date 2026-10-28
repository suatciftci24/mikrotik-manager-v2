export type MikaEvent = {
  id:string;domain:string;priority:'P1'|'P2'|'P3'|'P4';state:'OPEN'|'UPDATED'|'RECOVERING'|'RESOLVED';
  title:string;reason:string;evidence:string;affected_router_ids:string[];recommendation:string;
  confidence:'HIGH'|'MEDIUM'|'LOW';opened_at:string;updated_at:string;resolved_at:string|null;
  history:{state:string;occurred_at:string;evidence:string;observation_ids:string[]}[];is_demo:true;
};
export type MikaAnalysis = {
  source:string;generated_at:string;evaluated_at:string;read_only:true;is_demo:true;
  health:{router_id:string;name:string;health:string;signals:Record<string,string>;latest_observed_at:string|null;reliability:string}[];
  events:MikaEvent[];summary:Record<string,number>;operational_summary:string;limitations:string[];
};
export type MikaFilters={query:string;priority:string;state:string;router:string;domain:string};
export function filterMikaEvents(events:MikaEvent[],filters:MikaFilters) {
  return events.filter(e=>(filters.priority==='ALL'||e.priority===filters.priority)
    &&(filters.state==='ALL'||filters.state==='ACTIVE'&&e.state!=='RESOLVED'||filters.state===e.state)
    &&(!filters.router||e.affected_router_ids.includes(filters.router))&&(filters.domain==='ALL'||e.domain===filters.domain)
    &&`${e.title} ${e.reason} ${e.evidence}`.toLocaleLowerCase('tr-TR').includes(filters.query.toLocaleLowerCase('tr-TR')))
    .sort((a,b)=>a.priority.localeCompare(b.priority)||b.updated_at.localeCompare(a.updated_at)||a.id.localeCompare(b.id));
}
export function assertMikaAnalysis(data:MikaAnalysis) {
  if(data.is_demo!==true||data.read_only!==true||data.events.some(e=>e.is_demo!==true)) throw new Error('Salt okunur sentetik kaynak doğrulanamadı.');
  return data;
}
export const mikaStatus:Record<string,string>={GOOD:'İyi gözlem',BAD:'Sorun gözlemi',UNKNOWN:'Bilinmiyor',CURRENT:'Güncel',STALE:'Eski veri',MISSING:'Veri yok',ATTENTION:'İnceleme gerekli',HEALTHY:'İyi gözlemler',HIGH:'Yüksek',MEDIUM:'Orta',LOW:'Düşük',OPEN:'Açık',UPDATED:'Güncellendi',RECOVERING:'İyileşiyor',RESOLVED:'Çözüldü'};
