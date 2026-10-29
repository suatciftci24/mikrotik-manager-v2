import {useEffect,useRef,useState,type KeyboardEvent,type ReactNode} from 'react';
import {useResource} from '../lib/useResource';
import {subscriberCenterTabs,safeSubscriberCenter,subscriberRouterHash,accountStatus,type SubscriberCenterData,type SubscriberTab,type CenterSubscriber} from '../lib/subscriberCenter';
import {ResourceState,Facts,dateTime} from './Resource';
import {PageHeading} from './PageHeading';
import {ExpirySummary} from './Expiry';
import {useTurkeyToday} from '../lib/useTurkeyToday';
const dependencies=['/subscribers','/subscriber-workspace'] as const;
export function SubscriberDeviceCenter({id,onBack,onEdit,legacy}:{id:string;onBack:()=>void;onEdit?:(item:CenterSubscriber)=>void;legacy?:ReactNode}){
 const resource=useResource<SubscriberCenterData>('/subscriber-center/'+encodeURIComponent(id),undefined,dependencies);
 const [tab,setTab]=useState<SubscriberTab>('overview');const heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{setTab('overview');heading.current?.focus();window.scrollTo(0,0);},[id]);
 const data=resource.data;const error=resource.error||(data&&!safeSubscriberCenter(data,id)?'Abone kaynağı veya router ID bağı doğrulanamadı; detay gösterilmedi.':undefined);
 return <section className="screen-stack"><button className="detail-back button-secondary" onClick={onBack}>← Abone listesine dön</button><PageHeading title="Abone Detay Merkezi" eyebrow="SENTETİK DEMO · CANLI İŞLEM YOK" description="Kayıtlı hesap bilgileri gösterilir; cihaz ve RADIUS bağlantısı başlatılmaz." headingRef={heading}/><ResourceState {...resource} error={error}/>{data&&!resource.loading&&!error&&<SubscriberDeviceCenterView data={data} tab={tab} onTab={setTab} onEdit={onEdit} legacy={legacy}/>}</section>;
}
export function SubscriberDeviceCenterView({data,tab,onTab,onEdit,legacy}:{data:SubscriberCenterData;tab:SubscriberTab;onTab:(tab:SubscriberTab)=>void;onEdit?:(item:CenterSubscriber)=>void;legacy?:ReactNode}){
 const r=data.item;const today=useTurkeyToday();const buttons=useRef<(HTMLButtonElement|null)[]>([]);const [expanded,setExpanded]=useState(false);const routerHash=subscriberRouterHash(r);
 function key(event:KeyboardEvent,index:number){let next=index;if(event.key==='ArrowRight')next=(index+1)%subscriberCenterTabs.length;else if(event.key==='ArrowLeft')next=(index+subscriberCenterTabs.length-1)%subscriberCenterTabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=subscriberCenterTabs.length-1;else return;event.preventDefault();onTab(subscriberCenterTabs[next][0]);buttons.current[next]?.focus();}
 return <><section className="panel registry-detail router-device-summary"><div className="page-heading-row"><div><span className="eyebrow">SENTETİK ABONE · {r.access_type??'ERİŞİM TÜRÜ BİLİNMİYOR'}</span><h2>{r.customer_name}</h2><p>{r.username} · {accountStatus(r.status)}</p></div>{data.source==='PERSISTENT_WORKSPACE'&&onEdit&&<button className="button-secondary" onClick={()=>onEdit(r)}>Sentetik aboneyi düzenle</button>}</div><Facts items={[
 ['Bağlı router',routerHash?<a className="record-link" href={routerHash}>{r.router_name??r.router_id}</a>:'Bilinmiyor · güvenli ID bağı yok'],['Profil / Paket',r.plan],['Yetkili kaynak',r.source??'Bilinmiyor'],['Oturum durumu','Bilinmiyor · canlı oturum ölçülmedi'],['Sentetik kayıt IP adresi',r.ip_address??'Ölçülmedi'],['Son bağlantı',r.last_connected_at?dateTime(r.last_connected_at):'Bilinmiyor · bağlantı kanıtı yok'],['Son sentetik örnek',r.last_seen_at?dateTime(r.last_seen_at):'Bilinmiyor']
 ]}/><p>Hesap etkinliği veya EXPIRE tarihi çevrimiçi oturum kanıtı değildir.</p></section>
 <div className="filter-tabs router-device-tabs" role="tablist" aria-label="Abone detay bölümleri">{subscriberCenterTabs.map(([id,label],index)=><button key={id} ref={node=>{buttons.current[index]=node;}} role="tab" id={'subscriber-tab-'+id} aria-controls={'subscriber-panel-'+id} aria-selected={tab===id} tabIndex={tab===id?0:-1} onKeyDown={event=>key(event,index)} onClick={()=>onTab(id)} className={tab===id?'selected':''}>{label}</button>)}</div>
 <section className="panel registry-detail router-device-panel" role="tabpanel" id={'subscriber-panel-'+tab} aria-labelledby={'subscriber-tab-'+tab} tabIndex={0}><h2>{subscriberCenterTabs.find(([key])=>key===tab)?.[1]}</h2>
 {tab==='overview'?<><Facts items={[["Kayıt kimliği",r.id],["Router ID",r.router_id??'Bilinmiyor'],['Veri deposu',data.persistence],['Revizyon',r.revision]]}/><p>PPPoE ve Hotspot erişim türleri ayrı saklanır. Tek yetkili kaynak LOCAL veya RADIUS'tur; gerçek kaynakta işlem yapılmaz.</p>{legacy&&<details onToggle={e=>setExpanded(e.currentTarget.open)}><summary>Mevcut demo işlemleri ve raporları</summary>{expanded&&legacy}</details>}</>
 :tab==='package'?<><Facts items={[["Profil / Paket",r.plan],['Hesap durumu',accountStatus(r.status)],['Erişim türü',r.access_type??'Bilinmiyor']]}/><p>Bu alan sentetik hesap tanımıdır; gerçek cihaz veya RADIUS profili uygulanmaz.</p></>
 :tab==='expiry'?<><ExpirySummary expiresOn={r.expires_on} today={today}/><p>EXPIRE yalnız kaydedilmiş sentetik takvim tarihidir. Eksik tarih katılım veya bağlantı zamanından türetilmez.</p></>
 :tab==='history'?<>{data.history.length?<ol className="registry-history">{data.history.map((e,index)=><li key={index}><strong>{e.operation==='CREATE'?'Sentetik kayıt eklendi':e.operation==='UPDATE'?'Sentetik kayıt düzenlendi':'Kaydedilmiş demo işlemi'}</strong><span>{dateTime(e.occurred_at)} · {e.actor_id}</span>{e.revision!==null&&<span>Revizyon {e.revision}</span>}</li>)}</ol>:<p>Kayıtlı işlem geçmişi bulunmuyor.</p>}<p>En fazla son 50 kayıt işlemi; bağlantı geçmişi değildir.</p></>
 :<p className="missing-data">Ölçülmedi. Bağlantı/oturum açılış-kapanış kaynağı bağlı değil; sentetik hesap veya audit kaydından oturum üretilmez.</p>}
 </section></>;
}
