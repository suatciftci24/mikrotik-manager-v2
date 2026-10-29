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
