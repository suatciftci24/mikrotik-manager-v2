import {useEffect,useRef,useState,type FormEvent} from 'react';
import {ResourceState,dateTime} from './Resource';
import {SourceBadge} from './Status';
import {linkedDetailHash} from '../lib/detailLinks';
import {reportPages} from '../lib/managementReport';
import {dailyLabels} from '../lib/subscriberManagementCenter';
import {historyActor,valuesText} from '../lib/subscriberHistory';
import {operationReportCsv,operationReportPath,operationReportResult,operationReportResults,operationReportTypes,type OperationReportRow} from '../lib/subscriberOperationReport';
import {useResource} from '../lib/useResource';

type ReportPage={items:OperationReportRow[];total:number;counts:{success:number;failed:number;skipped:null};is_demo:true};
const emptyFilters={start:'',end:'',actor_id:'',operation:'ALL',result:'ALL'};
const pageSize=25;

export function SubscriberOperationReport(){
 const [draft,setDraft]=useState(emptyFilters),[filters,setFilters]=useState(emptyFilters),[page,setPage]=useState(1);
 const [exporting,setExporting]=useState(false),[exportError,setExportError]=useState('');
 const activeExport=useRef<AbortController|null>(null);
 const path=operationReportPath+'?'+new URLSearchParams({...filters,daily:'true'});
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
  <form className="router-report-controls" onSubmit={submit}>
   <label className="form-label">Başlangıç<input type="date" required={!!draft.end} value={draft.start} onChange={e=>setDraft({...draft,start:e.target.value})}/></label>
   <label className="form-label">Bitiş<input type="date" required={!!draft.start} min={draft.start||undefined} value={draft.end} onChange={e=>setDraft({...draft,end:e.target.value})}/></label>
   <label className="form-label">İşlem türü<select value={draft.operation} onChange={e=>setDraft({...draft,operation:e.target.value})}><option value="ALL">Tümü</option>{operationReportTypes.map(key=><option key={key} value={key}>{dailyLabels[key]}</option>)}</select></label>
   <label className="form-label">İşlemi yapan kullanıcı kimliği<input maxLength={80} value={draft.actor_id} onChange={e=>setDraft({...draft,actor_id:e.target.value})}/></label>
   <label className="form-label">Sonuç<select value={draft.result} onChange={e=>setDraft({...draft,result:e.target.value})}><option value="ALL">Tümü</option>{Object.entries(operationReportResults).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
   <button className="button-primary">Filtrele</button>
   <button type="button" className="button-secondary" onClick={()=>{setDraft(emptyFilters);apply(emptyFilters);}}>Temizle</button>
  </form>
  <p>Uzatma, paket ve durum audit kayıtları abone bazındadır. Toplu çağrı kimliği ve atlanan satırlar audit’te tutulmaz.</p>
  <button className="button-secondary" disabled={resource.loading||!!error||!data?.total||exporting} onClick={()=>void download()}>{exporting?'CSV hazırlanıyor…':'Filtrelenen kayıtları CSV indir'}</button>
  {exportError&&<p role="alert">{exportError}</p>}
  <ResourceState {...resource} error={error}/>
  {!resource.loading&&!error&&data&&<>
   <p role="status">Başarılı: {data.counts.success} · Atlandı: Veri yok · Başarısız: {data.counts.failed}</p>
   <p>Özet, sonuç filtresi dışındaki seçili ölçütlere göre hesaplanır.</p>
   {filters.result==='SKIPPED'?<p>Atlanan işlemler için geçmiş kaydı bulunmaz.</p>:data.items.length===0?<p>Bu filtrelere uyan kayıt bulunamadı.</p>:<ol className="registry-history">
    {data.items.map(row=><li key={row.request_id}>
     <strong>{dailyLabels[row.operation]} · {operationReportResult(row)}</strong>
     <span>{dateTime(row.occurred_at)} · <button type="button" className="record-link" onClick={()=>{const next={...filters,actor_id:row.actor_id};setDraft(next);apply(next);}}>{historyActor(row)}</button></span>
     <a className="record-link" href={linkedDetailHash({module:'subscribers',workspace:'PERSISTENT',id:row.item_id},window.location.hash)}>{row.subscriber_name??row.item_id}{row.subscriber_username&&` · ${row.subscriber_username}`}</a>
     <span>Yetkili kaynak <SourceBadge source={row.source??null}/></span>
     <dl className="detail-facts"><div><dt>Önceki</dt><dd>{valuesText(row.previous)}</dd></div><div><dt>Yeni</dt><dd>{valuesText(row.values)}</dd></div></dl>
    </li>)}
   </ol>}
   <div className="table-footer"><span>{data.total} kayıt</span><button disabled={page===1} onClick={()=>setPage(page-1)}>Önceki</button><span>{page}</span><button disabled={page*pageSize>=data.total} onClick={()=>setPage(page+1)}>Sonraki</button></div>
  </>}
 </section>;
}
