import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, type Router, type Subscriber, type DemoOptions } from '../lib/api';
import { useResource } from '../lib/useResource';
import { invalidateResources } from '../lib/resourceEvents';
import { extensionDate } from '../lib/quick';
import { expiryDate } from '../lib/expiry';

export type QuickAction = 'EXTEND'|'PLAN'|'STATUS'|'CREATE';
type Entry = {item_id:string; change:Record<string,unknown>};
type Result = {item_id:string; success:boolean; error?:string};
export function QuickActions({rows,today,onClose,initialAction,onSaved}: {rows:Subscriber[];today:string;onClose:()=>void;initialAction?:QuickAction;onSaved?:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const options=useResource<DemoOptions>('/subscribers/demo-options');
  const routers=useResource<{items:Router[]}>('/routers');
  const [action,setAction]=useState<QuickAction>(initialAction??(rows.length?'EXTEND':'CREATE'));
  const [days,setDays]=useState('30'); const [custom,setCustom]=useState('');
  const [plan,setPlan]=useState(''); const [status,setStatus]=useState('ACTIVE');
  const [router,setRouter]=useState(rows[0]?.router_name??'');
  const [source,setSource]=useState('LOCAL'); const [username,setUsername]=useState(''); const [name,setName]=useState('');
  const [review,setReview]=useState<Entry[]|null>(null); const [results,setResults]=useState<Result[]|null>(null);
  const [error,setError]=useState(''); const [pending,setPending]=useState(false); const sending=useRef(false);
  useEffect(()=>{const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{node?.close();if(origin?.isConnected)origin.focus({preventScroll:true});else document.querySelector<HTMLElement>('.detail-back')?.focus();};},[]);
  useEffect(()=>{if(review)dialog.current?.querySelector<HTMLElement>('h2')?.focus();},[review]);
  function prepare(e:FormEvent) {
    e.preventDefault(); setError('');
    if (rows.some(r=>r.is_demo!==true || !r.source)) {setError('Yalnız kaynağı bilinen sentetik demo aboneleri seçin.');return;}
    if (new Set(rows.map(r=>r.router_name)).size>1) {setError('Toplu işlem için aynı router üzerindeki aboneleri seçin.');return;}
    if (!routers.data || routers.error) {setError('Router kimliği doğrulanamadı; pencereyi yeniden açın.');return;}
    const routerItems=routers.data.items;
    const targets=rows.length?rows:[null];
    const entries=targets.map(row=>{
      const id=crypto.randomUUID();
      const expires=action==='CREATE'?custom:action==='EXTEND'?(days==='CUSTOM'?custom:extensionDate(row!.expires_on,today,Number(days))):row!.expires_on;
      return {item_id:row?.id??`demo-sub-${id}`,change:{action,request_id:id,confirmed:true,expected_revision:row?.revision??0,
        expected_source:row?.source??source,expected_expires_on:row?.expires_on??null,expires_on:expires,
        router_id:routerItems.find(r=>r.name===(row?.router_name??router))?.id??'',
        days:action==='EXTEND'&&days!=='CUSTOM'?Number(days):null,plan,status,router_name:row?.router_name??router,username,customer_name:name}};
    });
    if (entries.some(e=>(action==='EXTEND'||action==='CREATE')&&(!e.change.expires_on||e.change.expires_on<today))) {setError('Geçerli bitiş tarihi seçin. Bilinmeyen bitiş için özel tarih kullanın.');return;}
    if (action==='CREATE'&&(!router||!username.trim()||!name.trim()||!plan.trim())) {setError('Router, kullanıcı, abone adı ve paket zorunlu.');return;}
    if (action==='PLAN'&&!plan.trim()) {setError('Yeni paket girin.');return;}
    if(entries.some(e=>!e.change.router_id)) {setError('Router kimliği bulunamadı.');return;}
    setReview(entries);setResults(null);
  }
  async function save() {
    if (!review||sending.current) return;
    sending.current=true;setPending(true);setError('');
    try {const response=await api<{results:Result[]}>('/subscribers/demo-quick',{method:'POST',headers:{'X-V2-Demo-Action':'expiry'},body:JSON.stringify({entries:review})});setResults(response.results);if(response.results.some(result=>result.success))onSaved?.();}
    catch(e){setError(e instanceof Error?e.message:'İşlem sonucu alınamadı.');}
    finally {invalidateResources(['/subscribers','/routers','/dashboard']);sending.current=false;setPending(false);}
  }
  return <dialog ref={dialog} className="expiry-dialog" aria-labelledby="quick-title" onCancel={e=>{e.preventDefault();if(!sending.current)onClose();}}>
    <h2 id="quick-title" tabIndex={-1}>Hızlı İşlemler · DEMO / SENTETİK</h2>
    <p>Yalnız V2 demo kayıtları ve denetim geçmişi güncellenir. Paket seçimi kayıtlı demo fiyatını da günceller.</p>
    {!review?<form onSubmit={prepare}>
      {(routers.loading||((action==='PLAN'||action==='CREATE')&&options.loading))&&<p role="status">Router/paket bilgileri yükleniyor…</p>}
      {routers.error&&<p role="alert" className="form-error">Router bilgileri alınamadı: {routers.error} <button type="button" className="text-link" onClick={routers.retry}>Routerları yeniden yükle</button></p>}
      {(action==='PLAN'||action==='CREATE')&&options.error&&<button type="button" className="button-secondary" onClick={options.retry}>Paketleri yeniden yükle</button>}
      {rows.length>0&&<label className="form-label">İşlem<select value={action} onChange={e=>setAction(e.target.value as QuickAction)}><option value="EXTEND">Abonelik uzatma</option>{rows.length===1&&<><option value="PLAN">Paket değiştirme</option><option value="STATUS">Etkinleştir / devre dışı bırak</option></>}</select></label>}
      {action==='CREATE'&&<><label className="form-label">Router<select value={router} onChange={e=>setRouter(e.target.value)}><option value="">Seçin</option>{routers.data?.items.map(r=><option key={r.id}>{r.name}</option>)}</select></label>{routers.error&&<p role="alert">{routers.error}</p>}<label className="form-label">Yetkili kaynak<select value={source} onChange={e=>setSource(e.target.value)}><option>LOCAL</option><option>RADIUS</option></select></label><label className="form-label">Kullanıcı adı<input required pattern="[a-zA-Z0-9_.-]+" maxLength={80} value={username} onChange={e=>setUsername(e.target.value)}/></label><label className="form-label">Abone adı<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/></label></>}
      {(action==='CREATE'||action==='PLAN')&&<label className="form-label">Yeni paket<select required value={plan} onChange={e=>setPlan(e.target.value)}><option value="">Paket seçin</option>{options.data?.plans.map(p=><option key={p.name} value={p.name}>{p.name} · {p.monthly_price} TL</option>)}</select>{options.error&&<span role="alert">{options.error}</span>}</label>}
      {action==='STATUS'&&<label className="form-label">Yeni durum<select value={status} onChange={e=>setStatus(e.target.value)}><option value="ACTIVE">Etkin</option><option value="PAUSED">Devre dışı (duraklatıldı)</option></select></label>}
      {action==='EXTEND'&&<label className="form-label">Uzatma<select value={days} onChange={e=>setDays(e.target.value)}><option value="7">7 gün</option><option value="15">15 gün</option><option value="30">30 gün</option><option value="CUSTOM">Özel bitiş tarihi</option></select></label>}
      {(action==='CREATE'||action==='EXTEND'&&days==='CUSTOM')&&<label className="form-label">Yeni bitiş tarihi<input required type="date" min={today} value={custom} onChange={e=>setCustom(e.target.value)}/></label>}
      <p>Uzatma, bitiş henüz dolmadıysa mevcut bitişten; dolduysa Türkiye bugününden hesaplanır. Özel tarih doğrudan yeni bitiştir.</p>
      <button className="button-primary" disabled={routers.loading||!!routers.error||((action==='PLAN'||action==='CREATE')&&(options.loading||!!options.error))}>Önizle ve gözden geçir</button>
    </form>:<>
      <h3>Eski → Yeni · {({EXTEND:'Abonelik uzatma',PLAN:'Paket değiştirme',STATUS:'Durum değiştirme',CREATE:'Abone oluşturma'} as Record<string,string>)[action]}</h3>
      {review.map((entry,i)=><section key={entry.item_id} className="quick-preview"><strong>{rows[i]?.customer_name??name} · {rows[i]?.username??username}</strong><p>{String(entry.change.router_name)} ({String(entry.change.router_id)}) · {String(entry.change.expected_source)}</p><p>Abone kimliği: {entry.item_id}</p><p>Bitiş: {expiryDate(rows[i]?.expires_on??null)} → {expiryDate(entry.change.expires_on as string|null)}</p>{(action==='PLAN'||action==='CREATE')&&<p>Paket: {rows[i]?.plan??'Yok'} → {plan} · Aylık tutar: {rows[i]?.monthly_price??0} → {options.data?.plans.find(p=>p.name===plan)?.monthly_price??'Bilinmiyor'} TL</p>}{(action==='STATUS'||action==='CREATE')&&<p>Durum: {rows[i]?.status??'Yok'} → {status}</p>}</section>)}
      {results&&<div role="status">{results.filter(r=>r.success).length} başarılı / {results.filter(r=>!r.success).length} başarısız{results.map((r,i)=><p key={r.item_id}>{rows[i]?.customer_name??name}: {r.success?'PASS — kaydedildi':r.error}</p>)}</div>}
      <p>Yanıt kaybolursa aynı onayı tekrar gönderin; başarılı kayıt ikinci kez uygulanmaz.</p>
      <div className="expiry-editor-actions"><button className="button-secondary" disabled={pending} onClick={()=>{onClose();}}>Kapat ve güncel listeden yeniden seç</button><button className="button-primary" disabled={pending} onClick={save}>{pending?'Kaydediliyor…':results?'Aynı isteği tekrar gönder':'Onayla ve uygula'}</button></div>
    </>}
    {error&&<p role="alert" className="form-error">{error}</p>}
    <button className="button-secondary expiry-editor-cancel" disabled={pending} onClick={onClose}>Kapat</button>
  </dialog>;
}
