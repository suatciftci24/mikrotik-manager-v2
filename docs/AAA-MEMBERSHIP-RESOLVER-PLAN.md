# AAA membership resolver uygulama planı — v1

2026-11-12 · Kaynak HEAD 48df672. **PASS: kaynak ve sözleşme planı;
BLOCKED: runtime resolver / kalıcı üyelik kabulü.** Ürün kodu, DB veya migration
bu görevde değiştirilmedi. [Yazıcı entegrasyon planı](AAA-OWNER-WRITER-INTEGRATION-PLAN.md).

## Mevcut güvenilir kaynak ve eksikler

| Kaynak / fonksiyon | Kanıtlanan kod davranışı | Resolver kararı |
| --- | --- | --- |
| core/security.py login_demo/current_demo_user | Opaque process-local session actor ID/timeout; her request find_user ile kullanıcıyı yeniden okur | Oturumdan yalnız doğrulanmış actor ID alınır; role/tenant beyanı istemciden alınmaz |
| services/identity.py adapter/find_user | Store şeması allowlist v2_demo/v26_acceptance; marker/setup seal kontrolü; users satırı role/active/permissions/revision | Profil ile sabitlenmiş users tablosu aktif aktör kaynağı olabilir; aynı UoW session'ında tekrar okunmalı |
| identity.py find_user/bootstrap + identity_setup.inspect_setup | Kurulum durumuna göre bootstrap fallback; sealed ortam LOCAL origin kontrolü | Bootstrap/DEMO fallback AAA resolver'da yasak; kısmi seal/eksik origin fail-closed |
| identity.py save_user/transition | Aktif ADMIN, router izinleri, expected revision; target FOR UPDATE; user_audit | Aktiflik/rol/izin revizyon kaynağıdır; membership veya AAA capability oluşturmaz |
| core/authorization.py allowed/can_manage_role/require_router | Router kapsamı, ADMIN/OPERATOR/VIEWER ve PPPoE/Hotspot günlük yetkileri | Günlük izin AAA dispatch/decision iznine çevrilmez |
| models/identity.py PanelUser; models/access.py Role/Permission | Domain UUID users/role FK ve is_active modeli | Çalışan demo identity ile aynı tablo değildir; ID/email üzerinden birleştirilmez |
| models/subscriber_workspace.py ve router_workspace.py | Sentetik workspace isimli şemalar; owner/router FK, revision | Workspace adı tenant/membership değildir; store ID türü tenant üretmez |
| repositories/aaa_owner_contract.py | OwnerScope/OwnershipGrant v1; tenant/actor/subscriber/capability ve metadata kontrolü | Saf doğrulayıcı yeniden kullanılacak; grant'i yaratmak güvenilir membership kanıtı değildir |

Kaynakta kalıcı tenant/membership entity veya üyelik epoch'u **yok**. Mevcut
users.permissions router JSON'u tenant membership yerine kullanılamaz. users.revision
aktör değişikliğini izler; membership_revision ile eşit varsayılamaz. PostgreSQL
katalogları, kullanıcıların gerçek aktifliği ve üyelik kayıtları sorgulanmadı.

## Kaynak seçimi ve additive membership gereksinimi

İlk kabul yalnız disposable V2.6 profili ve PERSISTENT_WORKSPACE owner içindir.
Deployment kimliği, tenant UUID ve actor schema server allowlist'ten sabitlenir.
Acceptance actor kaynağı yalnız v26_acceptance.users; ofis local-demo kimlik
analizinde v2_demo.users kullanılabilir fakat acceptance resolver oraya fallback
etmez. Domain panel_users için ayrı adapter/explicit schema kararı gerekir.
Username/e-posta eşitliği ortamlar arasında aktör eşleştirmesi değildir.

Tenant kaydı mevcut olmadığı için ilk izole profil için pinned deployment+tenant
kimliği yeterlidir; gerçek çoklu tenant registry tasarımı ayrı karardır. **Kalıcı
üyelik kaydı yine gereklidir.** Var olan bir tabloya eşdeğer bulunmadığından,
ayrı onay sonrası tek membership ilişkisi önerisi: tenant UUID + actor ID PK,
active, membership_revision bigint>0, capabilities allowlist, policy_revision,
updated_at, değişikliği yapan aktör/korelasyon. Actor FK yalnız seçilen profile
ait users tablosuna bağlanır; farklı şemalara polymorphic actor FK yoktur.
Bu mevcut abone deposu veya ikinci kullanıcı/rol tablosu değildir. Tenant/actor
sahibi ve schema seçimi kesinleşmeden migration/backfill yapılmaz.

Her üyelik değişimi aynı mevcut user audit ya da onaylı merkezi audit hedefinde
append-only kaydedilmeli; üyelik revision++ ve audit aynı transaction. Kullanıcı
rolü/aktifliği ile üyelik izinleri birlikte kontrol edilir. Owner tenant/router
ilişkisi server kaynağından okunur; request'teki subscriber ID tek başına kapsam
kanıtı değildir. Tenant ataması onaylı, iki ortamın veri farkı ve yedeğiyle
ayrı ele alınır; mevcut demo hesaplara toplu varsayımsal üyelik verilmez.

## Resolver sözleşmesi

Önerilen DI portu: `resolve(session, authenticated_actor, OwnerScope, capability)`.
Return mevcut OwnershipGrant; deny PermissionError/domain conflict, eksik bilgi
asla default grant değildir. Port yeni auth sistemi veya HTTP endpoint'i değildir.

1. Enjekte edilmiş target guard exact environment/profile/database/schema/role/
   owned-cluster/marker kanıtını doğrular; yanlış hedefte ilk yazımdan önce durur.
2. Oturumun güvenilir actor ID'si ve origin/seal bağlamı alınır; supplied actor,
   tenant veya role header'ı güvenilir değildir. Aktör bulunamaz/pasif/DEMO/
   bootstrap/kısmi identity şemasıysa ret. Worker için ayrı server principal
   ve dar capability gerekir; eski kullanıcı cookie'si worker izni değildir.
3. Aynı UoW session'ında actor, tenant membership, owner/router kapsamı okunur.
   `find_user()` doğrudan çağrılmaz: ayrı connection/transaction ve bootstrap
   fallback içerir. Onun exact-schema/seal/aktiflik mantığı yeniden kullanılacak
   küçük session-aware okuma sınırı ayrıca tasarlanır; auth güvenliği gevşetilmez.
4. Membership active/revision/policy ve mevcut actor role/router sınırı birlikte
   kontrol edilir. AAA_METADATA/DAILY_OWNER genel grant'ine ek olarak operasyon
   özel evaluate/issue/consume/prepare/execute kapsamı service seviyesinde kalır.
5. Grant actor/tenant/subscriber'a bağlanır. actor_revision, membership_revision,
   policy_revision ve source deployment stamp ayrı freshness proof'ta taşınmalı;
   mevcut grant yalnız membership_revision içerir. Tek revision'a birleştirme
   veya hash'ten yetki üretme yok. Gerekli additive contract alanları ayrı kod
   görevinde sürümlenecek; bu belgeyi mevcut kod destekliyormuş gibi sunma.
6. Issue ve consume ayrı resolve çağrılarıdır. Apply anında aktör/üyelik/owner
   revizyon/fence taze doğrulanır. Grant TTL ve single-use korunur; üyelik iptali
   TTL sonunu beklemez. UUID replay result okumak için de güncel scope gerekir.

## İptal ve transaction içi TOCTOU

Request başındaki fresh user okuması transaction içi revocation garantisi değildir.
Önerilen global lock sırası: actor kimlik satırı → membership → router parent'lar
sıralı → owner'lar sıralı → operation → action → outbox → attempt. Günlük mevcut
router-first ve AAA owner-first yolları bu sıra altında birlikte uyarlanmalıdır;
karışık sırayla devreye alma deadlock riski taşır.

Resolver/kullanıcı ve membership değiştiren servisler aynı actor/membership lock
protokolüne katılır. Böylece revocation commit edilmişse sonraki consume reddedilir;
önce consume lock aldıysa revocation onu bekler ve işlem sırası audit'te açık kalır.
“İptal isteği geldiği anda in-flight dış etkiyi geri alma” garantisi verilmez.
Uzun transaction yok; dış provider çağrısı lock tutulurken yapılmaz. Başlangıç ve
commit öncesi revision/policy CAS kontrolü farklı connection'dan yapılmaz. Identity
save_user içinde actor okuması bugün lock'suzdur; ilgili revocation/role yazıcıları
katılmadan güçlü transaction freshness iddiası yapılamaz.

## Aşama kapısı ve geri alma

Ön koşul: seçilmiş schema/actor origin, tenant sahibi, membership kayıt politikası,
capability dağıtımı ve global lock sırası onaylı olmalı. Değişecek kod: DI resolver,
session-aware identity read, grant freshness sözleşmesi ve membership mutation
sınırı; mevcut login/password/cookie kontratı değiştirilmemeli.

Hedefli kabul: wrong tenant/actor/owner/router, inactive/DEMO/bootstrap, eksik
üyelik/seal, revocation ile concurrent consume, role/policy değişimi, expired/
used authorization, pool tenant-context sızıntısı, unknown DB marker. PASS ancak
same-session freshness ve scope kanıtıyla; identity fallback veya membership
olmaması BLOCKED. İlk kod testi memory/fake, gerçek locking ayrıca disposable PG.

Geri alma: yeni AAA DI wiring'i kapat, bekleyen işleri HELD/UNKNOWN bırak; önceki
audit/üyelik/receipt silinmez. Yeni yazıcılar devreye girdikten sonra tenant/kilit
kontrollerini eski günlük yola düşürerek bypass etmek güvenli rollback değildir.
Additive kolonlar korunur; DROP/backfill reversal/restore otomatik yapılmaz.
Canlı etkisi: bu planın yoktur; uygulama yalnız ayrı izinli disposable kabulde.
