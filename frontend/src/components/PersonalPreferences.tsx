import {useState} from 'react';
import {api} from '../lib/api';
import {useResource} from '../lib/useResource';
import {ResourceState} from './Resource';
import type {Presentation} from '../lib/presentation';
export type PersonalValues={theme:Presentation['theme']|null;page_size:Presentation['page_size']|null;notifications_enabled:boolean|null;notification_levels:string[]|null};
export function PersonalPreferences(){
 const resource=useResource<{values:Presentation;personal:PersonalValues;revision:number;storage_ready:boolean}>('/preferences');
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function change(patch:Partial<PersonalValues>){
  if(!resource.data||busy)return;setBusy(true);setError('');
  try{await api('/preferences',{method:'POST',headers:{'X-V2-Demo-Action':'ui-preferences'},body:JSON.stringify({request_id:crypto.randomUUID(),expected_revision:resource.data.revision,confirmed:true,values:{...resource.data.personal,...patch}})});resource.retry();window.dispatchEvent(new Event('v2-preferences-change'));}
  catch(e){setError(e instanceof Error?e.message:'Tercih kaydedilemedi.');}finally{setBusy(false);}
 }
 const data=resource.data;
 return <details className="personal-preferences"><summary>Kişisel bildirim ve arayüz tercihleri</summary><ResourceState {...resource}/>{error&&<p role="alert">{error}</p>}{data&&!resource.loading&&<>
 <p>Yalnız sizin sunum tercihinizdir. Okundu ve ACK kaydı değiştirilmez; boş seçim sistem varsayılanını izler.</p>
 <label>Panel bildirimleri<select aria-label="Kişisel bildirim görünürlüğü" disabled={busy||!data.storage_ready} value={data.personal.notifications_enabled===null?'INHERIT':String(data.personal.notifications_enabled)} onChange={e=>change({notifications_enabled:e.target.value==='INHERIT'?null:e.target.value==='true'})}><option value="INHERIT">Sistem varsayılanı</option><option value="true">Göster</option><option value="false">Gizle</option></select></label>
 <label>Tema<select aria-label="Kişisel varsayılan tema" disabled={busy||!data.storage_ready} value={data.personal.theme??'INHERIT'} onChange={e=>change({theme:e.target.value==='INHERIT'?null:e.target.value as Presentation['theme']})}><option value="INHERIT">Sistem varsayılanı</option><option value="system">İşletim sistemi</option><option value="light">Beyaz</option><option value="dark">Gece</option></select></label>
 <label>Sayfa boyutu<select aria-label="Kişisel sayfa boyutu" disabled={busy||!data.storage_ready} value={data.personal.page_size??'INHERIT'} onChange={e=>change({page_size:e.target.value==='INHERIT'?null:Number(e.target.value) as Presentation['page_size']})}><option value="INHERIT">Sistem varsayılanı</option>{[10,25,50].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
 <div aria-label="Kişisel bildirim önem seviyeleri">{['P1','P2','P3','P4'].map(level=><label key={level}><input type="checkbox" aria-label={'Kişisel '+level} checked={(data.personal.notification_levels??data.values.notification_levels).includes(level)} disabled={busy||!data.storage_ready} onChange={e=>change({notification_levels:e.target.checked?[...(data.personal.notification_levels??data.values.notification_levels),level]:(data.personal.notification_levels??data.values.notification_levels).filter(v=>v!==level)})}/>{level}</label>)}</div>
 <button className="button-secondary" disabled={busy||!data.storage_ready} onClick={()=>change({theme:null,page_size:null,notifications_enabled:null,notification_levels:null})}>Kişisel tercihleri varsayılana bağla</button>
 {!data.storage_ready&&<p>Tercih deposu hazır değil; yazma kapalı.</p>}</>}</details>;
}
