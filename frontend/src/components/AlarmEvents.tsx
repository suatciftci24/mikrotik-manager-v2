import { useEffect, useRef, useState } from 'react';
import type { Router } from '../lib/api';
import { alarmCounts, alarmStatusLabels, durationText, emptyAlarmFilter, eventLabels, filterAlarmEvents, loadRouterEvents } from '../lib/routerEvents';
import type { AlarmEvent, AlarmFilter } from '../lib/routerEvents';
import { detailText } from '../lib/subscriberObservation';
import { useResource } from '../lib/useResource';
import { Facts, ResourceState, dateTime } from './Resource';

function useAlarmTime(){
  const [now,setNow]=useState(()=>new Date());
  useEffect(()=>{const tick=()=>setNow(new Date());const timer=window.setInterval(tick,30000);window.addEventListener('focus',tick);return()=>{window.clearInterval(timer);window.removeEventListener('focus',tick);};},[]);
  return now;
}
function readFilter():AlarmFilter{
  const params=new URLSearchParams(typeof window==='undefined'?'':window.location.hash.slice(1));
  return params.get('module')==='operations'?Object.fromEntries(Object.entries(emptyAlarmFilter).map(([key,value])=>[key,params.get(key)??value])) as AlarmFilter:{...emptyAlarmFilter};
}
export function AlarmEventDetails({event,routerName,onClose}:{event:AlarmEvent;routerName:string;onClose:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const origin=document.activeElement as HTMLElement|null;const node=dialog.current;node?.showModal();return()=>{node?.close();origin?.focus({preventScroll:true});};},[]);
  return <dialog ref={dialog} className="expiry-dialog operation-dialog" aria-labelledby="alarm-detail-title" onCancel={e=>{e.preventDefault();onClose();}}>
    <h2 id="alarm-detail-title">Demo alarm olayı detayı</h2><p><span className="demo-chip">SENTETİK</span> Kaydedilmiş olay; canlı internet kontrolü değildir.</p>
    <Facts items={[
      ['Olay kimliği',event.id],['Router',routerName],['Router kimliği',event.router_id],['Tür',eventLabels[event.kind]],['Durum',alarmStatusLabels[event.status]],
      ['Başlangıç / kayıt (Türkiye)',event.started_at?dateTime(event.started_at):'Veri yok'],['Bitiş (Türkiye)',event.ended_at?dateTime(event.ended_at):'Veri yok'],
      ['Süre',durationText(event.duration_seconds)],['Geri gelme kaydı',event.recovery_id??'Veri yok'],['İlişkili kesinti kaydı',event.down_event_id??'Veri yok'],
      ['Önceki WAN',detailText(event.previous_wan)],['Yeni WAN',detailText(event.new_wan)],
    ]}/><p>Eksik veya güvenilir eşleşmeyen zamanlardan süre hesaplanmaz. Devam ediyor etiketi yalnız açık olay kaydını belirtir; canlı bağlantı durumu değildir.</p>
    <div className="expiry-editor-actions"><button className="button-secondary" onClick={onClose}>Kapat</button><a className="button-primary" href={'#'+new URLSearchParams({module:'routers',id:event.router_id}).toString()}>Router detayını aç</a></div>
  </dialog>;
}
export function AlarmEvents({mode='list',routerId,routers=[]}:{mode?:'list'|'cards';routerId?:string;routers?:Router[]}){
  const resource=useResource<AlarmEvent[]|null>('/router-events',loadRouterEvents);
  const now=useAlarmTime();
  const [filter,setFilter]=useState(readFilter);
  const [selected,setSelected]=useState<string|null>(null);
  useEffect(()=>{const read=()=>setFilter(readFilter());window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[]);
  const change=(key:keyof AlarmFilter,value:string)=>{
    const next={...filter,[key]:value};setFilter(next);
    if(!routerId){const params=new URLSearchParams({module:'operations',...next});window.history.replaceState(null,'',window.location.pathname+window.location.search+'#'+params);}
  };
  let rows:AlarmEvent[]=[],error=resource.error;
  try{rows=filterAlarmEvents(resource.data??[],routerId?{...emptyAlarmFilter,router:routerId}:filter,now);}catch(failure){error=failure instanceof Error?failure.message:'Filtre geçersiz.';}
  const counts=alarmCounts(resource.data??null,now);
  const chosen=resource.data?.find(event=>event.id===selected);
  const names=new Map(routers.map(router=>[router.id,router.name]));
  const routerIds=[...new Set([...routers.map(r=>r.id),...(resource.data??[]).map(event=>event.router_id),...(filter.router?[filter.router]:[])])];
  return <section className="panel central-events alarm-events" aria-label="İnternet ve WAN alarm merkezi">
    <h2>{mode==='cards'?'Son 24 saat internet ve WAN olayları':routerId?'Router kesinti ve WAN olay geçmişi':'İnternet Kesintisi ve WAN Alarm Merkezi'}</h2>
    <p><span className="demo-chip">SENTETİK</span> Zamanlar Europe/Istanbul. Son görülme internet erişimi kanıtı değildir.</p>
    <ResourceState loading={resource.loading} error={error} retry={resource.retry}/>
    {!resource.loading&&!resource.error&&<>
      {mode==='cards'?<div className="alarm-card-grid">{([['INTERNET_DOWN','İnternet kesintileri',counts.outages],['WAN_CHANGE','WAN değişiklikleri',counts.wan]] as const).map(([kind,label,count])=><a key={kind} className="button-secondary alarm-count-card" href={'#'+new URLSearchParams({module:'operations',kind,period:'24H'}).toString()}>{label}: {count===null?'Veri yok':count}</a>)}</div>:<>
        {!routerId&&<div className="router-report-controls alarm-filters">
          <label className="form-label">Router<select value={filter.router} onChange={e=>change('router',e.target.value)}><option value="">Tüm routerlar</option>{routerIds.map(id=><option key={id} value={id}>{names.get(id)??id}</option>)}</select></label>
          <label className="form-label">Olay türü<select value={filter.kind} onChange={e=>change('kind',e.target.value)}><option value="ALL">Tüm olaylar</option>{Object.entries(eventLabels).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label>
          <label className="form-label">Durum<select value={filter.status} onChange={e=>change('status',e.target.value)}><option value="ALL">Tüm durumlar</option>{Object.entries(alarmStatusLabels).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label>
          <label className="form-label">Dönem<select value={filter.period} onChange={e=>change('period',e.target.value)}><option value="ALL">Tüm kayıtlar</option><option value="24H">Son 24 saat</option></select></label>
          <label className="form-label">Başlangıç günü<input type="date" value={filter.from} onChange={e=>change('from',e.target.value)}/></label>
          <label className="form-label">Bitiş günü<input type="date" value={filter.to} onChange={e=>change('to',e.target.value)}/></label>
          <button className="button-secondary" onClick={()=>{setFilter({...emptyAlarmFilter});window.history.replaceState(null,'',window.location.pathname+window.location.search+'#module=operations');}}>Filtreleri temizle</button>
        </div>}
        <p>Aralık olay başlangıcı/kayıt zamanına uygulanır; Türkiye günleri dahil. Zamanı eksik kayıtlar yalnız tarih filtresi yokken görünür. Son 24 saat: {dateTime(new Date(now.getTime()-86400000).toISOString())} → {dateTime(now.toISOString())}.</p>
        {rows.length>0&&<div className="table-scroll"><table className="data-table"><thead><tr><th>ROUTER</th><th>OLAY</th><th>DURUM</th><th>BAŞLANGIÇ / KAYIT</th><th>BİTİŞ</th><th>SÜRE</th></tr></thead><tbody>{rows.map(event=><tr key={event.id} onClick={()=>setSelected(event.id)} className="clickable-row"><td>{names.get(event.router_id)??event.router_id}</td><td><button className="record-link" onClick={()=>setSelected(event.id)}>{eventLabels[event.kind]} · {event.id}</button></td><td>{alarmStatusLabels[event.status]}</td><td>{event.started_at?dateTime(event.started_at):'Veri yok'}</td><td>{event.ended_at?dateTime(event.ended_at):'Veri yok'}</td><td>{durationText(event.duration_seconds)}</td></tr>)}</tbody></table></div>}
      </>}
      {!error&&resource.data===null?<p className="missing-data">Veri yok. Yerel V2 demo olay kaynağı bulunmuyor; kesinti veya WAN sayısı sıfır kabul edilmez.</p>:!error&&mode!=='cards'&&!rows.length?<p className="missing-data">Veri yok. Seçili kapsama uygun kaydedilmiş olay bulunmuyor.</p>:null}
      <button className="button-secondary" onClick={resource.retry}>Olay kayıtlarını yenile</button>
    </>}
    {chosen&&<AlarmEventDetails event={chosen} routerName={names.get(chosen.router_id)??chosen.router_id} onClose={()=>setSelected(null)}/>}
  </section>;
}
