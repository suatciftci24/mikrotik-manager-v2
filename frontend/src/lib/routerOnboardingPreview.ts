import {candidatePayload,emptyRouterForm,type RouterForm,type RegisteredRouter} from './routerRegistry.ts';

/** Pure offline checks; cannot return a verification ID or a register command. */
export function offlineRouterPreview(form:RouterForm,item?:RegisteredRouter){
 const value=candidatePayload(form,'offline-form-check',item);
 if(value.ca_pem&&!/^(?:\s*-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+\s+-----END CERTIFICATE-----\s*)+$/.test(value.ca_pem))
  throw new Error('Public CA, PEM sertifikası olmalı. BEGIN CERTIFICATE / END CERTIFICATE satırlarıyla birlikte yapıştırın veya PEM dosyası yükleyin.');
 return {is_demo:true as const,persisted:false as const,device_connected:false as const,
  name:value.name,endpoint:`${value.management_address}:${value.port}`,
  credentials:item&&(!value.username||!value.password)?'Boş alanlar için mevcut bilgiler korunacak':'Gerekli giriş alanları dolu',
  certificate:value.ca_pem?'PEM metin biçimi uygun; sertifika zinciri doğrulanmadı':'Kayıtlı public CA korunacak',
  pin:'64 hexadecimal karakter; cihaz sertifikasıyla eşleşme doğrulanmadı',
  identity:'Cihaz kimliği / model / sürüm okunmadı',
  trust:'TLS zinciri, IP SAN ve leaf pin yalnız gerçek bağlantıda backend tarafından doğrulanır.'};
}
export function syntheticRouterPreview(){
 return offlineRouterPreview({...emptyRouterForm,name:'Sentetik örnek router',management_address:'192.0.2.10',
  username:'synthetic-example',password:'SYNTHETIC_PREVIEW_ONLY',
  ca_pem:'-----BEGIN CERTIFICATE-----\nU1lOVEhFVElDX09OTFk=\n-----END CERTIFICATE-----',leaf_sha256:'a'.repeat(64)});
}
