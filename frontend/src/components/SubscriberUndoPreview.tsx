import {useRef,useState} from 'react';
import {api,ApiError} from '../lib/api';
import {historyActor,valuesText} from '../lib/subscriberHistory';
import {operationReportPath,operationReportResult,operationHistoryLink,operationGroupLink,undoStatusLabels,type UndoStatus} from '../lib/subscriberOperationReport';
import {useResource} from '../lib/useResource';
import {rememberPending,forgetPending} from '../lib/pendingSubscriberOperations';
import {invalidateResources} from '../lib/resourceEvents';
import {subscriberSaveDependencies} from '../lib/subscriberDependencies';
import {subscriberOperationError} from '../lib/subscriberOperationError';
import {dailyLabels,type OperationReceipt} from '../lib/subscriberManagementCenter';
import {ResourceState,dateTime} from './Resource';

type Change={field:string;previous:string|null;applied:string|null;current:string|null};
type Preview={
 request_id:string;
 item_id:string;
 subscriber_name?:string|null;
 source_group_id:string|null;
 can_execute:boolean;
 audit_revision:number;
 current_revision:number;
 status:UndoStatus;
 operation:string;
 actor_id:string;
 actor_username?:string|null;
 occurred_at:string;
 undo_request_id?:string|null;
 reason:string;
 changes:Change[];
 is_demo:true;
};
type PreviewTarget={requestId:string;itemId:string;groupId?:never}|{groupId:string;requestId?:never;itemId?:never};
type UndoEntry={
 request_id:string; source_request_id:string; source_group_id:string|null; item_id:string;
 expected_revision:number; field:string; previous:string|null; applied:string|null;
};
const allowedFields=['customer_name','status','expires_on'];

function UndoConfirmation({items,canExecute}:{items:Preview[];canExecute:boolean}){
 const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false);
 const [results,setResults]=useState<OperationReceipt[]|null>(null),[error,setError]=useState(''),[rejected,setRejected]=useState(false);
 const [attempted,setAttempted]=useState(false);
 const sourceGroup=items[0]?.source_group_id;
 const sourceLink=sourceGroup?operationGroupLink(sourceGroup):operationHistoryLink(items[0].request_id);
 const sending=useRef(false),finished=useRef(false),attempt=useRef<UndoEntry[]|null>(null);
 const eligible=items.filter(item=>item.can_execute&&item.status==='ELIGIBLE'&&item.changes.length===1
  &&allowedFields.includes(item.changes[0].field)&&item.changes[0].current===item.changes[0].applied
  &&item.changes[0].previous!==item.changes[0].applied);
 if(!canExecute||eligible.length!==items.length)return null;

 async function apply(){
  if(!confirmed||sending.current||finished.current)return;
  const replay=attempt.current!==null;
  attempt.current??=items.map(item=>{
   const {field,previous,applied}=item.changes[0];
   return {request_id:crypto.randomUUID(),source_request_id:item.request_id,source_group_id:item.source_group_id,
    item_id:item.item_id,expected_revision:item.current_revision,field,previous,applied};
  });
  const entries=attempt.current;
  sending.current=true;setBusy(true);setAttempted(true);setError('');
  try{
   for(const entry of entries)rememberPending(entry.request_id,'/subscriber-workspace/management/requests/'+entry.request_id);
   const response=await api<{is_demo:true;results:OperationReceipt[]}>('/subscriber-workspace/management/undo',{
    method:'POST',headers:{'X-V2-Demo-Action':'subscriber-workspace'},
    body:JSON.stringify({confirmed:true,entries}),signal:AbortSignal.timeout(15000),
   });
   if(response?.is_demo!==true||!Array.isArray(response.results)||response.results.length!==entries.length)
    throw new Error('Geri alma sonucu doğrulanamadı.');
   const receipts=entries.map(entry=>response.results.find(r=>r?.request_id===entry.request_id));
   const group=receipts[0]?.group_id??null;
   if((entries.length>1)!==!!group||receipts.some((row,i)=>!row||!validReceipt(row,entries[i])
     ||row.success!==receipts[0]?.success||(row.group_id??null)!==group))
    throw new Error('Geri alma sonucu onaylanan kayıtlarla eşleşmedi.');
   for(const entry of entries)forgetPending(entry.request_id);
   finished.current=true;setResults(receipts as OperationReceipt[]);
   // The current history card keeps the confirmation and receipt visible.
   invalidateResources(subscriberSaveDependencies.filter(path=>path!=='/subscriber-workspace'));
  }catch(failure){
   const definitive=failure instanceof ApiError&&[400,401,403,404,409,422].includes(failure.status);
   if(definitive){
    if(!replay)for(const entry of entries)forgetPending(entry.request_id);
    finished.current=true;setRejected(true);
   }
   setError(subscriberOperationError(failure)+(definitive&&replay?' Önceki gönderimin sonucu hâlâ belirsiz.':''));
  }finally{
   sending.current=false;setBusy(false);
  }
 }

 if(results)return <div role="status">
  <strong>{results[0].success?'Geri alma kaydedildi.':'Geri alma reddedildi. Hiçbir abonelik değişmedi.'}</strong>
  <ul>{results.map((row,i)=><li key={row.request_id}>{items[i].subscriber_name??row.item_id} · {operationReportResult(row)}
   {row.error&&<p>{row.error}</p>}
   <a className="record-link" href={operationHistoryLink(row.request_id)}>Geri alma audit kaydını aç</a>
  </li>)}</ul>
  <a className="record-link" href={sourceLink}>{sourceGroup?'Kaynak işlem grubunu aç':'Kaynak işlem kaydını aç'}</a>
 </div>;
 return <>
  {!rejected&&<fieldset disabled={busy}>
   <legend>{items.length>1?`${items.length} abonelik için toplu geri alma`:'Tek abonelik için geri alma'}</legend>
   <label className="registry-consent"><input type="checkbox" checked={confirmed} disabled={attempted}
    onChange={event=>setConfirmed(event.target.checked)}/>Gösterilen önceki değerleri ve abonelikleri kontrol ettim. Geri yüklemeyi onaylıyorum.</label>
   <button type="button" className="button-primary" disabled={!confirmed} onClick={()=>void apply()}>
    {busy?'Geri alma bekleniyor…':attempted?'Aynı istekle tekrar dene':items.length>1?'Onayla ve grubu geri al':'Onayla ve geri al'}
   </button>
  </fieldset>}
  {error&&<div role="alert">
   <p>{error}{!rejected&&' Sonuç belirsiz. Doğrulama için aynı istekle tekrar deneyin.'}</p>
   <a className="record-link" href={sourceLink}>Kaynak işlem geçmişini aç</a>
   {attempt.current?.map((entry,index)=><p key={entry.request_id}>
    <a className="record-link" href={operationHistoryLink(entry.request_id)}>
     {items[index]?.subscriber_name??entry.item_id} · Geri alma kaydını sorgula
    </a>
   </p>)}
  </div>}
 </>;
}

function validReceipt(row:OperationReceipt,entry:UndoEntry){
 if(row.item_id!==entry.item_id||row.source_request_id!==entry.source_request_id
   ||row.source_group_id!==entry.source_group_id||row.operation!=='UNDO'||row.recorded!==true||row.skipped
   ||!row.actor_id||!Number.isFinite(Date.parse(row.occurred_at)))return false;
 return row.success===true
  ? row.revision===entry.expected_revision+1&&row.error===null&&row.previous?.[entry.field]===entry.applied&&row.values?.[entry.field]===entry.previous
  : row.success===false&&Number.isInteger(row.revision)&&row.revision>0&&typeof row.error==='string'&&!!row.error;
}

function PreviewContent(target:PreviewTarget){
 const path=target.groupId
  ? operationReportPath+'/groups/'+encodeURIComponent(target.groupId)+'/undo-preview'
  : operationReportPath+'/'+encodeURIComponent(target.requestId??'')+'/undo-preview';
 const resource=useResource<Preview|{is_demo:true;group_id:string;items:Preview[];can_execute:boolean;reason?:string|null}>(path);
 const data=resource.data;
 const items=data&&'items' in data
  ? (target.groupId===data.group_id&&Array.isArray(data.items)?data.items:null)
  : (data&&data.request_id===target.requestId&&data.item_id===target.itemId?[data]:null);
 const verified=data?.is_demo===true&&!!items?.length&&items.every(item=>Object.hasOwn(undoStatusLabels,item.status)&&Array.isArray(item.changes));
 const canExecute=data?.can_execute===true;
 const reason=data&&'items' in data?data.reason:null;
 const error=resource.error||(data&&!verified?'Geri alma önizlemesi işlem kaydıyla eşleşmedi.':undefined);
 return <>
  <ResourceState {...resource} error={error}/>
  {items&&verified&&!resource.loading&&!error&&<>
   <p>{canExecute?'Onay, gösterilen önceki değerleri sentetik aboneliklere geri yükler. Sunucu güncel değerleri ve revizyonları yeniden doğrular. Bir kayıt çakışırsa hiçbir abonelik değişmez.':'Salt okunur değerlendirme'}</p>
   {reason&&<p role="status">{reason}</p>}
   {items.map(preview=><section key={preview.request_id}>
    {target.groupId&&<strong>{preview.subscriber_name??preview.item_id}</strong>}
    <dl className="subscriber-operation-metadata">
     <div><dt>Kaynak işlem</dt><dd><a className="record-link" href={operationHistoryLink(preview.request_id)}>{dailyLabels[preview.operation]??preview.operation??'İşlem kaydı'}</a></dd></div>
     <div><dt>Operatör</dt><dd>{historyActor(preview)}</dd></div>
     <div><dt>İşlem zamanı</dt><dd>{dateTime(preview.occurred_at)}</dd></div>
    </dl>
    <p role="status"><strong>{undoStatusLabels[preview.status]}.</strong> {preview.reason}</p>
    {preview.undo_request_id&&<a className="record-link" href={operationHistoryLink(preview.undo_request_id)}>Geri alma kaydını aç</a>}
    {!target.groupId&&preview.source_group_id&&preview.status==='ELIGIBLE'&&
     <a className="record-link" href={operationGroupLink(preview.source_group_id)}>Kaynak grubun tamamını incele</a>}
    <p>İşlem revizyonu {preview.audit_revision} · Güncel revizyon {preview.current_revision}</p>
    {preview.changes.map(change=><dl key={change.field} className="subscriber-operation-metadata">
     <div><dt>İşlemden önce</dt><dd>{valuesText({[change.field]:change.previous})}</dd></div>
     <div><dt>İşlemde kaydedilen</dt><dd>{valuesText({[change.field]:change.applied})}</dd></div>
     <div><dt>Güncel</dt><dd>{valuesText({[change.field]:change.current})}</dd></div>
    </dl>)}
   </section>)}
   <UndoConfirmation items={items} canExecute={canExecute}/>
  </>}
 </>;
}

export function SubscriberUndoPreview(target:PreviewTarget){
 const [open,setOpen]=useState(false);
 const [loaded,setLoaded]=useState(false);
 return <details className="subscriber-undo-preview" onToggle={event=>{
  const visible=event.currentTarget.open;setOpen(visible);
  if(visible)setLoaded(true);
 }}>
  <summary>{target.groupId?'Grubu geri alma önizlemesi':'Geri alma önizlemesi'}</summary>
  {loaded&&<div hidden={!open}><PreviewContent {...target}/></div>}
 </details>;
}
