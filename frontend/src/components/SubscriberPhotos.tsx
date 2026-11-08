import {useState,type ChangeEvent} from 'react';
import {api} from '../lib/api';
import {assertSubscriberPhotos,subscriberPhotoImagePath,subscriberPhotosPath,type SubscriberPhotoCollection} from '../lib/subscriberPhotos';
import {useResource} from '../lib/useResource';
import {ResourceState,dateTime} from './Resource';

export function SubscriberPhotos({id,source,accessType,canManage}:{id:string;source:'LOCAL'|'RADIUS';accessType:'PPPOE'|'HOTSPOT';canManage:boolean}){
 const path=subscriberPhotosPath(id);
 const resource=useResource<SubscriberPhotoCollection>(path,async(url,init)=>assertSubscriberPhotos(await api<SubscriberPhotoCollection>(url,init),id,source,accessType),['/subscriber-center']);
 const [uploading,setUploading]=useState(false),[uploadError,setUploadError]=useState(''),[deleteId,setDeleteId]=useState<string|null>(null),[deleting,setDeleting]=useState(false),[selected,setSelected]=useState<string|null>(null);
 async function upload(event:ChangeEvent<HTMLInputElement>){
  const file=event.currentTarget.files?.[0];event.currentTarget.value='';if(!file)return;
  setUploadError('');setUploading(true);
  try{await api(path,{method:'POST',headers:{'X-V2-Demo-Action':'subscriber-photos','Content-Type':file.type||'application/octet-stream'},body:file});resource.retry();}
  catch(error){setUploadError(error instanceof Error?error.message:'Fotoğraf yüklenemedi.');}
  finally{setUploading(false);}
 }
 async function remove(photoId:string){
  setDeleting(true);setUploadError('');
  try{await api(path+'/'+photoId,{method:'DELETE',headers:{'X-V2-Demo-Action':'subscriber-photos'}});if(selected===photoId)setSelected(null);setDeleteId(null);resource.retry();}
  catch(error){setUploadError(error instanceof Error?error.message:'Fotoğraf silinemedi.');}
  finally{setDeleting(false);}
 }
 const data=resource.data&&!resource.loading&&!resource.error?resource.data:undefined;
 return <section className="panel subscriber-photos" aria-labelledby="subscriber-photos-title">
  <div className="panel-title"><h3 id="subscriber-photos-title">Kurulum / İş Fotoğrafları</h3><span className="demo-chip">SENTETİK · V2.6</span></div>
  <p>Yalnız bu aboneye ait JPEG/PNG görüntüleri. Sunucuda yeniden kodlanır; dosya adı ve görüntü metadata'sı saklanmaz.</p>
  {canManage&&<label className="button-secondary subscriber-photo-upload">{uploading?'Fotoğraf yükleniyor…':'Fotoğraf ekle'}<input aria-label="Kurulum fotoğrafı seç" type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" disabled={uploading||deleting||!data||data.items.length>=20} onChange={upload}/></label>}
  {(uploading||deleting)&&<p role="status">{uploading?'Görüntü doğrulanıyor ve güvenli biçimde kaydediliyor…':'Fotoğraf siliniyor…'}</p>}
  {uploadError&&<p role="alert" className="form-error">{uploadError}</p>}
  <ResourceState {...resource}/>
  {data&&data.items.length===0&&<p className="missing-data">Henüz bu aboneye ait kurulum fotoğrafı yok.</p>}
  {data&&data.items.length>0&&<div className="subscriber-photo-grid" aria-label="Abone kurulum fotoğrafları">{data.items.map(photo=><article className="subscriber-photo-card" key={photo.id}>
   <button className="subscriber-photo-preview" aria-label="Fotoğrafı tam boyutta görüntüle" onClick={()=>setSelected(photo.id)}><img loading="lazy" src={'/api/v1'+subscriberPhotoImagePath(id,photo.id,'thumbnail')} alt="Kurulum / iş fotoğrafı"/><span>{dateTime(photo.created_at)}</span></button>
   <div><small>{Math.max(1,Math.round(photo.size_bytes/1024))} KiB · JPEG</small>{canManage&&<button className="button-secondary" disabled={deleting||uploading} onClick={()=>setDeleteId(photo.id)}>Sil</button>}</div>
   {deleteId===photo.id&&<div className="subscriber-photo-confirm" role="alertdialog" aria-label="Fotoğraf silme onayı"><p>Bu aboneye ait fotoğraf kalıcı olarak silinsin mi?</p><button className="button-secondary" disabled={deleting} onClick={()=>setDeleteId(null)}>Vazgeç</button><button className="button-secondary subscriber-photo-delete-confirm" disabled={deleting} onClick={()=>remove(photo.id)}>Fotoğrafı sil</button></div>}
  </article>)}</div>}
  {selected&&data?.items.some(photo=>photo.id===selected)&&<div className="subscriber-photo-lightbox" role="dialog" aria-modal="true" aria-label="Tam boyutlu abone fotoğrafı"><button className="button-secondary" onClick={()=>setSelected(null)}>Görüntüyü kapat</button><img src={'/api/v1'+subscriberPhotoImagePath(id,selected,'full')} alt="Kurulum / iş fotoğrafı tam boyut"/></div>}
  {canManage&&<p className="daily-description">En fazla 20 fotoğraf; dosya başına 10 MiB ve 24 megapiksel. Silme işlemi geri alınamaz.</p>}
 </section>;
}
