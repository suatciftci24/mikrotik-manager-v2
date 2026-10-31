import {useRef,useState} from 'react';
import {api} from '../lib/api';
import {connectionError,type RegisteredRouter} from '../lib/routerRegistry';
import {invalidateResources} from '../lib/resourceEvents';

export function RouterInventoryOnboarding({onClose,onSaved}:{onClose:()=>void;onSaved:(id:string)=>void}){
 const [form,setForm]=useState({name:'',management_address:'',port:'8729',credential_ref:'',description:'',site:'',model:'',routeros_version:''});
 const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const request=useRef(crypto.randomUUID()),sending=useRef(false),attempted=useRef(false);
 async function save(){
  if(sending.current||!confirmed)return;
  sending.current=true;attempted.current=true;setBusy(true);setError('');
  try{
   const result=await api<{item:RegisteredRouter}>('/router-registry/inventory',{method:'POST',headers:{'X-V2-Demo-Action':'router-onboarding'},body:JSON.stringify({...form,port:Number(form.port),request_id:request.current,confirmed:true})});
   invalidateResources(['/router-registry']);onSaved(result.item.id);
  }catch(e){setError(connectionError(e instanceof Error?e.message:''));}
  finally{sending.current=false;setBusy(false);}
 }
 return <dialog open className="expiry-editor"><h2>Bağlantısız router envanteri</h2><p>Doğrulama bekliyor · PENDING_VERIFICATION. Bu kayıt bağlantı izni vermez; probe ve gerçek PPPoE okuması kapalıdır. Model ve sürüm operatör beyanıdır.</p><form onSubmit={e=>{e.preventDefault();void save();}}>
 {Object.entries({name:'Router adı',management_address:'Yönetim IPv4',port:'API-SSL portu',credential_ref:'Mevcut V2 credential_ref (UUID)',description:'Açıklama',site:'Konum',model:'Bildirilen model',routeros_version:'Bildirilen RouterOS sürümü'}).map(([key,label])=><label className="form-label" key={key}>{label}<input value={form[key as keyof typeof form]} required={['name','management_address','port','credential_ref'].includes(key)} maxLength={key==='description'?1000:key==='model'?80:key==='routeros_version'?40:120} disabled={busy} onChange={e=>{if(attempted.current){request.current=crypto.randomUUID();attempted.current=false;}setForm({...form,[key]:e.target.value});}}/></label>)}
 <p>Yalnız güvenli V2 kaynağının mevcut referansını girin. Parola veya özel anahtar girmeyin.</p>
 <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>Yalnız envanter kaydı oluşturmayı onaylıyorum.</label>
 {error&&<p role="alert">{error}</p>}<button className="button-primary" disabled={!confirmed||busy} type="submit">{busy?'Kaydediliyor…':'Doğrulama bekleyen kaydı oluştur'}</button><button type="button" className="button-secondary" disabled={busy} onClick={onClose}>Kapat</button>
 </form></dialog>;
}
