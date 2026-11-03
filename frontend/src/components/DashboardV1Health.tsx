import {TriangleAlert} from 'lucide-react';
import {V1Inventory,type InventoryState} from './V1Inventory';
import {PageHeading} from './PageHeading';
import {MetricCard} from './Status';
import {ResourceState,dateTime} from './Resource';
import {HEALTH_STATES} from '../lib/routerHealth';
import {dashboardV1Health} from '../lib/dashboardV1Health';

const routerCenter='#module=routers&source=V1_INVENTORY';
const percent=(value:number|null)=>value===null?'Veri yok':`${value}%`;
export function DashboardV1Health(){
 return <V1Inventory render={resource=><DashboardV1HealthView {...resource}/>}/>;
}
export function DashboardV1HealthView(resource:InventoryState&{retry:()=>void;now?:number}){
 let health:ReturnType<typeof dashboardV1Health>|undefined,error=resource.error;
 if(!resource.loading&&!error){try{health=dashboardV1Health(resource.data,resource.now??Date.now());}catch(failure){error=failure instanceof Error?failure.message:'Sağlık kaynağı doğrulanamadı.';}}
 const count=(value:number|undefined)=>value===undefined?'Veri yok':value.toLocaleString('tr-TR');
 const headers=['Router','Model / RouterOS','CPU / RAM','Son internet denemesi','Gerçek ölçüm · İstanbul','Sağlık durumu / gerekçe'];
 return <div className="screen-stack dashboard-overview dashboard-real-health">
  <PageHeading title="Merkezi Dashboard" eyebrow="GERÇEK V1 · SALT OKUNUR" description="Son bilinen sağlık ölçümleri · Canlı online durum değildir" actions={<button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Şimdi yenile</button>}/>
  <section className="overview-section" aria-labelledby="real-overview-title"><div className="overview-section-heading"><h2 id="real-overview-title">Genel durum</h2><a className="record-link" href={routerCenter}>Router Merkezi’ni aç</a></div>
   <div className="metric-grid">
    {HEALTH_STATES.map(status=><MetricCard key={status} title={status} value={count(health?.counts[status])} note="Gerçek ölçüm · bilgilendirme" icon={<TriangleAlert size={18}/>}/>)}
   </div>
  </section>
  <section className="panel overview-section" aria-labelledby="health-alerts-title"><h2 id="health-alerts-title">Öncelikli sağlık uyarıları</h2>
   {!health?<p>Veri yok · Sağlık durumu doğrulanamadı.</p>:!health.total?<p>Veri yok · Envanter boş.</p>:health.alerts.length?<ul className="health-alerts">{health.alerts.slice(0,5).map(({row,health:state})=><li key={row.id}><a className="record-link" href={routerCenter}>{row.name}</a> · <strong>{state.status}</strong><small>{state.reason} · {state.age}</small></li>)}</ul>:<p>Güncel ölçümlerde eşik aşımı yok.</p>}
   {health&&health.alerts.length>5&&<a className="record-link" href={routerCenter}>Tüm {health.alerts.length} uyarıyı Router Merkezi’nde gör</a>}
  </section>
  <section className="panel overview-section dashboard-real-table" aria-labelledby="real-router-title"><div className="overview-section-heading"><h2 id="real-router-title">Router sağlık özeti</h2><span className="daily-description">Salt okunur · 60 sn yenileme</span></div>
   <p className="daily-description">Son başarılı API yenileme: {resource.lastSuccess?dateTime(new Date(resource.lastSuccess).toISOString()):'Veri yok'} · Ölçüm zamanı değildir.</p>
   <ResourceState loading={resource.loading} error={error} retry={resource.retry}/>
   {health&&health.rows.length>0?<div className="table-scroll" role="region" tabIndex={0} aria-label="Gerçek V1 Dashboard sağlık tablosu"><table className="data-table"><thead><tr>{headers.map(header=><th scope="col" key={header}>{header}</th>)}</tr></thead><tbody>{health.rows.map(({row,measured,health:state})=><tr key={row.id}>
    <td>{row.name}</td><td>{row.model??'Veri yok'}<small>RouterOS {row.routeros_version??'Veri yok'}</small></td>
    <td>{measured?`${percent(row.cpu_load_percent)} / ${percent(row.memory_used_percent)}`:'Veri yok'}</td>
    <td>{!measured||row.connection_status==='NO_DATA'?'Veri yok':row.connection_status==='LAST_PROBE_SUCCEEDED'?'Son deneme başarılı':'Son deneme başarısız'}</td>
    <td>{measured?dateTime(row.sampled_at).replace(' (İstanbul)',''):'Veri yok'}</td><td className={state.status!=='Normal'?'inventory-stale':''}><strong>{state.status}</strong><small>{state.reason} · {state.age}</small></td>
   </tr>)}</tbody></table></div>:health&&<p className="missing-data">Veri yok · Gerçek envanter aktarımı boş. Router sayısı tahmin edilmez.</p>}
  </section>
  <section className="panel overview-section dashboard-real-unavailable" aria-labelledby="real-coverage-title"><h2 id="real-coverage-title">Bu kaynakta sunulmuyor</h2><p>Abonelik ve bitişler, PPPoE işlemleri, aktif oturumlar, WAN olayları ve alarmlar: <strong>Veri yok</strong>.</p></section>
  <p className="daily-description">V2.6 başlangıç eşikleri: Dikkat CPU ≥ %70 veya RAM ≥ %80; Kritik CPU ≥ %90 veya RAM ≥ %95. Eski veri: 10 dakikadan eski. Yalnız arayüz bilgilendirmesidir; kalıcı alarm veya bildirim oluşturmaz.</p>
  <details className="panel overview-info"><summary>Veri kapsamı ve zamanlar</summary>
   <p>Snapshot oluşturma/aktarım zamanı: Veri yok · Mevcut API bu alanı sunmuyor. API yenilemesi yalnız okuma saatidir; her satırdaki gerçek sağlık örneğinin zamanını değiştirmez.</p>
   <p>Son internet denemesi canlı online kanıtı değildir. Güncellik gerçek ölçüm zamanından, 10 dakika sınırıyla hesaplanır. Eksik/eski ölçüm sağlıklı sayılmaz; envanter tarihi sağlık örneği yerine kullanılmaz.</p>
   <p>Yalnız mevcut V1 salt okunur aktarımı okunur. Demo kayıtları ve alarm toplamları bu kaynağa eklenmez. Sekmeden ayrılınca istek iptal edilir ve 60 saniyelik yenileme durur.</p>
  </details>
 </div>;
}
