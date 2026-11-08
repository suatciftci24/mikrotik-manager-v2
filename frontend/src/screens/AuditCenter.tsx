import {useEffect,useMemo,useState} from 'react';
import {PageHeading} from '../components/PageHeading';
import {ResourceState,dateTime} from '../components/Resource';
import {useResource} from '../lib/useResource';
import {useIdentity} from '../lib/permissions';
import {auditCsv,auditFilter,auditHash,auditQuery,type AuditFilter,type AuditSource} from '../lib/auditCenter';
import type {Router} from '../lib/api';

type AuditRow={id:string;audit_id:string|null;occurred_at:string;actor_id:string|null;target_id:string|null;subscriber_id:string|null;router_id:string|null;operation:string;result:'SUCCESS'|'FAILED'|'UNKNOWN';source:string;details:Record<string,string|null|Record<string,unknown>|undefined>};
type AuditData={items:AuditRow[];total:number;page:number;page_size:number;source:AuditSource;source_available:boolean;read_at:string;is_demo:true;read_only:true;routers:Router[];sources:Record<string,{available:boolean;result_coverage:string}>};
const labels:Record<AuditSource,string>={SUBSCRIBER:'PPPoE / Hotspot işlemleri',WORKSPACE:'Kalıcı abone işlemleri',USER:'Kullanıcı denetim kayıtları',WAN:'Router WAN olayları'};
const results:Record<string,string>={SUCCESS:'Başarılı',FAILED:'Başarısız',UNKNOWN:'Belirsiz'};
const sourceNames:Record<string,string>={LEGACY_SUBSCRIBER_AUDIT:'PPPoE / Hotspot audit',SUBSCRIBER_WORKSPACE:'Kalıcı abone audit',USER_AUDIT:'Kullanıcı audit',ROUTER_WAN:'Router WAN'};
const dateFromHash=()=>auditFilter(window.location.hash);
export function AuditCenter(){
 const identity=useIdentity(),admin=identity?.role_code==='ADMIN'&&identity.can_manage_users===true;
 const [filter,setFilter]=useState<AuditFilter>(dateFromHash);
 useEffect(()=>{const read=()=>setFilter(dateFromHash());window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[]);
 const path='/reports/audit-center?'+auditQuery(filter);
 const resource=useResource<AuditData>(path);
 const data=resource.data,error=resource.error||(data&&(data.is_demo!==true||data.read_only!==true)?'Rapor kaynağı salt okunur V2.6 kaynağı olarak doğrulanamadı.':undefined);
 const change=(next:Partial<AuditFilter>)=>{const updated={...filter,...next,page:next.page??1};setFilter(updated);window.location.hash=auditHash(updated);};
 const names=useMemo(()=>Object.fromEntries(data?.routers.map(router=>[router.id,router.name])??[]),[data?.routers]);
 const changeSource=(source:AuditSource)=>change({source,router_id:source==='USER'?'':filter.router_id,actor_id:source==='WAN'?'':filter.actor_id});
 const rowLink=(row:AuditRow,kind:'subscribers'|'routers',id:string)=>{
  const params=new URLSearchParams({module:kind,id,...(kind==='subscribers'?{workspace:id.startsWith('demo-managed-')?'PERSISTENT':'LEGACY'}:{source:id.startsWith('demo-managed-')?'MANAGED_DEMO':'DEMO'}),report_start:filter.start,report_end:filter.end,report_router:filter.router_id});
  params.set('audit_source',filter.source);params.set('audit_result',filter.result);params.set('audit_query',filter.query);params.set('audit_actor',filter.actor_id);params.set('audit_operation',filter.operation);
  window.location.hash=params.toString();
 };
 return <div className="screen-stack audit-center">
  <PageHeading title="Raporlama ve Denetim Merkezi" eyebrow="SENTETİK · SALT OKUNUR · EUROPE/ISTANBUL" description="Mevcut PPPoE/Hotspot, kalıcı abone, kullanıcı audit ve WAN olay kaynakları. Her satır kaynak etiketi taşır; veri yokluğu sıfır veya başarı olarak sunulmaz." actions={<><button className="button-secondary" disabled={resource.loading||!data?.source_available||!data.items.length} onClick={()=>{if(!data)return;const blob=new Blob([auditCsv(data.items)],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=`v26-audit-${filter.source.toLowerCase()}-${filter.start}-${filter.end}-page-${filter.page}.csv`;anchor.click();URL.revokeObjectURL(url);}}>Bu sayfayı CSV indir</button><button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Yenile</button></>}/>
  <section className="panel"><div className="router-report-controls">
   <label className="form-label">Kaynak<select aria-label="Denetim veri kaynağı" value={filter.source} onChange={e=>changeSource(e.target.value as AuditSource)}><option value="SUBSCRIBER">{labels.SUBSCRIBER}</option><option value="WAN">{labels.WAN}</option>{admin&&<><option value="WORKSPACE">{labels.WORKSPACE}</option><option value="USER">{labels.USER}</option></>}</select></label>
   <label className="form-label">Başlangıç<input aria-label="Denetim başlangıç tarihi" type="date" value={filter.start} onChange={e=>change({start:e.target.value})}/></label>
   <label className="form-label">Bitiş<input aria-label="Denetim bitiş tarihi" type="date" value={filter.end} onChange={e=>change({end:e.target.value})}/></label>
   <label className="form-label">Router<select aria-label="Denetim router filtresi" value={filter.router_id} disabled={filter.source==='USER'} onChange={e=>change({router_id:e.target.value})}><option value="">Tüm yetkili routerlar</option>{data?.routers.map(r=><option value={r.id} key={r.id}>{r.name}</option>)}</select></label>
   {filter.source!=='WAN'&&<label className="form-label">Aktör kimliği<input aria-label="Denetim aktör filtresi" maxLength={80} value={filter.actor_id} onChange={e=>change({actor_id:e.target.value})}/></label>}
   <label className="form-label">İşlem türü<input aria-label="Denetim işlem filtresi" maxLength={40} value={filter.operation} onChange={e=>change({operation:e.target.value})} placeholder="Tümü"/></label>
   <label className="form-label">Sonuç<select aria-label="Denetim sonuç filtresi" value={filter.result} onChange={e=>change({result:e.target.value as AuditFilter['result']})}><option value="ALL">Tümü</option>{Object.entries(results).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label>
   <label className="form-label">Ara<input aria-label="Denetim araması" maxLength={120} value={filter.query} onChange={e=>change({query:e.target.value})}/></label>
   <button className="button-secondary" onClick={()=>change({...dateFromHash(),router_id:'',actor_id:'',operation:'',result:'ALL',query:''})}>Filtreleri temizle</button>
  </div><p>En fazla 366 Türkiye günü · sayfa başına en fazla 50 kayıt. Kullanıcı audit’i ADMIN’e özeldir; OPERATOR ve VIEWER yalnız mevcut router rapor yetkileri içindeki kaynakları görür.</p></section>
  <ResourceState {...resource} error={error}/>
  {data&&!resource.loading&&!error&&<>
   <section className="panel"><p>Kaynak: <strong>{labels[filter.source]}</strong> · Okuma: {dateTime(data.read_at)} · Salt okunur sentetik rapor.</p>
    {!data.source_available?<p className="missing-data">Veri yok: bu kaynak veya seçilen sonuç türü için kayıt kanıtı mevcut değil; toplam sıfır kabul edilmedi.</p>:data.items.length===0?<p className="table-empty">Seçili filtrelerde kayıt yok.</p>:<div className="table-scroll" role="region" tabIndex={0} aria-label="Raporlama ve denetim kayıtları"><table className="data-table"><thead><tr><th>ZAMAN / KAYNAK</th><th>AKTÖR / İŞLEM</th><th>HEDEF</th><th>SONUÇ / DENETİM KİMLİĞİ</th></tr></thead><tbody>{data.items.map(row=><tr key={row.id}><td>{dateTime(row.occurred_at)}<br/>{sourceNames[row.source]??row.source}</td><td>{row.actor_id??'Veri yok'}<br/>{row.operation}{(row.details.changes||row.details.previous||row.details.next)&&<details><summary>İzinli değişiklik alanları</summary><pre>{JSON.stringify(row.details.changes??{previous:row.details.previous,next:row.details.next},null,2)}</pre></details>}</td><td>{row.subscriber_id?<button className="record-link" onClick={()=>rowLink(row,'subscribers',row.subscriber_id!)}>{String(row.details.subscriber??row.details.username??row.subscriber_id)}</button>:row.router_id?<button className="record-link" onClick={()=>rowLink(row,'routers',row.router_id!)}>{names[row.router_id]??row.router_id}</button>:row.target_id??'Veri yok'}{row.router_id&&row.subscriber_id&&<><br/><button className="record-link" onClick={()=>rowLink(row,'routers',row.router_id!)}>{names[row.router_id]??row.router_id}</button></>}</td><td>{results[row.result]??'Belirsiz'}<br/>{row.audit_id??'Audit UUID yok'} · {row.id}</td></tr>)}</tbody></table></div>}
    {data.source_available&&<><p role="status">{data.total} kayıt · Sayfa {filter.page} / {Math.max(1,Math.ceil(data.total/data.page_size))}</p><div className="daily-links"><button className="button-secondary" disabled={filter.page===1} onClick={()=>change({page:filter.page-1})}>Önceki</button><button className="button-secondary" disabled={filter.page*data.page_size>=data.total} onClick={()=>change({page:filter.page+1})}>Sonraki</button></div></>}
   </section>
   {filter.source==='SUBSCRIBER'&&<p className="daily-description">Bu kaynakta saklanan audit kanıtı başarıyla kaydedilmiş değişikliklerle sınırlıdır. Başarısız veya belirsiz girişimler için veri yoktur; işlem başarısı çıkarımı yapılmaz. WAN kaynağıyla eş zamanlı karşılaştırmak için kaynak filtresini değiştirin.</p>}
  </>}
 </div>;
}
