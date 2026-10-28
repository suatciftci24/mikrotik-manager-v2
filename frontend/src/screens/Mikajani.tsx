import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { useResource } from '../lib/useResource';
import { ResourceState, dateTime, Facts } from '../components/Resource';
import { PageHeading } from '../components/PageHeading';
import { assertMikaAnalysis, filterMikaEvents, mikaStatus, type MikaAnalysis, type MikaEvent } from '../lib/mikajani';

const dependencies=['/subscribers','/routers'] as const;
async function load(path:string,init?:RequestInit) {return assertMikaAnalysis(await api<MikaAnalysis>(path,init));}
export function Mikajani() {
  const [scenario,setScenario]=useState('');
  const scenarios=useResource<{items:{key:string;name:string}[]}>('/mikajani/scenarios');
  const resource=useResource<MikaAnalysis>('/mikajani/analysis'+(scenario?'?scenario='+encodeURIComponent(scenario):''),load,dependencies);
  const [query,setQuery]=useState('');const [priority,setPriority]=useState('ALL');const [state,setState]=useState('ACTIVE');
  const [router,setRouter]=useState('');const [domain,setDomain]=useState('ALL');const [selected,setSelected]=useState<string|null>(null);
  useEffect(()=>{const tick=()=>resource.retry();const timer=window.setInterval(tick,60000);return()=>window.clearInterval(timer);},[resource.retry]);
  const data=resource.data;
  const rows=data?filterMikaEvents(data.events,{query,priority,state,router,domain}):[];
  const event=selected?data?.events.find(e=>e.id===selected):undefined;
  const names=Object.fromEntries(data?.health.map(r=>[r.router_id,r.name])??[]);
  return <div className="screen-stack mikajani-center">
    <PageHeading title="MikAjanı V2" eyebrow="SALT OKUNUR · KURAL TABANLI · SENTETİK" description="Ağ sağlığı, açıklanabilir olay analizi ve operatör önerileri." actions={<button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Analizi yenile</button>}/>
    <section className="panel mika-panel"><label className="form-label">Analiz kaynağı<select value={scenario} onChange={e=>{setScenario(e.target.value);setSelected(null);setRouter('');}}><option value="">Kayıtlı V2 demo verisi</option>{scenarios.data?.items.map(s=><option key={s.key} value={s.key}>SENARYO · {s.name}</option>)}</select></label>{scenarios.error&&<p role="alert">Senaryo listesi: {scenarios.error}</p>}
      <p>DEMO / SENTETİK. Öneriler otomatik uygulanmaz. Gerçek AI API çağrısı yoktur.</p>{scenario&&<p className="demo-save-notice">Ayrı sentetik senaryo seçili; kayıtlı aboneler veya routerlar değiştirilmez. Senaryo saati sabittir.</p>}
    </section>
    <ResourceState {...resource}/>
    {data&&!resource.loading&&!resource.error&&<>
      <section className="panel mika-panel"><h2>Operasyonel özet</h2><p>{data.operational_summary}</p><p>Kaynak: {data.source} · Değerlendirme: {dateTime(data.evaluated_at)} · Yanıt: {dateTime(data.generated_at)}</p>
        <div className="mika-counts">{['P1','P2','P3','P4'].map(p=><button className="button-secondary" key={p} onClick={()=>{setPriority(p);setState('ACTIVE');}}>{p} · {data.summary[p]??0}</button>)}<span>Çözülen: {data.summary.resolved} · Sağlığı belirsiz: {data.summary.uncertain}</span></div>
      </section>
      <section className="panel mika-panel"><h2>Merkezi ağ sağlığı</h2><p>İyi gözlem canlı bağlantı garantisi değildir. IPsec kaynağı yoksa Bilinmiyor gösterilir.</p><div className="mika-health">{data.health.map(r=><article key={r.router_id}><h3>{r.name}</h3><p>{mikaStatus[r.health]} · {mikaStatus[r.reliability]}</p><small>{dateTime(r.latest_observed_at)}</small><dl>{Object.entries(r.signals).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{mikaStatus[v]??v}</dd></div>)}</dl>{r.reliability!=='CURRENT'&&<p>Öneri: yeni zaman damgalı gözlem sağlayın.</p>}</article>)}</div></section>
      <section className="panel mika-panel"><h2>Olaylar ve geçmiş</h2><div className="mika-filters">
        <label>Olay ara<input value={query} onChange={e=>setQuery(e.target.value)}/></label>
        <label>Öncelik<select value={priority} onChange={e=>setPriority(e.target.value)}>{['ALL','P1','P2','P3','P4'].map(v=><option key={v} value={v}>{v==='ALL'?'Tümü':v}</option>)}</select></label>
        <label>Yaşam döngüsü<select value={state} onChange={e=>setState(e.target.value)}>{['ACTIVE','ALL','OPEN','UPDATED','RECOVERING','RESOLVED'].map(v=><option key={v} value={v}>{v==='ACTIVE'?'Aktif olaylar':v==='ALL'?'Tüm geçmiş':mikaStatus[v]}</option>)}</select></label>
        <label>Router<select value={router} onChange={e=>setRouter(e.target.value)}><option value="">Tümü</option>{data.health.map(r=><option key={r.router_id} value={r.router_id}>{r.name}</option>)}</select></label>
        <label>Alan<select value={domain} onChange={e=>setDomain(e.target.value)}>{['ALL','ROUTER','WAN','IPSEC','PPPOE','MONITOR','DATA','CORRELATION'].map(v=><option key={v} value={v}>{v==='ALL'?'Tümü':v}</option>)}</select></label>
      </div><p role="status">{rows.length} olay · Önceliğe göre sıralı</p><div className="mika-events">{rows.map(e=><article key={e.id}><div><strong>{e.priority} · {e.title}</strong><span>{mikaStatus[e.state]} · Güven: {mikaStatus[e.confidence]}</span></div><p>{e.reason}</p><p>{e.affected_router_ids.map(id=>names[id]??id).join(', ')}</p><p>Öneri: {e.recommendation}</p><time>{dateTime(e.updated_at)}</time><button className="button-secondary" onClick={()=>setSelected(e.id)}>Kanıt ve geçmişi aç</button></article>)}</div>{rows.length===0&&<p className="table-empty">Bu filtrelerde olay yok. Eksik veri sağlıklı sonuç anlamına gelmez.</p>}</section>
      <section className="panel mika-panel"><h2>Analiz sınırları</h2>{data.limitations.map(text=><p key={text}>{text}</p>)}</section>
      {event&&<EventDialog event={event} names={names} onClose={()=>setSelected(null)}/>}
    </>}
  </div>;
}
function EventDialog({event,names,onClose}:{event:MikaEvent;names:Record<string,string>;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const origin=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();origin?.focus({preventScroll:true});};},[]);
  return <dialog ref={dialog} className="expiry-dialog" aria-labelledby="mika-event-title" onCancel={e=>{e.preventDefault();onClose();}}><h2 id="mika-event-title">{event.priority} · {event.title}</h2><p>DEMO / SENTETİK · Salt okunur bulgu</p>
    <Facts items={[["Durum",mikaStatus[event.state]],["Neden",event.reason],["Kanıt",event.evidence],["Etkilenen routerlar",event.affected_router_ids.map(id=>(names[id]??id)+' ('+id+')').join(', ')],["Güven",mikaStatus[event.confidence]],["Önerilen işlem",event.recommendation],["Açılış",dateTime(event.opened_at)],["Son değişiklik",dateTime(event.updated_at)],["Çözülme",dateTime(event.resolved_at)],["Olay kimliği",event.id]]}/>
    <h3>Yaşam döngüsü ve kaynak kanıtı</h3><ol className="subscriber-history">{event.history.map((h,i)=><li key={i}><strong>{mikaStatus[h.state]}</strong><time>{dateTime(h.occurred_at)}</time><p>{h.evidence}</p><small>Gözlemler: {h.observation_ids.join(', ')}</small></li>)}</ol><button autoFocus className="button-secondary" onClick={onClose}>Kapat</button>
  </dialog>;
}
