import {useEffect,useRef,useState,type FormEvent} from 'react';
import {ResourceState} from './Resource';
import {SubscriberOperationMetadata} from './SubscriberOperationMetadata';
import {SubscriberOperationValues} from './SubscriberOperationValues';
import {SubscriberUndoPreview} from './SubscriberUndoPreview';
import {subscriberOperationConflict} from '../lib/subscriberOperationError';
import {SourceBadge} from './Status';
import {linkedDetailHash} from '../lib/detailLinks';
import {reportPages} from '../lib/managementReport';
import {dailyLabels} from '../lib/subscriberManagementCenter';
import {executionLabels,operationReportCsv,operationReportPath,operationReportResult,operationReportResults,operationReportTypes,type OperationReportRow} from '../lib/subscriberOperationReport';
import {useResource} from '../lib/useResource';

type Counts={success:number;failed:number;skipped:number};
type ReportPage={items:OperationReportRow[];total:number;counts:Counts;groups:{group_id:string;total:number;success:number;failed:number;skipped:number}[];is_demo:true};
const emptyFilters={start:'',end:'',actor_id:'',operation:'ALL',result:'ALL',execution_type:'ALL',group_id:''};
const pageSize=25;

export function SubscriberOperationReport(){
 const [draft,setDraft]=useState(emptyFilters),[filters,setFilters]=useState(emptyFilters),[page,setPage]=useState(1);
 const [exporting,setExporting]=useState(false),[exportError,setExportError]=useState('');
 const activeExport=useRef<AbortController|null>(null);
 const params=new URLSearchParams({...filters,daily:'true'});
 if(!filters.group_id)params.delete('group_id');
 const path=operationReportPath+'?'+params;
 const resource=useResource<ReportPage>(path+`&page=${page}&page_size=${pageSize}`);
 const data=resource.data;
 const error=resource.error||(data&&(data.is_demo!==true||!data.counts)?'Toplu işlem raporu kaynağı doğrulanamadı.':undefined);

 useEffect(()=>()=>activeExport.current?.abort(),[]);

 function apply(next:typeof emptyFilters){
  activeExport.current?.abort();
  setExporting(false);
  setExportError('');
  setPage(1);
  setFilters({...next,actor_id:next.actor_id.trim()});
 }

 function openGroup(groupId:string){
  const next={...emptyFilters,execution_type:'BULK',group_id:groupId};
  setDraft(next);
  apply(next);
 }

 async function download(){
  if(activeExport.current&&!activeExport.current.signal.aborted)return;
  const controller=new AbortController();
  activeExport.current=controller;
  setExporting(true);
  setExportError('');
  try{
   const rows=await reportPages<OperationReportRow>(path,{signal:controller.signal});
   if(controller.signal.aborted)return;
   const url=URL.createObjectURL(new Blob([operationReportCsv(rows)],{type:'text/csv;charset=utf-8'}));
   const link=document.createElement('a');
   link.href=url;
   link.download='v26-toplu-abone-islemleri.csv';
   link.click();
   setTimeout(()=>URL.revokeObjectURL(url),0);
  }catch(cause){
   if(!controller.signal.aborted)setExportError(cause instanceof Error?cause.message:'CSV oluşturulamadı.');
  }finally{
   if(activeExport.current===controller){
    activeExport.current=null;
    if(!controller.signal.aborted)setExporting(false);
   }
  }
 }

 function submit(event:FormEvent){
  event.preventDefault();
  apply(draft);
 }

 return <section className="panel registry-detail">
  <h2>Toplu İşlem Raporu</h2>
  {filters.group_id&&<p className="operation-group-id">Grup ayrıntıları · {filters.group_id}</p>}
  <form className="router-report-controls" onSubmit={submit}>
   <label className="form-label">Başlangıç<input type="date" required={!!draft.end} value={draft.start} onChange={e=>setDraft({...draft,start:e.target.value})}/></label>
   <label className="form-label">Bitiş<input type="date" required={!!draft.start} min={draft.start||undefined} value={draft.end} onChange={e=>setDraft({...draft,end:e.target.value})}/></label>
   <label className="form-label">İşlem türü<select value={draft.operation} onChange={e=>setDraft({...draft,operation:e.target.value})}><option value="ALL">Tümü</option>{operationReportTypes.map(key=><option key={key} value={key}>{dailyLabels[key]}</option>)}</select></label>
   <label className="form-label">İşlemi yapan kullanıcı kimliği<input maxLength={80} value={draft.actor_id} onChange={e=>setDraft({...draft,actor_id:e.target.value})}/></label>
   <label className="form-label">Sonuç<select value={draft.result} onChange={e=>setDraft({...draft,result:e.target.value})}><option value="ALL">Tümü</option>{Object.entries(operationReportResults).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
   <label className="form-label">İşlem kapsamı<select value={draft.execution_type} onChange={e=>setDraft({...draft,execution_type:e.target.value})}><option value="ALL">Tümü</option>{Object.entries(executionLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
   {filters.group_id&&<button type="button" className="button-secondary" onClick={()=>{const next={...draft,group_id:''};setDraft(next);apply(next);}}>Grup filtresini kaldır</button>}
   <button className="button-primary">Filtrele</button>
   <button type="button" className="button-secondary" onClick={()=>{setDraft(emptyFilters);apply(emptyFilters);}}>Temizle</button>
  </form>
  <button className="button-secondary" disabled={resource.loading||!!error||!data?.total||exporting} onClick={()=>void download()}>{exporting?'CSV hazırlanıyor…':'Filtrelenen kayıtları CSV indir'}</button>
  {exportError&&<p role="alert">{exportError}</p>}
  <ResourceState {...resource} error={error}/>
  {!resource.loading&&!error&&data&&<>
   <p role="status">Başarılı: {data.counts.success} · Atlandı: {data.counts.skipped} · Reddedildi: {data.counts.failed}</p>
   <p>Sonuç filtresi özet sayımlarını değiştirmez. Atlandı sayısı yalnızca kalıcı sonuç kayıtlarını içerir.</p>
   {!!data.groups?.length&&<ul aria-label="Yetkili kayıtların grup toplamları" className="registry-history">{data.groups.map(group=><li key={group.group_id}>
    <button type="button" className="record-link" onClick={()=>openGroup(group.group_id)}>{group.group_id}</button>
    <span>Toplam: {group.total} · Başarılı: {group.success} · Reddedildi: {group.failed} · Atlandı: {group.skipped}</span>
   </li>)}</ul>}
   {data.items.length===0?<p>Bu filtrelere uyan kayıt bulunamadı.</p>:<ol className="registry-history">
    {data.items.map(row=><li key={row.request_id}>
     <strong>{dailyLabels[row.operation]} · {operationReportResult(row)}</strong>
     <SubscriberOperationMetadata row={row} onGroup={openGroup} onActor={()=>{const next={...filters,actor_id:row.actor_id};setDraft(next);apply(next);}}/>
     {row.skipped&&<span>Hesap zaten hedef durumdaydı.</span>}
     {row.recorded&&!row.success&&row.error&&<span>{subscriberOperationConflict(row.error)??row.error}</span>}
     <a className="record-link" href={linkedDetailHash({module:'subscribers',workspace:'PERSISTENT',id:row.item_id},window.location.hash)}>{row.subscriber_name??row.item_id}{row.subscriber_username&&` · ${row.subscriber_username}`}</a>
     <span>Yetkili kaynak <SourceBadge source={row.source??null}/></span>
     <SubscriberOperationValues row={row}/>
     <SubscriberUndoPreview requestId={row.request_id} itemId={row.item_id}/>
    </li>)}
   </ol>}
   <div className="table-footer"><span>{data.total} kayıt</span><button disabled={page===1} onClick={()=>setPage(page-1)}>Önceki</button><span>{page}</span><button disabled={page*pageSize>=data.total} onClick={()=>setPage(page+1)}>Sonraki</button></div>
  </>}
 </section>;
}
