# NEXT_STEP_CONTINUE_HELD sonrası hazırlık — fixture v1

Yalnız memory/fake provider. Veri niteliğinde NEXT_STEP_PREPARED_HELD kaydı;
çalıştırma, hesap değişikliği veya canlı hazır olma kanıtı değildir.

## Mevcut mekanizmayı yeniden kullanma

NextStepPreparationService, NextStepExecutionService doğrulayıcısını ve
FixtureExecutionService'in TTL/registry/tek kullanım/atomik stage motorunu
kullanır. Ayrı authorization registry veya abone deposu yoktur. Yetki rolü mevcut
FixtureExecutionAuthority can_issue/can_stage alanlarıdır; burada can_stage
sadece hazırlık kaydını tüketme iznidir. Bu yetki provider yürütmesine dönüşmez.

Plan NEXT_STEP_PREPARATION_PLAN_V1_FIXTURE, authorization
NEXT_STEP_PREPARATION_AUTH_V1_FIXTURE ve ayrı strict record tipi kullanır.
Yürütme yetkisi execution_authorized=false; provider_dispatch/external_writes/
live_ready=false. Mevcut executor yalnız kesin execution record/authorization
sınıflarını kabul eder; hazırlık alt tipi o sınıflarla eşdeğer değildir.
stage giriş noktası da yalnız hazırlık üretebilir. Yeni otomatik worker state'i
NEXT_STEP_PREPARED_HELD için claim kapalıdır.

## Kanıt ve sıra

- Mevcut next-step CONTINUE policy registry kaydı ve sürümü/UUID'si eşleşmeli;
  NEXT_STEP_CANCELLED_HELD veya ilk adım CONTINUE buna dönüşmez.
- Mevcut policy checkpoint, özel kopyada NEXT_STEP_DECISION_RECORDED öncesini
  ve mevcut evidence evaluator aracılığıyla bağımsız provider kanıtını yeniden
  doğrular. Kaynak state/provider geriye sarılmaz. Sonuç kesin CONFIRM_SUCCESS
  olmalı; UNKNOWN/ret/kararsızlık yeterli değildir.
- Tenant/subscriber/request/previous execution/event/attempt, plan/CONTINUE
  hash'i, step sequence/identity, evidence/UNKNOWN receipt fingerprint, owner
  revision/fence/token ve contract sürümleri plan/checkpoint hash'ine bağlıdır.
- Mevcut dört adımlı kanonik plan içinde ENABLE_RADIUS sonrası yalnız kalan
  COMMIT_OWNER_CAS (sequence4) hazırlanabilir. Bu, owner commit çalıştırmaz.
  Son adım sonrası kalan iş yoksa veya sıra farklıysa durulur. Yeni plan adımı
  uydurulmaz. Deterministik next_step_id ve mevcut record/state kontrolü ikinci
  hazırlığı engeller; aynı UUID replay de reddedilir.

## Tüketim ve sınırlar

Issue TTL 1–300 saniye; actor/tenant scope ve ayrı issue izni zorunlu. Prepare
anında izin/expiry/registry içerik eşleşmesi ve güncel kanonik plan tekrar
kontrol edilir. Mevcut memory transaction owner revision/fence+1, journal
revision+1, lease token+1, audit, HELD outbox, record ve authorization tüketimini
birlikte yayımlar. Önceki record/audit/outbox geçmişi korunur; yeni olay eklenir.
Provider, owner authority ve active_request değişmez. Başarı state'i, retry,
telafi, dispatch, execution veya sonraki adım başlatılmaz.

8 yeni hedefli test: hazırlık JSON roundtrip ve executor/worker reddi; CANCEL/
ret/yanlış sıra/son adım; scope/hash/event/attempt/receipt/step/version bağları;
TTL/izin/değişmiş grant; owner/journal/lease/provider drift; beş atomik fault;
yarış/duplicate/reused UUID; UNKNOWN/unresolved/policy sürümü. State ve provider
snapshot'ları karşılaştırılır. Eski başarılı AAA suite tekrarlanmadı.
PostgreSQL/migration/gerçek audit/AAA/secret erişimi yoktur.

Sonraki işlem veya bu veri kaydını yürütme yetkisine dönüştürme bu tasarımın
dışındadır; ayrı kapsam ve güvenlik tasarımı gerektirir.

## Ayrı execution authorization checkpoint'i — 2026-11-12

PreparedExecutionService mevcut FixtureExecutionService issue/stage motorunu,
ExecutionIntent TTL sınırını, execution_authorizations/execution_records registry'sini
ve atomik transaction'ı kullanır. Yeni paralel yetki deposu yoktur. plan() mevcut
hazırlığın consumed kaydı, event/audit/hash ve CAS/fencing bağlarını kontrol eder;
özel predecessor kopyasında aynı NextStepPreparationService üzerinden tüm önceki
kanıt/sıra zincirini yeniden doğrular. Gerçek unit/provider geriye sarılmaz.

PREPARED_EXECUTION_PLAN_V1_FIXTURE hazırlık ID/fingerprint'ini ve mevcut
execution/event/attempt/tenant/subscriber/canonical step/hash/evidence/receipt/
owner revision/fence/token/sürüm bağlarını taşır. Yetki
PREPARED_EXECUTION_AUTH_V1_FIXTURE ayrı UUID ve actor ile aynı registry'ye kaydedilir.
Issue provider çağırmaz, owner/journal/outbox/preparation kaydı değiştirmez.

consume (stage alias'ı da yalnız aynı işlemi yapar) scope/TTL/registry/tek kullanım
ve güncel planı tekrar doğrular. Mevcut transaction owner revision/fence+1,
journal revision+1, lease token+1, audit, HELD outbox ve tüketim kaydını birlikte
EXECUTION_AUTHORIZED_HELD durumunda yayımlar. Önceki PREPARED_HELD dahil tüm
kayıtlar korunur; yeni kayıt eklenir. Owner authority/active_request/provider
aynı kalır. Bu checkpoint yalnız yetkilendirme metadata'sıdır; çalıştırma
capability'si değildir. execution_authorized=false burada executor tarafından
kabul edilen yetki olmadığını belirtir; ayrı issued authorization nesnesinin
varlığını inkâr etmez. Dispatch için ayrı, henüz tanımlanmamış kabul yolu gerekir.
Mevcut exact-type executor ve worker bu yeni checkpoint'i çalıştıramaz.

7 yeni test PASS: issue/consume ayrımı ve JSON roundtrip; kapsam/kimlik/event/
attempt/hash/step/version bağları; CAS/fence/provider/preparation drift;
TTL/permission; beş atomik fault; concurrent CAS/duplicate/replay; UNKNOWN/
CANCELLED/eksik kanıt/preparation. Testte yeni akış boyunca fake execute/run
metotları yasak; provider snapshot değişmez. Önceki başarılı testler tekrarlanmadı.
Gerçek DB/kullanıcı/audit/AAA veya ağ işlemi yapılmadı; push yok.

## Kontrollü authorized-held fixture execution — 2026-11-12

Önceki bölümde kapalı olan **explicit fixture claim** kapısı bu sürümde yalnız
PreparedExecutionAuthorization + PreparedExecutionRecord + PreparedExecutionPlan
exact-type üçlüsü ve EXECUTION_AUTHORIZED_HELD için açılmıştır. PREPARED_HELD
hâlâ yeterli değildir. Issue/consume otomatik dispatch başlatmaz; planın geçmiş
execution_authorized=false alanı tek başına izin taşımaz. Ayrı ExecutorContext
can_execute, permission, kayıt, TTL, claim ve güncel kanıt kontrolleri gerekir.

Mevcut FixtureExecutor kullanılır; ikinci executor/provider/receipt sistemi yok.
Claim ve run öncesinde PreparedExecutionService mevcut hazırlık/evidence/sıra
zincirini private predecessor image üzerinde tekrar doğrular. Owner/journal,
HELD event, consumed audit, next-step/preparation kimlikleri ve plan sürümü
bağlanır. Attempt TTL'si kalan authorization TTL'si ile sınırlıdır; süresi dolmuş
yetkiyle claim/run yapılamaz. Timeout coordinator yalnız UNKNOWN kaydı oluşturmak
üzere süresi dolmuş claim'i okuyabilir; yeni dispatch yapamaz.

Aynı execution/attempt eşzamanlı claim ve run mevcut kilit/status/fencing yolu
ile bir STARTED üretir. RESPONDED tekrarında yalnız saklanan receipt döner;
IN_FLIGHT veya UNKNOWN yeniden dispatch edilmez. Mevcut
AAA_EXECUTOR_RECEIPT_V1_FIXTURE komut/receipt sürümü, execution/event/attempt,
step/plan hash, owner revision/fence/token eşleşmesiyle atomik kabul edilir.
SUCCESS bu kanonik son adımda yalnız fixture owner CAS'ını RADIUS yapar;
REJECTED ve UNKNOWN owner LOCAL/active_request'i korur. Sonraki adım başlatılmaz.
COMMIT_OWNER_CAS fake provider durumunu değiştiren bir router/AAA komutu değildir;
yalnız fake receipt ve sonuç kabulünde in-memory owner CAS söz konusudur.

Beş atomik kayıt hata sınırında receipt tüketimi geri alınır; fake receipt ve
RESPONDED/IN_FLIGHT kanıtı korunur. CAS/fence drift'te kör retry yoktur. Kaybolan
cevap veya crash timeout ile UNKNOWN olarak tutulur. Kaydedilmiş geç UNKNOWN,
sonradan gelen kesin receipt ile otomatik değiştirilemez.
NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE execution_plan_contract alanı artık
PREPARED_EXECUTION_PLAN_V1_FIXTURE değerini de taşır. unknown_evidence mevcut
salt okunur paketi sağlar. Mevcut EVIDENCE_EVALUATION evaluator bu checkpoint'i
correlation/receipt fingerprint ile READ_ONLY_RECONCILIATION_REQUIRED olarak
raporlar; kesin bağımsız değerlendirme/karar yetkisi henüz açılmamıştır. Böylece
bu görevde yeni reconciliation motoru veya sahte kesin başarı üretilmez.

8 yeni executor testi ve yeni explicit claim davranışına uyarlanan 1 authorization
izni testi geçti. SUCCESS/REJECTED/UNKNOWN, crash/lost-response, claim/run/accept
race, replay, TTL/scope/version/content, stale fencing/history, post-effect CAS
ve beş atomik fault kapsandı. Eski başarılı suite tekrarlanmadı. PostgreSQL/ağ/
gerçek provider/secret kullanılmadı; test fixture dış IO girişlerini yasaklar.

## Prepared UNKNOWN bağımsız evidence değerlendirmesi — 2026-11-12

Önceki bölümdeki prepared checkpoint için koşulsuz read-only blokajı aynı
EVIDENCE_EVALUATION_V1_FIXTURE evaluator içinde kaldırıldı. Yeni evaluator,
karar servisi veya input kanıt endpoint'i yoktur. Yetkili pinned fake reader
üzerinden receipt/current state/fence okunur. Executor fake dispatch sırasında
provider state'ine receipt canonical fingerprint'ini `executor_evidence` olarak
kaydeder; bu kayıt local timeout/UNKNOWN kabulünden üretilmez. Kesin provider
receipt'i bu dispatch kaydıyla eşleşmeli, execution için tek olmalı ve provider
örneği execution'ın kayıtlı kaynağı olmalıdır. Kopya reader, local UNKNOWN veya
UNKNOWN'dan outcome değiştirilerek türetilmiş beyan tek başına kanıt değildir.
Bu metadata fake provider trust boundary'sidir, kriptografik imza veya canlı
sağlayıcı bağımsızlığı garantisi değildir; tüm internal state'i yetkisiz yazabilen
bir saldırgana karşı tamper-proof ledger iddiası yoktur.

Mevcut UNKNOWN referansı execution/event/attempt/tenant/subscriber/step/plan hash,
receipt fingerprint, owner revision/fence/token ve contract sürümüne bağlanır.
Mevcut staging/UNKNOWN checkpoint ve audit/outbox sayımları kontrol edilir.
Prepared authorization ve tüm öncül preparation/CONTINUE/decision/provider
zinciri mevcut doğrulayıcılarla private kopyalarda yeniden değerlendirilir.
COMMIT_OWNER_CAS provider durumunu değiştirmediğinden pinned reader'ın kesin
SUCCESS/REJECTED receipt'i gereklidir; aynı provider state'inden başarı tahmini
üretilmez. Eksik/UNKNOWN/duplicate/stale/çelişkili kanıt fail-closed kalır.

Çıktı yalnız CONFIRMED_SUCCESS / CONFIRMED_REJECTION veya
READ_ONLY_RECONCILIATION_REQUIRED değerlendirmesidir. Unknown receipt, owner,
journal, audit, outbox, history ve provider değişmez. execution_plan_contract
alanı prepared kanıtı açıkça ayırır. Bu yeni evaluation için mevcut issue/apply
karar kapısı kapalıdır: PREPARED_EXECUTION_READ_ONLY_EVALUATION_ONLY. Otomatik
SUCCESS/CONTINUE/CANCEL/retry/dispatch/telafi yoktur.

7 yeni hedefli test PASS: kesin success/ret ve history değişmezliği; UNKNOWN/
missing/local-derived kanıt reddi; referans scope/hash/kimlik/sürüm; bağımsız
receipt scope/step/version; stale fence/CAS/provider, duplicate audit/event ve
missing history; foreign reader/izin/crash; duplicate receipt/dispatch-provenance.
Son provenance kontrolü sonrası yalnız yeni test ve ilgili kesin kanıt matrisi
tekrarlandı. Eski başarılı AAA suite çalıştırılmadı. Gerçek PG/ağ/AAA erişimi yok.
Açık sınır: ayrı yetkili karar entegrasyonu ve gerçek provider kabulü bu görevin
dışındadır; fixture doğrulaması canlı entegrasyon izni vermez.

## Prepared UNKNOWN atomik yetkili karar bağlantısı — 2026-11-12

Koşulsuz prepared-evaluation karar blokajı kaldırıldı; yeni servis/registry/state
oluşturulmadı. Mevcut ExecutorReconciliationService issue/apply ve
AUTHORIZED_DECISION_V1_EXECUTOR_FIXTURE, prepared plan sürümü ile
NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE eşleşmesini şart koşarak yeniden kullanılır.
Fresh evaluator issue/apply öncesinde UNKNOWN checkpoint'i, pinned fake provider
receipt/provenance, tek execution kaydı ve tüm önceki hazırlık/karar zincirini
tekrar doğrular. Scope, execution/event/attempt, canonical step/plan hash,
receipt/evidence fingerprint, owner revision/fence/token ve sürüm bağları grant'ın
nested evaluation'ında korunur. Step identity mevcut doğrulanmış plan ve receipt
üzerindedir; kullanıcıdan bağımsız yeni bir step beyanı kabul edilmez.

Issue yalnız süreli server-registry grant ve ISSUED audit üretir. Apply ayrı
can_apply_decision ve can_evaluate izinleriyle TTL/tek kullanım/replay ve güncel
CAS/fencing/kanıtı tekrar kontrol eder. Mevcut transaction owner revision/fence,
journal revision, lease token, audit, HELD outbox ve grant tüketimini atomik
kaydeder. Aynı NEXT_STEP_DECISION_RECORDED durumu kullanılır; yeni durum yoktur.
Owner authority LOCAL/active_request ve orijinal UNKNOWN receipt korunur.
Önceki kayıt/audit geçmişi değiştirilmez, yeni olaylar eklenir. Outbox sonuç
etiketi yetkili kararın kanıt yorumudur; provider effect/SUCCESS geçişi değildir.

7 yeni test + yeni issue izni davranışına uyarlanan 1 ilgili evaluator testi
PASS. Success/ret, scope/kimlik/hash/sürüm, eksik/bağımsız olmayan kanıt, current
CAS/fence/provenance, TTL/izin, reused UUID/duplicate/concurrency ve beş atomik
fault kapsandı. Önceki başarılı suite tekrarlanmadı. Otomatik SUCCESS/CONTINUE/
CANCEL/retry/telafi/staging/dispatch yok. Gerçek PostgreSQL veya provider/ağ
kabulü yapılmadı. Sonraki işlem seçimi bu kararın otomatik sonucu değildir.
