import type {ScreenKey} from '../components/Sidebar';

export type SourceOption = {value:string;label:string;description:string;access:string};
export const routerSources: readonly SourceOption[] = [
 {value:'DEMO',label:'Demo envanter',description:'Mevcut örnek routerlar ve raporlar. Canlı cihaz ölçümü değildir.',access:'Sentetik kayıtlar'},
 {value:'MANAGED_DEMO',label:'Sentetik router yönetimi',description:'Ayrı kalıcı V2 çalışma alanı. Ekleme ve düzenleme yalnız sentetik kayıtları etkiler.',access:'Yetkili yerel kayıt işlemleri'},
 {value:'REGISTERED',label:'Kayıtlı cihazlar ve pilot',description:'Gerçek cihaz kayıtları ve API-SSL pilot hazırlığı. Bağlantısız kayıt ile onaylı bağlantı farklı işlemlerdir.',access:'Kayıt yönetimi · Bağlantı ayrıca onaylı'},
 {value:'V1_INVENTORY',label:'V1 aktarılmış envanter',description:'V1’den aktarılmış son envanter ve sağlık verileri. Bu ekrandan V1’e yazılmaz.',access:'Salt okunur'},
];
export const subscriberSources: readonly SourceOption[] = [
 {value:'LEGACY',label:'Mevcut demo aboneleri',description:'Mevcut demo kayıtları; LOCAL / RADIUS burada yetkili hesap kaynağıdır, canlı bağlantı değildir.',access:'Yetkili sentetik kayıt işlemleri'},
 {value:'PERSISTENT',label:'Sentetik PPPoE / Hotspot yönetimi',description:'Ayrı kalıcı abone çalışma alanı. Mevcut demo aboneleriyle birleştirilmez.',access:'Merkezi yönetici · Sentetik kayıt işlemleri'},
 {value:'HISTORY',label:'İşlem geçmişi',description:'Demo ve kalıcı çalışma alanının audit kayıtları, kendi kaynak filtreleriyle görüntülenir.',access:'Salt okunur geçmiş'},
];
export type WorkspaceContext = {label:string;description:string;access:string};
export function workspaceContext(screen:ScreenKey,hash:string):WorkspaceContext {
 const p=new URLSearchParams(hash.replace(/^#/,''));
 const local=(label:string,description:string,access:string):WorkspaceContext=>({label,description,access});
 if(screen==='routers') {
  const id=p.get('id')??'';
  const source=id.startsWith('registered-')?'REGISTERED':id.startsWith('demo-managed-router-')?'MANAGED_DEMO':id?'DEMO':p.get('source')??'DEMO';
  const option=routerSources.find(x=>x.value===source)??routerSources[0];
  return local(option.label,option.description,option.access);
 }
 if(screen==='subscribers') {
  const id=p.get('id')??'';
  const source=id.startsWith('demo-managed-sub-')?'PERSISTENT':id?'LEGACY':p.get('workspace')??'LEGACY';
  const option=subscriberSources.find(x=>x.value===source)??subscriberSources[0];
  return local(option.label,option.description,option.access);
 }
 if(screen==='radius')return local('RADIUS · Hazırlık','Entegrasyon kapsamı gösterilir. Bağlı RADIUS verisi veya canlı yönetim akışı yoktur.','Bağlantı yok');
 if(screen==='operations')return local('Sentetik operasyon kayıtları','Kayıtlı demo alarmları ve olayları. ACK ve okundu işlemleri mevcut sunucu yetkilerine bağlıdır.','Yetkiye bağlı alarm işlemleri');
 if(screen==='mikajani')return local('Sentetik analiz','Kayıtlı demo verisi veya seçilen ayrı senaryo. Öneriler otomatik uygulanmaz.','Salt okunur');
 if(screen==='dashboard'&&p.get('dashboard_source')==='V1_INVENTORY'&&(!p.get('view')||p.get('view')==='OVERVIEW'))return local('V1 aktarılmış envanter','Son kayıtlı envanter ve sağlık verileri; canlı bağlantı kanıtı değildir.','Salt okunur');
 return local('V2 demo çalışma alanı','Sentetik veriler kullanılır. Kayıt işlemleri mevcut kaynak ve sunucu yetkileriyle sınırlıdır.','Yetkiye bağlı V2 kayıt işlemleri');
}
