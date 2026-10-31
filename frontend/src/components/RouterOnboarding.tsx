import {RouterPilotRead} from './RouterPilotRead';
import {RouterDeviceCenter} from './RouterDeviceCenter';
import {applyTrustProfile,type TrustProfile} from '../lib/routerTrustProfiles';
import {connectionProfile,routerConnectionProfiles} from '../lib/routerConnectionProfiles';
import {offlineRouterPreview,syntheticRouterPreview} from '../lib/routerOnboardingPreview';
import {useEffect,useRef,useState,type FormEvent} from 'react';
import {api} from '../lib/api';
import {useResource} from '../lib/useResource';
import {invalidateResources} from '../lib/resourceEvents';
import {dateTime,ResourceState} from './Resource';
import {candidatePayload,connectionError,routerForm,registryStatus,type RegisteredRouter,type RegistryOptions,type Verification} from '../lib/routerRegistry';

const actionHeaders={'X-V2-Demo-Action':'router-onboarding'};
export function RouterOnboarding({item,onClose,onSaved,onPilot}:{item?:RegisteredRouter;onClose:()=>void;onSaved:(id:string)=>void;onPilot?:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),sending=useRef(false),requestId=useRef(crypto.randomUUID());
 const options=useResource<RegistryOptions>('/router-registry/options');
 const profiles=useResource<{items:TrustProfile[];total:number}>('/router-workspace/profiles');
 const [profileName,setProfileName]=useState('');
 const [form,setForm]=useState(()=>routerForm(item));const [consent,setConsent]=useState(false),[confirm,setConfirm]=useState(false);
 const [proof,setProof]=useState<Verification|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[phase,setPhase]=useState<'FORM'|'REVIEW'>('FORM');
 const [profileId,setProfileId]=useState('api-ssl-auto');
 const [preview,setPreview]=useState<ReturnType<typeof offlineRouterPreview>|null>(null);
 const [caSource,setCaSource]=useState('');
 const [attempted,setAttempted]=useState(false);const active=useRef(true);
 useEffect(()=>{active.current=true;const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{active.current=false;node?.close();origin?.isConnected&&origin.focus({preventScroll:true});};},[]);
 const update=(field:keyof typeof form,value:string)=>{setForm(previous=>({...previous,[field]:value}));requestId.current=crypto.randomUUID();setAttempted(false);setError('');setPreview(null);};
 const close=()=>{if(sending.current)return;if(proof&&(proof.state==='VERIFIED'||proof.state==='EXPIRED'))void api('/router-registry/verifications/'+proof.verification_id+'/cancel',{method:'POST',headers:actionHeaders}).catch(()=>{});onClose();};
 async function verify(event:FormEvent){
  event.preventDefault();if(sending.current||!consent||!window.isSecureContext||!options.data?.connection_enabled||!options.data.operator_authorized)return;setError('');
  let payload;try{offlineRouterPreview(form,item);payload=candidatePayload(form,requestId.current,item);}catch(e){setError(e instanceof Error?e.message:'Alanlar geçersiz.');return;}
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
  try{const text=await file.text();if(text.includes('PRIVATE KEY')){setError('Özel anahtar yüklenemez. Yalnız public CA seçin.');return;}if(active.current){update('ca_pem',text);setCaSource('Public CA dosyası yüklendi; içeriği aşağıdaki PEM alanındadır.');}}
  catch{if(active.current)setError('Public CA dosyası okunamadı.');}
 }

 async function saveTrustProfile(){
  if(sending.current)return;setError('');
  try{
   if(!form.management_address)throw new Error('Sertifika profili için hedef IPv4 adresi gerekli.');
   if(!/^[a-f0-9]{64}$/.test(form.leaf_sha256))throw new Error('Profil için 64 hexadecimal karakterli SHA-256 pin gerekli.');
   if(!form.ca_pem)throw new Error('Profil için public CA metni gerekli; kayıtlı gizli materyal okunmaz.');
   if(!profileName.trim())throw new Error('Sertifika profiline bir ad verin.');
   sending.current=true;setBusy(true);
   await api('/router-workspace/profiles',{method:'POST',headers:{'X-V2-Demo-Action':'router-workspace'},body:JSON.stringify({request_id:crypto.randomUUID(),fields:{name:profileName,management_address:form.management_address,port:Number(form.port),ca_pem:form.ca_pem,leaf_sha256:form.leaf_sha256},expected_revision:0,confirmed:true})});
   profiles.retry();setCaSource('Sertifika profili yerel V2 veritabanına kaydedildi. Cihaz bağlantısı kurulmadı.');
  }catch(e){setError(e instanceof Error?e.message:'Profil kaydedilemedi.');}finally{sending.current=false;setBusy(false);}
 }
 function previewForm(){
  setError('');setPreview(null);
  try{setPreview(offlineRouterPreview(form,item));}catch(e){setError(e instanceof Error?e.message:'Form doğrulanamadı.');}
 }
 const ready=options.data?.connection_enabled&&options.data.operator_authorized&&window.isSecureContext;
 return <dialog ref={dialog} className="expiry-dialog router-onboarding" aria-labelledby="router-onboarding-title" onCancel={event=>{event.preventDefault();close();}}>
  <div className="onboarding-heading"><span className="eyebrow">GÜVENLİ ROUTER ONBOARDING</span><h2 id="router-onboarding-title">{item?'Router bağlantısını düzenle':'Router ekle'}</h2><p>1. Güvenli bağlantı → 2. Cihazı doğrula → 3. Kaydı onayla</p></div>
  {!item&&onPilot&&!proof&&<button type="button" disabled={busy} onClick={onPilot}>Gerçek Router / Salt Okunur Pilot — CEBECI_TOWERS</button>}
  <p className="registry-security-note">TLS CA zinciri, IP SAN ve leaf SHA-256 pin zorunludur. Yalnız kimlik ve sistem kaynak bilgisi okunur; cihaz ayarı değiştirilmez ve polling başlatılmaz.</p>
  {!window.isSecureContext&&<p role="alert" className="form-error">Parola girişi için HTTPS veya localhost gerekir. Bu sayfadan credential gönderilemez.</p>}
  <ResourceState {...options} error={options.error?connectionError(options.error):undefined}/>
  {options.data&&!ready&&<p role="alert" className="form-error">{connectionError(options.data.connection_enabled?'ONBOARDING_OPERATOR_NOT_AUTHORIZED':'ONBOARDING_CONNECTION_DISABLED')}</p>}
  {phase==='FORM'&&<>
   <section aria-label="Yeniden kullanılabilir sertifika profilleri"><h3>Sertifika profilleri · Cihaza özel</h3><ResourceState {...profiles}/><label className="form-label">Kayıtlı public CA ve pin<select defaultValue="" disabled={busy} onChange={e=>{const profile=profiles.data?.items.find(p=>p.id===e.target.value);if(!profile)return;try{setForm(applyTrustProfile(form,profile));requestId.current=crypto.randomUUID();setConsent(false);setPreview(null);setError('');setCaSource('Profil yüklendi. IP SAN ve pin gerçek bağlantıda tekrar doğrulanır.');}catch(error){setError(error instanceof Error?error.message:'Profil uygulanamadı.');}e.target.value='';}}><option value="">Profil seçin</option>{profiles.data?.items.map(profile=><option key={profile.id} value={profile.id}>{profile.fields.name} · {profile.fields.management_address}:{profile.fields.port}</option>)}</select></label><p>Public CA ve pin yalnız kayıtlı hedef IP/port ile kullanılır. Hesap/parola saklanmaz; cihaz doğrulanmış sayılmaz.</p><label className="form-label">Yeni sertifika profili adı<input maxLength={120} disabled={busy} value={profileName} onChange={e=>setProfileName(e.target.value)}/></label><button type="button" className="button-secondary" disabled={busy} onClick={()=>void saveTrustProfile()}>Public CA ve pini profil olarak sakla</button></section>
   <p><strong>Zorunlu:</strong> Router adı, yönetim IPv4 adresi, API-SSL portu ve SHA-256 pin. {item?'Kullanıcı adı, parola ve CA boş bırakılırsa kayıtlı değerler korunur.':'İlk kayıtta API kullanıcı adı, parola ve public CA da gereklidir.'} <strong>İsteğe bağlı:</strong> Beklenen RouterOS sürümü ve ilk kayıtta cihaz kimliği.</p>
   <label className="form-label">Bağlantı profili<select value={profileId} disabled={busy} onChange={e=>{const profile=connectionProfile(e.target.value);setProfileId(profile.id);update('port',profile.port);setConsent(false);}}>{routerConnectionProfiles.map(profile=><option key={profile.id} value={profile.id}>{profile.label}</option>)}</select></label>
   <p>{connectionProfile(profileId).versionHint} Profiller yalnız güvenli port varsayılanını doldurur; sertifika, pin, hedef adresi ve hesap bilgileri cihaza özeldir.</p>
  </>}
  {phase==='FORM'?<form onSubmit={verify} autoComplete="off">
   <fieldset disabled={busy||!window.isSecureContext} className="onboarding-fields"><legend>Cihaz ve güvenli erişim</legend>
    <label className="form-label">Router adı<input required maxLength={120} value={form.name} onChange={e=>update('name',e.target.value)}/></label>
    <label className="form-label">Yönetim IPv4 adresi<input required inputMode="decimal" placeholder="10.x.x.x" value={form.management_address} onChange={e=>update('management_address',e.target.value)}/></label>
    <label className="form-label">API-SSL portu<input required type="number" min={1024} max={65535} value={form.port} onChange={e=>update('port',e.target.value)}/></label>
    <label className="form-label">Beklenen RouterOS sürümü<input maxLength={40} placeholder="Boş: otomatik algıla (6.49.x / 7.x)" value={form.expected_version} onChange={e=>update('expected_version',e.target.value)}/></label>
    <label className="form-label">Beklenen cihaz kimliği<input maxLength={120} placeholder="İlk kayıtta isteğe bağlı; önizlemede doğrulanır" value={form.expected_identity} onChange={e=>update('expected_identity',e.target.value)}/></label>
    <label className="form-label">API kullanıcı adı<input required={!item} autoComplete="off" maxLength={128} placeholder={item?'Boş: mevcut hesabı koru':''} value={form.username} onChange={e=>update('username',e.target.value)}/></label>
    <label className="form-label">API parolası<input required={!item} type="password" aria-label="API parolası" autoComplete="new-password" maxLength={1024} placeholder={item?'Boş: kayıtlı parolayı koru':''} value={form.password} onChange={e=>update('password',e.target.value)}/><small>API yanıtına, denetim kaydına veya tarayıcı depolamasına yazılmaz.</small></label>
    <p className="onboarding-wide">Public CA için iki seçenekten birini kullanın: PEM dosyası yükleyin veya aşağıya sertifika metnini yapıştırın. Dosya yükleme aynı PEM alanını doldurur. DER ve özel anahtar dosyaları kabul edilmez.</p>
    <label className="form-label">Public CA dosyası<input type="file" accept=".pem,.crt,.cer" onChange={e=>{void loadCa(e.target.files?.[0]);e.target.value='';}}/></label>
    <label className="form-label onboarding-wide">Public CA PEM<textarea required={!item} rows={5} spellCheck={false} placeholder={item?'Boş: mevcut public CA korunur':'-----BEGIN CERTIFICATE-----'} value={form.ca_pem} onChange={e=>{update('ca_pem',e.target.value);setCaSource('PEM metni elle düzenlendi.');}}/></label>
    {caSource&&<p role="status" className="onboarding-wide">{caSource}</p>}
    <p className="onboarding-wide">CA, cihazın TLS sertifikasını imzalayan public sertifikadır. Cihaz sertifikasının IP SAN alanı yönetim IPv4 adresini içermeli. SHA-256 pinini güvenilir kanaldan alın; burada otomatik üretilmez.</p>
    <label className="form-label onboarding-wide">Sunucu leaf SHA-256 pini<input required minLength={64} maxLength={64} spellCheck={false} autoCapitalize="none" value={form.leaf_sha256} onChange={e=>update('leaf_sha256',e.target.value.trim().toLowerCase())}/></label>
   </fieldset>
   <div className="heading-actions"><button type="button" className="button-secondary" disabled={busy} onClick={previewForm}>Formu bağlantısız kontrol et</button><button type="button" className="button-secondary" disabled={busy} onClick={()=>{setError('');setPreview(syntheticRouterPreview());}}>Sentetik örneği önizle</button></div>
   <p>Bağlantısız kontrol form biçimini inceler. Cihazla bağlantı kurmaz, sertifika güvenini kanıtlamaz ve kayıt oluşturmaz.</p>
   <p>Yönetim kaynağı: <strong>{options.data?.source_ip??'Yapılandırılmamış'}</strong> · İzinli portlar: {options.data?.allowed_ports.join(', ')??'Bilinmiyor'}</p>
   {ready&&<label className="registry-consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} disabled={busy}/>Bu hedefte tek seferlik, salt-okunur API-SSL bağlantısını yapmaya yetkiliyim ve onaylıyorum.</label>}
   <button className="button-primary" disabled={!ready||!consent||busy}>{!ready?'Gerçek bağlantı kapalı · Yalnız form kontrolü ve önizleme':busy?'Güvenli bağlantı doğrulanıyor…':attempted?'Aynı isteğin sonucunu getir':'Bağlantıyı doğrula'}</button>
   {attempted&&<p>Sonuç kaybolduysa aynı istek ikinci bağlantı açmaz. Başarısız doğrulamayı tekrar denemek için alanları bilinçli olarak düzenleyin; otomatik tekrar yoktur.</p>}
  </form>:proof?.preview&&<section className="onboarding-review" aria-label="Doğrulanmış cihaz önizlemesi">
   <h3>Cihaz doğrulandı · {proof.state==='SAVED'?'Kayıt zaten oluşturulmuş':'Kayıt onayı bekleniyor'}</h3>
   <dl className="registry-facts"><div><dt>Panel adı</dt><dd>{item?.name??'Yeni kayıt'} → {proof.preview.name}</dd></div><div><dt>Uç nokta</dt><dd>{item?`${item.management_address}:${item.port} → `:''}{proof.preview.management_address}:{proof.preview.port}</dd></div><div><dt>Router kimliği</dt><dd>{proof.preview.metadata.identity}</dd></div><div><dt>Model</dt><dd>{proof.preview.metadata.model}</dd></div><div><dt>RouterOS</dt><dd>{proof.preview.metadata.routeros_version}</dd></div><div><dt>Kaynak IP</dt><dd>{proof.preview.source_ip}</dd></div><div><dt>Doğrulama</dt><dd>{dateTime(proof.preview.checked_at)}</dd></div><div><dt>Onay son zamanı</dt><dd>{dateTime(proof.expires_at)}</dd></div></dl>
   <label className="registry-consent"><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)} disabled={busy}/>Okunan cihaz kimliği/model/sürümü ve hedef adresini inceledim; bu V2 kaydını onaylıyorum.</label>
   <button className="button-primary" disabled={!confirm||busy} onClick={()=>void save()}>{busy?'Kaydediliyor…':item?'Değişikliği kaydet':'Doğrulanmış routerı kaydet'}</button>
  </section>}
  {phase==='FORM'&&preview&&<section className="onboarding-review" aria-label="Sentetik bağlantısız önizleme"><h3>SENTETİK ÖNİZLEME · CİHAZA BAĞLANILMADI</h3><p>Bu bir cihaz doğrulaması değildir. Veritabanına kayıt yapılamaz.</p><dl className="registry-facts">{Object.entries({'Panel adı':preview.name,'Uç nokta':preview.endpoint,'Giriş alanları':preview.credentials,'Public CA':preview.certificate,'SHA-256 pin':preview.pin,'Cihaz bilgisi':preview.identity,'Güven kontrolü':preview.trust}).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>}
  {error&&<p role="alert" className="form-error">{error}</p>}
  {proof?.error_code&&<p className="registry-error-code">STOP: {proof.error_code}</p>}
  <button className="button-secondary expiry-editor-cancel" disabled={busy} onClick={close}>Kapat</button>
 </dialog>;
}

export function RegisteredRouterDetail({id,onBack,onEdit,embedded=false}:{id:string;onBack:()=>void;onEdit:(item:RegisteredRouter)=>void;embedded?:boolean}){
 const detail=useResource<{item:RegisteredRouter;history:{action:string;occurred_at:string;actor_id:string;details:Record<string,unknown>}[]}>('/router-registry/'+encodeURIComponent(id));
 const options=useResource<RegistryOptions>('/router-registry/options');
 const [checking,setChecking]=useState(false),[error,setError]=useState(''),[confirm,setConfirm]=useState(false);
 const request=useRef<string|null>(null),sending=useRef(false);
 const item=detail.data?.item;
 async function check(){
  if(!item||item.status==='PENDING_VERIFICATION'||!confirm||sending.current)return;request.current??=crypto.randomUUID();sending.current=true;setChecking(true);setError('');
  try{const result=await api<{item?:RegisteredRouter;error_code?:string;state?:string}>(`/router-registry/${encodeURIComponent(id)}/check`,{method:'POST',signal:AbortSignal.timeout(25000),headers:actionHeaders,body:JSON.stringify({request_id:request.current,expected_revision:item.revision,confirmed_read_only:true})});if(!result.item)setError(result.error_code?connectionError(result.error_code):'Doğrulama tamamlanmadı; otomatik tekrar yapılmadı.');}
  catch(e){setError(connectionError(e instanceof Error?e.message:''));}
  finally{setChecking(false);sending.current=false;setConfirm(false);invalidateResources(['/router-registry']);}
 }
 return <section className="screen-stack">{!embedded&&<button className="detail-back button-secondary" onClick={onBack}>← Router listesine dön</button>}<ResourceState {...detail} error={detail.error?connectionError(detail.error):undefined}/>{item&&<>
  {!embedded&&<><div className="page-heading-row"><div><div className="eyebrow">KAYITLI CİHAZ · SALT OKUNUR</div><h1>{item.name}</h1><p>{item.identity} · {item.management_address}:{item.port}</p></div><button className="button-secondary" disabled={checking||item.status==='PENDING_VERIFICATION'} onClick={()=>onEdit(item)}>Bağlantıyı düzenle</button></div>
  <div className="panel registry-detail"><h2>Cihaz ve son doğrulama</h2><dl className="registry-facts">{Object.entries({'Kimlik':item.identity,'Model':item.model,'RouterOS':item.routeros_version,'Durum':registryStatus(item.status),'Son başarılı kontrol':dateTime(item.last_success_at),'Son kontrol':dateTime(item.last_checked_at),'Kaynak IP':item.source_ip,'Sertifika leaf SHA-256':item.leaf_sha256,'WAN / IPsec / trafik / aboneler':'Bilinmiyor — bu onboarding oturumunda okunmadı.'}).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p>Sürekli izleme kapalıdır. Başarılı geçmiş kontrol, şu an çevrimiçi olduğunun kanıtı değildir.</p>{item.last_error&&<p role="alert" className="form-error">{connectionError(item.last_error)} <span className="registry-error-code">{item.last_error}</span></p>}</div>
  </>}<div className="panel registry-detail"><h2>Tek seferlik kontrol</h2>{item.status==='PENDING_VERIFICATION'&&<p>Doğrulama bekliyor. Envanter kaydı bağlantı izni vermez; canlı kontrol kapalıdır.</p>}<ResourceState {...options} error={options.error?connectionError(options.error):undefined}/><label className="registry-consent"><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)} disabled={checking||!!request.current}/>Kimlik ve sistem kaynağı için tek salt-okunur bağlantıyı onaylıyorum.</label><button className="button-secondary" onClick={()=>void check()} disabled={item.status==='PENDING_VERIFICATION'||!confirm||checking||!!request.current||!options.data?.connection_enabled||!options.data?.operator_authorized}>{checking?'Kontrol ediliyor…':request.current?'Bu görünümdeki kontrol tamamlandı':'Şimdi bir kez kontrol et'}</button>{error&&<p role="alert" className="form-error">{error}</p>}</div>
  {!embedded&&<div className="panel registry-detail"><h2>İşlem geçmişi</h2>{detail.data?.history.length?<ol className="registry-history">{detail.data.history.map((event,index)=><li key={index}><strong>{event.action}</strong><span>{dateTime(event.occurred_at)} · {event.actor_id}</span>{typeof event.details.error_code==='string'&&<span>{connectionError(event.details.error_code)}</span>}</li>)}</ol>:<p>İşlem kaydı bulunamadı.</p>}</div>}
 </>}</section>;
}

export function RegisteredRouterCenter({id,onBack,onEdit}:{id:string;onBack:()=>void;onEdit:(item:RegisteredRouter)=>void}){
 const detail=useResource<{item:RegisteredRouter}>('/router-registry/'+encodeURIComponent(id));
 const options=useResource<RegistryOptions>('/router-registry/options');
 return <RouterDeviceCenter id={id} onBack={onBack} actions={detail.data&&detail.data.item.status!=='PENDING_VERIFICATION'&&<button className="button-secondary" onClick={()=>onEdit(detail.data!.item)}>Bağlantıyı düzenle</button>} security={<>{detail.data?.item.pilot_kind==='CEBECI_TOWERS'&&<RouterPilotRead id={id} revision={detail.data.item.revision} enabled={!!options.data?.connection_enabled&&!!options.data.operator_authorized}/>}<RegisteredRouterDetail id={id} onBack={onBack} onEdit={onEdit} embedded/></>}/>;
}
