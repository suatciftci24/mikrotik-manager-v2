# AAA uçtan uca kabul — 2026-11-12

**PASS: yalnız in-memory deterministik fixture kabulü.** Başlangıç:
office-development / 76fd55d. Gerçek PostgreSQL/HTTP/UI/cihaz/AAA kabulü değildir.

## Çalıştırılan kapsam

Yeni `backend.tests.test_aaa_e2e_acceptance`: 6 test metodu, PASS.
Mevcut test sınıfı yalnız fixture kurucusu olarak kullanılır; eski suite/test
metotları çalıştırılmaz. Kurucu canonical AtomicPlan/AtomicRequest oluşturup
gerçek memory owner/journal/outbox/lease, fake provider, UNKNOWN, evidence,
yetkili karar ve ilk CONTINUE servis çağrılarını yapar. Yeni testler kalan
zinciri aynı request/unit/provider üzerinde sürdürür; sonuca göre doğrudan
başarılı state ataması veya mock başarı dönüşü yoktur. Yalnız dış socket/SQLite/
psycopg girişleri mevcut fixture tarafından hata verecek şekilde kapatılmıştır.
Negatif testlerde state kopyasının bozulması saldırı/fault girdisidir, başarı
kanıtı olarak kullanılmaz. Clock sabit fixture clock'tur; gerçek bekleme yoktur.

Akış:

```
canonical plan/hash → root claim/lease/fake execution → UNKNOWN receipt
→ bağımsız kanıt → yetkili karar → CONTINUE → execution authorization/staging
→ ENABLE_RADIUS fake execution → kayıp cevap/UNKNOWN
→ bağımsız evaluator → atomik NEXT_STEP_DECISION_RECORDED
→ CONTINUE → NEXT_STEP_PREPARED_HELD → ayrı execution authorization issue/consume
→ EXECUTION_AUTHORIZED_HELD → claim/fenced fake execution → receipt
```

CANCEL alternatif terminal koludur: hazırlık/execution'a ilerlemez. Final
COMMIT_OWNER_CAS SUCCESS yalnız fixture owner'ı RADIUS yapar; ret/belirsizlik
LOCAL kalır. Son UNKNOWN gerçek kayıp cevap durumunda ayrıca evaluator ve ayrı
atomik karar üzerinden NEXT_STEP_DECISION_RECORDED'e ulaşır; UNKNOWN receipt
korunur ve bu karar owner authority'yi değiştirmez. Hiçbir kol sonraki işi,
retry/telafi/dispatch'i otomatik başlatmaz.

## Kabul matrisi

| Test | Sonuç | Kanıt |
| --- | --- | --- |
| Tam zincir: son SUCCESS / REJECTED / UNKNOWN ve kayıp cevap sonrası karar | PASS | Aynı plan/unit üstünde gerçek servis geçişleri; fixture owner ve receipt durumları; eski kayıtlar/audit korunur |
| CANCEL sonrası hazırlık/execution engeli | PASS | Değişmeyen state/provider snapshot ve fail-closed hata |
| Concurrent claim/run/accept, replay, provider sonrası AUDIT yazım hatası | PASS | Bir STARTED; eşit receipt; atomik rollback; cached receipt ikinci effect üretmez |
| Expired authorization ve stale owner CAS/lease fencing | PASS | Claim reddi; state/provider değişmez |
| Yanlış tenant/subscriber/execution/plan hash/step ve receipt attempt | PASS | Run/accept öncesi ret; state/provider değişmez |
| UNKNOWN no-retry; eksik/çelişkili/UNKNOWN türevi bağımsız olmayan kanıt | PASS | READ_ONLY_RECONCILIATION_REQUIRED; run/yeni attempt reddi; state/provider değişmez |

Geçmiş koruma assertion'ları eski execution/UNKNOWN/decision/policy kayıtlarını
birebir karşılaştırır ve audit'in önceki kısmını korur. Final outbox'ta PENDING
yoktur. Önceki journal durumları mevcut audit zincirindedir; yeni journal head
revizyonları kontrollü servis geçişleriyle oluşur. Yeni başarı için eski geçmiş
silinmez. Aynı request'in geçici store kopyaları yalnız negatif test izolasyonudur.

## Bulgular ve sınırlar

Yeni kabulde ürün kusuru veya kopuk bağlantı bulunmadı; backend değişikliği yok.
Önceki başarılı AAA suite, frontend TypeScript/build, browser/HTTP ve socket
teşhisleri tekrarlanmadı. Yeni testler ve dokümanlar tek commit'e alınır; push yok.
BASH/echo/pg_isready, stash ve backup/office-20261109 korunur. Gerçek DB, demo
abone/kullanıcı/audit, .env/secret/yedek, V1/V2.5/VDS/router/RADIUS/IPsec okunmaz
yazılmaz; migration/reset/restart/deploy yapılmaz.

**Gerçek entegrasyon BLOCKED / bu görevin dışında:** PostgreSQL migration ve
transaction/rol/RLS/crash-recovery kabulü; gerçek source owner CAS; provider
idempotency/fencing/kanıt kaynağı ve durable outbox/uzlaştırma; tenant/NAS/realm/
profil/abonelik politikaları; secret yönetimi; gerçek ağ timeout/partial failure
ve geri dönüş kabulü hâlâ ayrıca gereklidir. Memory fake source fingerprint'i
canlı imza veya distributed exactly-once kanıtı değildir. Bu belge canlı
bağlantı, veri taşıma, migration veya deploy onayı oluşturmaz.

Sıradaki tek öncelik: kabul sonucunu değerlendirdikten sonra ayrı güvenli Git
senkronizasyonu; canlı entegrasyon bu fixture PASS'inden başlatılmaz.

## Next-Step deadline güvenlik regresyonu — 2026-11-12

Başlangıç `main-guncel` / `32082b5`; GitHub ucu aynı, ağaç temiz.
Prepared authorization, fixture executor, evidence, atomik decision ve receipt
bağlantıları zaten uygulanmıştı. Bu incelemede iki gerçek eksik saptandı:
`claim` değiştirilmiş Pydantic AttemptIntent için 1–300 saniye sınırını yeniden
doğrulamıyordu; coordinator `timeout` attempt dolmadan UNKNOWN kaydedebiliyordu.
Yeni testlerde her iki eksik düzeltme öncesinde başarısız oldu.

Claim artık yeni ve duplicate girişte intent'i JSON sözleşmesiyle yeniden
doğrular. Timeout aynı unit/provider kilitleri altında expiry öncesini reddeder;
expiry eşitliğinde UNKNOWN kabulü ve idempotent tekrar korunur. Prepared claim
expiry'si authorization TTL'siyle sınırlı kalır. Dört eski fixture kurucusu artık
timeout öncesi sahte saati 30 saniye ilerletir; test beklentileri gevşetilmedi.

PASS: 3 yeni deadline testi + 2 doğrudan timeout regresyonu = 5 test;
değişen dört fixture modülü ve mevcut E2E kabulü = 52 test. Toplam 57 test geçti.
Yeni testler alt/üst TTL sınırlarını, değiştirilmiş new/duplicate claim'i,
dispatch/effect crash ve kayıp cevapta erken timeout reddini, expiry sınırını,
UNKNOWN replay ve geç kesin receipt çatışmasını state/provider snapshot'larıyla
doğrular. İlk düzeltme koşusundaki eski fixture timeout ihlalleri giderildi;
yanlış test sınıfı adı gerçek FixtureExecutorTests adıyla düzeltildi.
Diff kontrolü temiz. İlgisiz frontend/build/HTTP/PG kabulleri çalıştırılmadı.

Salt okunur canlı HTTPS 200 ve kaynakta doğrulanan `/api/ready` kimliği başarılı;
readiness `database_checked=false` bildirir, DB veya bütün servislerin sağlık
kanıtı değildir. DB sorgulayan `/api/health` çağrılmadı. Değişiklikler yalnız
memory fixture kodu/test/belge kapsamındadır; canlı DB, cihaz, RADIUS, VDS,
deployment/migration/restart/silme yoktur. Gerçek entegrasyon için önceki
PostgreSQL, trusted membership/owner writer ve provider kabul engelleri sürer.
