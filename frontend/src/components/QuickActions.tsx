import {subscriberOperationError} from '../lib/subscriberOperationRecovery';
import {subscriberSaveDependencies} from '../lib/subscriberDependencies';
import '../styles/subscriber-edit-highlight.css';
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { api, type Router, type Subscriber, type DemoOptions, type SubscriberDetailData } from '../lib/api';
import { useResource } from '../lib/useResource';
import { invalidateResources } from '../lib/resourceEvents';
import { extensionDate } from '../lib/quick';
import { expiryDate } from '../lib/expiry';

export type QuickAction = 'EXTEND'|'PLAN'|'STATUS'|'CREATE';
type Entry = {item_id:string; change:Record<string,unknown>};
type Result = {item_id:string; success:boolean; error?:string; result?:SubscriberDetailData};
export function QuickActions({rows,today,onClose,initialAction,onSaved}: {rows:Subscriber[];today:string;onClose:()=>void;initialAction?:QuickAction;onSaved?:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null),expected=useRef(new Map<string,Partial<Subscriber>>()),activeRequest=useRef<AbortController|null>(null);
  const fieldId=useId();
  const options=useResource<DemoOptions>('/subscribers/demo-options');
  const routers=useResource<{items:Router[]}>('/routers');
  const [action,setAction]=useState<QuickAction>(initialAction??(rows.length?'EXTEND':'CREATE'));
  const [days,setDays]=useState('30'); const [custom,setCustom]=useState('');
  const [plan,setPlan]=useState(''); const [status,setStatus]=useState('ACTIVE');
  const [router,setRouter]=useState(rows[0]?.router_name??'');
  const [source,setSource]=useState('LOCAL'); const [username,setUsername]=useState(''); const [name,setName]=useState('');
  const [review,setReview]=useState<Entry[]|null>(null); const [results,setResults]=useState<Result[]|null>(null);
  const [error,setError]=useState(''); const [pending,setPending]=useState(false); const [attempted,setAttempted]=useState(false); const sending=useRef(false);
  useEffect(()=>{const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{activeRequest.current?.abort();node?.close();if(origin?.isConnected)origin.focus({preventScroll:true});else document.querySelector<HTMLElement>('.detail-back')?.focus();};},[]);
  useEffect(()=>{if(review)dialog.current?.querySelector<HTMLElement>('h2')?.focus();},[review]);
  function prepare(e:FormEvent) {
    e.preventDefault(); setError('');
    if (rows.some(r=>r.is_demo!==true || r.can_manage_pppoe!==true || !['LOCAL','RADIUS'].includes(r.source??''))) {setError('Yalnız kaynağı bilinen sentetik demo aboneleri seçin.');return;}
    if (new Set(rows.map(r=>r.router_name)).size>1) {setError('Toplu işlem için aynı router üzerindeki aboneleri seçin.');return;}
    if (!routers.data || routers.error) {setError('Router kimliği doğrulanamadı; pencereyi yeniden açın.');return;}
    const routerItems=routers.data.items;
    const targets=rows.length?rows:[null];
    const entries=targets.map(row=>{
      const id=crypto.randomUUID();
      const expires=action==='CREATE'?custom:action==='EXTEND'?(days==='CUSTOM'?custom:extensionDate(row!.expires_on,today,Number(days))):row!.expires_on;
      return {item_id:row?.id??`demo-sub-${id}`,change:{action,request_id:id,confirmed:true,expected_revision:row?.revision??0,
        expected_source:row?.source??source,expected_expires_on:row?.expires_on??null,expires_on:expires,
        router_id:row?.router_id?(routerItems.find(r=>r.id===row.router_id)?.id??''):(routerItems.filter(r=>r.name===(row?.router_name??router)).length===1?routerItems.find(r=>r.name===(row?.router_name??router))!.id:''),
        days:action==='EXTEND'&&days!=='CUSTOM'?Number(days):null,plan,status,router_name:row?.router_name??router,username,customer_name:name}};
    });
    if (entries.some(e=>(action==='EXTEND'||action==='CREATE')&&(!e.change.expires_on||e.change.expires_on<today))) {setError('Geçerli bitiş tarihi seçin. Bilinmeyen bitiş için özel tarih kullanın.');return;}
    if (action==='CREATE'&&(!router||!username.trim()||!name.trim()||!plan.trim())) {setError('Router, kullanıcı, abone adı ve paket zorunlu.');return;}
    if (action==='PLAN'&&!plan.trim()) {setError('Yeni paket girin.');return;}
    if(entries.some(e=>!e.change.router_id)) {setError('Router kimliği bulunamadı.');return;}
    const selectedPlan=options.data?.plans.find(p=>p.name===plan);
    if((action==='PLAN'||action==='CREATE')&&!selectedPlan){setError('Kayıtlı bir demo paketi seçin; paket bilgisi alınamadıysa yeniden deneyin.');return;}
    expected.current=new Map(entries.map((entry,index)=>{
      const row=targets[index];
      const values:Partial<Subscriber>={id:entry.item_id,is_demo:true,revision:(row?.revision??0)+1,router_id:String(entry.change.router_id),source:row?.source??source as Subscriber['source'],customer_name:row?.customer_name??name.trim(),username:row?.username??username.trim(),plan:row?.plan??plan,monthly_price:row?row.monthly_price:selectedPlan!.monthly_price,status:row?.status??status as Subscriber['status'],expires_on:row?.expires_on??null};
      if(action==='EXTEND'||action==='CREATE')values.expires_on=entry.change.expires_on as string;
      if(action==='PLAN'||action==='CREATE'){values.plan=plan;values.monthly_price=selectedPlan!.monthly_price;}
      if(action==='STATUS'||action==='CREATE')values.status=status as Subscriber['status'];
      return [entry.item_id,values];
    }));
    setReview(entries);setResults(null);
  }
  async function save() {
    if (!review||sending.current||results?.every(result=>result.success)) return;
    sending.current=true;setPending(true);setAttempted(true);setError('');
    const controller=new AbortController();activeRequest.current=controller;
    const timer=setTimeout(()=>controller.abort(),15000);
    try {
      const response=await api<{results:Result[]}>('/subscribers/demo-quick',{method:'POST',signal:controller.signal,headers:{'X-V2-Demo-Action':'expiry'},body:JSON.stringify({entries:review})});
      if(!Array.isArray(response?.results)||response.results.length!==review.length||new Set(response.results.map(r=>r?.item_id)).size!==review.length||response.results.some(r=>{
        if(!r||!review.some(e=>e.item_id===r.item_id)||typeof r.success!=='boolean')return true;
        if(!r.success)return false;
        const saved=r.result,values=expected.current.get(r.item_id);
        return !values||saved?.is_demo!==true||saved.persistence!=='local-postgresql-demo'||!saved.item||Object.entries(values).some(([key,value])=>(saved.item as unknown as Record<string,unknown>)[key]!==value);
      }))throw new Error('İşlem sonucu onaylanan kayıt, router veya değerlerle eşleşmedi.');
      setResults(response.results);if(response.results.some(result=>result.success))onSaved?.();
    }
    catch(e){setError(subscriberOperationError(e)+' Kalıcı sonuç doğrulanamadı; işlem uygulanmış olabilir. Yeni önizleme oluşturmadan aynı istekle sonucu alın.');}
    finally {clearTimeout(timer);invalidateResources([...subscriberSaveDependencies]);sending.current=false;setPending(false);}
  }
  return <dialog ref={dialog} className="expiry-dialog" aria-busy={pending} aria-labelledby="quick-title" onCancel={e=>{e.preventDefault();if(!sending.current)onClose();}}>
    <h2 id="quick-title" tabIndex={-1}>Abone İşlemleri · Demo</h2>
    <p>Yalnız V2 demo kayıtları ve denetim geçmişi güncellenir. Paket seçimi kayıtlı demo fiyatını da günceller.</p>
     {rows.length===1&&<div className="quick-preview">
       <strong>Abone: {rows[0].customer_name}</strong>
       <p>Kullanıcı adı: {rows[0].username}</p>
       <p>Mevcut paket: <strong className="current-plan-highlight">{rows[0].plan}</strong></p>
       <p>Mevcut aylık ücret: {rows[0].monthly_price.toLocaleString('tr-TR')} TL</p>
     </div>}
    {!review?<form onSubmit={prepare}>
      {(routers.loading||((action==='PLAN'||action==='CREATE')&&options.loading))&&<p role="status">Router/paket bilgileri yükleniyor…</p>}
      {routers.error&&<p role="alert" className="form-error">Router bilgileri alınamadı: {routers.error} <button type="button" className="text-link" onClick={routers.retry}>Routerları yeniden yükle</button></p>}
      {(action==='PLAN'||action==='CREATE')&&options.error&&<button type="button" className="button-secondary" onClick={options.retry}>Paketleri yeniden yükle</button>}
      {rows.length>0&&<label className="form-label">İşlem<select value={action} onChange={e=>setAction(e.target.value as QuickAction)}><option value="EXTEND">Abonelik uzatma</option>{rows.length===1&&<><option value="PLAN">Paket değiştirme</option><option value="STATUS">Etkinleştir / devre dışı bırak</option></>}</select></label>}
      {action==='CREATE'&&<><label className="form-label">Router<select value={router} onChange={e=>setRouter(e.target.value)}><option value="">Seçin</option>{routers.data?.items.map(r=><option key={r.id}>{r.name}</option>)}</select></label>{routers.error&&<p role="alert">{routers.error}</p>}<label className="form-label">Yetkili kaynak<select value={source} onChange={e=>setSource(e.target.value)}><option>LOCAL</option><option>RADIUS</option></select></label><label className="form-label">Kullanıcı adı<input required pattern="[a-zA-Z0-9_.-]+" maxLength={80} value={username} onChange={e=>setUsername(e.target.value)}/></label><label className="form-label">Abone adı<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/></label></>}
      {action==='PLAN'&&rows.length===1&&plan&&options.data?.plans.some(p=>p.name===plan)&&<div className="quick-preview">
        <strong>Paket değişikliği önizlemesi</strong>
        <p>Eski paket: {rows[0].plan} → Yeni paket: {plan}</p>
        <p>Eski ücret: {rows[0].monthly_price.toLocaleString('tr-TR')} TL</p>
        <p>Yeni ücret: {options.data.plans.find(p=>p.name===plan)!.monthly_price.toLocaleString('tr-TR')} TL</p>
        <p><strong>Aylık fark: {(options.data.plans.find(p=>p.name===plan)!.monthly_price-rows[0].monthly_price).toLocaleString('tr-TR')} TL</strong></p>
      </div>}
      {(action==='CREATE'||action==='PLAN')&&<label className="form-label"><span id={`${fieldId}-plan`}>Yeni paket</span><select aria-labelledby={`${fieldId}-plan`} required value={plan} onChange={e=>setPlan(e.target.value)}><option value="">Paket seçin</option>{options.data?.plans.map(p=><option key={p.name} value={p.name}>{p.name} · {p.monthly_price} TL</option>)}</select>{options.error&&<span role="alert">{options.error}</span>}</label>}
      {action==='STATUS'&&<label className="form-label"><span id={`${fieldId}-status`}>Yeni durum</span><select aria-labelledby={`${fieldId}-status`} value={status} onChange={e=>setStatus(e.target.value)}><option value="ACTIVE">Etkin</option><option value="PAUSED">Devre dışı (duraklatıldı)</option></select></label>}
      {action==='EXTEND'&&<label className="form-label"><span id={`${fieldId}-extension`}>Uzatma</span><select aria-labelledby={`${fieldId}-extension`} value={days} onChange={e=>setDays(e.target.value)}><option value="7">7 gün</option><option value="15">15 gün</option><option value="30">30 gün</option><option value="60">60 gün</option><option value="90">90 gün</option><option value="CUSTOM">Özel bitiş tarihi</option></select></label>}
      {(action==='CREATE'||action==='EXTEND'&&days==='CUSTOM')&&<label className="form-label">Yeni bitiş tarihi<input required type="date" min={today} value={custom} onChange={e=>setCustom(e.target.value)}/></label>}

       <p>{({EXTEND:'Uzatma, bitiş henüz dolmadıysa mevcut bitişten; dolduysa Türkiye bugününden hesaplanır. Özel tarih doğrudan yeni bitiştir.',PLAN:'Seçilen paket ve kayıtlı aylık ücret güncellenir. Bitiş tarihi ve hesap durumu korunur.',STATUS:'Yalnız hesap aktifliği güncellenir. Paket ve bitiş tarihi korunur; hesap durumu canlı oturum kanıtı değildir.',CREATE:'Yeni sentetik abone seçilen router, kaynak, paket ve bitiş tarihiyle kaydedilir.'} as Record<QuickAction,string>)[action]}</p>
      <button className="button-primary" disabled={routers.loading||!!routers.error||((action==='PLAN'||action==='CREATE')&&(options.loading||!!options.error))}>Önizle ve gözden geçir</button>
    </form>:<>
      <h3>Eski → Yeni · {({EXTEND:'Abonelik uzatma',PLAN:'Paket değiştirme',STATUS:'Durum değiştirme',CREATE:'Abone oluşturma'} as Record<string,string>)[action]}</h3>
      {review.map((entry,i)=><section key={entry.item_id} className="quick-preview"><strong>{rows[i]?.customer_name??name} · {rows[i]?.username??username}</strong><p>{String(entry.change.router_name)} ({String(entry.change.router_id)}) · {String(entry.change.expected_source)}</p><p>Abone kimliği: {entry.item_id}</p><p>Bitiş: {expiryDate(rows[i]?.expires_on??null)} → {expiryDate(entry.change.expires_on as string|null)}</p>{(action==='PLAN'||action==='CREATE')&&<p>Paket: {rows[i]?.plan??'Yok'} → {plan} · Aylık tutar: {rows[i]?.monthly_price??0} → {options.data?.plans.find(p=>p.name===plan)?.monthly_price??'Bilinmiyor'} TL</p>}{(action==='STATUS'||action==='CREATE')&&<p>Durum: {rows[i]?.status??'Yok'} → {status}</p>}</section>)}
      {results&&<div role="status">{results.filter(r=>r.success).length} başarılı / {results.filter(r=>!r.success).length} başarısız{results.map(r=><p key={r.item_id}>{rows.find(row=>row.id===r.item_id)?.customer_name??name}: {r.success?(action==='PLAN'?`Kaydedildi · Güncel paket: ${r.result?.item.plan} · Aylık tutar: ${r.result?.item.monthly_price} TL`:action==='STATUS'?`Kaydedildi · Güncel durum: ${r.result?.item.status==='ACTIVE'?'Aktif':'Pasif'}`:`Kaydedildi · Güncel bitiş: ${expiryDate(r.result?.item.expires_on??null)}`):r.error??'İşlem uygulanmadı.'}</p>)}</div>}
      <p>Yanıt kaybolursa aynı onayı tekrar gönderin; başarılı kayıt ikinci kez uygulanmaz.</p>
      <div className="expiry-editor-actions"><button className="button-secondary" disabled={pending} onClick={()=>{onClose();}}>Kapat ve güncel listeden yeniden seç</button><button className="button-primary" disabled={pending||!!results?.every(r=>r.success)} onClick={save}>{pending?'Kaydediliyor…':results?.every(r=>r.success)?'İşlem tamamlandı':results?'Aynı istekle eksik sonuçları getir':attempted?'Aynı istekle sonucu doğrula':'Onayla ve uygula'}</button></div>
    </>}
    {error&&<p role="alert" className="form-error">{error}</p>}
    <button className="button-secondary expiry-editor-cancel" disabled={pending} onClick={onClose}>Kapat</button>
  </dialog>;
}
