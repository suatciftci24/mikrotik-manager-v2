# CEBECI_TOWERS gerçek pilot hazırlığı — 2026-11-16

Yerel geliştirme PASS; canlı bağlantı/geçiş kabulü yapılmadı.
Başlangıç: main-guncel / 4e168b9, temiz çalışma ağacı.

İnceleme: V1 backend/mikrotik_client.py ve router_poller.py yalnız kaynak
okumasıyla incelendi. V1 .19 hedefini kendi hesap/env bağlantısıyla okur;
WAN için default route gateway-status → interface → address eşlemesi kullanır,
poller DB/alarmlara yazar. Bu hesap, bağlantı ve yan etkiler V2'ye taşınmadı.
V1 dosyaları import edilmedi/kopyalanmadı; sır veya üretim verisi okunmadı.
V2 mevcut RouterRegistry.read_details, RouterApiSslClient.read_snapshot,
RegistryReadWire ve ReadOnlySnapshot zinciri genişletildi. Yeni servis,
provider, DB, migration, bağlantı endpoint'i veya başlangıç işi oluşturulmadı.

Tek hedef: 10.250.0.19:8729, source 10.250.0.1, CEBECI_TOWERS,
RB3011UiAS / 6.49.19 ve v2-cebeci-ro. Mevcut ADMIN/operator/CSRF,
explicit confirmation, kayıt revizyonu, ayrı secret vault ve TLS chain/SAN/pin
kontrolleri korunur. Diğer router, demo, sentetik workspace ve V1 aktarımı
bu gerçek detail okumasına yönlendirilmedi. Tüm varsayılan kapılar korunur.

Kaynaklar: identity/resource, interface, route, ip/address, ppp/secret,
ppp/active, hotspot/user, hotspot/active. Login dışında yalnız sabit print ve
proplist; hesap adı/parola/profil veya abone yönetim kaynağı toplanmaz.
CPU/bellek/uptime ve UTC snapshot zamanı korunur. PPPoE/Hotspot hesap ve
aktif oturum sayıları ayrı sunulur; service=any hesaplarında PPPoE toplamı
bilinmiyor kalır. WAN yalnız tek etkin default rota, gateway-status ile eşleşen
çalışan interface ve tek etkin IPv4 adresinde belirlenir. ECMP, eksik ilişki
ve çoklu adres bilinmiyor; internet erişimi veya trafik hızı iddia edilmez.
Eski snapshot'larda yeni oturum alanları null olur, sıfır üretilmez.

Sınırlar: tek TLS oturumu, ortak 10 sn deadline (son detail read sonrası dahil),
128 satır/menu, 256 sentence ve 256 KiB bütçe; taşma/bozuk yanıt/izin reddinde
bütün okuma başarısızdır, kısmi başarı yoktur. Büyük envanter pilotta STOP
üretebilir; retry/polling yok. Son başarılı snapshot başarısız okumada korunur;
UI bunu kaydedilmiş okuma olarak gösterir. Gerçek veriyle uyumluluk henüz
kanıtlanmadı; sentetik test canlı cihaz kabulü değildir.

Doğrulama: 45 benzersiz hedefli backend testi PASS (3 yeni telemetri,
7 transport, registry ve pilot secret regresyonları); test düzenlemesinden
sonra yalnız 3 yeni test tekrar PASS. Soketler mock, DB yalnız test fixture'ı;
mevcut veritabanına erişim yok. Frontend TypeScript/Vite build PASS;
git diff --check PASS. Gerçek tarayıcı veya canlı TLS oturumu çalıştırılmadı.

Sonraki ayrı onay kapsamı: operatörün V2'ye özel mevcut güven materyali ve salt
okunur hesap yetkisini doğrulaması; mevcut güvenli bağlantı ekranından yalnız
CEBECI için açık onayla bir okuma; kimlik, zaman, durum, WAN ve oturum sayılarının
cihazla karşılaştırılması. Bu paket bağlantı veya V1'den ayrılma başlatmaz.
V1'den ayrılma ayrıca planlanıp onaylanmalıdır; okuma pilotu yönetim sahipliğini
ve LOCAL/RADIUS yetkisini değiştirmez. Geri dönüş: okuma kapısını kapalı tutmak;
router/V1/DB restore veya servis restartı gerekmez.

V1, canlı MikroTik yapılandırması, VDS servisleri, mevcut DB ve RADIUS'a
bağlantı/değişiklik yapılmadı. GitHub DNS erişimi yok; push sonucu görev
sonunda ayrıca raporlanır. Önceki BLOCKED/ROLLBACK kayıtları çözülmüş sayılmaz.


## EV WSL canlı devreye alma — 2026-11-16 — BLOCKED

Kullanıcı bu görevde yalnız CEBECI salt okunur pilotu için V2.6 dağıtım,
servis işlemleri ve hata halinde geri dönüş yetkisini açıkça verdi.
Başlangıç main-guncel / 7f5f511, çalışma ağacı temiz. Önceki yerel hedefli
PASS testleri tekrar çalıştırılmadı. V1 bağlantısını kesme yetkisi yoktur.

Ön koşul sonuçları:
- Mevcut SSH alias mikmanager, mikadmin@185.139.5.51; BatchMode ve strict
  known-host kontrolüyle tek bağlantı denendi. Sonuç exit 255:
  `socket: Operation not permitted`. SSH oturumu kurulmadı.
- HTTPS `/api/ready` yanıtı alındı: service mikrotik-manager-v2,
  environment v26-acceptance, runtime_profile v26-isolated-acceptance,
  database_checked=false, api_port=18996. Bu yanıt DB/gerçek pilot
  sağlığını veya 7f5f511 sürümünün canlıda olduğunu kanıtlamaz.
- GitHub başlangıç HEAD kontrolü DNS hatasıyla başarısız oldu.
- VDS erişilemediği için güncel yedek varlığı/bütünlüğü, restore yolu,
  çalışan unit/kod/env/DB envanteri, private V2 TLS/credential dosyaları,
  CEBECI source route ve operator/gate kapsamı doğrulanamadı.

Dağıtım, yedek oluşturma, migration, servis değişimi/restart, canlı cihaz
okuması veya panelde gerçek veri kabulü yapılmadı. Hiçbir değişiklik
uygulanmadığından rollback gerekmedi ve çalıştırılmadı. V1/MikroTik
konfigürasyonu/aboneler/RADIUS/diğer routerlar ve mevcut V2.6 verileri
üzerinde işlem yapılmadı. Canlı durum, WAN, PPPoE/Hotspot hesap ve oturum
sayıları bilinmiyor; örnek veri gerçek veri olarak gösterilmedi.

Tek gereken sonraki eylem: VDS SSH erişimi sağlayan bir yürütme ortamında
bu onaylı görevi sürdürmek. Yeni dağıtım öncesi önce mevcut VDS sürümü,
sağlık, doğrulanmış yedek ve geri dönüş yolu kontrol edilmeli; ardından
mevcut kayıtlı CEBECI güvenli okuma akışıyla tek snapshot alınıp aynı UTC
snapshot'ın panel alanlarıyla eşleşmesi doğrulanmalı. Güvenlik/izolasyon
kapıları gevşetilmeyecek; V1 bağlantısı korunacak.

## V2.6 içinde açık yetkili CEBECI okuma kapısı — 2026-11-16 — yerel PASS

Bu bölüm güncel yerel geliştirme sonucudur. Başlangıç 82ef534/main-guncel,
çalışma ağacı temiz. Kullanıcının son talimatı yalnız yerel geliştirme/test/build/
commit/push'tır; önceki dağıtım onayı bu görevde kullanılmadı. SSH denenmedi.

Kullanıcının bildirdiği VDS kanıtları: mikrotik-v26-api.service,
mikrotik-v26-web.service, postgresql@16-v26.service active/running;
çalışma dizini /srv/mikrotik-v26-next, profil v26-isolated-acceptance,
API 18996; tek --run-once sonucu PASS CEBECI_TOWERS 6.49.19 (stable);
pg_dump yedeği alındı, pg_restore -l geçti. Bunlar kullanıcı doğrulamasıdır;
bu oturumda canlıya bağlanılıp yeniden doğrulanmadı. --run-once sonucu tam
WAN/PPPoE/Hotspot/panel kabulü değildir. Eski BLOCKED/ROLLBACK kayıtları silinmez.

### Uygulanan sınır

Yeni v26_cebeci capability'si mevcut kabul profilinin içinde çalışır.
V2_DEPLOYMENT_PROFILE, V2_DATABASE_URL, API host/port, ortam, şema marker'ı,
kullanıcı/oturum/veri deposu seçimi ve runtime ROOT kontrolü değişmez.
V2_ROUTER_ONBOARDING_ENABLED=false, V2_CEBECI_API_SSL_ENABLED=false ve
V2_ROUTER_ONBOARDING_OPERATOR_IDS boş kalır. Yeni kapı varsayılan kapalıdır:

- V2_V26_CEBECI_READ_ENABLED: varsayılan false.
- V2_V26_CEBECI_OPERATOR_ID: varsayılan boş; açıkça seçilmiş tek kanonik
  v2-user-UUID. Eski VDS_OPERATOR_ID'den değer devralınmaz.
- V2_V26_CEBECI_OPERATOR_REVISION: varsayılan boş; seçilen hesabın güncel
  negatif olmayan revision değeri. Kapı kapalıyken ID/revision da boş olmalıdır.

Açık konfigürasyon tek başına kimlik kanıtı değildir: mevcut /auth/me zinciri
her istekte DB'den kullanıcıyı yeniden okur. LOCAL, bootstrap_closed, active,
ADMIN, can_manage_users, tam ID ve revision eşleşmesi zorunludur. Demo,
yetkisiz hesap, eski ID, yanlış veya değişmiş revision 403 olur. Aynı ID eski
VDS kimliğiyle tesadüfen eşleşse bile açık seçim ve gerçek yerel hesap/rol/
revision kanıtı olmadan yetki doğmaz. Oturum veya kullanıcı oluşturulmaz,
parola/reset/import işlemi yapılmaz.

ConnectionPolicy kabul profilinde yalnız bu ayrı kapıyı kullanır; hedef/source/
port sabittir: 10.250.0.19/32, 10.250.0.1, 8729. Transport ayrıca identity/model/
version, v2-cebeci-ro ve incelenmiş SHA256 pin'i sabit doğrular. Mevcut CA zinciri,
IP SAN, TLS >=1.2, peer/source, private secret dosyaları ve bounded wire korunur.
API generic verify/check ve inventory ekleme yolu bu profil için kapalıdır.
Kayıtlı cihaz listesi yalnız CEBECI pilot kayıtlarını içerir; başka kayıt veya
proof ile detail/read/register/cancel kapsamı aşılamaz. Diğer kaynaklar ve
aboneler bu kapıya bağlanmaz. Her registry çağrısından önce mevcut V2.6 DB
kimliği/şema marker'ı doğrulanır; tablo oluşturma veya migration yoktur.

Mevcut iki aşamalı pilot verify → manuel register ve ayrı manuel read-only
akışı kullanılır. İlk probe yalnız identity/resource; tam snapshot ayrı onaylı
read-only isteğidir. Mevcut request UUID replay/CAS/audit/transaction davranışı
korunur. Audit ön kaydı başarısızsa transport çağrılmaz. Son başarılı snapshot
okuma hatasında korunur; otomatik retry/polling veya cihaz yazımı yoktur.
UI ayrıca seçenek kimliğinin revision'ını authenticated pilot kimliğiyle
karşılaştırır; backend yetkisi esastır. Kapı açılışı bağlantı başlatmaz.

### Yerel doğrulama

- 61 hedefli backend testi PASS: yeni capability/oturum/registry kapsamı,
  mevcut telemetri, RouterOS TLS transport, registry, private pilot secret
  ve pin regresyonları. Yeni capability modülünün ilk 10 testi PASS;
  ortak sınırdaki son değişikliklerle ilgili paket bir kez çalıştırıldı.
- Sentetik SQLite transaction/vault ve mock socket kullanıldı; capability
  transaction testinde PG guard mock'tur. Gerçek PostgreSQL/migration sonucu
  iddia edilmez; mevcut profile/marker guard testleri de pakette PASS.
- Frontend TypeScript/Vite build PASS; cebeciPilot ve pilotOperator test
  dosyaları PASS. Stale revision kontrolü eklenince yalnız ilgili UI dosyası
  tekrar PASS. İki backend test assertion kapsamı netleştirilince yalnız bu
  iki test tekrar PASS. Yerel diff kontrolü PASS.
- Gerçek cihaz/TLS/SSH/HTTP/browser/DB/VDS dağıtım veya servis işlemi yoktur.

### Tek güvenli dağıtım planı — bu görevde uygulanmadı

1. VDS'de mevcut üç servisin gerçek ExecStart/WorkingDirectory/EnvironmentFile
   ve çalışan backend/frontend hash'lerini salt okunur kaydet. /srv/mikrotik-v26-next
   ile validate_runtime'ın doğruladığı gerçek kök ilişkisini teyit et. Kodda
   kabul ROOT'u hâlâ /tmp/mikrotik-v26-acceptance'dır; servis başka bir factory
   kullanıyor olabilir. Mevcut fabrika/symlink/gerçek yol eşleşmeden STOP;
   ROOT kontrolünü atlatma veya yolu varsayımla değiştirme. Yalnız bu commit'in
   farklarını mevcut VDS sürümüyle karşılaştır; VDS driftini ezme.
2. Güncel yalnız V2.6 pg_dump yedeğinin dosya bütünlüğünü ve pg_restore -l
   sonucunu, eski backend/frontend/env/unit ve private V2 materyal yedeklerini
   erişimi sınırlı konumda doğrula. Yedekleri/sırları Git'e koyma. Mevcut DB,
   kullanıcılar, abone sayıları/revizyonları ve şema marker'ını baseline kaydet.
   Bağlı DB mevcut v26 hedefi olarak kalmalı. v2_registered_routers,
   v2_router_verifications ve v2_router_registry_audit tabloları ile gereken
   mevcut haklar/indeksler yoksa STOP; bu plan migration içermez.
3. Mevcut gerçek V2.6 yönetici oturumunda /api/v1/auth/me üzerinden ELIGIBLE
   LOCAL/active/ADMIN/can_manage_users ve candidate ID/revision'ı doğrula.
   Eski VDS sabit ID'sini kopyalama. Dedicated kapıyı false ve yeni ID/revision'ı
   boş tutarak kod+derlenmiş frontend'i aşamalı hazırla; .env/.local/venv/veri/
   kullanıcıları paketle değiştirme. Gerekli private pilot dosyaları mevcut
   uygulamanın PILOT_RUNTIME_ROOT altında trust/ca.pem, secrets/username,
   secrets/password'dür; sahip/izin/symlink/hardlink kontrollerini koru.
   Username v2-cebeci-ro, CA/SAN/pin ve 10.250.0.1 source route hazır değilse STOP.
4. Ayrı yeni dağıtım onayı alındığında yalnız mevcut V2.6 kod/frontend'ini
   yayınla; gereken yalnız mikrotik-v26-api.service ve gerekiyorsa web unit
   işlemini yap. PostgreSQL/V1/V2.5/router/RADIUS/IPsec servislerine dokunma.
   Önce kapalı yeni konfigürasyonda HTTPS/API/auth/veri baseline eşitliğini
   doğrula. Sonra yalnız üç yeni değişkende true + doğrulanmış ID/revision
   seçimini uygula ve gerekli API restartından sonra aynı sağlık kapısını
   kontrol et. Genel eski iki erişim bayrağı false, eski operator listesi boş
   kalır; DB URL/kimliği ve mevcut kullanıcılar aynıdır.
5. Yetkili HTTPS panelinde Kayıtlı cihazlar → CEBECI pilot akışını aç.
   /router-registry/options tek hedef/source/8729, operator_authorized=true
   göstermeli. Yeni cihazda manuel identity/resource probe ve ayrı kayıt
   onayını tamamla; mevcut doğrulanmış CEBECI kaydı varsa yeniden ekleme,
   onun salt okunur aksiyonunu kullan. Manuel read-only onayıyla yalnız bir
   tam snapshot al. Durum/CPU/bellek/uptime/WAN ve PPPoE/Hotspot hesap+aktif
   sayıları için aynı captured_at ve aynı snapshot'ı /router-center/{id}
   yanıtı ile panelde karşılaştır; dinamik ikinci okuma ile yanlış karşılaştırma
   yapma. Sonuç SAVED, read_only=true, is_demo=false ve ilgili audit görülmeli.
   service=any veya belirsiz WAN'da unknown başarılı ölçüm gibi sunulmamalı.
   Abone/kullanıcı baseline'ı değişmemeli; yalnız registry/audit/snapshot
   yazımları beklenir. V1 bağlantısını kesme; cihaz üzerinde değişiklik yapma.
6. Herhangi bir kapı/sağlık/veri/panel kontrolü başarısızsa yeni kapıyı false,
   yeni ID/revision'ı boş yap; önceki doğrulanmış backend/frontend/env ve
   gerekiyorsa V2.6 unit sürümünü geri yükle, yalnız ilgili V2.6 unit'i yeniden
   başlatıp önceki HTTPS/API/auth/veri baseline'ını doğrula. DB dump'ını otomatik
   restore etme, yeni kullanıcı/abone verisini ezme veya registry/audit kayıtlarını
   silme. Şema değişmediği için kod/env geri dönüşü DB restore gerektirmez.
   Belirsiz isteği yeni UUID ile otomatik tekrarlama; mevcut proof/audit'i incele.

## 79b8484 runtime/root ve dağıtım bağımlılık incelemesi — 2026-11-16

### Kanıtlanan kök neden ve çağrı zinciri

79b8484 öncesi/sonrası kaynak zinciri:

- app.main:app doğrudan girişinde runtime/root guard yoktu. /api/ready,
  DB'ye ve root'a dokunmadan yanıt verebiliyordu; hazır yanıtı runtime kabulü değildi.
- app.pilot_panel:create_app → validate_runtime(ROOT) gerçek __file__ kökünü
  kullanıyordu. /srv/mikrotik-v26-next fiziksel ağaçsa varsayılan /tmp köküyle
  uyuşmaz ve doğru biçimde V26_ACCEPTANCE_ROOT_REJECTED verirdi.
- PostgresDemoStore → validate_runtime(v26_acceptance.ROOT),
  validate_scope → validate(values, v26_acceptance.ROOT), capability
  operator_allowed/policy ve fotoğraf deposu → validate(root=ROOT) çağrıları
  beklenen sabiti doğrulayıcıya geri veriyordu. Bu, gerçek import edilen kod
  ağacının nerede olduğunu kanıtlamıyordu. Çalışan API ile factory yolu bu
  nedenle farklı sonuç verebiliyordu. Önceki testler bu ölçüm eksikliğini
  sentetik beklenen ROOT üzerinden örtük taşıyordu.

Dolayısıyla sorun salt yanlış environment bayrağı değildir. ROOT'u /srv ile
körlemesine değiştirmek fotoğraf/ilk yönetici gibi mevcut /tmp veri/bakım
sınırlarını taşır; root kontrolünü kaldırmak veya sabiti geri vermeye devam
etmek gerçek kod ağacını doğrulamaz. Bu iki yaklaşım kullanılmadı.

### Yerel kalıcı düzeltme

ROOT=/tmp/mikrotik-v26-acceptance veri/bakım sabiti korundu. Ayrı ve sabit kod
konumu sözleşmesi eklendi:

- V2_V26_RUNTIME_LAYOUT verilmezse veya acceptance ise yalnız fiziksel
  /tmp/mikrotik-v26-acceptance kod ağacı kabul edilir.
- Yalnız açık V2_V26_RUNTIME_LAYOUT=vds-next seçimi fiziksel
  /srv/mikrotik-v26-next kod ağacını kabul eder.
- Başka değer/yol, göreli yol ve başka fiziksel ağaca çözülen alias reddedilir.
  Serbest root environment override'ı, otomatik keşif veya fallback yoktur.
- validate_current() root'u kendi __file__ yolundan ölçer. app.main ilk
  satırlarda routes/engine kurulmadan önce bunu çağırır. Store, scope,
  capability ve fotoğraf doğrulaması da artık bu ölçümü kullanır.
  pilot_panel zaten gerçek kök geçirir; aynı iki sabit layout sözleşmesine uyar.
- Profil/host/API 18996, DB rol/ad/55433, şema marker'ı, eski genel iki false
  bayrak, boş eski operator allowlist, yeni explicit ADMIN ID/revision,
  TLS/pin/source/tek router/manual consent/audit kontrolleri değişmedi.
- Fotoğrafların mevcut /tmp yolu ve bakıma ait ilk yönetici sınırı taşınmadı.
  vds-next layout ilk-yönetici oluşturma aracına /srv yetkisi vermez.
  .local secret/vault kökü mevcut fiziksel VDS kod ağacına göre kalır;
  tmp/V1/V2.5'ten otomatik sır veya veri kopyalanmaz.

V2.6 adaptörünün gerçek engine URL'sinde query host/socket override'ı da
bağlantı öncesinde reddedilir; yalnız environment URL kontrolüne dayanılmaz.

Sentetik workspace testleri gerçek /srv kurulumu değildir: path ölçümü bu
fixture'larda artık açıkça mock'lanır. Disposable PG fixture ve import-only
teşhisi de kaynak ağacından import ettiklerini açıkça belirtir. Ürün kodunda
bir test bayrağıyla root/DB güvenliğini atlayan yol eklenmedi. Yeni bağımsız
root regresyonu, gerçek workspace importunun DB/network öncesinde reddini
ayrı süreçte kanıtlar.

### Dağıtım bağımlılıkları ve tek karar

Yeni app.v26_cebeci_preflight --inspect yalnız READ ONLY / REPEATABLE READ
transaction içinde mevcut DB kimliği/marker, ORM'nin gerçekten çözdüğü üç
registry tablosunun namespace/sütun/type/PK/index/endpoint unique kuralı ve
SELECT/INSERT/UPDATE haklarını kontrol eder. Aynı snapshot'ta mevcut kapalı
bootstrap ve açık seçilmiş gerçek LOCAL ADMIN ID/revision/scope doğrulanır.
Yalnız bundan sonra private V2 dosyaları ve public CA parse edilir; RouterOS
soketi/login/probe, schema yaratma, migration, kullanıcı yazma ve servis işlemi
yoktur. Transaction her sonuçta rollback edilir. Hata çıktısı sır/SQL/DSN
sızdırmaz. PASS burada yalnız preflight'tır; canlı cihaz/panel/deploy kabulü değildir.

Bu oturumda VDS erişilmedi. Kullanıcının bildirdiği servis active/run-once PASS/
pg_dump listesi aşağıdakilerin kanıtı değildir:

1. Mevcut üç registry tablosunun uyumlu şema/indeks/haklarla varlığı.
   Migration 006 bunların tarihsel tanımıdır; kabul kullanıcısı/abone kurulumu
   bunları tek başına garanti etmez. Eksik oldukları varsayılmaz; mevcut
   kanıtlarla varlıkları da doğrulanmış sayılamaz. Eksikte ayrı migration
   değerlendirmesi gerekir; bu görevde migration yetkisi yoktur.
2. Gerçek V2.6 yöneticisinin doğrulanmış ID/revision/scope seçimi.
   Eski VDS sabit ID'sinden bu bilgi üretilemez veya grant devralınamaz.
3. İlgili API unit'in gerçek factory/env dosyası, sürüm drift'i, kod/config/dist
   geri dönüş yedeği ve yeni layout seçiminin o unit'e uygulanma biçimi.
   pg_restore -l DB dump okunabilirliğidir; uygulama/env rollback kanıtı değildir.

Bu bağımlılıklar kapatılmadan tek satır git pull/restart, eski V2/V2.5 deploy
aracı veya frontend-only update.py kullanmak uygulanabilir dağıtım çözümü
olmaz. Eski araçların sabit hedefleri farklıdır ve backend/env güncellemesini
karşılamaz. Runtime düzeltmesi gerekli olsa da bunların yerine geçmez.

SON KARAR: yerel düzeltme/test/build PASS; tek komutla canlı dağıtım BLOCKED.
Gerçek neden SSH kısıtı değil, onaylı gerçek ADMIN seçimi ve registry/unit/
rollback bağımlılıklarının kanıtlanmamış olmasıdır. Önceki altı adımlı planın
root/factory belirsizliği bu bölümdeki explicit layout çözümüyle güncellendi;
VDS'de dependency preflight PASS olmadan uygulama adımına geçilmez.

### Doğrulama ve sınırlar

İki hedefli backend paketi: 28 ve 24 test çalıştırıldı (import edilen aynı
fixture'dan 3 tekrar dahil; toplam 49 benzersiz test). İlkinde tek eski
V2.5 fixture'ında schema string'i yerine MagicMock verilmesi, ikincisinde
context manager fixture'ında Mock kullanımı görüldü. Ürün kontrolleri korunup
fixture'lar explicit schema/MagicMock ile düzeltildi; yalnız bu iki başarısız
test yeniden PASS. Diğer PASS testler tekrarlanmadı. Son engine-query override reddi eklendiğinde
yalnız ilgili root/storage testi yeniden PASS oldu.
Soketsiz --import-only uygulama grafiği PASS: socket/DB/process başlatma yasak.
Frontend TypeScript/Vite build ve diff kontrolü PASS. Gerçek PostgreSQL,
VDS/SSH/router/RADIUS/IPsec/deploy/restart/migration işlemi yapılmadı.

## 209fd6d sonrası tek salt okunur VDS ön kontrolü — 2026-11-16

Kullanıcı VDS'nin 79b8484'te olduğunu, information_schema sonucunun boş
olduğunu, root env dosyasının mikadmin tarafından okunamadığını ve gerçek
ADMIN ID/revision'ın henüz doğrulanmadığını bildirdi. Bunlar salt okunur
standalone araçla ayrı ayrı denetlenir; information_schema görünürlüğü tablo
varlığının kesin kanıtı değildir. Kaynak/model incelemesi tamamlandı.

Araç: deploy/v26-cebeci/readonly-preflight.py. VDS'ye kurulmaz, mevcut app
modüllerini import etmez ve 209fd6d'nin canlıya geçmiş olmasını gerektirmez.
Komut pinli GitHub commit'inden aracı HTTPS ile belleğe alıp yayımlanan SHA256
ile doğrular; root + etkileşimli VDS terminalinde çalıştırır. İndirme/hash hatası
uygulama/env okumasından önce BLOCKED verir. sudo yalnız okunamayan root env,
/proc service metadata ve mevcut private yedekleri okumak içindir. Env dosyası
source/eval edilmez, izinleri değiştirilmez ve içeriği ekrana çıkarılmaz.

Beklenen DB: 127.0.0.1:55433 / mikrotik_v26_acceptance / v26_acceptance.
Beklenen tablolar: v2_registered_routers, v2_router_verifications,
v2_router_registry_audit. ORM şema belirtmez; aynı public veya v26_acceptance
şemasında, mevcut search_path'in gerçekten çözdüğü tek tablo kümesi gerekir.
CONNECT, USAGE ve her tabloda SELECT/INSERT/UPDATE zorunludur. CREATE/ALTER/
DELETE, rol yükseltme, migration veya yeni şema beklenmez. SQLAlchemy model
sütun/type/nullability/PK/index ve endpoint UNIQUE tanımı araçta kaynakla
pinlidir; yerel test bu kontratın modelle birebir eşitliğini doğrular.
pg_catalog varlığı, to_regclass çözümü ve gerçek rol hakları ayrı kontrol
edilir: TABLE_ABSENT / TABLE_SHADOWED_OR_NOT_RESOLVABLE / PRIVILEGES_REQUIRED
ayrımı yapılır. Üç tablonun her biri raporlanır; bağımsız kontroller devam eder.

Gerçek kimlik yolu: kullanıcı zaten giriş yaptığı V2.6 panelinin v2_session
çerezini yalnız aracın gizli TTY istemine girer. Çerez komut satırı/env/dosya/
rapora girmez ve paylaşılmaz. Araç yalnız 127.0.0.1:18996 üzerinde GET
/api/v1/auth/me kullanır; login/logout POST, yeni oturum veya demo fallback yok.
LOCAL/active/ADMIN/can_manage_users/bootstrap_closed ve pilot candidate
ID/revision doğrulanır; aynı kimlik ayrı READ ONLY/REPEATABLE READ DB snapshot'ında
yeniden eşleşmelidir. Rapora yalnız doğrulanmış ID/revision adayı çıkar;
herhangi bir grant veya kalıcı operator seçimi oluşturulmaz. Kapı zaten açıksa
seçili ID/revision bu gerçek oturumla aynı olmalıdır; kapalıysa stale grant
bulunmamalıdır. Eski sabit VDS ID'si devralınmaz.

Diğer kontroller: üç sabit unit active/running ve NeedDaemonReload=no;
gerçek process cwd/env/interpreter ile env dosyası eşleşmesi; çalışan API
repo/build hash'lerinin fiziksel backend ağacıyla eşitliği; DB sağlık; doğrulanmış
HTTPS üzerinden aynı API identity ve frontend index/ilk JS-CSS hash eşitliği;
private pilot/vault owner/izinleri, CA parse, sabit pin/host/source/port;
yalnız kernel metadata'sından local source IP ve route. RouterOS socket/login
ve uzaktaki SAN/pin tekrar testi yoktur. Yeni runtime layout seçimi vds-next
olarak raporlanır; hiçbir environment veya unit ayarı uygulanmaz.

Yedek kapsamı: araç mevcut pg_dump, backend/app + frontend/dist + dependency
manifest tar arşivi ve env/API-web unit/drop-in/EnvironmentFile geri dönüş
kopyalarının tam yollarını TTY'de ister. Yeni yedek yaratmak salt okunur işlem
olmadığından bu komut oluşturmaz. Dump yalnız pg_restore --list ile doğru DB
ve kullanıcı/abone veri TOC'si bakımından denetlenir; restore testi değildir.
Kod/dist arşivi extract edilmeden akışla, config dosyaları da yalnız hash/byte
eşitliğiyle güncel baseline'a karşı doğrulanır. Eksik/farklı/geniş izinli yedek
BLOCKED; otomatik chmod, veri restore veya silme yoktur. Kod/env içeriği hiçbir
çıktıya yazılmaz. Büyük arşivler/dump metadata okumasıyla sınırlanır; dump'ın
tamamı RAM'e yüklenmez. DB kontrolü her sonuçta rollback eder.

PASS yalnız tüm bu ön koşullar için geçerlidir; dağıtım/cihaz/panel etkileşimi
veya restore kabulü değildir. Her eksik/uyuşmazlık ayrı BLOCKED kodu ve overall
BLOCKED üretir. Veri/sırların veya başka servislerin aranmasıyla fallback yok.

Yerel doğrulama: 13 benzersiz sentetik hedefli test PASS; son private owner-read/
vault parent kontrolü sonrası yalnız ilgili 3 test tekrar PASS. Kaynak syntax
ve diff kontrolü PASS. Uygulama/frontend değişmediği için frontend build ve
önceki uygulama testleri tekrarlanmadı. VDS/SSH/deploy/restart/migration/router/
V1/V2.5/RADIUS/IPsec veya mevcut DB verilerine işlem yapılmadı.

## Standalone betik güvenlik incelemesi — 2026-11-16 — düzeltilmiş sürüm PASS

Başlangıç 07a9032 temiz. Eski dosyanın SHA256'sı yayımlanan
368ee5ceccbb93458e44c50354f804f3689fb323c40ff77fb4c83f8383a233b9 ile
birebir eşleşti. Hash doğru olsa da eski sürüme koşulsuz güvenlik PASS verilmedi:

- Servis venv Python'u -I ile başlatılıyordu. -I, .pth/sitecustomize çalışmasını
  engellemez; read-only SQL başlamadan önce yan etkili başlangıç kodu çalışabilirdi.
- ssl.create_default_context SSLKEYLOGFILE değişkenini kullanarak dosya
  açabilirdi. salt okunur iddiası ortamdan bağımsız değildi.
- Backup metadata kontrolünden sonra archive/pg_restore dosyayı yoluyla yeniden
  açıyordu. Yol değişiminde kontrol edilen nesneyle okunan nesne farklılaşabilirdi.
- capture_output sınırı süreç bittikten sonra uygulanıyordu; büyük/bozuk dump
  çıktısının RAM kullanımını gerçek zamanlı sınırlamıyordu.

Düzeltmeler:

1. Servis venv'i ve uygulama kodu artık çalıştırılmaz/import edilmez. Root
   sahipliği ve yazılabilirlik denetimli /usr/bin/python3, -I -S -B ile,
   API UID/GID'sinde açılır. Helper yalnız stdlib ctypes + root sahipli sistem
   libpq'su kullanır; system/site/user Python başlangıç kancaları yoktur.
   Ana betik de bu launcher bayrakları yoksa secret toplamadan önce BLOCKED olur.
2. DB URL env/argv/dosyaya yazılmaz; bounded stdin pipe'ıyla helper'a gider.
   URL parametreleri tekrar doğrulanır, libpq PQconnectdbParams yalnız sabit
   host+hostaddr=127.0.0.1, 55433, v26_acceptance/mikrotik_v26_acceptance'a bağlanır.
   DB query/fragment/service/socket override yoktur. Bu yalnız loopback DB
   probunda SSL/GSS kapalı, passfile=/dev/null'dır: kullanıcı HOME altındaki
   varsayılan sertifika/pgpass/GSS dosyaları aranmaz. Router TLS politikası
   değiştirilmedi. SQL değerleri PQexecParams parametreleridir; assert ile
   atlanabilen kontrol yoktur. BEGIN REPEATABLE READ READ ONLY + SHOW doğrulaması,
   session default_transaction_read_only=on ve her sonuçta ROLLBACK vardır.
   Catalog fonksiyonları pg_catalog ile nitelikli, core tablolar regular table
   olarak doğrulanır. Yalnız sabit SELECT/SHOW/transaction SQL'i vardır.
3. TLS context doğrudan SSLContext(PROTOCOL_TLS_CLIENT) ile kurulup TLS>=1.2,
   hostname/chain doğrulaması ve sabit sistem CA dosyasıyla kullanılır.
   SSLKEYLOGFILE/SSL_CERT_FILE/SSL_CERT_DIR ortamı key-log veya CA override açmaz.
   Public pilot CA parse'ı da key-log açmaz. Yeni indirme komutu aynı yaklaşımı
   kullanır; proxy ve redirect kapalı, commit+hash sabittir, kod hash öncesi çalışmaz.
4. Çerez gizli TTY girişinden yalnız loopback GET /api/v1/auth/me header'ına
   gider; başka endpoint, dış HTTPS, argv, env, dosya veya çıktıya gönderilemez.
   Ana süreç ve DB helper core dump'ı kapatır, Linux dumpable durumunu sıfırlar.
   Çerez için getpass echo fallback'i reddedilir. Yeni login/grant yaratılmaz.
5. Dosyalar her parent bileşeni directory FD/openat + O_NOFOLLOW ile dolaşılıp
   O_RDONLY açılır. Metadata ve içerik aynı FD üzerinden kontrol edilir.
   Arşiv fileobj'den okunur; pg_restore --list yalnız miras verilen read-only
   /proc/self/fd/N'i açar. Hiçbir archive extract çağrısı yoktur. PAX/GNU metadata
   header boyutları payload parse edilmeden sınırlanır, sparse/link türleri reddedilir.
6. Alt süreçler root sahipli sabit sistem araçlarıdır; ortamları temizlenmiştir.
   stdout/input pipe'ları canlı byte limiti ve deadline ile işlenir, stderr
   terminale/dosyaya aktarılmaz. Limitte yalnız aracın kendi child'ı sonlandırılır;
   mevcut VDS servislerine kill/restart/deploy/DB migration çağrısı yoktur.

Ağ envanteri: launcher raw.githubusercontent.com HTTPS; betik yalnız
v26.mikmanager.com.tr HTTPS hazır/statik dosyalar, 127.0.0.1:18996 GET ve
127.0.0.1:55433 DB. Cookie dış HTTPS'e gitmez. systemctl yalnız local show,
ip yalnız kernel address/route get metadatası; 10.250.0.19'a RouterOS socket,
login veya veri isteği yoktur. DNS çözümü sistem resolver'ını kullanabilir.

Yazma kapsamı: kod/env/backup/config izin ve içerikleri değişmez; yeni dosya,
yedek, migration, kalıcı DB değişikliği veya oturum/grant talep edilmez.
TTY/pipe/stdout IO vardır. Normal OS erişim metadata'sı ve mevcut API/DB erişim
logları okuma sırasında ilerleyebilir; 'writes_performed=false' bu aracın
kalıcı değişiklik istemediğini belirtir, tüm işletim sistemi disk hareketlerinin
sıfır olduğunu iddia etmez. incidental access logging olasılığı JSON'da da
belirtilir. PASS yalnız incelenmiş launcher ve güvenilen sistem araçları için
yerel güvenlik sonucudur; gerçek VDS/PG16 işlev veya canlı cihaz kabulü değildir.

Doğrulama: toplam 18 benzersiz hedefli test PASS. İlk 13'lü koşuda sistem yol
sahipliği fixture'ı host'a dayandığı için tek test BLOCKED oldu; explicit trusted
system path mock'u eklendi, yalnız o test ve yeni güvenlik testleri çalıştırıldı.
Son arşiv metadata ve native DB parametre değişikliklerinde yalnız ilgili testler
tekrarlandı. Gerçek SSLKEYLOGFILE env testi dosya yaratılmadığını kanıtladı;
read-only FD değişim testi, parent rename/symlink yarışı, timeout/output limit,
libpq C parametre/cleanup mock ve transaction/rollback negatifleri PASS.
Native libpq testi gerçek DB'ye bağlanmaz. Syntax/diff PASS. App/frontend değişmedi;
VDS/SSH/servis/DB/router/RADIUS/IPsec/deployment/migration işlemi yapılmadı.

## TABLE_ABSENT sonrası registry planı — 2026-11-16

Kullanıcının son VDS readonly sonucu: authenticated_local_admin,
capability_selection, database, session_database_match PASS; aday
v2-user-49b00e12-4d11-4413-94ee-f222ab056703 / revision 0. Üç tablo TABLE_ABSENT;
ACTIVE_CODE_IDENTITY_MISMATCH ve ikincil CODE_SNAPSHOT_REQUIRED; rollback
kanıtları tamamlanmamış. Geçmiş BLOCKED kayıtları kapanmış sayılmaz.

Tek güncel operasyon planı: [CEBECI_REGISTRY_MIGRATION_PLAN.md](CEBECI_REGISTRY_MIGRATION_PLAN.md).
Yalnız public üç registry tablosuna özel, onay/receipt/maintenance/DB/core seal/
role/lock/schema/ACL guard'lı install.sql ve normatif contract/hash hazırlandı.
Başlangıç 006 değiştirilmedi veya startup migration eklenmedi. İdempotent kurulum,
managed NOOP, partial/drift/unmanaged STOP ve atomic migration audit tanımlıdır.
Default rollback kod/env geri dönüşü + registry/audit korunmasıdır; populated
altyapıyı silen down yoktur. Yapısal boş kaldırma ayrı onay/receipt/RESTRICT gerektirir.

Preflight artık disk snapshot'ını çalışan API kimliği kontrolünden ayırır.
Mismatch disk yedek denetimini atlatmaz; yedek sadece disk baseline'ı olarak
etiketlenir ve overall BLOCKED devam eder. Repo/build/scope mismatch ayrı
sabit kodlarla ve yalnız geçerli hash değerleriyle raporlanır; yeni hash yayımlandı.
Eski readonly komutu eski sürümünü okumaya devam eder; yeni teşhis artefaktı
kullanılmadan yeni davranış varsayılmaz.

Yerel PASS: yeni PG16 single-user ortamında SQL kurulum/noop/negatif/gerçek
SQL audit hatası rollback ve core veri korunumu; metadata/model/legacy hash
kontratı; iki yeni readonly diagnostic testi. Gerçek VDS/SSH/migration/restart/
deploy/router/RADIUS/IPsec ve mevcut DB işlemi yapılmadı. Ayrıntı ve gerçek
BLOCKED koşulları tek planın son bölümlerindedir.
