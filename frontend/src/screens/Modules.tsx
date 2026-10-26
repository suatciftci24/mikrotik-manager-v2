import { Activity, CircleDollarSign, Database, RadioTower, Settings2, ShieldCheck, Sparkles, UserRoundCog, Workflow } from 'lucide-react';
import type { ReactNode } from 'react';
import { EmptyModule } from '../components/Status';
import type { ScreenKey } from '../components/Sidebar';

const content: Partial<Record<ScreenKey,{title:string;description:string;icon:ReactNode;features:string[]}>> = {
  radius: {title:'RADIUS Entegrasyonu',description:'FreeRADIUS adaptör sınırı ve NAS kimlik modeli hazır. Bu çalışma alanında RADIUS sunucusuna bağlanılmaz.',icon:<RadioTower size={24}/>,features:['FreeRADIUS adaptör sözleşmesi','LOCAL / RADIUS kaynak ayrımı','Kimlik ve NAS görünümü']},
  operations: {title:'Operasyon Merkezi',description:'Olay akışı, görev kuyruğu ve denetim izleri için modül alanı hazır.',icon:<Workflow size={24}/>,features:['Merkezi olay zaman çizelgesi','Audit kayıtları','İş ve görev görünümü']},
  mikajani: {title:'MikAjanı',description:'Ağ sağlığı, açıklanabilir teşhis ve salt okunur öneriler için modül alanı hazır.',icon:<Activity size={24}/>,features:['Router sağlık özeti','İncelenebilir bulgular','Salt okunur analiz sözleşmesi']},
  system: {title:'Sistem ve Kullanıcı Yönetimi',description:'Kullanıcı, rol ve izin temeli V2 modelinde tanımlı. Demo çalışma alanında yönetim değişikliği yapılmaz.',icon:<UserRoundCog size={24}/>,features:['Merkezi roller ve izinler','Panel kullanıcıları','Sistem yapılandırması']},
};
export function ModuleScreen({screen}:{screen:ScreenKey}) {
 const value=content[screen]; if(!value) return null;
 return <div className="screen-stack"><section className="page-heading-row"><div><div className="eyebrow"><span className="eyebrow-line"/>V2 DOMAIN MODULE</div><h1>{value.title}</h1><p>Bağımsız alan arayüzü · fazlı geliştirme</p></div><span className="phase-pill"><Sparkles size={14}/> FAZ 1 İSKELETİ</span></section><div className="module-layout"><section className="panel module-overview"><EmptyModule icon={value.icon} title={`${value.title} hazırlanıyor`} description={value.description}/></section><aside className="panel module-scope"><span className="eyebrow">ALAN SINIRI</span><h3>Bu modülde</h3><div className="scope-list">{value.features.map((feature,i)=><div key={feature}><span className="scope-number">0{i+1}</span><span>{feature}</span></div>)}</div><div className="scope-note"><ShieldCheck size={15}/>Modül sınırları V2 API ve adaptör sözleşmeleriyle korunur.</div></aside></div><div className="module-integrations"><span className="eyebrow">BAĞLANTI DURUMU</span><div className="integration-list"><span><RadioTower size={15}/>FreeRADIUS <i>Bağlı değil</i></span><span><Database size={15}/>V2 PostgreSQL <i>Faz 1'de kullanılmıyor</i></span><span><Settings2 size={15}/>Harici çalışma <i>Kapalı</i></span><span><CircleDollarSign size={15}/>Üretim verisi <i>Kullanılmıyor</i></span></div></div></div>;
}
