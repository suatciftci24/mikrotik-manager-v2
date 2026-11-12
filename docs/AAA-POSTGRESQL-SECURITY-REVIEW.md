# AAA PostgreSQL güvenlik değerlendirmesi — taslak v1

2026-11-12 · Kaynak tabanı 52a0e40. **PASS: belge incelemesi**.
**BLOCKED: gerçek DB/provider güvenlik kabulü**; katalog/rol/grant/cluster veya
servis sağlığı sorgulanmadı. Ürün kodu/migration değiştirilmedi.
Veri modeli ve crash matrisi: [AAA-POSTGRESQL-DESIGN.md](AAA-POSTGRESQL-DESIGN.md).

## Kaynak envanteri ve güven sınırları

- core/config.py yalnız PostgreSQL+loopback, DB adı ve 5432 dışı port kontrolü
  yapar. Bu, localhost'taki başka proje/DB'yi ayırmaz; mevcut varsayılan profili
  yeni AAA repository için otomatik fallback yapmak kabul edilemez.
- core/v26_acceptance.py profil/host/port/root, environment ve router access
  flag'lerini birlikte sınırlar. API 127.0.0.1:18996; DB 127.0.0.1:55433,
  mikrotik_v26_acceptance/v26_acceptance; private root
  /tmp/mikrotik-v26-acceptance. Bunlar **kod beklentisi**, çalışan ortam kanıtı değil.
- dev.sh yerel demo DB'si 127.0.0.1:55432/mikrotik_manager_v2'dır. .local altındaki
  mevcut cluster ve gerçek demo kayıtları bu AAA persistence denemelerinin
  hedefi olmamalıdır. Bu görevde bağlantı veya socket denemesi yapılmadı.
- demo_repair.verify_database ve demo storage doğrulaması marker/owned cluster
  dizini/sentetik veri/yetki kapılarını gösterir; izinleri tek tek sınama önemlidir.
  Bir marker veya port tek başına güvenilir DB kimliği değildir. Marker'ın
  mevcut katalogda bulunduğu bu incelemeyle doğrulanmış sayılmaz.
- In-memory LeasedMemoryOutbox/FakeFencedProvider RLock/deepcopy transaction,
  mantıksal clock ve id(provider) kullanır. Süreç restartı, DB rol sınırı veya
  gerçek kriptografik provider kimliği bu modelin kanıtı değildir. SQLite
  prototype de PG durability/locking/RLS kabulüne dönüştürülemez.

## Ortamların kesin ayrımı

| Ortam | Bu tasarımda kullanım | Zorunlu ayırıcılar / ret |
| --- | --- | --- |
| Yeni disposable V2.6 acceptance | Gelecekte yalnız onaylı metadata adapter kabulü | Exact profile, env, API/DB host+port+name+role, marker, owned PGDATA/cluster kimliği; boş fixture sahibi ve disposable çalışma kökü |
| Ofis V2 local demo | Korunur, test hedefi değildir | 55432 mevcut DB; mevcut aboneler/kullanıcılar/audit ve .env aynen korunur |
| V2.5 pilot | Kapsam dışı, erişim yok | DSN/rol/secret/sunucu/servis/unit/backend import mirası alınmaz |
| V1 ve üretim/VDS | Kapsam dışı, erişim yok | Her DB/provider/migration/restart/deploy için ayrı hedefe özgü izin; bu belge izin değildir |

Network loopback yeterli izolasyon değildir. Future PG preflight, bağlantı izni
verilmiş ayrı görevde current_database/current_user/server port, owned PGDATA,
expected marker/schema version ve cluster identity'yi allowlist ile karşılaştırıp
yanlış hedefte **ilk yazımdan önce** durmalı. Mismatched identity'de otomatik
CREATE/GRANT/restore/parola reset veya alternatif DSN araması yok. Test fixture
dış hedef egress'i kapalı; V1/V2.5 adresleri test girdisi olarak dahi tüketilmez.
Bu görevde live health endpoint'i çağrılmadı; kullanıcı yalnız belge incelemesi
ve gerçek sistemlere dokunmama sınırı verdi. Canlı sağlık PASS iddiası yoktur.

## Risk matrisi

| Öncelik | Risk | Gerekli kontrol | Bu görevde kanıt |
| --- | --- | --- | --- |
| Kritik | Yanlış DB/profile veya default DSN fallback | Exact identity guard, owned cluster, profile allowlist, fail-closed | Mevcut guard kodu incelendi; katalog kabulü yok |
| Kritik | Tenant scope IDOR, yanlış subscriber FK | Server context; composite FK/unique; yetkili tenant/account sorgusu ve RLS | Tenant entity/membership bugün eksik; migration kapısı |
| Kritik | Çift consume/CAS yarışı | owner-first lock sırası, revision/fence rowcount, unique, tek transaction audit/outbox | Memory kabulü var; PG concurrency kabulü yok |
| Kritik | IN_FLIGHT crash sonrası double dispatch | Send öncesi durable intent; belirsizlikte UNKNOWN; read-only provider uzlaştırma | Tasarım crash matrisi; gerçek provider kabulü yok |
| Kritik | Eski worker dış etki üretir | Monoton owner epoch/token ve provider'ın token doğrulaması | DB token tek başına yetmez; provider desteği karar bekliyor |
| Yüksek | UNKNOWN'dan sahte SUCCESS/kanıt türetme | Immutable UNKNOWN; pinned bağımsız receipt/observation, source/version/correlation | Fake source fingerprint canlı imza değildir |
| Yüksek | Owner üzerinde günlük yönetim AAA kilidini atlar | Tüm owner writers aynı active_operation/CAS sözleşmesine katılır | Mevcut günlük yönetim bu entegrasyon için henüz adapte edilmedi |
| Yüksek | Yetki TTL/replay/audit kaybı | DB clock, consumed CAS, server registry, fingerprint ve atomic audit | TTL/retention/DB fault kabulü bekliyor |
| Yüksek | Backup/restore fence regression | Restore sonrası dispatch disabled; bağımsız provider epoch uzlaştırma | Test edilmedi; otomatik resume yasak |
| Yüksek | JSON/trace/backuplarda secret | Strict allowlist/schema/size limit, redacted exception, private backup rolü | Gerçek secret okunmadı; gelecekteki adapter için kapı |
| Yüksek | Audit sahibinin tahrifatı | Runtime'a UPDATE/DELETE yok; ayrı migration owner, retention/export | DB grants ve denetim kabulü yapılmadı |
| Orta | Lease starvation/deadlock/clock drift | Lock sıra standardı, kısa txn, bounded DB retry, DB expiry, izlenebilir stuck state | Tasarım; PG yük/crash testi bekler |

## Yetkilendirme ve DB rol taslağı

Ayrı migration sahibi runtime rolü olamaz. Runtime DDL/superuser/CREATEROLE/
BYPASSRLS yetkisi taşımaz; search_path sabitlenir ve sorgular şema-qualified
kullanılır. Schema PUBLIC CREATE ve gereksiz default grant'ler kapatılmalı;
aktarım sırasında otomatik GRANT yok. İşçi rolü yalnız gerekli metadata
claim/receipt işlemlerine, evaluator salt okunur role veya salt okunur transaction'a
sahip olmalı. Provider credential okuma yetkisi evaluator'a verilmez.

Server request context'ten tenant/actor/membership çözülür. Rol grant'i tenant
ve konu kapsamını genişletmez. RLS, composite FK ve uygulama kontrolü birlikte
kullanılmalı; pool connection'da tenant context yalnız SET LOCAL ve transaction
ömürlü olmalı, önceki kullanıcıdan sızmamalı. FORCE RLS değerlendirilir; owner/
superuser bypass sınırı ayrı test edilir. Gerçek tenancy tablosu yokken RLS var
varsayılmaz veya istemci tenant header'ı güvenilir sayılmaz.

Capabilities ayrı: view/evaluate, issue decision, consume decision, issue policy,
consume policy, prepare, authorize execution, claim/dispatch/receipt record.
Mevcut ADMIN veya okuma izni otomatik AAA yazma izni değildir. Expired/used veya
aktör pasifleşmiş yetki tüketilemez; apply anında güncel policy/membership tekrar
kontrol edilir. Tarihsel aktör/scope/policy sürümü audit'te korunur. Ledger GET
bile authorization ister; fingerprint veya UUID gizli bearer token değildir.

## Integrity ve kanıt kaynağı

Immutable plan/authorization/receipt/evaluation alanları mutable state kolonlarından
ayrılmalı. Runtime bu immutable alanları güncelleyememeli (kolon grant/denetimli
service transaction sınırı; gerekirse migration-reviewed trigger). FK/unique/CHECK
ile type/scope/sequence/revision ilişkileri sertleştirilir; JSON hash eşitliği
izin, güncellik veya provider doğruluğu değildir. JSON boyutu/sürümü/anahtarları
sınırlandırılır, canonical v1 byte'ı korunur. Canonicalization değişimi ayrı sürüm
ve explicit plan reissue gerektirir; kayıtlar sessizce yeniden hash'lenmez.

Owner active_operation bağlantısı aynı tenant/subscriber'ın operation'ına
composite FK ile bağlı olmalı; bunun için operations üzerinde
UNIQUE(tenant_id,subscriber_id,operation_id) gerekir. İlk owner reservation'da
operation insert ve owner link aynı transaction'da yapılır; nullable başlangıç
ve lock sırası tasarlanmalı. Parent→child cycle nedeniyle deferrable FK kararı
migration incelemesinde açık verilmelidir; constraint'i kapatmak çözüm değildir.

Local UNKNOWN immutable; bağımsız observation başka origin/provenance alanındadır.
Fixture provider_side receipt hash'i trusted memory içinde provenance modelidir;
gerçek adaptörde authenticated provider identity, endpoint/config sürümü,
provider receipt ID, request/attempt/fence bağlantısı ve anlamlı monotonic
kanıt zamanı gerekir. Aynı ağ bağlantısından dönmüş ham başarı metni veya
client tarafından post edilmiş receipt bağımsız kanıt değildir. Kanıt source'u
belirlenemiyorsa evaluator yalnız READ_ONLY_RECONCILIATION_REQUIRED döner.

## Crash, timeout, DB hatası ve restore kontrolleri

- Statement/lock timeout başarısız transaction'dır; provider uygulanmadı demek
  değildir. Dispatch sonrasında connection/commit cevabı kaybında owner SUCCESS
  döndürülmez; scoped idempotency lookup ve bağımsız gözlem gerekir.
- Claim/IN_FLIGHT/receipt transaction commit'lerinin her sınırı ayrı durability
  kabulü ister. Provider çağrısı DB transaction/row lock boyunca tutulmaz.
- DB serialization/deadlock retry dış etkiden önce ve sınırlı olabilir; provider
  send'i bir transaction retry fonksiyonuna konulmaz. IN_FLIGHT timeout/redelivery
  yasak; lease expiry tek başına yeni dispatch izni vermez.
- Audit/outbox insert hatası owner/action değişimini geri alır. Provider state'i
  DB rollback ile geri alınmış varsayılmaz. Recovery history silmez/overwrite
  etmez, sessiz cleanup ile UNKNOWN çözmez.
- Backup içerikleri Git'e/loga girmez. Restore her iki ortamın yedeği/farkı ve
  ayrı izin olmadan yapılmaz. Eski dispatch/fence/token restore edilmişse canlı
  yazma kapalı; provider epoch ve aktif talepler uzlaştırılmadan devam yok.
- Retention: aktif/UNKNOWN operasyon, tek kullanımlık yetki ve idempotency
  tombstone purge edilmez. Audit ve receipt saklama süreleri veri minimizasyonu
  ile kararlaştırılmalı; UUID yeniden kullanımını açan otomatik cleanup yok.

## Ayrı onaya bırakılan kararlar ve ilk uygulama

1. Tek owner hedefi PERSISTENT_WORKSPACE ve tenant/actor sahipliği; gerçek domain
   adapter'i, source authority ve mevcut secret CHECK ile uyum ayrı tasarım.
2. Exact PG profile/cluster/marker ve migration versiyon/checksum mekanizması;
   schema/rol/RLS/immutable alan/retention politikaları.
3. Canonicalization ve trusted provider kimliği, fencing/idempotency desteği,
   independent observation, retry/compensation ve restore epoch sözleşmesi.
4. Yalnız disposable acceptance DB için hedefli PG repository/transaction kabulü:
   çift issue/consume, owner CAS, cross-tenant FK/RLS, lease expiry, deadlock,
   crash/commit ambiguity, receipt/audit/outbox fault ve recovery testleri.

**Sıradaki tek uygulama önceliği:** onaylı sözleşmeye bağlı, dış provider dispatch'i
kapalı PostgreSQL metadata repository/UoW adapter'i için izole kabul hazırlığı.
Bu görevin belge onayı DB erişimi/migration veya canlı provider izni değildir.

## Ortak owner sözleşmesi prototipi — 2026-11-12

[Owner-writer matrisi](AAA-OWNER-WRITER-CONTRACT.md) gerçek kaynak yazıcılarını ve
uyumsuzlukları listeler. DI metadata repository artık boolean authorize sonucunu
kabul etmez: sürümlü tenant/aktif actor/subscriber/capability OwnershipGrant gerekir.
Reserve/issue/consume missing owner metadata ve active_operation kapsamını kontrol
eder; consume ortak monoton metadata transition ve tenant+revision+fence+source+
active_operation SQL CAS predicate'lerini kullanır. Günlük yazıcıların aynı sözleşmeye
katılma sınırı tanımlandı; çalışan servislerin davranışı değiştirilmedi.

**BLOCKED devam eder:** runtime daily writers, seed/repair ve şema hâlâ AAA fence/
active lock taşımaz; güvenilir membership resolver, FK/RLS/rol ve gerçek PostgreSQL
concurrency kabulü yok. Grant modelini oluşturabilmek veya callback'te sabit grant
döndürmek yetki kanıtı değildir. Python sözleşmesi raw SQL/DBA bypass'ını tek başına
engellemez. Fake test sonuçları yalnız DI/prototip mantığını doğrular.
