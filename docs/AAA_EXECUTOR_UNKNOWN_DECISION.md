# Executor UNKNOWN evidence evaluation / authorized decision — v1 fixture

2026-11-11 · `app.simulation.aaa_executor_decision`. Yalnız explicit memory UoW
ve FakeFencedProvider kullanılır. Gerçek auth/DB/provider/endpoint/dispatch yoktur.
Mevcut UI ve önceki AAA kabulleri değişmez; eski test suite'leri çalıştırılmaz.

## Kanıtın kaynağı ve bağları

`EVIDENCE_EVALUATION_V1_FIXTURE` yalnız kabul edilmiş UNKNOWN executor receipt'i
karşısında değerlendirilir. Tenant/subscriber/request, execution/event/attempt
UUID, execution plan hash, fencing token, owner fence/revision, operation revision,
provider evidence fingerprint ve sözleşme sürümü sonuca bağlanır.

Executor ilk claim'de kullanılan sahte provider instance'ını aynı memory UoW'ye
sabitler. Değerlendirici kaydı caller'dan değil, doğrudan bu instance'ın bağımsız
executor ledger'ından okur. Başka instance'a kopyalanmış receipt/state bile trusted
kaynak sayılmaz. Instance bağı yalnız process-local fixture kimliğidir; uzaktaki
sunucu kimliği, imza veya durable credential mekanizması değildir. Eski fixture'da
kaynak bağı yoksa sessizce trusted sayılmaz.

Değerlendirme aynı unit→provider lock sırasıyla şunları kontrol eder:

- Accepted receipt UNKNOWN, checkpoint ve journal FIXTURE_STEP_UNKNOWN; owner
  CAS/revizyonu, aktif request, fence/token, lease DONE ve kabul sonrası hash.
- Exact execution/event/attempt/step/plan bağları; staged authorization ve provider
  komutu aynı tek yürütmeye ait olmalı. Command expiry okuma yetkisi değildir;
  geçmiş sonucu incelemek yeni yürütme izni vermez.
- Provider'ın kendi definitive SUCCESS/REJECTED receipt'i, güncel evidence hash'i
  ve en yüksek fencing çifti. Receipt yokluğu REJECTED kanıtı değildir.
- İlk provider prefix'i ve pre-execution evidence anchor'ı; mevcut saf effect
  kuralıyla beklenen son state. Önceki prefix veya son state değişmişse reddedilir.
- Journal audit, UNKNOWN outbox event'i, STARTED ve UNKNOWN executor audit kayıtları.

EVIDENCE_EVALUATION yalnız CONFIRMED_SUCCESS, CONFIRMED_REJECTION veya
READ_ONLY_RECONCILIATION_REQUIRED döndürür. Read-only işlem hiçbir kaydı değiştirmez.
Missing, malformed, UNKNOWN, çelişkili veya stale kanıtta üçüncü durum korunur.
APPLY_THEN_UNKNOWN receipt'i kesin kanıt değildir; görünür etki tek başına başarı
sayılmaz. Kaybolmuş kesin provider yanıtı ise güncel ve tutarlıysa doğrulanabilir.

Fingerprint; UNKNOWN receipt, provider receipt/state/source, staged plan/grant,
owner/journal/lease/outbox görüntülerini sürümlü canonical hash'e bağlar. observed_at
sadece okuma zamanıdır; issue/apply her seferinde provider'ı yeniden okur. Okunan
kanıt aynı kalırsa zamanın ilerlemesi yeni etki anlamına gelmez.

## Karar ve yürütme yetkisinden ayrım

ExecutorEvidenceContext.can_evaluate, can_issue_decision, can_apply_decision
varsayılan false ve ayrı fixture kapılarıdır. Issue/apply ayrıca read yetkisini
ister. Eski reconciliation grant'i, worker veya execution yetkisi bunların yerine
geçmez. Ortam yalnız AAA_EXECUTOR_RECONCILIATION_FIXTURE_ONLY'dır.

`AUTHORIZED_DECISION_V1_EXECUTOR_FIXTURE` tenant/subscriber/execution/plan hash,
kanıt fingerprint'i, owner revision, karar türü ve sürümü tam evaluation üzerinden
bağlar; event/attempt/fence de aynı kapsamın içindedir. Kararlar CONFIRM_SUCCESS
ve CONFIRM_REJECTION'dır. Kayıtlı grant UUID+aktör+tam kapsam,1–300s UTC TTL
(varsayılan60) taşır; expiry eşitliği geçersizdir. Caller evaluation'ı güncel
okumayla tekrar karşılaştırılır. Değişen kanıt yeni yetki gerektirir.

Tek kullanımlık grant aynı memory UoW registry'sindedir. Yeniden issue, duplicate
apply, sahte/yanlış kapsam veya eski CAS/fence reddedilir. READ_ONLY sonucundan
hiçbir karar yetkisi üretilemez. Registry imzalı gerçek sistem grant'i değildir.

## Atomik yetkili karar

Apply kanıtı tekrar doğruladıktan sonra tek copy/publish'te:

1. Owner revision/fence+1 ve journal revision+1/EXECUTOR_DECISION_RECORDED.
   Kaynak ve account rezervasyonu korunur; adım kanıtı tüm geçişin tamamı değildir.
2. Adjudicated event ACKED/APPLIED veya CANCELLED/NOT_APPLIED olur; yeni HELD
   karar kontrol kaydı eklenir. Yeni PENDING provider intent'i yoktur.
3. Lease token artırılıp DONE kalır; base/worker/decision audit ve grant tüketimi
   birlikte yayınlanır. Original UNKNOWN receipt değiştirilmez; provenans korunur.

Bu yetkili kayıt da otomatik yürütme izni değildir. Yeni state claim'e kapalıdır;
geç ACK, eski executor retry veya eski UNKNOWN receipt üzerinden overwrite yoktur.
OWNER/JOURNAL/AUDIT/OUTBOX/AUTHORIZATION fault'unda tüm unit candidate geri alınır;
provider belleği hiç değiştirilmez. RAM atomikliği DB/distributed durability kanıtı değildir.

## Yeni hedefli doğrulama

12 yeni test: salt okunur/bound/versioned değerlendirme, missing/malformed/UNKNOWN
source, kesin ret, çelişkili/stale proof, ayrı permission, wrong scope/cached proof,
expiry, atomik karar/no dispatch, concurrent duplicate, CAS/fence/evidence drift ve
5 fault sınırı, üç executor adımı, kopya provider instance reddi. İlk malformed
provider testinin yakaladığı error-path düzeltildi; yalnız başarısız kapsam tekrarlandı.
Socket/PG/SQLite connect testlerde yasak; önceki başarılı suite'ler tekrarlanmadı.

Sonraki tek teknik öncelik: EXECUTOR_DECISION_RECORDED noktasını, eski yetki veya
intent'leri açmadan sürümlü devam/iptal politikasına bağlamak; canlı bağlantı yok.

[Executor kararının devam/iptal politikası](AAA_EXECUTOR_DECISION_POLICY.md), karar
sonrası checkpoint fingerprint'ini taşır ve mevcut kanıt doğrulayıcısını private
snapshot kopyasında yeniden kullanır. İki yetkili geçiş de held ve dispatch'e kapalıdır;
UNKNOWN receipt ile dış etkiler korunur.

## Next-step UNKNOWN yetkili karar entegrasyonu — 2026-11-12

Aynı `ExecutorReconciliationService.issue/apply` ve
`AUTHORIZED_DECISION_V1_EXECUTOR_FIXTURE` kullanılır; ikinci karar deposu veya
servisi yoktur. Next-step yetkisi nested `EVIDENCE_EVALUATION_V1_FIXTURE` içinde
`NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE` sürümünü ve bağımsız execution kimliğini
bağlar. Tenant/subscriber/request/event/attempt, plan/evidence/receipt fingerprint,
owner revizyon/fence, worker token, karar türü ve actor aynı server-side registry
grant'ının parçasıdır. Kopyalanmış/değiştirilmiş grant eşleşmez; yanlış sözleşme
sürümü reddedilir. Süre 1–300 saniye, UTC fixture clock; aynı authorization UUID
tekrar kullanılamaz. Okuma/evaluate yetkisi issue/apply yetkisi değildir.

Issue ve apply öncesinde aynı evaluator güncel bağımsız fake provider kanıtını,
next-step sırasını ve önceki UNKNOWN→yetkili karar→CONTINUE zincirini yeniden
kontrol eder. Eksik/belirsiz kanıt yetkiye dönüşmez. Grant verildikten sonraki
owner/journal/fencing/provider/evidence drift'i tüketimi engeller.

Apply mevcut tek in-memory transaction içinde owner revision+1/fence+1,
journal revision+1, korelasyonlu audit, HELD outbox olayı, lease token+1 ve
registry tüketimini birlikte kaydeder. Yalnız **NEXT_STEP_DECISION_RECORDED**
durumu oluşur. Owner authority LOCAL ve active_request korunur; başarı state'i,
retry, telafi, provider dispatch veya sonraki adım yoktur. UNKNOWN receipt'ler,
önceki evaluation/decision/CONTINUE kayıtları değişmez. İlgili güncel outbox olayının
ACKED/APPLIED veya CANCELLED/NOT_APPLIED etiketi yalnız yetkili kanıt kararıdır;
provider işlemi veya otomatik hesap SUCCESS sonucu değildir. Son ek olay HELD'dir.
Mevcut CONTINUE politikası yalnız önceki EXECUTOR_DECISION_RECORDED durumunu kabul
ettiğinden bu yeni checkpoint için continuation açılmış değildir.

8 yeni hedefli test; iki adımda başarı/ret, eksik/çelişkili/yanlış scope-sürüm
kanıt, yetki/süre, stale CAS/fence/geçmiş, tek kazanan yarış, duplicate karar ve
beş atomik hata sınırı kapsanır. Önceki read-only testinin artık geçersiz olan
“yetkili issue da kapalı” beklentisi, değerlendirme otomatik grant üretmez ve
ayrı issue izni gerekir beklentisine güncellendi; yalnız bu değişen test çalıştı.
Gerçek PostgreSQL, kalıcı audit/AAA veya canlı yetki kabulü değildir.
