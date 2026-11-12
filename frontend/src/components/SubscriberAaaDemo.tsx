import {api} from '../lib/api';
import {useState} from 'react';
import {useResource} from '../lib/useResource';
import {Facts,ResourceState,dateTime} from './Resource';
import {subscriberSource} from '../lib/source';
import './subscriber-aaa-demo.css';

type Scenario='PLAN'|'COMPENSATION'|'RECONCILIATION';
export type AaaDemoPreview={mode:'SYNTHETIC_FIXTURE_ONLY';scenario:Scenario;account_id:'demo-sub-aaa-memory';request_id:string;correlation_id:string;fingerprint:string;history_persistence:'DISPOSABLE_MEMORY';result:{label:string;outcome:'PASS'|'BLOCKED';live_ready:false;external_writes:false;simulated_final_authority:string|null;simulated_final_revision:number|null;blockers:string[]};events:{revision:number;state:string;at:string;correlation_id:string;actor_id:string}[]};
const labels:Record<Scenario,string>={PLAN:'LOCAL → RADIUS: yalnız plan',COMPENSATION:'Kaynak geçişi sonrası telafi',RECONCILIATION:'Telafi çatışması / uzlaştırma'};
const scenarioGuides:Record<Scenario,{description:string;target:string;risk:string;intervention:string}>={
 PLAN:{description:'Örnek LOCAL hesabın RADIUS kaynağına geçiş planını inceleyin. Hesap değiştirilmez.',target:'RADIUS yönetimi (yalnız model)',risk:'Kimlik, NAS, profil ve geçiş yetkisi canlı ortamda doğrulanmadı.',intervention:'Planı inceleyin. Gerçek geçiş için ayrıca güncel kaynak, yetki ve eşleme kanıtları gerekir.'},
 COMPENSATION:{description:'Kaynak geçişinden sonra oluşan örnek hatada güvenli dönüşün nasıl modellendiğini görün.',target:'LOCAL kaynağına dönüş (yalnız telafi modeli)',risk:'Geçişin yarıda kalması iki yetkili kaynak oluşturabilir. Gerçek hesap ve oturum durumu bu örnekte okunmaz.',intervention:'Telafi modelini inceleyin. Gerçek geri dönüşten önce kaynak ve hedef durumları yeniden doğrulanmalıdır.'},
 RECONCILIATION:{description:'Telafi sırasında revizyon çatışması olduğunda otomatik değişikliğin neden durduğunu görün.',target:'Kaynak kararından önce kanıtlı uzlaştırma',risk:'Kaynak revizyonu değişmiş olabilir; otomatik geri dönüş güvenli değildir.',intervention:'İşlemi durdurun. Güncel kaynak, hedef ve revizyon kanıtlarını salt okunur inceleyin; otomatik tekrar yapmayın.'},
};
const states:Record<string,string>={RESERVED:'İstek ayrıldı',PLANNED:'Planlandı',MODELED:'Modellendi',COMPENSATING:'Telafi modelleniyor',COMPENSATED:'Telafi modellendi',RECONCILIATION:'Salt okunur uzlaştırma gerekli'};
export function SubscriberAaaDemo({source}:{source:unknown}){
 const [open,setOpen]=useState(false);
 return <section className="aaa-demo" aria-label="Merkezi AAA demo"><h3>Merkezi AAA — sentetik önizleme</h3>
 <p>Güncel yetkili kaynak: <strong>{subscriberSource(source)==='UNKNOWN'?'BELİRSİZ':subscriberSource(source)}</strong>. Kaynak değişikliği bu panelden uygulanmaz.</p>
 <p>Örnek AAA geçmişi seçili aboneye ait değildir. Sabit demo hesabı kullanılır; abone ve audit kayıtları değişmez.</p>
 <button type="button" className="button-secondary" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'AAA demo önizlemesini kapat':'AAA demo önizlemesini aç'}</button>
 {open&&<AaaDemoScenarios/>}</section>;
}
export function CentralAaaManagement(){
 const [open,setOpen]=useState(false);
 return <section className="panel aaa-demo aaa-management" aria-label="Merkezi AAA yönetimi"><h2>Merkezi AAA yönetimi</h2>
 <p>Hesap görünürlüğü ve geçiş ön incelemesi aşağıdadır. Bu bölümdeki plan, telafi ve uzlaştırma aynı sentetik AAA akışını gösterir.</p>
 <div className="aaa-operation-boundary"><strong>Sentetik önizleme</strong><p>Sabit örnek hesap kullanılır; seçili depo, arama ve kaynak filtrelerinden bağımsızdır. Hiçbir abonenin geçmişi veya canlı işlem sonucu değildir.</p><strong>Gerçek AAA işlemleri bağlı değil</strong><p>Router veya FreeRADIUS üzerinde kaynak değiştirme ve işlem uygulama bu merkezde kullanılamaz.</p></div>
 <button type="button" className="button-secondary" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'Sentetik senaryoları kapat':'Sentetik senaryoları incele'}</button>
 {open&&<AaaDemoScenarios/>}</section>;
}
export function loadAaaDemoPreview(path:string,init?:RequestInit){
 return api<AaaDemoPreview>(path,{...init,method:'GET'});
}
export function AaaDemoScenarios(){
 const [scenario,setScenario]=useState<Scenario>('PLAN');
 const resource=useResource<AaaDemoPreview>('/aaa-demo/preview?scenario='+scenario,loadAaaDemoPreview);
 return <><label className="form-label">Örnek senaryo<select value={scenario} onChange={e=>setScenario(e.target.value as Scenario)}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><p className="aaa-scenario-description">{scenarioGuides[scenario].description}</p><ResourceState {...resource}/>{!resource.loading&&!resource.error&&resource.data&&<AaaDemoResult data={resource.data} scenario={scenario}/>}</>;
}
export function AaaDemoResult({data,scenario}:{data:AaaDemoPreview;scenario:Scenario}){
 if(data.mode!=='SYNTHETIC_FIXTURE_ONLY'||data.account_id!=='demo-sub-aaa-memory'||data.scenario!==scenario||data.history_persistence!=='DISPOSABLE_MEMORY'||data.result.live_ready!==false||data.result.external_writes!==false)return <p role="alert">AAA demo sözleşmesi doğrulanamadı; sonuç gösterilmedi.</p>;
 const guide=scenarioGuides[scenario];
 const outcome=data.result.outcome==='PASS'?'Örnek geçiş planı oluşturuldu.':scenario==='COMPENSATION'&&data.events.at(-1)?.state==='COMPENSATED'?'Örnek hata sonrası telafi modellendi; geçiş başarılı sayılmadı.':scenario==='RECONCILIATION'&&data.events.at(-1)?.state==='RECONCILIATION'?'Örnek çatışma nedeniyle model durdu; uzlaştırma gerekiyor.':'Örnek işlem bloke oldu; devam etmeden nedenleri inceleyin.';
 return <div className="aaa-demo-result"><p role="status">{outcome} Gerçek işlem yapılmadı.</p>
 <Facts items={[
 ['Başlangıç durumu','LOCAL · sabit örnek hesap'],['Hedef durum',guide.target],
 ['Son bilinen model durumu',data.result.simulated_final_authority??'BELİRSİZ'],
 ['Risk',guide.risk],['Gerekli kullanıcı müdahalesi',data.result.outcome==='BLOCKED'&&scenario==='PLAN'?'Plan bloke oldu. Teknik ayrıntılardaki nedenleri inceleyin; gerçek geçiş başlatmayın.':guide.intervention],
 ]}/>
 <p>Canlı hazırlık doğrulanmadı. Abone kayıtları ve kalıcı audit değişmez.</p>
 <details className="aaa-technical"><summary>Teknik ayrıntılar ve örnek işlem izi</summary>
 <Facts items={[["Örnek hesap",data.account_id],['İstek UUID',data.request_id],['Korelasyon UUID',data.correlation_id],['Fingerprint (SHA-256)',data.fingerprint],['Model hesap revizyonu',data.result.simulated_final_revision],['Teknik sonuç',data.result.label]]}/>
 {data.result.blockers.length>0&&<p>Modelin durma nedenleri: {data.result.blockers.join(', ')}</p>}
 <h4>Örnek AAA işlem geçmişi</h4><p>Geçici bellekte yeniden üretilir; kalıcı audit veya seçili abonenin işlem kanıtı değildir. Zamanlar Türkiye saatindedir.</p>
 <ol className="registry-history">{data.events.map(event=><li key={event.revision}><strong>{states[event.state]??event.state} · İşlem revizyonu {event.revision}</strong><span>{dateTime(event.at)} · Örnek aktör: {event.actor_id}</span><span>Korelasyon: {event.correlation_id}</span></li>)}</ol></details></div>;
}
