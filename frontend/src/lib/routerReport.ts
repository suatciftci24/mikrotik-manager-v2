import type { Router } from './api.ts';

export type ConnectionStatus = 'ONLINE' | 'OFFLINE' | 'DEGRADED' | 'UNKNOWN';
export function connectionStatus(value: unknown): ConnectionStatus {
  return value==='ONLINE'||value==='OFFLINE'||value==='DEGRADED' ? value : 'UNKNOWN';
}
export function validPercent(value: unknown): number | null {
  return typeof value==='number' && Number.isFinite(value) && value>=0 && value<=100 ? value : null;
}
export function percentText(value: unknown): string {
  const percent=validPercent(value);
  return percent===null ? 'Veri yok' : new Intl.NumberFormat('tr-TR',{maximumFractionDigits:1}).format(percent)+'%';
}
function sourceTimestamp(value: unknown): string | null {
  return typeof value==='string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)) ? value : null;
}
export function buildRouterReport(items: Router[], now=new Date()) {
  if (!Array.isArray(items) || items.some(item=>item.is_demo!==true || typeof item.id!=='string' || !item.id)) throw new Error('Rapor yalnız kimliği belirli sentetik demo router kayıtlarını destekler.');
  if (new Set(items.map(item=>item.id)).size!==items.length) throw new Error('Router kayıtları tekil değil; rapor oluşturulamadı.');
  const rows=items.map(item=>({
    id:item.id, name:typeof item.name==='string'&&item.name.trim()?item.name:'Veri yok',
    site:typeof item.site==='string'&&item.site.trim()?item.site:'Veri yok', status:connectionStatus(item.status),
    cpu:validPercent(item.cpu_percent), memory:validPercent(item.memory_percent), source_time:sourceTimestamp(item.last_seen),
    device_uptime:typeof item.uptime==='string'&&item.uptime.trim()?item.uptime:null,
  }));
  const cpu=rows.flatMap(row=>row.cpu===null?[]:[row.cpu]);
  const memory=rows.flatMap(row=>row.memory===null?[]:[row.memory]);
  return {
    rows, generated_at:now.toISOString(), is_demo:true as const,
    counts:{total:rows.length,online:rows.filter(r=>r.status==='ONLINE').length,offline:rows.filter(r=>r.status==='OFFLINE').length,degraded:rows.filter(r=>r.status==='DEGRADED').length,unknown:rows.filter(r=>r.status==='UNKNOWN').length},
    cpu:{average:cpu.length?cpu.reduce((sum,n)=>sum+n,0)/cpu.length:null,samples:cpu.length},
    memory:{average:memory.length?memory.reduce((sum,n)=>sum+n,0)/memory.length:null,samples:memory.length},
    // No event or traffic source exists; never synthesize history from repeated snapshot reads.
    connection_history:null, traffic:null,
  };
}
