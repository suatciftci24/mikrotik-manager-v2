# AAA owner-writer entegrasyon planı — v1

2026-11-12 · Kaynak HEAD 48df672. **PASS: entegrasyon planı; BLOCKED: uygulama.**
[Membership resolver](AAA-MEMBERSHIP-RESOLVER-PLAN.md),
[mevcut sözleşme matrisi](AAA-OWNER-WRITER-CONTRACT.md),
[PG tasarım](AAA-POSTGRESQL-DESIGN.md), [fixture kabul](AAA-E2E-ACCEPTANCE.md).
Bu belge ürün kodu, migration veya gerçek DB kabulü değildir.

## Yazıcı ve çağrı zinciri matrisi

| Akış / kaynak fonksiyonları | Mevcut identity/transaction/lock/revision | Audit/outbox | Entegrasyon gereği |
| --- | --- | --- | --- |
| PPPoE/Hotspot workspace create/edit: api/v1/subscriber_center.py create/update → services/subscriber_center.py SubscriberWorkspace.save | current_admin/mutator aktörü; parent router FOR UPDATE, account FOR UPDATE varsa; expected_revision, Session.begin | events CREATE/UPDATE; UUID receipt | Resolver; create için router+tenant membership ve unique identity, yok owner'a lock uygulanmış sayılmaz. İlk owner revision/fence ve tenant tek transaction'da atanmalı |
| Workspace paket/profil/durum/aç-duraklat: subscriber_center.py manage → subscriber_operations.py execute/change | source/router/revision kontrolü; sorted parent'lar ve owner FOR UPDATE; fields değişimi +revision | events _management UUID/fingerprint ve receipt; outbox yok | Aktif AAA varsa tüm mutation ret; ortak CAS ve fence+1; aynı request replay scoped lookup |
| Workspace uzatma: subscriber_center.py renew → SubscriberWorkspace.renew; manage EXTEND/EXPIRE → SubscriberOperationsService.change | expected source/router/revision/date, Türkiye günü kontrolü; Session.begin | events RENEWAL veya EXTEND/EXPIRE | Tarih iş kuralı korunur; günlük lock/revision/fence predicate'e katılır; paket ve uzatma farklı bypass yolu bırakmaz |
| QuickActions/toplu workspace: subscriber_center.py manage döngüsü → execute/change/failed | Her öğe ayrı transaction/sonuç; batch atomik değil | Per-item success/failure receipt | Her öğe taze membership/owner scope; tek shared tenant varsayımı yok; tek UUID tekrar uygulanmaz. Tüm batch'i tek transaction'a sessizce dönüştürme |
| Legacy PPPoE create/change: api/v1/subscribers.py create_demo_subscriber/change_demo_subscriber → adapters/demo_subscriptions.py create_subscriber/change_subscriber/_persist | current_demo_account_mutator/router izni; engine.begin, _item(lock=True), revision; legacy store | v2_demo.events/requests | Workspace'e ID/tenant türetme yok; ilk aşama AAA dışında. Aktif AAA owner'a geçişe yol açacak legacy mapping ayrıca engellenmeli |
| Legacy tarih/QuickActions: subscribers.py change_demo_expiry/quick_batch → change_expiry; services/demo_subscriptions.py memory karşılığı | actor/router izinleri, per-item request/revision/transaction | events/requests; memory history ayrı | Aynı tenant resolver adapter'i olmadan PG AAA hedefi olamaz. Memory demo üretim yazıcısı sayılmaz |
| Failure audit: subscriber_operations.py failed/audit; subscriber_center.py audit | Ayrı failure transaction, owner bazen yok | Mevcut workspace events; aynı request replay | Scope izinli değilse subscriber varlığını sızdırmayan denial; owner başarısı gibi revision+fence ilerletilmez. Failure audit owner lock bypass yapmaz |
| Seed/repair: demo_storage.py initialize_demo/seed_examples ve subscriber payload upgrade yolları; demo_repair.py main; local_demo_database.py ensure_database | engine.begin ve marker/cluster guard; bazı payload SQL update'larında revision CAS yok | Başlangıç events/requests, marker | AAA aktif epoch varken maintenance kapısı kapalı; seed hiçbir mevcut owner'ı sessizce overwrite etmez. Runtime ile eşzamanlı repair yok |
| AAA metadata: repositories/aaa_metadata.py reserve/issue/consume + aaa_owner_contract | DI grant; row lock/CAS/fence, same-session transaction | operations/actions/attempts/outbox + workspace events | Güvenilir resolver, tam schema/constraints ve initial reservation eksik. Bool grant yasak; mevcut prototype runtime'a bağlı değil |
| Memory owner başlangıcı/settle/telafi: simulation/aaa_atomic.py MemoryAtomicUnit | PreviewScope ve RLock/copy, owner revision/fence | memory journal/audit/outbox | Domain geçişleri yeniden kullanılacak, PG adaptör diye etiketlenmez |
| Worker/recovery: aaa_worker.py claim/renew/dispatch/ack/nack/retry/compensate | WorkerContext/attempt/lease/token expiry ve transaction | worker audit/outbox | PG lease ve monotonic fencing; UNKNOWN/IN_FLIGHT expiry resend değil; actor yerine dar worker principal |
| Authorization/preparation: aaa_execution.py issue/stage; aaa_next_step.py; aaa_next_step_preparation.py; aaa_prepared_authorization.py consume | TTL, registry single-use, private checkpoint ve owner CAS | HELD journal/audit/outbox | Metadata kaydı provider capability değildir; taze membership ve owner revision bağlanmalı |
| Execution: aaa_executor.py claim/run/accept/timeout | Fenced fake provider/attempt; owner yalnız accept/timeout transaction'ında değişir | Receipt, UNKNOWN reference, audit/outbox | Network provider sınırı açık; post-send rollback uygulanmadı anlamına gelmez. Source commit ayrı kanıtlı owner transition |
| Decision/policy: aaa_decision.py commit; aaa_followup.py commit; aaa_executor_decision.py issue/apply; aaa_executor_policy.py apply | Ayrı capability, fresh evidence, TTL/single-use/CAS | DECISION/CONTINUE/CANCEL HELD kayıtları | Karar metadata authority flip değildir. İptal eski grant'i kapsam dışı yapar; history korunur |

services/demo_management.py calculate_create/calculate_management_change saf
hesaplamadır; persistence writer ilgili adapter'dir. PPPoE readonly servis ve
independent evaluator owner yazmaz. Foto deposu yalnız dosya metadata'sı yazar.
Router/user servisleri subscriber owner yazmaz; parent/membership invalidation
ve global lock sırası için yine entegrasyon kapsamındadır. Domain
SubscriberAccount ayrı modeldir; bu matrise sahte runtime writer eklenmedi.

## Additive owner metadata taslağı — uygulanmadı

Hedef yalnız disposable acceptance PERSISTENT_WORKSPACE owner'ı. Mevcut 008
tabloya tenant_id UUID (onaylı atama sonrası NOT NULL), aaa_fence bigint>=0,
aaa_active_operation UUID nullable ve tenant+id UNIQUE önerilir; revision mevcut
sayaçtır. Source/fields.source ve router ilişkisi tutarlılığı korunmalı. Aktif
operation aynı tenant/subscriber operations kaydına composite FK; cycle için
nullable ilk reserve veya deferrable kararını reviewed migration belirlemeli.
Event'e tenant_id ve güvenilir operation/action korelasyonu eklenmeli; eski audit
sahibi ve satırlar overwrite edilmez. Membership'in additive gereği resolver
belgesindedir. İlk owner create, reserve/release, source commit ve recovery epoch
geçişleri ayrıca tanımlanmalı; metadata-only +1 helper bunları bugün desteklemez.

Mevcut kayıtları backfill etmek ayrı yedek+fark analizi/onay gerektirir; test
şeması varsayımıyla ofis kayıtlarına tenant verilmez. Legacy/domain owner'a aynı
kolonları topluca eklemek veya ID dönüştürmek planın parçası değildir.

## Ortak transaction protokolü

Güvenilir actor/membership lock'ları önce; sonra router parent'lar sıralı, owner'lar
sıralı, operation/action/outbox/attempt. Bu yeni global sıra, mevcut owner-first
AAA prototip sırasının üstüne actor/membership/router katmanlarını ekler; günlük
router-first kodla birlikte ayrıca gözden geçirilmelidir. Kimlik/rol değiştiriciler
aynı sıraya katılmadan revocation freshness garantisi yoktur.

DAILY_OWNER: active_operation NULL; tenant/id/revision/fence/source/NULL CAS;
revision+1/fence+1 ve audit aynı transaction. İş kuralı farklı olsa da paket,
tarih, status veya router mutation bu kilidi atlayamaz. İlk create için yok
row'u kilitlemiş varsaymak yerine tenant/router kimlik unique'leri ve request
idempotency ile insert yapılır; yarış unique conflict olarak ele alınır.
AAA_METADATA: aynı active UUID ve beklenen revision/fence; journal/audit/outbox
ve authorization consumption aynı transaction. HELD kayıtlar kuyruk değildir.
Failure audit izinli kapsamda ayrı olaydır; başarılı owner mutation oluşturmaz.
Aktör/membership veya owner scope bilinmiyorsa ret; eski davranışa fallback yok.

## Aşamalı uygulama / kabul / geri alma kapıları

| Aşama | Ön koşul ve değişecek bileşen | Risk ve hedefli kabul | PASS / BLOCKED | Geri alma ve canlı etki |
| --- | --- | --- | --- | --- |
| 1 Resolver | Actor schema/origin, tenant ve membership sahibi; DI resolver + session-aware identity + grant freshness | Wrong tenant/router, DEMO/inactive/missing/seal, revocation concurrent consume, role/policy epoch | PASS yalnız aynı session fresh grant; eksik üyelik BLOCKED | DI kapalı, pending HELD; login fallback açılmaz. Bu aşamada canlı etki yok |
| 2 Owner metadata | Additive FK/unique/CHECK/backfill ve membership kararı, ayrı migration izni; model/repository projeksiyonu | Tenant FK, metadata NULL/stale, first create/reserve/release ve rollback; mevcut satırların korunması | PASS disposable katalog+veri özeti; approval/schema eksikse BLOCKED | Yeni yol disabled; kolonlar korunur, otomatik DROP/restore yok. Gerçek ofis DB kapsam dışı |
| 3 Günlük writers | 1–2; save/renew/change/failed, legacy sınırı, maintenance ve identity lock protokolü | AAA vs paket/uzatma/status/router/create yarışı, grant iptali, per-item batch, audit failure, idempotency | PASS bütün girişler common CAS'a katılınca; tek bypass bile BLOCKED | İşleri durdur/HELD tut; aktif AAA varken eski writer'a geri düşme yok. Ayrı izin olmadan çalışan sisteme dağıtım yok |
| 4 AAA bağlayıcı | Tüm writer katılımı; UoW/contract validator/target guard bağlanır | Payload/receipt/evidence/scope, single-use, held-only, owner lock release/source commit | PASS DI varsayılan kapalı + kapsamlı fixture test; opaque callback true BLOCKED | Adapter seçimi kapalı; history silinmez. Provider dispatch kapalı |
| 5 Disposable PG | Ayrı onaylı kimlik, schema/roller/RLS ve owned cluster | MVCC/CAS/fencing, lock sıra/deadlock, çift consume, DB clock, tenant isolation, audit/outbox fault ve commit cevabı kaybı | PASS gerçek disposable SQL/katalog kabulü; fake-session sonucu yeterli değil | Yalnız test kaynağı ownership doğrulamasıyla durdurulur; ofis DB'ye restore yok. Üretim etkisi yok |
| 6 Recovery/rollback | PG acceptance, epoch/retention ve bağımsız provider kanıt tasarımı | IN_FLIGHT/send crash, timeout, late receipt, UNKNOWN restore, lease expiry, token regression | PASS dispatch öncesi/sonrası sınırlar; belirsizde otomatik retry varsa BLOCKED | Dispatch kapalı, UNKNOWN korunur, read-only uzlaştırma; source flip/compensation ayrı yetki. Canlı provider hâlâ ayrı kabul/onay |

Aşamalar takvim taahhüdü veya verilmiş migration/deploy onayı değildir.
Rollback önce capability/wiring kapatma ve held işleri korumadır; veriyi silme,
parola reset, fence sayacı geri sarma veya iki ortamı restore ile birleştirme değildir.

## İzolasyon ve somut ilk uygulama

V2.6 disposable profil exact schema/DB/rol/port/marker/owned directory ile
sabitlenmeli; yalnız localhost demek yeterli değildir. Ofis demo DB'si ayrı,
V2.5 pilot/V1/VDS/gerçek router/RADIUS/IPsec tamamen kapsam dışıdır. Env/default
DSN/credential/oturum/env dosyası fallback'i veya ortak secret kullanımı yok.
Git kodu eşitliği DB/user/membership eşitliği anlamına gelmez. Gerçek katalog
ve servisler bu belgede doğrulanmadı; salt belge kontrolü yapıldı.

**Sıradaki tek uygulama önceliği:** aşama 1'in güvenilir session-aware resolver ve
freshness proof sözleşmesini, seçilmiş actor schema/tenant membership kararıyla
izole DI testlerinde geliştirmek. Membership verisi/migration veya gerçek DB
kullanımı ayrıca açık yetki gerektirir; kararsız tenant bilgisinden grant üretilmez.
