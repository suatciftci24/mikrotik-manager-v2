# AAA PostgreSQL kalıcılık tasarımı — karar taslağı v1

2026-11-12 · İncelenen HEAD: 52a0e40. **PASS: kaynak temelli tasarım**;
**BLOCKED: uygulama, migration ve gerçek katalog kabulü**. Bu belge DDL veya
çalıştırılabilir migration değildir. DB bağlantısı açılmadı; mevcut gerçek
katalog, roller, satır sayıları veya servis sağlığı doğrulanmış sayılmaz.
Güvenlik değerlendirmesi: [AAA-POSTGRESQL-SECURITY-REVIEW.md](AAA-POSTGRESQL-SECURITY-REVIEW.md).

## 1. Kaynakta mevcut mimari

| Kaynak | Doğrulanan kod beklentisi | AAA için sınır |
| --- | --- | --- |
| `backend/app/core/database.py` | SQLAlchemy SessionLocal; pool_pre_ping/hide_parameters, connect/statement/lock timeout; import bağlantı açmaz | Repository/UoW enjekte edilir; import/startup migration olmaz |
| `001_initial_v2.sql`, models/subscriptions.py | subscriber_accounts→customer/router/plan FK; LOCAL/RADIUS tek otorite CHECK ve router+username unique | Tenant, owner revision/fence/active_request yok; workspace ile aynı depo değil |
| models/operations.py | subscriber_events ve audit_logs; UUID PK, actor FK, UTC zaman/JSON | Teknik AAA kanıtı veya outbox kendiliğinden mevcut değil |
| `002` demo storage | v2_demo.schema_state marker; subscribers/events/requests | Legacy sentetik kaynak; domain veya workspace ile birleştirilmez |
| `004` demo identity | v2_demo.users/user_audit | Domain panel_users ile eşdeğer aktör deposu değil |
| `006/007/008` | registry; v2_router_workspace.records/audit; v2_subscriber_workspace.subscribers/events | 008 owner revision ve LOCAL/RADIUS source mevcut; tenant/fence/AAA lock yok |
| services/subscriber_operations.py | FOR UPDATE, tekrar fingerprint okuma, account+event transaction; UUID receipt mevcut event changes._management içinde | Günlük yönetim receipt'i ile AAA multi-step ledger aynı şey değil |
| simulation/aaa_atomic/worker/executor/decision/policy/preparation | Canonical frozen plan, revision/fence, TTL, lease/attempt, receipt/evidence, atomik checkpoint | RLock/deepcopy/clock ve id(provider) kalıcı kanıt olamaz |
| simulation/aaa_journal.py | Disposable SQLite journal prototype | Tam AAA PG adaptörü değil; ikinci production ledger olarak kullanılmaz |

Bu ayrım [CENTRAL_AAA_CONTRACTS.md](CENTRAL_AAA_CONTRACTS.md) ve
[AAA-E2E-ACCEPTANCE.md](AAA-E2E-ACCEPTANCE.md) sınırlarını korur. Kaynaktaki SQL
varlığı migration'ın gerçek DB'ye uygulandığını kanıtlamaz.

## 2. Kalıcılık hedefi ve veri sahipliği

İlk **önerilen** PG uygulaması yalnız yeni disposable V2.6 acceptance DB'sindeki
PERSISTENT_WORKSPACE sentetik owner'ı kapsasın. Mevcut ofis DB'si hedef değildir.
008 subscriber aynı hesap sahibi kalır; yeni accounts/subscribers/owner kopyası
yok. LEGACY_DEMO salt okunur kalır; string ID'si domain UUID'sine çevrilmez.
Domain subscriber_accounts için ileride ayrı owner adapter ve gerçek FK kararı
verilmeden aynı tabloya polymorphic subscriber FK konulmaz.

Workspace subscriber'a gelecekte eklenmesi gereken metadata: tenant_id UUID,
aaa_fence bigint>=0, aaa_active_operation UUID nullable; mevcut revision CAS
sayacı ve source otoritesi korunur. UNIQUE(tenant_id,id) tenant composite FK
hedefidir. Tenant değeri/membership sahibi bugün yok: izole fixture için pinned
UUID yapılandırması; gerçek tenancy için ayrıca tasarım şart. İstemciden gelen
tenant, owner veya aktör beyanı yetki değildir. Mevcut satırlara keyfi tenant
atayan otomatik backfill yapılmaz. Yazma yapan bütün owner servisleri AAA active
operation kilidine uymadan bu alanların eklenmesi güvenli entegrasyon sayılmaz.

## 3. Önerilen minimal fiziksel model

Mantıksal şema adı `v2_aaa` öneridir. Yalnız dört yeni teknik tablo; ayrı plans,
receipts, evidences, decisions, preparations, policies veya leases tabloları
önerilmez. Aşağıdaki alanlar migration öncesi inceleme şartıyla belirlenmiştir.
Tüm zamanlar timestamptz, revizyon/token bigint; JSON yalnız allowlist metadata.

### operations — idempotency ve journal head

- tenant_id UUID + operation_id UUID composite PK; request UUID=operation_id.
- subscriber_id varchar(64), workspace owner'a composite FK(tenant_id,id)
  RESTRICT; actor_id mevcut v2_demo.users ID tipiyle uyumlu FK RESTRICT önerisi.
  Actor silme yerine deaktivasyon; tip ve audit saklama kararı doğrulanmalı.
- correlation_id UUID; contract_version, canonicalization_version, immutable
  plan JSONB ve plan_hash/payload_fingerprint (32-byte digest), ordered steps.
  Fixture v1 byte canonicalization'ı yeniden kullanılır; DB jsonb metninden
  hash hesaplanmaz. UTC/date/Unicode/field-order kuralları sürümlenir.
- expected_account_revision, source/target mapping/namespace/policy revisions;
  state, operation_revision>0, owner_revision>=0, owner_fence>=0,
  current_action_id UUID nullable, reconciliation_required bool,
  created_at/updated_at. Farklı revizyonların anlamı birleştirilmez.
- UNIQUE(tenant_id,subscriber_id,expected_account_revision): aynı kaynak
  revizyonuna farklı UUID rezervasyonunu reddeder. Reddedilmiş/UNKNOWN kayıt
  silinerek anahtar yeniden kullanılamaz. Gelecek meşru retry ayrı yetkili
  işlem ve güncel owner revision üzerinden olmalı.
- Bir hesapta tek açık operasyon için partial UNIQUE(tenant_id,subscriber_id)
  WHERE closed_at IS NULL önerilir. Held/UNKNOWN closed değildir. closed_at
  state'le tutarlı CHECK ve kapanış yetkisi olmadan değişmez.

### actions — plan/authorization/karar/checkpoint kayıtları

- PK(tenant_id,action_id UUID); FK(tenant_id,operation_id)→operations RESTRICT.
  UNIQUE(tenant_id,operation_id,action_id) alt bağlantıların composite hedefidir.
- kind enum/CHECK: EXECUTION, DECISION, CONTINUE, CANCEL, PREPARATION,
  PREPARED_EXECUTION; ayrı authorization UUID=action_id. Execution türlerinde
  execution_id=action_id; diğerlerinde subject_execution_id ilişkili execution'a
  FK(tenant,operation,action). previous_action_id ve preparation_id aynı
  operation composite FK'si. Döngü/yön/sıra hizmet doğrulamasında reddedilir.
- actor_id, immutable versioned plan JSONB/hash, expected_state, step_identity,
  sequence, next_step_id, decision_type, expected owner/operation revision,
  owner_fence/worker_token; evidence/receipt/checkpoint fingerprint, immutable
  evaluation JSONB (source/execution/event/attempt/observed_at/sürüm dahil).
- issued_at/expires_at, consumed_at nullable, action_revision, result_state ve
  result revision/checkpoint. expires_at>issued_at ve politika üst TTL sınırı;
  issued/consumed aktör ve yetki-policy revizyonu kaydedilir.
- Yetki yalnız sunucu registry satırından doğrulanır; JSON nesnesi bearer token
  değildir. SINGLE USE consumed_at IS NULL CAS ile; kullanılan satır silinmez.
- UNIQUE(tenant,operation,next_step_id,kind) hazırlık/çalıştırma kayıtlarında
  meşru PREPARATION ve PREPARED_EXECUTION'ı ayırır. Aynı aşama iki kez oluşmaz.
  İptal/expiry sonrası yeniden issue politikası ayrı karar; ilk sürüm aynı
  kimliği overwrite etmez, kendiliğinden yeni capability üretmez.

### attempts — dispatch sınırı ve receipt/UNKNOWN kanıtı

- PK(tenant_id,attempt_id UUID); FK(tenant,operation,execution_action_id)→actions;
  UNIQUE(tenant,execution_action_id): ilk sürüm execution başına tek attempt.
- event_id UUID, plan hash/step identity, worker_id, owner_revision/fence,
  fencing_token, expires_at; state CLAIMED/IN_FLIGHT/RESPONDED/UNKNOWN/ACCEPTED,
  started_at, completed_at, attempt_revision. UUID başka execution'da kullanılamaz.
- local_received_receipt JSONB/hash/outcome, UNKNOWN accepted receipt JSONB/hash,
  independent_observation JSONB/hash, provider identity/version/correlation,
  provider observed_at, verification status. UNKNOWN receipt immutable;
  sonraki read-only gözlem ayrı alana/yeniden değerlendirme action'ına kaydedilir.
- Kesin receipt veya değişen observation overwrite edilmez. Tek definitive
  observation çelişirse yeni değerlendirme action'ı ve reconciliation blokajı;
  önceki kanıt audit'te korunur. Sınırsız JSON kanıt listesi yerine actions.kind
  için EVIDENCE_REVIEW gerektiğinde aynı sürümlü kayıt modeli kullanılır.
- UNIQUE(tenant,event_id) dispatch subject event'ine bağlar. Attempt, outbox'ın
  composite (tenant,operation,event_id) FK'sini taşır. Bağımsız provider receipt
  kimliği varsa provider-instance+external-receipt-id unique; aynı kanıt farklı
  execution'a taşınamaz. Eksik kimlik doğrulanamadı olarak kalır.

### outbox — HELD/PENDING intent ve lease aynı satırda

- PK(tenant_id,event_id UUID); FK(tenant,operation_id)→operations; subject_action
  composite FK; sequence, step, version, plan_hash, correlation_id,
  status HELD/PENDING/CLAIMED/IN_FLIGHT/ACKED/CANCELLED/UNKNOWN, result,
  event_revision, created_at. UNIQUE(tenant,operation,sequence).
- lease_owner, attempt_id, fencing_token, lease_expires_at, dispatch_started_at;
  unique attempt_id nullable scoped tenant; attempt link eklenirken FK sırası
  transaction içinde çözülür (outbox→attempt geri FK zorunlu değil).
- Lease ayrı tablodaki ikinci gerçeklik olmaz. İndeksler: (tenant,status,
  lease_expires_at,sequence), PENDING ve expired CLAIMED için partial indeks;
  tenant+operation+sequence ve evidence/execution lookup'ları.
- HELD olayları worker kuyruğuna girmez. Authorization issue olayı otomatik
  PENDING üretmez. Her state değişiminin meşru sürümlü geçişi hizmette doğrulanır;
  CHECK tek başına geçiş grafiğini/kanıt sırasını ispatlamaz.

### Mevcut audit'i yeniden kullanma

İlk workspace hedefinde 008 `events` aynı transaction'da append-only teknik
AAA olaylarını taşır: mevcut id UUID string, actor, subscriber, UTC ISO zaman,
owner revision; operation kısa `AAA` (varchar20 sınırı), ayrıntılı sürümlü kind
ve operation/action/event/attempt/correlation, previous→new state, revision,
fingerprints `changes._aaa` allowlist içinde. operation_type'a uzun state adı
basılmaz. Silme/güncelleme yetkisi verilmez; tenant_id ve güvenilir operation
referansı/FK eklenmesi migration tasarımına dahildir. (tenant,operation,
operation_revision,event_kind) unique olay anahtarı önerilir; aynı revision'da
ISSUED gibi farklı action olayları için action_id de anahtara dahil edilir.
Domain hedefinde mevcut audit_logs seçilir; iki depoya aynı teknik olay
mükerrer yazılmaz. Kullanıcı geçmişi görünürlüğü mevcut event API'sinden
projeksiyonla korunur; frontend'e gizli teknik metadata dökülmez.

## 4. Transaction, lock ve concurrency sınırları

1. Sunucunun güvenilir actor/tenant/yetki bağlamı; pinned DB kimlik kontrolü.
2. Lock sırası tüm yazıcılarda owner→operation→action→outbox→attempt. Aynı
   türde UUID sırası; deadlock'ta yalnız dış etki başlamamış DB transaction'ı
   bounded retry edilir. Network çağrısı açık DB transaction içinde yapılmaz.
3. READ COMMITTED + row lock + beklenen revision/fence CAS + unique constraint
   başlangıç önerisidir. Namespace gibi çok satırlı predicate kontrolleri için
   composite unique yeterli değilse SERIALIZABLE veya namespace lock ayrıca
   gerekir; Redis/process lock DB güvenlik sınırı sayılmaz.
4. Idempotency: tenant/request unique INSERT; çatışmada rollback/savepoint
   sonrası mevcut immutable fingerprint ve actor/scope kontrol edilir. Aynı
   istek tarihsel receipt döner, farklı payload reddedilir. Anahtar secrecy
   sağlamaz; result GET her seferinde güncel yetki ister.
5. Authorization consumption, owner revision/fence CAS, action result,
   operation journal head, outbox, audit aynı Session.begin içinde commit olur.
   Tek bir rowcount=0 veya audit failure tüm transaction'ı geri alır. Owner
   authority ancak kanıtlı COMMIT_OWNER_CAS adımında değişir; karar kayıtları
   yalnız metadata checkpoint, source flip değildir.
6. DB clock authority: TTL/lease zamanı row lock alındıktan sonra taze DB
   clock'tan değerlendirilir; transaction başı zamanı uzun lock beklemesinde
   stale olabilir. Client clock yetki değildir. expires_at anında ret.
7. Her yeni owner lock epoch'unda monoton fence; her lease generation'ında
   monoton token. Pair owner_fence/token attempt/receipt'e yazılır. Provider
   gerçekten token reddetmiyorsa DB fencing tek başına dış etkileri fence etmez.
8. `SKIP LOCKED` dispatch kuyruğunda iş paylaşımı içindir; owner CAS veya
   authorization doğrulamasının yerine geçmez. Lock sırasını ters çevirmemek
   için candidate event ID seçimi sonrası owner-first transaction ile yeniden
   kontrol gerekir; seçilen ID henüz claim sayılmaz.

## 5. Dispatch ve crash recovery matrisi

| Çökme noktası | Kalıcı kanıt | Recovery kuralı |
| --- | --- | --- |
| Claim transaction commit öncesi | Claim yok | Provider çağrısı yasak; transaction rollback |
| CLAIMED commit sonrası, IN_FLIGHT öncesi | Lease var, dispatch intent yok | Expired claim taze yetki/CAS ve yeni token ile ancak politika izin verirse alınabilir; otomatik execution değil |
| IN_FLIGHT commit öncesi | Dispatch başlamamalı | Worker commit başarısını görmeden network çağırmaz |
| IN_FLIGHT commit sonrası, send öncesi | Dispatch olabilir | Send olmadı varsayılmaz; UNKNOWN/reconciliation, kör redelivery yok |
| Send sonrası timeout/crash | Dispatch outcome belirsiz | UNKNOWN immutable; bağımsız provider lookup/kanıt ve yetkili karar gerekir |
| Kesin cevap sonrası receipt transaction öncesi | Provider değişmiş olabilir | Crash'te UNKNOWN; in-memory cevap kalıcılık kanıtı değildir |
| Receipt+CAS/audit transaction hata | Yerel sonuç commit değil | Owner SUCCESS yok; IN_FLIGHT ve provider kanıtı korunur; resend yok |
| Commit başarılı fakat client cevabı kayıp | Committed receipt var | Aynı UUID scoped lookup; ikinci dispatch/consume yok |
| UNKNOWN sonrası geç cevap | Orijinal UNKNOWN var | Receipt overwrite yok; ayrı independent observation/evaluation; otomatik SUCCESS yok |

IN_FLIGHT durumunu commit etmek ile gerçek send arasında atomiklik yoktur;
transactional outbox tam bir distributed exactly-once garantisi sağlamaz.
Provider'a erişmeden gönderilmediği ispatlanamayan her yol fail-closed UNKNOWN.
Lease expiry yalnız işi kimin gözlemleyeceğini belirler; eski provider çağrısını
iptal etmez. Recovery worker dispatch yetkisi kazanmaz. Restore/snapshot sonrası
token regression riski varken yazma adapter'i kapalı kalır; provider epoch ve
namespace uzlaştırılmadan eski tokenlarla resume edilmez.

## 6. UNKNOWN, karar, CONTINUE/CANCEL ve hazırlık

UNKNOWN ve prepared/authorized-held/decision checkpoint'leri kapalı worker
state'leridir. Evaluator yalnız read-only snapshot ve pinned bağımsız provider
kanıtı okur. `id(provider)` yerine environment/provider-instance/config sürümü,
kimlik doğrulanmış receipt/correlation ve zaman/sıra kanıtı gerekir. UNKNOWN'dan
üretilmiş outcome beyanı kabul edilmez. Salt okunur değerlendirme audit/queue
mutasyonu yapmaz; kanıtı saklamak ayrı açık yetkili metadata transaction'ıdır.

DECISION issue/apply ayrı; intent TTL, tek kullanım, scope/actor ve immutable
evaluation fingerprint'ine bağlı. Apply fresh evidence/CAS/fence'i yeniden
kontrol eder ve NEXT_STEP_DECISION_RECORDED üretir. CONTINUE/CANCEL ayrıca
single-use action; yalnız HELD sonuç. PREPARATION ve PREPARED_EXECUTION ayrı
action tipleri ve exact contract; preparation tek başına execution izni değildir.
Önceki UNKNOWN ve tüm actions/events korunur. Telafi ayrı yetki ve güncel CAS
ister; DB restore veya kör source flip değildir.

## 7. Uygulama kapıları ve kabul planı

İlk uygulama önceliği: mevcut UoW arayüzüne uygun PostgreSQL metadata repository
adapter'i ve **yalnız disposable acceptance DB** için transaction/constraint
kabul tasarımı. Migration oluşturma/uygulama ve DB erişimi bu belge görevinin
kapsamı değildir; ayrı açık izin gerekir. Önce tenant/actor FK/owner metadata ve
state/TTL/retention kararları kesinleşmeli; günlük owner yazıcıları da kilit
sözleşmesine katılmalı. Ardından isolated concurrency, çift consume, deadlock,
crash/commit ambiguity, UNKNOWN restore/recovery, rol/RLS ve audit atomicity
kabulü yapılır. Canlı provider bu kabulden sonra bile ayrı karardır.
