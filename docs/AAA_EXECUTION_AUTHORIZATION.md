# AAA execution authorization — v1 fixture

2026-11-11 · `EXECUTION_AUTHORIZATION_V1_FIXTURE` ve
`AAA_EXECUTION_STEP_V1_FIXTURE`. Yalnız `app.simulation.aaa_execution`.
Explicit LeasedMemoryOutbox/FakeFencedProvider dışında adaptör kabul edilmez.
Gerçek permission, API, worker, provider dispatch veya ağ bağlantısı eklenmez.

## CONTINUE ile yürütme yetkisi ayrımı

CONTINUE_HELD tek başına yürütme yetkisi değildir. FixtureExecutionAuthority'nin
can_issue ve can_stage kapıları varsayılan false ve önceki continue/cancel,
reconciliation veya worker izinlerinden ayrıdır. Tenant/actor scope ile hem
issue hem stage anında kontrol edilir. Ortam yalnız AAA_EXECUTION_FIXTURE_ONLY.

Plan şu alanları kanonik JSON SHA-256 ile bağlar: sözleşme sürümü,
tenant/store/subscriber/request, continue plan hash/followup ID, decision ID,
karar evidence fingerprint ve provider evidence anchor, owner/operation revision,
owner fence/worker token, yalnız izin verilen adım ve sıra, önceki event ID/
APPLIED sonucu, beklenen CONTINUE_HELD durumu ve held checkpoint fingerprint.
`provider_dispatch=false` değişmez. Hash gerçek yetki tokenı değildir.

FollowupRecord'a held checkpoint fingerprint eklendi: followup commit sonundaki
owner/journal/lease/outbox görüntüsü. Eksik eski fixture kaydı sessizce yürütülebilir
sayılmaz. Continue grant'in tüketilmiş ve journal/audit ile tutarlı olduğu, önceki
kararın provider anchor'ı ve güncel provider görüntüsü tekrar doğrulanır.

## Ön koşullar ve adım sırası

Yalnız mevcut provider receipt prefix'inin tamamı kesin APPLIED ise sıradaki adım
planlanır. NOT_APPLIED bilinen sonuç olsa da bu ileri-yürütme sözleşmesi otomatik
retry planı değildir; ayrı inceleme gerekir. Missing/stale/UNKNOWN/çelişkili
kanıtta READ_ONLY_RECONCILIATION_REQUIRED hatasıyla held durum korunur; yetki
üretilmez/tüketilmez, otomatik telafi veya tekrar gönderim yapılmaz.

| Önceki kesin provider adımı | Tek izin verilen sonraki aşama |
| --- | --- |
| Kapalı hedef hazırlandı | FENCE_LOCAL |
| LOCAL devre dışı/fenced | ENABLE_RADIUS |
| RADIUS etkin, LOCAL kapalı/fenced | COMMIT_OWNER_CAS (yerel işlem) |

Owner reservation revision/fence ve journal revision eşleşmelidir. Eski worker
lease'i DONE/revoked kalır; token ve held snapshot güncel olmalıdır. Son provider
fence kanıtı aynı root request ve kayıtlı provider receipt'ine bağlı olmalıdır;
provider state değişmişse ilerlenmez. Yeni owner/worker fencing sayacı eski
provider gözlem tokenıyla karıştırılmaz: staging yeni sayaç üretir, dış provider
bu yeni token'ı henüz kabul etmiş sayılmaz.

Outbox'ta önceki adım ACKED/APPLIED, eski iptal edilmiş intent'ler CANCELLED ve
continue kontrol olayı HELD olmalıdır. Sıra atlama, CANCELLED_HELD veya bozulmuş
journal/outbox/audit kabul edilmez. Planlama salt okunurdur, yetki vermez.

## Tek kullanımlık yetki ve atomik staging

Yetki registry'si aynı memory UoW'dedir; UUID, tam plan, aktör ve UTC süreyle
bağlıdır. Ömür1–300s (varsayılan60), FakeLeaseClock kaynağından hesaplanır;
now>=expiry geçersizdir. Registry eşleşmesi olmadan caller belgesi kabul edilmez.
Aynı UUID tekrar verilemez, tüketilmiş grant tekrar kullanılamaz. Terminal eski
lease geri açılmaz; bu yetki yalnız staging içindir ve kendi TTL'si vardır.

Stage commit'i tüm ön koşulları güncel provider okumasıyla yeniden doğrular.
Tek copy/publish sınırında grant tüketimi, owner revision/fence+1, journal
revision+1/FIXTURE_EXECUTION_STAGED, base/worker/execution audit, lease token
revocation ve yeni HELD `FIXTURE_STAGE:<izinli_adım>` kontrol kaydı oluşur.
Kaynak ve aktif account rezervasyonu korunur. Eski intent diriltilmez; yeni
PENDING provider komutu veya aktif worker lease'i üretilmez.

FIXTURE_EXECUTION_STAGED `next_event` seviyesinde kapalıdır. Bu aşama gerçek
adımın APPLIED olduğu, owner source flip veya provider etki receipt'i değildir.
Provider execute/ACK/NACK çağrılmaz; provider RAM'i bile değişmez. Gelecekteki
kontrollü fake executor yeni step/event/attempt/fence doğrulaması gerektirir.

OWNER/JOURNAL/AUDIT/OUTBOX/AUTHORIZATION fault'unda grant ve bütün candidate
değişiklikleri geri alınır. Aynı checkpoint'e iki grant'in yarışında tek CAS
kazananı vardır; kaybeden grant tüketilmez. Gerçek DB atomikliği/crash durability
veya FreeRADIUS fencing özelliği bu RAM modelinden türetilmez.

## Yeni hedefli kanıt ve sonraki adım

11 yeni test: kapsam/sürüm, ayrı izin, yanlış step/hash/evidence, expiry/reuse,
atomik held staging, üç ileri aşamanın doğru sırası, CANCEL/NOT_APPLIED reddi,
CAS/fence/outbox drift, UNKNOWN,5 fault sınırı ve eşzamanlı tek CAS kazananı.
Socket/PG/SQLite connect yasak; önceki başarılı AAA suite'leri tekrarlanmadı.

Sonraki tek teknik öncelik: staged tek adımı ayrı kontrollü sahte executor ve
receipt/UNKNOWN sonuç sözleşmesiyle tamamlamak; gerçek dispatch açmamak.
