import {useEffect,useState} from 'react';
import {api,ApiError} from '../lib/api';
import {useIdentity} from '../lib/permissions';
import {identityStamp,pendingIdentity,pendingOperations,recoverPending,type PendingOperation} from '../lib/pendingSubscriberOperations';
import {invalidateResources} from '../lib/resourceEvents';
import {subscriberSaveDependencies} from '../lib/useSubscriberSave';
export function PendingSubscriberOperations(){
 const user=useIdentity(),stamp=identityStamp(user);
 const [items,setItems]=useState<PendingOperation[]>([]),[messages,setMessages]=useState<string[]>([]),[retry,setRetry]=useState(0);
 useEffect(()=>{
  pendingIdentity(user);setMessages([]);
  const controller=new AbortController();let busy=false;
  const sync=async()=>{
   if(busy)return;busy=true;
   const entries=pendingOperations().filter(i=>i.actor===user?.id&&user.role_code==='ADMIN'&&user.active!==false);setItems(entries);
   try{for(const item of entries){
    if(controller.signal.aborted)break;
    try{
     const status=await recoverPending(item,AbortSignal.any([controller.signal,AbortSignal.timeout(15000)]),api);
     if(controller.signal.aborted)break;
     if(status==='DENIED'){controller.abort();setItems([]);setMessages([]);break;}
     if(status!=='UNKNOWN'){setMessages(m=>[...m,`${item.id}: ${status==='SUCCESS'?'İşlem tamamlandı':'İşlem başarısız olarak kaydedildi'}`]);invalidateResources([...subscriberSaveDependencies]);}
    }catch(e){if(e instanceof ApiError&&[401,403].includes(e.status)){pendingIdentity(null);controller.abort();setItems([]);setMessages([]);break;}}
   }}finally{busy=false;if(!controller.signal.aborted)setItems(pendingOperations().filter(i=>i.actor===user?.id&&user.role_code==='ADMIN'));}
  };
  const changed=(event:StorageEvent)=>{if(event.key===null||event.key?.startsWith('v2.pending-subscriber.')){controller.abort();setItems([]);setMessages([]);setRetry(r=>r+1);}};
  // A new POST is tracked immediately, but recovered only after reload or explicit query.
  const added=()=>setItems(pendingOperations().filter(i=>i.actor===user?.id));
  void sync();window.addEventListener('storage',changed);window.addEventListener('v2-pending-change',added);
  return()=>{controller.abort();window.removeEventListener('storage',changed);window.removeEventListener('v2-pending-change',added);};
 },[stamp,retry]);
 if(!items.length&&!messages.length)return null;
 return <section className="panel" aria-label="Bekleyen işlem sonuçları"><h2>Bekleyen işlem sonuçları</h2>{messages.map(m=><p role="status" key={m}>{m}</p>)}{items.map(i=><p key={i.id}>{i.id} · Sonuç henüz doğrulanamadı.</p>)}{!!items.length&&<button className="button-secondary" onClick={()=>setRetry(r=>r+1)}>Kayıtlı sonuçları sorgula</button>}</section>;
}
