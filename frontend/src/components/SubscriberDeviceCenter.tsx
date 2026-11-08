import {canChangeWorkspace} from '../lib/subscriberActions';
import {LegacySubscriberActions} from './LegacySubscriberActions';
import {dailyLabels} from '../lib/subscriberManagementCenter';
import {expiryDate} from '../lib/expiry';
import {useEffect,useRef,useState,type KeyboardEvent,type ReactNode} from 'react';
import {useResource} from '../lib/useResource';
import {subscriberCenterTabs,safeSubscriberCenter,subscriberRouterHash,accountStatus,type SubscriberCenterData,type SubscriberTab,type CenterSubscriber} from '../lib/subscriberCenter';
import {ResourceState,Facts,dateTime} from './Resource';
import {PageHeading} from './PageHeading';
import {ExpirySummary} from './Expiry';
import {useTurkeyToday} from '../lib/useTurkeyToday';
const dependencies=['/subscribers','/subscriber-workspace'] as const;
export function SubscriberDeviceCenter({id,onBack,onEdit,onRenew,onManage,legacy}:{id:string;onBack:()=>void;onEdit?:(item:CenterSubscriber)=>void;onRenew?:(item:CenterSubscriber)=>void;onManage?:(item:CenterSubscriber)=>void;legacy?:ReactNode}){
 const resource=useResource<SubscriberCenterData>('/subscriber-center/'+encodeURIComponent(id),undefined,dependencies);
 const [tab,setTab]=useState<SubscriberTab>('overview');const heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{const read=()=>{const value=new URLSearchParams(window.location.hash.slice(1)).get('tab');setTab(subscriberCenterTabs.some(([key])=>key===value)?value as SubscriberTab:'overview');};read();heading.current?.focus();window.scrollTo(0,0);window.addEventListener('hashchange',read);return()=>window.removeEventListener('hashchange',read);},[id]);
 const data=resource.data;const error=resource.error||(data&&!safeSubscriberCenter(data,id)?'Abone kaynağı veya router ID bağı doğrulanamadı; detay gösterilmedi.':undefined);
 return <section className="screen-stack"><button className="detail-back button-secondary" onClick={onBack}>← Abone listesine dön</button><PageHeading title="Abone Detay Merkezi" eyebrow="SENTETİK DEMO · CANLI İŞLEM YOK" description="Kayıtlı hesap bilgileri gösterilir; cihaz ve RADIUS bağlantısı başlatılmaz." headingRef={heading}/><ResourceState {...resource} error={error}/>{data&&!resource.loading&&!error&&<SubscriberDeviceCenterView data={data} tab={tab} onTab={setTab} onEdit={onEdit} onRenew={onRenew} onManage={onManage} legacy={legacy}/>}</section>;
}
export function SubscriberDeviceCenterView({data,tab,onTab,onEdit,onRenew,onManage,legacy}:{data:SubscriberCenterData;tab:SubscriberTab;onTab:(tab:SubscriberTab)=>void;onEdit?:(item:CenterSubscriber)=>void;onRenew?:(item:CenterSubscriber)=>void;onManage?:(item:CenterSubscriber)=>void;legacy?:ReactNode}){
 const writable=canChangeWorkspace(data,!!(onEdit||onRenew||onManage));
 const r=data.item;const today=useTurkeyToday();const buttons=useRef<(HTMLButtonElement|null)[]>([]);const [expanded,setExpanded]=useState(false);const routerHash=subscriberRouterHash(r,typeof window==='undefined'?'':window.location.hash);
 function key(event:KeyboardEvent,index:number){let next=index;if(event.key==='ArrowRight')next=(index+1)%subscriberCenterTabs.length;else if(event.key==='ArrowLeft')next=(index+subscriberCenterTabs.length-1)%subscriberCenterTabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=subscriberCenterTabs.length-1;else return;event.preventDefault();onTab(subscriberCenterTabs[next][0]);buttons.current[next]?.focus();}
 return <><section className="panel registry-detail router-device-summary"><section className="inventory-toolbar" aria-label="Abone hızlı işlemleri">
{data.source==='LEGACY_DEMO'&&<LegacySubscriberActions key={r.id} id={r.id}/>}
{writable&&onEdit&&
<button className="button-secondary" onClick={()=>onEdit(r)}>
Profil / Paket, Durum ve EXPIRE Düzenle
</button>}
{writable&&onRenew&&
<button className="button-secondary" onClick={()=>onRenew(r)}>
Abonelik Süresini Uzat
</button>}
{writable&&onManage&&
<button className="button-secondary" onClick={()=>onManage(r)}>
Günlük İşlemler
</button>}
</section><div className="page-heading-row"><div><span className="eyebrow">SENTETİK ABONE · {r.access_type??'ERİŞİM TÜRÜ BİLİNMİYOR'}</span><h2>{r.customer_name}</h2><p>{r.username} · {accountStatus(r.status)}</p></div>{writable&&onManage&&<button className="button-primary" onClick={()=>onManage(r)}>Paket değiştir / Aktif · Pasif</button>}</div><Facts items={[
 ['Bağlı router',routerHash?<a className="record-link" href={routerHash}>{r.router_name??r.router_id}</a>:r.router_missing?'Router kaydı bulunamadı':'Bilinmiyor · güvenli ID bağı yok'],['Router modeli',r.router_model??(r.router_missing?'Router kaydı bulunamadı':'Bilinmiyor')],['Router kayıt kimliği',r.router_id??'Bilinmiyor'],['Profil / Paket',r.plan],['Yetkili kaynak',r.source??'Bilinmiyor'],['Oturum durumu','Bilinmiyor · canlı oturum ölçülmedi'],['Sentetik kayıt IP adresi',r.ip_address??'Ölçülmedi'],['Son bağlantı',r.last_connected_at?dateTime(r.last_connected_at):'Bilinmiyor · bağlantı kanıtı yok'],['Son sentetik örnek',r.last_seen_at?dateTime(r.last_seen_at):'Bilinmiyor']
 ]}/><ExpirySummary expiresOn={r.expires_on} today={today}/><p>Hesap etkinliği veya EXPIRE tarihi çevrimiçi oturum kanıtı değildir.</p></section>
 <div className="filter-tabs router-device-tabs" role="tablist" aria-label="Abone detay bölümleri">{subscriberCenterTabs.map(([id,label],index)=><button key={id} ref={node=>{buttons.current[index]=node;}} role="tab" id={'subscriber-tab-'+id} aria-controls={'subscriber-panel-'+id} aria-selected={tab===id} tabIndex={tab===id?0:-1} onKeyDown={event=>key(event,index)} onClick={()=>onTab(id)} className={tab===id?'selected':''}>{label}</button>)}</div>
 <section className="panel registry-detail router-device-panel" role="tabpanel" id={'subscriber-panel-'+tab} aria-labelledby={'subscriber-tab-'+tab} tabIndex={0}><h2>{subscriberCenterTabs.find(([key])=>key===tab)?.[1]}</h2>
 {tab==='overview'?<><Facts items={[["Kayıt kimliği",r.id],["Router ID",r.router_id??'Bilinmiyor'],['Veri deposu',data.persistence],['Revizyon',r.revision]]}/><p>PPPoE ve Hotspot erişim türleri ayrı saklanır. Tek yetkili kaynak LOCAL veya RADIUS'tur; gerçek kaynakta işlem yapılmaz.</p>{legacy&&<details onToggle={e=>setExpanded(e.currentTarget.open)}><summary>Mevcut demo işlemleri ve raporları</summary>{expanded&&legacy}</details>}</>
 :tab==='package'?<><Facts items={[["Profil / Paket",r.plan],['Hesap durumu',accountStatus(r.status)],['Erişim türü',r.access_type??'Bilinmiyor']]}/><p>Bu alan sentetik hesap tanımıdır; gerçek cihaz veya RADIUS profili uygulanmaz.</p>{writable&&onManage&&<button className="button-primary" onClick={()=>onManage(r)}>Paket değiştir · Aktif / Pasif</button>}</>
 :tab==='expiry'?<><ExpirySummary expiresOn={r.expires_on} today={today}/><p>EXPIRE yalnız kaydedilmiş sentetik takvim tarihidir. Eksik tarih katılım veya bağlantı zamanından türetilmez.</p>{writable&&onRenew&&<button className="button-primary" onClick={()=>onRenew(r)}>Hızlı İşlemler · Aboneliği uzat</button>}</>
 :tab==='history'?<>{data.history.length?<ol className="registry-history">{data.history.map((e,index)=><li key={index}><strong>{dailyLabels[e.operation]??(e.operation==='CREATE'?'Sentetik kayıt eklendi':e.operation==='UPDATE'?'Sentetik kayıt düzenlendi':e.operation==='RENEWAL'?'Abonelik uzatıldı':e.operation==='DATE_EDIT'?'Bitiş tarihi düzenlendi':e.operation==='PLAN'||e.operation==='PLAN_CHANGE'?'Paket değiştirildi':e.operation==='STATUS'||e.operation==='STATUS_CHANGE'?'Hesap durumu değiştirildi':'Kaydedilmiş demo işlemi')}</strong><span>{dateTime(e.occurred_at)} · {e.actor_id}</span>{e.date_changed&&<span>Eski bitiş: {expiryDate(e.previous_expires_on)} → Yeni bitiş: {expiryDate(e.expires_on)}</span>}<span>Sonuç: {e.result==='FAILED'?'Başarısız · Kayıt değiştirilmedi':'Uygulandı · Sentetik kayıt'}</span>{e.router_id&&<span>Router: {e.router_id}</span>}{e.new_values&&Object.keys(e.new_values).length>0&&<div className="registry-history-changes">
{Object.entries(e.new_values).filter(([field])=>!e.date_changed||field!=='expires_on').map(([field,value])=><div key={field}>
<strong>{({
plan:'Paket',profile:'Profil',monthly_price:'Aylık ücret (TL)',status:'Hesap durumu',
expires_on:'EXPIRE / Bitiş tarihi',source:'Abone kaynağı',
access_type:'Bağlantı türü'
} as Record<string,string>)[field]??field}</strong>: {String((e.previous_values as Record<string,unknown>|undefined)?.[field]??'Belirtilmemiş')} → {String(value??'Belirtilmemiş')}
</div>)}
</div>}{e.error&&<span>{e.error}</span>}{e.revision!==null&&<span>Revizyon {e.revision}</span>}</li>)}</ol>:<p>Kayıtlı işlem geçmişi bulunmuyor.</p>}<p>En fazla son 50 kayıt işlemi; bağlantı geçmişi değildir. Zamanlar Türkiye saatinde (Europe/Istanbul) gösterilir.</p></>
 :<p className="missing-data">Ölçülmedi. Bağlantı/oturum açılış-kapanış kaynağı bağlı değil; sentetik hesap veya audit kaydından oturum üretilmez.</p>}
 </section></>;
}
