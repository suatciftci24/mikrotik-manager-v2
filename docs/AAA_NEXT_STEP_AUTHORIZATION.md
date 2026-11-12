# Executor sonraki adım yetkisi — v1 fixture

`aaa_next_step.NextStepExecutionService`, mevcut FixtureExecutionService'in
izin, süre, tek kullanım registry'si ve atomik staging işlemini yeniden kullanır.
Yeni canlı yetki, API, bağlantı veya ayrı grant altyapısı yoktur.

NEXT_STEP_EXECUTION_PLAN_V1_FIXTURE kanonik JSON SHA-256 kapsamı: tenant,
store/subscriber/request, previous execution ID, decision ID, CONTINUE policy ID
ve hash, evidence/provider fingerprint, owner/operation revision, owner fence,
worker token, next step ID/sırası, önceki event/sonuç, beklenen
EXECUTOR_CONTINUE_HELD durumu ve sözleşme sürümü. Next step ID policy, execution,
sıra ve kanıttan deterministik türetilir; hash yetki değildir.

NEXT_STEP_EXECUTION_AUTHORIZATION_V1_FIXTURE tam planı, aktörü, UUID ve süreyi
bağlar. Mevcut fixture execution can_issue/can_stage izinleri varsayılan kapalıdır.
Ömür 1–300 saniye (varsayılan 60); registry eşleşmesi, tenant/actor, expiry ve
tek kullanım issue/stage sınırlarında doğrulanır. Eski policy yetkisi yeterli değildir.

CONTINUE checkpoint/grant/tüketim/audit/outbox doğrulanır. Yalnız private kopyada
önceki karar checkpoint'i kurularak mevcut policy/UNKNOWN kanıt doğrulayıcısı
güncel, kaynağı sabitlenmiş sahte provider'a karşı tekrar kullanılır. Gerçek memory
state geri sarılmaz. Yetkili CONFIRM_SUCCESS ve bağımsız kesin SUCCESS zorunludur;
UNKNOWN, ret, eksik/çelişkili/değişmiş kanıt READ_ONLY_RECONCILIATION_REQUIRED
olarak reddedilir. Ret otomatik retry veya adım atlama izni değildir.

Yalnız hemen sonraki adım mümkündür: FENCE_LOCAL → ENABLE_RADIUS veya
ENABLE_RADIUS → COMMIT_OWNER_CAS. Son adımdan sonra successor yoktur. Önceki
olayın ACKED/APPLIED olması, provider'ın kaynak çiti/hedef hazırlığı, güncel owner
CAS/fencing ve journal/outbox tutarlılığı zorunludur. CANCEL kapalı kalır.

Grant tüketimi, owner revision/fence, journal revision, audit, lease token
revocation ve HELD outbox kontrol olayı aynı memory transaction içinde değişir.
Sonuç yalnız NEXT_STEP_EXECUTION_STAGED; kayıt da aynı durumu taşır. PENDING
olay, aktif lease veya provider dispatch üretilmez; normal worker claim reddedilir.
Önceki UNKNOWN receipt ve karar/policy geçmişi korunur. Yarışta tek CAS kazananı
vardır; kaybeden grant tüketilmez. Beş fault sınırında kısmi değişiklik kalmaz.
Bu RAM modeli gerçek DB transaction veya crash durability kanıtı değildir.

10 yeni hedefli test: kanonik kapsam, ortak izin/registry, atomik held staging,
adım sırası, CANCEL/ret, yanlış kapsam/kanıt, expiry/reuse/version, stale CAS/fence
ve değişen provider, eşzamanlı girişimler ve beş commit fault'u. Önceki suite'ler
yeniden çalıştırılmadı. Sonraki öncelik: staged next-step için ayrı kontrollü
fixture executor/receipt kabulü; gerçek dispatch kapalı kalmalı.
