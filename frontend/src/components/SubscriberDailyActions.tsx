import {valuesText} from '../lib/subscriberHistory';
import {SourceBadge} from './Status';
import {nextAccountStatus} from '../lib/subscriberActions';
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
import {dailyEntries,dailyLabels,previousDailyValue,type DailyAction,type DailyEntry,type OperationReceipt} from '../lib/subscriberManagementCenter';
import type {CenterSubscriber} from '../lib/subscriberCenter';
import {ResourceState,dateTime} from './Resource';
import {expiryDate} from '../lib/expiry';
export function SubscriberDailyActions({rows,onClose,initialAction='EXTEND'}:{rows:CenterSubscriber[];onClose:()=>void;initialAction?:DailyAction}){
 const dialog=useRef<HTMLDialogElement>(null),sending=useRef(false),attempted=useRef(false),frozen=useRef<{entries:DailyEntry[];body:string}|null>(null);const today=useTurkeyToday();
 const [action,setAction]=useState<DailyAction>(initialAction),[days,setDays]=useState<30|60|90>(30),[value,setValue]=useState(initialAction==='STATUS'&&rows.length===1?nextAccountStatus(rows[0].status):''),[review,setReview]=useState<DailyEntry[]|null>(null),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[results,setResults]=useState<OperationReceipt[]|null>(null),[uncertain,setUncertain]=useState(false),[rejected,setRejected]=useState(false);
 const routers=useResource<{items:{id:string;fields:{name:string}}[]}>('/router-workspace/routers?page_size=100');
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();if(origin?.isConnected)origin.focus({preventScroll:true});};},[]);
 function prepare(event:FormEvent){event.preventDefault();setError('');try{
  const entries=dailyEntries(rows,action,value,days,today,()=>crypto.randomUUID());
  frozen.current={entries,body:JSON.stringify({entries})};attempted.current=false;
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
 return <dialog ref={dialog} className="expiry-dialog router-onboarding" aria-busy={busy} aria-labelledby="daily-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}><h2 id="daily-title">Günlük PPPoE / Hotspot işlemleri · SENTETİK</h2><p>{rows.length} seçili abone. Yalnız izole V2 kayıtları ve audit değişir. Hesap durumu, oturum ve abonelik süresi ayrıdır. Her abonenin kaydı ve audit’i birlikte kaydedilir; toplu işlemde diğer abonelerden bağımsız sonuç oluşabilir.</p>
 <details><summary>Seçilen aboneler ({rows.length})</summary><ul>{rows.map(row=><li key={row.id}>{row.customer_name} · {row.username} · {row.access_type} · {row.router_name}</li>)}</ul></details>
 {!review?<form onSubmit={prepare}>{rows.length===1&&action==='PLAN'&&<div className="quick-preview"><p>Mevcut paket: <strong>{rows[0].plan}</strong></p><p>Yeni paket: {value||'Paket seçilmedi'}</p></div>}<label className="form-label">İşlem<select value={action} onChange={e=>{setAction(e.target.value as DailyAction);setValue(e.target.value==='STATUS'&&rows.length===1?nextAccountStatus(rows[0].status):'');}}><option value="EXTEND">Abonelik uzatma</option><option value="STATUS">Etkinleştirme / devre dışı bırakma</option>{rows.length===1&&<><option value="EDIT">Abone bilgisini düzenle</option><option value="PLAN">Paket / profil değiştir</option><option value="EXPIRE">Bitiş tarihi belirle</option><option value="ROUTER">Bağlı routerı değiştir</option></>}</select></label>
 {action==='EXTEND'?<label className="form-label">Süre<select value={days} onChange={e=>setDays(Number(e.target.value) as 30|60|90)}>{[30,60,90].map(d=><option key={d} value={d}>{d} gün</option>)}</select></label>:action==='STATUS'?<label className="form-label">Yeni hesap durumu<select required value={value} onChange={e=>setValue(e.target.value)}><option value="">Seçin</option><option value="ACTIVE">Aktif hesap</option><option value="PAUSED">Pasif hesap</option></select></label>:action==='ROUTER'?<><ResourceState {...routers}/><label className="form-label">Hedef sentetik router<select required value={value} onChange={e=>setValue(e.target.value)}><option value="">Seçin</option>{routers.data?.items.map(r=><option key={r.id} value={r.id}>{r.fields.name} · {r.id}</option>)}</select></label></>:<label className="form-label">{dailyLabels[action]}<input required={action!=='EXPIRE'} type={action==='EXPIRE'?'date':'text'} maxLength={action==='PLAN'?120:160} value={value} onChange={e=>setValue(e.target.value)}/>{action==='EXPIRE'&&<small>Boş bırakılırsa tarih bilinmiyor olarak kaydedilir; hesap pasifleştirilmez.</small>}</label>}
 <button className="button-primary">Önizle ve gözden geçir</button></form>:<><h3>{dailyLabels[action]}{action==='EXTEND'?` · ${days} gün`:''} · {rows.length} abone etkilenecek</h3><div className="daily-review">{review.map(entry=>{const row=rows.find(r=>r.id===entry.item_id)!;return <div className="quick-preview" key={entry.item_id}><strong>{row.customer_name} · {row.username} · {row.access_type}</strong><p>Router: {row.router_name} · {row.router_id} · Kaynak: {row.source}</p><p>Eski: {display(previousDailyValue(row,action))} → Yeni: {display(entry.value)}</p></div>;})}</div><label className="registry-consent"><input type="checkbox" disabled={busy} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Gösterilen {rows.length} sentetik kayıt için önceki/yeni değerleri inceledim ve onaylıyorum.</label><button className="button-primary" disabled={!confirmed||busy||rejected||!!results?.every(r=>r.recorded)} onClick={()=>void save()}>{busy?'İşleniyor…':results||uncertain?'Aynı UUID ile sonuçları sorgula':'Onayla ve uygula'}</button><p>Sonuç sorgusu yalnız kayıtlı receipt'leri okur; yeni işlem başlatmaz. Kayıtlı başarısız bir işlem için pencereyi kapatıp güncel kayıttan yeni önizleme oluşturun.</p></>}
 {results&&<div aria-live="polite"><h3>Başarılı: {results.filter(r=>r.success).length}</h3>{results.filter(r=>r.success).map(r=><p key={r.request_id}>{rows.find(i=>i.id===r.item_id)?.username} · Kaydedildi · {Object.values(r.values).join(' / ')||'Bilinmiyor'} · {dateTime(r.occurred_at)}</p>)}<h3>Başarısız: {results.filter(r=>!r.success&&r.recorded).length}</h3>{results.filter(r=>!r.success&&r.recorded).map(r=><p role="alert" key={r.request_id}>{rows.find(i=>i.id===r.item_id)?.username}: {r.error} {r.recorded?'Başarısız sonuç audit’e kaydedildi.':'Sonuç kalıcı kayda alınamadı.'}</p>)}{results.some(r=>!r.recorded)&&<><h3>Sonucu doğrulanamayan: {results.filter(r=>!r.recorded).length}</h3>{results.filter(r=>!r.recorded).map(r=><p role="alert" key={r.request_id}>{rows.find(i=>i.id===r.item_id)?.username}: {r.error} İşlemin kalıcı sonucu doğrulanamadı; aynı istek kimliğiyle sonucu alın.</p>)}</>}</div>}
 {rejected&&<p role="alert" className="form-error">İşlem isteği reddedildi. Güncel kayıtlardan yeni önizleme oluşturun.</p>}
 {uncertain&&<p role="alert" className="form-error">İşlemin kalıcı sonucu doğrulanamadı. İşlem uygulanmış olabilir; yeniden önizleme oluşturmadan aynı isteğin kayıtlı sonuçlarını getirin.</p>}
 {error&&<p role="alert" className="form-error">{error}</p>}<button className="button-secondary" disabled={busy} onClick={onClose}>Kapat</button></dialog>;
}
const historySources=['legacy','workspace'] as const;
const historyResults=['ALL','SUCCESS','FAILED'] as const;
const historyOperations=['ALL',...Object.keys(dailyLabels),'PLAN_CHANGE','STATUS_CHANGE','DATE_EDIT'] as const;
export function SubscriberOperationHistory(){
 const [pageText,setPageText]=useSubscriberTextFilter('history_page'),[id,setId]=useSubscriberTextFilter('history_id');
 const page=Math.min(1000000,Math.max(1,Math.floor(Number(pageText))||1));
 const setPage=(value:number)=>setPageText(value===1?'':String(value));
 const [result,setResult]=useListFilter('subscribers','history_result',historyResults,'ALL'),[operation,setOperation]=useListFilter('subscribers','history_operation',historyOperations,'ALL'),[source,setSource]=useListFilter('subscribers','history_source',historySources,'legacy');
 const resource=useResource<{items:OperationReceipt[];total:number;is_demo:true}>((source==='legacy'?'/subscribers/demo-history?':'/subscriber-workspace/management/history?')+new URLSearchParams({page:String(page),page_size:'25',result,operation,item_id:id.slice(0,64)}));
 const error=resource.error||(resource.data&&resource.data.is_demo!==true?'Sentetik işlem kaynağı doğrulanamadı; geçmiş gösterilmedi.':undefined);
 const link=(module:'subscribers'|'routers',id:string)=>linkedDetailHash({module,id,...(module==='subscribers'?{workspace:source==='workspace'?'PERSISTENT':'LEGACY'}:{source:source==='workspace'?'MANAGED_DEMO':'DEMO'})},window.location.hash);
 return <section className="panel registry-detail"><h2>Merkezi İşlem Geçmişi · Sentetik</h2><div className="inventory-toolbar"><label className="form-label">Kayıt kaynağı<select value={source} onChange={e=>{setSource(e.target.value as typeof source);setPage(1);setOperation("ALL");setId("");}}><option value="legacy">Mevcut demo aboneleri</option><option value="workspace">Kalıcı sentetik PPPoE / Hotspot</option></select></label><label className="form-label">Abone kayıt kimliği<input maxLength={64} value={id} onChange={e=>{setId(e.target.value);setPage(1);}}/></label><label className="form-label">İşlem<select value={operation} onChange={e=>{setOperation(e.target.value);setPage(1);}}><option value="ALL">Tümü</option>{Object.entries(dailyLabels).filter(([key])=>source==='workspace'||['PLAN','STATUS','EXTEND','CREATE','RENEWAL'].includes(key)).map(([key,label])=><option key={key} value={key}>{label}</option>)}{source==='legacy'&&<><option value="PLAN_CHANGE">Paket / profil (detay işlemi)</option><option value="STATUS_CHANGE">Hesap durumu (detay işlemi)</option><option value="DATE_EDIT">Bitiş tarihi (detay işlemi)</option></>}</select></label><label className="form-label">Sonuç<select value={result} onChange={e=>{setResult(e.target.value as typeof result);setPage(1);}}><option value="ALL">Tümü</option><option value="SUCCESS">Başarılı</option><option value="FAILED">Başarısız</option></select></label><button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Yenile</button></div><ResourceState {...resource} error={error}/>{!resource.loading&&!error&&resource.data&&<><ol className="registry-history">{resource.data.items.map(r=><li key={r.request_id}><strong>{dailyLabels[r.operation]??(r.operation==='PLAN_CHANGE'?'Paket / profil':r.operation==='STATUS_CHANGE'?'Hesap durumu':r.operation)} · {r.success?'Uygulandı':'Başarısız'}</strong><span>Abone: <a className="record-link" href={link('subscribers',r.item_id)}>{r.item_id}</a> · Router: {r.router_id?<a className="record-link" href={link('routers',r.router_id)}>{r.router_id}</a>:'Bilinmiyor'}</span><span>Kaynak: <SourceBadge source={r.source??null}/> · UUID: {r.request_id} · Revizyon: {r.revision}</span><span>Eski: {valuesText(r.previous)} → Yeni: {r.success?valuesText(r.values):'Uygulanmadı'}</span><span>{dateTime(r.occurred_at)} · {r.actor_id}</span>{r.error&&<span>{r.error}</span>}</li>)}</ol>{!resource.data.items.length&&<p>{resource.data.total?'Bu sayfada işlem yok. Önceki sayfaya dönün.':'Bu filtrede kayıtlı işlem yok.'}</p>}<div className="table-footer"><span>{resource.data.total} işlem</span><button disabled={page===1} onClick={()=>setPage(page-1)}>Önceki</button><span>{page}</span><button disabled={page*25>=resource.data.total} onClick={()=>setPage(page+1)}>Sonraki</button></div></>}</section>;
}
