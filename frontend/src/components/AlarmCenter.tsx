import {usePresentation} from '../lib/presentation';
import {PersonalPreferences} from './PersonalPreferences';
import {turkeyToday} from '../lib/expiry';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { useResource } from '../lib/useResource';
import { invalidateResources } from '../lib/resourceEvents';
import { alarmFilter,alarmHash,alarmQuery,alarmKinds,alarmStates,type AlarmFilter,type AlarmPage,type CentralAlarm } from '../lib/alarms';
import { ResourceState,Facts,dateTime } from './Resource';
const dependencies=['/alarms','/routers','/subscribers','/router-events'] as const;
const getHash=()=>typeof window==='undefined'?'':window.location.hash;
export function AlarmCenter({notifications=false,compact=false}:{notifications?:boolean;compact?:boolean}){
 const presentation=usePresentation();
 const [filter,setFilter]=useState(()=>alarmFilter(getHash()));
 const resource=useResource<AlarmPage>('/alarms?'+alarmQuery(compact||notifications?{...alarmFilter(''),state:compact?'ACTIVE':'ALL'}:filter)+(compact||notifications?'&order=LATEST&page_size=5':'')+(notifications?'&levels='+encodeURIComponent(presentation.notification_levels.join(',')||'NONE'):''),undefined,dependencies);
 const [selected,setSelected]=useState<string|null>(()=>new URLSearchParams(getHash().slice(1)).get('alarm_id'));
 useEffect(()=>{const read=()=>{setFilter(alarmFilter(getHash()));setSelected(new URLSearchParams(getHash().slice(1)).get('alarm_id'));};window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[]);
 useEffect(()=>{const tick=()=>{if(!document.hidden)resource.retry();};const timer=window.setInterval(tick,60000);window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);return()=>{window.clearInterval(timer);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};},[resource.retry]);
 const change=(patch:Partial<AlarmFilter>)=>{const next={...filter,...patch,page:patch.page??1};setFilter(next);setSelected(null);window.history.replaceState(null,'',alarmHash(next));};
 const selectAlarm=(id:string|null)=>{setSelected(id);const params=new URLSearchParams(getHash().slice(1));if(id)params.set('alarm_id',id);else params.delete('alarm_id');window.history.replaceState(null,'',window.location.pathname+window.location.search+'#'+params);};
 const data=resource.data,error=resource.error||(data&&data.is_demo!==true?'Sentetik kaynak doğrulanamadı.':undefined);
 return <section className="panel alarm-center" aria-label={notifications?'Panel içi alarm bildirimleri':compact?'Dashboard alarm özeti':'Merkezi Alarm Yönetimi'}>
  <div className="panel-title"><h2>{notifications?'Alarm bildirimleri':compact?'Merkezi alarm özeti':'Merkezi Alarm Yönetimi'}</h2><span className="demo-chip">SENTETİK</span></div>
  <p>ACK yalnız operatör onayıdır; arızayı çözmez. Okundu bilgisi kişiye özeldir ve ACK’ten ayrıdır. Harici bildirim gönderilmez.</p>
  <button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Alarmları yenile</button>
  {notifications&&<PersonalPreferences/>}
  {notifications&&!presentation.notifications_enabled&&<p role="status">Bildirim listesi kişisel/sistem tercihiyle gizli. Alarm Merkezi ve ACK durumu değişmedi.</p>}
  <ResourceState {...resource} error={error}/>
  {data&&!resource.loading&&!error&&(!notifications||presentation.notifications_enabled)&&<>
   <p>Genel açık kritik (P1/P2, ACK ve iyileşen dahil): <strong>{data.summary.critical}</strong> · Aktif: {data.summary.active} · Okunmamış: {data.summary.unread}</p>
   <p>Kaynak okuması: {dateTime(data.generated_at)}. {data.coverage.note}</p>
   {!data.coverage.connection_available&&<p className="missing-data">Veri yok: internet/WAN olay kaynağı bağlı değil.</p>}{!data.coverage.ipsec_available&&<p className="missing-data">IPsec gözlemi: Veri yok / bilinmiyor; alarm uydurulmaz.</p>}
   {!data.storage_ready&&<p role="status">Alarm onay/okundu deposu hazır değil; yalnız kaynak okunur. Açık yerel alarms-init bakımı gerekir.</p>}
   {!compact&&!notifications&&<div className="router-report-controls">
    <label>Router<select aria-label="Alarm router filtresi" value={filter.router_id} onChange={e=>change({router_id:e.target.value})}><option value="">Tüm routerlar</option>{data.routers.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
    <label>Önem<select aria-label="Alarm önem filtresi" value={filter.severity} onChange={e=>change({severity:e.target.value})}>{['ALL','P1','P2','P3','P4'].map(v=><option key={v}>{v}</option>)}</select></label>
    <label>Durum<select aria-label="Alarm durum filtresi" value={filter.state} onChange={e=>change({state:e.target.value})}><option value="ALL">Tümü</option><option value="ACTIVE">Aktif</option>{Object.entries(alarmStates).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label>
    <label>Tür<select aria-label="Alarm tür filtresi" value={filter.kind} onChange={e=>change({kind:e.target.value})}><option value="ALL">Tümü</option>{Object.entries(alarmKinds).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label>
    <label>Başlangıç<input type="date" aria-label="Alarm başlangıç tarihi" value={filter.start} onChange={e=>change({start:e.target.value})}/></label><label>Bitiş<input type="date" aria-label="Alarm bitiş tarihi" value={filter.end} onChange={e=>change({end:e.target.value})}/></label>
    <button className="button-secondary" onClick={()=>change(alarmFilter(''))}>Alarm filtrelerini temizle</button>
   </div>}
   {!compact&&!notifications&&<p>Tarih filtresi son kaynak zamanına uygulanır. PPPoE bitiş gününden kesin ilk/son alarm saati türetilmez; zamanı olmayan kayıtlar tarih filtresinde gösterilmez.</p>}
   {data.items.length?<div className="table-scroll" role="region" tabIndex={0} aria-label="Merkezi alarm tablosu"><table className="data-table"><thead><tr><th>ÖNEM / OLAY</th><th>ROUTER</th><th>DURUM / BİLDİRİM</th><th>İLK / SON KAYNAK ZAMANI</th><th>TEKRAR</th></tr></thead><tbody>{data.items.slice(0,compact||notifications?5:data.page_size).map(alarm=><tr key={alarm.id}><td>{compact||notifications?<a className="record-link" href={alarmHash({...alarmFilter(''),router_id:alarm.router_id},alarm.id)}>{alarm.severity} · {alarmKinds[alarm.kind]}</a>:<button className="record-link" onClick={()=>selectAlarm(alarm.id)} aria-label={`${alarm.title} · ${alarm.id} detayını aç`}>{alarm.severity} · {alarmKinds[alarm.kind]}</button>}</td><td><a href={'#'+new URLSearchParams({module:'routers',id:alarm.router_id})}>{data.routers.find(r=>r.id===alarm.router_id)?.name??alarm.router_id}</a></td><td>{alarm.source_available===false?'Son bilinen: ':''}{alarmStates[alarm.state]} · {alarm.notification_read?'Okundu':'Okunmadı'}</td><td>{dateTime(alarm.first_seen)} / {dateTime(alarm.last_seen)}</td><td>{alarm.repeat_count}</td></tr>)}</tbody></table></div>:<p className="table-empty">Bu kapsamda kaynak alarmı yok. Eksik veri sağlıklı sistem kanıtı değildir.</p>}
   <div className="daily-links"><a className="button-secondary" href="#module=operations">Alarm Merkezi’ni aç</a>{!compact&&!notifications&&<><span>{data.total} alarm · Sayfa {filter.page}</span><button className="button-secondary" disabled={filter.page===1} onClick={()=>change({page:filter.page-1})}>Önceki alarm sayfası</button><button className="button-secondary" disabled={filter.page*data.page_size>=data.total} onClick={()=>change({page:filter.page+1})}>Sonraki alarm sayfası</button></>}</div>
  </>}
  {notifications&&!presentation.notifications_enabled&&<a href="#module=operations">Alarm Merkezi’ni aç</a>}
  {selected&&!compact&&!notifications&&!error&&<AlarmDialog id={selected} canAck={data?.can_ack===true} storage={data?.storage_ready===true} onClose={()=>selectAlarm(null)}/>}
 </section>;
}
function AlarmDialog({id,canAck,storage,onClose}:{id:string;canAck:boolean;storage:boolean;onClose:()=>void}){
 const resource=useResource<{item:CentralAlarm;can_ack:boolean}>('/alarms/'+encodeURIComponent(id),undefined,dependencies);
 const dialog=useRef<HTMLDialogElement>(null),sending=useRef(false);
 const [review,setReview]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 const request=useRef<{ACK:string;READ:string}>({ACK:crypto.randomUUID(),READ:crypto.randomUUID()});
 useEffect(()=>{const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{node?.close();origin?.focus();};},[]);
 const alarm=resource.data?.item;
 async function action(type:'ACK'|'READ'){
  if(!alarm||sending.current)return;sending.current=true;setPending(true);setError('');
  try{await api('/alarms/'+encodeURIComponent(id)+(type==='ACK'?'/ack':'/read'),{method:'POST',headers:{'X-V2-Demo-Action':type==='ACK'?'alarm-ack':'alarm-read'},body:JSON.stringify({request_id:request.current[type],occurrence_id:alarm.occurrence_id,confirmed:true})});setMessage(type==='ACK'?'Operatör onayı kaydedildi; kaynak arızası çözülmüş sayılmadı.':'Bildirim okundu; alarm onayı değişmedi.');invalidateResources(['/alarms']);}
  catch(e){setError(e instanceof Error?e.message:'İşlem tamamlanamadı.');}finally{sending.current=false;setPending(false);}
 }
 return <dialog ref={dialog} className="expiry-dialog alarm-dialog" aria-labelledby="central-alarm-title" onCancel={e=>{e.preventDefault();if(!pending)onClose();}}>
  <h2 id="central-alarm-title">Alarm kanıtı ve onay geçmişi</h2><ResourceState {...resource}/>
  {alarm&&!resource.error&&<>{alarm.source_available===false&&<p role="status">Kaynak olayı artık projeksiyonda yok; yalnız son kayıtlı kanıt ve audit gösteriliyor. Çözülme zamanı/durumu çıkarılmadı.</p>}<Facts items={[["Kimlik",alarm.id],["Tür",alarmKinds[alarm.kind]],["Önem",alarm.severity],["Durum",alarmStates[alarm.state]],["Kaynak durumu",alarm.source_state],["İlk görülme",dateTime(alarm.first_seen)],["Son kaynak güncellemesi",dateTime(alarm.last_seen)],["Farklı kaynak olayı / tekrar",alarm.repeat_count],["Kanıt",alarm.evidence],["Kaynak",alarm.source],["Kaynak olay kimliği",alarm.source_id],["Kesinti süresi",alarm.lifecycle?.duration_seconds===null||alarm.lifecycle?.duration_seconds===undefined?'Hesaplanamıyor':alarm.lifecycle.duration_seconds+' sn'],["Operatör onayı",alarm.acknowledgement?alarm.acknowledgement.actor_id+' · '+dateTime(alarm.acknowledgement.occurred_at):'Yok'],["Bildirim",alarm.notification_read?'Okundu':'Okunmadı']]}/>
   <div className="daily-links"><a className="button-secondary" href={'#'+new URLSearchParams({module:'routers',id:alarm.router_id})}>Router detayını aç</a>{alarm.subscriber_id&&<a className="button-secondary" href={'#'+new URLSearchParams({module:'subscribers',id:alarm.subscriber_id})}>Abone detayını aç</a>}<a className="button-secondary" href={'#'+new URLSearchParams({module:'mikajani',...(alarm.mika?{event:alarm.mika.id}:{})})}>MikAjanı kanıtlarını aç</a><a className="button-secondary" href={'#'+new URLSearchParams({module:'dashboard',view:'OPERATIONS_REPORT',router_id:alarm.router_id,category:alarm.source==='mikajani'?'MIKA':alarm.source==='router-events'?'CONNECTION':'AUDIT',...(alarm.last_seen?{start:turkeyToday(new Date(alarm.last_seen)),end:turkeyToday(new Date(alarm.last_seen))}:{}),...(alarm.subscriber_id?{subscriber_id:alarm.subscriber_id}:{})})}>Operasyon raporunu aç</a></div>
   <h3>Alarm işlem audit geçmişi</h3>{alarm.action_history.length?<ol className="subscriber-history">{alarm.action_history.map(a=><li key={a.id}>{a.action==='ACK'?'Operatör onayı':'Bildirim okundu'} · {a.actor_id} · {dateTime(a.occurred_at)} · {a.id}</li>)}</ol>:<p>Henüz kayıtlı alarm işlemi yok.</p>}
   <button className="button-secondary" disabled={pending||!storage||alarm.notification_read} onClick={()=>action('READ')}>Bildirimi okundu işaretle</button>
   {canAck&&resource.data?.can_ack===true&&alarm.source_available!==false&&alarm.state!=='RESOLVED'?(review?<><p>Onay yalnız bu kaynak olayı içindir. Arıza çözülmeyecek; adınız ve zaman audit’e kaydedilecek.</p><button className="button-primary" disabled={pending} onClick={()=>action('ACK')}>{alarm.acknowledgement?'Aynı ACK isteğini tekrar gönder':'Alarm onayını kaydet'}</button></>:<button className="button-primary" disabled={pending} onClick={()=>setReview(true)}>Alarmı onayla</button>):<p>Alarm onayı için yetki/depo veya aktif kaynak durumu gerekli.</p>}
  </>}{message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
  <button className="button-secondary" disabled={pending} onClick={onClose}>Kapat</button>
 </dialog>;
}
