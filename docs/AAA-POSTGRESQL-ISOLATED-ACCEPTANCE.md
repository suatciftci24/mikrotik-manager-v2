# AAA PostgreSQL izole kabul incelemesi — 2026-11-12

**Genel sonuç: BLOCKED — gerçek PostgreSQL kabulü çalıştırılmadı.**
Başlangıç `main-guncel` / `78c70dc`; temiz çalışma ağacı ve aynı GitHub SHA'sı
doğrulandı. Önceki 57 test tekrarlanmadı.

## İzolasyon kapısı

[Güvenlik incelemesindeki](AAA-POSTGRESQL-SECURITY-REVIEW.md) sabit disposable
kök `/tmp/mikrotik-v26-acceptance`, `os.path.lexists` ile yok olarak doğrulandı.
Owned PGDATA/cluster, marker, exact DB/rol ve hazır AAA şema kanıtı bulunmadığından
PostgreSQL bağlantısı kurulmadı. Başka DSN/env/credential veya mevcut local-demo
veritabanı alternatif hedef olarak aranmadı. Mevcut HTTP/WSL harness yeni cluster
hazırlar; `test_v26_identity_postgres.py` setup'ında `initdb` çağrısı vardır.
Bu görev yeni veritabanı oluşturmayı yasakladığı için harness çalıştırılmadı.
Kaynak kodundaki port/şema tanımları kurulu ve güvenli test ortamı kanıtı değildir.

## Kabul matrisi

| Kapsam | Sonuç | Kanıt / engel |
| --- | --- | --- |
| Gerçek PG claim TTL, prepared authorization, executor decision ve receipt | BLOCKED | Hazır doğrulanmış izole ortam yok; memory executor henüz PG UoW'ye bağlı değil |
| Membership resolver | BLOCKED | Kalıcı membership kaynağı, session-aware resolver ve actor/policy freshness entegrasyonu yok; sabit test grant'i gerçek üyelik değildir |
| Owner-writer PostgreSQL çalışma uyumu | BLOCKED | Additive tenant/fence/active-operation metadata ve bütün günlük writer'ların ortak protokole katılımı tamamlanmadı; katalog/MVCC/lock/rol/RLS doğrulanmadı |
| Owner CAS PostgreSQL SQL derlemesi | PASS, yalnız offline | AAA ve DAILY sorgularında tenant/subscriber/revision/fence/source/active-operation predicate ve UUID binding; DAILY için IS NULL |
| DI metadata TTL ve grant sınırları | PASS, yalnız fake session | 1–300 saniye, aware timestamp revalidation, değiştirilmiş grant reddi ve atomik metadata kontrolleri |
| Provider fixture | PASS, yalnız RAM | Replay tek etki/tek ACK; RADIUS enable için source fence; provider kanıtı owner commit sayılmaz |

## Kanıtlanan ve giderilen kod eksikleri

- `PostgresMetadataRepository.issue` 0.5 saniye TTL'yi kabul ediyordu. Alt sınır
  artık 1 saniye, üst sınır 300 saniye. Değiştirilmiş `ActionMetadata` JSON
  sözleşmesi yeniden doğrulanır; naive timestamp karşılaştırma TypeError'ı yerine
  sözleşme validation hatasıyla ret verilir. Mevcut DB clock kontrolü korunur.
- `require_ownership` değiştirilmiş grant içindeki truthy `actor_active='false'`
  veya `1` ve `membership_revision=True`/`1.5` değerlerini kabul ediyordu.
  Artık yalnız gerçek True ve pozitif int revision kabul edilir. Bu kontrol
  güvenilir resolver'ın yerini tutmaz; runtime'a yeni yetki yolu açılmaz.

Yeni testler düzeltme öncesinde bu sorunları gösterdi, sonrasında geçti.
`backend.tests.test_aaa_postgres_contract_boundaries` 4 yeni test;
doğrudan etkilenen metadata repository 8 ve owner contract 7 test;
`ProviderFencingTests` içinden replay ve source-fence için 2 test: **21 PASS**.
Fake-session testlerinde socket/psycopg/SQLite bağlantıları yasaktır. SQLAlchemy
PostgreSQL dialect derlemesi gerçek sunucu SQL yürütmesi veya transaction kanıtı
değildir. Yeni PostgreSQL driver/engine, resolver varsayımı veya schema DDL yok.

## Korunan sınırlar ve sonraki adım

HTTPS 200 ve kaynakta doğrulanmış `/api/ready` kimliği değişiklik öncesi/sonrası
başarılı. Yanıttaki `database_checked=false` nedeniyle DB sağlığı iddia edilmez;
DB sorgulayan `/api/health` çağrılmadı. Mevcut PG verileri/kullanıcılar okunmadı
ve değiştirilmedi. DB oluşturma/migration/DROP/TRUNCATE/DELETE/restore, servis
restartı, deployment, VDS veya gerçek router/RADIUS işlemi yapılmadı.

Sonraki gerekli girdi: önceden hazırlanmış, kimliği ve ownership'i kanıtlanmış
AAA şemalı izole kabul ortamı. Bunun yanında [resolver](AAA-MEMBERSHIP-RESOLVER-PLAN.md)
ve [writer](AAA-OWNER-WRITER-INTEGRATION-PLAN.md) ön koşulları tamamlanmalıdır.
Bu kayıttan yeni DB/migration veya mevcut veriye yazma izni türetilmez.

## Salt okunur yerel ortam envanteri — 2026-11-12

Başlangıç `main-guncel` / `64432d5`, temiz ağaç; GitHub SHA aynı.
**BLOCKED: kullanılabilir, önceden hazırlanmış izole AAA PostgreSQL ortamı
doğrulanamadı.** Kabul testleri çalıştırılmadı; yalnız bu rapor ve PROGRESS değişti.

| Ortam | Kimlik / profil kaynağı | Bu görevde doğrulanan durum |
| --- | --- | --- |
| AAA/V2.6 disposable kabul | `v26-isolated-acceptance`; beklenen `127.0.0.1:55433`, `mikrotik_v26_acceptance` / `v26_acceptance`; `/tmp/mikrotik-v26-acceptance`; `core/v26_acceptance.py` | Kök yok, host görünümünde 55433 dinleyicisi yok. DB/rol/marker/AAA şeması varlığı doğrulanmadı; kullanılamaz |
| Yerel V2 demo | Repo `.local/postgres-v2-demo`, PG16; beklenen `127.0.0.1:55432`, `mikrotik_manager_v2` / `v2_local` | Dizin var, symlink değil, UID1000 sahibi, PG_VERSION16. `pg_ctl status`: no server running; 55432 dinleyicisi yok. Mevcut demo korunur, AAA hedefi değildir |
| Sistem PostgreSQL | `postgresql@16-main.service`; `/var/lib/postgresql/16/main`; OS sahibi postgres; `127.0.0.1:5432` ve `/var/run/postgresql/.s.PGSQL.5432` | Hostta active/running, `pg_lsclusters` online. DB adları/roller/şemalar yetki nedeniyle okunamadı; ürün kimliği UNKNOWN, AAA hedefi değildir |
| Kaynakta tanımlı Cebeci V2 pilot | `CEBECI_VDS_PILOT_SETUP.md`; `/srv/mikrotik-manager-v2-pilot/postgres`; 55432, `mikrotik_manager_v2` / `v2_local` | Yalnız kaynak profili; uzak host sorgulanmadı. Yerel demo ile ad/port eşitliği aynı ortam olduklarını göstermez; PGDATA/host/rol sahibi farklıdır |
| Kaynakta tanımlı Fresh V2 pilot | `deploy/fresh-v2-pilot/profile.json`; `/srv/mikrotik-manager-v2-fresh-pilot`; 55442, `mikrotik_manager_v2_fresh_pilot`, `v2_fresh_owner` / `v2_fresh_app` | Yalnız kaynak profili; yerelde 55442 dinleyicisi yok. VDS doğrulaması/bağlantısı yapılmadı; AAA hedefi değildir |
| V2.5/eski pilot ve V1 | Korunan ayrı sistemler; `PILOT_LEGACY_UPGRADE_DECISION.md`, `V1_INVENTORY_HANDOFF.md` | Bu görevde kesin DB/host kimliği kanıtı yok. Cebeci/Fresh profilleri V2.5 ile eşitlenmedi; 5432 V1 veya V2.5 varsayılmadı. Kaynakları/kimlik bilgileri/servisleri açılmadı |

### Kanıtın kapsamı

- Sandbox `pg_lsclusters` çıktısı 16/main'i down/nobody gösterdi ve systemd/netlink
  erişimi reddedildi. İzinli salt okunur host kontrolünde cluster online/postgres,
  systemd active/running ve 5432 listener doğrulandı; servis kararı host çıktısına
  dayanır. Sandbox/host görünüm farkı ürün veya PostgreSQL arızası sayılmadı.
- Demo `postmaster.pid` dosyası 55432 ve ready içeriyor; `pg_ctl status` ve listener
  kanıtı bunun güncel çalışma kanıtı olmadığını gösteriyor. PID dosyası silinmedi;
  cluster başlatılmadı. PGDATA içerikleri veya yedekler taranmadı.
- Yerelde loaded `mikrotik*` service unit listesi boş; bu uzak servislerin yokluğu
  veya tüm installed unit'lerin envanteri değildir. 5432/55432/55433/55442 portları
  hedefli okundu; diğer portlarda DB olmadığı iddia edilmez.
- Repo `.env` ve `backend/.env` yok; süreçte hedeflenen V2/PG bağlantı anahtarları
  bulunmadı. `.local/runtime` ve `.local/deployment` doğrudan dosya listesi boş.
  Kaynak profil tanımları çalışan bağlantı veya DB katalog kanıtı değildir.
- Sistem cluster'ında `BEGIN READ ONLY` ile yalnız kimlik ve `pg_database`
  ad/sahip kataloğu amaçlandı; bağlantı `role "suat" does not exist` ile SQL'den
  önce reddedildi. Mevcut postgres OS kimliğiyle `sudo -n` denemesi parola istedi;
  sorgu çalışmadı. Parola istenmedi/okunmadı, rol/grant değişmedi, başka kimlik
  denenmedi. Bu nedenle tüm mevcut DB adlarını kesin ayırma kısmı BLOCKED.
- Zorunlu HTTPS200 ve doğrulanmış `/api/ready` `v26-acceptance` kimliği başarılı;
  `database_checked=false`. Uzak readiness yerel AAA DB varlığını veya DB sağlığını
  kanıtlamaz. VDS/router/RADIUS erişimi veya kabul testi yapılmadı; yerel
  PostgreSQL kimlik doğrulaması başarılı olmadı, SQL çalıştırılmadı.

### Kullanılabilir ortam için eksik koşullar

Önceden hazırlanmış hedefte exact loopback host/55433/DB/rol/profil ile private,
symlink olmayan owned PGDATA ve cluster kimliği birlikte kanıtlanmalı. Salt
okunur erişimle gerçek `current_database/current_user`, port/data_directory,
marker ve sürümlü AAA katalog/constraint/rol/RLS envanteri doğrulanmalı. Marker
ve port tek başına yeterli değildir; mevcut demo, sistem/V1/V2.5 veya pilot
veritabanı yeniden etiketlenemez. Runtime rolü ayrı ve sınırlı olmalı; credentials
Git/rapor dışında tutulmalı; provider yalnız fixture/mock ve dış etkiler kapalı
kalmalıdır. Membership kaynağı/freshness, owner metadata ve bütün writer'ların
ortak kilit sözleşmesine katılımı da ayrıca gereklidir.

Bu görev hazırlama yetkisi vermez: DB/rol/şema/servis oluşturma, migration,
DML/restore veya restart yoktur. Mevcut katalogların kesin envanteri için ayrıca
mevcut ve yetkili salt okunur erişim gerekir; bu erişim eksikliği giderilmeden
5432'ye ürün kimliği atanmaz. Kabul hâlâ kapalıdır.

## Ev WSL'de yeni AAA cluster ve gerçek metadata kabulü — 2026-11-12

Başlangıç `main-guncel` / `804ac7f`, temiz ağaç ve GitHub SHA aynı.
Bu görevde kullanıcı yalnız ev WSL'de yeni izole ortam oluşturmayı açıkça
yetkilendirdi; önceki envanter bölümünün oluşturma yasağı tarihsel kapsamdır.
**PASS: yeni ortamın izolasyonu ve aşağıdaki metadata PostgreSQL senaryoları.**
**BLOCKED: uygulamanın uçtan uca prepared/resolver/executor/receipt entegrasyonu.**

| Kimlik | Doğrulanan değer |
| --- | --- |
| Host | Ev WSL `DESKTOP-MT2JS7H`; Microsoft kernel + WSL_DISTRO_NAME; UID1000 ve repo sahipliği |
| PostgreSQL | Yeni PG16 cluster; system identifier `7707358750625226262` |
| PGDATA | `/tmp/mikrotik-v26-acceptance/postgres-test` |
| Ağ | Yalnız `127.0.0.1:55433`; private root içindeki Unix socket |
| Veritabanı | `mikrotik_v26_acceptance` |
| Test rolü | `v26_aaa_fixture`; superuser/CREATEDB/CREATEROLE/BYPASSRLS kapalı |
| Sahiplik | Root/PGDATA UID1000 ve0700; inode/device manifest eşit; symlink yok |
| Private varlıklar | Manifest ve yalnız bu yeni cluster'ın bootstrap parola dosyası0600; Git dışında |
| Son durum | Yalnız owned postmaster durduruldu; PGDATA korundu. pg_ctl no server running,55433 listener yok |

Yeni `backend.tests.run_aaa_postgres_wsl` runner'ı WSL/hostname/repo/owner/dal
kontrolünden sonra sabit portu bind ederek çakışmayı reddeder; mevcut kök varsa
yeniden kullanım yapmaz. OwnedRoot ve DisposableClusterGuard yeniden kullanılır.
İlk SQL yazımından önce TCP host/port, current_database/current_user, gerçek
data_directory ve process/PGDATA sahipliği doğrulanır. Runtime UoW her transaction'da
process, DB/rol/port ve rastgele fixture marker'ını tekrar kontrol eder.

Yalnız yeni DB'de test projeksiyon şemaları ve sentetik membership/owner kayıtları
oluşturuldu. `metadata.create_all` burada yalnız test projeksiyonları içindir;
kurulu ürün şemasına migration veya tam constraint/RLS tasarımı kabulü değildir.
Gerçek kullanıcı/abone, mevcut5432/demo veya VDS kaynağı kullanılmadı.

### Çalıştırılan gerçek PostgreSQL kapsamı

Runner tek sentetik akışta altı senaryoyu doğruladı: sınırlı runtime rolü; DB
clock_timestamp ile issue; audit CHECK hatası SQLSTATE23514 sonrası owner/action/
outbox/attempt rollback; önceden commit edilmiş fixture membership iptalinde ret;
owner revision/fence CAS ve single-use replay reddi; tek audit ile UNKNOWN receipt
ve HELD outbox atomik kaydı. Bunlar **6 senaryo**,6 ayrı unittest değildir.

Fixture üyelik okuması aynı session'da scoped SECURITY DEFINER SQL fonksiyonuyla
kilit alır: sabit schema-qualified tablo, search_path=pg_catalog, dinamik SQL yok,
PUBLIC execute kapalı. Runtime membership INSERT/UPDATE ve audit UPDATE yetkisi
almadı. Bu fonksiyon ürün resolver'ı değildir; authenticated actor/identity schema,
actor/policy freshness, cross-tenant RLS ve concurrent revocation kabulü eksiktir.

5 yeni soketsiz runner güvenlik testi PASS: yabancı host reddi, mevcut kök reddi,
port çakışmasında dosya oluşturmama ve Python optimize modunda kaldırılmayan kabul
kontrolü ve hazırlık öncesi harici PGOPTIONS/PGHOSTADDR ortamının temizlenmesi.
Önceki57/21 test veya ilgisiz HTTP/browser/build tekrarlanmadı.

### Giderilen harness sorunları ve korunan kanıt

İlk doğrudan dosya çağrısı import yolu nedeniyle dosya oluşturmadan durdu; doğru
giriş `PYTHONPATH=backend backend/.venv/bin/python -m backend.tests.run_aaa_postgres_wsl`.
İlk cluster denemesinde inet metninin host gösterimi assertion'ı durdurdu;
`host(inet_server_addr())` ile düzeltildi. Sonraki deneme PostgreSQL'in kilitli
SELECT için UPDATE yetkisi gereğini gösterdi. Yetkiyi gevşetmek yerine yukarıdaki
dar fixture fonksiyonu eklendi. Düzeltilen kabul exit0 ile tamamlandı.
Başarısız iki yeni cluster yalnız durdurulduktan ve sahiplikleri doğrulandıktan
sonra private `/tmp/mikrotik-v26-acceptance-failed-*` tanı dizinlerinde korundu;
mevcut/demo küme silinmedi veya yeniden adlandırılmadı. Kör tekrar yoktur.

### Açık entegrasyon kapıları

Prepared authorization ve executor decision/receipt registry'leri hâlâ memory
motorundadır; gerçek sürümlü payload validator ve PG execution/lease bağlayıcısı
yoktur. Bu kabulde payload `FIXTURE_TEST_ONLY` ve UNKNOWN receipt test verisidir;
gerçek prepared authorization/claim TTL veya bağımsız provider kabulü değildir.
Gerçek membership resolver, bütün günlük owner writers, final source commit,
FK/RLS/immutable audit, concurrency/durability/crash-recovery kabulü BLOCKED kalır.
Yeni fixture tablo/fonksiyonları bunları tamamlanmış saydırmaz.

Yeni cluster durdurulmuş olarak korunur; runner mevcut kökü reddeder. Güvenli
yeniden bağlanma/çalıştırma akışı ayrıca sahiplik ve cluster kimliğini doğrulamalı;
runner'ı tekrar çalıştırmak için dizin silme veya guard gevşetme önerilmez.
Sonraki teknik iş, ürün resolver ve sürümlü metadata bağlayıcısını bu izole
hedefe güvenli bağlamaktır. Canlı deployment veya mevcut DB migration izni yoktur.
Önce/sonra HTTPS200 ve API readiness başarılı; database_checked=false. Mevcut
servis restartı, canlı DB/VDS/router/RADIUS işlemi yapılmadı.

## Mevcut AAA kümesinde sürümlü PostgreSQL bağlayıcı kabulü — 2026-11-12

Başlangıç `main-guncel/d32e290`; GitHub SHA aynı ve ağaç temizdi. Çalışan
`7707358750625226262` / `127.0.0.1:55433` / `mikrotik_v26_acceptance` kimliği,
gerçek PGDATA, loopback listen adresi ve kayıtlı inode/device sahipliği salt
okunur doğrulandı. Yeni cluster oluşturulmadı, cluster başlatılmadı/durdurulmadı.

**PASS: yalnız izole, sentetik DI bağlayıcı ve aşağıdaki gerçek PG kabulü.**
**BLOCKED/kapsam dışı: normal panel/canlı günlük writer entegrasyonu ve dağıtım.**

| Bileşen | Gerçekleştirilen bağ |
| --- | --- |
| SessionMembershipResolver | Aynı session'da actor→membership kilit sırası; LOCAL origin, deployment stamp, aktiflik/rol/kapsam/capability ve ayrı actor/membership/policy revizyonları; bootstrap/login/env fallback yok |
| Typed checkpoint codec | Açık model allowlist'i, strict sürümlü JSON roundtrip, UUID/aware UTC/tuple/set desteği; pickle veya dinamik import yok |
| PostgresFixtureBridge | Mevcut domain servislerini private LeasedMemoryOutbox üstünde yeniden kullanır; varsayılan engine veya HTTP wiring yok. Yeni state machine oluşturulmadı |
| Prepared authorization | Gerçek PREPARED_EXECUTION_AUTH_V1_FIXTURE/plan/record; issue ve consume ayrı PG transaction'larında. Scope, TTL, single-use, generation ve owner CAS korunur; grant freshness proof'a bağlıdır |
| Owner/audit/outbox | Tek mevcut subscribers/events ve AAA operations/actions/attempts/outbox projeksiyonları kullanılır. Checkpoint ikinci owner/audit kopyası taşımaz; rehydration kanonik SQL kayıtlarından yapılır |
| Executor | Claim ve IN_FLIGHT checkpoint'i kalıcıdır. Dispatch öncesi DB clock lock sonrası yeniden okunur. Fake effect SQL transaction'ı dışında; response commit kaybında kalıcı IN_FLIGHT resend izni vermez |
| Receipt/decision | Gerçek sürümlü receipt atomik owner/journal/audit/outbox/attempt kabulüne bağlandı. UNKNOWN receipt immutable; bağımsız fake evidence ve ayrı yetkili karar aynı domain doğrulayıcılarından geçer |
| Günlük owner sözleşmesi | daily_touch yalnız fixture metadata revision/fence+audit işlemi; aktif AAA sırasında ret, kesin final receipt sonrası boş reservation üzerinde CAS. Normal panel save/renew/status akışları değiştirilmedi |

### Kabul kanıtı

`backend.tests.test_aaa_pg_bridge` içinde **11 farklı gerçek PostgreSQL testi PASS**:
prepared consume→claim→fake run→SUCCESS receipt, yeni unit/bridge ile yeniden
yükleme ve idempotent receipt; gerçek sunucu saatiyle authorization expiry;
concurrent consume tek kazanan/unused kaybeden; durable IN_FLIGHT ve kayıp cevap
sonrası UNKNOWN→evidence→yetkili decision; actor/membership/capability iptali;
scope/version/counter regression reddi; actor/policy epoch değişiminde eski grant
reddi; SQLSTATE23514 audit fault'unda owner/receipt/registry rollback ve fake
evidence'ın korunması; detached load sonrası süresi dolan attempt'in dispatch
edilmemesi; REJECTED ve UNKNOWN terminal kollarında LOCAL/reservation korunması.
UNKNOWN'dan otomatik başarı veya retry üretilmedi.

3 yeni soketsiz resolver/codec testi ve dispatch callback'ten doğrudan etkilenen
1 mevcut executor crash/timeout testi PASS. Toplam **15 farklı test** doğrulandı;
kod değiştikçe yalnız etkilenen kapsam tekrarlandı. Önceki57/21 suite, frontend
build, HTTP/browser kabulü çalıştırılmadı. Opt-in olmadan PG testleri skip olur;
skip sonucu PG PASS sayılmadı. Açık opt-in komutunda gerçek SQL çalıştırıldı.

Uçtan uca kabul başlangıcındaki predecessor chain sentetik mevcut servis
kurucularıyla memory'de üretilip explicit AAA_SEED yetkisiyle bir kez bootstrap
edilir. Bu önceki adımların tümünü PostgreSQL'de işletme kanıtı değildir.
Bootstrap sonrası yeni prepared issue/consume, claim/run/receipt ve decision
ayrı gerçek PG transaction'larında ve yeniden yüklenen typed state ile yürür.

### İzolasyon ve yetki sınırı

Test harness her transaction başında bootstrap bağlantısıyla exact cluster
kimliğini doğrular, sonra `SET LOCAL ROLE v26_aaa_fixture` uygular. Mevcut test
rolünün parolası/hesap ayarı değiştirilmedi; bu role parola ile login kabulü
iddia edilmez. Actor/membership için yalnız fixed, schema-qualified, dar SECURITY
DEFINER okuma fonksiyonları kullanılır; PUBLIC execute kapalıdır. Gerçek ürün
kullanıcı tablosu yerine yalnız izinli `v2_aaa` içindeki sentetik actor/membership
kayıtları vardır. Eski fixture kayıtları silinmedi; ek kolonların NULL değerleri
fail-closed reddedilir. Actor kaynağı normal panel kimliğiyle eşitlenmez.

Yalnız kimliği doğrulanmış AAA şemalarında sentetik DDL/DML yapıldı; audit fault
constraint'i sadece kendi fixture tenant'ına uygulandı ve finally kaldırıldı.
Gerçek router/RADIUS yerine yalnız exact FakeFencedProvider kullanılır. Fake
provider process-local kaynak kimliğine bağlıdır; process restartı veya gerçek
provider durability/remote fencing/dağıtık exactly-once kabulü değildir.
Runtime RLS/FK/immutable DB grant sertleştirmesi, tüm gerçek günlük writer'lar,
gerçek authenticated identity adapter'i ve crash/restore kabulü hâlâ ayrı kapıdır.

Mevcut panel başlangıçta ve sonda `127.0.0.1:5173`, aynı PID4363, HTTP200 doğrulandı;
dev.sh veya panel/API süreçlerine sinyal/restart gönderilmedi. Demo DB'ye bağlantı
yapılmadı. Mevcut5432, V1/V2.5/VDS/canlı V2.6/gerçek cihazlar korunur.
AAA55433 pg_isready accepting connections; önce/sonra HTTPS200 ve API readiness
başarılı. HTTPS readiness DB health kanıtı değildir.
Sıradaki iş gerçek runtime wiring'i için ayrı şema/identity/writer ve rol-RLS
kabulüdür; bu izole PASS normal panelde AAA dispatch açmaz.

## Panel entegrasyonu için kapalı adaptör hazırlığı — 2026-11-12

Başlangıç `main-guncel/0bbc747`; temiz ağaç ve GitHub HEAD eşitliği doğrulandı.
**PASS: varsayılan kapalı, yalnız seçilmiş sentetik DI panel sınırı ve10 yeni test.**
Önceki11 PostgreSQL kabul senaryosu/bağlayıcısı yeniden geliştirilmedi veya
çalıştırılmadı. Bu görevde PostgreSQL bağlantısı, SQL veya gerçek login yoktur.

### Kod üzerinden incelenen panel akışları

- `core/security.py`: opaque session ve current_demo_user her istekte aktif
  kimliği yeniden okur. current_admin ADMIN/can_manage_users/is_demo kontrolüyle
  aynı user dict'ini döndürür. `identity.public_user` account_origin ile is_demo
  çevre bayrağını ayırır; LOCAL/seal/login bilgisi birlikte değerlendirilir.
- `identity.find_user` ayrı connection ve bootstrap fallback içerir; AAA UoW
  resolver'ı yerine çağrılmadı. Gerçek cookie/login adapter'i enjekte edilmedi.
- Workspace route'ları merkezi ADMIN + sentetik işlem header'ı kullanır;
  save/renew ve operations.change revision/source/router ve transaction/row lock
  kontrol eder. Bunlar ve mevcut AAA preview route'u değiştirilmedi.

### Yeni adaptör ve yetki sınırı

`services/aaa_panel_adapter.py` içinde PanelAaaAdapter varsayılan olarak kapalıdır.
Ortam değişkeniyle açılamaz. Yalnız enabled=true seçilmiş fixture configuration,
explicit actor/subscriber allowlist'i, tenant/deployment/worker bağı ve injected
isolation guard ile kullanılabilir. Guard backend'e erişmeden önce çalışır.
Default factory, engine, SessionLocal, identity reader, router veya API mount yok.
Normal startup/router/core/writer dosyalarında adaptör import'u bulunmadığı kod
üzerinden doğrulandı. Gerçek kullanıcı/abone kaynağına bağlanmadı.

Her çağrıda trusted opaque fixture session okuyucusu, merkezi admin policy,
server owner binding ve ayrı PanelFixtureAccess tekrar okunur. LOCAL/sealed/aktif
kimlik, ADMIN, doğru tenant/owner/router/request ve seçilmiş fixture aktörü gerekir;
is_demo tek başına kimlik veya yetki değildir. Merkezi policy'nin False/None dönüşü
reddedilir. ADMIN ayrı AAA issue/consume/execute/accept/timeout yetkisi sağlamaz.

Prepared plan server tarafında mevcut PreparedExecutionService ile hesaplanır;
grant/command/receipt strict JSON sözleşmesi ve scope tekrar doğrulanır. Adaptör
PostgresFixtureBridge'in invoke/run portuna uyar; AAA_PREPARE/AAA_EXECUTE ve
ServerPrincipal/PreviewScope bağını korur. Membership çözümleme backend'de kalır,
adapter tarafında cached grant veya ikinci registry/state machine oluşturulmaz.
Run ayrı durable dispatch yoluna gider; consume provider çalıştırmaz.

UNKNOWN ve timeout salt ayrı açık yetkiyle mevcut receipt motoruna gider.
UNKNOWN otomatik SUCCESS/decision/retry/telafi üretmez. Geç kesin receipt çatışma
olarak kalır; geçerli exact receipt tekrarı idempotenttir, ikinci execution değildir.
Yeni adaptör normal writer çağırmaz, domain TTL/fence/single-use kapısını gevşetmez.

### Hedefli kabul

10 yeni soketsiz fixture testi PASS: default/env ile açılmama ve guard sırası;
unauthenticated/DEMO/bootstrap/VIEWER/inactive/truthy flag/merkezi policy reddi;
yanlış owner/tenant/router/actor/request; açık sentetik başarı ve receipt replay;
expired prepared grant; ADMIN'den ayrı izin ve fresh panel identity; membership
iptali; UNKNOWN no-retry/no-promotion; foreign grant/command/receipt; ayrı timeout
izni/expiry ve late receipt conflict. Test backend'i gerçek domain servisleri ve
SessionMembershipResolver ile çalışır; PG transaction motorunu yeniden sınamaz.
Socket/psycopg/SQLite girişleri testte yasaktır. Son iki kapı değişince yalnız bu
yeni10 test tekrarlandı ve geçti. İlgisiz build/browser/PG kabulü çalıştırılmadı.

Kalan BLOCKED sınırı değişmedi: gerçek session-aware identity kaynağı, tüm panel
writer'larının ortak AAA kilidine katılımı, runtime şema/rol/RLS ve canlı wiring
kabulü. Bu kayıt canlı entegrasyon, migration veya dispatch izni değildir.
HTTPS200 ve doğrulanmış API readiness ön/son başarılı; gerçek panel veya dev.sh
süreçlerine müdahale edilmedi. Hazırlık yalnız yeni servis modülü/test ve belgedir.

## Ofis WSL runner hazırlığı — 2026-11-13 — PG kabulü BLOCKED

Başlangıç main-guncel/bdb3a44, temiz ağaç ve üç stash korundu. Önceki ev PG
PASS sonuçları ofis kabulü olarak sunulmadı. Bilinen sandbox socket EPERM
tekrarlanmadı; gerçek cluster/initdb/start/SQL/11 PG testi bu oturumda çalışmadı.

`backend.tests.run_aaa_postgres_office_wsl` exact Office host
DESKTOP-VD5T7VG, repo /home/suatpc/Codex-Projects/mikrotik-manager-v2, repo .venv,
WSL/UID/sahiplik, temiz main-guncel ister. Ev host/path guard'ı değiştirilmedi.
Mevcut provisioner'ın yok-root ve boş55433 kontrolleri, OwnedRoot/PGDATA inode/
UID/PG16, private credential, loopback DB/rol ve cleanup protokolü yeniden kullanılır.
Mevcut /tmp/mikrotik-v26-acceptance varsa reuse/delete/restart yok; BLOCKED.
Mevcut servis/DB değişmez; oluşturulan kendi test postmaster'ı finally durdurulur,
private test dosyaları korunur. Kullanıcı açık izni yalnız yeni izole AAA ortamıdır.

Provisioner'a optional bridge callback eklendi. Kimliği doğrulanmış private
PGDATA bağlantısından gelen gerçek system_identifier callback'e aktarılır;
ENV/CLI cluster-ID veya DSN override yoktur. Aynı 11 PostgresBridgeAcceptance
senaryosu Office subclass'ında çalışır; ev sınıfının varsayılan pinned kimliği
korunur. Skip, test sayısının11 olmaması veya herhangi failure PASS üretmez.
İlk setup'ta mevcut metadata_probe test şeması/rol altyapısını kurar; normal
ürün migration'ı veya mevcut DB'ye şema yüklemesi değildir. Provider exact fake,
normal panel writer/gerçek identity/API wiring kapalı kalır.

PASS yalnız 5 yeni office runner safety +5 doğrudan etkilenen provisioning safety
soketsiz testidir. Mock'lar sadece guard/provision çağrısının engellendiğini sınar;
PG başarısı üretmez. Önceki13 panel/resolver veya11 gerçek PG testi tekrarlanmadı.
Bağımlılıklar önceki ofis kontrolünde hazırdı; yeni paket/servis kurulmadı.

**PG BLOCKED:** sandbox socket yetkisi yok; cluster oluşturulmadı, kullanıcı/
servis/DB katalog sağlığı bağımsız doğrulanmadı. **Push BLOCKED:** tek git fetch
origin main-guncel denemesi Could not resolve host: github.com verdi; geçmiş
uyumu/uzak SHA doğrulanamadığı için push denenmez. Yerel güvenli commit korunur.

Normal Ofis WSL terminalinde, temiz main-guncel ve socket yetkisi olan ortam için
tek açık runner komutu (mevcut root/port engelinde durur; otomatik reuse yok):

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2 && PYTHONPATH=backend .venv/bin/python -B -m backend.tests.run_aaa_postgres_office_wsl
```

Gerçek11 PG sonucu ve uzak HEAD eşitliği görülmeden uçtan uca ofis/push PASS
verilemez. Port veya root engelinde mevcut veri/servis temizleme yapılmamalıdır.

## OFFICE_WSL_IDENTITY_REJECTED düzeltmesi / mevcut cluster — 2026-11-13

Normal Ofis terminalindeki yeni hata esas alındı. Kök neden: main'in ilk ofis
guard'ından sonra `_isolated_runtime()` WSL_DISTRO_NAME değişkenini siliyordu;
PostgresBridgeAcceptance.setUpClass ikinci office_guard çağrısında kimliği
reddediyordu. Before/inside-isolation marker farkı soketsiz yeniden üretildi.
Office runtime şimdi yalnız önceden doğrulanmış aynı WSL marker'ını korur;
libpq/loader/harici ayarlar hâlâ temizlenir. Host/path/venv/UID/kernel/branch ve
clean-worktree kontrollerinin hiçbiri kaldırılmadı.

Salt okunur pg_controldata, private manifest/PG_VERSION/inode/UID kontrolüyle
mevcut Ofis cluster **7707521885424832975**, durum **shut down** doğrulandı.
Bu SQL/katalog/servis accepting-connections kanıtı değildir. Manifestin
HOME_WSL_AAA_FIXTURE purpose etiketi ortak provisioner'daki hardcoded değerden
kaynaklanıyor; bilgisayarın ev ortamı olduğunu ispatlamıyor. Eski manifest
**değiştirilmedi**. Yeni ofis provisioning çağrısı explicit OFFICE_WSL_AAA_FIXTURE
etiketi üretir; ev varsayılanı aynı kalır.

`--existing` yalnız bu sabit Ofis cluster ID'si, exact Office host/repo/.venv ve
private PGDATA/manifest/password/socket/log/config sınırlarıyla çalışır.
Env/CLI ile başka cluster seçilemez. PG16 controldata kimliği, manifest sahiplik
ve sabit DB/port/rol kontrol edilir; include/recovery/preload/harici config
indirection reddedilir. Historical HOME label yalnız bu exact pinned cluster'ın
manifestinde kabul edilir; label kimlik kontrolünün yerine geçmez.

Mevcut cluster silinmez/re-init edilmez; initdb veya metadata_probe çağrılmaz.
Şu an durmuş olduğu için socket izinli normal WSL'de verified existing cluster
başlatılıp aynı11 gerçek PG bridge testi çalışır. Test öncesi her transaction
SQL'de DB/PGDATA/port/listen/system ID doğrular; test DDL/DML yalnız AAA sentetik
şemalarına aittir. Bu ürün migration'ı değildir. Runner yalnız kendisinin
başlattığı verified PID'yi finally durdurur; cluster zaten çalışıyorsa stop/restart
göndermez. Önceki stopped/running durumu korunur; dosyalar/credential/manifest
silinmez. Beklenmeyen config/root/kimlikte fail-closed durur.

PASS:19 farklı soketsiz guard testi (önceki düzeltmede15, mevcut mode için4 yeni).
Existing mode provision çağırmama, wrong ID/guard öncesi start engeli, sabit ID,
çalışan/durmuş lifecycle ve failure cleanup kontrol edildi. Bunlar gerçek PG
PASS üretmez. Gerçek11 PG senaryosu sandbox socket engeli nedeniyle çalışmadı;
engel tekrar denenmedi. Mevcut cluster tüm bu oturum boyunca shut down kaldı.

Normal **Ofis WSL terminalinde**, temiz main-guncel için tek kabul komutu:

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2 && PYTHONPATH=backend .venv/bin/python -B -m backend.tests.run_aaa_postgres_office_wsl --existing
```

GitHub senkronizasyonu BLOCKED: fetch origin main-guncel DNS çözümlemesinde
durdu; güncel uzak ancestry doğrulanamadığından normal push yapılmadı.
Gerçek11 test PASS'i veya GitHub SHA eşitliği iddia edilmez.

## Ofis kalıcı sentetik AAA okuma entegrasyonu — 2026-11-13

- Kullanıcı yalnız yeni boş sentetik cluster için açık onay verdi. Hedefli
  aramada eski /tmp AAA cluster/manifest/yedek bulunmadı; mevcut .local demo
  PostgreSQL korunur. İnceleme erişilebilir repo/.local/share/tmp kapsamındadır.
- Yeni sabit, Git dışı konum .local/aaa-office-fixture; private owner/inode,
  manifest+PG16 system ID, loopback55433 ve exact DB/rol kontrolleri korunur.
  Dolu root/port reddedilir; silme/restore/re-init veya servis kurulumu yoktur.
  --existing kalıcı manifest kimliğini doğrular; eksik root artık sabit
  PERSISTENT_FIXTURE_MISSING verir. WSL tmp temizliği yeni konumu etkilemez.
- Boundary typed AtomicRequest sahibini projekte eder; gate PreviewScope ve
  ServerPrincipal sözleşmeleriyle bridge.read çağırır. Bridge içinde aynı
  transaction actor/member kilidi ve owner/journal revision kontrolü korunur.
  Gerçek writer execute daima kapalıdır; normal API wiring yapılmaz.
- Yalnız bir hedefli gerçek PG okuma kabulü seçildi: başarılı okuma, kimlik/izin
  iptali, tenant reddi, inspection sonrası iptal/sahiplik yarışı, writer reddi
  ve provider/veri değişmezliği. Önceki11 PG test paketi çalıştırılmaz.
  Yeni ortamda yalnız sentetik şema bootstrap edildi; eski metadata senaryoları
  tekrar çalıştırılmadı. PASS: 1 gerçek PG testi / 0.325s, skip/failure yok.
- HTTPS200 ve /api/ready runtime_profile=v26-isolated-acceptance ön kontrolü
  geçti. Canlı deploy/migration/restart, V1/V2.5/router/RADIUS/IPsec değişmez.
- Yeni cluster system ID 7707635612888176393; runner yalnız kendi başlattığı
  süreci durdurdu. Son salt okunur verify_existing_files kontrolü private
  manifest/config/PG16 kimliğini ve shut down durumunu doğruladı. WSL reboot
  fiilen denenmedi; kalıcı konum ve --existing ön koşulları doğrulandı.
- Son HTTPS200 ve aynı API runtime_profile kapısı geçti. .local/ Git ignore
  doğrulandı; private parolalar/cluster içeriği Git'e alınmadı. Üç stash korundu.
  Görev kapsamındaki izole okuma kabulü PASS; gerçek runtime/writer açılmadı.
- Sonraki sentetik kullanım aynı Ofis WSL'de mevcut mod ile yapılır:
  `PYTHONPATH=backend .venv/bin/python -B -m backend.tests.run_aaa_postgres_office_wsl --existing`.
  Bu görevde başarılı test tekrar çalıştırılmadı; servis kurulumu/otomatik başlatma yok.

## AAA sentetik abone komutları / PostgreSQL audit-receipt — 2026-11-13 — izole PASS

- Başlangıç güncel main-guncel/bd01a52; temiz ağaç ve fetch sonrası uzak eşitlik
  doğrulandı. Önceki panel iyileştirmeleri, üç stash ve bf2ad12 okuma sınırı korundu.
- Mevcut integration_preparation içinde strict versioned command/account/receipt
  sözleşmeleri: CREATE/EXTEND/PLAN/STATUS, tenant/actor/router/subscriber/source,
  UUID, önceki/yeni değer, revision/fence ve açık bool onayı. Sır/credential alanı
  yoktur. FakeFencedProvider aynı yapı içinde yalnız saf sentetik etki hesaplar.
- PostgresFixtureBridge yeni subscriber_change/subscriber_result yöntemleriyle
  mevcut tek owner/audit tablolarını kullanır. İkinci owner deposu, yeni tablo,
  migration, endpoint veya normal subscriber store bağlantısı yoktur. Hesap
  özellikleri ve kanonik receipt mevcut audit'ten yeniden okunur. UUID fingerprint
  çatışması, audit/receipt sapması ve owner/revision/source değişimi reddedilir.
- CREATE yalnız önceden açıkça ayrılmış sentetik owner slotunda AAA hesap
  projeksiyonu oluşturur; gerçek panel abonesi/kullanıcısı oluşturmaz. Aynı tenant/
  router/username için transaction advisory lock ve namespace sahipliği kontrolü
  vardır. Gerçek LOCAL/RADIUS kimlik kaydı veya credential provisioning yapılmaz.
- Actor→membership→namespace→owner kilit sırası; fresh ADMIN, açık işlem izni,
  DAILY_OWNER ve AAA_ROUTER:<id> grant zorunludur. Owner revision+fence CAS ve
  audit INSERT aynı transaction'dadır. Aktif kaynak devriyle günlük işlem
  çakışamaz. Saf fake etkide audit hatası tüm işlemi geri alır; bu garanti gerçek
  uzak sağlayıcıya taşınmış sayılmaz. Üretim UNKNOWN/reconciliation kabulü ayrıdır.
- PanelAaaAdapter varsayılan kapalı kalır; ayrı can_manage_subscriber ve
  can_read_subscriber izinleri eklendi. Merkezi identity boundary ile read gate
  yeniden kullanılır; PG aynı transaction'da tekrar yetkilendirir. RADIUS kaynağı
  açık ve doğrulanmış binding ile desteklenir; varsayılan read boundary LOCAL
  davranışı değişmez. Boundary.execute hâlâ koşulsuz kapalıdır.
- RouterOS/FreeRadius mevcut Protocol'lerine açık apply_subscriber sözleşmesi
  eklendi. V1 fixture-only komut canlı izin değildir; gelecekteki canlı adaptör
  bunu reddetmelidir. Gerçek dispatch için ayrıca kabul edilmiş provider sürümü,
  runtime identity/şema/RLS hardening, credential/NAS/profile eşleme ve gerçek
  provider hata/timeout/reconciliation kabulü gerekir. Bunlar tamamlanmadı;
  AAA üretim entegrasyonu veya tüm ürün AAA'sı bitmiş olarak raporlanmaz.
- PASS: mevcut kalıcı izole PG'de tek hedefli test, 0.759s / 1 test / skip yok.
  İki kaynakta dört işlem, UUID replay/çatışma ve salt okunur receipt recovery,
  varsayılan kapalı panel, panel kimlik/izin reddi, PG actor aktiflik/rol reddi,
  inspection sonrası üyelik/owner source değişimi, yabancı tenant/router reddi,
  gerçek PostgreSQL 22012 audit hatasında rollback, iki rakip komuttan yalnız
  birinin kaydı, kanonik receipt ve tamper reddi doğrulandı. Önceki11 PG/read/
  panel/frontend test paketleri tekrar çalıştırılmadı; yeni test dosyası yok.
- Runner --existing --subscriber-writes yalnız yeni kabulü seçer; mevcut fixture
  şemasını salt okunur kontrol eder, DDL veya provision çağırmaz. Testin ürettiği
  yeni UUID'li actor/member/owner/audit kayıtları dışında eski kayıtlar değişmez.
  Yeni cluster/servis, restore/reset/silme yoktur. Kendi başlattığı izole postmaster
  finally durduruldu; private manifest/config/PG16 ve shut down durumu son
  salt okunur kontrolde doğrulandı. Veri ve parolalar .local/ altında Git dışıdır.
- Ön/son HTTPS200 ve /api/ready runtime_profile=v26-isolated-acceptance geçti.
  V1/V2.5/canlıV2.6, gerçek router/RADIUS/IPsec, mevcut demo abone/kullanıcı/DB,
  deploy/migration/servis restartı değişmedi. Güvenli kod ve belge normal commit/
  push kapsamındadır. Sonraki iş yalnız ayrı onaylı gerçek entegrasyon kabulüdür.
