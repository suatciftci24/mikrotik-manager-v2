import type { DailyOperation } from './dailySummary.ts';

const DAY=24*60*60*1000;
export function buildOperationWindow(history:DailyOperation[],now=new Date()) {
  const end=now.getTime();
  if (!Number.isFinite(end)) throw new Error('İşlem aralığı zamanı geçersiz.');
  const events=history.filter(event=>{
    const time=Date.parse(event.occurred_at);
    return time>=end-DAY&&time<=end;
  }).sort((a,b)=>Date.parse(b.occurred_at)-Date.parse(a.occurred_at)||a.id.localeCompare(b.id));
  const affected=[...new Map(events.map(event=>[event.subscriber_id,{id:event.subscriber_id,name:event.customer_name,router_name:event.router_name}])).values()];
  return {
    from:new Date(end-DAY).toISOString(),to:now.toISOString(),events,affected,
    counts:{total:events.length,create:events.filter(e=>e.operation==='CREATE').length,
      plan:events.filter(e=>e.operation==='PLAN_CHANGE').length,status:events.filter(e=>e.operation==='STATUS_CHANGE').length,
      renewal:events.filter(e=>e.operation==='RENEWAL').length,date_edit:events.filter(e=>e.operation==='DATE_EDIT').length},
  };
}
