# AAA yetkili CONTINUE / CANCEL planı — v1 fixture

2026-11-11 · `app.simulation.aaa_followup`. Yalnız explicit LeasedMemoryOutbox ve
FakeFencedProvider kullanılır; gerçek izin, endpoint, DB veya executor eklenmez.
Önceki başarılı AAA/demo testleri tekrarlanmaz; RADIUS canlı bağlantı yok bilgisi korunur.

## Ayrı kanonik planlar

CONTINUE `AAA_CONTINUE_PLAN_V1_FIXTURE`, CANCEL `AAA_CANCEL_PLAN_V1_FIXTURE`
sözleşmeleridir. Aynı canonical JSON SHA-256 fonksiyonu kullanılır; sürüm/kind
farkı farklı hash üretir. Her plan tenant/store/subscriber/request, önceki root
plan hash, decision ID, karar evidence fingerprint, provider evidence anchor,
owner/operation revision, owner/worker fence ve beklenen DECISION_RECORDED
state'ini bağlar. Checkpoint fingerprint karar kaydı, owner/journal/outbox/lease
snapshot'ını kapsar. Tür ve sürüm uyuşmazlığı reddedilir; hash yetki değildir.

Decision ID mevcut immutable DecisionRecord.authorization_id anahtarıdır.
DecisionRecord'a ayrı provider_evidence_fingerprint eklenmiştir: karar commit'i
öncesinde trusted fake provider'dan okunan evidence'in hash'i. Yeni followup
planı oluşturulurken ve uygulanırken aynı kanıt tekrar okunur. Bu anchor olmadan
eski/eksik checkpoint otomatik yükseltilmez veya yürütülmez; yeniden inceleme gerekir.

Checkpoint kontrolü mevcut kararın grant/tüketim/audit ilişkisini, owner CAS ve
aktif rezervasyonunu, revocation token'ını ve tüm eski outbox sıra/sonuçlarını
doğrular. Değişen provider state/receipt veya tutarsız geçmiş fail-closed reddedilir.
Plan oluşturma salt okunurdur; karar veya devam yetkisi üretmez.

## Fixture authorization

FixtureFollowupAuthority.can_continue ve can_cancel varsayılan false ve bağımsızdır.
İlgili kapı hem issue hem commit'te mevcut tenant/actor scope ile tekrar kontrol
edilir. Eski reconciliation grant'i, worker izni veya diğer kararın yetkisi yeterli
değildir. Context yalnız AAA_FOLLOWUP_FIXTURE_ONLY ortamındadır; gerçek sistemlere
permission grant eden mekanizma yoktur.

AAA_FOLLOWUP_AUTH_V1_FIXTURE UUID'si aynı memory UoW registry'sinde tam plan ve
aktörle kaydedilir. Ömür1–300s, varsayılan60; repository'nin fake UTC clock'u
kullanılır, now>=expiry reddedilir. Checkpoint lease'i zaten iptal edilmiş olduğundan
eski recovery lease yeniden açılmaz; yeni yetki kendi TTL'si ve checkpoint CAS'iyle
sınırlıdır. UUID yeniden verilemez, tüketilmiş yetki ikinci kez uygulanamaz.
Alanı değiştirilmiş, başka tenant/subscriber/plan/decision/evidence kapsamlı veya
registry'de bulunmayan belge kabul edilmez. Registry RAM'dedir, imzalı canlı grant değildir.

## Atomik state geçişleri

| Karar | Geçiş | Dış etki / dispatch |
| --- | --- | --- |
| CONTINUE | DECISION_RECORDED → CONTINUE_HELD | Devam planı kabul edilir; yürütme ayrı inceleme/izin bekler. |
| CANCEL | DECISION_RECORDED → CANCELLED_HELD | Bekleyen plan kapanır; yapılmış provider etkileri geri alınmış sayılmaz. |

İki işlemde de owner revision/fence ve journal revision artar; kaynak ve aktif
request rezervasyonu korunur. Rezervasyonu bırakmak, provider dış etkileri
hakkında ek kanıt ve ayrı plan gerektirir; CANCEL kör yeni geçiş açmaz.

Mevcut ACK/CANCELLED outbox geçmişi değiştirilmez/diriltilmez. Yeni hash'e bağlı
bir **HELD** kontrol olayı append edilir: CONTINUE_EXECUTION_REVIEW veya
CANCEL_NO_ROLLBACK_ASSUMED. HELD teslim edilebilir provider intent'i değildir.
Base audit root request/plan bağını, followup audit ve record yeni plan hash/
parent decision zincirini taşır. Lease DONE kalır ve token yeniden artırılır.

Yetki tüketimi + owner CAS + journal + audit + outbox + lease tek private
copy/publish işlemidir. Concurrent CONTINUE/CANCEL aynı checkpoint'ten yalnız
bir kazanan çıkarır; kaybeden yetki tüketilmez. OWNER/JOURNAL/AUDIT/OUTBOX/
AUTHORIZATION fault'unda tüm candidate atılır. Provider'da hiçbir yazma yapılmaz.

## Yürütme kapısı — bu görevde kapalı

Her iki yeni state `next_event` seviyesinde kapalıdır; yanlışlıkla PENDING olay
oluşsa bile claim ilerleyemez. CONTINUE tek başına dispatch authorization değildir.
Gelecekte bir yürütme planı ancak şu koşulları yeniden doğrulayarak tasarlanabilir:

- Yeni state/owner revision/fence'e bağlı ayrı sürümlü plan ve tek kullanımlık
  açık execution authorization; eski grant, intent veya lease kullanılmaması.
- Güncel tenant/aktör/namespace/NAS/profil/policy ve provider evidence kanıtı;
  stale observation veya UNKNOWN'da read-only reconciliation.
- Kaynak kapalı/fenced olmadan hedefi açmayan adım ön koşulları; tek etkin kaynak.
- Yeni attempt/lease/token, provider idempotency ve plan/event binding'i;
  CAS+journal/audit/outbox sınırının korunması.

Bu listeyi otomatik etkinleştiren flag, dispatch metodu veya canlı bağlantı yoktur.
CANCEL sonrası cleanup/rollback da ayrı kanıtlı ve yetkili plan ister.

## Yeni hedefli kanıt

11 yeni test: kanonik ayrık sürümler/scope, bağımsız izinler, registry/expiry,
CONTINUE hold ve dispatch reddi, etkileri koruyan CANCEL, duplicate, CONTINUE/
CANCEL yarışı,5 partial commit fault'u, revision/fence drift ve evidence değişimi.
Socket/PG/SQLite connect testlerde yasaktır; eski suite'ler çalıştırılmaz.

Sonraki tek teknik öncelik: CONTINUE_HELD için ayrı execution authorization ve
adım ön koşullarını sahte adaptörlerle modellemek; gerçek dispatch açmamak.
