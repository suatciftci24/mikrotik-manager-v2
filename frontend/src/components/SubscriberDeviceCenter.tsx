import {packagePrice} from '../lib/packages';
import {SubscriberAaaDemo} from './SubscriberAaaDemo';
import {SourceBadge} from './Status';
import {sourceDescription,sourceLabels,subscriberSource} from '../lib/source';
import {QuickActions,type QuickAction} from './QuickActions';
import type {SubscriberDetailData} from '../lib/api';
import {linkedDetailHash} from '../lib/detailLinks';
import {SubscriberQuickButtons} from './SubscriberQuickButtons';
import {canChangeWorkspace,workspaceActionUnavailableReason} from '../lib/subscriberActions';
import {LegacySubscriberActions} from './LegacySubscriberActions';
import {dailyLabels} from '../lib/subscriberManagementCenter';
import {expiryDate,expiryInfo,remainingDays} from '../lib/expiry';
import {detailText,observationTime} from '../lib/subscriberObservation';
import {changedHistoryValues,historyActor,valuesText} from '../lib/subscriberHistory';
import {useEffect,useRef,useState,type KeyboardEvent,type ReactNode} from 'react';
import {useListFilter} from '../lib/useListFilter';
import {useResource} from '../lib/useResource';
import {subscriberCenterTabs,subscriberPhotoTab,subscriberTab,safeSubscriberCenter,subscriberRouterHash,accountStatus,type SubscriberCenterData,type SubscriberTab,type CenterSubscriber} from '../lib/subscriberCenter';
import {ResourceState,Facts,dateTime} from './Resource';
import {PageHeading} from './PageHeading';
import {useTurkeyToday} from '../lib/useTurkeyToday';
import {can,useIdentity} from '../lib/permissions';
import {SubscriberPhotos} from './SubscriberPhotos';
const dependencies=['/subscribers','/subscriber-workspace'] as const;
export function SubscriberDeviceCenter({id,onBack,onEdit,onRenew,onManage,legacy,photosEnabled=false}:{id:string;onBack:()=>void;onEdit?:(item:CenterSubscriber)=>void;onRenew?:(item:CenterSubscriber)=>void;onManage?:(item:CenterSubscriber,action?:'PLAN'|'STATUS')=>void;legacy?:ReactNode|((tab:SubscriberTab)=>ReactNode);photosEnabled?:boolean}){
 const [legacyAction,setLegacyAction]=useState<{detail:SubscriberDetailData;action:QuickAction}|null>(null);
 const today=useTurkeyToday();
 const resource=useResource<SubscriberCenterData>('/subscriber-center/'+encodeURIComponent(id),undefined,dependencies);
 const tabKeys=[...subscriberCenterTabs.map(([key])=>key),'package','expiry',...(photosEnabled?['photos' as const]:[])] as const;
 const [tab,setTab]=useListFilter('subscribers','tab',tabKeys,'overview');const heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{heading.current?.focus();window.scrollTo(0,0);},[id]);
 const data=resource.data;const error=resource.error||(data&&!safeSubscriberCenter(data,id)?'Abone kaynağı veya router ID bağı doğrulanamadı; detay gösterilmedi.':undefined);
 return <section className="screen-stack">{legacyAction&&<QuickActions rows={[legacyAction.detail.item]} today={today} initialAction={legacyAction.action} onClose={()=>setLegacyAction(null)}/>}<button className="detail-back button-secondary" onClick={onBack}>← Geri dön</button><PageHeading title="Abone Detay Merkezi" eyebrow="SENTETİK DEMO · CANLI İŞLEM YOK" description="Kayıtlı hesap bilgileri gösterilir; cihaz ve RADIUS bağlantısı başlatılmaz." headingRef={heading}/><ResourceState {...resource} error={error}/>{data&&!resource.loading&&!error&&<SubscriberDeviceCenterView data={data} tab={tab} onTab={setTab} onEdit={onEdit} onRenew={onRenew} onManage={onManage} onLegacyAction={(detail,action)=>setLegacyAction({detail,action})} legacy={legacy} photosEnabled={photosEnabled}/>}</section>;
}
export function SubscriberDeviceCenterView({data,tab,onTab,onEdit,onRenew,onManage,onLegacyAction,legacy,photosEnabled=false}:{data:SubscriberCenterData;tab:SubscriberTab;onTab:(tab:SubscriberTab)=>void;onEdit?:(item:CenterSubscriber)=>void;onRenew?:(item:CenterSubscriber)=>void;onManage?:(item:CenterSubscriber,action?:'PLAN'|'STATUS')=>void;onLegacyAction?:(detail:SubscriberDetailData,action:QuickAction)=>void;legacy?:ReactNode|((tab:SubscriberTab)=>ReactNode);photosEnabled?:boolean}){
 const writable=canChangeWorkspace(data,!!(onEdit||onRenew||onManage));
 const identity=useIdentity();const r=data.item;const today=useTurkeyToday();const buttons=useRef<(HTMLButtonElement|null)[]>([]);const routerHash=subscriberRouterHash(r,typeof window==='undefined'?'':window.location.hash);
 const tabs=subscriberCenterTabs;const activeTab=subscriberTab(tab);
 const [photosOpen,setPhotosOpen]=useState(tab==='photos');
 useEffect(()=>{if(tab==='photos')setPhotosOpen(true);},[tab]);
 const supplementary=typeof legacy==='function'?legacy(activeTab):legacy;
 const expiry=expiryInfo(r.expires_on,today);
 const savedTime=(value:string|null)=>observationTime(value)?dateTime(value):'Ölçülmedi';
 const photoPermission=r.access_type==='HOTSPOT'?'can_manage_hotspot':'can_manage_pppoe';
 const photoIdentityValid=!!r.router_id&&!r.router_missing&&r.router_source!=='UNKNOWN'&&(r.source==='LOCAL'||r.source==='RADIUS')&&(r.access_type==='PPPOE'||r.access_type==='HOTSPOT');
 const canManagePhotos=photoIdentityValid&&(data.source==='PERSISTENT_WORKSPACE'?identity?.role_code==='ADMIN'&&identity.can_manage_users===true:can(identity,r.router_id,photoPermission));
 const workspaceMenu=data.source==='PERSISTENT_WORKSPACE'?<div className="subscriber-actions-menu">
 <SubscriberQuickButtons compact label={r.customer_name} unavailableReason={writable?undefined:workspaceActionUnavailableReason(r)} status={r.status} onHistory={()=>onTab('history')} onEdit={writable&&onEdit?()=>onEdit(r):undefined} available={[...(onRenew?['EXTEND' as const]:[]),...(onManage?['PLAN' as const,'STATUS' as const]:[])]} onAction={writable?action=>{if(action==='EXTEND')onRenew?.(r);else onManage?.(r,action);}:undefined}/>
 </div>:null;
 function key(event:KeyboardEvent,index:number){let next=index;if(event.key==='ArrowRight')next=(index+1)%tabs.length;else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;event.preventDefault();onTab(tabs[next][0]);buttons.current[next]?.focus();}
 return <><section className="panel registry-detail router-device-summary subscriber-summary" aria-label="Abone özeti">
 <div className="subscriber-summary-title"><div><span className="eyebrow">SENTETİK · Güncel yetkili kaynak: {subscriberSource(r.source)==='UNKNOWN'?'BELİRSİZ':sourceLabels[subscriberSource(r.source)]} · Erişim türü: {r.access_type??'Bilinmiyor'}</span><h2>{detailText(r.customer_name)}</h2></div><div className="subscriber-summary-actions"><span className="demo-chip">{accountStatus(r.status)}</span>{workspaceMenu}</div></div>
 <Facts items={[
 ['Kullanıcı adı',detailText(r.username)],['Paket',detailText(r.plan)],['Paket hızı',r.package_snapshot?`${r.package_snapshot.download_mbps}/${r.package_snapshot.upload_mbps} Mbps`:'Veri yok'],
 ['Router',routerHash?<a className="record-link" aria-label="İlgili routerı aç" href={routerHash}>{r.router_name||'Routerı aç'}</a>:detailText(r.router_name)],
 ['Bitiş tarihi',expiry.days===null?'Veri yok':expiryDate(r.expires_on)],['Kalan gün',expiry.days===null?'Veri yok':remainingDays(expiry.days)]
 ]}/>{subscriberSource(r.source)==='UNKNOWN'&&<p role="status">{sourceDescription(r.source)}</p>}{!r.access_type&&<p>Erişim türü kayıtlı değil; PPPoE/Hotspot türü yetkili kaynaktan veya router atamasından tahmin edilmez.</p>}</section>
 <div className="filter-tabs router-device-tabs" role="tablist" aria-label="Abone detay bölümleri">{tabs.map(([id,label],index)=><button key={id} ref={node=>{buttons.current[index]=node;}} role="tab" id={'subscriber-tab-'+id} aria-controls={'subscriber-panel-'+id} aria-selected={activeTab===id} tabIndex={activeTab===id?0:-1} onKeyDown={event=>key(event,index)} onClick={()=>onTab(id)} className={activeTab===id?'selected':''}>{label}</button>)}</div>
 <section className="panel registry-detail router-device-panel" role="tabpanel" id={'subscriber-panel-'+activeTab} aria-labelledby={'subscriber-tab-'+activeTab} tabIndex={0}><h2>{tabs.find(([key])=>key===activeTab)?.[1]??'Abone detayı'}</h2>
 {activeTab==='overview'?<><details className="technical-info"><summary>Teknik bilgiler</summary><Facts items={[
 ['Kayıt kimliği',r.id],['Erişim türü',r.access_type??'Bilinmiyor'],['Güncel yetkili kaynak',<SourceBadge source={r.source}/>],
 ['Veri deposu',data.persistence],['Veri kaynağı',data.source==='PERSISTENT_WORKSPACE'?'Kalıcı sentetik çalışma alanı':'Mevcut sentetik demo'],['Güncel abonelik revizyonu',r.revision],['Başlangıç tarihi',r.started_on?expiryDate(r.started_on):'Veri yok'],...(r.package_snapshot?[["Paket sürümü",String(r.package_revision)],["Aylık ücret",packagePrice(r.package_snapshot.monthly_price)],["Profil eşleme etiketi",r.package_snapshot.router_profile??'Yok · cihazda uygulanmadı']] as [string,string][]:[])
 ]}/><p>Bitiş tarihi Türkiye takvim gününe göre hesaplanır; hesap etkinliği çevrimiçi oturum kanıtı değildir.</p></details>
 {supplementary}
 {photosEnabled&&<details className="subscriber-photo-disclosure" open={photosOpen} onToggle={event=>setPhotosOpen(event.currentTarget.open)}><summary>{subscriberPhotoTab[1]}</summary>{photosOpen&&(photoIdentityValid?<SubscriberPhotos id={r.id} source={r.source!} accessType={r.access_type!} canManage={canManagePhotos}/>:<p className="missing-data" role="status">Fotoğraf erişimi için doğrulanmış LOCAL/RADIUS kaynağı, PPPoE/Hotspot türü ve router bağı gerekir.</p>)}</details>}
 </>
 :activeTab==='actions'?<><p>İşlemler menüsünden seçim yapın; önizlemedeki değişikliği onaylayın.</p>
 <section className="inventory-toolbar" aria-label="Abone işlemleri">
 {data.source==='LEGACY_DEMO'&&<LegacySubscriberActions key={r.id} id={r.id} onHistory={()=>onTab('history')} onSelect={onLegacyAction}/>}

 {data.source==='PERSISTENT_WORKSPACE'&&!writable&&<p role="status">İşlemler için ilgili routerda abone yönetim izni, kalıcı demo deposu ve doğrulanmış kaynak/router bağı gerekli.</p>}
 </section><details className="technical-info"><summary>Teknik önizlemeler</summary><SubscriberAaaDemo key={r.id+':'+r.revision+':'+r.source} source={r.source}/></details>{supplementary}</>
 :activeTab==='history'?<>{data.history.length?<ol className="registry-history">{data.history.map((e,index)=><li key={index} style={{padding:"18px",marginBottom:"16px",border:"1px solid var(--border-color, #354154)",borderRadius:"10px"}}><strong>{dailyLabels[e.operation]??({DATE_EDIT:'Bitiş tarihi düzenlendi',PLAN_CHANGE:'Paket değiştirildi',STATUS_CHANGE:'Hesap durumu değiştirildi'} as Record<string,string>)[e.operation]??detailText(e.operation)}</strong><span>{observationTime(e.occurred_at)?dateTime(e.occurred_at):'Veri yok'} · İşlemi yapan: {historyActor(e)}</span>{e.result==='FAILED'&&<span>Başarısız · Kayıt değiştirilmedi</span>}{e.result!=='FAILED'&&e.result!=='APPLIED'&&<span>Sonuç bilinmiyor</span>}{e.result!=='FAILED'&&<ul aria-label="Değişen alanlar">{changedHistoryValues(e).map(change=><li key={change.key}><strong>{change.label}</strong>: {change.previous} → {change.next}</li>)}</ul>}<details><summary>Teknik detaylar</summary><span>Aktör kimliği: {detailText(e.actor_id)}</span><span>Sonuç: {e.result==='FAILED'?'Başarısız · Kayıt değiştirilmedi':e.result==='APPLIED'?'Uygulandı · Sentetik kayıt':'Veri yok'}</span><span>İşlem UUID: {detailText(e.request_id)}</span><span>İşlem revizyonu: {e.revision??'Veri yok'} · Güncel abonelik revizyonu: {r.revision}</span><span>İşlem anındaki yetkili kaynak: {sourceLabels[subscriberSource(e.source)]}</span>{e.router_id&&<span>İşlemdeki router: <a className="record-link" href={linkedDetailHash({module:'routers',id:e.router_id,source:data.source==='PERSISTENT_WORKSPACE'?'MANAGED_DEMO':'DEMO'},typeof window==='undefined'?'':window.location.hash)}>{e.router_id}</a></span>}<p>Önceki değerler: {valuesText(e.previous_values)}</p><p>Yeni değerler: {valuesText(e.new_values)}</p>{e.error&&<p>{e.error}</p>}</details></li>)}</ol>:<p className="missing-data">Veri yok. Kayıtlı işlem geçmişi bulunmuyor.</p>}<p>Son 50 işlem · Türkiye saati (Europe/Istanbul).</p></>
 :activeTab==='connections'?<><Facts items={[["Router",routerHash?<a className="record-link" href={routerHash}>{r.router_name||'Routerı aç'}</a>:'Veri yok'],['Oturum','Bilinmiyor · canlı oturum ölçülmedi']]}/><details className="technical-info"><summary>Teknik bilgiler</summary><Facts items={[
 ['Bağlı router',routerHash?<a className="record-link" href={routerHash}>{r.router_name??r.router_id}</a>:r.router_missing?'Router kaydı bulunamadı':'Bilinmiyor · güvenli ID bağı yok'],
 ['Router modeli',r.router_model??(r.router_missing?'Router kaydı bulunamadı':'Bilinmiyor')],['Router kayıt kimliği',r.router_id??'Bilinmiyor'],
 ['Güncel yetkili kaynak',<SourceBadge source={r.source}/>],['Sentetik kayıt IP adresi',detailText(r.ip_address)==='Veri yok'?'Ölçülmedi':r.ip_address],
 ['Oturum durumu','Bilinmiyor · canlı oturum ölçülmedi'],['Son bağlantı','Bilinmiyor · bağlantı kanıtı yok'],['Son sentetik örnek',savedTime(r.last_seen_at)],
 ...(r.last_connected_at?[['Kaydedilmiş bağlantı zamanı (sentetik)',savedTime(r.last_connected_at)] as [string,ReactNode]]:[])
 ]}/><p className="missing-data">Ölçülmedi. Bağlantı/oturum açılış-kapanış kaynağı bağlı değil; sentetik hesap veya audit kaydından oturum üretilmez.</p></details>{supplementary}</>
 :<p className="missing-data">Abone detay bölümü bulunamadı.</p>}

 </section></>;
}
