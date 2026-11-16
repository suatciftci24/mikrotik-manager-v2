# CEBECI V2.6 registry — tek kurulum ve dağıtım planı

Durum: yerel plan/SQL kabulü PASS; VDS uygulaması BLOCKED. Bu belge uygulama
onayı değildir. SSH, VDS SQL, restart, deploy ve router bağlantısı yapılmadı.

Kullanıcının son VDS kanıtı: gerçek LOCAL ADMIN oturumu, capability seçimi,
DB ve session/DB eşleşmesi PASS; aday `v2-user-49b00e12-4d11-4413-94ee-f222ab056703`,
revision 0. Bu bir yetki oluşturma veya süresiz onay değildir. Üç registry
tablosu katalog kontrolünde TABLE_ABSENT. ACTIVE_CODE_IDENTITY_MISMATCH ve
CODE_SNAPSHOT_REQUIRED mevcut; geri dönüş yedekleri doğrulanmamış.

## Kurulum sözleşmesi

- Yalnız PostgreSQL 16, `mikrotik_v26_acceptance`, port 55433,
  PGDATA `/var/lib/postgresql/16/v26`; mevcut maintenance oturumu `postgres`.
  Unix socket maintenance bağlantısında inet_server_port NULL olabileceğinden
  port `current_setting('port')` ile, hedef de PGDATA/DB/role ile birlikte doğrulanır.
- Yeni nesneler yalnız `public.v2_registered_routers`,
  `public.v2_router_verifications`, `public.v2_router_registry_audit`.
  Yeni schema/role/database/sequence/servis/abone veya cihaz kaydı oluşturulmaz.
- Sahip mevcut maintenance rolü postgres; runtime v26_acceptance.
  Runtime için mevcut CONNECT ve public USAGE ön koşuldur; üç yeni tabloda
  yalnız SELECT/INSERT/UPDATE verilir, grant option verilmez. PUBLIC table ACL
  temizliği yalnız yeni üç tabloya uygulanır. Global default ACL/schema ACL,
  mevcut roller, üyelikler, kullanıcı/parola/permissions satırları değiştirilmez.
- Runtime superuser/createrole/createdb/bypassrls/replication, postgres üyeliği
  veya public CREATE yetkisine sahipse STOP; yetkiler otomatik geri alınmaz.
  Bu durumun çözümü ayrı kapsam/yetki değerlendirmesi gerektirir.
- Mevcut 006 DDL/model tipleri ve nullable kuralları korunur. Altı nonunique
  B-tree index, üç id PK, management_address+port UNIQUE ve güvenli port CHECK
  gerekir. Yeni FK/RLS/policy/trigger/default/column ACL eklenmez; core users veya
  subscriber tablolarına bağ kurulmaz. Gölgelenen/kısmi isim veya enabled DB
  event trigger bulunursa STOP. Runtime search_path değiştirilmez; gerçek
  runtime bağlantısının public tabloları çözmesi son kontrolde doğrulanır.
- Audit UPDATE zorunludur: mevcut register akışı verification_id üzerinden
  audit router_id bağlantısını günceller. Append-only izni vermek bu akışı bozar.
  DDL+ACL+tek kurulum audit satırı aynı transaction'dadır. Kurulum satırında
  actor=migration:postgres, ayrı namespace `migration:v26-registry-001` proof
  referansı kullanılır; bu gerçek RouterVerification değildir ve API UUID'siyle
  eşleşmez. Böylece normal audit link işlemi migration kaydını taşımaz.
- Audit yalnız migration/contract kimliği, doğrulanmış aday ID/revision,
  release ve yedek/auth receipt hash'lerini saklar. DSN, parola, cookie veya
  yedek/env içeriği saklanmaz. Yeni LOCAL kullanıcı veya kalıcı grant yaratılmaz.

## İncelenebilir artefaktlar

[install.sql](../deploy/v26-cebeci/registry-migration/install.sql) ayrı onayla
gelecekte kullanılacak koşullu SQL'dir; startup'a veya toplu migration runner'a
bağlanmadı. Eski `migrations/versions/006_router_registry.sql` değiştirilmedi.
[contract.json](../deploy/v26-cebeci/registry-migration/contract.json) model,
owner/ACL/index/CHECK ve receipt sözleşmesini;
[SHA256SUMS](../deploy/v26-cebeci/registry-migration/SHA256SUMS) dosya pinlerini içerir.

SQL'in önceki bir transaction'a eklenmesi yerine ayrı maintenance oturumunda,
ON_ERROR_STOP ile tek dosya olarak yürütülmesi planlanır. BEGIN REPEATABLE READ,
3 saniye lock_timeout, 15 saniye statement_timeout, advisory transaction kilidi,
pg_catalog search_path ve tüm guard'lar DDL öncesindedir. Bir hatada transaction
abort olur; caller ayrıca ROLLBACK/bağlantı kapanışını doğrular. Otomatik retry yoktur.

SQL şu context değerleri olmadan ilk guard'da durur: approval tam
INSTALL_V26_REGISTRY_ONLY, closed_gates_receipt=VERIFIED, mevcut operator_id ve
revision, 40 hex release_sha, 64 hex backup_manifest_sha256 ve auth_receipt_sha256.
Bunlar yalnız session-local maintenance context'tir; uygulama env/grant değildir.
Hash biçimini doğru yazmak gerçek yedek/kimlik kanıtının yerine geçmez: yetkili
operatör önce aşağıdaki kapıları kanıtlarıyla kapatmalıdır. SQL DB tarafındaki
kimlik/revision/seal ve nesne guard'larını yeniden kontrol eder; dış dosya veya
unit durumunu kendi başına doğrulayabildiği iddia edilmez.

### İdempotent davranış

| Mevcut durum | Sonuç |
| --- | --- |
| Üç tablo da yok, başka isim/type/index çakışması yok, tüm ön koşullar sağlanmış | Yalnız üç tablo/index/ACL ve bir kurulum audit satırı; tek COMMIT |
| Üç tablo var, owner/schema/model/index/ACL/CHECK tam eşleşiyor ve aynı migration+contract audit kaydı var | NO-OP; veri, grant ve audit satır sayısı değişmez; dolu registry de korunur |
| Bir/iki tablo var veya aynı ad başka şemada/type/index olarak var | BLOCKED; eksik parçayı tamamlama/repair yok |
| Üç tablo var fakat receipt yok/farklı veya metadata/ACL drift var | BLOCKED; mevcut altyapıyı sahiplenme, ALTER veya kör IF NOT EXISTS yok |
| Audit INSERT veya başka postcondition hata veriyor | Yeni DDL/ACL/audit tümü rollback; core veri değişmez |

Migration kaydı `dc9fa0f4-e1db-5810-ad18-8c3ac2971c94`; version
`v26-cebeci-registry-001`. Aynı sürüm uyumluluğu yalnız kolonları değil JSON
manifest içindeki tüm normatif permission/index/constraint politikasını hash'ler.

## Tek operasyon sırası

1. **Önce kimlik ve çalışan sürüm kanıtı.** Yeni standalone preflight disk
   snapshot'ını API kimliğinden ayrı toplar. Böylece disk/code yedeği kontrolü
   ACTIVE mismatch yüzünden atlanmaz; fakat backup sonucu yalnız disk baseline'ı
   sayılır, running sürümü temsil ettiği iddia edilmez. Beklenen/gerçek repo ve
   build hash'leri ayrı, yalnız 64 hex olarak raporlanır. Repo farkında gerçek
   module/factory/proxy hedefi; build farkında çalışan import anındaki sürüm ile
   disk içeriği bulunur. Restart ederek veya mevcut diski overwrite ederek
   nedeni gizleme. Canlı build ile eşleşen geri dönüş release artefaktı bulunamazsa STOP.
2. **Yedek ve koruma baseline'ı.** Env içeriği yalnız root belleğinde kalır.
   V2.6 tam DB dump + TOC/hash; mevcut gerçek backend kaynak/dependency ve tüm
   frontend dist/source/build manifest'i; env dosyaları; API/web unit fragment,
   drop-in ve EnvironmentFile kopyaları private bir rollback setine alınır.
   Bu yedek yaratma işlemi ayrı açık gelecek işlem onayı gerektirir; readonly
   komut yeni yedek yaratmaz. Hash/izin/owner ve running/disk sürüm eşlemesi
   doğrulanır; dump TOC'si restore testi sayılmaz. DB yedeğinin gerekli restore
   kabulü yalnız ayrı izole hedefte, mevcut DB'ye restore yapmadan kanıtlanır.
   Kullanıcı/revision/role, aboneler, paketler ve mevcut audit/event/şema
   baseline'ı private receipt'e alınır; gerçek içerik Git'e veya genel rapora çıkmaz.
3. **Tek kapalı release'i hazırlama ve onay.** Sadece onaylı V2.6 hedefinde
   backend/frontend/config manifest'i hazırlanır; rastgele git pull veya eski
   V2.5/fresh-pilot installer'ı kullanılmaz. Gerçek code root
   /srv/mikrotik-v26-next için yeni kodda V2_V26_RUNTIME_LAYOUT=vds-next açıkça
   seçilir; eski /tmp data/bakım kökü taşınmaz. DB URL/role/port ve kullanıcılar
   korunur. İki eski genel flag false/eski operator listesi boş; yeni CEBECI
   READ_ENABLED=false ve yeni operator ID/revision boş olur. Önce gate'i kapalı
   olacak doğrulanmış rollback env'i de hazırlanır: eski yedekte flag true ise
   onu körlemesine geri yüklemek tablolar kurulduktan sonra erişimi açabilir.
   Tüm kanıtlar tamamlanınca yalnız bu release/API-web işlemleri ve registry
   DDL/ACL/audit kapsamı için yeni açık onay alınır; router bağlantısı bu onaya dahil değildir.
4. **Kapalı release'i yayınlama.** Yalnız mevcut API/web servislerinde gerekli
   işlemler yapılır; PostgreSQL/V1/V2.5/RADIUS/IPsec unit'lerine dokunulmaz.
   Kaynak/hash, HTTPS/API/auth/DB sağlık ve mevcut veri baseline'ı doğrulanır.
   Başarısızsa DB migration'a geçmeden onaylı kapalı rollback release/env'i
   geri yüklenir. Başarılı restart in-memory cookie'yi geçersiz kılabilir;
   gerçek kullanıcı normal panel girişini yapar, /auth/me → DB kanıtı tazelenir.
   Bildirilen aday ID/revision 0 güncel değilse sıfırlama yapılmaz; yeni onaylı
   kimlik/revision kullanılır. Gate'in dosyada ve çalışan process'te kapalı
   olduğu ayrı receipt ile doğrulanır.
5. **Koşullu registry transaction'ı.** Yukarıdaki artefakt/hash/context ve taze
   gerçek kimlik kanıtıyla postgres maintenance oturumunda yalnız install.sql
   değerlendirilir. Hedef DB/port/PGDATA/schema/role ve core seal yeniden kontrol
   edilir. SQL kapalı uygulamada çalışır; kurulum kendiliğinden pilot bağlantısı
   başlatmaz. Kalıcı migration ledger olarak yalnız yeni registry audit satırı
   kullanılır; eski migration ledger/seal/user_audit tablolarına yazılmaz.
   COMMIT sonucu belirsizse kör tekrar yerine marker ve nesne sözleşmesi okunur.
6. **Kurulum sonrası salt okunur kabul.** Runtime v26_acceptance ile aynı
   readonly preflight çalışır; üç tablo/schema/index/ACL ve session DB eşleşmesi
   PASS olmalı, kurulumdan hemen sonra routers=0, verifications=0, audit'te tek
   migration kaydı olmalıdır. Core kullanıcı/aboneler/permissions/audit verileri
   baseline'a göre korunur. Eşzamanlı meşru iş trafiğindeki fark rollback/restore
   gerekçesi yapılmaz; hangi işlem değiştirdiği araştırılır. Kurulum audit receipt'i
   private rollback setine dışarıdan doğrulanarak eklenir. Gate kapalı kalır.
7. **Son karar.** Yalnız registry altyapısı + kapalı release kabulü PASS ilan
   edilir. Gerçek cihaz okuması ve yetkili adayla gate açılması sonraki ayrı
   onaylı işlemdir. Bu plan V1 bağlantısını kesmez; abone, LOCAL/RADIUS sahipliği,
   canlı router veya diğer cihazlarda hiçbir değişiklik içermez.

## Geri dönüş politikası

- Transaction tamamlanmadan hata: normal ROLLBACK; yeni üç tablo/ACL/kurulum
  kaydı da kalmaz. DB dump restore edilmez, eski veriler üzerine yazılmaz.
- COMMIT sonrası uygulama hatası: önce CEBECI gate kapalı kalır, onaylı eski
  backend/frontend ve kapalı rollback env/unit seti geri yüklenip sağlık/veri
  kanıtı alınır. Yeni additive tablolar ve audit varsayılan olarak korunur.
  Eski uygulama bu boş altyapıdan etkilenmez; otomatik down/drop yoktur.
- Yapısal kaldırma ancak **ayrı açık removal onayıyla**: aynı DB/owner/advisory
  kilit, üç tablo ACCESS EXCLUSIVE lock, tam contract/ACL/owner eşitliği,
  sıfır router ve verification, audit'te yalnız birebir kurulum marker'ı,
  hiçbir yeni index/policy/trigger/FK/foreign dependency ve kapalı process gate'i
  yeniden doğrulanır. Kurulum audit satırı/DDL ve receipt önce private dış
  yedekte doğrulanmış olmalıdır. Yalnız bu üç tablo DROP ... RESTRICT ile
  kaldırılabilir; DROP SCHEMA/CASCADE/DELETE/TRUNCATE uygulanmaz.
  Herhangi bir operasyon/audit/verification/cihaz kaydı varsa kaldırma BLOCKED;
  altyapı tutulur. Bu görevde down executor yazılmadı veya çalıştırılmadı.
  Bu sınır audit silerek sahte bir 'rollback PASS' üretmeyi önler.

## Bugünkü gerçek BLOCKED koşulları

- Üç tablo yok: kurulum ihtiyacı kanıtlandı; fakat migration onayı verilmiş değil.
- Çalışan/disk code identity uyuşmuyor; gerçek running rollback artefaktı henüz
  doğrulanmadı. CODE_SNAPSHOT_REQUIRED yedek yokluğu kanıtı değil, önceki aracın
  bu koşulda snapshot'ı vermemesinin ikincil sonucudur.
- Backend/frontend/env/unit/dump rollback seti ve restore/sağlık baseline'ı
  doğrulanmadı. Bunlar olmadan kapatmak için dahi kör restart yapılmaz.
- Maintenance owner/PGDATA, runtime role attribute/schema CREATE, etkin DB event
  trigger, global isim/type/index çakışmaları ve app search_path henüz güncel
  maintenance transaction'ında doğrulanmadı. Hiçbiri varsayımla PASS değildir.
- Önceki oturum PASS'ı yeniden başlatma sonrası yeni session/fresh revision
  kanıtının yerine geçmez; geçmiş sabit VDS ID'sinden grant devralınmaz.

## Yerel kanıt

İki SQL/contract test metodu: model ve eski 006 checksum eşleşmesi; yalnız üç
public tablo ve altı index yazma allowlist'i. Yeni /tmp/v26-registry-plan-* PG16
cluster'ı yalnız initdb ve postgres --single ile kullanıldı; hiçbir socket,
listener, mevcut port/DB veya VDS bağlantısı yok. Production SQL kopyasında
**yalnız** PGDATA sabiti yeni fixture path'iyle değiştirildi; gerçek dosya guard'ı
korundu ve değiştirilmemiş dosyanın reddi ayrıca test edildi. Apply/NOOP,
dolu registry/audit korunumu, excess ACL, kolon drift, unmanaged receipt,
partial schema, namespace collision, aşırı güçlü runtime rolü ve audit aşamasında
SQL division-by-zero ile tam DDL rollback/core veri korunumu PASS.
İlk test aracında SET ile ilk SQL yorum satırının newline'sız birleştirilmesi
SQL'i yorum yapmıştı; yalnız fixture ayracı düzeltilip başarısız test tekrarlandı.
Son normatif contract/hash/index kontrolleriyle nihai iki test PASS.
İki yeni preflight diagnostic testi PASS; yanlış API içeriği secret olarak
rapora alınmaz. Syntax/diff/hash kontrolleri PASS. Frontend/app değişmediği için
build/önceki uygulama testleri tekrarlanmadı. Bu kanıt VDS migration kabulü değildir.
