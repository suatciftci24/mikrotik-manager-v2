import {CentralAaaManagement} from '../components/SubscriberAaaDemo';
import {RadiusTransitionPreview} from '../components/RadiusTransitionPreview';
import {useCallback,useEffect,useState} from 'react';
import {PageHeading} from '../components/PageHeading';
import {SourcePicker} from '../components/SourcePicker';
import {ResourceState} from '../components/Resource';
import {SourceBadge,StatusBadge} from '../components/Status';
import {SubscriberDisclosure} from '../components/CompactSubscriberList';
import {CompactOperationList} from '../components/CompactOperationList';
import {useIdentity} from '../lib/permissions';
import {useResource} from '../lib/useResource';
import {expiryDate} from '../lib/expiry';
import {loadRadiusVisibility,filterRadiusRecords,radiusFiltersFromHash,radiusHash,radiusDetailLink,type RadiusFilters} from '../lib/radiusVisibility';
import '../styles/radius-center.css';

const scopes=[{value:'LEGACY',label:'Mevcut demo hesapları',access:'Yetkili router kapsamı · Salt okunur',description:'Abone Merkezi ile aynı yerel demo kaydı; canlı AAA verisi değildir.'},{value:'PERSISTENT',label:'Kalıcı sentetik PPPoE / Hotspot',access:'Merkezi yönetici · Salt okunur',description:'Ayrı çalışma alanı; mevcut demo hesaplarıyla birleştirilmez.'}];
const dependencies=['/subscribers','/subscriber-workspace','/router-workspace/routers'] as const;
export function RadiusCenter(){
 const user=useIdentity(),admin=user?.role_code==='ADMIN'&&user.can_manage_users===true;
 const [filters,setFilters]=useState(()=>radiusFiltersFromHash(typeof window==='undefined'?'':window.location.hash));
 useEffect(()=>{const read=()=>setFilters(radiusFiltersFromHash(window.location.hash));window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[]);
 const change=(next:RadiusFilters)=>{setFilters(next);window.history.replaceState(null,'',window.location.pathname+window.location.search+radiusHash(next));};
 const loader=useCallback((_path:string,init?:RequestInit)=>loadRadiusVisibility(filters.scope,admin,init),[filters.scope,admin]);
 const resource=useResource('/radius-visibility?scope='+filters.scope,loader,dependencies);
 const rows=filterRadiusRecords(resource.data??[],filters);
 return <div className="screen-stack radius-center"><PageHeading title="RADIUS Merkezi" eyebrow="SENTETİK · SALT OKUNUR" description="Yerel hesap görünürlüğü; FreeRADIUS bağlantısı ve canlı AAA ölçümü yok." actions={<button className="button-secondary" disabled={resource.loading} onClick={resource.retry}>Yenile</button>}/>
 <p className="radius-boundary" role="note">LOCAL / RADIUS hesabın yetkili kaynağıdır; PPPoE / Hotspot erişim türüdür. Hesabın aktif olması oturum veya RADIUS sunucusu sağlığı kanıtı değildir.</p>
 <CentralAaaManagement/>
 <div className="filter-tabs" role="group" aria-label="RADIUS Merkezi görünümleri"><button type="button" aria-pressed={!filters.preview} onClick={()=>{const next={...filters};delete next.preview;change(next);}}>Hesap görünürlüğü</button><button type="button" aria-pressed={!!filters.preview} onClick={()=>change({...filters,preview:true})}>Geçiş önizlemesi — işlem yapılmaz</button></div><SourcePicker label="Kayıt deposu" value={filters.scope} options={admin?scopes:scopes.slice(0,1)} onChange={scope=>change({...filters,scope:scope as RadiusFilters['scope']})}/>
 <div className="radius-controls"><label className="form-label">Hesap ara<input maxLength={120} value={filters.query} onChange={e=>change({...filters,query:e.target.value})} placeholder="Ad, kullanıcı, router veya paket"/></label><SubscriberDisclosure>{!filters.preview&&<label className="form-label">Yetkili kaynak<select value={filters.authority} onChange={e=>change({...filters,authority:e.target.value as RadiusFilters['authority']})}><option value="ALL">Tümü</option><option value="LOCAL">LOCAL</option><option value="RADIUS">RADIUS</option><option value="UNKNOWN">BELİRSİZ</option></select></label>}<label className="form-label">Erişim türü<select value={filters.access} onChange={e=>change({...filters,access:e.target.value as RadiusFilters['access']})}><option value="ALL">Tümü</option><option value="PPPOE">PPPoE</option><option value="HOTSPOT">Hotspot</option><option value="UNKNOWN">Bilinmiyor</option></select></label></SubscriberDisclosure></div>
 <ResourceState {...resource}/>
 {!resource.loading&&!resource.error&&resource.data&&<>{filters.preview?<RadiusTransitionPreview key={filters.scope} rows={resource.data} filters={filters}/>:<><div className="radius-counts" aria-label="Seçili filtrede yetkili kaynak sayıları">{(['LOCAL','RADIUS','UNKNOWN'] as const).map(source=><div key={source}><span>{source==='UNKNOWN'?'BELİRSİZ':source}</span><strong>{rows.filter(row=>row.authority===source).length}</strong></div>)}</div><p role="status">{rows.length} / {resource.data.length} erişilebilir hesap · PPPoE {rows.filter(row=>row.access==='PPPOE').length} · Hotspot {rows.filter(row=>row.access==='HOTSPOT').length} · Türü bilinmeyen {rows.filter(row=>row.access==='UNKNOWN').length}</p>
 <section className="panel radius-accounts"><h2>Hesap / profil / abonelik görünümü</h2><CompactOperationList key={JSON.stringify(filters)} label="Sentetik AAA hesapları" rows={rows.map(row=>({id:row.id,title:row.name,subject:(row.authority==='UNKNOWN'?'BELİRSİZ':row.authority)+' · '+(row.access==='UNKNOWN'?'Tür bilinmiyor':row.access)+' · '+row.plan,when:expiryDate(row.expiresOn),result:row.status==='ACTIVE'?'Aktif':row.status==='PAUSED'?'Pasif':'Bilinmiyor'}))} onOpen={id=>{const row=rows.find(row=>row.id===id);if(row)window.location.hash=radiusDetailLink(row,filters)!;}}/>
 <div className="table-scroll" role="region" tabIndex={0} aria-label="Sentetik AAA hesap tablosu"><table className="data-table"><thead><tr><th>Hesap</th><th>Kaynak / Tür</th><th>Router bağı</th><th>Paket / Bitiş</th><th>Hesap / Revizyon</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td><a className="record-link" href={radiusDetailLink(row,filters)!}>{row.name}</a><small>{row.username}</small></td><td><SourceBadge source={row.authority} unknownLabel="BELİRSİZ"/><small>{row.access==='UNKNOWN'?'Tür bilinmiyor':row.access}</small></td><td>{radiusDetailLink(row,filters,true)?<a className="record-link" href={radiusDetailLink(row,filters,true)!}>{row.routerName??row.routerId}</a>:'Router bağı doğrulanamadı'}<small>NAS yetkisi veya cihaz erişimi kanıtı değildir.</small></td><td>{row.plan}<small>{expiryDate(row.expiresOn)}</small></td><td><StatusBadge status={row.status}/><small>Revizyon {row.revision}</small></td></tr>)}</tbody></table>{!rows.length&&<p className="missing-data">Bu filtrelerde sentetik hesap yok.</p>}</div></section></>}</>}
 <details className="panel radius-notes"><summary>AAA sınırları ve audit</summary><p>Bu görünüm yalnız mevcut V2 GET sözleşmelerini kullanır. Değiştirme, kimlik oluşturma, senkronizasyon, NAS kaydı, bağlantı kontrolü veya secret çözümleme yapılmaz.</p><p>Paket adı bir FreeRADIUS profili/attribute eşlemesi değildir. Bitiş tarihi kayıtlı abonelik tarihidir; aktif oturum süresi değildir. Router ID yerel ilişkidir; doğrulanmış NAS-Identifier değildir.</p><p>Aktör, UUID, revizyon ve önceki/yeni değerler aynı depodaki Abone Detayı → Geçmiş üzerinden okunur. Audit kaydı canlı RADIUS accounting kanıtı sayılmaz. Bilinmeyen kaynak LOCAL veya RADIUS olarak tahmin edilmez.</p></details>
 </div>;
}
