import type {PilotIdentity} from './pilotOperator';
export type RegisteredRouter={
  pilot_kind?:'CEBECI_TOWERS'|null;id:string;name:string;management_address:string;port:number;identity:string;model:string;routeros_version:string;
  revision:number;last_checked_at:string;last_success_at:string;last_error:string|null;
  status:'VERIFIED'|'STALE'|'CHECK_FAILED';leaf_sha256:string;source_ip:string;
  expected_identity:string;expected_version:string;credentials_configured:boolean;is_demo:false;continuous_monitoring:false;
};
export type RegistryOptions={pilot_identity?:PilotIdentity|null;operator_candidate?:{id:string;revision:number;source:'V2_AUTHENTICATED_SESSION'}|null;connection_enabled:boolean;operator_authorized:boolean;source_ip:string|null;allowed_networks:string[];allowed_ports:number[];tls_required:true;pin_required:true;read_only:true;automatic_polling:false;is_demo:false};
export type RouterForm={name:string;management_address:string;port:string;expected_identity:string;expected_version:string;username:string;password:string;ca_pem:string;leaf_sha256:string};
export type Verification={verification_id:string;state:'RUNNING'|'VERIFIED'|'FAILED'|'SAVED'|'CANCELLED'|'EXPIRED';expires_at:string;error_code:string|null;saved_router_id:string|null;
  preview?:{name:string;management_address:string;port:number;metadata:{identity:string;model:string;routeros_version:string};source_ip:string;checked_at:string;expected_revision:number};is_demo:false};
export const emptyRouterForm:RouterForm={name:'',management_address:'',port:'8729',expected_identity:'',expected_version:'',username:'',password:'',ca_pem:'',leaf_sha256:''};
export function routerForm(item?:RegisteredRouter):RouterForm{return item?{...emptyRouterForm,name:item.name,management_address:item.management_address,port:String(item.port),expected_identity:item.identity,expected_version:item.expected_version,leaf_sha256:item.leaf_sha256}:{...emptyRouterForm};}
export function candidatePayload(form:RouterForm,requestId:string,item?:RegisteredRouter){
  if(!form.name.trim())throw new Error('Router adı gerekli.');
  for(const [value,label,max] of [[form.name,'Router adı',120],[form.expected_identity,'Beklenen cihaz kimliği',120],[form.expected_version,'Beklenen RouterOS sürümü',40]] as const){
    if(value.length>max)throw new Error(`${label} en fazla ${max} karakter olabilir.`);
    if(/[\x00-\x1f]/.test(value))throw new Error(`${label} kontrol karakteri içeremez.`);
  }
  if(form.username.length>128)throw new Error('API kullanıcı adı en fazla 128 karakter olabilir.');
  if(form.ca_pem.length>262144)throw new Error('Public CA PEM en fazla 262144 karakter olabilir.');
  const octets=form.management_address.split('.');
  if(octets.length!==4||octets.some(value=>!/^\d{1,3}$/.test(value)||Number(value)>255||String(Number(value))!==value))throw new Error('Geçerli IPv4 yönetim adresi girin.');
  const port=Number(form.port);
  if(!Number.isInteger(port)||port<1024||port>65535||port===8728)throw new Error('Geçerli API-SSL portu girin; API 8728 kullanılamaz.');
  if(!/^[a-f0-9]{64}$/.test(form.leaf_sha256))throw new Error('Leaf SHA-256 pin, 64 küçük hexadecimal karakter olmalı.');
  if(!item&&(!form.username||!form.password||!form.ca_pem))throw new Error('API kullanıcı adı, parola ve public CA zorunlu.');
  if(form.ca_pem.includes('PRIVATE KEY'))throw new Error('Yalnız public CA sertifikası yükleyin; özel anahtar kabul edilmez.');
  return {request_id:requestId,name:form.name.trim(),management_address:form.management_address,port,expected_identity:form.expected_identity.trim(),expected_version:form.expected_version.trim(),
    username:form.username,password:form.password||null,ca_pem:form.ca_pem,leaf_sha256:form.leaf_sha256,router_id:item?.id??null,expected_revision:item?.revision??0,confirmed_read_only:true};
}
const errors:Record<string,string>={
 PILOT_SCOPE_MISMATCH:'Pilot hedefi, kaynak IP veya kayıtlı kimlik CEBECI_TOWERS kapsamıyla eşleşmiyor.',
 PILOT_ACCOUNT_MISMATCH:'Güvenli pilot referansı v2-cebeci-ro hesabına ait değil.',
 READ_SCOPE_REJECTED:'İstenen okuma salt okunur pilot kapsamı dışında.',
 ROW_LIMIT:'Okuma kayıt sınırı aşıldı; kısmi veri veya eksik sayım kaydedilmedi.',
 READ_ONLY_RESPONSE_REJECTED:'Cihazdan beklenen güvenli alanlar alınamadı; snapshot kaydedilmedi.',
 RESOURCE_METRICS_REJECTED:'CPU/RAM/uptime alanları geçersiz; ölçüm uydurulmadı.',
 ROUTER_NOT_FOUND:'Router kaydı bulunamadı. Listeyi yenileyip güncel bir kayıt seçin.',
 VERIFICATION_NOT_FOUND:'Doğrulama kaydı bulunamadı veya bu oturuma ait değil. Formu kapatıp yeniden açın.',
 VERIFICATION_IN_PROGRESS:'Doğrulama sürüyor; işlem tamamlanmadan iptal edilemez.',
 'İstek alanları doğrulanamadı.':'Form alanları sunucu tarafından kabul edilmedi. Alan biçimlerini ve uzunluklarını kontrol edin.',
 SECURE_PANEL_TRANSPORT_REQUIRED:'Gizli bilgi girişi için HTTPS veya localhost gerekli.',
 SENSITIVE_METADATA_REJECTED:'Cihaz güvenli olmayan metadata döndürdü; sonuç kaydedilmedi.',
 ONBOARDING_CONNECTION_DISABLED:'Canlı onboarding sunucu yapılandırmasında kapalı. Hiçbir cihaz bağlantısı başlatılmadı.',
 ONBOARDING_OPERATOR_NOT_AUTHORIZED:'Bu oturum canlı onboarding için yetkilendirilmemiş. Varsayılan demo hesabı kullanılamaz.',
 REGISTRY_STORAGE_UNAVAILABLE:'V2 router kayıt deposu hazır değil veya erişilemiyor. İşlem belleğe düşürülmedi.',
 CONNECTION_POLICY_INVALID:'Sunucu bağlantı güvenlik politikası geçersiz.',TARGET_OR_SOURCE_NOT_ALLOWED:'Hedef IP, port veya kaynak IP sunucu izin kapsamı dışında.',
 CA_CERTIFICATE_REJECTED:'Public CA zinciri kabul edilmedi. Sertifika doğrulaması zorunlu.',TLS_VERIFICATION_FAILED:'TLS sertifika zinciri veya hedef kimliği doğrulanamadı.',
 CERTIFICATE_PIN_MISMATCH:'Sunulan sertifikanın SHA-256 pini eşleşmiyor.',CERTIFICATE_SAN_MISMATCH:'Sertifika IP SAN alanı yönetim IP’siyle eşleşmiyor.',
 SECRET_STORAGE_REJECTED:'V2 gizli bilgi deposunun dosya güvenliği doğrulanamadı.',CONNECTION_TIMEOUT:'Bağlantı zaman aşımına uğradı. Otomatik tekrar yapılmadı.',
 ROUTER_MODEL_MISMATCH:'Okunan cihaz modeli kayıtlı modelle eşleşmiyor.',
 ROUTER_IDENTITY_MISMATCH:'Okunan cihaz kimliği beklenen kimlikle eşleşmiyor.',ROUTEROS_VERSION_MISMATCH:'Okunan RouterOS sürümü beklenen sürümle eşleşmiyor.',
 ROUTEROS_VERSION_UNSUPPORTED:'Bu sürüm destek kapsamında değil. RouterOS 6.49.x veya 7.x gerekli.',API_SSL_STOP:'Bağlantı güvenli biçimde durduruldu. Otomatik tekrar yapılmadı.',
 ROUTER_ENDPOINT_EXISTS:'Bu IP ve port için zaten bir router kaydı var.',ROUTER_REVISION_CONFLICT:'Router kaydı değişmiş. Güncel detayı açıp yeniden gözden geçirin.',
 VERIFICATION_EXPIRED:'Doğrulama süresi doldu; eski sonuçla kayıt oluşturulamaz.',VERIFICATION_NOT_SUCCESSFUL:'Başarılı bir doğrulama olmadan kayıt oluşturulamaz.',
 VERIFICATION_REQUEST_CONFLICT:'Doğrulama isteği başka bir işleme ait.',CONNECTION_POLICY_CHANGED:'Kaynak IP politikası değişti. Önceki doğrulama kullanılamaz.',
 CREDENTIAL_FORMAT_REJECTED:'API kullanıcı adı veya parola biçimi geçersiz.',
};
export function connectionError(code:string):string{
 if(code.startsWith('PILOT_RUNTIME_FILE_REJECTED'))return 'Güvenli V2 pilot kimlik bilgisi veya public CA dosyası bulunamadı/izinleri uygun değil. Referansı sunucu tarafında hazırlayın; parola gönderilmedi.';
 if(code.startsWith('AUTHENTICATION_REJECTED:'))return code.includes('PERMISSION_DENIED')?'Cihaz API girişine izin vermedi. Yetkili operatör hesap durumunu ve API yetkisini kontrol etmeli.':'Cihaz hesabı veya parolayı reddetti. Disabled hesap, kaynak kısıtı ve API yetkisi de aynı sonucu verebilir; otomatik parola değişikliği yapılmaz.';
 if(code.startsWith('AUTHENTICATION_PROTOCOL_ERROR:'))return 'Cihazın login yanıtı desteklenen API protokolüyle eşleşmedi.';
 if(code.startsWith('DEVICE_READ_REJECTED:'))return 'API girişi sonrasında salt-okunur metadata sorgusu reddedildi.';
 return errors[code]??'İşlem tamamlanamadı. Güvenlik veya bağlantı ön koşullarını kontrol edin.';
}
export const registryStatus=(status:string)=>({VERIFIED:'Son kontrol başarılı',STALE:'Kontrol eskimiş',CHECK_FAILED:'Son kontrol başarısız'}[status]??'Bilinmiyor');
