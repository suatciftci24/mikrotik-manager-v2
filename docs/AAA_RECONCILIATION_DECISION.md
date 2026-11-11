# AAA uzlaştırma kararı ve atomik commit — v1 fixture

2026-11-11 · `AAA_RECONCILIATION_AUTH_V1_FIXTURE`.
`app.simulation.aaa_decision` yalnız explicit LeasedMemoryOutbox ve
FakeFencedProvider kabul eder. Gerçek yetki/permission, endpoint, signing key,
DB, worker veya provider bağlantısı eklenmedi. RADIUS/demo UI değişmedi.

## Kanıt ile karar yetkisi ayrımı

`reconcile_unknown` hâlâ salt okunur kanıt değerlendirmesidir. APPLIED veya
NOT_APPLIED sınıflandırması karar yetkisi vermez. FixtureDecisionAuthority ayrı
can_issue/can_commit kapılarını taşır; ikisi varsayılan false ve ortam yalnız
AAA_DECISION_FIXTURE_ONLY'dır. Worker can_deliver/can_compensate izinleri bu
kapıların yerine geçmez. Mevcut tenant/actor PreviewScope ve güncel recovery
lease kontrolleri ayrıca zorunludur. Bu model iki kişi onayı şartı koymaz;
aynı fixture aktöründe bile iki ayrı capability kontrol edilir.

İki karar vardır: ACCEPT_APPLIED_EVIDENCE ve ACCEPT_NOT_APPLIED_EVIDENCE.
İkisi de yalnız kanıtlanan **adımı kaydeder ve geçişi bekletir**. Otomatik
resume, source flip, provider komutu veya geri dönüş izni anlamına gelmez.

## Açık kapsamlı tek kullanımlık yetki

Yetki kayıtlı UUID, sözleşme sürümü, tenant/store/subscriber/request, aktör,
plan hash, event UUID, owner/operation revision, owner fence, worker token/
worker/attempt ve evidence fingerprint'e bağlıdır. Fingerprint; doğrudan
provider'dan okunan evidence, journal, owner ve tüm outbox snapshot'ının mevcut
canonical JSON hash fonksiyonuyla birleşimidir. Tarihsel dispatch kanıtı da
her değerlendirmede yeniden kontrol edilir.

Ömür1–300 saniye, varsayılan60; repository FakeLeaseClock UTC'si kullanılır.
expires_at geçerli lease sonunu aşamaz; now>=expires_at reddedilir. Renewal
mevcut yetkinin ömrünü uzatmaz. Renew audit'i tek başına provider kanıtını
değiştirmez; owner/journal/outbox/provider değişimi eski fingerprint'i geçersiz kılar.

Yetki aynı memory UoW'de registry'ye kaydedilir. Caller'ın yeniden oluşturduğu
veya alanları değişmiş belge, registry kaydıyla tam eşleşmeden kabul edilmez.
UUID yeniden verilemez; kullanılan yetki tekrar uygulanamaz. Aynı event için
iki ayrı yetkiden biri commit olursa diğeri revision/fence/lease kontrolünde
reddedilir. Süreç kaybında registry yoksa yetki geçersizdir; durable veya imzalı
gerçek sistem grant'i olduğu iddia edilmez.

## Tek atomik karar işlemi

Commit sabit UoW→provider lock sırasıyla güncel yetki, scope, recovery lease,
provider evidence, account CAS ve fingerprint'i yeniden doğrular. Kanıt halen
tam/tutarlı değilse veya karar türüyle uyuşmuyorsa hiçbir kayıt değişmez.

Aynı private copy/publish sınırında:

1. Owner revision+1 ve owner fence+1; yetkili kaynak LOCAL ve aktif request
   rezervasyonu korunur. Provider adım kanıtı tamamlanmış account geçişi değildir.
2. Journal revision+1, yeni terminal **DECISION_RECORDED** kontrol noktasına geçer;
   owner revision/fence bağı güncellenir. Eski journal kayıtları migrate edilmez.
3. UNKNOWN event, APPLIED kararında ACKED/APPLIED, NOT_APPLIED kararında
   CANCELLED/NOT_APPLIED olur. Önceki ACK geçmişi korunur; kalan PENDING
   intent'ler CANCELLED olur. Yeni provider intent veya otomatik bildirim eklenmez.
4. Recovery lease DONE olur, worker token artırılarak eski handle iptal edilir.
5. Immutable karar kaydı, base audit, worker audit ve yetki tüketim kaydı birlikte
   oluşur. Yetki ancak başarılı yayınla tek kullanılmış sayılır.

DECISION_RECORDED doğrudan `next_event` seviyesinde de dispatch'e kapalıdır;
sonradan PENDING intent sızsa bile yeni claim ilerleyemez. Producer replay yalnız
bu tarihsel durumu döndürür. Owner rezervasyonu başka request'in kör geçişini
engeller. Devam etmek ayrıca sürümlü ve açık yetkili bir plan gerektirir.

OWNER/JOURNAL/AUDIT/OUTBOX/AUTHORIZATION fixture fault'larında tüm copy atılır;
owner, journal, audit, outbox, lease ve grant tüketimi birlikte geri alınır.
Provider'da hiç değişiklik yapılmaz. Bu lock/copy modeli PostgreSQL transaction,
crash durability veya dağıtık atomiklik kanıtı değildir.

## Yeni hedefli doğrulama

13 yeni test: kanıt/karar yetkisi ayrımı; tüm grant kapsamları/fixture sürümü;
registry/expiry; applied ve not-applied atomik karar; CAS/journal drift;
5 fault sınırı; eşzamanlı duplicate karar; aynı event'e ikinci yetki; stale lease;
henüz geçerli grant ile yeni fencing token; değişmiş ama tutarlı evidence;
eksik/çelişkili kanıt ve yanlışlıkla PENDING terminal intent reddi.
Socket/PG/SQLite connect yasak; önceki başarılı AAA suite'leri tekrarlanmadı.

Sonraki tek teknik öncelik: DECISION_RECORDED rezervasyonundan devam/iptal için
ayrı yetkili, sürümlü plan sözleşmesi; önceki yetkiyi veya iptal edilmiş intent'i
yeniden kullanmamak. Gerçek bağlantı ve gerçek yetkilendirme yine kapalıdır.
