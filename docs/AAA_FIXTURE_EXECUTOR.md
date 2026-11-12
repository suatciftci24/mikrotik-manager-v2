# AAA kontrollü fixture executor / receipt / UNKNOWN — v1

2026-11-11 · `AAA_FIXTURE_EXECUTOR_V1` / `AAA_EXECUTOR_RECEIPT_V1_FIXTURE`.
`app.simulation.aaa_executor` yalnız explicit memory UoW ve FakeFencedProvider
kabul eder. Gerçek provider adaptörü, ağ, DB, credential, endpoint veya worker
daemon yoktur. RADIUS UI ve önceki başarılı AAA kabulleri korunur.

## Staged adımın sahipliği

ExecutionRecord artık stage commit sonundaki owner/journal/lease/outbox
checkpoint fingerprint'ini taşır. Claim ve etki öncesinde bu fingerprint,
tüketilmiş execution grant/audit, plan hash, event ID ve izinli adım doğrulanır.
Eksik eski fixture kaydı kendiliğinden yürütülebilir sayılmaz.

ExecutorContext can_execute/can_accept ve ayrı can_record_timeout kapıları
varsayılan false'dur. Context yalnız AAA_EXECUTOR_FIXTURE_ONLY. Mevcut tenant/
actor PreviewScope ayrıca kontrol edilir. Gerçek sistem yetkisi oluşturulmaz.

Tek staged execution ID (ExecutionRecord.authorization_id) bir attempt UUID'sine
bağlanır. Komut tenant/subscriber/request, execution/event ID, attempt, execution
plan hash, izinli adım, owner revision/fence, worker token/kimliği ve aware UTC
son geçerlilik zamanını kapsar. Attempt1–300s (varsayılan30), repository fake
clock'undan hesaplanır. Expiry eşitliği geçersizdir. Aynı aktif claim dönebilir;
farklı attempt veya expired claim otomatik yeni yürütme başlatamaz.

## Sahte etki ve receipt iki ayrı aşamadır

1. `run` güncel staged owner CAS, token, event/plan ve provider evidence anchor'ını
   tekrar doğrular. Provider high-water `(owner_fence, worker_token)` daha düşük
   olmalıdır. Unit→provider lock sırası TOCTOU'yu bu RAM instance'ında engeller.
2. IN_FLIGHT attempt/audit kaydı önce yayınlanır; bundan sonra sonuç belirsiz olabilir.
3. Yalnız kapalı hedefin ardından LOCAL fence veya doğrulanmış source fence ardından
   RADIUS enable, mevcut saf `_transition` kuralıyla provider RAM'inde modellenir.
   COMMIT_OWNER_CAS dış provider etkisi değildir. Ağ çağrısı yapılmaz.
4. Provider RAM'indeki yeni execution ledger receipt'i saklar. Aynı geçerli
   command tekrarı RESPONDED receipt'ini döndürür; etki ikinci kez uygulanmaz.
   IN_FLIGHT veya crash sonrası run tekrar gönderim yapmaz, read-only uzlaştırma ister.
5. `accept` ayrı atomic memory UoW'de receipt'i kaydeder. Fake provider etkisi bu
   transaction'ın parçası değildir; receipt commit fault'u etkiyi geri almaz.

Eski source-fence kanıtı aynı root request ve provider state'e bağlıdır. Güncel
execution owner/worker counter'ı bu kanıttan ayrıdır; ENABLE sırasında LOCAL
kapalı kalır. Bu eşleşme gerçek uzak FreeRADIUS fencing desteği kanıtı değildir.

Receipt sürüm, execution/request/event/attempt ID, tenant/subscriber, plan hash,
adım, owner revision/fence, worker token ve provider evidence fingerprint taşır.
Fingerprint, tam command + provider son state'inin kanonik hash'idir. Caller'ın
uydurduğu veya değişmiş provider görüntüsüne ait receipt kabul edilmez.

| Receipt sonucu | Journal | Davranış |
| --- | --- | --- |
| SUCCESS | FIXTURE_STEP_SUCCEEDED | İlgili step ACKED/APPLIED. Yalnız COMMIT_OWNER_CAS step'inde owner RADIUS'a geçer ve reservation kalkar. |
| REJECTED | FIXTURE_STEP_REJECTED | Step CANCELLED/NOT_APPLIED; önceki provider etkileri geri alınmaz. |
| UNKNOWN | FIXTURE_STEP_UNKNOWN | Step UNKNOWN; owner rezervasyonu ve source korunur, ayrı uzlaştırma gerekir. |

Her kabulde owner revision+1, journal revision+1, ilgili outbox sonucu, lease
revision bağı, accepted receipt ve audit tek copy/publish'te güncellenir.
Fencing counter sabit tutulur; aynı receipt'in güvenli tekrarında kabul sonrası
checkpoint ve güncel counter kontrol edilir. Post-commit drift, eski token,
farklı içerik/sonuç veya expired worker receipt'i no-op adı altında kabul edilmez.
Geçerli exact duplicate yalnız tarihsel kabul sonucunu döndürür; yeni audit/etki yoktur.

## Çökme, kayıp yanıt ve belirsizlik

AFTER_DISPATCH / AFTER_EFFECT crash fixture'ları IN_FLIGHT bırakır. İkincisinde
provider ledger'ı SUCCESS bilse bile worker'ın geç ACK'i otomatik karar değildir.
Ayrı can_record_timeout yetkili coordinator, güncel CAS/fence'i doğrulayarak
expired attempt için UNKNOWN kaydedebilir. Worker bu yetkiyi varsayılan taşımaz.

UNKNOWN kabul edildikten sonra geç gelen farklı SUCCESS receipt'i çatışmadır.
Etki gözlenmemesi de REJECTED kanıtı sayılmaz. UNKNOWN fixture hem görünür etki
olmadan hem APPLY_THEN_UNKNOWN ile etki oluştuğu halde sınanır. Retry, telafi veya
sonraki adım otomatik başlamaz. `unknown_evidence` yalnız salt okunur accepted
UNKNOWN, provider receipt/state ve UoW görüntüsünü ayrı kanıt sürecine sunar;
başarıya çeviren veya eski reconciliation grant'ini açan metot yoktur.

Üç terminal state de worker claim'e kapalıdır. Başarı bir sonraki step'i veya
eski iptal edilmiş intent'i açmaz. Receipt commit fault'unda journal/owner/audit/
outbox/accepted receipt tamamen eski kalır; provider etkisi ise korunur.

## Yeni hedefli doğrulama

15 yeni test: sürümlü receipt, scope/attempt/event/hash/step/fence, eşzamanlı tek
sahte etki, idempotent kabul ve conflicting receipt, kesin ret, etkili/etkisiz
UNKNOWN, dispatch/effect sonrası crash ve timeout, CAS/fence drift,4 fault sınırı,
expiry/forgery, final owner CAS, stage consumption audit ve duplicate checkpoint,
LOCAL kapalıyken enable ve concurrent valid/conflicting receipt. İlk harness'teki unittest.run isim çakışması helper adıyla
düzeltildi; ürün hatası olarak sunulmadı. Önceki AAA testleri çalıştırılmadı.
Socket/PG/SQLite connect yasak. Crash durability/gerçek DB/uzak provider garantisi yok.

Sonraki tek teknik öncelik: yeni executor UNKNOWN receipt'ini, eski yetkileri
kullanmadan ayrı kanıt değerlendirme/karar sözleşmesine bağlamak; canlı bağlantı yok.

[Executor UNKNOWN değerlendirme ve yetkili karar devamı](AAA_EXECUTOR_UNKNOWN_DECISION.md)
pinned sahte provider'dan salt okunur kanıt alır. Executor provider instance'ı ilk
claim'de bağlar. Yeni ayrı fixture yetkisi olmadan kayıt ilerlemez; original UNKNOWN
receipt ve gerçek dispatch yasağı korunur.
