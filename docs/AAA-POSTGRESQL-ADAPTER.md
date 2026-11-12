# AAA PostgreSQL metadata repository / UoW prototipi

2026-11-12 · **PARTIAL: izole adapter sözleşmesi hazır; uygulama entegrasyonu BLOCKED.**
`backend/app/repositories/aaa_metadata.py` SQLAlchemy Core ifadeleri üretir.
Engine/config/SessionLocal import etmez, bağlantı/DDL/create_all/migration veya
provider çağrısı yapmaz. Mevcut API/startup ve in-memory zincire bağlanmadı.

## Dependency injection ve yeniden kullanım

PostgresMetadataUow dört zorunlu dependency alır: session factory, target_guard,
authorize ve validate_contract. Varsayılan yoktur. Guard, transaction başlamışken
exact disposable hedef/şema/owner-writer uyumunu doğrulamalıdır. authorize her
repository çağrısında güvenilir tenant/actor/subscriber membership'ini yeniden
kontrol etmelidir. Eksik scope veya guard false ise ret. Bu görevde gerçek
kimlik doğrulayan guard yazılmadı: DB erişimi yasaktır. Lambda true yalnız fake
test içindir, gerçek uygulama entegrasyonuna uygun değildir.

validate_contract mevcut strict/sürümlü AAA authorization/evidence/receipt
sözleşmelerini yeniden doğrulayan güvenilir callback olmalı; payload'ın scope,
operation, plan, CAS/fence/lease, TTL, sıra ve geçişini kontrol etmeli ve secret
alanlarını reddetmelidir. Repository yeni state machine yaratmaz; OperationFixture,
OwnerFixture, OutboxFixture ve canonical_hash kullanır. Callback'in generic JSON
kabul etmesi güvenli değildir. Testte kullanılan FIXTURE_TEST_ONLY payload gerçek
capability değildir. Adaptör kendi başına evaluator veya authorization servisi
olarak sunulamaz; bu callback'in production bağlayıcısı henüz yazılmadı.

## Metadata projeksiyonları ve kapsam

`operations/actions/attempts/outbox` önerilen dört metadata tablo projeksiyonudur;
owner ve audit mevcut `v2_subscriber_workspace.subscribers/events` projeksiyonlarıdır.
İkinci owner/audit/state-machine deposu yok. Table tanımları installed şema değildir;
PK dışı FK/unique/index/rol/RLS ve tam kolon tasarımı henüz migration'a dönüştürülmedi.
Owner tenant_id/aaa_fence/aaa_active_operation ve event tenant_id kaynak şemada yok.
Bu projeksiyonlar doğrudan metadata.create_all ile kullanılmamalıdır.

- reserve: owner-first row lock ve operation lock; scoped immutable request
  fingerprint eşitse replay, farklı içerik/aktör/subscriber ret. İlk kayıt için
  owner revision/fence ve active_operation zaten doğrulanmış/ayrılmış olmalı.
  İlk owner rezervasyonunu bu prototip yapmaz. Yeni owner oluşturmaz/taşımaz.
- issue: explicit scope/contract callback, owner→operation lock; aynı operation
  sahibi, server clock ve 1–300 saniyelik TTL; immutable action fingerprint.
  Duplicate PK exception transaction'ı geri alır; overwrite yok.
- consume: tekrar scope/contract doğrulaması, owner→operation→action lock;
  lock sonrası DB clock_timestamp, unused/TTL/fingerprint/scope ve operation CAS.
  Owner revision/fence rowcount1, single-use action consume, journal CAS,
  HELD outbox ve mevcut event audit tek transaction'da. Token owner fence'den
  ayrı lease_token parametresidir; doğru token/kanıt ilişkisi callback yükümlülüğü.
  Yalnız aynı authority ve aynı active_operation tutulabilir; gerçek source flip
  veya provider dispatch bu prototipte yoktur.
- Optional AttemptMetadata yalnız UNKNOWN checkpoint ekleyebilir; execution/event
  payload bağı ve callback receipt/evidence doğrulaması gerekir. INSERT-only;
  orijinal UNKNOWN güncellenmez. Diğer crash işaretleri typed modelde tanımlı,
  fakat gerçek claim/IN_FLIGHT/lease-recovery yazıcı metotları henüz uygulanmadı.
- Başarılı context çıkışı commit, exception rollback. consume/SQL hatası
  yakalanıp yutulsa bile repository poisoned olur; context commit'e izin vermez.
  Commit cevabı kaybında başarı döndürme/retry mekanizması eklenmedi; transaction
  exception dışarı taşar. Gerçek recovery/receipt lookup ayrı entegrasyon kapısıdır.

## Owner yazıcı denetimi — gerçek blokaj

services/subscriber_center.py create/edit/renewal ve
services/subscriber_operations.py change revision/FOR UPDATE kontrol eder;
AAA active_operation veya monoton aaa_fence kontrolü yapmaz. 008 model/SQL'de bu
kolonlar yoktur. v2_demo legacy kayıtları ve domain SubscriberAccount ayrı sahiplerdir;
PK/aktör/tenant eşdeğeri varsayılamaz. Hepsini değiştirmek mevcut görevin ötesinde
şema ve uygulama entegrasyonu gerektirir. Bu yüzden varsayılan runtime'a adaptör
bağlanmadı; target_guard owner-writer uyumunu kanıtlamadan true döndüremez.

## Fake kabul ve kanıtın sınırı

8 yeni fake-session testi PASS: atomic commit/replay; beş yazım sınırında rollback
ve caught exception poison; concurrent CAS tek kazanan; stale fence/expired/
wrong tenant-actor; duplicate idempotency/different payload; UNKNOWN immutable ve
attempt insert fault; target/contract guard reddi. Son UNKNOWN callback bağı
sıkılaştırılınca yalnız etkilenen test tekrarlandı. Test SQLAlchemy Core ifadelerinin
predicate/value'larını yorumlayan kilitli, deep-copy fake session kullanır;
UoW kapandıktan sonra repository kullanımı reddedilir; PostgreSQL dialect SQL
offline derleme de sınandı. success cevabı önceden sıralanmış mock değildir. Socket/SQLite/psycopg girişleri yasak.

**Bu testler PostgreSQL semantiğini doğrulamaz:** FK/unique/index/RLS, MVCC,
row-level locking, SERIALIZABLE/deadlock, server clock/commit durability, crash/
restart/network ambiguity ve provider outbox exactly-once sınırları test edilmedi.
Fake global lock gerçek PostgreSQL eşzamanlılığı değildir. Önceki AAA suite
tekrarlanmadı; in-memory executor/UoW'uyla drop-in uyumluluk iddiası yoktur.

## Sonraki tek öncelik

Şema/tenant-actor ve tüm owner-writer kilit sözleşmesi için kapsamı belirlenmiş
entegrasyon planını kesinleştirmek. Ardından ayrı açık onayla yalnız disposable
DB'de migration/identity/grant ve PG repository kabulü gerekir. Bu görevde kod
üretimi DB erişimi/migration yetkisi değildir; gerçek provider dispatch kapalıdır.
