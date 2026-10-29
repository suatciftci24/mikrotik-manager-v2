import {useEffect,useRef,useState,type FormEvent} from 'react';
import {api} from '../lib/api';
import {useResource} from '../lib/useResource';
import {invalidateResources} from '../lib/resourceEvents';
import {dateTime,ResourceState} from './Resource';
import {candidatePayload,connectionError,routerForm,registryStatus,type RegisteredRouter,type RegistryOptions,type Verification} from '../lib/routerRegistry';

const actionHeaders={'X-V2-Demo-Action':'router-onboarding'};
export function RouterOnboarding({item,onClose,onSaved}:{item?:RegisteredRouter;onClose:()=>void;onSaved:(id:string)=>void}){
 const dialog=useRef<HTMLDialogElement>(null),sending=useRef(false),requestId=useRef(crypto.randomUUID());
 const options=useResource<RegistryOptions>('/router-registry/options');
 const [form,setForm]=useState(()=>routerForm(item));const [consent,setConsent]=useState(false),[confirm,setConfirm]=useState(false);
 const [proof,setProof]=useState<Verification|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[phase,setPhase]=useState<'FORM'|'REVIEW'>('FORM');
 const [attempted,setAttempted]=useState(false);const active=useRef(true);
 useEffect(()=>{active.current=true;const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{active.current=false;node?.close();origin?.isConnected&&origin.focus({preventScroll:true});};},[]);
 const update=(field:keyof typeof form,value:string)=>{setForm(previous=>({...previous,[field]:value}));requestId.current=crypto.randomUUID();setAttempted(false);setError('');};
 const close=()=>{if(sending.current)return;if(proof&&(proof.state==='VERIFIED'||proof.state==='EXPIRED'))void api('/router-registry/verifications/'+proof.verification_id+'/cancel',{method:'POST',headers:actionHeaders}).catch(()=>{});onClose();};
 async function verify(event:FormEvent){
  event.preventDefault();if(sending.current||!consent||!window.isSecureContext)return;setError('');
  let payload;try{payload=candidatePayload(form,requestId.current,item);}catch(e){setError(e instanceof Error?e.message:'Alanlar geçersiz.');return;}
  sending.current=true;setBusy(true);setAttempted(true);
  try{
   const result=await api<Verification>('/router-registry/verify',{method:'POST',signal:AbortSignal.timeout(25000),headers:actionHeaders,body:JSON.stringify(payload)});
   if(!active.current)return;
   setProof(result);
   if(result.state==='VERIFIED'||result.state==='SAVED'){setPhase('REVIEW');setForm(previous=>({...previous,password:''}));}
   else setError(result.error_code?connectionError(result.error_code):'Doğrulama henüz sonuçlanmadı. Aynı isteği sorgulamak yeni bağlantı başlatmaz.');
  }catch(e){if(active.current)setError(connectionError(e instanceof Error?e.message:''));}
  finally{if(active.current){sending.current=false;setBusy(false);invalidateResources(['/router-registry']);}}
 }
 async function save(){
  if(!proof||!confirm||sending.current)return;setError('');sending.current=true;setBusy(true);
  try{
   const result=await api<{item:RegisteredRouter}>('/router-registry/register',{method:'POST',signal:AbortSignal.timeout(25000),headers:actionHeaders,body:JSON.stringify({verification_id:proof.verification_id,confirmed:true})});
   invalidateResources(['/router-registry']);if(active.current)onSaved(result.item.id);
  }catch(e){if(active.current)setError(connectionError(e instanceof Error?e.message:''));}
  finally{if(active.current){sending.current=false;setBusy(false);}}
 }
 async function loadCa(file?:File){
  if(!file)return;
  if(file.size>262144){setError('Public CA en fazla 256 KiB olabilir.');return;}
  try{const text=await file.text();if(text.includes('PRIVATE KEY')){setError('Özel anahtar yüklenemez. Yalnız public CA seçin.');return;}if(active.current)update('ca_pem',text);}
  catch{if(active.current)setError('Public CA dosyası okunamadı.');}
 }

 const ready=options.data?.connection_enabled&&options.data.operator_authorized&&window.isSecureContext;
 return <dialog ref={dialog} className="expiry-dialog router-onboarding" aria-labelledby="router-onboarding-title" onCancel={event=>{event.preventDefault();close();}}>
  <div className="onboarding-heading"><span className="eyebrow">GÜVENLİ ROUTER ONBOARDING</span><h2 id="router-onboarding-title">{item?'Router bağlantısını düzenle':'Router ekle'}</h2><p>1. Güvenli bağlantı → 2. Cihazı doğrula → 3. Kaydı onayla</p></div>
  <p className="registry-security-note">TLS CA zinciri, IP SAN ve leaf SHA-256 pin zorunludur. Yalnız kimlik ve sistem kaynak bilgisi okunur; cihaz ayarı değiştirilmez ve polling başlatılmaz.</p>
  {!window.isSecureContext&&<p role="alert" className="form-error">Parola girişi için HTTPS veya localhost gerekir. Bu sayfadan credential gönderilemez.</p>}
  <ResourceState {...options}/>
  {options.data&&!ready&&<p role="alert" className="form-error">{connectionError(options.data.connection_enabled?'ONBOARDING_OPERATOR_NOT_AUTHORIZED':'ONBOARDING_CONNECTION_DISABLED')}</p>}
  {phase==='FORM'?<form onSubmit={verify} autoComplete="off">
   <fieldset disabled={busy||!window.isSecureContext} className="onboarding-fields"><legend>Cihaz ve güvenli erişim</legend>
    <label className="form-label">Router adı<input required maxLength={120} value={form.name} onChange={e=>update('name',e.target.value)}/></label>
    <label className="form-label">Yönetim IPv4 adresi<input required inputMode="decimal" placeholder="10.x.x.x" value={form.management_address} onChange={e=>update('management_address',e.target.value)}/></label>
    <label className="form-label">API-SSL portu<input required type="number" min={1024} max={65535} value={form.port} onChange={e=>update('port',e.target.value)}/></label>
    <label className="form-label">Beklenen RouterOS sürümü<input maxLength={40} placeholder="Boş: otomatik algıla (6.49.x / 7.x)" value={form.expected_version} onChange={e=>update('expected_version',e.target.value)}/></label>
    <label className="form-label">Beklenen cihaz kimliği<input maxLength={120} placeholder="İlk kayıtta isteğe bağlı; önizlemede doğrulanır" value={form.expected_identity} onChange={e=>update('expected_identity',e.target.value)}/></label>
    <label className="form-label">API kullanıcı adı<input required={!item} autoComplete="off" maxLength={128} placeholder={item?'Boş: mevcut hesabı koru':''} value={form.username} onChange={e=>update('username',e.target.value)}/></label>
    <label className="form-label">API parolası<input required={!item} type="password" aria-label="API parolası" autoComplete="new-password" maxLength={1024} placeholder={item?'Boş: kayıtlı parolayı koru':''} value={form.password} onChange={e=>update('password',e.target.value)}/><small>API yanıtına, denetim kaydına veya tarayıcı depolamasına yazılmaz.</small></label>
    <label className="form-label">Public CA dosyası<input type="file" accept=".pem,.crt,.cer" onChange={e=>{void loadCa(e.target.files?.[0]);e.target.value='';}}/></label>
    <label className="form-label onboarding-wide">Public CA PEM<textarea required={!item} rows={5} spellCheck={false} placeholder={item?'Boş: mevcut public CA korunur':'-----BEGIN CERTIFICATE-----'} value={form.ca_pem} onChange={e=>update('ca_pem',e.target.value)}/></label>
    <label className="form-label onboarding-wide">Sunucu leaf SHA-256 pini<input required minLength={64} maxLength={64} spellCheck={false} autoCapitalize="none" value={form.leaf_sha256} onChange={e=>update('leaf_sha256',e.target.value.trim().toLowerCase())}/></label>
   </fieldset>
   <p>Yönetim kaynağı: <strong>{options.data?.source_ip??'Yapılandırılmamış'}</strong> · İzinli portlar: {options.data?.allowed_ports.join(', ')??'Bilinmiyor'}</p>
   <label className="registry-consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} disabled={busy}/>Bu hedefte tek seferlik, salt-okunur API-SSL bağlantısını yapmaya yetkiliyim ve onaylıyorum.</label>
   <button className="button-primary" disabled={!ready||!consent||busy}>{busy?'Güvenli bağlantı doğrulanıyor…':attempted?'Aynı isteğin sonucunu getir':'Bağlantıyı doğrula'}</button>
   {attempted&&<p>Sonuç kaybolduysa aynı istek ikinci bağlantı açmaz. Başarısız doğrulamayı tekrar denemek için alanları bilinçli olarak düzenleyin; otomatik tekrar yoktur.</p>}
  </form>:proof?.preview&&<section className="onboarding-review" aria-label="Doğrulanmış cihaz önizlemesi">
   <h3>Cihaz doğrulandı · {proof.state==='SAVED'?'Kayıt zaten oluşturulmuş':'Kayıt onayı bekleniyor'}</h3>
   <dl className="registry-facts"><div><dt>Panel adı</dt><dd>{item?.name??'Yeni kayıt'} → {proof.preview.name}</dd></div><div><dt>Uç nokta</dt><dd>{item?`${item.management_address}:${item.port} → `:''}{proof.preview.management_address}:{proof.preview.port}</dd></div><div><dt>Router kimliği</dt><dd>{proof.preview.metadata.identity}</dd></div><div><dt>Model</dt><dd>{proof.preview.metadata.model}</dd></div><div><dt>RouterOS</dt><dd>{proof.preview.metadata.routeros_version}</dd></div><div><dt>Kaynak IP</dt><dd>{proof.preview.source_ip}</dd></div><div><dt>Doğrulama</dt><dd>{dateTime(proof.preview.checked_at)}</dd></div><div><dt>Onay son zamanı</dt><dd>{dateTime(proof.expires_at)}</dd></div></dl>
   <label className="registry-consent"><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)} disabled={busy}/>Okunan cihaz kimliği/model/sürümü ve hedef adresini inceledim; bu V2 kaydını onaylıyorum.</label>
   <button className="button-primary" disabled={!confirm||busy} onClick={()=>void save()}>{busy?'Kaydediliyor…':item?'Değişikliği kaydet':'Doğrulanmış routerı kaydet'}</button>
  </section>}
  {error&&<p role="alert" className="form-error">{error}</p>}
  {proof?.error_code&&<p className="registry-error-code">STOP: {proof.error_code}</p>}
  <button className="button-secondary expiry-editor-cancel" disabled={busy} onClick={close}>Kapat</button>
 </dialog>;
}

export function RegisteredRouterDetail({id,onBack,onEdit}:{id:string;onBack:()=>void;onEdit:(item:RegisteredRouter)=>void}){
 const detail=useResource<{item:RegisteredRouter;history:{action:string;occurred_at:string;actor_id:string;details:Record<string,unknown>}[]}>('/router-registry/'+encodeURIComponent(id));
 const options=useResource<RegistryOptions>('/router-registry/options');
 const [checking,setChecking]=useState(false),[error,setError]=useState(''),[confirm,setConfirm]=useState(false);
 const request=useRef<string|null>(null),sending=useRef(false);
 const item=detail.data?.item;
 async function check(){
  if(!item||!confirm||sending.current)return;request.current??=crypto.randomUUID();sending.current=true;setChecking(true);setError('');
  try{const result=await api<{item?:RegisteredRouter;error_code?:string;state?:string}>(`/router-registry/${encodeURIComponent(id)}/check`,{method:'POST',signal:AbortSignal.timeout(25000),headers:actionHeaders,body:JSON.stringify({request_id:request.current,expected_revision:item.revision,confirmed_read_only:true})});if(!result.item)setError(result.error_code?connectionError(result.error_code):'Doğrulama tamamlanmadı; otomatik tekrar yapılmadı.');}
  catch(e){setError(connectionError(e instanceof Error?e.message:''));}
  finally{setChecking(false);sending.current=false;setConfirm(false);invalidateResources(['/router-registry']);}
 }
 return <section className="screen-stack"><button className="detail-back button-secondary" onClick={onBack}>← Router listesine dön</button><ResourceState {...detail}/>{item&&<>
  <div className="page-heading-row"><div><div className="eyebrow">KAYITLI CİHAZ · SALT OKUNUR</div><h1>{item.name}</h1><p>{item.identity} · {item.management_address}:{item.port}</p></div><button className="button-secondary" disabled={checking} onClick={()=>onEdit(item)}>Bağlantıyı düzenle</button></div>
  <div className="panel registry-detail"><h2>Cihaz ve son doğrulama</h2><dl className="registry-facts">{Object.entries({'Kimlik':item.identity,'Model':item.model,'RouterOS':item.routeros_version,'Durum':registryStatus(item.status),'Son başarılı kontrol':dateTime(item.last_success_at),'Son kontrol':dateTime(item.last_checked_at),'Kaynak IP':item.source_ip,'Sertifika leaf SHA-256':item.leaf_sha256,'WAN / IPsec / trafik / aboneler':'Bilinmiyor — bu onboarding oturumunda okunmadı.'}).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p>Sürekli izleme kapalıdır. Başarılı geçmiş kontrol, şu an çevrimiçi olduğunun kanıtı değildir.</p>{item.last_error&&<p role="alert" className="form-error">{connectionError(item.last_error)} <span className="registry-error-code">{item.last_error}</span></p>}</div>
  <div className="panel registry-detail"><h2>Tek seferlik kontrol</h2><ResourceState {...options}/><label className="registry-consent"><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)} disabled={checking||!!request.current}/>Kimlik ve sistem kaynağı için tek salt-okunur bağlantıyı onaylıyorum.</label><button className="button-secondary" onClick={()=>void check()} disabled={!confirm||checking||!!request.current||!options.data?.connection_enabled||!options.data?.operator_authorized}>{checking?'Kontrol ediliyor…':request.current?'Bu görünümdeki kontrol tamamlandı':'Şimdi bir kez kontrol et'}</button>{error&&<p role="alert" className="form-error">{error}</p>}</div>
  <div className="panel registry-detail"><h2>İşlem geçmişi</h2>{detail.data?.history.length?<ol className="registry-history">{detail.data.history.map((event,index)=><li key={index}><strong>{event.action}</strong><span>{dateTime(event.occurred_at)} · {event.actor_id}</span>{typeof event.details.error_code==='string'&&<span>{connectionError(event.details.error_code)}</span>}</li>)}</ol>:<p>İşlem kaydı bulunamadı.</p>}</div>
 </>}</section>;
}
