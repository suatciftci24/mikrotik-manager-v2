# Executor decision CONTINUE / CANCEL politikası — v1 fixture

2026-11-11 · `app.simulation.aaa_executor_policy`. Yalnız explicit memory UoW ve
sahte provider. Gerçek auth, bağlantı, provider dispatch, DB veya migration yoktur.
Önceki AAA/demo kabulleri ve UI korunur; eski test suite'leri çalıştırılmaz.

## Ayrı kanonik planlar

EXECUTOR_CONTINUE_POLICY_V1_FIXTURE ve EXECUTOR_CANCEL_POLICY_V1_FIXTURE aynı
kanonik JSON SHA-256 fonksiyonuyla hash üretir. Tür/sürüm farklı hash verir.
Planlar tenant/store/subscriber/request, execution ID, executor decision ID,
önceki execution plan hash, evidence/provider fingerprint, original UNKNOWN
receipt fingerprint, owner/operation revision, owner fence/worker token ve
beklenen EXECUTOR_DECISION_RECORDED state'ine bağlıdır. `automatic_dispatch=false`.

Continue ek olarak SEPARATE_FRESH_EXECUTION_AUTH_REQUIRED politikasını;
Cancel NOT_REVERSED_BY_CANCEL dış etki kuralını taşır. Plan hash'i yetki değildir.

## Mevcut doğrulayıcıyı yeniden kullanma

ExecutorDecisionRecord artık karar sonrası owner/journal/lease/outbox checkpoint
fingerprint'ini taşır. Plan oluşturulurken karar/grant/tüketim/audit bağı,
reservation CAS ve revocation fence bu fingerprint'le doğrulanır. Eski/eksik
checkpoint sessizce yükseltilmez.

Mevcut UNKNOWN doğrulayıcı karar sonrasını eski UNKNOWN state'i olarak kabul
etmez. Bunun için yalnız private bir kopyada karar öncesi owner/journal/lease
metadata'sı ve UNKNOWN outbox event'i yeniden kurulur; sondaki karar audit/control
olayı kopyadan kaldırılır. Gerçek UoW veya provider hiçbir aşamada geri sarılmaz.
Bu görüntü caller tarafından verilmez; kayıtlı karar ve grant'ten türetilir.

Aynı source-pinned EVIDENCE_EVALUATION doğrulayıcısı bu kopyayı **güncel** provider
receipt/state/fence ile karşılaştırır. Yeni değerlendirme, kayıtlı kararın tüm
alanlarıyla (yalnız observed_at hariç) eşleşmelidir. Missing/UNKNOWN/çelişkili veya
stale provider kanıtı READ_ONLY_RECONCILIATION_REQUIRED verir. Plan oluşturma
salt okunurdur; yeni karar veya yürütme yetkisi üretmez.

## Ayrı fixture authorization

ExecutorPolicyAuthority.can_continue ve can_cancel varsayılan false ve ayrıdır.
İlgili kapı issue/apply sırasında tenant/actor ve mevcut PreviewScope ile tekrar
kontrol edilir. Eski continue/cancel, decision veya executor yetkisi yeterli değildir.
Ortam yalnız AAA_EXECUTOR_POLICY_FIXTURE_ONLY; gerçek permission açılmaz.

EXECUTOR_POLICY_AUTH_V1_FIXTURE registry kaydı UUID, aktör ve tam planı bağlar.
Ömür1–300s (varsayılan60), repository fake UTC clock'undan hesaplanır; expiry
anında reddedilir. UUID tekrar verilemez, grant yalnız bir kez tüketilir. Tam
registry eşleşmesi olmadan caller'ın değiştirdiği grant kabul edilmez. Bu RAM
registry'si imzalı veya durable canlı authorization değildir.

## Atomik geçişler ve kapalı yürütme

| Plan | Geçiş | Sonuç |
| --- | --- | --- |
| CONTINUE | EXECUTOR_DECISION_RECORDED → EXECUTOR_CONTINUE_HELD | Ayrı yeni yürütme planı/yetkisi bekler; otomatik dispatch veya sonraki step yoktur. |
| CANCEL | EXECUTOR_DECISION_RECORDED → EXECUTOR_CANCELLED_HELD | Bekleyen yol kapanır; UNKNOWN receipt ve oluşmuş dış etkiler korunur. |

Her ikisi; grant tüketimi, owner revision/fence+1, journal revision+1, base/worker/
policy audit, DONE lease token revocation ve yeni HELD kontrol olayını tek atomic
copy/publish'te kaydeder. Original UNKNOWN accepted receipt'i değiştirilmez.
Kaynak ve aktif owner rezervasyonu korunur; CANCEL provider'ı geri almış veya
account'u yeni kör geçişe açmış sayılmaz. Kesin ret sonrası CONTINUE bile retry
izni değildir.

İki yeni state `next_event` seviyesinde dispatch'e kapalıdır. Yeni PENDING intent,
aktif worker lease veya provider çağrısı üretilmez. Eski iptal edilmiş intent ve
grant'ler diriltilmez. Devam için ayrıca yeni scope/kanıt/revizyon ile sürümlü
execution authorization; dış etkilerin temizliği için ayrı kanıtlı plan gerekir.

CONTINUE/CANCEL yarışı tek checkpoint CAS'inde bir kazanan çıkarır. Kaybeden grant
tüketilmez. OWNER/JOURNAL/AUDIT/OUTBOX/AUTHORIZATION fixture fault'unda owner,
journal, audit, outbox, lease ve authorization consumption birlikte geri alınır.
Provider değişmez. Bu model gerçek DB isolation/crash durability kanıtı değildir.

## Yeni hedefli kanıt

11 yeni test: kanonik ayrık sürüm/scope, ayrı izin, held continue/no dispatch,
iptalde uygulanan etki ve UNKNOWN receipt'in korunması, wrong grant/scope,
expiry/reuse, CONTINUE/CANCEL yarışı, revision/fence drift, missing/changed/
contradictory evidence,5 commit fault'u ve kesin ret sonrası held-only devam.
Socket/PG/SQLite connect yasak; önceki başarılı testler tekrarlanmadı.

Sonraki tek teknik öncelik: EXECUTOR_CONTINUE_HELD için ayrı yeni-adım execution
authorization bağlantısını modellemek; otomatik veya gerçek dispatch açmamak.
