import {historyActor} from '../lib/subscriberHistory';
import {eventLabel,managementLabels,routerFieldLabels,simulationLabels,type ManagementStatus,type RouterEvent,type SimulationStatus} from '../lib/routerCenter';
import {dateTime} from './Resource';

function fieldValue(key:string,value:string|null){
 if(!value)return '—';
 if(key==='simulated_last_seen_at')return dateTime(value);
 if(key==='management_status')return managementLabels[value as ManagementStatus]??value;
 if(key==='simulated_status')return simulationLabels[value as SimulationStatus]??value;
 return value;
}

export function RouterHistory({events}:{events:RouterEvent[]}){
 if(!events.length)return <p>Kayıtlı işlem bulunmuyor.</p>;
 return <ol className="registry-history">{events.map((event,index)=>
  <li key={index}>
   <strong>{eventLabel(event.action)}</strong>
   <span>{dateTime(event.occurred_at)} · {historyActor(event)}</span>
   <details className="technical-info">
    <summary>İşlem ayrıntıları</summary>
    {event.record_id&&<p>Kayıt kimliği: {event.record_id}</p>}
    <p>Aktör kimliği: {event.actor_id}{event.revision!=null&&` · Revizyon ${event.revision}`}</p>
    {event.changes&&Object.keys(event.changes).length>0&&<dl className="registry-facts">
     {Object.entries(event.changes).map(([key,{previous,new:next}])=><div key={key}>
      <dt>{routerFieldLabels[key as keyof typeof routerFieldLabels]??key}</dt>
      <dd>Önceki: {fieldValue(key,previous)}<br/>Yeni: {fieldValue(key,next)}</dd>
     </div>)}
    </dl>}
   </details>
  </li>)}</ol>;
}
