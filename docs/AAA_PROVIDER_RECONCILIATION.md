# AAA sahte provider fencing ve kanıta dayalı uzlaştırma — v1

2026-11-11 · `AAA_FAKE_PROVIDER_V1`. Yalnız `app.simulation.aaa_provider`.
Mevcut plan/journal/owner CAS/outbox ve LeasedMemoryOutbox kullanılır. Gerçek
RADIUS/RouterOS adaptörü, ağ, credential, DB, endpoint veya worker eklenmedi.
RADIUS Merkezi'nin canlı bağlantı yok bilgisi ve önceki kabulü korunur.

## Provider doğrulaması

FakeFencedProvider tek açık sentetik tenant/store/account için bağımsız bellek
tutar. Komut; kanonik plan hash, request/envelope fingerprint, account, event
UUID/sıra/adım, correlation, worker, attempt UUID, account-owner fence, worker
token ve dispatch anındaki operation revision içerir. Keyfi attributes/sır yoktur.

Etki öncesinde güncel trusted fixture scope/worker izni ve lease tekrar okunur;
expired/foreign/stale worker, başka plan/event/account veya dispatch kaydı olmayan
komut reddedilir. Fixture'da UoW kilidi ve provider kilidi sabit sırada tutulur;
kontrol ile sahte etki arasına lease devri giremez. Ağ çağrısı kilit altında yoktur.
Bu ortak bellek kontrolü gerçek uzak provider'ın desteklediği özellik sayılmaz.

Provider kendi account high-water mark'ını `(owner_fence, worker_token)` olarak
monoton tutar. Owner fence yeni operation'da artar; worker token operation içinde
artar. Böylece token'ın sonraki operation'da1'e dönmesi eski komutu geçerli
kılmaz. Düşük çift, aynı çiftin yeni attempt/event için kullanımı ve çelişkili
attempt digest'i reddedilir. Üretimde bu sayaçlar kalıcı/sunucu yetkili olmalıdır.

Idempotency anahtarı `(tenant,request,event)`; attempt anahtarı
`(tenant,request,attempt_uuid)` ve tam komut fingerprint'idir. Aynı geçerli
lease+aynı içerik önceki receipt'i döndürür, state generation ikinci kez artmaz.
Farklı içerik CONFLICT olur. Replay bile lease/ownership/fence kontrolünden geçer;
expired worker'a tarihsel receipt üzerinden yeni ACK yetkisi verilmez. Yeni
recovery attempt eski receipt'i yalnız read-only kanıt olarak okuyabilir.

Provider yalnız üç dış adımı modeller: hedefi kapalı hazırlama, LOCAL'i fence
ile kapatma, ardından RADIUS'u açma. Önceki provider receipt'leri sıralı APPLIED
olmalıdır. RADIUS'u açmak için LOCAL kapalı ve fence aynı request/owner fence'e
bağlı olmalıdır. Owner CAS ve telafi bildirimi sağlayıcı komutu değildir.

## ACK/NACK ve UNKNOWN ayrımı

`accept_provider_response` güncel lease ile provider'ın kendi sakladığı receipt'i
karşılaştırır; caller'ın outcome beyanını kullanmaz. Geçerli APPLIED→ACK,
NOT_APPLIED/UNKNOWN→NACK yoluna gider. Aynı geçerli sonuç tekrarında yeni journal/
audit olayı üretilmez. Sahte/çelişkili receipt veya geç gelen stale worker yanıtı
journal'ı değiştiremez. Önceki ham lease fixture ACK/NACK metotları üretim giriş
noktası değildir; yeni provider sınırının alternatifi olarak kullanılmamalıdır.

APPLIED receipt'in kaybolması veya dispatch sonrası lease kaybı UNKNOWN kalır.
Provider'da receipt bulunmaması “uygulanmadı” kanıtı değildir. UNKNOWN fixture
receipt'i de başarı/başarısızlık olarak sınıflandırılmaz. Provider script outcome'u
test kurulumunda sabittir; istek içeriğinden seçilmez.

## Salt okunur uzlaştırma

`reconcile_unknown` yalnız güncel RECONCILE lease ile provider'ı doğrudan okur;
caller tarafından verilmiş proof'u yetki veya güvenilir provider kanıtı saymaz.
Pure `assess_unknown` aşağıdakileri karşılaştıran fixture sözleşmesidir:

- Journal'ın request fingerprint/plan hash, RECONCILIATION durumu ve revision'ı;
  ilişkili son audit aktör/correlation/plan hash/operation revision kaydı.
- Owner'ın beklenen rezervasyon revision'ı, aktif request'i, LOCAL sahipliği ve
  fence'i. Account revision drift'inde restore/overwrite/auto retry yoktur.
- Tüm outbox event ID'leri, sıra/adımlar ve correlation; tek UNKNOWN başlık,
  önceki ACKED/APPLIED ve sonraki dokunulmamış PENDING kayıtlar.
- Provider'ın eksiksiz receipt prefix'i, exact account/tenant/plan/envelope ve
  event bağları; tarihsel DISPATCH worker/attempt/token/operation revision kanıtı.
- Receipt'lerin birbirine bağlı ön/son state zinciri, izinli provider geçişleri
  ve güncel provider generation/state'i. Eksik prefix, stale revision, çelişkili
  NACK/APPLIED veya UNKNOWN sonucu karar vermeyi durdurur.

Tam tutarlı kanıt yalnız **PROVIDER_APPLIED_CONFIRMED** veya
**PROVIDER_NOT_APPLIED_CONFIRMED** şeklinde ilgili adımı sınıflandırır. Bu,
operation başarısı/başarısızlığı veya source flip değildir. `automatic_resume=false`;
journal RECONCILIATION ve owner rezervasyonu değişmez. Geriye kalan her durumda
**READ_ONLY_RECONCILIATION_REQUIRED** korunur. Provider ve UoW okumaları veri
mutasyonu yapmaz. Saf karşılaştırıcı tek başına authenticated/signed proof sağlamaz.

## Yeni izole kanıt ve kalan sınır

11 yeni test: exact replay/duplicate ACK, yanlış plan/event/attempt/fence/account,
provider high-water ve attempt ledger, unauthorized/stale/late ACK, eşzamanlı
tek etki, sahte ACK/NACK, kayıp/UNKNOWN receipt, tam applied/not-applied kanıt,
kısmi prefix, çelişkili/stale history ve RADIUS activation source fence.
Socket/PostgreSQL/SQLite connect testlerde yasak; önceki AAA suite'leri yoktur.

Bunlar RAM modelidir; crash durability, PostgreSQL transaction, uzak provider
fencing, TLS, imza, gerçek credential veya üretim erişimi kanıtlanmaz.
Sonraki tek teknik öncelik: kanıtla onaylanan uzlaştırma kararının, ayrı açık
fixture yetkisiyle mevcut CAS/journal/outbox'a atomik işlenmesi; canlı bağlantı yok.
