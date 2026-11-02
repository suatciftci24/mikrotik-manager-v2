import {validInventory,freshness,type Inventory} from '../components/V1Inventory.tsx';
import {observationTime} from './subscriberObservation.ts';
type Row=Inventory['items'][number];
/** A legacy inventory timestamp is not a verified router health sample. */
export function hasV1Health(row:Row,now:number){
 const stamp=observationTime(row.sampled_at);
 return row.health_source==='V1_ROUTER_HEALTH_SAMPLES'&&!!row.health_sample_id&&stamp!==null&&Date.parse(stamp)<=now;
}
export function dashboardV1Health(data:unknown,now=Date.now()){
 if(!validInventory(data)||!Number.isFinite(now)||data.availability==='NO_DATA'&&data.items.length>0||data.availability==='AVAILABLE'&&data.items.length===0)throw new Error('Gerçek V1 sağlık kaynağı doğrulanamadı.');
 const rows=data.items.map(row=>({row,measured:hasV1Health(row,now),freshness:hasV1Health(row,now)?freshness(row,now):'Veri yok'}));
 return {rows,total:rows.length,recent:rows.filter(item=>item.measured&&item.freshness==='Son bilinen ölçüm').length,stale:rows.filter(item=>item.measured&&item.freshness==='Güncel değil').length,missing:rows.filter(item=>!item.measured).length};
}
