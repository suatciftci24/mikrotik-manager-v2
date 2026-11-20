import {useState,useRef} from 'react';
import {api,ApiError} from '../lib/api';
import {useIdentity} from '../lib/permissions';
import {useResource} from '../lib/useResource';
import {useSettledSearch} from '../lib/useSettledSearch';
import {invalidateResources} from '../lib/resourceEvents';
import {ResourceState,dateTime} from '../components/Resource';
import {PageHeading} from '../components/PageHeading';
import {packageCurrencies,packagePrice,packageSpeed,type PackageCurrency,type PackageRecord,type PackageFields} from '../lib/packages';

const empty:PackageFields={name:'',download_mbps:100,upload_mbps:20,router_profile:null,radius_policy_ref:null,monthly_price:null,currency:'TRY',duration_days:30,active:true};
const packageResources=['/packages','/subscriber-workspace/options'];
const pageSize=25;

type PackageReview={
 path:string;body:string;method:'POST'|'DELETE';before:PackageFields|null;next:PackageFields|null;
};

function packageValues(fields:PackageFields|null){
 return fields?[fields.name,packageSpeed(fields),`${fields.duration_days} gün`,packagePrice(fields.monthly_price,fields.currency),
  fields.active?'Aktif':'Pasif',fields.router_profile??'Belirtilmedi',fields.radius_policy_ref??'Belirtilmedi']:[];
}

function PackageComparison({before,next}:{before:PackageFields|null;next:PackageFields|null}){
 const previous=packageValues(before),updated=packageValues(next);
 const names=['Paket adı','İndirme / yükleme','Süre','Aylık ücret','Durum','MikroTik profil etiketi','RADIUS politika referansı'];
 return <dl className="detail-facts package-comparison">{names.map((label,index)=><div key={label}>
  <dt>{label}</dt><dd>{previous[index]??'—'} → {updated[index]??'—'}</dd>
 </div>)}</dl>;
}

export function PackageManagement(){
 const identity=useIdentity();
 return identity?.role_code==='ADMIN'&&identity.can_manage_users===true?<Catalog/>:<p role="alert">Paket yönetimi için merkezi ADMIN yetkisi gerekli.</p>;
}

function Catalog(){
 const [page,setPage]=useState(1),[editing,setEditing]=useState<PackageRecord|null|undefined>(undefined),[form,setForm]=useState<PackageFields>(empty);
 const [query,setQuery]=useState(''),[status,setStatus]=useState('ALL'),[historyId,setHistoryId]=useState('');
 const [search,searching]=useSettledSearch(query.trim());
 const [review,setReview]=useState<PackageReview|null>(null),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false);
 const [error,setError]=useState(''),[message,setMessage]=useState('');
 const request=useRef(''),sending=useRef(false);
 const params=new URLSearchParams({include_inactive:'true',page:String(page),page_size:String(pageSize),query:search,status});
 const resource=useResource<{items:PackageRecord[];total:number}>('/packages?'+params,api,packageResources,!searching);

 function start(item:PackageRecord|null){
  setEditing(item);setForm(item?{...item.fields}:{...empty});setHistoryId(item?.id??'');
  request.current=crypto.randomUUID();setReview(null);setError('');setMessage('');setUncertain(false);
 }

 async function save(){
  if(!review||sending.current)return;
  sending.current=true;setBusy(true);setError('');
  try{
   await api(review.path,{method:review.method,headers:{'X-V2-Demo-Action':'package-workspace'},body:review.body});
   setEditing(undefined);setReview(null);setUncertain(false);
   setMessage(review.method==='DELETE'?'Paket silindi. Audit kaydı korundu.':'Paket ve audit kalıcı kaydedildi.');
   invalidateResources(packageResources);
  }catch(error){
   setError(error instanceof Error?error.message:'Paket işlemi tamamlanamadı.');
   setUncertain(!(error instanceof ApiError)||![400,401,403,404,409,422].includes(error.status));
  }finally{sending.current=false;setBusy(false);}
 }

 function prepareDelete(item:PackageRecord){
  if(item.subscriber_count!==0)return;
  start(item);
  setReview({path:'/packages/'+encodeURIComponent(item.id),method:'DELETE',before:item.fields,next:null,
   body:JSON.stringify({request_id:request.current,expected_revision:item.revision,confirmed:true})});
 }

 return <div className="screen-stack package-management">
  <PageHeading eyebrow="SENTETİK ABONELİK KATALOĞU" title="Paket Yönetimi"
   description="MikroTik profil adı yalnız eşleme etiketidir. RADIUS referansı katalog bilgisi olarak saklanır."
   actions={<button className="button-primary" disabled={busy||uncertain} onClick={()=>start(null)}>Paket oluştur</button>}/>
  {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
  {editing!==undefined&&<section className="panel">
   <h2>{review?.method==='DELETE'?'Paketi sil':editing?'Paketi düzenle':'Yeni paket'}</h2>
   {!review?<form onSubmit={event=>{
    event.preventDefault();setError('');
    const fields={...form,name:form.name.trim(),router_profile:form.router_profile?.trim()||null,
     radius_policy_ref:form.radius_policy_ref?.trim()||null,monthly_price:form.monthly_price||null};
    setReview({path:'/packages'+(editing?'/'+encodeURIComponent(editing.id):''),method:'POST',
     before:editing?.fields??null,next:fields,
     body:JSON.stringify({request_id:request.current,expected_revision:editing?.revision??0,confirmed:true,fields})});
   }}>
    <fieldset disabled={busy} className="onboarding-fields">
     <label className="form-label">Paket adı<input required maxLength={120} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
     <label className="form-label">İndirme hızı (Mbps)<input required type="number" min={1} max={1000000} value={form.download_mbps} onChange={e=>setForm({...form,download_mbps:Number(e.target.value)})}/></label>
     <label className="form-label">Yükleme hızı (Mbps)<input required type="number" min={1} max={1000000} value={form.upload_mbps} onChange={e=>setForm({...form,upload_mbps:Number(e.target.value)})}/></label>
     <label className="form-label">MikroTik profil etiketi<input maxLength={120} value={form.router_profile??''} onChange={e=>setForm({...form,router_profile:e.target.value||null})}/></label>
     <label className="form-label">RADIUS politika referansı<input maxLength={120} value={form.radius_policy_ref??''} onChange={e=>setForm({...form,radius_policy_ref:e.target.value||null})}/></label>
     <label className="form-label">Aylık ücret<input type="number" step="0.01" min={0} max="9999999999.99" value={form.monthly_price??''} onChange={e=>setForm({...form,monthly_price:e.target.value||null})}/></label>
     <label className="form-label">Para birimi<select value={form.currency??'TRY'} onChange={e=>setForm({...form,currency:e.target.value as PackageCurrency})}>
      {packageCurrencies.map(currency=><option key={currency}>{currency}</option>)}
     </select></label>
     <label className="form-label">Süre (gün)<input required type="number" min={1} max={3660} value={form.duration_days} onChange={e=>setForm({...form,duration_days:Number(e.target.value)})}/></label>
     <label><input type="checkbox" checked={form.active} onChange={e=>setForm({...form,active:e.target.checked})}/>Aktif paket</label>
     <button className="button-primary">Değişikliği gözden geçir</button>
    </fieldset>
   </form>:<>
    <PackageComparison before={review.before} next={review.next}/>
    {review.method==='DELETE'&&<p>Silme sırasında bağlı abone olup olmadığı yeniden kontrol edilir.</p>}
    {uncertain&&<p role="alert">Sonuç belirsiz. Aynı UUID ve onayla tekrar deneyin.</p>}
    <div className="package-actions">
     <button className="button-primary" disabled={busy} onClick={()=>void save()}>{review.method==='DELETE'?'Silme işlemini onayla':'Onayla ve kaydet'}</button>
     {review.method==='POST'&&<button className="button-secondary" disabled={busy||uncertain} onClick={()=>{request.current=crypto.randomUUID();setReview(null);}}>Düzenlemeye dön</button>}
    </div>
   </>}
   <button className="button-secondary" disabled={busy||uncertain} onClick={()=>{setEditing(undefined);setReview(null);setHistoryId('');setError('');}}>Kapat</button>
  </section>}
  <section className="panel">
   <div className="inventory-toolbar">
    <label className="form-label">Paket adı ara<input maxLength={120} value={query} onChange={e=>{setQuery(e.target.value);setPage(1);}}/></label>
    <label className="form-label">Durum filtresi<select value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}>
     <option value="ALL">Tümü</option><option value="ACTIVE">Aktif</option><option value="INACTIVE">Pasif</option>
    </select></label>
   </div>
   <ResourceState {...resource}/>
   {!resource.loading&&!resource.error&&resource.data&&<>
    {resource.data.items.length>0?<ul className="package-results" aria-label="Paketler">{resource.data.items.map(item=><li key={item.id}>
     <div><strong>{item.fields.name}</strong><span>{item.fields.active?'Aktif':'Pasif'} · Sürüm {item.revision}</span></div>
     <div>{packageSpeed(item.fields)}<span>{item.fields.router_profile??'Profil etiketi yok'}</span></div>
     <div>{packagePrice(item.fields.monthly_price,item.fields.currency)}<span>{item.fields.duration_days} gün</span></div>
     <div>{item.subscriber_count??'Bilinmiyor'} abone</div>
     <div className="package-actions">
      <button className="button-secondary" disabled={busy||uncertain} onClick={()=>start(item)}>Düzenle / Geçmiş</button>
      <button className="button-secondary" aria-label={item.fields.name+' paketini sil'} disabled={busy||uncertain||item.subscriber_count!==0} onClick={()=>prepareDelete(item)}>Sil</button>
     </div>
    </li>)}</ul>:<p>{resource.data.total?'Bu sayfada paket yok.':search||status!=='ALL'?'Filtrelerle eşleşen paket yok.':'Henüz kayıtlı paket yok. Paket oluştur düğmesini kullanın.'}</p>}
    <div className="table-footer"><span>{resource.data.total} paket</span>
     <button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Önceki</button><span>Sayfa {page}</span>
     <button disabled={page*pageSize>=resource.data.total} onClick={()=>setPage(p=>p+1)}>Sonraki</button>
    </div>
   </>}
  </section>
  {historyId&&<PackageHistory key={historyId} id={historyId}/>}
 </div>;
}

function PackageHistory({id}:{id:string}){
 const resource=useResource<{items:{request_id:string;action:string|null;actor_id:string;occurred_at:string;revision:number;previous:PackageFields|null;values:PackageFields|null}[]}>('/packages/'+encodeURIComponent(id)+'/audit',api,packageResources);
 return <section className="panel"><h3>Paket audit geçmişi</h3><ResourceState {...resource}/>
  {!resource.loading&&!resource.error&&resource.data?.items.map(item=><details key={item.request_id}>
   <summary>{dateTime(item.occurred_at)} · {item.actor_id} · Sürüm {item.revision}{item.action==='DELETE'?' · Silindi':''}</summary>
   <PackageComparison before={item.previous} next={item.values}/>
  </details>)}
 </section>;
}
