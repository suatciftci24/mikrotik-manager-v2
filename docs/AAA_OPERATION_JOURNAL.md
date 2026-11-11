# Merkezi AAA işlem günlüğü — izole prototip v1

2026-11-11. Bu çalışma gerçek AAA yürütücüsü veya PostgreSQL entegrasyonu değildir.

## Kök eksiklik ve sınır

Bellek simülasyonundaki geçici receipt süreç kapanınca kaybolur; iki çağıranın
aynı revizyonu eşzamanlı rezervasyonu engellenmez. Mevcut subscriber_operations
fingerprint+event transaction yaklaşımı örnek alınarak ayrı **işlem metadata**
günlüğü hazırlanmıştır. İkinci abone deposu oluşturulmaz. Hesap/credential/plan
verisi saklanmaz; yalnız mevcut hesabın referansı ve rezervasyon revizyonu tutulur.

`app.simulation.aaa_journal.IsolatedJournal` yalnız çağıranın açıkça sağladığı
SQLite bağlantısıyla çalışır. Import, constructor veya uygulama başlangıcında
şema oluşturmaz; initialize yalnız disposable test şeması içindir. Uygulama
engine/config/env/secret veya adapter import edilmez. HTTP endpoint, job,
RADIUS yazma yolu ve otomatik telafi yoktur. Üretimde bu adaptör kullanılmamalı.

## Sözleşme ve atomiklik

- JournalRequest v1: tenant, UUID istek anahtarı, correlation UUID, aktör,
  mevcut frozen AaaSnapshot ve hedef RADIUS. Strict/extra-forbid sözleşme;
  parola/attribute dump kabul etmez. Snapshot saklanmaz, canonical JSON SHA-256
  fingerprint'e katılır. Tenant/aktör/korelasyon/hedef de fingerprint içindedir.
- PK `(tenant, request_id)`. Aynı içerik tekrarında son kaydedilmiş durum ve
  işlem revizyonu döner; yeni operation/event oluşmaz. Farklı içerik veya
  aktörde IDEMPOTENCY_CONFLICT. Yetki kontrolü replay/history öncesinde yapılır.
- `UNIQUE(tenant, store, account, account_revision)` aynı kaynak revizyonunu
  farklı UUID ile yeniden rezerve etmeyi engeller. FAILED dahil rezervasyon
  silinmez; yeni girişim için kaynağın yeniden değerlendirilmesi gerekir.
- İşlem revizyonu 1'den başlar; account revizyonundan ayrıdır. Her advance
  beklenen işlem revizyonu ve izinli edge ister. BEGIN IMMEDIATE + CAS UPDATE
  + event INSERT tek transaction'dır. Audit insert hatasında ikisi rollback olur.
- Event PK tenant/request/revision, FK operation; aktör/correlation ve aware UTC
  zamanı içerir. Eventler bu arayüzde append-only; ham bağlantıyı elinde tutan
  kişi için değiştirilemez/tamper-proof audit garantisi verilmez.
- Günlük rezervasyonu kaynak hesabın güncel revizyonunu kanıtlamaz. İleride
  account sahibiyle atomik kaynak CAS/revizyon doğrulaması şarttır. Burada
  kaynak deposu değiştirilmez; sahte account CAS başarısı üretilmez.

## Durum makinesi ve geri dönüş

```
RESERVED -> PLANNED | FAILED
PLANNED -> MODELED | FAILED | UNCERTAIN
MODELED -> COMPENSATING | RECONCILIATION
UNCERTAIN -> RECONCILIATION
COMPENSATING -> COMPENSATED | RECONCILIATION
```

FAILED/COMPENSATED/RECONCILIATION terminaldir. MODELED yalnız sentetik planın
model sonucudur; APPLIED/live success değildir. Timeout UNCERTAIN olarak kalır;
tekrar reserve onu başarıya çeviremez. COMPENSATING/COMPENSATED yalnız plan
metadata'sıdır: gerçek source flip, target delete veya rollback çalıştırmaz.
Telafi çatışması RECONCILIATION ile durur. Gerçek telafi öncesi mevcut account,
NAS/profil, hedef sonuç ve revizyon kanıtları yeniden okunmalı; ayrı yazma
onayı, tek otorite, monoton account revizyonu ve ilişkili audit zorunludur.

## İzole kabul

8 yeni test: replay/changed fingerprint; tenant/yetki reddi; aynı account
revizyonuna ikinci UUID; stale CAS + telafi; timeout/uzlaştırma; failed retry;
audit insert fault ile atomik rollback; dosya kapat/aç kalıcılığı + iki bağımsız
bağlantıda eşzamanlı CAS (bir kazanan). Tüm veriler sabit sentetik fixture'dır.
Mevcut 16 sözleşme/simülasyon regresyonu da geçti. Frontend değişmedi;
TypeScript/build ve görsel kabul tekrarlanmadı. Gerçek DB/socket denenmedi.

## PostgreSQL şema/migration taslağı — uygulanmadı

Ayrı onay sonrası mevcut modüler monolit içinde operation journal repository
ve transaction sınırı tasarlanmalı; mevcut abone deposu sahibi korunmalı.
Önerilen operations: tenant UUID/text (nihai tenancy kararı bekler), request UUID,
fingerprint SHA-256, actor FK/reference, store+account reference, expected account
revision, correlation UUID, state enum/CHECK ve operation revision bigint>0.
PK tenant/request; unique tenant/store/account/expected_revision; fingerprint
format CHECK; actor/tenant/store referanslarının gerçek sahipleri netleşmeli.
Events: tenant/request/operation_revision PK, operation composite FK RESTRICT,
state, timestamptz, correlation, actor; append-only en az yetkili DB rolü.
Gelecekte sunucu UTC zamanı kullanılmalı; test clock istemci yetkisi değildir.

DDL veya migration dosyası eklenmedi/uygulanmadı. PostgreSQL lock/isolation,
restart/crash recovery, fsync, rol/grant/RLS, tenant FK ve migration checksum
kabulü yapılmadı. SQLite testi bunların kanıtı değildir. Retention/tombstone
politikası anahtar tekrar kullanımını engellemeli; otomatik purge yok.
Dış işlem için ayrı outbox/lease/fencing/provider-idempotency tasarımı,
kanıtlı uzlaştırma ve audit saklama politikası gerekir; distributed exactly-once
garantisi yok. Okuma scope'u AAA yazma izni değildir. Canlı AAA, migration,
PostgreSQL yazımı ve telafi için ayrı açık hedefe özgü onay gerekir.

## Demo panel okuma sınırı — 2026-11-11

`GET /api/v1/aaa-demo/preview?scenario=PLAN|COMPENSATION|RECONCILIATION`
mevcut oturum doğrulamasını kullanır. Yalnız sabit `demo-sub-aaa-memory`
fixture'ını ve her çağrıda kapatılan `:memory:` journal'ı sunar. Seçili abone
kimliği, tenant veya proof almaz; mevcut PostgreSQL/audit/credential okumaz.
Detaydaki İşlemler bölümünde isteğe bağlı açılır; güncel hesap kaynağı ayrı,
örnek geçmiş ve korelasyon ayrı gösterilir. Sabit örnek aktör/tarih kullanıcı
veya güncel olay olarak sunulmaz. GET sonucu kalıcı receipt, canlı hazırlık veya
yazma yetkisi değildir; `live_ready=false`, `external_writes=false` korunur.
