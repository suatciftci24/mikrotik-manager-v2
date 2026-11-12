# Next-step fixture executor ve receipt — v1

`FixtureExecutor` mevcut claim/run/accept/timeout motoruyla hem ilk staging'i hem
NEXT_STEP_EXECUTION_STAGED durumunu işler. Ayrı executor, worker, registry veya
canlı adaptör eklenmez. AAA_EXECUTOR_RECEIPT_V1_FIXTURE ve ReceiptAcceptance
modeli yeniden kullanılır; execution/event/attempt UUID, plan hash, adım, owner
revision/fence, worker token ve provider fingerprint aynı receipt'te bağlıdır.

Claim ve sahte effect öncesinde next-step yetki/record/sürüm, tüketilmiş staging
izni, audit/outbox checkpoint ve güncel CAS/fencing doğrulanır. Yalnız private
snapshot'ta staging öncesi metadata kurularak mevcut NextStepExecutionService
plan doğrulayıcısı tekrar kullanılır. Karar/CONTINUE/kanıt zinciri **güncel** ve
kaynağı sabitlenmiş fake provider'a karşı eşleşmelidir. Gerçek state geri sarılmaz.
Grant staging sırasında bir kez tüketilmiştir; executor receipt kabulü aynı
execution attempt'ini ACCEPTED yaparak tüketir, grant'i tekrar açmaz.

| Sonuç | Journal | Etki |
| --- | --- | --- |
| SUCCESS | FIXTURE_STEP_SUCCEEDED | ENABLE_RADIUS yalnız sahte state'i değiştirir; son COMMIT_OWNER_CAS yalnız kesin başarıda memory owner'ı RADIUS yapar. |
| REJECTED | FIXTURE_STEP_REJECTED | Kaynak rezervasyonu ve önceki etkiler korunur; başarı veya rollback varsayılmaz. |
| UNKNOWN | FIXTURE_STEP_UNKNOWN | READ_ONLY_RECONCILIATION_REQUIRED; retry, telafi veya sonraki adım yoktur. |

Receipt kabulü; attempt tüketimi, owner CAS, journal, audit, outbox terminal
sonucu ve lease operation revision'ını tek copy/publish transaction'da kaydeder.
OWNER/JOURNAL/AUDIT/OUTBOX/AUTHORIZATION fault'unda tümü geri alınır; önceden
oluşmuş sahte provider etkisi geri alınmış sayılmaz. Aynı receipt güncel checkpoint
ve fencing ile idempotenttir; içerik, worker, attempt, revizyon, event veya token
uyuşmazlığı reddedilir. Provider fencing drift'i geç ACK ve duplicate'ı da kapatır.

AFTER_DISPATCH/AFTER_EFFECT çökmesi ya da kayıp yanıtta coordinator timeout aynı
receipt modeliyle UNKNOWN kaydeder. Sonradan gelen SUCCESS bu kaydı değiştiremez.
Önceki UNKNOWN receipt, evaluation, decision ve CONTINUE kayıtları değişmez kalır.

Yeni UNKNOWN kabulüne NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE eklenir: tenant,
subscriber/request, current/previous execution, decision, next step, event/attempt,
plan/continue hash, önceki evidence ve yeni provider/receipt fingerprint,
owner revision/fence/token, plan ve evaluation sözleşme sürümleri. Referans
karar veya yürütme yetkisi değildir. `unknown_evidence` ile mevcut salt okunur
kanıt paketinde sunulur. Mevcut evaluator bu yeni lineage için henüz karar açmaz:
strict type kapısı READ_ONLY döner. Sonraki iş, bu referansı aynı kanıt doğrulama
sürecinde desteklemek; bu görev otomatik veya yetkili karar uygulaması eklemez.

13 yeni hedefli test; ENABLE/COMMIT, ret, UNKNOWN, crash/lost response, geçmişin
korunması, idempotency, yanlış kapsam/içerik, CAS/fencing/provider kaynağı, iki
concurrency sınırı ve beş atomik fault kapsandı. Socket/PG/SQLite connect testte
yasaktır. Önceki başarılı suite'ler, build ve HTTP kabulü tekrarlanmadı. Gerçek
DB, veri, servis, router veya RADIUS erişimi yoktur; model RAM fixture kapsamındadır.
