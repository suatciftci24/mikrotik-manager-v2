import {valuesText} from '../lib/subscriberHistory';
import type {OperationReportRow} from '../lib/subscriberOperationReport';

export function SubscriberOperationValues({row}:{row:OperationReportRow}){
 return <dl className="subscriber-operation-metadata">
  <div><dt>Önceki değerler</dt><dd>{valuesText(row.previous)}</dd></div>
  <div><dt>Yeni değerler</dt><dd>{row.skipped?'Değişiklik yok':row.success&&row.recorded?valuesText(row.values):row.recorded?'Uygulanmadı':'Veri yok'}</dd></div>
 </dl>;
}
