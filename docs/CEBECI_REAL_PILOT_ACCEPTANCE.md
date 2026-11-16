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
