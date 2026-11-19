import {dateTime} from './Resource';
import {historyActor} from '../lib/subscriberHistory';
import {executionLabels,type OperationReportRow} from '../lib/subscriberOperationReport';

export function SubscriberOperationMetadata({row,onActor}:{row:OperationReportRow;onActor?:()=>void}){
 const actor=historyActor(row);
 return <dl className="subscriber-operation-metadata">
  <div><dt>Operatör</dt><dd>{onActor&&row.actor_id
   ?<button type="button" className="record-link" onClick={onActor}>{actor}</button>:actor}</dd></div>
  <div><dt>İşlem zamanı</dt><dd><time dateTime={row.occurred_at}>{dateTime(row.occurred_at)}</time></dd></div>
  <div><dt>İşlem kapsamı</dt><dd>{executionLabels[row.execution_type??'UNKNOWN']}</dd></div>
  {row.group_id&&<div><dt>Grup kimliği</dt><dd>{row.group_id}</dd></div>}
 </dl>;
}
