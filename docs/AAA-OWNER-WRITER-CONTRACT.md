# AAA tenant/aktör ve owner-writer sözleşmesi — v1

2026-11-12 · Başlangıç 5055e06. **PARTIAL: DI prototip sözleşmesi PASS;
çalışan owner yazıcılarının entegrasyonu BLOCKED.** Gerçek DB/katalog/rol,
üyelik veya production kapsamı doğrulanmadı.

## Güvenilir sahiplik ve ortak CAS

`repositories/aaa_owner_contract.py` saf sözleşmedir; DB, config veya kimlik
servisine bağlanmaz. OwnerScope tenant UUID/actor/subscriber ister. OwnershipGrant
v1 aynı üçlü, actor_active=true, pozitif membership_revision ve açık
AAA_METADATA/DAILY_OWNER capability ister. Boolean True, None, farklı tenant/
aktör/owner, inactive, eksik capability veya yanlış sürüm fail-closed reddedilir.
Grant güvenilir server membership resolver'ından gelmelidir; istemci JSON'u
veya sadece model oluşturabilmek yetki değildir. Bu resolver henüz bağlanmadı.
Deaktivasyon/üyelik değişimi her repository çağrısında yeniden çözülmelidir;
uzun ömürlü cached grant için güncellik garantisi yoktur.

Owner kimliği `(PERSISTENT_WORKSPACE,tenant_id,subscriber_id)`; legacy string ID,
domain UUID veya PPPoE/Hotspot türü tenant yerine kullanılamaz. `locked_owner`
row içinde tenant/id/revision/source/aaa_fence/aaa_active_operation zorunlu tutar.
Revision/fence int ve >=0; UNKNOWN kaynak veya eksik alan fallback yapmaz.
AAA_METADATA yazarı yalnız aynı active_operation UUID ile; DAILY_OWNER yalnız
active_operation=NULL ve operation_id=None iken ilerleyebilir. Aktif AAA işi
varken günlük edit/uzatma başka alanı değiştiriyor olsa bile bloke olur.

Ortak SQL CAS predicate: tenant + owner ID + beklenen revision + fence + source
+ beklenen active_operation. SELECT FOR UPDATE yerine geçmez; stale read ve
lock atlama girişimine karşı ek rowcount=1 savunmasıdır. Metadata değişiminde
revision/fence tam +1; source/active_operation sabit kalır. Bu dar prototipte
source flip, ilk reservation veya lock release yoktur. Bunlar ileride plan/kanıt
ve ayrı izinli state geçişiyle kapsanmalıdır, generic override bayrağı eklenmez.

Tüm gerçek yazıcılar owner→operation→action→outbox→attempt lock sırasına ve
aynı transaction'da owner/journal/audit/outbox atomikliğine katılmalıdır.
Grant, Python validator veya callback tek başına raw SQL bypass'ı engelleyemez;
DB rol/RLS/constraint ve bütün yazarların adaptasyonu ayrıca gerekir.

## Kaynak temelli owner-writer matrisi

Kaynak taraması backend altındaki model kullanımları, SQL INSERT/UPDATE ve
revision/source yazımları üzerinden yapıldı. Aşağıdakiler kod davranışıdır;
gerçek servisler çağrılmadı. Dış DBA/manuel SQL bütünlüğü ayrıca rol denetimi ister.

| Yazıcı / kaynak | Tenant/actor ve owner | Revision/fence + lock/transaction | Journal/audit/outbox | Eksik / karar |
| --- | --- | --- | --- | --- |
| services/subscriber_center.py save | current API aktörü; workspace string ID, tenant yok | parent router lock, Account FOR UPDATE, expected revision; Session.begin; fence yok | mevcut events CREATE/UPDATE + request receipt | AAA active lock ve tenant grant yok; çalışan davranış değişmedi, BLOCKED |
| subscriber_center.py renew | aktör, workspace ID/router/source | FOR UPDATE ve expected revision/date; aynı transaction | events RENEWAL/UUID | common fence/active_operation yok; BLOCKED |
| services/subscriber_operations.py change | aktör, workspace LOCAL source/router kontrolü; EDIT/PLAN/STATUS/EXPIRE/EXTEND/ROUTER | parent+owner lock; revision CAS, Session.begin | events ve _management receipt | tenant/fence/AAA lock yok; BLOCKED |
| subscriber_operations.py failed/audit | aktör; bazen account bulunmayabilir | failure audit ayrı transaction; owner lock varsa okunur | failure event ve UUID recovery | owner değişmez fakat actor/tenant ve ortak audit kapsamı şart; BLOCKED |
| adapters/demo_subscriptions.py create/change/expiry/_persist | LEGACY_DEMO; actor ve request scope, tenant yok | engine.begin; _item(lock=True), revision; _persist ID tabanlı SQL | v2_demo events/requests | ikinci owner store; workspace'e map edilmez. AAA metadata hedefi dışı, ileride ayrı adapter/lock kuralı |
| services/demo_subscriptions.py memory store, demo_management.py hesaplama | legacy sentetik IDs/actor | memory davranışı; saf calculate fonksiyonları kalıcı writer değildir | sentetik history | production owner değildir; değiştirilmedi |
| demo_storage.py initialize/seed, demo_repair.py, local_demo_database.py | yönetim/bootstrap; mevcut demo owner payload/revision | explicit engine.begin, marker/owned-dir guard; bazı payload UPDATE'ları revision/fence sözleşmesinde değil | seed/events/requests başlangıcı | aktif AAA varken bootstrap/repair yasak; otomatik entegrasyon yok, BLOCKED |
| simulation/aaa_atomic.py reserve/settle/compensate | PreviewScope tenant/actor/store/router, OwnerFixture | RLock/deepcopy publish, revision/fence | memory journal/audit/outbox | fixture kabulü var; PG/aktif günlük writer koordinasyonu yok |
| simulation/aaa_worker.py claim/renew/dispatch/ack/nack/retry/recovery | worker tenant/scope + attempt | memory transaction, lease/token/expiry, owner revision | lease journal/outbox/audit | DB lease/crash semantics değil; recovery expiry dispatch izni değildir |
| simulation/aaa_execution/next_step/preparation/prepared_authorization | ayrı actor capability, owner/step plan | registry TTL/tek kullanım, staging CAS/fence memory transaction | HELD checkpoint ve consumed audit | yeniden kullanılacak domain mekanizması; mevcut runtime'a PG bağlanmadı |
| simulation/aaa_executor.py accept/timeout | bound execution/attempt/actor scope | receipt→owner CAS, fence; atomik memory acceptance | SUCCESS/REJECTED/UNKNOWN journal/audit/outbox | fake run provider state yazar; owner yalnız acceptance'ta. Gerçek provider yok |
| simulation/aaa_executor_decision/decision/followup/executor_policy | ayrı issue/apply yetkileri, tenant/actor | fresh evidence/TTL/single-use/CAS/fence | metadata decision/CONTINUE/CANCEL + HELD | evaluator salt okunur; issue yalnız registry; apply owner metadata yazar |
| repositories/aaa_metadata.py | yeni zorunlu OwnershipGrant + contract/target DI | ortak locked_owner + SQL CAS; session transaction/poison | metadata head + mevcut workspace events + HELD outbox | bu görevde düzeltildi, fakat şema/resolver/all-writers kabulü yok |
| models/subscriptions.py domain SubscriberAccount | customer/router/plan UUID FK; panel_users actor dünyası | modelde AAA revision/fence/tenant yok | domain subscriber_events/audit_logs | model tanımı writer değildir; workspace ile paralel owner olarak kullanılmaz |
| subscriber_photos.py | source/tür/subscriber ve actor metadata | dosya atomic write/delete | foto dosya metadata; owner source/revision yazmaz | aynı hesap çevresi fakat owner CAS writer değildir; kapsam dışı |
| router_workspace/router_registry ve identity servisleri | router/user kendi sahipliği | kendi revision/transaction kuralları | router/user audit | subscriber owner doğrudan yazmaz; router-parent ve aktör üyeliği invalidation kapısı ayrıca gerekir |

api/v1/subscribers.py legacy store'a, api/v1/subscriber_center.py workspace
servislerine yönlendirir; ayrı gizli owner transaction değildir. PPPoE readonly
servis/adapter'leri ve evidence evaluator okuma yoludur; capability veya source
adındaki RADIUS yazma çağrısı yapıldığı anlamına gelmez. Testlerdeki fake state
seed/fault mutasyonları production yazıcı diye sunulmaz.

## Bu görevde DI düzeltmeleri

- Scope tek ortak OwnerScope olarak alias edilir; dış prototype çağrı adı korunur.
- authorize(session,scope) artık bool yerine OwnershipGrant döndürmelidir.
  Eski bool callback fail-closed kırılır; production API/in-memory etkilenmez.
- reserve/issue/consume owner row'unun tüm metadata/active lock kapsamını sınar.
  Önceki issue SELECT sonucu kullanılmıyordu; artık missing/wrong owner reddedilir.
- consume ortak metadata transition/CAS predicate üreticisini kullanır.
  Journal/audit/outbox/authorization transaction motoru korunur; başka state machine yok.
- Saf DAILY_OWNER kontrolü hazırlanmıştır; çalışan günlük servisler bu fonksiyonu
  henüz çağırmaz. Bu belge günlük write koruması uygulanmış gibi okunmamalıdır.

## Hedefli kabul ve sonraki uygulama planı

7 yeni fake/in-memory test: grant scope/actor/inactive/sürüm, missing metadata,
stale revision/fence; aktif AAA lock'u aşan DAILY write ve SQL rowcount0; eşzamanlı
AAA/DAILY tek yetkili kazanan; atomik journal/audit/outbox rollback/replay;
boolean authorizer ve missing owner issue reddi; monoton transition. Değişen
repository'nin 8 ilgili testi de geçti; yeni error tipi için yalnız etkilenen
beklenti düzeltildi. Fake global lock MVCC/PG row lock semantiği değildir.

**BLOCKED uygulama planı:** tenant/aktör membership sahibi ve güvenilir resolver;
owner tenant/fence/active-operation şema/constraint tasarımı; tüm günlük writer,
bootstrap ve repair girişlerinin ortak kilit sözleşmesine alınması; router-parent
lock sırasıyla owner-first sırasının deadlock değerlendirmesi; audit/failed event
scope ve DB rol/RLS; ayrı disposable PG gerçek concurrency/commit-crash kabulü.
Bu adımlar migration ve çalışan davranış değişikliği içerir, bu görevde yapılmadı.
İlk reservation/source commit/release için açık ayrı protokol gerekir.

Sıradaki tek öncelik: güvenilir tenant/aktör resolver'ı ve bütün günlük owner
writer'ları için kapsamı sınırlandırılmış entegrasyon planını onaya hazır hale
getirmek. Canlı DB/migration/provider izni bu belgelerden türetilmez.
