# Merkezi Router Yönetimi ve Onboarding

Mevcut Router Merkezi içinde **DEMO / Sentetik envanter** ve **Kayıtlı cihazlar ·
API-SSL** açıkça ayrılır. Demo router/abone/audit kayıtları değiştirilmez. Operatörün
bildirdiği CEBECI_TOWERS / 6.49.19 pilot PASS sonucu dış doğrulama bilgisidir;
yeni kayıt deposuna otomatik canlı kanıt veya hazır credential olarak aktarılmaz.

## Panel akışı

1. Merkezi ADMIN, **Router ekle** ile ad, IPv4 yönetim adresi, API-SSL portu
   (8729), API hesabı/parolası, public CA ve güvenilir kanaldan edinilmiş leaf
   SHA-256 pinini girer. RouterOS sürümü boşsa algılanır; istenirse beklenen sürüm
   ve cihaz identity'si girilebilir. Özel anahtar girilmez.
2. Açık onaydan sonra **Bağlantıyı doğrula** yalnız bir TLS/API oturumu açar.
   Login ardından `/system/identity/print` (name) ve `/system/resource/print`
   (board-name, version) okunur. Kullanıcı/PPPoE/firewall/IPsec/config/script/
   scheduler/write/delete/restart işlemi yoktur.
3. Okunan kimlik, model, RouterOS sürümü, uç nokta, kaynak ve kontrol zamanı
   önizlenir. Ayrı kayıt onayı olmadan envantere router eklenmez. Başarısız
   bağlantıda kayıt oluşturulmaz, güvenli STOP nedeni gösterilir.
4. Doğrulama kanıtı beş dakika geçerli ve oturum kullanıcısına bağlıdır. Kaydet
   ikinci bağlantı açmaz. Aynı request ID ile doğrulama tekrarı mevcut sonucu
   getirir; zaman aşımı/RUNNING durumunda yeni oturum açmaz. Form değişikliği yeni
   request ID üretir; otomatik retry yoktur. Kaydet onayı da idempotent'tir.
5. Listede sunucuda sayfalama, ad/IP/identity/model/sürüm araması ve kontrol durumu
   filtresi vardır. Detayda güvenli metadata, son başarılı/son kontrol zamanı,
   hata ve audit geçmişi görülür. **Bağlantıyı düzenle** aynı doğrulama/onay
   yolunu kullanır; boş username/password/public CA mevcut materyali korur.
   Revizyon uyuşmazlığında eski ekran yeni kaydı ezemez.
6. Detaydaki açık onaylı kontrol aynı altyapıyı kullanır. Eski başarılı kontrol
   başarısız yenisinde korunur; başarısız son kontrol ayrı gösterilir. Beş
   dakikadan eski başarı STALE olur. Bunlar anlık ONLINE/OFFLINE veya sürekli
   izleme iddiası değildir. WAN/IPsec/trafik/abone ölçümleri okunmadığından
   **bilinmiyor** gösterilir.

## Bir kez yapılan V2 sunucu hazırlığı

Her router için kod, Python dosyası veya terminal komutu gerekmez. Deployment
seviyesindeki aşağıdaki hazırlık **bir kez**, yalnız izole V2 ortamı için yapılır;
bu geliştirme sırasında migration/deploy/restart veya gerçek cihaz erişimi yoktur.

- `migrations/versions/006_router_registry.sql` normal, yetkili V2 şema süreciyle
  uygulanmalıdır. Uygulama import/startup sırasında tablo oluşturmaz. Mevcut V2
  PostgreSQL engine'i kullanılır; V1 veya demo tablolarına yazılmaz. Şema/DB yoksa
  REGISTRY_STORAGE_UNAVAILABLE döner; process-memory/boş başarı fallback'i yoktur.
- `V2_ROUTER_ONBOARDING_ENABLED=false` varsayılandır. Gerçek erişim için yetkili
  işletim yapılandırmasında ayrıca `true` gerekir; UI bu flag'i değiştiremez.
- `V2_ROUTER_ONBOARDING_ALLOWED_CIDRS`: işletim tarafından incelenmiş yönetim
  ağlarının virgülle ayrılmış listesi; varsayılan boş/ret. `0.0.0.0/0`, loopback,
  link-local, multicast, unspecified/reserved adresler reddedilir. DNS adı,
  URL veya metadata-service adresine bağlantı yoktur.
- `V2_ROUTER_ONBOARDING_SOURCE_IP`: bu V2 ortamının atanmış IPv4 yönetim kaynağı;
  varsayılan boş/ret. Soket bu IP'ye bind edilir; doğrulanmış TLS peer/local
  adresleri ayrıca kontrol edilir. Ağ rotası/IPsec/V1 ayarı değiştirilmez.
- `V2_ROUTER_ONBOARDING_ALLOWED_PORTS`: incelenmiş API-SSL portları; varsayılan
  `8729`. API 8728 ve ayrı plaintext fallback'i her koşulda yasaktır.
- `V2_ROUTER_ONBOARDING_OPERATOR_IDS`: gerçek erişim için ayrıca yetkilendirilmiş
  mevcut V2 ADMIN kullanıcı ID'leri. Liste/detay okumaları da bu allowlist ile sınırlıdır. Varsayılan boş/ret. Bilinen bootstrap
  `demo-user`, allowlist'e yazılsa da reddedilir. Merkezi auth her istekte güncel
  kullanıcı durumunu/yetkisini okur; VIEWER ve sınırlı ADMIN erişemez.
- Credential girişi HTTPS panel veya yerel loopback üzerinden olmalıdır; UI ve
  backend bunu ayrı kontrol eder. HTTPS reverse proxy trust ayarı yalnız işletim
  tarafından doğrulanmış proxy'lere sınırlandırılmalıdır. Prod kimlik sağlayıcı/
  TLS/servis yapılandırması bu yerel geliştirmeyle kurulmuş sayılmaz.

## Güvenlik ve saklama

- Pilotun katı public-CA verifier'ı ve bounded RouterOS wire/login/reply kodu
  ortak kullanılır. CERT_REQUIRED, TLS 1.2+, strict X509 chain, IP SAN, CN fallback
  kapalı ve leaf DER SHA-256 pin zorunludur. Sistem CA deposuna/anonymous TLS'e/
  verify=False'a dönüş yoktur. Pin değişikliği yeniden açık doğrulama gerektirir.
- Protokol/mimari hedefi 6.49.x ve 7.x'tir. Gerçek diğer cihaz/sürüm uyumluluğu
  burada ölçülmedi; testler sentetiktir. Mevcut CEBECI tek-router CLI scope/gate'i
  genişletilmedi ve pilot dosyaları okunmaz/değiştirilmez.
- Bağlantı/IO timeout iki saniye, ortak oturum bütçesi on saniyedir. Tek socket,
  iki salt-okunur sorgu ve her çıkışta close vardır. Cihaz response/credential
  hataları sabit güvenli kodlara çevrilir. Router'ın parola yansıtan metadata'sı
  kayda alınmaz. Salt-okunurluk yalnız cihazın read/api grubuna dayanmaz.
- Parola/username yalnız `.local/router-registry/secrets/<random UUID>` içinde
  owner-only dosyada (0600; dizinler 0700) saklanır. Git-ignored bu namespace
  CEBECI pilot/V1 secret alanlarıyla paylaşılmaz. Symlink, hardlink, başka owner,
  geniş izin ve path traversal reddedilir. Bu OS izinli dosya saklamadır; dosya
  içeriği uygulama seviyesinde şifrelenmiş değildir. Sunucu disk/yedek şifreleme
  ve işletim hesabı izolasyonu deployment sorumluluğudur.
- PostgreSQL yalnız opaque credential referansı, public CA/pin ve güvenli
  metadata tutar. API/validation/audit yanıtlarında credential/ref/path yoktur.
  Parola React belleğinde form süresiyle sınırlıdır; URL/localStorage/sessionStorage
  veya kayıt onayı gövdesine yazılmaz. Gerçek credential request-body logging
  reverse proxy/APM tarafında da kapalı tutulmalıdır.
- Probe request/success/failure ve kayıt/değişiklik audit'i korunur. Envanter
  yazması ve audit aynı transaction'dadır. Başarısız probe'un geçici secret'ı ve
  kapatılarak iptal edilen önizlemenin secret'ı kaldırılır. Düzenleme sonrası eski
  ref yalnız yeni kayıt commit edildikten sonra kaldırılır. Çökme/terk edilen
  önizlemelerde artık private dosya kalabilir; expired kanıtla kayıt yapılamaz.
  Bu dosyalar shared alanlarda otomatik taranmaz/silinmez; bakım ve yedekleme
  politikası yalnız V2 namespace'ini kapsamalıdır.

## Hedefli doğrulama

Backend: yeni registry transaction/yetki, vault ve mocked TLS/API testleri.
Etkilenen pilot TLS helper ve iki-sorgu CLI kontrolü ayrıca hedeflenmiştir.
Frontend: `frontend/tests/routerRegistry.test.mjs`, TypeScript + Vite build.

Yalnız sentetik API yanıtlarıyla, gerçek DB/backend/cihaz kullanmadan 320/390/1440px
panel etkileşim kabulü için tek WSL komutu:

```bash
npm --prefix frontend run build && node frontend/tests/routerOnboarding.browser.mjs
```

Mevcut yerel Playwright/Chromium kullanılır; indirip kurmaz. Browser yok/sandbox
engelliyse exit 2/BLOCKED döner. Bu mocked UI sonucu gerçek HTTP/PostgreSQL veya
canlı MikroTik kabulü değildir. Bu ortamda Chromium başlatma BLOCKED oldu; tekrar
edilmedi. Bilinen PostgreSQL/ASGI engelleri tekrar araştırılmadı. Migration ve
canlı onboarding çalıştırılmadığından bu entegrasyonlar **BLOCKED / doğrulanmadı**.

## Bağlantısız form hazırlığı ve bağlantı profilleri

Sihirbaz zorunlu alanları ve isteğe bağlı kimlik/sürüm alanlarını açıklar.
İlk kayıtta public CA, kullanıcı adı ve parola zorunludur; düzenlemede boş alanlar
kayıtlı materyali korur. Public CA dosyası yükleme ve PEM yapıştırma aynı alanı
besler. Public sertifika zinciri PEM biçiminde olabilir; özel anahtar ve DER
kabul edilmez. Yerel kontrol yalnız PEM metin biçimini inceler, X509 geçerliliği
ve CA güveni iddiası üretmez.

**Formu bağlantısız kontrol et** cihaz, DB veya doğrulama endpoint'ine istek
atmaz. **Sentetik örneği önizle** ayrı sentetik verilerle aynı kontrolleri gösterir;
canlı formu doldurmaz. Önizleme açıkça SENTETİK / CİHAZA BAĞLANILMADI gösterir,
credential/CA değerlerini içermez ve kayıt için gereken verification ID üretmez.
Kapalı bağlantı politikası veya yetkisiz operatör gerçek doğrulamaya geçemez.
Önizleme gerçek cihaz doğrulaması, envanter kaydı veya TLS kabulü değildir.

`routerConnectionProfiles.ts` yeniden kullanılabilir, salt okunur ve sürümlenebilir
profil kataloğunun temelidir. Otomatik/6.49.x/7.x şablonları ortak API-SSL 8729
varsayılanını ve değiştirilemez chain/IP SAN/leaf pin/read-only koşullarını taşır.
Sürüm ailesi açıklamadır; tam beklenen sürüm ayrı alanla belirtilebilir.
Profil seçimi TLS politikasını veya sunucu allowlist'ini değiştirmez. Profilde
adres, credential, public CA veya cihaz pini saklanmaz; bunlar her hedefe özeldir.
Paylaşımlı credential deposu, profil DB migration'ı veya pilot dosyası importu
oluşturulmadı. Mevcut backend'in pilotla ortak katı TLS doğrulayıcısı korunur.

Hedefli test: `node frontend/tests/routerOnboardingPreview.test.mjs`.

## İzole yerel PostgreSQL hazırlığı ve kabulü

Normal ev WSL terminalinde repo kökünden `./accept-router-postgres.sh` kullanılır.
Komut önce loopback iznini ve V2 hedefini kontrol eder; yalnız repo sahibi PG16
kümesini `dev-db.sh` ile hazırlar. Canlı onboarding flag'i açılmaz, router erişimi
veya credential değişikliği yapılmaz.

`app.local_router_registry --apply` yalnız loopback:55432 / mikrotik_manager_v2 /
v2_local ve repo altındaki data_directory ile, mevcut sentetik V2 marker'ı ve
izinleri doğrulandıktan sonra 006 SQL migration'ını transaction içinde uygular.
Üç tablonun hiçbiri yoksa oluşturulur. Üçü de varsa sütun/tip/null/primary key,
indeks, endpoint unique ve güvenli port CHECK doğrulanır. Kısmi veya farklı şema
otomatik düzeltilmez; transaction geri alınır. Demo abone/event/request digest'i
değişmemelidir. Başlangıçta veya normal HTTP isteğinde migration yoktur.

Ardından `V2_RUN_REGISTRY_PG_TESTS=1` ile 14 hedefli gerçek PostgreSQL transaction
testi çalışır. Her test ayrı `v2_registry_test_<UUID>` şemasında aynı SQL migration'ı
kullanır; yalnız kendi test şemasını temizler. Ekleme, yeniden okuma, düzenleme,
detay, arama/filtre/sayfalama, duplicate/revision, idempotency, audit/rollback ve
kapalı policy kontrolleri yapılır. Public registry ve demo kayıtlarına test verisi
eklenmez. Testlerde cihaz/TLS yanıtları sentetiktir; ağ adaptörü çağrılmaz ve
bunlar canlı cihaz/TLS kabulü sayılmaz. Gerçek API'de silme endpoint'i yoktur;
bu kabul yeni bir silme yetkisi veya güvenlik atlatma modu eklemez.

Soket engelinde komut ilk kontrolde durur; başarılı PostgreSQL kabulü raporlanmaz.

## Kalıcı sentetik router yönetimi ve public sertifika profilleri

Router Merkezi tasarımı korunur. **Sentetik router ekle**, **Kalıcı sentetik
routerlar** alanına gider: ad, örnek IPv4 adresi, model ve isteğe bağlı konum
ile kayıt eklenir; arama, detay, revizyon kontrollü düzenleme ve açık onaylı
silme sağlanır. Parola/sertifika istenmez. Yalnız RFC5737 örnek ağları
192.0.2.0/24, 198.51.100.0/24 ve 203.0.113.0/24 kabul edilir. Durum her zaman
“Ölçülmedi · Sentetik”tir; cihaz bağlantısı veya ONLINE sonucu üretilmez.

Bu kayıtlar ayrı `v2_router_workspace.records` tablosunda DEMO_ROUTER türündedir.
Eski sentetik envanter/grant/abone kayıtlarına veya public gerçek cihaz registry'sine
eklenmez. Silme yalnız bu çalışma alanındaki sentetik kaydı etkiler; audit aynı
transaction'da kalır. API `/api/v1/router-workspace/routers` altındadır; merkezi
ADMIN ve mutasyonlarda `X-V2-Demo-Action: router-workspace` gerekir. Rol/izin
kontrolleri mevcut merkezi kimlik doğrulamasına bağlıdır. Kaynak/credential
belirsizliğinde canlı endpoint'e veya belleğe fallback yapılmaz.

Gerçek cihazlar ayrı **Kayıtlı cihazlar · API-SSL** alanındadır. Gerçek bağlantı
kapalıysa sihirbaz yalnız form kontrolü/sentetik önizleme sunar; cihaz erişim
onayı göstermez. Public sertifika profili kaydetmek ayrı bir yerel DB işlemidir.
Bu, gerçek router kaydı veya başarılı bağlantı anlamına gelmez.

Sihirbazda **Sertifika profilleri** public CA zinciri ve SHA-256 pinini hedef
IPv4/port ile birlikte tekrar kullanır. Profil kaydında mevcut katı public-CA
parser'ı kullanılır; özel anahtar/credential kabul edilmez. Profil seçimi farklı
bir dolu hedef IP'yi sessizce değiştirmez. Profil yalnız eşleşen hedef IP'ye
uygulanır ve portunu da doldurur; gerçek bağlantıda TLS chain/IP SAN/leaf pin
kontrollerinin tamamı yeniden uygulanır. Kullanıcı adı/parola profil payload'ına,
audit'e veya tarayıcı depolamasına yazılmaz. Pilot dosyaları paylaşılmaz.
Profiller aynı ayrı şemada TRUST_PROFILE türündedir; sentetik listeye katılmaz.

Açık yerel hazırlık **007 migration** gerektirir. `./accept-router-postgres.sh`
artık 006 ve 007'yi repo sahibi V2 kümesinde doğrular/uygular; ardından gerçek
PostgreSQL registry ve workspace testlerini ayrı UUID şemalarında çalıştırır.
Eski demo ve public registry baseline'ları kontrol edilir, business tablolarına
örnek router eklenmez. Normal başlangıç migration çalıştırmaz. Yalnız 007 için:
`PYTHONPATH=backend .venv/bin/python -m app.local_router_workspace --apply`.
Sandbox loopback engelinde gerçek migration/PG kabulü tamamlanmış sayılmaz.

## Sentetik liste 404 / eski çalışan API

Sentetik CRUD sözleşmesi `/api/v1/router-workspace/routers` altındadır. Vite,
`V2_API_PORT` ile aynı loopback backend'e proxy yapar. Eski bir API sürecinin
`/api/ready` yanıtı tek başına güncel route'ların varlığını kanıtlamaz.

Hazır kontrolü artık import sırasında sabitlenen backend kaynak hash'i, checkout
kimliği, API portu ve workspace sözleşme sürümünü doğrular. Eski/farklı checkout
veya yanlış porttaki API hazır kabul edilmez; UI proxy kontrolü de aynı sözleşmeyi
ister. Kaynağı güncellemek, hâlihazırda import edilmiş eski Python sürecini
değiştirmez. API root'undan gelen ham 404, UI'da modülün çalışan backend'de
bulunmadığını açıklayan mesajla gösterilir; gerçekten silinmiş kayıtların özel
404 açıklaması korunur.

Normal ev WSL'de tek yenileme/başlatma komutu:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_API_PORT=18000 V2_UI_PORT=15173 ./dev.sh --refresh-owned
```

Bu açık seçenek önce loopback iznini, iki portun dinleyen socket sahibini, aynı
UID'yi, tam proje cwd/argv/port eşleşmesini ve process başlangıç kimliğini doğrular.
İki süreç de doğrulanmadan sinyal göndermez. Yalnız bu projenin bilinen
Uvicorn/Vite süreçlerine sabit pidfd üzerinden SIGTERM yollar; SIGKILL kullanmaz.
Başka süreç/checkout, wildcard listener, belirsiz sahip veya eksik pidfd desteğinde
durur. Yeniden başlatma normal dev.sh yaşam döngüsünü kullanır; DB/migration/veri
ve diğer servisleri değiştirmez. Normal dev.sh mevcut güncel süreci yeniden
kullanır; örtülü restart yapmaz. Yenileme yeni oturum açılmasını gerektirebilir.
