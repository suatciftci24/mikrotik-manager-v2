# V2 entegrasyon hazırlığı (sözleşme v1)

Bu aşama yalnız izole yerel sentetik kaynak içindir. RouterOS/FreeRADIUS istemcisi,
secret resolver, ağ bağlantısı, polling, scheduler, üretim migration veya V1 geçişi yoktur.
Mevcut Dashboard/rapor/alarm/MikAjanı yolları değiştirilmedi. Yeni hazırlık sınırı
gelecekteki tüketiciler için açık ve salt okunurdur; canlı entegrasyon yapılmış değildir.

## Veri akışı ve arayüzler

`router API -> current_demo_user -> require_router(can_view_reports) -> gateway ->
SyntheticProvider -> mevcut router_detail / yerel demo store -> doğrulanmış Batch`.
Sistem hazırlık metadata endpoint'i ayrıca mevcut tam kapsamlı ADMIN guard'ını ister.
Backend tipi istemci seçimiyle belirlenmez: PPPoE otoritesi kayıtlı source alanındaki
LOCAL/RADIUS enum'udur; bilinmeyen kaynak None kalır, otomatik LOCAL seçilmez.
SYNTHETIC sağlayıcı adı dışında dispatch 403'tür. Gerçek sağlayıcıya fallback yoktur.

`integrations/contracts.py`: Inventory, PPPoE, Session, WAN, IPsec, Health, Event
provider Protocol'leri ortak `read(router_id) -> Batch` sözleşmesini paylaşır.
Sözleşme yalnız güvenli özet alanları taşır; keyfi payload/sır alanı kabul etmez.
SyntheticProvider mevcut RouterDetail/DemoReport doğrulamasını kullanır. IPsec
kaynağı yoksa NO_DATA; WAN zamanında yalnız kayıtlı report zamanı kullanılır.
Hesabın ACTIVE olması canlı oturum anlamına gelmez. Türü bilinmeyen eski hesap
PPPoE sayılmaz. Olaylar mevcut router_events kimliklerinden gelir, yeni olay üretilmez.
Yeni endpoint sayfalıdır (en fazla 50); sentetik köprü mevcut store list_items yolunu
sunucuda kullanır. Gelecekte büyük envanter için scoped SQL sayfalaması gerekecektir;
bu aşama mevcut depo/iş ekranlarını yeniden yazmaz veya ölçek sertifikası sunmaz.

## Snapshot/delta, hata ve tekrar işleme

Batch version/source_id/router_id/cursor, SNAPSHOT veya DELTA modu, complete bilgisi
ve gözlemleri içerir. Her gözlem kaynak ID/revision/observed_at, veri türü, durum ve
varsa otoriteyi taşır. Zaman timezone-aware'dır; UI Europe/Istanbul yaklaşımı korunur.
Delta base_cursor zorunludur; boşluk, kaynak/router uyuşmazlığı, yinelenen kayıt,
eski revision veya aynı revision'da farklı veri reddedilir. Tam olmayan snapshot
ve delta eksik kaydı silmez. Tam snapshot envanter üyeliğini değiştirebilir fakat
silinme kesinti/iyileşme olayı üretmez.

`reconcile` saf, açıkça çağrılan offline reducer'dır; scheduler veya persistent store
değildir. Aynı cursor/content yeniden uygulaması değişiklik üretmez; farklı content
aynı cursor ile reddedilir. Event kimlikleri complete snapshot'tan kaybolsa da receipt
hafızasında kalır; yeniden görünme yeni effect üretmez, farklı veriyle aynı event ID
reddedilir. Replica uygulayan çağıran yeni state'i saklamalıdır. Bu preview ledger'ı
süreçler arası dayanıklı exactly-once garantisi değildir. Gelecekte kalıcı ingest,
mevcut transaction/idempotency/audit + deterministik olay kimliğiyle aynı transaction
sınırında yapılmalı; bu faz DB'de yeni audit/incident veya ledger tablosu oluşturmaz.
Mevcut sentetik olay otomasyonu/idempotency yolları korunur.

Gateway timeout, provider erişim reddi ve diğer hataları ayrı, gizli ayrıntısız
router envelope'una çevirir; başarısız kaynağın toplamı bilinmiyor (null), OFFLINE
değildir. Başka router isteği bağımsızdır. Başarılı kaynakta bile gözlem zamanı
eskiyse STALE; zaman yok/gelecekteyse UNKNOWN. AVAILABLE kaynak okumasını ifade
eder, router bağlantı sağlığı veya gözlemin güncelliği değildir. Beş dakika yalnız
bu hazırlık projeksiyonunun açık freshness eşiğidir, canlı SLA değildir.

## Secret ve güvenlik sınırları

SecretReference yalnız `secretref:v2/<opaque-owner>/<opaque-key>` ve amaç
(ROUTEROS_AUTH/RADIUS_AUTH/IPSEC_PSK) içerir. Endpoint, parola, PSK veya API anahtarı
almaz; bu aşamada hiçbir yere kaydedilmez/çözümlenmez. Gelecekte ayrı onaylanmış
secret store çözümlemeli, sırlar API/audit/log veya düz metin DB alanlarına taşınmamalıdır.
ExternalConfiguration yalnız SYNTHETIC, routeros_enabled=false,
radius_enabled=false, external_writes=false kabul eder. Gateway dış yazmayı onay
ve request UUID verilse dahi koşulsuz reddeder. Mevcut lokal PPPoE onay/audit/
idempotency davranışı değişmez. Auth her istekte DB'den yenilenir; sınır yetkiyi
I/O öncesinde tekrar kontrol eder. Kullanıcı kontrollü router/backend/provider alanı
başka router verisini veya dış yazmayı açamaz. Kaynak DTO sahipliği ayrıca doğrulanır.

## Sonraki entegrasyon için onay kapıları

Önce ayrı kapsamlı kullanıcı onayıyla izole test cihazı/DB/ağ hedefi ve salt okunur
izinler tanımlanmalı. Ardından secret store ve rotasyon/redaction, TLS sertifika
kontrolü, dar client timeout/iptal ve hız sınırı, kaynağa özgü cursor/snapshot
anlamları, kalıcı ingest idempotency/transaction ve arıza izolasyonu test edilmelidir.
Dış yazma için ayrı açık yetkilendirme, preview/onay, kaynak otoritesi, audit,
idempotency ve geri dönüş tasarımı gerekir. Bu kapılar otomatik onay veya canlıya
bağlanma yetkisi değildir. V1 verisi/kimliği/adaptörü kullanılmaz, V1→V2 geçişi
başlatılmaz. Yönetim paneli yalnız DEMO/SYNTHETIC, RouterOS/RADIUS DISCONNECTED ve
V1 ISOLATED gösterir; connect/test düğmesi yoktur.

Aşama 17 sağlamlaştırması: yeni tam snapshot'lar için açık source sequence,
UTC/kayıt sırası normalizasyonu, omission sonrası revision watermark ve yetki
kontrollü offline recovery/CAS/backoff modeli eklendi. Ayrıntı ve operasyonel
sınırlar [SECURITY_RESILIENCE.md](SECURITY_RESILIENCE.md) belgesindedir. Provider
özetleri ve readonly sağlık görünümü gerçek entegrasyon veya otomatik retry değildir.
