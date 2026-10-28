# Aşama 17 güvenlik ve dayanıklılık kararları

## Kapsam ve kanıt

Bu faz yalnız sentetik V2 içindir. Gerçek RouterOS/RADIUS/V1 bağlantısı, scheduler,
otomatik retry, production migration veya deploy eklenmedi. Dış yazma kapalıdır.
Offline/fake transaction testleri gerçek PostgreSQL veya tarayıcı kabulü sayılmaz.
Mevcut kimlik, abone, alarm, ayar ve audit tabloları değiştirilmez.

## Yetki ve sır sınırı

Provider I/O ve recovery önizlemesinin her accept/fail/view çağrısı mevcut
require_router(can_view_reports) ile korunur. Görünmeyen router 404, görünen ancak
yetkisiz özellik 403'tür. Önbellek/önizleme state'i oturumun eski grant'ini saklamaz.
current_demo_user aynı cookie için her istekte DB rol/active/permissions okur.
Sistem sağlık/entegrasyon/dayanıklılık endpoint'leri tam kapsamlı ADMIN ister;
VIEWER ve sınırlı ADMIN bunlardan global metadata öğrenemez. Mevcut scoped rapor
SQL count/page ve alarm scope testleri korunur.

Doğrulama yanıtı önceden input/ctx'yi çıkarsa da msg ve dinamik loc anahtarlarını
döndürüyordu. Bunlar validator mesajı veya kullanıcı kontrollü dictionary anahtarıyla
hassas değer yansıtabilirdi. Artık yalnız body/query/path/header/cookie konumu ve
sabit hata mesajı/türü, en fazla 20 hata döndürülür; msg/field-name/input/ctx echo yok.
Provider özeti secretref/credential assignment/bağlantı URI taşıyıcılarını reddeder;
provider exception metni/log traceback'i gateway yanıtına taşınmaz. SecretReference
opaque anahtarı repr/model_dump/model_dump_json dışında tutulur, API/audit deposuna
bağlanmaz. Gerçek sır çözümleme/saklama eklenmedi. Bu kontroller keyfi serbest metin
veya harici log altyapısı için genel DLP sertifikası değildir; gelecekte secret
resolver/client eklenmeden önce ayrıca uçtan uca log redaction onayı gerekir.

## Snapshot/delta sırası ve atomiklik

Batch gözlemleri UTC ve kind/id sırasına normalize edilir; eş değer saat dilimi
ve kayıt sırası cursor fingerprint'ini değiştirmez. Delta base_cursor doğrulaması
korunur. İlk snapshot'tan sonraki yeni tam snapshot açık source sequence taşır;
bilinen sequence'e eşit/eski değer veya sırasız tam snapshot reddedilir. Cursor
opaque'dir; hash/string'den yeni/eski sırası türetilmez. İlk salt okunur sentetik
snapshot sequence'siz okunabilir; bu kaynağın otomatik ingest'i başlatılmış değildir.

Tam snapshot'tan kaybolan kayıt için revision/gözlem watermark'ı korunur. Böylece
çıkarılmış kayıt eski revision ile yeniden eklenemez. Aynı kayıt için yükselen
revision eski gözlem zamanı taşıyamaz; ayrı kimlikli geç gelen tarihsel olay kabul
edilir, aynı event ID tekrarı yeniden effect üretmez. Omission WAN_DOWN/RESOLVED
olayı değildir. Başarısız reconcile önceki immutable state'i değiştirmez.

RecoveryPreview açıkça çağrılan, instance-local, kilitli offline simülasyondur.
Accept expected_cursor ile compare-and-swap yapar; eşzamanlı iki farklı komutun
biri 409 alır. Aynı batch replay'i yeni effect/son başarılı zaman oluşturmaz ve
mevcut arıza durumunu temizlemez. Gecikmiş fail, eski cursor/zamanla yeni başarıyı
DEGRADED yapamaz. Yetki kaldırılınca son başarılı snapshot da okunamaz.

Timeout/ERROR için yalnız önerilen 1,2,4,... en fazla 60 saniye backoff hesaplanır;
ACCESS_DENIED otomatik retry önermez. Hiçbir timer, sleep, polling veya provider
çağrısı bu sınıfta yoktur. Retry öncesi accept reddedilir. Son başarılı snapshot
korunur, fallback açık işaretlenir ve gözlem güncelliği ayrıca STALE/UNKNOWN olarak
hesaplanır. Başarı yoksa UNKNOWN, başarısız kaynakta eski kayıt varsa DEGRADED'dır.
Bu state API global cache'i veya dayanıklı ingest ledger'ı değildir; restart sonrası
kayıt saklama, kalıcı CAS ve audit transaction entegrasyonu gelecek onaylı faza aittir.
Mevcut kalıcı user/settings mutation + audit rollback/idempotency sınırları korunur.

## Kaynağa dayalı görünüm

/system/resilience yalnız GET'tir; her router ayrı provider envelope'undan okunur.
Bir timeout/bozuk veri diğer router, kayıtlı Dashboard veya rapor kaynağını değiştirmez.
Summary tüm yetkili batch üzerinde, tek provider read ile pagination öncesi hesaplanır;
ilk 50 kayıt dışındaki STALE gözlem gizlenmez. İstemciye tüm batch taşınmaz.
UNKNOWN/NO_DATA, bağlantı kesildi anlamına gelmez. STALE kaynak zamanına dayanır;
DEGRADED ölçülen provider hatasını gösterir, fiziksel router OFFLINE iddiası değildir.
Sistem Sağlığı provider_observations kartı aynı özeti kullanır. Son başarılı senkronizasyon
ölçülmediğinden last_success null'dır; kontrol zamanı gözlem zamanı yerine kullanılmaz.

Alarm ACK/READ/RESOLVED semantiği değiştirilmedi. Kaynak eksikliği yeni kesinti,
yinelenen snapshot yeni incident veya preview retry business audit üretmez.

## Salt okunur browser kabulü

V2_BROWSER_RESILIENCE_ONLY=1 mevcut ManagedAPI/UI yaşam döngüsünü kullanır; schema
veya test hesabı hazırlamaz. Gerçek UI'da provider TIMEOUT ve boş kaynak senaryosu
Playwright response interception ile yalnız tarayıcıda uygulanır. Bunlar gerçek
backend arızası diye raporlanmaz. Diğer router görünümü, UNKNOWN, senaryo kaldırılınca
kaynağın geri gelmesi, health kartı, 320/390px ve mutation isteği olmaması kontrol edilir.
Mevcut ADMIN/ayar/tercih ve abone/audit baseline'ı ile alarm ACK/okundu durumu korunur.
Gerçek tarayıcı çalışmazsa bu kapsam PASS sayılmaz.
