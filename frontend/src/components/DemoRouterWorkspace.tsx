import {CompactRouterList} from './CompactRouterList';
import {useCompactSubscribers} from './CompactSubscriberList';
import {RouterDeviceCenter} from './RouterDeviceCenter';
import {useEffect,useState,useRef} from 'react';
import {api} from '../lib/api';
import {useResource} from '../lib/useResource';
import {invalidateResources} from '../lib/resourceEvents';
import {ResourceState} from './Resource';
import {RouterHistory} from './RouterHistory';
import {managementLabels,simulationLabels,routerFieldLabels,type ManagementStatus,type SimulationStatus,type RouterEvent} from '../lib/routerCenter';

type Fields={name:string;management_address:string;model:string;site:string;identity:string;routeros_version:string;
 description:string;management_status:ManagementStatus;simulated_status:SimulationStatus;simulated_last_seen_at:string|null};
type Item={id:string;revision:number;kind:'DEMO_ROUTER';fields:Fields;is_demo:true;device_connected:false};
const dependencies=['/router-workspace/routers'] as const;
const empty:Fields={name:'',management_address:'192.0.2.10',model:'Sentetik model',site:'',identity:'',
 routeros_version:'',description:'',management_status:'ACTIVE',simulated_status:'UNKNOWN',simulated_last_seen_at:null};
const textFields={name:120,management_address:15,model:120,site:120,identity:120,routeros_version:60} as const;

function StatusOptions({labels}:{labels:Record<string,string>}){
 return <>{Object.entries(labels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</>;
}
const headers={'X-V2-Demo-Action':'router-workspace'};
export function DemoRouterWorkspace({startCreate=0,detailId,onOpen,onBack,readOnly=false}:{readOnly?:boolean;startCreate?:number;detailId?:string;onOpen?:(id:string)=>void;onBack?:()=>void}){
 const compact=useCompactSubscribers(),pageSize=compact?5:25;
 const requestId=useRef(crypto.randomUUID());
 const [query,setQuery]=useState(''),[page,setPage]=useState(1),[selected,setSelected]=useState<Item|null>(null),[editing,setEditing]=useState(false),[form,setForm]=useState<Fields>(empty),[busy,setBusy]=useState(false),[error,setError]=useState(''),[confirmDelete,setConfirmDelete]=useState(false);
 const [management,setManagement]=useState(''),[simulation,setSimulation]=useState(''),[showHistory,setShowHistory]=useState(false);
 const filters=new URLSearchParams({query,page:String(page),page_size:String(pageSize)});
 if(management)filters.set('management_status',management);
 if(simulation)filters.set('simulated_status',simulation);
 const resource=useResource<{items:Item[];total:number}>(`/router-workspace/routers?${filters}`,api,dependencies);
 function change<K extends keyof Fields>(key:K,value:Fields[K]){
  requestId.current=crypto.randomUUID();
  setForm(previous=>({...previous,[key]:value}));
 }
 useEffect(()=>{if(startCreate){requestId.current=crypto.randomUUID();setSelected(null);setForm({...empty});setEditing(true);setError('');}},[startCreate]);
 useEffect(()=>{
  if(!detailId||readOnly)return;
  const controller=new AbortController();
  setSelected(null);setEditing(false);
  void detail(detailId,controller.signal);
  return ()=>controller.abort();
 },[detailId,readOnly]);
 function open(item?:Item){requestId.current=crypto.randomUUID();setSelected(item??null);setForm(item?item.fields:{...empty});setEditing(true);setError('');setConfirmDelete(false);}
 async function save(event:React.FormEvent){event.preventDefault();if(busy||readOnly)return;setBusy(true);setError('');
  try{const item=await api<Item>('/router-workspace/routers'+(selected?'/'+encodeURIComponent(selected.id):''),{method:'POST',headers,body:JSON.stringify({request_id:requestId.current,fields:form,expected_revision:selected?.revision??0,confirmed:true})});setSelected(onOpen&&!detailId?null:item);setEditing(false);if(!detailId)onOpen?.(item.id);invalidateResources(['/router-workspace/routers']);}
  catch(e){setError(e instanceof Error?e.message:'Sentetik kayıt kaydedilemedi.');}finally{setBusy(false);}}
 async function remove(){if(!selected||!confirmDelete||busy||readOnly)return;setBusy(true);setError('');try{await api('/router-workspace/routers/'+encodeURIComponent(selected.id)+'/delete',{method:'POST',headers,body:JSON.stringify({expected_revision:selected.revision,confirmed:true})});setSelected(null);setConfirmDelete(false);if(detailId)onBack?.();invalidateResources(['/router-workspace/routers']);}catch(e){setError(e instanceof Error?e.message:'Kayıt silinemedi.');}finally{setBusy(false);}}
 async function detail(id:string,signal?:AbortSignal){
  setError('');
  try{
   const item=await api<Item>('/router-workspace/routers/'+encodeURIComponent(id),{signal});
   if(!signal?.aborted){setSelected(item);setConfirmDelete(false);}
  }catch(error){
   if(!signal?.aborted)setError(error instanceof Error?error.message:'Detay alınamadı.');
  }
 }
 const editor=<form className="router-workspace-form" onSubmit={save}><fieldset disabled={busy} className="onboarding-fields">
  <legend>{selected?'Sentetik kaydı düzenle':'Yeni sentetik router'}</legend>
  {(Object.keys(textFields) as (keyof typeof textFields)[]).map(key=><label key={key} className="form-label">{routerFieldLabels[key]}
   <input required={key==='name'||key==='management_address'||key==='model'} maxLength={textFields[key]} value={form[key]} onChange={e=>change(key,e.target.value)}/>
  </label>)}
  <label className="form-label">Açıklama<textarea maxLength={500} value={form.description} onChange={e=>change('description',e.target.value)}/></label>
  <label className="form-label">Yönetim durumu<select value={form.management_status} onChange={e=>change('management_status',e.target.value as ManagementStatus)}><StatusOptions labels={managementLabels}/></select></label>
  <label className="form-label">Simüle durum<select value={form.simulated_status} onChange={e=>change('simulated_status',e.target.value as SimulationStatus)}><StatusOptions labels={simulationLabels}/></select></label>
  <label className="form-label">Sentetik son görülme (UTC)<input type="datetime-local" step="1" value={form.simulated_last_seen_at?.slice(0,19)??''} onChange={e=>change('simulated_last_seen_at',e.target.value?e.target.value+'Z':null)}/></label>
  <small>Simüle durum ve son görülme örnek veridir. Bağlantı ölçümü yapılmaz.</small>
  <p>Örnek IPv4 ağları: 192.0.2.0/24, 198.51.100.0/24 ve 203.0.113.0/24.</p>
  <button className="button-primary">Sentetik kaydı kaydet</button><button type="button" className="button-secondary" onClick={()=>setEditing(false)}>Vazgeç</button>
 </fieldset></form>;
 if(detailId&&readOnly)return <RouterDeviceCenter id={detailId} onBack={()=>onBack?.()}/>;
 if(detailId)return <div className="screen-stack"><RouterDeviceCenter id={detailId} onBack={()=>onBack?.()} actions={selected&&<button className="button-secondary" disabled={busy} onClick={()=>open(selected)}>Sentetik kaydı düzenle</button>}/>{error&&<p role="alert" className="form-error">{error}</p>}{editing&&editor}{selected&&<div className="panel registry-detail"><h2>Sentetik kayıt yönetimi</h2><p>Yalnız bu yerel sentetik kayıt değişir; cihaz bağlantısı başlatılmaz.</p><label className="registry-consent"><input type="checkbox" checked={confirmDelete} disabled={busy} onChange={e=>setConfirmDelete(e.target.checked)}/>Yalnız bu sentetik kaydın silinmesini onaylıyorum.</label><button className="button-secondary" disabled={busy||!confirmDelete} onClick={()=>void remove()}>Sentetik kaydı sil</button></div>}</div>;
 return <section className="panel registry-detail router-mobile-list" aria-label="Kalıcı sentetik routerlar"><h2>Routerlar</h2>{readOnly&&<p>Yalnız yetkili routerlar · Salt okunur</p>}<details className="technical-info"><summary>Teknik bilgiler</summary><p>Kalıcı V2.6 sentetik kayıtları. Cihaz bağlantısı ve canlı ölçüm yoktur.</p></details>
 <div className="inventory-toolbar"><label className="form-label">Sentetik router ara<input maxLength={120} value={query} onChange={e=>{setQuery(e.target.value);setPage(1);}}/></label>
 <label className="form-label">Yönetim durumu<select value={management} onChange={e=>{setManagement(e.target.value);setPage(1);}}><option value="">Tümü</option><StatusOptions labels={managementLabels}/></select></label>
 <label className="form-label">Simüle durum<select value={simulation} onChange={e=>{setSimulation(e.target.value);setPage(1);}}><option value="">Tümü</option><StatusOptions labels={simulationLabels}/></select></label>
 {!readOnly&&<button className="button-secondary" disabled={busy} onClick={()=>open()}>Router ekle</button>}<button className="button-secondary" onClick={resource.retry}>Listeyi yenile</button></div>
 <ResourceState {...resource}/>{error&&<p role="alert" className="form-error">{error}</p>}
 {editing?editor:selected?<div><h3>{selected.fields.name} · SENTETİK</h3><dl className="registry-facts">{Object.entries(selected.fields).map(([key,value])=><div key={key}><dt>{routerFieldLabels[key as keyof Fields]}</dt><dd>{key==='management_status'?managementLabels[value as ManagementStatus]:key==='simulated_status'?simulationLabels[value as SimulationStatus]:value||'Belirtilmemiş'}</dd></div>)}</dl><p>Revizyon: {selected.revision} · Kalıcı yerel kayıt · Cihaz doğrulanmadı</p>{!readOnly&&<><button className="button-secondary" disabled={busy} onClick={()=>open(selected)}>Sentetik kaydı düzenle</button><label className="registry-consent"><input type="checkbox" checked={confirmDelete} disabled={busy} onChange={e=>setConfirmDelete(e.target.checked)}/>Yalnız bu sentetik kaydın silinmesini onaylıyorum.</label><button className="button-secondary" disabled={busy||!confirmDelete} onClick={()=>void remove()}>Sentetik kaydı sil</button></>}<button className="button-secondary" onClick={()=>setSelected(null)}>Detayı kapat</button></div>:null}
 {!resource.loading&&!resource.error&&resource.data&&<><CompactRouterList rows={resource.data.items.map(item=>({id:item.id,name:item.fields.name,status:`Yönetim: ${managementLabels[item.fields.management_status??'ACTIVE']} · Simüle: ${simulationLabels[item.fields.simulated_status??'UNKNOWN']}`}))} onOpen={id=>onOpen?onOpen(id):void detail(id)} page={page} onPage={setPage} total={resource.data.total}/><div className="table-scroll"><table className="data-table"><thead><tr><th>SENTETİK ROUTER</th><th>ÖRNEK IP</th><th>MODEL</th><th>YÖNETİM</th><th>SİMÜLE DURUM</th></tr></thead><tbody>{resource.data.items.map(item=><tr key={item.id}><td><button className="record-link" onClick={()=>onOpen?onOpen(item.id):void detail(item.id)}>{item.fields.name}</button></td><td>{item.fields.management_address}</td><td>{item.fields.model}</td><td>{managementLabels[item.fields.management_status??'ACTIVE']}</td><td>{simulationLabels[item.fields.simulated_status??'UNKNOWN']}</td></tr>)}</tbody></table></div>{!resource.data.total&&<p>Henüz eşleşen sentetik kayıt yok.</p>}<div className="table-footer"><span>{resource.data.total} sentetik kayıt</span><button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Önceki</button><span>{page}</span><button disabled={page*pageSize>=resource.data.total} onClick={()=>setPage(p=>p+1)}>Sonraki</button></div></>}
 {!readOnly&&<details onToggle={event=>setShowHistory(event.currentTarget.open)}><summary>Silinen sentetik routerlar</summary>{showHistory&&<DeletedRouterHistory/>}</details>}
 </section>;
}

function DeletedRouterHistory(){
 const history=useResource<RouterEvent[]>('/router-workspace/deleted-routers/history',api,dependencies);
 return <><ResourceState {...history}/>{!history.loading&&!history.error&&history.data&&<RouterHistory events={history.data}/>}</>;
}
