import {dateTime} from './Resource';
import {historyActor} from '../lib/subscriberHistory';
import {executionLabels,operationHistoryLink,type OperationReportRow} from '../lib/subscriberOperationReport';

export function SubscriberOperationMetadata({row,onActor,onGroup}:{row:OperationReportRow;onActor?:()=>void;onGroup?:(id:string)=>void}){
 const actor=historyActor(row),group=row.group_id;
 return <dl className="subscriber-operation-metadata">
  <div><dt>Operatör</dt><dd>{onActor&&row.actor_id
   ?<button type="button" className="record-link" onClick={onActor}>{actor}</button>:actor}</dd></div>
  <div><dt>İşlem zamanı</dt><dd><time dateTime={row.occurred_at}>{dateTime(row.occurred_at)}</time></dd></div>
  <div><dt>İşlem kapsamı</dt><dd>{executionLabels[row.execution_type??'UNKNOWN']}</dd></div>
  {group&&<div><dt>Grup kimliği</dt><dd>{onGroup?<button type="button" className="record-link" onClick={()=>onGroup(group)}>{group}</button>:group}</dd></div>}
  {row.source_request_id&&<div><dt>Kaynak işlem</dt><dd><a className="record-link" href={operationHistoryLink(row.source_request_id)}>{row.source_request_id}</a></dd></div>}
  {row.source_group_id&&<div><dt>Kaynak grup</dt><dd>{row.source_group_id}</dd></div>}
 </dl>;
}
