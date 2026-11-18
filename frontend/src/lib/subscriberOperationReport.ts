import {auditLocalTime,excelCsv} from './auditCenter.ts';
import {dailyLabels,type OperationReceipt} from './subscriberManagementCenter.ts';
import {historyActor,valuesText} from './subscriberHistory.ts';

export type OperationReportRow=OperationReceipt & {
 subscriber_name?:string|null;
 subscriber_username?:string|null;
 actor_username?:string|null;
};

export const operationReportResults={SUCCESS:'Başarılı',SKIPPED:'Atlandı',FAILED:'Başarısız'} as const;
export const operationReportTypes=['EXTEND','PLAN','STATUS'] as const;
export const operationReportPath='/subscriber-workspace/management/history';

export function operationReportResult(row:OperationReportRow){
 return row.skipped?'Atlandı':row.recorded?(row.success?'Başarılı':'Başarısız'):'Belirsiz';
}

export function operationReportCsv(rows:OperationReportRow[]){
 return excelCsv(
  ['İşlem zamanı (Türkiye saati)','İşlemi yapan','Aktör kimliği','Abone','Abone kullanıcı adı','Abone kimliği','Yetkili kaynak','İşlem','Sonuç','Önceki değerler','Yeni değerler','Audit UUID'],
  rows.map(row=>[
   auditLocalTime(row.occurred_at),historyActor(row),row.actor_id,row.subscriber_name,row.subscriber_username,row.item_id,
   row.source,dailyLabels[row.operation]??row.operation,operationReportResult(row),valuesText(row.previous),valuesText(row.values),row.request_id,
  ]),
 );
}
