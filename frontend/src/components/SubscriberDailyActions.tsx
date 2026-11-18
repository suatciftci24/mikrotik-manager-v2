import {SubscriberOperationResults} from './SubscriberOperationResults';
import {SubscriberOperationPreview} from './SubscriberOperationPreview';
import {loadPackageChoices,selectablePackage,packageSpeed,type PackageRecord} from '../lib/packages';
import {loadWorkspaceRouterChoices} from '../lib/workspaceDashboard';
import {useIdentity} from '../lib/permissions';
import {changedHistoryValues,historyActor,valuesText} from '../lib/subscriberHistory';
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
import {dailyEntries,dailyLabels,maxDailyExtensionDays,previousDailyValue,type DailyAction,type DailyEntry,type OperationReceipt} from '../lib/subscriberManagementCenter';
import type {CenterSubscriber} from '../lib/subscriberCenter';
import {ResourceState,dateTime} from './Resource';
import {expiryDate} from '../lib/expiry';
export function SubscriberDailyActions({rows,onClose,initialAction='EXTEND',fixedAction}:{rows:CenterSubscriber[];onClose:()=>void;initialAction?:DailyAction;fixedAction?:DailyAction}){
 const identity=useIdentity();const centralAdmin=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
 const catalog=useResource<{items:PackageRecord[]}>('/packages',loadPackageChoices,['/packages']);
 const [packageId,setPackageId]=useState('');
 const activePackages=catalog.data?.items.filter(selectablePackage)??[];
 const dialog=useRef<HTMLDialogElement>(null),sending=useRef(false),attempted=useRef(false),frozen=useRef<{entries:DailyEntry[];body:string;package?:PackageRecord['fields']}|null>(null);const today=useTurkeyToday();
 const entryAction=useRef(fixedAction),entryStatus=useRef(rows[0]?.status);
 const [selectedAction,setAction]=useState<DailyAction>(entryAction.current??initialAction),[duration,setDuration]=useState('30'),[customDays,setCustomDays]=useState(''),[value,setValue]=useState((entryAction.current??initialAction)==='STATUS'&&rows.length===1?nextAccountStatus(rows[0].status):''),[review,setReview]=useState<DailyEntry[]|null>(null),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[results,setResults]=useState<OperationReceipt[]|null>(null),[uncertain,setUncertain]=useState(false),[rejected,setRejected]=useState(false);
 const action=entryAction.current??selectedAction;
 const days=Number(duration==='CUSTOM'?customDays:duration);
 const title=entryAction.current==='PLAN'?'Paket Değiştir':entryAction.current==='STATUS'?accountActionLabel(entryStatus.current??''):entryAction.current==='EXTEND'?'Abonelik Uzat':entryAction.current?dailyLabels[entryAction.current]:'Abone işlemi';
 const routers=useResource<{items:{id:string;fields:{name:string}}[]}>('/router-workspace/routers?page_size=100',loadWorkspaceRouterChoices,['/router-workspace/routers']);
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};},[]);
 function prepare(event:FormEvent){event.preventDefault();setError('');try{
  if(entryAction.current&&rows.length!==1)throw new Error('Bu işlem girişi yalnız bir abone için kullanılabilir.');
  const selected=action==='PLAN'?activePackages.find(row=>row.id===packageId):undefined;
  if(action==='PLAN'&&(catalog.loading||catalog.error||!selected))throw new Error('Kayıtlı aktif paket seçin.');
  const entries=dailyEntries(rows,action,selected?.fields.name??value,days,today,()=>crypto.randomUUID(),selected?{package_id:selected.id,package_revision:selected.revision}:undefined);
  frozen.current={entries,body:JSON.stringify({entries}),package:selected?{...selected.fields}:undefined};attempted.current=false;
  setReview(entries);setConfirmed(false);setResults(null);setUncertain(false);setRejected(false);
 }catch(e){setError(e instanceof Error?e.message:'Alanları kontrol edin.');}}
 async function save(){
  if(!frozen.current||!confirmed||sending.current||rejected||results?.every(r=>r.recorded))return;
  const command=frozen.current,query=attempted.current;attempted.current=true;
  sending.current=true;setBusy(true);setError('');
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try{
   let receipts:OperationReceipt[];
   if(query)receipts=await readOperationResults(command.entries,results??[],controller.signal);
   else{
    for(const entry of command.entries)rememberPending(entry.request_id,'/subscriber-workspace/management/requests/'+entry.request_id);
    const data=await api<{results:OperationReceipt[]}>('/subscriber-workspace/management/execute',{method:'POST',signal:controller.signal,headers:{'X-V2-Demo-Action':'subscriber-workspace'},body:command.body});
    if(!Array.isArray(data?.results)||data.results.length!==command.entries.length||new Set(data.results.map(r=>r?.request_id)).size!==command.entries.length||data.results.some(r=>!command.entries.some(e=>operationReceiptMatches(e,r))))throw new Error('İşlem sonuçları onaylanan kayıtlarla eşleşmedi.');
    receipts=data.results;
   }
   for(const receipt of receipts)if(receipt.recorded)forgetPending(receipt.request_id);
   setResults(receipts);setUncertain(receipts.some(r=>!r.recorded));
  }catch(e){
   const failed=!query&&e instanceof ApiError&&[400,401,403,404,409,422].includes(e.status);
   if(failed)for(const entry of command.entries)forgetPending(entry.request_id);
   setRejected(failed);setUncertain(!failed);
   if(!failed)setResults(command.entries.map(entry=>results?.find(r=>r.recorded&&operationReceiptMatches(entry,r))??unknownOperation(entry)));
   setError(subscriberOperationError(e));
  }finally{clearTimeout(timer);sending.current=false;setBusy(false);invalidateResources([...subscriberSaveDependencies]);}
 }
 const display=(v:string|null)=>action==='EXTEND'||action==='EXPIRE'?expiryDate(v):action==='STATUS'?(v==='ACTIVE'?'Aktif hesap':v==='PAUSED'?'Pasif hesap':'Bilinmiyor'):action==='ROUTER'?`${routers.data?.items.find(r=>r.id===v)?.fields.name??rows.find(r=>r.router_id===v)?.router_name??'Ad bilinmiyor'} · ${v}`:v??'Bilinmiyor';
 return <dialog ref={dialog} className={'expiry-dialog router-onboarding'+(entryAction.current?' fixed-subscriber-operation':'')} aria-busy={busy} aria-labelledby="daily-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}><h2 id="daily-title">{title} · SENTETİK</h2><p>{rows.length} seçili abone · Yalnız sentetik kayıt ve audit değişir. Her abone için sonuç ayrı doğrulanır.</p>
 <details><summary>Seçilen aboneler ({rows.length})</summary><ul>{rows.map(row=><li key={row.id}>{row.customer_name} · {row.username} · {row.access_type} · {row.router_name}</li>)}</ul></details>
 {!review?<form onSubmit={prepare}>{action==='PLAN'&&<><ResourceState {...catalog}/><label className="form-label">Kayıtlı yeni paket<select required value={packageId} disabled={catalog.loading||!!catalog.error} onChange={e=>{const selected=activePackages.find(row=>row.id===e.target.value);setPackageId(selected?.id??'');setValue(selected?.fields.name??'');}}><option value="">Kayıtlı aktif paket seçin</option>{activePackages.map(row=><option key={row.id} value={row.id}>{row.fields.name} · {packageSpeed(row.fields)}</option>)}</select></label>{!catalog.loading&&!catalog.error&&!activePackages.length&&<p>Atanabilecek aktif paket yok. Paket Yönetimi’nden paket ekleyin.</p>}{rows.length===1&&<div className="package-choice-summary"><p>Mevcut paket: <strong>{rows[0].plan}</strong> · {packageSpeed(rows[0].package_snapshot)}</p><p>Yeni paket: <strong>{activePackages.find(row=>row.id===packageId)?.fields.name??'Paket seçilmedi'}</strong> · {packageSpeed(activePackages.find(row=>row.id===packageId)?.fields)}</p></div>}</>}{!entryAction.current&&<label className="form-label">İşlem<select value={action} onChange={e=>{setAction(e.target.value as DailyAction);setValue(e.target.value==='STATUS'&&rows.length===1?nextAccountStatus(rows[0].status):'');}}><option value="EXTEND">Abonelik uzatma</option><option value="STATUS">Etkinleştirme / devre dışı bırakma</option>{rows.length===1&&<><option value="EDIT">Abone bilgisini düzenle</option><option value="PLAN">Paket / profil değiştir</option><option value="EXPIRE">Bitiş tarihi belirle</option>{centralAdmin&&<option value="ROUTER">Bağlı routerı değiştir</option>}</>}</select></label>}
 {action==='EXTEND'?<><label className="form-label">Süre<select value={duration} onChange={e=>setDuration(e.target.value)}>{[30,60,90].map(d=><option key={d} value={d}>{d} gün</option>)}<option value="CUSTOM">Özel gün sayısı</option></select></label>{duration==='CUSTOM'&&<label className="form-label">Uzatma süresi (gün)<input type="number" inputMode="numeric" required min={1} max={maxDailyExtensionDays} step={1} value={customDays} onChange={e=>setCustomDays(e.target.value)}/></label>}</>:action==='STATUS'&&entryAction.current?<p>Yeni hesap durumu: <strong>{value==='ACTIVE'?'Aktif hesap':'Pasif hesap'}</strong></p>:action==='STATUS'?<label className="form-label">Yeni hesap durumu<select required value={value} onChange={e=>setValue(e.target.value)}><option value="">Seçin</option><option value="ACTIVE">Aktif hesap</option><option value="PAUSED">Pasif hesap</option></select></label>:action==='ROUTER'?<><ResourceState {...routers}/><label className="form-label">Hedef sentetik router<select required value={value} onChange={e=>setValue(e.target.value)}><option value="">Seçin</option>{routers.data?.items.map(r=><option key={r.id} value={r.id}>{r.fields.name} · {r.id}</option>)}</select></label></>:action==='PLAN'?null:<label className="form-label">{dailyLabels[action]}<input required={action!=='EXPIRE'} type={action==='EXPIRE'?'date':'text'} maxLength={160} value={value} onChange={e=>setValue(e.target.value)}/>{action==='EXPIRE'&&<small>Boş bırakılırsa tarih bilinmiyor olarak kaydedilir; hesap pasifleştirilmez.</small>}</label>}
 <button className="button-primary">Önizle ve gözden geçir</button></form>:<>{!results&&!rejected&&<><h3>{dailyLabels[action]}{action==='EXTEND'?` · ${days} gün`:''} · {rows.length} abone etkilenecek</h3>{!attempted.current&&<button className="button-secondary" onClick={()=>{setReview(null);setConfirmed(false);frozen.current=null;}}>Önizlemeyi düzenle</button>}<div className="daily-review">{review.map(entry=>{const row=rows.find(r=>r.id===entry.item_id)!;return <SubscriberOperationPreview key={entry.item_id} subscriber={row.customer_name} username={row.username} router={row.router_name??'Bilinmiyor'} changes={[{label:action==='EXTEND'?'Bitiş tarihi':dailyLabels[action],previous:display(action==='EXTEND'?entry.expected_expires_on:previousDailyValue(row,action)),next:display(entry.value)},...(action==='PLAN'?[{label:'Hız',previous:packageSpeed(row.package_snapshot),next:packageSpeed(frozen.current?.package)}]:[])]} outcome={action==='STATUS'?'Hesap durumu değişecek; abonelik bitişi korunacak.':action==='PLAN'?'Paket değişecek; abonelik bitişi korunacak.':'Yalnız önizlenen alan ve audit kaydı değişecek.'}/>;})}</div><label className="registry-consent"><input type="checkbox" disabled={busy} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Gösterilen {rows.length} sentetik kayıt için önceki/yeni değerleri inceledim ve onaylıyorum.</label>{!attempted.current&&<button className="button-primary" disabled={!confirmed||busy} onClick={()=>void save()}>Onayla ve uygula</button>}</>}{busy&&<p role="status">İşlem sonucu bekleniyor…</p>}{results&&<SubscriberOperationResults results={results} rows={rows} routerName={id=>routers.data?.items.find(r=>r.id===id)?.fields.name}>{attempted.current&&!rejected&&uncertain&&<button className="button-secondary" disabled={busy||!confirmed} onClick={()=>void save()}>Aynı UUID ile sonuçları sorgula</button>}</SubscriberOperationResults>}{!results&&attempted.current&&<details className="technical-info"><summary>Teknik detaylar</summary><p>İstekler: {frozen.current?.entries.map(e=>e.request_id).join(', ')}</p>{!rejected&&uncertain&&<button className="button-secondary" disabled={busy||!confirmed} onClick={()=>void save()}>Aynı UUID ile sonuçları sorgula</button>}</details>}</>}

 {rejected&&<p role="alert" className="form-error">İşlem isteği reddedildi. Güncel kayıtlardan yeni önizleme oluşturun.</p>}
 {uncertain&&<p role="alert" className="form-error">İşlemin kalıcı sonucu doğrulanamadı. İşlem uygulanmış olabilir; yeniden önizleme oluşturmadan aynı isteğin kayıtlı sonuçlarını getirin.</p>}
 {error&&<p role="alert" className="form-error">{error}</p>}<button className="button-secondary" disabled={busy} onClick={onClose}>Kapat</button></dialog>;
}
const historySources=['legacy','workspace'] as const;
const historyResults=['ALL','SUCCESS','FAILED'] as const;
const historyOperations=['ALL',...Object.keys(dailyLabels),'PLAN_CHANGE','STATUS_CHANGE','DATE_EDIT'] as const;
export function SubscriberOperationHistory({workspaceOnly=false}:{workspaceOnly?:boolean}={}){
 const [pageText,setPageText]=useSubscriberTextFilter('history_page'),[id,setId]=useSubscriberTextFilter('history_id');
 const page=Math.min(1000000,Math.max(1,Math.floor(Number(pageText))||1));
 const setPage=(value:number)=>setPageText(value===1?'':String(value));
 const [result,setResult]=useListFilter('subscribers','history_result',historyResults,'ALL'),[operation,setOperation]=useListFilter('subscribers','history_operation',historyOperations,'ALL'),[selectedSource,setSource]=useListFilter('subscribers','history_source',historySources,'legacy');
 const source=workspaceOnly?'workspace':selectedSource;
 const resource=useResource<{items:OperationReceipt[];total:number;is_demo:true}>((source==='legacy'?'/subscribers/demo-history?':'/subscriber-workspace/management/history?')+new URLSearchParams({page:String(page),page_size:'25',result,operation,item_id:id.slice(0,64)}));
 const error=resource.error||(resource.data&&resource.data.is_demo!==true?'Sentetik işlem kaynağı doğrulanamadı; geçmiş gösterilmedi.':undefined);
 const link=(module:'subscribers'|'routers',id:string)=>linkedDetailHash({module,id,...(module==='subscribers'?{workspace:source==='workspace'?'PERSISTENT':'LEGACY'}:{source:source==='workspace'?'MANAGED_DEMO':'DEMO'})},window.location.hash);
 return <section className="panel registry-detail"><h2>Merkezi İşlem Geçmişi · Sentetik</h2><div className="inventory-toolbar"><label className="form-label">Kayıt kaynağı<select value={source} onChange={e=>{setSource(e.target.value as typeof source);setPage(1);setOperation("ALL");setId("");}}>{!workspaceOnly&&<option value="legacy">Mevcut demo aboneleri</option>}<option value="workspace">Kalıcı sentetik PPPoE / Hotspot</option></select></label><label className="form-label">Abone kayıt kimliği<input maxLength={64} value={id} onChange={e=>{setId(e.target.value);setPage(1);}}/></label><label className="form-label">İşlem<select value={operation} onChange={e=>{setOperation(e.target.value);setPage(1);}}><option value="ALL">Tümü</option>{Object.entries(dailyLabels).filter(([key])=>source==='workspace'||['PLAN','STATUS','EXTEND','CREATE','RENEWAL'].includes(key)).map(([key,label])=><option key={key} value={key}>{label}</option>)}{source==='legacy'&&<><option value="PLAN_CHANGE">Paket / profil (detay işlemi)</option><option value="STATUS_CHANGE">Hesap durumu (detay işlemi)</option><option value="DATE_EDIT">Bitiş tarihi (detay işlemi)</option></>}</select></label><label className="form-label">Sonuç<select value={result} onChange={e=>{setResult(e.target.value as typeof result);setPage(1);}}><option value="ALL">Tümü</option><option value="SUCCESS">Başarılı</option><option value="FAILED">Başarısız</option></select></label><button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Yenile</button></div><ResourceState {...resource} error={error}/>{!resource.loading&&!error&&resource.data&&<><ol className="registry-history">{resource.data.items.map(r=><li key={r.request_id}><strong>{dailyLabels[r.operation]??(r.operation==='PLAN_CHANGE'?'Paket / profil':r.operation==='STATUS_CHANGE'?'Hesap durumu':r.operation)} · {r.success?'Uygulandı':'Başarısız'}</strong><span>{dateTime(r.occurred_at)} · {historyActor(r)}</span><a className="record-link" href={link('subscribers',r.item_id)}>Abone detayını aç</a>{r.success&&<ul aria-label="Değişen alanlar">{changedHistoryValues({previous_values:r.previous,new_values:r.values}).map(change=><li key={change.key}>{change.label}: {change.previous} → {change.next}</li>)}</ul>}<details className="technical-info"><summary>Teknik detaylar</summary><span>Abone: {r.item_id} · Aktör: {r.actor_id}</span><span>Router: {r.router_id?<a className="record-link" href={link('routers',r.router_id)}>{r.router_id}</a>:'Bilinmiyor'}</span><span>Kaynak: <SourceBadge source={r.source??null}/> · UUID: {r.request_id} · Revizyon: {r.revision}</span><span>Eski: {valuesText(r.previous)} → Yeni: {r.success?valuesText(r.values):'Uygulanmadı'}</span>{r.error&&<span>{r.error}</span>}</details></li>)}</ol>{!resource.data.items.length&&<p>{resource.data.total?'Bu sayfada işlem yok. Önceki sayfaya dönün.':'Bu filtrede kayıtlı işlem yok.'}</p>}<div className="table-footer"><span>{resource.data.total} işlem</span><button disabled={page===1} onClick={()=>setPage(page-1)}>Önceki</button><span>{page}</span><button disabled={page*25>=resource.data.total} onClick={()=>setPage(page+1)}>Sonraki</button></div></>}</section>;
}
