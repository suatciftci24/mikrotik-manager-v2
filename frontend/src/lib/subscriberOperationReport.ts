import {auditLocalTime,excelCsv} from './auditCenter.ts';
import {dailyLabels,type OperationReceipt} from './subscriberManagementCenter.ts';
import {historyActor,valuesText} from './subscriberHistory.ts';

export type OperationReportRow=OperationReceipt & {
 subscriber_name?:string|null;
 subscriber_username?:string|null;
 actor_username?:string|null;
};

export const operationReportResults={SUCCESS:'Başarılı',SKIPPED:'Atlandı',FAILED:'Reddedildi'} as const;
export const executionLabels={SINGLE:'Tekil',BULK:'Toplu',UNKNOWN:'Veri yok'} as const;
export const operationReportTypes=['EXTEND','PLAN','STATUS'] as const;
export const operationReportPath='/subscriber-workspace/management/history';

export function operationReportResult(row:OperationReportRow){
 return row.skipped?'Atlandı':row.recorded?(row.success?'Başarılı':'Reddedildi'):'Belirsiz';
}

export function operationReportCsv(rows:OperationReportRow[]){
 return excelCsv(
  ['İşlem zamanı (Türkiye saati)','İşlemi yapan','Aktör kimliği','Abone','Abone kullanıcı adı','Abone kimliği','Yetkili kaynak','İşlem','İşlem kapsamı','Grup kimliği','Sonuç','Önceki değerler','Yeni değerler','İstek UUID'],
  rows.map(row=>[
   auditLocalTime(row.occurred_at),historyActor(row),row.actor_id,row.subscriber_name,row.subscriber_username,row.item_id,
   row.source,dailyLabels[row.operation]??row.operation,row.execution_type?executionLabels[row.execution_type]:null,row.group_id,operationReportResult(row),valuesText(row.previous),valuesText(row.values),row.request_id,
  ]),
 );
}
