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
