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
