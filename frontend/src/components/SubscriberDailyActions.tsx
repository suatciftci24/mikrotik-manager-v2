import {SubscriberOperationResults} from './SubscriberOperationResults';
import {SubscriberOperationReport} from './SubscriberOperationReport';
import {SubscriberOperationPreview} from './SubscriberOperationPreview';
import {SubscriberOperationMetadata} from './SubscriberOperationMetadata';
import {SubscriberOperationValues} from './SubscriberOperationValues';
import {SubscriberUndoPreview} from './SubscriberUndoPreview';
import {operationReportResult,operationReportResults,type OperationReportRow} from '../lib/subscriberOperationReport';
import {subscriberOperationConflict} from '../lib/subscriberOperationError';
import {loadPackageChoices,selectablePackage,packageSpeed,type PackageRecord} from '../lib/packages';
import {loadWorkspaceRouterChoices} from '../lib/workspaceDashboard';
import {useIdentity} from '../lib/permissions';
import {SourceBadge} from './Status';
import {accountActionLabel,nextAccountStatus} from '../lib/subscriberActions';
import {linkedDetailHash} from '../lib/detailLinks';
import {useSubscriberTextFilter} from '../lib/useSubscriberTextFilter';
import {useListFilter} from '../lib/useListFilter';
import {rememberPending,forgetPending} from '../lib/pendingSubscriberOperations';
import {useEffect,useRef,useState,type FormEvent} from 'react';
import {api,ApiError} from '../lib/api';
import {subscriberOperationError,operationReceiptMatches,readOperationResults,unknownOperation} from '../lib/subscriberOperationRecovery';
import {subscriberSaveDependencies} from '../lib/useSubscriberSave';
import {useResource} from '../lib/useResource';
import {invalidateResources} from '../lib/resourceEvents';
import {useTurkeyToday} from '../lib/useTurkeyToday';
import {dailyEntries,dailyLabels,maxDailyExtensionDays,operationResolved,previousDailyValue,type DailyAction,type DailyEntry,type OperationReceipt} from '../lib/subscriberManagementCenter';
import type {CenterSubscriber} from '../lib/subscriberCenter';
import {ResourceState} from './Resource';
import {expiryDate} from '../lib/expiry';
export function SubscriberDailyActions({rows,onClose,initialAction='EXTEND',fixedAction}:{rows:CenterSubscriber[];onClose:()=>void;initialAction?:DailyAction;fixedAction?:DailyAction}){
 const identity=useIdentity();const centralAdmin=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
 const catalog=useResource<{items:PackageRecord[]}>('/packages',loadPackageChoices,['/packages']);
 const [packageId,setPackageId]=useState('');
 const activePackages=catalog.data?.items.filter(selectablePackage)??[];
 const dialog=useRef<HTMLDialogElement>(null),sending=useRef(false),attempted=useRef(false),frozen=useRef<{entries:DailyEntry[];body:string}|null>(null);const today=useTurkeyToday();
 const entryAction=useRef(fixedAction),entryStatus=useRef(rows[0]?.status);
 const [selectedAction,setAction]=useState<DailyAction>(entryAction.current??initialAction),[duration,setDuration]=useState('30'),[customDays,setCustomDays]=useState(''),[value,setValue]=useState((entryAction.current??initialAction)==='STATUS'&&rows.length===1?nextAccountStatus(rows[0].status):''),[review,setReview]=useState<ReturnType<typeof previewCards>|null>(null),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[results,setResults]=useState<OperationReceipt[]|null>(null),[uncertain,setUncertain]=useState(false),[rejected,setRejected]=useState(false);
 const action=entryAction.current??selectedAction;
 const days=Number(duration==='CUSTOM'?customDays:duration);
 const title=entryAction.current==='PLAN'?'Paket Değiştir':entryAction.current==='STATUS'?accountActionLabel(entryStatus.current??''):entryAction.current==='EXTEND'?'Abonelik Uzat':entryAction.current?dailyLabels[entryAction.current]:'Abone işlemi';
 const routers=useResource<{items:{id:string;fields:{name:string}}[]}>('/router-workspace/routers?page_size=100',loadWorkspaceRouterChoices,['/router-workspace/routers']);
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};},[]);
 const reviewHeading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{if(review)reviewHeading.current?.focus();},[review]);

 function display(value:string|null){
  if(action==='EXTEND'||action==='EXPIRE')return expiryDate(value);
  if(action==='STATUS')return value==='ACTIVE'?'Aktif hesap':value==='PAUSED'?'Pasif hesap':'Bilinmiyor';
  if(action==='ROUTER'&&value){
   const name=routers.data?.items.find(r=>r.id===value)?.fields.name??rows.find(r=>r.router_id===value)?.router_name;
   return name?`${name} · ${value}`:value;
  }
  return value??'Bilinmiyor';
 }

 function previewCards(entries:DailyEntry[], selected?:PackageRecord){
  return entries.map((entry,index)=>{
   const row=rows[index];
   const skip=entry.operation==='STATUS'&&entry.expected_status===entry.value;
   const currentPackage=row.package_snapshot;
   const samePackage=!!selected&&!!currentPackage&&row.plan===entry.value&&row.package_id===selected.id
    &&row.package_revision===selected.revision&&Object.keys(currentPackage).length===Object.keys(selected.fields).length
    &&Object.entries(selected.fields).every(([key,value])=>currentPackage[key as keyof typeof currentPackage]===value);
   const disposition=skip?'skip' as const:samePackage?'reject' as const:'change' as const;
   const previous=action==='EXTEND'?entry.expected_expires_on:action==='STATUS'?entry.expected_status??null:previousDailyValue(row,action);
   const changes=[{label:action==='EXTEND'?'Bitiş tarihi':dailyLabels[action],previous:display(previous),next:display(entry.value)}];
   if(selected)changes.push({label:'Hız',previous:packageSpeed(row.package_snapshot),next:packageSpeed(selected.fields)});
   const outcome=skip?'Önizlemede zaten hedef durumda. Revizyon güncelse hesap değişmeden atlanır.'
    :samePackage?'Seçilen paket ve sürümü zaten kayıtlı. Sunucu mevcut değerle aynı olan seçimi reddeder.'
    :action==='STATUS'?'Hesap durumu güncellenir. Abonelik bitişi korunur.'
    :action==='PLAN'?'Paket seçimi uygulanır. Abonelik bitişi korunur.':'Yalnız gösterilen alan güncellenir.';
   return {id:row.id,customer_name:row.customer_name,username:row.username,router:row.router_name??'Bilinmiyor',changes,outcome,disposition};
  });
 }
 function prepare(event:FormEvent){event.preventDefault();setError('');try{
  if(entryAction.current&&rows.length!==1)throw new Error('Bu işlem girişi yalnız bir abone için kullanılabilir.');
  const selected=action==='PLAN'?activePackages.find(row=>row.id===packageId):undefined;
  if(action==='PLAN'&&(catalog.loading||catalog.error||!selected))throw new Error('Kayıtlı aktif paket seçin.');
  const entries=dailyEntries(rows,action,selected?.fields.name??value,days,today,()=>crypto.randomUUID(),selected?{package_id:selected.id,package_revision:selected.revision}:undefined);
  frozen.current={entries,body:JSON.stringify({entries})};attempted.current=false;
  setReview(previewCards(entries,selected));setConfirmed(false);setResults(null);setUncertain(false);setRejected(false);
 }catch(e){setError(e instanceof Error?e.message:'Alanları kontrol edin.');}}
 async function save(){
  if(!frozen.current?.entries.length||!confirmed||sending.current||rejected||results?.every(operationResolved))return;
  const command=frozen.current,query=attempted.current;attempted.current=true;
  sending.current=true;setBusy(true);setError('');
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try{
   let receipts:OperationReceipt[];
   if(query)receipts=await readOperationResults(command.entries,results??[],controller.signal);
   else{
    for(const entry of command.entries)rememberPending(entry.request_id,'/subscriber-workspace/management/requests/'+entry.request_id);
    const data=await api<{results:OperationReceipt[]}>('/subscriber-workspace/management/execute',{method:'POST',signal:controller.signal,headers:{'X-V2-Demo-Action':'subscriber-workspace'},body:command.body});
    if(!Array.isArray(data?.results)||data.results.length!==command.entries.length||new Set(data.results.map(r=>r?.request_id)).size!==command.entries.length)throw new Error('İşlem sonuçları onaylanan kayıtlarla eşleşmedi.');
    receipts=command.entries.map(entry=>data.results.find(receipt=>operationReceiptMatches(entry,receipt))??unknownOperation(entry));
    if(!receipts.some(operationResolved))throw new Error('İşlem sonuçları onaylanan kayıtlarla eşleşmedi.');
   }
   for(const receipt of receipts)if(operationResolved(receipt))forgetPending(receipt.request_id);
   setResults(receipts);setUncertain(receipts.some(r=>!operationResolved(r)));
  }catch(e){
   const failed=!query&&e instanceof ApiError&&[400,401,403,404,409,422].includes(e.status);
   if(failed)for(const entry of command.entries)forgetPending(entry.request_id);
   setRejected(failed);setUncertain(!failed);
   if(!failed)setResults(command.entries.map(entry=>results?.find(r=>operationResolved(r)&&operationReceiptMatches(entry,r))??unknownOperation(entry)));
   setError(subscriberOperationError(e));
  }finally{clearTimeout(timer);sending.current=false;setBusy(false);invalidateResources([...subscriberSaveDependencies]);}
 }
 const skipCount=review?.filter(card=>card.disposition==='skip').length??0;
 const changeCount=review?.filter(card=>card.disposition==='change').length??0;
 const rejectCount=(review?.length??0)-changeCount-skipCount;
 return <dialog ref={dialog} className={'expiry-dialog router-onboarding subscriber-daily-dialog'+(entryAction.current?' fixed-subscriber-operation':'')} aria-busy={busy} aria-labelledby="daily-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}><h2 id="daily-title">{title} · SENTETİK</h2><p>{review?.length??rows.length} seçili abone</p>
 {!review&&<details><summary>Seçilen aboneler ({rows.length})</summary><ul>{rows.map(row=><li key={row.id}>{row.customer_name} · {row.username} · {row.access_type} · {row.router_name}</li>)}</ul></details>}
 {!review?<form onSubmit={prepare}>{action==='PLAN'&&<><ResourceState {...catalog}/><label className="form-label">Kayıtlı yeni paket<select required value={packageId} disabled={catalog.loading||!!catalog.error} onChange={e=>{const selected=activePackages.find(row=>row.id===e.target.value);setPackageId(selected?.id??'');setValue(selected?.fields.name??'');}}><option value="">Kayıtlı aktif paket seçin</option>{activePackages.map(row=><option key={row.id} value={row.id}>{row.fields.name} · {packageSpeed(row.fields)}</option>)}</select></label>{!catalog.loading&&!catalog.error&&!activePackages.length&&<p>Atanabilecek aktif paket yok. Paket Yönetimi’nden paket ekleyin.</p>}{rows.length===1&&<div className="package-choice-summary"><p>Mevcut paket: <strong>{rows[0].plan}</strong> · {packageSpeed(rows[0].package_snapshot)}</p><p>Yeni paket: <strong>{activePackages.find(row=>row.id===packageId)?.fields.name??'Paket seçilmedi'}</strong> · {packageSpeed(activePackages.find(row=>row.id===packageId)?.fields)}</p></div>}</>}{!entryAction.current&&<label className="form-label">İşlem<select value={action} onChange={e=>{setAction(e.target.value as DailyAction);setValue(e.target.value==='STATUS'&&rows.length===1?nextAccountStatus(rows[0].status):'');}}><option value="EXTEND">Abonelik uzatma</option><option value="STATUS">Etkinleştirme / devre dışı bırakma</option>{(rows.length===1||rows.every(row=>row.access_type==='PPPOE'))&&<option value="PLAN">Paket / profil değiştir</option>}{rows.length===1&&<><option value="EDIT">Abone bilgisini düzenle</option><option value="EXPIRE">Bitiş tarihi belirle</option>{centralAdmin&&<option value="ROUTER">Bağlı routerı değiştir</option>}</>}</select></label>}
 {action==='EXTEND'?<><label className="form-label">Süre<select value={duration} onChange={e=>setDuration(e.target.value)}>{[30,60,90].map(d=><option key={d} value={d}>{d} gün</option>)}<option value="CUSTOM">Özel gün sayısı</option></select></label>{duration==='CUSTOM'&&<label className="form-label">Uzatma süresi (gün)<input type="number" inputMode="numeric" required min={1} max={maxDailyExtensionDays} step={1} value={customDays} onChange={e=>setCustomDays(e.target.value)}/></label>}</>:action==='STATUS'&&entryAction.current?<p>Yeni hesap durumu: <strong>{value==='ACTIVE'?'Aktif hesap':'Pasif hesap'}</strong></p>:action==='STATUS'?<label className="form-label">Yeni hesap durumu<select required value={value} onChange={e=>setValue(e.target.value)}><option value="">Seçin</option><option value="ACTIVE">Hesabı Etkinleştir</option><option value="PAUSED">Hesabı Pasifleştir</option></select></label>:action==='ROUTER'?<><ResourceState {...routers}/><label className="form-label">Hedef sentetik router<select required value={value} onChange={e=>setValue(e.target.value)}><option value="">Seçin</option>{routers.data?.items.map(r=><option key={r.id} value={r.id}>{r.fields.name} · {r.id}</option>)}</select></label></>:action==='PLAN'?null:<label className="form-label">{dailyLabels[action]}<input required={action!=='EXPIRE'} type={action==='EXPIRE'?'date':'text'} maxLength={160} value={value} onChange={e=>setValue(e.target.value)}/>{action==='EXPIRE'&&<small>Boş bırakılırsa tarih bilinmiyor olarak kaydedilir; hesap pasifleştirilmez.</small>}</label>}
 <button className="button-primary">Önizle ve gözden geçir</button></form>:<>
 {!results&&!rejected&&<>
  <h3 ref={reviewHeading} tabIndex={-1}>{dailyLabels[action]}{action==='EXTEND'?` · ${days} gün`:''}</h3>
  <p className="subscriber-preview-counts">Değişiklik beklenen: <strong>{changeCount}</strong> · Atlanması beklenen: <strong>{skipCount}</strong>{rejectCount>0&&<> · Uygulanması beklenmeyen: <strong>{rejectCount}</strong></>}</p>
  <p>Uygulama sırasında abone revizyonları kontrol edilir. Önizlemeden sonra değişen kayıtlar için yeni önizleme gerekir.</p>
  <div className="daily-review">{review.map(card=><SubscriberOperationPreview key={card.id}
   subscriber={card.customer_name} username={card.username} router={card.router} changes={card.changes}
   disposition={card.disposition} outcome={card.outcome}/>)}</div>
  <label className="registry-consent"><input type="checkbox" disabled={busy} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Gösterilen değerleri ve beklenen sonuçları inceledim, işlemi onaylıyorum.</label>
  {!attempted.current&&<div className="subscriber-preview-actions">
   <button className="button-primary" disabled={!confirmed||busy} onClick={()=>void save()}>Onayla ve uygula</button>
   <button className="button-secondary" onClick={()=>{setReview(null);setConfirmed(false);frozen.current=null;}}>Önizlemeyi düzenle</button>
  </div>}
 </>}
 {busy&&<p role="status">İşlem sonucu bekleniyor…</p>}
 {results&&<SubscriberOperationResults results={results} rows={review} routerName={id=>routers.data?.items.find(r=>r.id===id)?.fields.name}>{attempted.current&&!rejected&&uncertain&&<button className="button-secondary" disabled={busy||!confirmed} onClick={()=>void save()}>Aynı UUID ile sonuçları sorgula</button>}</SubscriberOperationResults>}
 {!results&&attempted.current&&<details className="technical-info"><summary>Teknik detaylar</summary><p>İstekler: {frozen.current?.entries.map(e=>e.request_id).join(', ')}</p>{!rejected&&uncertain&&<button className="button-secondary" disabled={busy||!confirmed} onClick={()=>void save()}>Aynı UUID ile sonuçları sorgula</button>}</details>}
 </>}

 {uncertain&&<p role="alert" className="form-error">İşlemin kalıcı sonucu doğrulanamadı. İşlem uygulanmış olabilir; yeniden önizleme oluşturmadan aynı isteğin kayıtlı sonuçlarını getirin.</p>}
 {error&&<p role="alert" className="form-error">{error}</p>}<button className="button-secondary" disabled={busy} onClick={onClose}>Kapat</button></dialog>;
}
const historySources=['legacy','workspace'] as const;
const historyResults=['ALL','SUCCESS','FAILED','SKIPPED'] as const;
const historyOperations=['ALL',...Object.keys(dailyLabels),'PLAN_CHANGE','STATUS_CHANGE','DATE_EDIT'] as const;
export function SubscriberOperationHistory({workspaceOnly=false}:{workspaceOnly?:boolean}={}){
 const [showReport,setShowReport]=useState(false);
 return <>
  <div className="daily-links"><button className="button-secondary" aria-pressed={showReport} onClick={()=>setShowReport(!showReport)}>{showReport?'İşlem geçmişine dön':'Toplu işlem raporu'}</button></div>
  {showReport?<SubscriberOperationReport/>:<SubscriberAuditHistory workspaceOnly={workspaceOnly}/>}
 </>;
}
function SubscriberAuditHistory({workspaceOnly}:{workspaceOnly:boolean}){
 const [pageText,setPageText]=useSubscriberTextFilter('history_page'),[id,setId]=useSubscriberTextFilter('history_id');
 const page=Math.min(1000000,Math.max(1,Math.floor(Number(pageText))||1));
 const setPage=(value:number)=>setPageText(value===1?'':String(value));
 const [result,setResult]=useListFilter('subscribers','history_result',historyResults,'ALL'),[operation,setOperation]=useListFilter('subscribers','history_operation',historyOperations,'ALL'),[selectedSource,setSource]=useListFilter('subscribers','history_source',historySources,'legacy');
 const [group,setGroup]=useSubscriberTextFilter('history_group');
 const source=workspaceOnly?'workspace':selectedSource;
 const activeGroup=source==='workspace'&&/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(group)?group:'';
 function openGroup(id:string){
  setGroup(id);setPage(1);setOperation('ALL');setResult('ALL');setId('');
 }
 const filters=new URLSearchParams({page:String(page),page_size:'25',result:source==='legacy'&&result==='SKIPPED'?'ALL':result,operation,item_id:id.slice(0,64)});
 if(source==='workspace')filters.set('include_skipped','true');
 if(activeGroup)filters.set('group_id',activeGroup);
 const resource=useResource<{items:OperationReportRow[];total:number;is_demo:true}>((source==='legacy'?'/subscribers/demo-history?':'/subscriber-workspace/management/history?')+filters);
 const error=resource.error||(resource.data&&resource.data.is_demo!==true?'Sentetik işlem kaynağı doğrulanamadı; geçmiş gösterilmedi.':undefined);
 const link=(module:'subscribers'|'routers',id:string)=>linkedDetailHash({module,id,...(module==='subscribers'?{workspace:source==='workspace'?'PERSISTENT':'LEGACY'}:{source:source==='workspace'?'MANAGED_DEMO':'DEMO'})},window.location.hash);
 return <section className="panel registry-detail"><h2>Merkezi İşlem Geçmişi · Sentetik</h2>{activeGroup&&<div className="subscriber-preview-actions">
  <strong className="operation-group-id">Grup ayrıntıları · {activeGroup}</strong>
  <button type="button" className="button-secondary" onClick={()=>{setGroup('');setPage(1);}}>Grup filtresini kaldır</button>
 </div>}<div className="inventory-toolbar"><label className="form-label">Kayıt kaynağı<select value={source} onChange={e=>{setSource(e.target.value as typeof source);setPage(1);setOperation("ALL");setResult("ALL");setId("");setGroup("");}}>{!workspaceOnly&&<option value="legacy">Mevcut demo aboneleri</option>}<option value="workspace">Kalıcı sentetik PPPoE / Hotspot</option></select></label><label className="form-label">Abone kayıt kimliği<input maxLength={64} value={id} onChange={e=>{setId(e.target.value);setPage(1);}}/></label><label className="form-label">İşlem<select value={operation} onChange={e=>{setOperation(e.target.value);setPage(1);}}><option value="ALL">Tümü</option>{Object.entries(dailyLabels).filter(([key])=>source==='workspace'||['PLAN','STATUS','EXTEND','CREATE','RENEWAL'].includes(key)).map(([key,label])=><option key={key} value={key}>{label}</option>)}{source==='legacy'&&<><option value="PLAN_CHANGE">Paket / profil (detay işlemi)</option><option value="STATUS_CHANGE">Hesap durumu (detay işlemi)</option><option value="DATE_EDIT">Bitiş tarihi (detay işlemi)</option></>}</select></label><label className="form-label">Sonuç<select value={filters.get('result')??'ALL'} onChange={e=>{setResult(e.target.value as typeof result);setPage(1);}}><option value="ALL">Tümü</option>{Object.entries(operationReportResults).filter(([key])=>source==='workspace'||key!=='SKIPPED').map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Yenile</button></div><ResourceState {...resource} error={error}/>{!resource.loading&&!error&&resource.data&&<><ol className="registry-history">{resource.data.items.map(r=><li key={r.request_id}>
  <strong>{dailyLabels[r.operation]??(r.operation==='PLAN_CHANGE'?'Paket / profil':r.operation==='STATUS_CHANGE'?'Hesap durumu':r.operation)} · {operationReportResult(r)}</strong>
  <SubscriberOperationMetadata row={r} onGroup={source==='workspace'?openGroup:undefined}/>
  <a className="record-link" href={link('subscribers',r.item_id)}>{r.subscriber_name? `${r.subscriber_name}${r.subscriber_username?` · ${r.subscriber_username}`:''}`:'Abone detayını aç'}</a>
  {r.skipped&&<span>Hesap zaten hedef durumdaydı.</span>}
  {r.recorded&&!r.success&&r.error&&<span>{subscriberOperationConflict(r.error)??r.error}</span>}
  <SubscriberOperationValues row={r}/>
  {source==='workspace'&&<SubscriberUndoPreview requestId={r.request_id} itemId={r.item_id}/>}
  <details className="technical-info"><summary>Teknik detaylar</summary>
   <span>Abone: {r.item_id} · Aktör: {r.actor_id}</span>
   <span>Router: {r.router_id?<a className="record-link" href={link('routers',r.router_id)}>{r.router_id}</a>:'Bilinmiyor'}</span>
   <span>Kaynak: <SourceBadge source={r.source??null}/> · UUID: {r.request_id} · Revizyon: {r.revision}</span>
   {r.error&&<span>{r.error}</span>}
  </details>
 </li>)}</ol>{!resource.data.items.length&&<p>{resource.data.total?'Bu sayfada işlem yok. Önceki sayfaya dönün.':'Bu filtrede kayıtlı işlem yok.'}</p>}<div className="table-footer"><span>{resource.data.total} işlem</span><button disabled={page===1} onClick={()=>setPage(page-1)}>Önceki</button><span>{page}</span><button disabled={page*25>=resource.data.total} onClick={()=>setPage(page+1)}>Sonraki</button></div></>}</section>;
}
