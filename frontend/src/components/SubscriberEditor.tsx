import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, type Subscriber, type SubscriberDetailData, type DemoOptions } from '../lib/api';
import { useResource } from '../lib/useResource';
import { invalidateResources } from '../lib/resourceEvents';
import { subscriberSource } from '../lib/source';
import { expiryDate } from '../lib/expiry';
import { statusText } from '../lib/subscriberHistory';
import { useTurkeyToday } from '../lib/useTurkeyToday';
import { Facts, ResourceState } from './Resource';

type Mode = 'CREATE' | 'PLAN_CHANGE' | 'STATUS_CHANGE';
type Review = {request_id:string; body:Record<string,unknown>; facts:[string,string][]};
export function SubscriberEditor({mode, subscriber, onClose, onSaved}: {
  mode:Mode; subscriber?:Subscriber; onClose:()=>void; onSaved:(id:string)=>void;
}) {
  const options=useResource<DemoOptions>('/subscribers/demo-options');
  const today=useTurkeyToday();
  const dialog=useRef<HTMLDialogElement>(null);
  const sending=useRef(false);
  const [customer,setCustomer]=useState('');const [username,setUsername]=useState('');
  const [router,setRouter]=useState('');const [source,setSource]=useState<'LOCAL'|'RADIUS'>('LOCAL');
  const [plan,setPlan]=useState('');const [status,setStatus]=useState('PAUSED');const [expires,setExpires]=useState('');
  const [review,setReview]=useState<Review|null>(null);const [pending,setPending]=useState(false);const [error,setError]=useState('');
  useEffect(()=>{const origin=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();origin?.focus({preventScroll:true});};},[]);
  useEffect(()=>{if(review)dialog.current?.querySelector<HTMLElement>('h2')?.focus();},[review]);
  const title=mode==='CREATE'?'Sentetik PPPoE abonesi oluştur':mode==='PLAN_CHANGE'?'Demo paket/profil değiştir':'Demo aboneyi etkinleştir / devre dışı bırak';
  const prepare=(event:FormEvent)=>{
    event.preventDefault();setError('');
    const data=options.data;if(!data||data.persistence!=='local-postgresql-demo'||data.is_demo!==true)return;
    const selectedPlan=data.plans.find(p=>p.name===plan);
    let body:Record<string,unknown>;let facts:[string,string][];
    const money=(n:number)=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY'}).format(n);
    if(mode==='CREATE'){
      const selectedRouter=data.routers.find(r=>r.id===router);
      if(!selectedRouter||!selectedPlan||customer.trim().length<2||! /^[A-Za-z0-9][A-Za-z0-9._@-]{0,95}$/.test(username.trim())){setError('Abone adı, geçerli kullanıcı adı, router ve demo paketi zorunludur.');return;}
      if(expires&&expires<today){setError('Bitiş tarihi Türkiye gününe göre geçmişte olamaz.');return;}
      body={customer_name:customer.trim(),username:username.trim(),router_id:router,source,plan,status,expires_on:expires||null};
      facts=[['İşlem','Yeni sentetik PPPoE kaydı'],['Abone',customer.trim()],['Kullanıcı adı',username.trim()],['Router',selectedRouter.name],['Kaynak',source],['Paket/profil',plan],['Aylık tutar',money(selectedPlan.monthly_price)],['Durum',statusText(status)],['Bitiş',expiryDate(expires||null)]];
    }else{
      if(!subscriber||subscriberSource(subscriber.source)==='UNKNOWN'){setError('Kaynak bilinmiyor; değişiklik kapalı.');return;}
      const old=mode==='PLAN_CHANGE'?subscriber.plan:subscriber.status;
      const value=mode==='PLAN_CHANGE'?plan:status;
      if(value===old||mode==='PLAN_CHANGE'&&!selectedPlan){setError('Mevcut değerden farklı, geçerli bir yeni değer seçin.');return;}
      body={operation:mode,value,expected_value:old,expected_revision:subscriber.revision,expected_source:subscriber.source};
      facts=[['Abone',subscriber.customer_name],['Kaynak',subscriber.source??'Bilinmiyor'],['Mevcut değer',mode==='PLAN_CHANGE'?old:statusText(old)],['Yeni değer',mode==='PLAN_CHANGE'?value:statusText(value)]];
      if(mode==='PLAN_CHANGE'&&selectedPlan)facts.push(['Mevcut aylık tutar',money(subscriber.monthly_price)],['Yeni aylık tutar',money(selectedPlan.monthly_price)]);
    }
    setReview({request_id:crypto.randomUUID(),body,facts});
  };
  const save=async()=>{
    if(!review||sending.current)return;
    sending.current=true;setPending(true);setError('');
    try{
      const path=mode==='CREATE'?'/subscribers/demo-create':`/subscribers/${encodeURIComponent(subscriber!.id)}/demo-management`;
      const result=await api<SubscriberDetailData>(path,{method:'POST',headers:{'X-V2-Demo-Action':'subscriber-management'},body:JSON.stringify({...review.body,request_id:review.request_id,confirmed:true})});
      if(result.persistence!=='local-postgresql-demo'||result.is_demo!==true)throw new Error('Kalıcı sentetik kayıt doğrulanamadı. Güncel kaydı kontrol edin.');
      onSaved(result.item.id);
    }catch(failure){setError(failure instanceof Error?failure.message:'Demo işlemi tamamlanamadı.');}
    finally{sending.current=false;setPending(false);}
  };
  const data=options.data;
  return <dialog ref={dialog} className="expiry-dialog" aria-labelledby="subscriber-editor-title" onCancel={e=>{e.preventDefault();if(!sending.current)onClose();}}>
    <h2 id="subscriber-editor-title" tabIndex={-1}>{review?'Demo işlemini onaylayın':title}</h2>
    <p><strong>SENTETİK DEMO.</strong> Yalnız izole yerel V2 PostgreSQL kaydı ve işlem geçmişi değişir. Router/RADIUS üzerinde kullanıcı, parola, profil veya oturum işlemi yapılmaz.</p>
    <ResourceState {...options}/>
    {data&&!options.loading&&!options.error&&data.persistence==='local-postgresql-demo'&&data.is_demo===true&&(review?<>
      <Facts items={review.facts}/><p>Onaydan sonra kayıt ve geçmiş birlikte kaydedilir.</p>
      {error&&<p className="form-error" role="alert">{error} Yanıt alınamadıysa aynı onayı tekrar gönderebilirsiniz; aynı işlem ikinci kez uygulanmaz.</p>}
      {error&&<button className="button-secondary" disabled={pending} onClick={()=>{onClose();invalidateResources(['/subscribers','/routers']);}}>Güncel kayıtları yeniden yükle</button>}
      <div className="expiry-editor-actions"><button className="button-secondary" disabled={pending} onClick={()=>{setReview(null);setError('');}}>Düzelt</button><button className="button-primary" disabled={pending} onClick={save}>{pending?'Kaydediliyor…':'Onayla ve demo kaydını kaydet'}</button></div>
    </>:<form onSubmit={prepare}>
      {mode==='CREATE'&&<>
        <label className="form-label">Abone adı<input autoFocus required minLength={2} maxLength={160} value={customer} onChange={e=>setCustomer(e.target.value)}/></label>
        <label className="form-label">PPPoE kullanıcı adı<input required maxLength={96} pattern="[A-Za-z0-9][A-Za-z0-9._@\-]*" value={username} onChange={e=>setUsername(e.target.value)}/></label>
        <p>Kullanıcı adları büyük/küçük harf ayrımı olmadan denetlenir. Aynı router'da tüm kaynaklar; RADIUS için ayrıca ortak RADIUS kapsamı kontrol edilir.</p>
        <label className="form-label">Yetkili kaynak<select value={source} onChange={e=>setSource(e.target.value as 'LOCAL'|'RADIUS')}><option value="LOCAL">LOCAL</option><option value="RADIUS">RADIUS</option></select></label>
        <label className="form-label">Demo router<select required value={router} onChange={e=>setRouter(e.target.value)}><option value="">Router seçin</option>{data.routers.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      </>}
      {mode!=='STATUS_CHANGE'&&<label className="form-label">Yeni demo paket/profil<select required value={plan} onChange={e=>setPlan(e.target.value)}><option value="">Paket seçin</option>{data.plans.map(p=><option key={p.name} value={p.name}>{p.name} · {p.monthly_price.toLocaleString('tr-TR')} TL/ay</option>)}</select></label>}
      {mode!=='PLAN_CHANGE'&&<label className="form-label">Yeni durum<select value={status} onChange={e=>setStatus(e.target.value)}><option value="ACTIVE">Etkin</option><option value="PAUSED">Devre dışı (duraklatıldı)</option></select></label>}
      {mode==='CREATE'&&<label className="form-label">Bitiş tarihi (isteğe bağlı, Türkiye)<input type="date" min={today} value={expires} onChange={e=>setExpires(e.target.value)}/></label>}
      {subscriber&&<p>Mevcut paket/profil: <strong>{subscriber.plan}</strong> · Mevcut durum: <strong>{statusText(subscriber.status)}</strong></p>}
      {error&&<p className="form-error" role="alert">{error}</p>}
      <button className="button-primary" type="submit">İşlemi gözden geçir</button>
    </form>)}
    <button className="button-secondary expiry-editor-cancel" disabled={pending} onClick={onClose}>İptal</button>
  </dialog>;
}
