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

## Aşama 29 — kapalı API-SSL adaptörü

Başlangıç `bf5efb9`. Ayrı hesabın/grubun ve source /32 kısıtının operatör tarafından
hazırlandığı, hesabın Disabled olduğu ve API-SSL'in kapalı/sertifikasız olduğu bu
görevde kullanıcı tarafından bildirildi. Bu bir handshake veya minimum yetki
kanıtı değildir. Gerçek credential değeri bu belgeye, Git'e veya demo kayıtlarına
aktarılmaz. **Hesap etkinleştirilmedi, servis açılmadı, sertifika yüklenmedi.**

### Mimariye bağlantı ve kapalı yetki

`backend/app/adapters/cebeci_api_ssl.py` mevcut `PilotReadAdapter.read_metadata`
imzasını uygular. `ReadIntent`, dar beş menülü `READ_SCOPE`, metadata sanitizer
ve Aşama 28 `prepare_offline_tls_context` yeniden kullanılır. Yeni sayfa/matris,
credential deposu veya bağlantı endpoint'i yoktur. Sentetik gateway bu adaptörü
provider olarak kaydetmez; tüm mevcut demo kaynakları aynı kalır.

İki bağımsız kapı vardır: default `enabled=false` ve backend
`authorize(...purpose='DEVICE_READ')`. **Mevcut backend gate'i CEBECI için hâlâ 403
verir; environment enable isteği tek başına bağlantı açamaz.** Mevcut dispatcher
da aynı kapalı sınırı korur. ADMIN plan GET'i yalnız saf `adapter_status` okur;
config/credential okumaz, adaptör instantiate etmez ve socket açmaz. Ekranda
NOT CONNECTED / NOT READY / NO_GO gösterilir; yeni test/connect/enable butonu yoktur.

### V2'ye özel yapılandırma

`.env.example` yalnız boş secret alanları ve kapalı örnek değerleri içerir. Modül
.env/V1 dosyası veya veritabanı okumaz; yalnız süreç ortamındaki aşağıdaki isimleri
kullanır. Gerçek secret değerlerini örnek dosyaya yazmayın; gelecekte yetkili ayrı
V2 servisinin korunan runtime secret/env enjeksiyonundan sağlayın. Bu görevde servis
kurulumu/deploy veya env secret girişi yapılmadı.

| Değişken | Sınır |
| --- | --- |
| V2_CEBECI_API_SSL_ENABLED | Default false; sadece true/false, gerçek yürütme yetkisi vermez |
| V2_CEBECI_API_SSL_HOST | Yalnız 10.250.0.19; DNS adı/başka router yok |
| V2_CEBECI_API_SSL_SOURCE_IP | Yalnız 10.250.0.1; bind edilen kaynak; V1 config'inden okunmaz |
| V2_CEBECI_API_SSL_PORT | Yalnız 8729; 8728 fallback yok |
| V2_CEBECI_API_SSL_CA_PEM | Explicit public CA PEM; private key/client cert/default OS trust yok |
| V2_CEBECI_API_SSL_LEAF_SHA256 | Ayrı incelenmiş public leaf DER SHA-256; 64 küçük hex |
| V2_CEBECI_API_SSL_USERNAME / PASSWORD | Dedicated V2 runtime credential; boş default; auth objesi/demo/API/log'a yazılmaz |
| V2_CEBECI_API_SSL_CONNECT_TIMEOUT | Default 2 saniye; 0.1–5 |
| V2_CEBECI_API_SSL_IO_TIMEOUT | Default 2 saniye; 0.1–5 |
| V2_CEBECI_API_SSL_TOTAL_TIMEOUT | Default 10 saniye; 1–30, auth ve bütün okumalar için ortak üst bütçe |

Kullanıcının doğruladığı hedef/source değerleri yalnız yeni, tek-router transport
config pinleridir; eski kanıtların zamanı veya doğrulanmışlık durumu değiştirilmez.
V2 runtime credential'ı V1/webpanel/admin/reception'dan otomatik alınamaz. Username
V2 namespace'inde olmalı; özel V2 hesabının gerçek değerini operatör runtime'da
sağlar. Bu isim kuralı hesap/grup güvenlik kanıtı değildir. Salt okunurluk aşağıdaki
uygulama sınırıyla ayrıca korunur; read/api grubuna güvenilmez.

### Doğrulama ve protokol sırası

1. Backend yetkisi, enabled flag ve immutable/revalidated tek-router config;
   sonra `ReadIntent` exact menü/print/property kontrolü. Yetkisiz, kapalı veya
   mutasyon isteğinde TLS, socket veya secret çözümü başlamaz.
2. Explicit CA ile TLS 1.2+, CERT_REQUIRED, hostname/SAN, strict X509 ve Aşama 28
   AEAD cipher politikası hazırlanır. Doğrulamasız/anonymous TLS seçeneği yoktur;
   context zayıfsa TCP açılmadan reddedilir.
3. Yalnız IPv4 socket, fixed source bind ve fixed hedef/8729; DNS keşfi, proxy,
   port/cihaz tarama veya alternatif adres yoktur. Connect ve handshake için bounded
   timeout; bütün oturum için monotonic total deadline uygulanır.
4. TLS handshake'in zincir/hedef doğrulaması başarılı olmadan devam edilmez.
   Gerçek peer/source socket adresi, TLS sürümü, binary leaf sertifika SHA-256 pini
   (constant-time karşılaştırma) ve exact IP SAN ayrıca kontrol edilir. Pin zincir
   doğrulamasının yerine geçmez. TLS/pin/SAN/source hata verirse credential okunmaz.
5. Ancak bundan sonra dedicated V2 username/password runtime'dan alınır ve TLS
   içinde post-6.43 `/login` protokolü kullanılır. Challenge/fallback auth yoktur;
   beklenmeyen yanıt sabit AUTHENTICATION_REJECTED/STOP kodudur. Credential değerleri
   instance/config üzerinde saklanmaz veya loglanmaz.
6. İlk okuma sadece `/system/identity/print` ile name'dir; yanlış identity'de
   resource veya kullanıcı isteğine dahi geçilmez. Sonra board-name ve version
   okunur. Exact RB3011UiAS ve numeric 6.49.19 beklenir; yalnız aynı numeric build'in
   `6.49.19 (stable)` seri gösterimi de kabul edilir. Diğer suffix/build/model,
   çoklu/eksik row veya çelişki STOP'tur; belirsiz alias normalize edilmez.
7. Yalnız doğrulanmış kimlik sonrasında kullanıcının dar metadata print isteği
   çalışır. Dönen alanlar .proplist'e rağmen tekrar denetlenir; ek/tekrarlı/eksik
   alan, sensitive marker veya control-character değeri reddedilir. Ham hata/yanıt
   dışarı çıkmaz. Boş normal session listesi mümkündür; buradan router OFFLINE,
   güvenli yetki veya abonelik kaynağı sonucu çıkarılmaz.
8. Başarıda da hatada da oturum kapanır. Ağ/TLS/timeout/protokol/scope hatası instance
   STOP latch'i oluşturur; aynı instance sonraki okumayı başlatamaz. Eşzamanlı ikinci
   isteğe izin verilmez. Otomatik retry/reconnect/polling/background task yoktur.

Protocol budget: en fazla 4096 bayt/word, 32 word/sentence, 256 reply sentence,
128 row/query ve auth dahil 262144 toplam response baytı; total süreye ek olarak
her IO kalan bütçeyle sınırlandırılır. Malformed/reserved frame veya limit aşımı
fail-closed STOP'tur. Kaynak hata exception'ları, trap mesajları, auth paketi,
sertifika veya credential değerleri log/API hata metni olarak kullanılmaz; sadece
sabit hata kodları verilir. Field allowlist/marker kontrolü, olası tüm hassas
semantik veriyi keşfeden genel bir DLP sistemi değildir.

### Salt okunurluk ve V1 izolasyonu

Dışarı açılan tek yetenek `read_metadata(ReadIntent)` olup yazma/execute metodu yoktur.
İzinli beş menu/print alanı eski Aşama 22 scope'udur. User/scheduler/script/firewall/
NAT/config/PPPoE secret/IPsec SA/RADIUS ve add/set/remove/enable/disable/run/export/
listen/getall/wildcard istekleri reddedilir. `/login` sadece iç auth akışıdır; genel
komut gönderme kabiliyeti olarak sunulmaz. Credential sahibi yanlışlıkla geniş yetkili
olsa bile bu uygulama herhangi bir mutation komutu oluşturamaz; yine de minimum
hesap/ROS6 lab kanıtı gerçek pilot ön koşulu olarak kalır.

V1 aynı VDS üzerinde çalışacak olsa da ayrı V2 env, servis ve veritabanı sınırları
korunur. V1 runtime/config/credential/DB bağlantısı aranmaz veya devralınmaz.
V1 API 8728 ve IPsec ayarı değiştirilmez; V1'i kapatma/migration/deploy/restart bu
adaptörün işi değildir. Yeni endpoint veya automatic sync sayesinde demo verisiyle
karışma yoktur; gerçek provider hâlâ kayıtlı değildir.

### Test ve gerçek doğrulama sınırı

15 yeni hedefli backend testi tüm socket/TLS transport'unu fake/Mock ile değiştirir;
gerçek dinleyici, handshake, router, VDS veya private key kullanmaz. Lokalize test
authorization mock'u sadece gelecekte ayrıca yetkili bir çağrının wire yolunu sınar;
production auth gate'i değiştirilmemiştir. Zincir/SAN doğrulama hatası, zayıf context,
pin/source/peer/identity/model/version farkı, mutation/extra-secret alanları,
framing/row/byte limitleri, timeout/deadline ve STOP/cleanup/no-fallback denetlenir.
Son sensitive-value ve build-format değişikliklerinde yalnız ilgili testler yeniden
çalıştırıldı. Üç yeni frontend kontrolü, gerçek offline domain profilinde environment
enable isteğine rağmen closed/not-ready statüsünü ve credential çıkmadığını doğrular.
TypeScript/Vite build PASS; eski geniş kabul paketleri çalıştırılmadı.

**Gerçek zincir/sertifika/pin/ROS6 field veya bağlantı uyumluluğu bu görevde
DOĞRULANMADI.** Hesap Disabled, API-SSL kapalı/sertifikasız kullanıcı bildirimi
çözülmüş sayılmaz; cert validity/revocation ve policy lab kanıtları eksik kalır.
Pilotu çalıştıran HTTP route veya onay/hesap etkinleştirme/servis/sertifika işlemi yoktur.
Mevcut karar matrisi NO_GO ve gerçek bağlantı kapalıdır.

Teknik uygulama referansları:
[RouterOS API framing/login/proplist](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API),
[Python SSL client chain/hostname doğrulaması](https://docs.python.org/3.12/library/ssl.html).
Bunlar gerçek cihazın mevcut sertifikası/yetki davranışı kanıtı değildir.

## Aşama 30 — canlı hazırlık onayı ve uygulanmamış operatör işi

Başlangıç `b917d78`. Kullanıcı yalnız CEBECI_TOWERS üzerinde API-SSL sertifika
kurulumu, 8729'un doğrulanmış 10.250.0.1/32 kaynağına kısıtlı açılması ve mevcut
ayrı V2 hesabının uygunluğu doğrulanarak etkinleştirilmesini onayladı. Bu dar onay,
Aşama 28–29'un bu üç hazırlık değişikliğine ilişkin önceki sınırını günceller;
**V2 gerçek bağlantısı, API login/polling/veri toplama henüz onaylı değildir.**
V1/webpanel/API8728/IPsec veya başka router/üretim servisi değişikliği kapsam dışıdır.

### Gerçek uygulama sonucu: BLOCKED / UYGULANMADI

Bu oturumda CEBECI_TOWERS için doğrulanmış güvenli yönetim oturumu/credential
sağlanmadı. Kullanılabilir araçlarda router yönetim oturumu yok; repo transport'u
ise salt okunur ve mevcut DEVICE_READ yetkisi kapalıdır. Bu durum bir router
bağlantı testi sonucu değildir: router/VDS/V1'e bağlanma, ping/port keşfi veya V2
adapter çağrısı denenmedi. V1 credential/SSH anahtarı aranmadı veya kullanılmadı.

| Başlık | Son kullanıcı bildirimi | Bu görevde uygulama/doğrulama |
| --- | --- | --- |
| Kimlik/sürüm | CEBECI_TOWERS / RB3011UiAS / 6.49.19 | Canlı doğrulanmadı |
| Sertifika | Cihazda sertifika yok | Oluşturulmadı/yüklenmedi; güncel durum doğrulanmadı |
| API-SSL 8729 | Kapalı | Açılmadı/bağlanmadı; güncel durum doğrulanmadı |
| Ayrı V2 hesabı | Disabled; read/api aday grubu, 10.250.0.1/32 | Policy/source sorgulanmadı, etkinleştirilmedi |
| V1/webpanel/API8728/IPsec | Çalışan mevcut erişim | Müdahale edilmedi; kesintisiz çalışması uzaktan doğrulanamadı |
| V2 gerçek bağlantısı | Onaysız / NO_GO | Başlatılmadı, env-enable veya execution gate değiştirilmedi |

Canlı başarı iddiası veya yeni gözlem zamanı üretilmedi. Kod uyumluluk düzeltmesi
saptanmadığından kod/env/ekran/matris değiştirilmedi; yeni veya eski test/build/
browser aşaması çalıştırılmadı. Yalnız belge ve ilerleme kaydı güncellendi.

### Tek güvenli operatör işlemi

**Yetkili operatör, yalnız CEBECI_TOWERS'ın kimliği doğrulanmış güvenli yönetim
konsolunda aşağıdaki API-SSL hazırlık işini tek kontrollü işlem olarak uygulasın;
V2 uygulamasını veya gerçek V2 API istemcisini başlatmasın.** Credential, parola,
PSK veya private key Codex'e, Git'e ya da VDS servis dosyasına aktarılmasın.

1. Değişiklikten önce hedef identity/model/6.49.19'u doğrula. Mevcut güvenli yönetim
   ve V1 oturumunun çalıştığını, API 8728/webpanel/IPsec durumunu ve 8729/ayrı V2
   hesabının önceki ayarlarını gizli olmayan baseline olarak kaydet. Kurtarma
   sorumlusu ve güvenli yerel erişim yolu hazır değilse STOP; global backup export,
   V1 ayar geri yüklemesi veya restart yapma.
2. **Hiçbir şeyi değiştirmeden** mevcut `v2-cebeci-ro` hesabının yalnız
   `v2-cebeci-pilot-ro` özel grubunda, grubun exact read,api aday setinde ve hesabın
   address alanının exact 10.250.0.1/32 olduğunu doğrula. Ek/eksik policy, geniş/boş
   source veya belirsizlikte STOP; grubu, başka hesabı veya parolayı düzeltmeye
   çalışma. read,api davranışı ayrıca lab kanıtı olmadan güvenli kabul edilmez.
3. Cihaza özel yeni sunucu private key'i **cihazın güvenli anahtar alanında** tutan,
   daha önce incelenmiş 6.49.19 uyumlu PKI yöntemini kullan. Gerekirse yalnız public
   CSR/certificate/CA verisiyle imzalama sürecini tamamla; private key'i dışarı
   aktaran yöntemi kullanma. Hedef IP SAN **10.250.0.19**, uygun server-auth kullanım,
   geçerli zaman aralığı, CA basicConstraints/keyCertSign ve eksiksiz incelenmiş
   zincir gerekir. SHA-256 ve uygun güçlü anahtar/TLS istemci uyumu önceden
   incelenmeli; desteklenmeyen GUI/PKI/extension durumunda tahmin ederek ilerleme.
   Yalnız bu iş için yeni isimli sertifika nesneleri kullanılmalı; isim çakışmasında
   mevcut sertifika/servise dokunmadan STOP. Sadece public leaf/CA üzerinden offline
   zincir ve IP SAN incelemesini ve leaf DER SHA-256 pinini doğrula; CN veya pin tek
   başına zincir/SAN yerine geçmez. Public fingerprint sır değildir; private key/
   parola/PKCS12/raw sensitive export veya secret hash alınmaz.
4. Sertifika/anahtar eşleşmesi ve public inceleme başarılıysa **yalnız api-ssl**
   servisinde sertifikayı bağla, portu 8729 ve address listesini exact
   10.250.0.1/32 yap. Gerçek 6.49.19 oturumunda desteklendiği doğrulanmış TLS 1.2
   kısıtını kullan; anonymous/certificate=none veya eski protokol/verification bypass
   ile açma. Gerekli uyumluluk doğrulanamıyorsa STOP. **api (8728)** servisine,
   firewall/IPsec veya V1/webpanel ayarlarına dokunma. Service address sınırı network
   firewall drop değildir; mevcut yol/kural incelemesi gerekli güvenceyi vermiyorsa
   bu görev adına firewall kuralı eklemek yerine STOP. Sertifikasız aralık bırakmadan
   api-ssl'i ancak bu kısıtlar yerinde olduğunda etkinleştir.
5. Grup/source ön kontrolü hâlâ uygunsa yalnız mevcut `v2-cebeci-ro` hesabını
   etkinleştir. Başka hesabı/grubu/parolayı değiştirme. Güvenli yönetim konsolundan
   sertifika bağlamasını, 8729/source/TLS ve hesabın enabled/policy/source durumunu
   yeniden oku; mevcut V1/webpanel/API8728/IPsec baseline'ının değişmediğini ve
   mevcut V1 oturumunun kesilmediğini kontrol et. V2 ile API login veya metadata
   okuma yapma; V2 env-enable/grant verme, polling başlatma. Sadece gizli olmayan
   önce/sonra sonuçları, public sertifika/pin inceleme sonucu, gerçek UTC/ofset zaman
   ve sorumlu rolünü kaydet. Bunlar V2 uçtan uca bağlantı başarısı sayılmaz.

Bu akış **burada çalıştırılmadı** ve sertifika/API-SSL/hesap başarısı olarak raporlanamaz.
Yeni gerçek V2 bağlantısı için ayrıca açık kullanıcı onayı gerekir; uygulama NO_GO kalır.

### STOP ve sınırlı geri dönüş

Yanlış kimlik/build, uygun olmayan read/api/source, güvenilmez zincir/SAN/pin/TLS,
erişim kaybı veya herhangi bir V1 etkisinde ilk hatada dur; alternatif router/hesap/
port deneme, policy artırma veya V1 restart yapma. Kullanıcının geri dönüş sınırı
yalnız **bu aşamada oluşturulan yeni nesnelerdir**. Mevcut V1 kullanıcısı, API8728,
IPsec politikası veya firewall silinemez/geri alınamaz. Önceden var olan API-SSL
servisi veya V2 hesabı için kapsam dışı otomatik geri dönüş varsayma; böyle bir
müdahale gerekecekse sorumlu operatör kapsamı netleştirmeden sonraki adıma geçmesin.

Yeni sertifika nesnesi ancak bu aşamada oluşturulduğu ve **hiçbir etkin servis
veya başka sertifika tarafından kullanılmadığı** kesinleşirse kaldırılabilir.
Etkin 8729'a bağlı sertifikayı silerek certificate=none/anonymous TLS durumu
oluşturma. Güvenli geri dönüş yalnız yeni nesne sınırında sağlanamıyorsa STOP ve
kurtarma sorumlusuna eskalasyon; toplu restore, mevcut servis/grup/hesap temizliği
veya otomatik yeniden deneme yoktur. Audit/baseline/aboneler korunur.

Teknik dayanaklar: [Services](https://help.mikrotik.com/docs/spaces/ROS/pages/103841820/Services)
address/certificate/tls-version servis özelliklerini ve address kısıtının firewall
olmadığını; [Certificates](https://help.mikrotik.com/docs/spaces/ROS/pages/2555969/Certificates)
SAN/kullanım alanlarını; [API](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API)
sertifikasız API-SSL'in anonymous DH davranışını açıklar. Güncel belgelerdeki bütün
özellikler 6.49.19 için kanıt sayılmaz; operatör build'deki uyumu doğrulayamıyorsa
STOP. Bu referanslar canlı uygulama sonucunun yerine geçmez.

## Aşama 31 — bildirilen public pinin yerel pilot yapılandırmasına bağlanması

Görev referansı `b917d78`; mevcut branch HEAD'i `9a2f624` olduğundan Aşama 30 belge
commit'i korunarak bu HEAD üzerinden devam edildi. Kullanıcı Aşama 30'un tamamlandığını,
sertifika doğrulamasının OK olduğunu, 8729/source kısıtını ve V1'in çalıştığını
bildirdi. Bu, operatörün harici doğrulama bildirimidir; Codex tarafından canlı
handshake/hesap/grup testi yapıldığı veya yeni gözlem tarihi oluştuğu anlamına gelmez.
Önceki Aşama 30 BLOCKED kaydı o oturumun tarihsel sonucu olarak korunur.

Kullanıcının verdiği **public leaf DER SHA-256**:

```text
896addde343bf45b429aa354605ee1930d91c30c024c71fe182b94243937acb6
```

Bu değer credential değildir. Mevcut adapter'da `REVIEWED_LEAF_SHA256` olarak ve
kapalı `.env.example` profilinde yapılandırıldı. Runtime environment loader'ı pin
verilmezse bu değeri kullanır; açıkça boş, farklı, uppercase/bozuk veya yeni bir pin
verilirse CONFIGURATION_REJECTED ile durur. Sertifika rotasyonu ayrı inceleme ve
bu bildirilen pin bağının güncellenmesini gerektirir; otomatik öğrenme/TOFU yoktur.
Düşük seviyeli config nesnesinin sentetik testlerdeki kontrollü pin enjeksiyonu
production environment loader'ını veya kapalı authorization gate'ini değiştirmez.

**CA yerine pin kullanılmaz.** Ortamda public CA PEM/CRT dosyası bulunmadı; ayrıca
bu oturuma aktarılmış `V2_CEBECI_API_SSL_CA_PEM`, USERNAME veya PASSWORD runtime
değişkenleri yok. Yalnız var/yok kontrol edildi; credential içeriği aranmadı/yazılmadı.
Fingerprint'ten CA/leaf sertifikası geri üretilemez. Başka CA ile sahte trust dosyası
oluşturulmadı; gerçek public trust yüklemesi burada tamamlandı diye raporlanamaz.

Public CA PEM gelecekte yalnız V2'nin korunan runtime ortamında mevcut CA_PEM
alanına sağlanmalı. Aşama 28'in explicit CA, TLS 1.2+, CERT_REQUIRED, strict X509,
SAN ve AEAD koşulları ile Aşama 29'un verified TLS sonrası exact IP SAN ve
constant-time leaf DER pin kontrolü korunur. Aktif yapılandırma tek CEBECI_TOWERS /
10.250.0.19:8729 / source 10.250.0.1 ile sınırlıdır. Timeout, deadline, STOP latch,
no retry ve exact beş print menüsü/alanı değişmedi. read/api grubu güvenli kabul
edilmedi; mutasyon/script/scheduler/firewall/secret/RADIUS işlemleri engelli kalır.

6 yeni hedefli yerel kontrol PASS: bildirilen pin/default kapalı scope ve timeout;
yanlış/boş pin reddi; CA olmadan aktivasyon reddi ve production auth 403; mocked
chain/SAN/pin hatasında auth öncesi durma; write/scope ve timeout STOP; başka hedef/
source/8728 reddi. Yalnız mevcut sentetik test yardımcıları kullanıldı; eski test
paketi çalıştırılmadı. Mocked TLS sertifikaları gerçek sertifika değildir; bu sonuç
bildirilen leaf'in DER/chain doğrulamasını kanıtlamaz. Frontend değişmedi; build/
browser/regresyon tekrarı yapılmadı. V1/VDS/router/abone/RADIUS erişimi, deploy,
restart/polling veya demo/audit yazması yok.

### Gerçek bağlantı için kalan engeller

1. Bu yerel çalışma ortamında **doğru public CA PEM** yok. Public trust root/zinciri
   ve gerekirse public leaf ile mevcut strict profile uygun offline inceleme gerekir;
   özel anahtar/parola/PSK gönderilmez veya Git'e yazılmaz.
2. Dedicated V2 runtime username/password korunan süreç ortamından sağlanmalı;
   mevcut V1 credential'ı okunmaz/devralınmaz. Burada değer girilmedi.
3. Gerçek pilot bağlantısı için **ayrı açık kullanıcı onayı/yürütme yetkisi** yok.
   DEVICE_READ backend gate'i hâlâ 403, adaptör default disabled ve canlı provider
   kaydı yoktur. Environment enable isteği tek başına bu kapıları açmaz. Bu görev
   bunları değiştirmez; gelecekte ayrıca incelenecek dar yürütme entegrasyonu gerekir.
4. Gerçek hedef/source bind, canlı peer zinciri/SAN/pin, 6.49.19 TLS/cipher ve minimal
   policy davranışı bu oturumda denenmedi. Bunların doğrulanması onaylı gelecekteki
   kontrollü pilot kapsamında olmalı; kullanıcı Aşama 30 bildiriminden otomatik
   canlı doğrulama/GO üretilmez.

**Yerel pin/koruma hazırlığı tamamlandı; gerçek bağlantı kapalı, pilot NO_GO.**
