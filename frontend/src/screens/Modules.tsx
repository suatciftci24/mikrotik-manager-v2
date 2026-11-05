import { Activity, CircleDollarSign, Database, RadioTower, Settings2, ShieldCheck, Sparkles, UserRoundCog, Workflow } from 'lucide-react';
import type { ReactNode } from 'react';
import { PageHeading } from '../components/PageHeading';
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
 return <div className="screen-stack"><PageHeading title={screen==='radius'?'RADIUS Merkezi':value.title} eyebrow="HAZIRLIK · BAĞLANTI YOK" description={value.description}/><section className="panel module-overview"><EmptyModule icon={value.icon} title={`${value.title} hazırlanıyor`} description="Bu ekranda canlı veri veya yönetim işlemi bulunmuyor."/></section><details className="panel center-disclosure"><summary>Planlanan kapsam ve bağlantı sınırları</summary><ul>{value.features.map(feature=><li key={feature}>{feature}</li>)}</ul><p>LOCAL / RADIUS yetkili kaynak ayrımı korunur. FreeRADIUS bağlantısı ve NAS yönetimi bu ekranda etkin değildir.</p><p>Bu hazırlık ekranı herhangi bir veritabanının çalışma durumunu doğrulamaz.</p></details></div>;
}
