import { useEffect, useState } from 'react';
import { useResource } from '../lib/useResource';
import { operationFilter, operationDetailHash, operationHash, operationQuery, type ReportFilter, type OperationReportData, type ConnectionRecord } from '../lib/operationReport';
import type { DailyOperation } from '../lib/dailySummary';
import type { MikaEvent } from '../lib/mikajani';
import { mikaStatus } from '../lib/mikajani';
import { historyValues, operationLabel } from '../lib/subscriberHistory';
import { dateTime, ResourceState, Facts } from '../components/Resource';
import { PageHeading } from '../components/PageHeading';
import { OperationDetails } from '../components/OperationDetails';
import { AlarmEventDetails } from '../components/AlarmEvents';
import { EventDialog } from './Mikajani';
import { durationText, eventLabels } from '../lib/routerEvents';
const dependencies=['/routers','/subscribers','/router-events','/mikajani'] as const;
export function OperationReport(){
 const [filter,setFilter]=useState(()=>operationFilter(typeof window==='undefined'?'':window.location.hash));
 const resource=useResource<OperationReportData>('/reports/operations?'+operationQuery(filter),undefined,dependencies);
 const [selected,setSelected]=useState<DailyOperation|ConnectionRecord|MikaEvent|null>(null);
 useEffect(()=>{const read=()=>{setFilter(operationFilter(window.location.hash));setSelected(null);};window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[]);
 useEffect(()=>{const tick=()=>{if(!document.hidden)resource.retry();};const timer=window.setInterval(tick,60000);window.addEventListener('focus',tick);document.addEventListener('visibilitychange',tick);return()=>{window.clearInterval(timer);window.removeEventListener('focus',tick);document.removeEventListener('visibilitychange',tick);};},[resource.retry]);
 const change=(value:Partial<ReportFilter>)=>{const next={...filter,...value,page:value.page??1};setFilter(next);setSelected(null);window.history.replaceState(null,'',window.location.pathname+window.location.search+operationHash(next));};
 const data=resource.data,error=resource.error||(data&&(data.is_demo!==true||data.read_only!==true)?'Salt okunur sentetik rapor kaynağı doğrulanamadı.':undefined);
 const link=(module:'routers'|'subscribers',id:string)=>operationDetailHash(module,id,filter);
 const names=Object.fromEntries(data?.routers.map(r=>[r.id,r.name])??[]);
 return <div className="screen-stack operation-report">
  <a className="button-secondary detail-back" href="#module=dashboard">Dashboard’a dön</a>
  <PageHeading title="Günlük Operasyon ve Bağlantı Raporları" eyebrow="SENTETİK · SALT OKUNUR · EUROPE/ISTANBUL" description="Kaydedilmiş audit, WAN ve MikAjanı kanıtları; geçmiş telemetri tahmini değildir." actions={<button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Raporu yenile</button>}/>
  <section className="panel"><div className="router-report-controls">
   <label className="form-label">Başlangıç<input aria-label="Rapor başlangıç tarihi" type="date" value={filter.start} onChange={e=>change({start:e.target.value})}/></label>
   <label className="form-label">Bitiş<input aria-label="Rapor bitiş tarihi" type="date" value={filter.end} onChange={e=>change({end:e.target.value})}/></label>
   <label className="form-label">Router<select aria-label="Rapor router filtresi" value={filter.router_id} onChange={e=>change({router_id:e.target.value})}><option value="">Tüm routerlar</option>{data?.routers.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}{filter.router_id&&!names[filter.router_id]&&<option value={filter.router_id}>{filter.router_id}</option>}</select></label>
   <label className="form-label">Rapor<select aria-label="Rapor türü" value={filter.category} onChange={e=>change({category:e.target.value as ReportFilter['category']})}><option value="AUDIT">PPPoE audit</option><option value="CONNECTION">İnternet / WAN</option><option value="MIKA">MikAjanı</option></select></label>
   {filter.category==='AUDIT'&&<><label className="form-label">İşlem<select aria-label="Rapor işlem filtresi" value={filter.operation} onChange={e=>change({operation:e.target.value})}><option value="">Tüm işlemler</option>{(['CREATE','PLAN_CHANGE','STATUS_CHANGE','RENEWAL','DATE_EDIT'] as const).map(k=><option key={k} value={k}>{operationLabel(k)}</option>)}</select></label><label className="form-label">Abone kimliği<input aria-label="Rapor abone kimliği" value={filter.subscriber_id} onChange={e=>change({subscriber_id:e.target.value})}/></label></>}
   {filter.category==='MIKA'&&<><label className="form-label">Öncelik<select aria-label="Rapor öncelik filtresi" value={filter.priority} onChange={e=>change({priority:e.target.value})}>{['ALL','P1','P2','P3','P4'].map(p=><option key={p}>{p}</option>)}</select></label><label className="form-label">Durum<select aria-label="Rapor olay durumu" value={filter.state} onChange={e=>change({state:e.target.value})}>{['ALL','ACTIVE','OPEN','UPDATED','RECOVERING','RESOLVED'].map(s=><option key={s} value={s}>{mikaStatus[s]??s}</option>)}</select></label></>}
   <button className="button-secondary" onClick={()=>{const next=operationFilter('');setFilter(next);setSelected(null);window.history.replaceState(null,'',operationHash(next));}}>Filtreleri temizle</button>
  </div><p>Tarih aralığı en fazla 366 Türkiye günü; bitiş günü dahil, gelecek kayıtlar hariç. Sayfa başına 25 kayıt sunucuda filtrelenir. Abone filtresi audit toplamı ve listesini; işlem türü yalnız audit listesini kapsamlar; öncelik/durum yalnız MikAjanı kapsamındadır.</p></section>
  <ResourceState {...resource} error={error}/>
  {data&&!resource.loading&&!error&&<>
   <section className="panel"><h2>Operasyon özeti</h2><p>Okuma: {dateTime(data.read_at)} · Her 60 saniye ve odağa dönüşte yenilenir. MikAjanı satırları dönemde en az bir yaşam döngüsü geçişi olan olaylardır; gösterilen durum ve kanıt son kayıtlı halidir. Router/hesap/açık olay sayıları son kayıtlı durumdur; seçili geçmiş tarihin snapshot’ı değildir.</p>
    <Facts items={[["Router · son durum",Object.entries(data.summary.router_status).map(([k,v])=>`${k}: ${v}`).join(' · ')],["Abone · aktif / pasif",`${data.summary.subscribers} · ${data.summary.active} / ${data.summary.paused}`],["Dönem PPPoE işlemi",data.summary.operations],["Etkinleştirme / duraklatma hareketi",`${data.summary.activated} / ${data.summary.deactivated}`],["Başarısız işlemler / hata açıklaması",'Veri yok · başarısız denemeler kalıcı audit kaynağında tutulmuyor'],["Kayıtlı açık MikAjanı olayı",data.summary.open_events??'Veri yok / yetki yok'],["Dönem bağlantı kayıtları",data.summary.connections??'Veri yok']]}/>
   </section>
   <section className="panel"><h2>{filter.category==='AUDIT'?'PPPoE audit kayıtları':filter.category==='CONNECTION'?'İnternet ve WAN yaşam döngüsü':'MikAjanı olay raporu'}</h2>
    {filter.category==='CONNECTION'&&!data.connections_available?<p className="missing-data">Veri yok: bağlantı olay kaynağı bulunmuyor; sıfır sayılmaz.</p>:data.items.length===0?<p className="table-empty">Seçili filtrelerde kayıt yok.</p>:<div className="table-scroll" role="region" tabIndex={0} aria-label="Operasyon raporu kayıtları"><table className="data-table"><thead><tr><th>KAYIT / DETAY</th><th>ABONE / ROUTER</th><th>ZAMAN / BAŞLANGIÇ</th><th>ÖNCEKİ / YENİ · BİTİŞ / SÜRE</th><th>SONUÇ / DURUM</th></tr></thead><tbody>{data.items.map(item=>{
     if(filter.category==='AUDIT'){const e=item as DailyOperation&{router_id?:string|null};const values=historyValues(e);return <tr key={e.id}><td><button className="record-link" onClick={()=>setSelected(e)}>{operationLabel(e.operation)} · {e.id}</button></td><td><a href={link('subscribers',e.subscriber_id)}>{e.customer_name||e.subscriber_id}</a><br/>{e.router_id?<a href={link('routers',e.router_id)}>{names[e.router_id]??e.router_name}</a>:e.router_name}</td><td>{dateTime(e.occurred_at)}</td><td>{values[0]} → {values[1]}</td><td>Kaydedildi · Hata: yok (başarılı audit)</td></tr>;}
     if(filter.category==='CONNECTION'){const e=item as ConnectionRecord;return <tr key={e.id}><td><button className="record-link" onClick={()=>setSelected(e)}>{eventLabels[e.kind]} · {e.id}</button></td><td><a href={link('routers',e.router_id)}>{names[e.router_id]??e.router_id}</a></td><td>{dateTime(e.occurred_at)}<br/>Kesinti başlangıcı: {dateTime(e.lifecycle.started_at)}</td><td>Bitiş: {dateTime(e.lifecycle.ended_at)} · Süre: {durationText(e.lifecycle.duration_seconds)}<br/>{e.previous_wan??'Veri yok'} → {e.new_wan??'Veri yok'}</td><td>{e.lifecycle.status}</td></tr>;}
     const e=item as MikaEvent;return <tr key={e.id}><td><button className="record-link" onClick={()=>setSelected(e)}>{e.priority} · {e.domain} · {e.title} · {e.id}</button></td><td>{e.affected_router_ids.map(id=><div key={id}><a href={link('routers',id)}>{names[id]??id}</a></div>)}</td><td>Açılma: {dateTime(e.opened_at)}<br/>Son değişiklik: {dateTime(e.updated_at)}</td><td>Çözülme: {dateTime(e.resolved_at)}</td><td>{mikaStatus[e.state]}</td></tr>;
    })}</tbody></table></div>}
    <p role="status">{data.total} kayıt · Sayfa {filter.page} / {Math.max(1,Math.ceil(data.total/data.page_size))}</p><div className="daily-links"><button className="button-secondary" disabled={filter.page===1} onClick={()=>change({page:filter.page-1})}>Önceki sayfa</button><button className="button-secondary" disabled={filter.page*data.page_size>=data.total} onClick={()=>change({page:filter.page+1})}>Sonraki sayfa</button></div>
   </section>
  </>}
  {selected&&!error&&filter.category==='AUDIT'&&<OperationDetails event={selected as DailyOperation} onClose={()=>setSelected(null)} onSubscriber={id=>{window.location.hash=link('subscribers',id);}}/>}
  {selected&&!error&&filter.category==='CONNECTION'&&<AlarmEventDetails event={(selected as ConnectionRecord).lifecycle} routerName={names[(selected as ConnectionRecord).router_id]??'Veri yok'} onClose={()=>setSelected(null)}/>}
  {selected&&!error&&filter.category==='MIKA'&&<EventDialog event={selected as MikaEvent} names={names} onClose={()=>setSelected(null)}/>}
 </div>;
}
