# CEBECI_TOWERS — Aşama 25 hesap ve bağlantı hazırlığı

**NO_GO / NOT CONNECTED / APPROVAL REQUIRED.** Yerel hazırlık sözleşmesidir;
hesap oluşturma veya gerçek bağlantı onayı değildir. Başlangıç `5d1be21`.
Kullanıcı Aşama 24 için **13/13 BROWSER PASS** bildirdi; bu tarihsel yerel UI
kabulü, gerçek cihaz güvenliği/erişim yetkisi kanıtı değildir.

## Mevcut sınır ve tekrar kullanılacak altyapı

[Ana pilot sözleşmesi](CEBECI_TOWERS_PILOT.md) Aşama 21–24 geçmişini, manuel
bildirimin zamanının UNKNOWN olduğunu ve eksik teknik kanıtları korur.
RB3011UiAS / 6.49.19, IPsec 10.250.0.19/32 ↔ 10.250.0.1/32, açık V1 API 8728
ve 10.250.0.1/32 service sınırı, kapalı/sertifikasız API-SSL, write yetkili V1
panel rolü ve geniş admin/reception kısıtları **manuel bildirim** olarak kalır.
Bunlar güncel V2 hedef/source binding'i, TLS, minimum hesap veya V1 etkisizliği
kanıtı yapılmaz. V1'in çalışan hesapları/grupları/API/IPsec ve aboneleri korunur.

- Aynı ADMIN GET `/api/v1/system/cebeci-pilot` yanıtına
  `access_preparation.account_preparation` eklendi. Ek endpoint, proof upload,
  onay deposu, credential alımı, account provisioner veya transport yoktur.
- Aşama 22 `AccessPlan`, exact `ReadIntent`, beş menülü `READ_SCOPE` ve
  `dispatch_pilot_read` korunur. Dispatcher adapter'a dokunmadan 403; demo ADMIN
  grant'i cihaz izni değildir. Yeni sözleşme ikinci bir bağlantı altyapısı değildir.
- Geçmiş IP/source değerleri metadata'dır; AccessPlan reviewed pin/source null
  kalır. Otomatik poll/retry/GO, servis/hesap değişikliği veya gerçek proof toplama yok.

## Minimum pilot servis hesabı sözleşmesi

`PilotAccountContract` kapalı/frozen tiptir: yalnız CEBECI_TOWERS; **özel grupta
exact read,api aday seti**, hesap paylaşımı FORBIDDEN, credential intake NONE.
Sıralama normalize edilir; eksik/tekrarlı/ek/bilinmeyen policy reddedilir.
write, policy, sensitive, password, reboot, test, ftp, ssh, winbox, telnet, local,
web, sniff, romon, rest-api ve herhangi başka ek policy kabul edilmez.

Bu hesap **oluşturulmadı**, kullanıcı/grup adı veya credential reference bile
alınmaz. Mevcut webpanel/admin/reception hesabı kullanılmaz, yeniden
adlandırılmaz, policy'si veya kaynak sınırı değiştirilmez. read,api yeterliliği
**DOĞRULANMADI**: tam 6.49.19 lab'ında alan/menü, dosya erişimi ve yan etki
sınırları incelenmeli; dar read garantisi veya güvenli varsayılan grup sayılmaz.
Eksik alan için yetki artırmak yerine STOP gerekir. Üretimde negatif write testi yoktur.

Gelecekte dahi uygulama kabiliyeti yalnız Aşama 22 beş metadata print menüsü/alanı
olabilir. PPP secret, auth username, user/certificate/file/export/script, firewall/
NAT, IPsec SA/peer, her türlü yazma/restart ve RADIUS kapsam dışıdır. Sır/private
key/PSK/raw certificate/SA/backup alınmaz. Credential yaşam döngüsü ve iptali ayrı
kurumsal güvenli süreçte incelenir; V2 bu fazda sır depolamaz/kullanmaz.

## Sekiz durum ve yirmi bağımsız kanıt alanı

| ADMIN hazırlık durumu | Bağımsız kanıt alanları | Şu an |
| --- | --- | --- |
| Ayrı V2 pilot hesabı | ACCOUNT_SEPARATE, ACCOUNT_AUTH | NOT_READY; hesap NOT_CREATED_NOT_VERIFIED |
| Minimum yetki doğrulaması | POLICY_EXACT, ROS6_LAB | NOT_READY; ROS6_LAB_NOT_VERIFIED |
| Güvenli taşıma | TLS_CLIENT, IPSEC_AUTH, IPSEC_PATH | NOT_READY |
| Kaynak IP kısıtlaması | SOURCE_ACCOUNT, SOURCE_SERVICE, SOURCE_FIREWALL | NOT_READY |
| Kimlik ve sertifika | ROUTER_IDENTITY, TLS_CHAIN, TLS_NAME, TLS_VALIDITY, TLS_PIN | NOT_READY |
| V1 izolasyonu | V1_IMPACT | NOT_READY |
| STOP / rollback | AUDIT, STOP_OWNER, ROLLBACK | NOT_READY |
| Operatör onayı | OPERATOR_REVIEW yalnız plan incelemesi; gerçek onay ayrı | NOT_RECORDED |

Her alan kendi kaynağını, UTC/ofset zamanını, sabit reason code'unu ve gereken
kanıtı gösterir. Varsayılan yirmi alan **MISSING**, zaman UNKNOWN'dur. Hesap/
service/firewall source incelemeleri birbirini tamamlamaz. TLS zinciri, SAN/IP,
geçerlilik/iptal/public pin ve istemci uyumu ayrıdır; IPsec peer kimlik doğrulaması,
yol/selector/NAT/tünel dışına kaçmama ve V1 etkisi ayrıca değerlendirilir.
Kaynakta beklenen güncel cihazın gördüğü V2 /32 kanıtlanmalıdır; eski V1 /32 yetmez.

`PreparationClaim` yalnız sabit alan/kod, sabit CEBECI adayı, kaynak, opsiyonel
aware zaman ve politika paketi SHA-256 taşır. Gerçek değer/raw belge/credential
almaz. Bu sadece offline domain test sözleşmesi; internet veya UI intake endpoint'i
yoktur. Hash imza veya operatör kimliği/kanıt doğruluğu değildir. Paket; Aşama 22
kapalı config/policy özetini, hesap sözleşmesini, dar scope'u, alan/grup tanımını
ve sürümü bağlar. Kopyalanmış model de boundary'de yeniden doğrulanır.

- Eksik MISSING; çift kayıt CONFLICT (sonuncuyu seçme yok); farklı paket CONFLICT.
- Negatif sonuç BLOCKED, bilinmeyen sonuç UNKNOWN. Eksik/gelecek zaman UNKNOWN;
  beş dakika ve üstü STALE. Her değişiklikte ilgili rapor ayrıca yeniden incelenmeli;
  bu faz otomatik drift izleme yapmaz. Süre sadece hazırlık inceleme politikasıdır.
- MANUAL_OBSERVATION ve OFFLINE_UNVERIFIED kaynaklarının PASS iddiası dahi
  UNVERIFIED kalır. Manuel gözlem otomatik güncel teknik kanıta dönüştürülmez.
- Yalnız taze SYNTHETIC_FIXTURE PASS, SYNTHETIC_REVIEW_PASS olabilir. Bu bir lab
  simülasyonu sonucudur, gerçek doğrulama değildir. Tüm alanlar bu sonucu verse bile
  NO_GO, live_verification=false, account_creation_allowed=false,
  connection_allowed=false, execution_authority=DENIED korunur.
- OPERATOR_REVIEW simülasyonda tam olsa bile OPERATOR_APPROVAL ve
  operator_approval **NOT_RECORDED** kalır. Gerçek operatör onayı bu tipin alanı
  veya API yetkisi değildir; fazın planı hazır olması onay sayılmaz.

## Taşıma karar modeli

**A — API-SSL 8729:** aynı yirmi kanıt alanı değerlendirilir. TLS zincir/SAN/
geçerlilik/public pin/istemci kanıtı IPsec auth/yol incelemesinin yerine geçmez:
bu tek-router yönetim yolunda ikisi ayrı incelenir. Sertifikasız/kapalı servis
bildirimi engelleyicidir; kendiliğinden servis veya sertifika hazırlığı yapılmaz.
Tüm sentetik kanıtlar tam olsa bile seçenek
`NO_GO_APPROVAL_AND_LIVE_VERIFICATION_REQUIRED`, approved=false kalır.

**B — IPsec yoluyla API 8728:** TLS alanları B'nin karşılaştırma kontrol listesinde
aranmıyor olması TLS muafiyeti **DEĞİLDİR**. Ayrı IPsec auth/yol, hesap, kaynak,
kimlik, V1 ve STOP/rollback kanıtları değerlendirilir ama seçenek koşulsuz
`BLOCKED_BY_CURRENT_TLS_CONTRACT` kalır. Aşama 22 sadece API_SSL/8729 kabul eder;
API/8728 reddedilir. B yalnız gelecekte ayrı güvenlik politikası/risk kabulü ve
kapsamlı açık onay gerektiren doküman seçeneğidir; fallback/otomatik seçim yoktur.

[Resmi API](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API),
[User/policy](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User) ve
[IPsec](https://help.mikrotik.com/docs/spaces/ROS/pages/11993097/IPsec) açıklamalarının
sürüm/kanıt sınırlamaları ana pilot belgesinde korunur. Bunlar cihazın mevcut
sertifikasını, gerçek hesap etkisini veya uçtan uca yolunu doğrulamaz.

## Güvenli uygulama ve geri dönüş — sadece plan

1. **Ön koşul:** atanmış ağ/güvenlik/V1/audit/STOP sahipleri, taze kanıtlar, tam
   ROS6 lab raporu, tek cihaz ve kaynak binding'i; sır içermeyen baseline incelemesi.
   Yanlış kimlik, kaynak veya çelişkili/stale kanıt varsa ilerleme.
2. **Açık onay:** kullanıcı/operatör aday, kapsam, yöntem, süre/okuma bütçesi ve
   iptal sorumluluğunu ayrıca açıkça onaylamalı. Yeni hesap/servis/sertifika veya
   başka canlı change gerekiyorsa ayrı kapsamlı change onayı da gerekir. Bu faz
   onayı almaz/saklamaz; gerçek bağlantı yapılmadığı/doğrulanmadığı sürece NO_GO.
3. **Yedek/geri dönüş kanıtı:** yetkili sahibin kurumda koruduğu güvenli yedeğin
   kurtarılabilirlik inceleme sonucu ve yeni V2 değişikliğine özel geri dönüş
   haritası onaylanmalı. V2 backup/export/private key almaz. Toplu restore, V1
   ayarının geri alınması veya audit/abone silinmesi planlanmaz.
4. **Gelecekte tek-router sınırı:** yalnız ayrıca geliştirilecek/incelenecek dar
   execution capability ve yeni V2 hesabı; V1/grupları/paylaşılan yollar değişmez.
   Mevcut kodun dispatcher'ı 403 verir; plan okunması hiçbir okuma başlatmaz.
5. **STOP:** beklenmeyen yazma/ek alan, kimlik/source uyuşmazlığı, TLS/IPsec
   belirsizliği/kaybı, yetki aşımı, V1 etkisi veya audit/rollback eksikliği halinde
   ilk hatada yeni V2 okuyucu durur. Retry/alternatif port/yol/hesap veya yetki
   artırma olmaz; sadece redacted sonuç ve baseline korunur.
6. **İptal/geri dönüş:** atanmış yetkili operatör yalnız ayrıca onaylanmış yeni
   V2 erişimini iptal eder; bu da canlı change için ayrı yetki gerektirir. Mevcut
   V1 hesabı/API/IPsec/firewall korunur. Şüphede global geri yükleme yapılmaz;
   erişim kapalı bırakılır, yeni inceleme/onay olmadan yeniden başlanmaz.

Bu aşamada çalıştırılabilir router komutu veya otomatik uygulama script'i yoktur;
plan için komut taslağına gerek duyulmadı. Yalnız V2 yerel kod/test/build/commit
ve normal GitHub push yapılır; demo verisi veya audit yazması yapılmaz.

## Aşama 25 salt okunur tarayıcı kabulü

Yeni exclusive dal önceki aşamaların kabulünü çağırmaz. Sekiz durum/yirmi bağımsız
kanıt, kapalı onay/hesap/bağlantı bayrakları, A/B kararı, UI veri-ready, 320/390/1440px,
reload ve mevcut yönetim/abone/audit baseline eşitliği denetlenir. Hesap/fixture
oluşturmaz. Normal ofis WSL'de tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_ACCOUNT_ONLY=1 ./browser-accept-demo.sh
```

## Aşama 26 görünüm bağlantısı

[Operasyonel karar paketi](CEBECI_TOWERS_DECISION_PACKET.md) bu belgedeki sekiz
hazırlık ve yirmi alanın durumlarını aynen kaynaklarından okur, Aşama 23 matrisine
bağlar. Hesap/kanıt modeli, policy, TLS/NO_GO veya yetki sınırı değiştirilmez.
Referans özeti teknik doğrulama, operatör onayı veya yürütme yetkisi değildir.

## Aşama 28 — onaylı ayrı hesap hazırlığı ve tek operatör uygulaması

Başlangıç `7e4d872`; kullanıcı Aşama 27 için 12/12 BROWSER PASS bildirdi.
**Bu görevdeki açık onay:** yalnız CEBECI_TOWERS için ayrı V2 pilot hesabı
oluşturma ve güvenli API erişiminin hazırlığı. Gerçek V2 bağlantısı, başka router,
V1 veya mevcut hesap/servis/IPsec değişikliği bu onaydan çıkarılamaz. Önceki
bölümlerdeki genel onay gereksinimleri artık bu dar hazırlık onayının yok olduğu
anlamına gelmez; gerçek pilot yürütme yetkisi ise hâlâ verilmedi.

### Gerçek uygulama durumu ve çelişmeyen kapsam

Bu Codex oturumunda onaylı bir canlı router yönetim oturumu/credential kullanılmadı;
hiçbir cihaza ping, DNS/port keşfi, SSH/API/Winbox bağlantısı veya handshake denenmedi.
**Routerda yeni grup/hesap/sertifika oluşturulmadı; servis açılmadı.** V1, webpanel,
admin/reception, API 8728 ve IPsec ayarları değişmedi. Mevcut manuel gözlem zamanları
UNKNOWN; gerçek minimum yetki/TLS/path kanıtı elde edilmedi. Pilot NO_GO.

API-SSL 8729'un kapalı/sertifikasız olduğu önceki tek zamanlı bildirimdir. API-SSL
servisini açmak veya sertifika bağlamak **mevcut servis ayarını değiştirir**; bu
görevin “mevcut servisleri değiştirme” sınırı nedeniyle uygulanmaz. Güvenli API
hazırlığı burada yerel TLS doğrulayıcı politikası ve operatör sertifika planıdır.
API 8728'i kapatma/taşıma, V2 için otomatik kullanma veya plain API fallback yoktur.

### Yerel yazılım hazırlığı — mevcut sözleşmeler üzerinde

`PilotAccountContract` aynı exact read,api adayını korur; üç hazırlık varsayılanı eklendi:

- `provisioning_method=OPERATOR_SECURE_MANAGEMENT_SESSION`: uygulama provisioner'ı
  değil, yetkili operatörün güvenli ayrı yönetim oturumu.
- `initial_account_state=DISABLED`: güvenliği henüz kanıtlanmamış hesap ilk anda
  devre dışı oluşturulmalı; önce etkin oluşturup sonra kapatma yöntemi yoktur.
- `existing_object_action=STOP_PRESERVE_EXISTING`: isim/grup çakışmasında overwrite,
  reuse veya policy değişimi yerine STOP. Mevcut V1 nesneleri korunur.

Hesap/grup adı, parola, credential reference veya yeni bağlantı ayarı alınmaz.
Bu metadata mevcut politika paketinin hash'ine dahildir; eski paket referansı
geçersizleşir. Yeni ekran, matris, endpoint, grant/onay deposu veya browser aşaması yoktur.
`account_creation_allowed=false` uygulamanın routerda hesap oluşturamayacağını,
`operator_approval=NOT_RECORDED` gerçek **pilot yürütme** onayının bu uygulamada
kaydedilmediğini ifade eder; bu görevdeki sınırlı insan hazırlık onayını geri almaz.

`cebeci_access.prepare_offline_tls_context` yalnız ADMIN için, bellek içinde bir
Python TLS istemci doğrulayıcısı hazırlar. Default boş planla durur; ayrıca
incelenmiş hedef/source /32/public leaf pin metadata'sı ve açıkça verilen public
CA PEM gerektirir. Eski adresler otomatik atanmaz. Bu metadata'nın sağlanması da
gerçek kanıt veya execution yetkisi değildir.

- Sistem trust store'u kendiliğinden kullanılmaz. Yalnız verilen public CA'lar
  yüklenir; eksik/bozuk/private-key/leaf-only/duplicate veya aşırı büyük girdi reddedilir.
- TLS 1.2+, CERT_REQUIRED, hostname kontrolü, SAN gereksinimi (CN fallback kapalı),
  X.509 strict inceleme; TLS 1.2 için ECDHE/DHE + AEAD (AES-GCM/uygun CHACHA20),
  TLS 1.3 varsayılan AEAD ve anonymous/NULL/DSS/MD5/RC4/3DES dışlama politikası hazırlanır.
- Secret/private key/client certificate yükleme, dosya/credential okuma, keylog,
  DNS, socket, handshake, connect veya polling yapılmaz. SSLKEYLOGFILE ortamından
  keylog açılmaz. Hata mesajları PEM/secret girdisini içermez.
- Bu fonksiyon **cihaz zincirini veya pinini doğrulamış değildir**; sadece boşta
  istemci context'i üretir. 6.49.19 istemci/cipher/CA/SAN uyumu, sertifika zaman/
  kullanım/iptal incelemesi ve bağımsız public pin kanıtları hâlâ eksiktir.
- Gelecekte ayrı onaylı adapter; doğrulanmış handshake ve hedef ismi sonrasında
  public leaf SHA-256 pinini ayrıca eşleştirmeden ve kimliği doğrulamadan credential
  gönderemez. O transport/pin handshake uygulaması bu görevde eklenmedi; mevcut
  `dispatch_pilot_read` hâlâ adapter'a dokunmadan 403 verir.

### Tek güvenli operatör adımı

**Yalnız CEBECI_TOWERS'a ait, kimliği doğrulanmış güvenli yönetim oturumunda aşağıdaki
sınırlı hesap hazırlık akışını uygulayın; V2/API testi veya servis değişimi yapmayın.**
Codex'e credential veya özel anahtar göndermeyin. Bu tek operatör işi aşağıdaki
ön kontrol/uygulama/geri dönüş sınırlarının tamamını kapsar; otomatik script değildir.

1. Operatörün kendi yetkili güvenli Winbox/yerel konsol oturumunda hedefin
   CEBECI_TOWERS / RB3011UiAS / 6.49.19 olduğunu bağımsız doğrulayın. Eski IP tek
   başına hedef kanıtı değildir. Yanlış/şüpheli kimlikte hiçbir nesne oluşturmayın.
   Güvenli yönetim oturumu yoksa API 8728 üzerinden yeni parola taşıyarak devam etmeyin.
2. Yalnız bu cihazda değişiklik öncesi mevcut hesap/grup, API 8728/8729 servis
   durumu/kaynak sınırı ve yönetim IPsec politikasının **gizli olmayan** baseline'ını,
   gözlem zamanını ve geri dönüş sorumlusunu kurum içinde belirleyin. Ham export,
   PSK, SA, private key veya şifre ekran görüntüsü almayın. Mevcut korunan yedeğin
   kurtarılabilirliğini kurum içinde inceleyin; V2'ye backup dosyası vermeyin.
3. Cihazın göreceği güncel V2 yönetim kaynağının tek /32'sini ve iptal sahibini
   belirleyin. 10.250.0.1/32 V1 kaynağını otomatik kopyalamayın. Hedef/source veya
   güvenli geri dönüş belirsizse STOP; geniş/boş address ile hesap oluşturmayın.
4. Users/Groups yönetiminde **yeni**, V1 ile paylaşılmayan bir özel grup için yalnız
   read ve api policy adaylarını seçin. Örnek hazırlık etiketi `v2-cebeci-pilot-ro`;
   etiket var olan grupsa onu düzenlemeyin/kullanmayın: STOP. Varsayılan read/full
   grubunu kopyalamayın; write/policy/test/sensitive/password/reboot ve diğer bütün
   policy'ler kapalı kalmalı. read,api yeterliliği bu işlemle kanıtlanmaz.
5. Yine benzersiz **yeni** bir V2 kullanıcı nesnesini yalnız bu özel gruba ve
   incelenmiş /32 adresine bağlayın. Başlangıçta **Disabled** olmasını sağlayın;
   kullanılan 6.49.19 yönetim arayüzünde oluşturma anında Disabled desteklenmiyorsa
   etkin kullanıcı oluşturup sonra kapatmayın: STOP. Güçlü benzersiz parolayı sadece
   operatörün güvenli yönetim/parola yöneticisi sürecinde üretip girin; boş/default
   parola bırakmayın, terminal/script/history/chat/GitHub/V2'ye yazmayın. Kullanıcı
   adı çakışmasında mevcut hesabı değiştirmek yerine STOP. Bu belge parola veya
   otomatik çalıştırılabilir RouterOS komutu içermez.
6. Aynı güvenli oturumda yeni nesnenin disabled, exact read,api grubunda ve doğru
   tek /32 kapsamında olduğunu kontrol edin; mevcut V1/webpanel/gruplar/API/IPsec
   baseline'ının değişmediğini inceleyin. V2 ile login/API testi yapmayın, hesabı
   etkinleştirmeyin. ROS6 alan/dosya/yan etki lab raporu olmadan “salt okunur güvenli”
   sonucu vermeyin. Sadece gizli olmayan sonuç kodu/rol/zamanı kurumda koruyun.
7. Bu akış sertifika veya API-SSL servisi değiştirmez. Güvenlik sahibi public CA
   zinciri, tek hedef SAN/IP, server-auth kullanım/zaman/iptal/public pin ve tam
   6.49.19 TLS 1.2+ lab uyumluluğu planını kurum içinde hazırlayabilir. Private key
   router/kurumun güvenli alanından çıkarılmaz; V2'ye aktarılmaz. Servis açma,
   sertifika yükleme, firewall/IPsec düzenleme ve gerçek V2 bağlantı başlatma bu
   akışın devamı olarak yapılmaz; mevcut sınırları aşan ayrı kapsam gerekir.

Bu akış **uygulanmış sayılmaz**. Başarı durumu ancak yetkili operatörün yeni nesneye
ait gizli olmayan gözlem sonucu ile bildirilebilir; tarihi verilmezse UNKNOWN kalır.
Mevcut yerel karar sistemi bu bildirimi otomatik canlı doğrulanmış kanıta dönüştürmez.

### STOP ve yalnız yeni hazırlık nesnelerine ait geri dönüş

Erişim kaybı, yanlış kimlik/source, beklenmeyen policy/yan etki, isim çakışması veya
V1 etkisinde ilk hatada durun; başka adres/hesap/port denemeyin. Yeni hesap disabled
kalmalı; iptal gerekiyorsa yalnız operatörün **bu işlemde oluşturduğu** nesnenin
kimliğini/aidiyetini doğrulayıp kaldırması planlanır. Yalnız bu yeni gruba bağlı
kullanıcı kalmadığı kesinleşirse yine sadece yeni grup kaldırılabilir. V1 veya
başkasına ait nesneyi isim benzerliğinden kaldırmayın; wildcard/overwrite yoktur.
Erişim kaybolmuşsa yeni bağlantılarla zorlamayın; belirlenmiş kurtarma sorumlusunun
güvenli yerel erişim prosedürüne geçin, otomatik global restore/restart yapmayın.
Baseline/audit/aboneler silinmez; mevcut API 8728, webpanel ve IPsec değiştirilmez.

### Teknik kaynak ve doğrulama sınırı

[Resmi User belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User)
policy/grup/adres modelini ve default read/dosya erişimi sınırlarını;
[API belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API)
API-SSL'in sertifikasız anonymous DH seçeneğini;
[Certificates belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/2555969/Certificates)
SAN ve sertifika kullanım alanlarını açıklar. Bunlar gerçek 6.49.19 cihazın GUI,
policy veya TLS uyumluluğunu kanıtlamaz; burada belirtilen strict context/disabled
ilk durum/rollback sınırları bizim hazırlık politikamızdır. GUI'de gerekli ilk durum
uygulanamıyorsa güvenliği gevşetmeden STOP yapılır.

Hedefli sonuç: 9 yeni backend kontrolü PASS. Testler salt yerel public OS CA'sını
**açıkça verilen public fixture** olarak kullanır, gerçek cihaz sertifikası/anahtarı
veya handshake kullanmaz. Hiçbir private key/test credential üretimi yapılmadı.
Frontend değişmedi; yeni browser senaryosu/eski kabul tekrarları oluşturulmadı.
