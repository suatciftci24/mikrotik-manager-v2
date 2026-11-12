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
