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
