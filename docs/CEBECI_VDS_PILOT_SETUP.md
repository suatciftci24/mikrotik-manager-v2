# CEBECI_TOWERS: kapalı VDS pilot kurulum paketi

## NPM_CHECK_FAILED: npm config kaynağı çakışması

0046518'de bu generic kod yalnız `npm --version` çağrısının başarısızlığıdır;
`npm ls` check=False olduğundan aynı rc hatası terminale bu kodla çıkmaz.
Dolayısıyla Node22/24 filtresi geçilmiş, henüz frontend npm ci/build yapılmamıştır.
Exact VDS sürüm ve raw hata metni bu oturumda alınmadı. API servisinin PATH'i
burada kullanılmaz: build root ve explicit PATH ile, API ise Python/uvicorn ile
çalışır. Bu görev servis veya global PATH değiştirmez.

Kesin betik kusuru: userconfig ve globalconfig aynı `/dev/null` kaynağıydı.
[npm10 config loader](https://github.com/npm/cli/blob/v10.9.2/workspaces/config/lib/index.js)
ve [güncel resmi kaynak](https://github.com/npm/cli/blob/latest/workspaces/config/lib/index.js)
aynı dosyanın farklı seviyelerde ikinci kez yüklenmesini reddeder. Config
yükleme npm --version için de yapılır. Çakışma eski sınıflandırmada generic
NPM_CHECK_FAILED olarak gizleniyordu. Yerelde Node/npm bulunmadığından gerçek
CLI reprodüksiyonu iddia edilmiyor; kaynak/env/aşama kanıtı ile kusur belirlendi.

Güncellenmiş isolated-build.py iki ayrı boş dosyayı root/0600 olarak yalnız
V2 build-home altında oluşturur: npm-user.npmrc ve npm-global.npmrc. Mevcut
nonempty/config link/mode çakışması STOP verir; credential dosyaları ezilmez.
Global npmrc veya sistem Node/npm değiştirilmez. npm sürüm sorgusu artık private
build-home cwd'sinde yapılır; seçilen Node bin'i yalnız child PATH'inin başına
eklenir. Sayısal Node/npm sürümleri ve seçilen public executable yolları yazılır;
raw stdout/exception/env dump yoktur. Repo frontend lock v3/root manifest eşleşmesi
salt okunur doğrulanmıştır; mevcut lockfile değiştirilmez.

Yeni ayrımlar: `V2_BUILD_NPM_VERSION_CONFIG_SOURCE_COLLISION`,
`CLI_MODULE_MISSING`, `PATH_NODE_MISSING`, `RUNTIME_SYNTAX_ERROR`,
`RUNTIME_INCOMPATIBLE`, `OUTPUT_INVALID`, `LOCKFILE_UNSUPPORTED`;
lock tarafında `V2_BUILD_NPM_LOCKFILE_VERSION_UNSUPPORTED`, `ROOT_MISSING`,
`MANIFEST_MISMATCH` ve ci'de `V2_BUILD_NPM_INSTALL_LOCKFILE_OUT_OF_SYNC`.
Diğer izin/ağ/disk kodları korunur. Eski NPM_CHECK evresi şimdi NPM_VERSION,
tree denetimi NPM_TREE'dir. VDS'ye güncellenmiş helper kaydedilince tek uygulama:

```bash
sudo python3 ~/isolated-build.py
```

Bu oturumda VDS kabulü uygulanmadı; düzeltmenin gerçek VDS sonucu henüz BLOCKED.
PostgreSQL, migration, kullanıcılar ve V1/router/RADIUS/IPsec kapsam dışıdır.

## İzole bağımlılık ve build onarımı

Son kullanıcı kanıtı: ADMIN preflight PASS, sonra eski installer'da
`isolated-dependencies-and-build` BLOCKED. Bu genel çıktı hangi alt komutun
başarısız olduğunu göstermez; VDS'de pip/Node veya ağın kesin neden olduğu
söylenemez. Başarılı PG/migration/preflight işlemleri tekrar yapılmaz.

Standalone `deploy/cebeci-v2-pilot/isolated-build.py` VDS'de
`~/isolated-build.py` olarak kaydedildikten sonra tek onarım komutu:

```bash
sudo python3 ~/isolated-build.py
```

Komut yalnız mevcut /srv/mikrotik-manager-v2-pilot/app, venv, toolchain,
build-home/cache, frontend/node_modules/dist ve build marker'ı kapsamında
çalışır. DB/kimlik/ADMIN, servis veya source-deployment işlemi yapmaz.
Parola istenmez. Mevcut owner/type/link/write korumaları gevşetilmez; yalnız
managed root-owned dependency ve build ağaçları servis için okunabilir yapılır.
Private app/.local, config ve postgres yollarına dokunulmaz.

Venv eksik/yarımsa `venv --without-pip`; pip eksikse [resmi PyPI pip wheel
metadata'sı](https://pypi.org/pypi/pip/json) ve SHA-256 kontrolü kullanılır.
Bu, Ubuntu ensurepip OS paketi olmadan da pip'i yalnız V2 venv'ine kurar.
Global site-packages reddedilir; Python paketleri yalnız venv içine, resmi
PyPI'dan binary wheel olarak kurulur. Zaten karşılanan bağımlılıklar zorla
yükseltilmez. Standard venv modülü veya temel OS kütüphanesi yoksa global
OS paketleri değiştirilmez; ayrı BLOCKED kodu verilir.

Node/npm eksik veya mevcut Node uyumsuzsa [resmi Node dağıtımları](https://nodejs.org/en/download)
içinden Node24 LTS, HTTPS + SHASUMS256 kontrolüyle yalnız V2 toolchain'ine
alınır. Global Node/npm veya sistem PATH'i değiştirilmez. Mevcut uyumlu 22/24
çifti veya daha önce hazırlanmış V2 toolchain'i yeniden indirilmez. npm lock
metadata'sı + npm ls doğrulaması geçerse node_modules korunur; aksi halde yalnız
bu frontend'de npm ci çalışır. Install/prebuild/postbuild lifecycle hook'ları
kapalıdır; onaylı `tsc -b && vite build` komutu açıkça çalıştırılır. Başarı marker'ı
ancak pip check ve tamamlanmış HTML build sonrasında yazılır; eski installer'ın
başarılı build'i tanıdığı source hash korunur. Kimlik oluşturma veya panel start
bu onarım komutunun parçası değildir.

| Kod ailesi | Anlamı |
| --- | --- |
| `V2_BUILD_PY_VENV_*` | venv modülü/create veya izin hatası |
| `V2_BUILD_PY_BOOTSTRAP_*` / `PIP_CHECKSUM_REJECTED` | pip wheel indirme/kurma/doğrulama |
| `V2_BUILD_PY_INSTALL_*` / `PY_CHECK_*` / `PY_SCOPE_*` | Python paketleri, dependency check veya yanlış venv |
| `V2_BUILD_NODE_DOWNLOAD_*` / `NODE_CHECK_*` / `NPM_CHECK_*` | Node/npm edinme, eksik executable, uyum veya sistem kütüphanesi |
| `V2_BUILD_NPM_INSTALL_*` | İzole npm ci hatası |
| `V2_BUILD_FRONTEND_TYPESCRIPT_FAILED` / `VITE_FAILED` / `PLATFORM_PACKAGE_MISSING` | Build/TypeScript veya platform binary paketi |
| `*_NETWORK_DNS` / `NETWORK_TLS` / `NETWORK_TIMEOUT` / `NETWORK_UNREACHABLE` | Ayrı ağ nedenleri; otomatik retry/SSL bypass yok |
| `*_PERMISSION_DENIED` / `*_OWNER_MISMATCH` / `*_WRITABLE_BY_OTHERS` / `*_SYMLINK_REJECTED` | İzin/sahiplik/link koruması; güvenlik gevşetilmez |
| `*_DISK_FULL` / `*_PROCESS_KILLED` | Disk dolu veya sinyal ile biten işlem; OOM olduğu varsayılmaz |
| `V2_ISOLATED_DEPENDENCIES_AND_BUILD_READY` | Yalnız dependency/build PASS; ADMIN/panel kurulduğu anlamına gelmez |

Subprocess çıktıları yalnız bellekte sınıflanır; terminale sır/DSN/hash veya raw
pip/npm error dump yazılmaz. Bilinmeyen hata aşamasıyla `*_FAILED` olarak durur.
Bu görevde gerçek VDS onarımı çalıştırılmadı; kesin alt neden hâlâ doğrulanmadı.

## Yalnız V2 üst dizin sahibi düzeltmesi

Gerçek `V2_PREFLIGHT_BASE_OWNER_MISMATCH` kodu yalnız base UID'nin root/0
olmadığını kanıtlar; belirli bir eski UID veya izin değeri göstermez. Preflight
base için root/0755 ister; grup koşulu yoktur. Kontrol gevşetilmez.

Standalone `deploy/cebeci-v2-pilot/fix-base-owner.py` VDS'de
`~/fix-base-owner.py` olarak kaydedildikten sonra tek komut:

```bash
sudo python3 ~/fix-base-owner.py
```

Betik eski UID/GID/mode'u güvenle gösterir, yalnız base inode sahibini gerektiğinde
root yapar, grubu korur ve yalnız gerekirse 0755 uygular. /srv parent sahiplik/
write kontrolü ve no-follow descriptor'ları path değiştirme/symlink riskini kapatır.
Önce mevcut V2 DB OS hesabı, postgres/postgres-socket owner/0700 ve PG_VERSION=16
doğrulanır; eksik/yanlış olduklarında STOP verir, bunları değiştirmez. PG metadata
önce/sonra ve base inode tekrar doğrulanır. Recursive işlem veya alt dizin/file
chown/chmod yoktur; database/user kayıtları okunmaz/değiştirilmez. SQL, migration,
servis, SSH/router/RADIUS/IPsec çağrısı yapmaz. Yalnız public metadata ve sabit
durum kodları yazılır. Başarılı sonuç base koşulunu doğrular; ADMIN veya panelin
kurulduğu anlamına gelmez. Bu oturumda VDS uygulaması henüz yapılmadı.

## Preflight teşhisi — genel hata mesajının yerine güvenli kodlar

58768e6 installer'ındaki `BLOCKED: preflight; existing identities never reset`
çıktısı DB bağlantısından önceki kontrollerden birinin durduğunu gösterir; mevcut
ADMIN veya başka kullanıcı bulunduğunun kanıtı değildir. Root/optimize, staging
yolu/dosyaları, OS hesapları, base/data/socket owner/mode kontrolleri eski sürümde
aynı mesajı üretiyordu. Gerçek VDS metadata olmadan bunlardan biri seçilemez.

Yeni standalone dosya `mikrotik-v2-native-admin-preflight.run` adıyla VDS'ye
kaydedilince tek salt okunur teşhis komutu:

```bash
sudo bash ~/mikrotik-v2-native-admin-preflight.run --preflight-only
```

Bu seçenek kaynak arşivi için private staging dışında yönetilen dosya/DB/servis
değiştirmez. Eksik hesabı/config'i otomatik yaratmaz veya izinleri gevşetmez;
migration, seed, ADMIN oluşturma, parola isteme/reset, bağımlılık kurma veya API
start yoktur. Normal kurulum seçeneği de var olan ADMIN/diğer kullanıcıda durur.

| Güvenli kod | Kanıtlanan engel |
| --- | --- |
| `V2_PREFLIGHT_DB_OS_USER_MISSING` | mikrotik-v2-db OS hesabı yok; DB'ye henüz bağlanılmadı |
| `V2_PREFLIGHT_BASE_*` | /srv/mikrotik-manager-v2-pilot eksik/type/owner/mode reddi; root/0755 beklenir |
| `V2_PREFLIGHT_PGDATA_*` / `PGSOCKET_*` | postgres veya postgres-socket yolu reddi; DB OS sahibi/0700 beklenir |
| `V2_PREFLIGHT_STAGE_*` / `ARCHIVE_*` / `NATIVE_SOURCE_*` / `COMPLETION_SOURCE_*` | Kaynak staging/dosya reddi; mikadmin, directory 0700/file 0600, no-link/nlink=1 |
| `V2_DB_PSQL_BINARY_MISSING` / `RUNUSER_BINARY_MISSING` | İzole bakım bağlantısı için program eksik |
| `V2_DB_SOCKET_UNAVAILABLE` / `CONNECTION_REFUSED` / `PEER_AUTH_FAILED` | Socket/bağlantı veya peer eşlemesi engeli |
| `V2_DB_ROLE_MISSING` / `V2_DATABASE_MISSING` / `V2_DB_SCHEMA_MISSING` | Beklenen rol/DB/şema bulunamadı; onarılmaz |
| `V2_DB_MAINTENANCE_PERMISSION_DENIED` / `PERMISSION_DENIED` | Bakım rolü gerekli işlemi yapamıyor; yetki otomatik genişletilmez |
| `V2_NATIVE_EXISTING_ADMIN_STOP` | En az bir ADMIN var; değişiklik yok |
| `V2_NATIVE_OTHER_USERS_STOP` | ADMIN yok fakat başka kullanıcı var; değişiklik yok |
| `V2_NATIVE_SETUP_CLOSED_STOP` / `SEAL_PRESENT_STOP` / `AUDIT_PRESENT_STOP` | Daha önce kapanmış/boş olmayan kurulum; reset yok |
| `V2_NATIVE_SETUP_STATE_REJECTED` | Beklenen açık modern şema marker'ı bulunamadı |
| `V2_NATIVE_PREFLIGHT_READY_NO_USERS_SETUP_OPEN` | Salt okunur ön kontrol PASS; ADMIN oluşturulmuş veya panel kurulmuş sayılmaz |

Suffix `MISSING`, `TYPE_REJECTED`, `OWNER_MISMATCH`, `MODE_MISMATCH`,
`HARDLINK_REJECTED`, `PERMISSION_DENIED` yalnız neden kodlarıdır. Gerçek UID,
parola/hash, bağlantı DSN'i, kayıt/SQL/exception içeriği yazılmaz. Bilinmeyen SQL
hatası `V2_DB_SQL_FAILED` veya `V2_DB_CONNECTION_FAILED` olarak kalır; tahminle
kimlik varlığına dönüştürülmez. Eski genel çıktıdan alt neden saptandı denemez.

## Güncel karar: ofis aktarımı iptal; VDS'de yeni LOCAL ADMIN

Kullanıcı artık VDS'de yeni suatciftci LOCAL ADMIN oluşturulmasını istedi. Eski
ofis export/transfer komutları bu görev için çalıştırılmaz; aşağıdaki eski kayıtlar
tarihsel bağlamdır. Gerçek VDS ADMIN yokluğu ve kurulum bu oturumda SSH EPERM
nedeniyle **BLOCKED / doğrulanmadı**. Hiçbir ADMIN oluşturulduğu varsayılmıyor.

`build-native-installer.py`, temiz commit kaynak arşivini gömen bağımsız
`.local/mikrotik-v2-native-admin.run` üretir. Bu dosya sır içermez; VDS'ye
`~/mikrotik-v2-native-admin.run` olarak alındıktan sonra normal VDS terminalinde:

```bash
sudo bash ~/mikrotik-v2-native-admin.run
```

İlk işlem exact izole küme/PG16.15/SCRAM/peer kimliğini ve READ ONLY ADMIN
varlığını kontrol etmektir. Aktif/pasif, LOCAL/DEMO fark etmeksizin herhangi bir
ADMIN varsa uygulama/hesap/config/servis değişikliği yapmadan durur. Mevcut modern
depo da boş ve first-admin kurulumu açık olmalıdır; aksi durumda STOP. Migration
çalıştırılmaz, ofis hesabı/hash'i okunmaz veya aktarılmaz. İsim/e-posta ve yeni
parola gerçek TTY'den alınır; parolanın iki girişi eşleşmeli ve mevcut 14–128
karakter doğrulamasını geçmelidir. Getpass echo fallback reddedilir. OLUSTUR
teyidi sonrası yeni rastgele UUID ile güçlü scrypt LOCAL ADMIN, FIRST_ADMIN_CREATE
audit'i, VDS operatör UID'li seal ve closed marker atomik yazılır. Kilit altında
ADMIN yokluğu tekrar kontrol edilir; eşzamanlı ADMIN varsa rollback olur.

Router operator listesi boş, iki gate false kalır. Runtime yalnız iki kapı kapalıysa
boş listeyi kabul eder; yeni hesabın router bağlantı yetkisi yoktur. Diğer scope,
TLS/pin/source kontrolleri gevşetilmez. Bağımlılıklar ayrı venv/npm alanında;
API nologin hesabı, SCRAM ve owner-private dosyalarla yalnız 127.0.0.1:18080'de
çalışır. SQL ADMIN doğrulaması geçmeden başlatılmaz. Son kabul yeni parolayla
HTTP login/me/options/logout, demo giriş reddi, DB sağlığı, built UI ve loopback
listener kontrolüdür. Parola/hash hiçbir stdout, argv, audit veya config dosyasına
yazılmaz; API DB rolü parolası ADMIN parolasından ayrıdır.

Dosya/owner/config çakışmaları güvenli STOP üretir. API inactive iken önceki
root-owned V2 app ve build işaretleri private native-preinstall-* backup'ına
taşınarak korunur; üzerine yazılmaz. Owner-belirsiz app reddedilir. Yalnız exact
kapalı eski env template'i yeni boş operator listesine atomik çevrilebilir;
başka config değiştirilmez. Başarısız kurulumdan sonra ADMIN oluşmuşsa yeniden
çalıştırmak da STOP verir; kullanıcı talebi gereği mevcut ADMIN'e dokunulmaz.
Bu betik hiçbir V1, router, RADIUS veya IPsec servisine bağlanmaz/değiştirmez.

## Yetkili tamamlama komutu — 2026-10-30

### Ofis connection-refused düzeltmesi

Hedef değişmiyor: 127.0.0.1:55432, mikrotik_manager_v2/v2_local ve repo altındaki
`.local/postgres-v2-demo`. Son yerel logda 2026-10-30 18:39:16 +03 smart shutdown
isteği bulunuyor; pg_ctl status=3 ve görünür postgres süreci yok. pg_control hâlâ
in production durumunda; temiz kapanış tamamlandı denemez. İsteği gönderen bu
kanıtlardan belirlenemez. Normal terminaldeki CONNECTION_REFUSED, hedefte kabul
eden bir listener olmamasıyla uyumludur. Codex'te ayrıca socket EPERM doğrulandı;
burada PostgreSQL başlatma veya bağlantı/export tekrar denemesi yapılmadı.

Normal ofis WSL terminalinde **yalnız mevcut izole V2 kümesini başlatıp export**:

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2 && python3 deploy/cebeci-v2-pilot/complete-office.py --start-existing-v2 --export-only
```

Yeni seçenek yalnız --export-only ile kullanılabilir; SSH/VDS aşamasına geçmez.
Owner/mode/no-link/PG16/gerçek data ve HBA/ident yolları, harici include ve
replication/archive/preload ayarları kontrol edilir. Socket yetkisi yoksa startup
artefact oluşturmadan durur. Çalışan küme yeniden başlatılmaz; stopping ise durur.
Kapalı kümede port boşluğu doğrulanıp yalnız exact dizin için pg_ctl start bir
kez, 30 sn sınırıyla çalışır. Log owner-only ve SQL/parametre dökümü kapalıdır.
PID/socket dosyası elle silinmez. Eski WAL için PostgreSQL'in normal crash recovery
işlemi gerekebilir; initdb, CREATE DATABASE, seed, migration, role/password reset
ve systemctl yoktur. Başlangıçtan sonra mevcut export SQL'i gerçek cluster ve
mevcut ADMIN guard'larını READ ONLY transaction'da doğrular. Başarılı export
görülmeden aktarım hazır/PASS sayılmaz; kaynak hesabın varlığı bu oturumda DB'den
yeniden doğrulanamamıştır. Kullanıcı/şifre değişikliği yapılmaz.

Export hata düzeltmesi: bu Codex ortamında bağımsız TCP socket oluşturma kontrolü
`errno=1 / EPERM` verdi. Yeni betik bu durumda DB bağlantısı, passfile oluşturma
veya SSH denemeden `BLOCKED: V2_EXPORT_SOCKET_EPERM` üretir. Önceki genel hata
mesajı kullanıcının terminalindeki nedeni tek başına kanıtlamaz. Normal ofis
terminalinde yalnız export kontrolü için aynı komuta `--export-only` eklenir;
bu seçenek VDS'ye bağlanmaz veya servis/DB kurulumu yapmaz.

Hatalarda yalnız sabit kod yazılır; ham subprocess stderr/stdout, SQL hatası,
exception/traceback, DSN, parola veya hash yazılmaz. Psql dili `LC_ALL=C`, bağlantı
süresi 5 sn, salt okunur session varsayılanı ve sorgu/kilit süre sınırları sabittir.
Mevcut PGPASSFILE kullanılırken URL içinde ayrıca parola bulunması gerekmez.
Kaynak hesap bulunamazsa SQL sabit `ACCOUNT_NOT_FOUND` hatası verir.

| Kod | Anlamı |
| --- | --- |
| `V2_EXPORT_SOCKET_EPERM` / `SOCKET_DENIED` | Yerel ortam socket oluşturmayı reddetti; retry yok |
| `V2_EXPORT_CONNECTION_REFUSED` | V2 hedefi bağlantıyı reddetti; servis otomatik başlatılmaz |
| `V2_EXPORT_DB_AUTH_FAILED` / `PGPASS_NO_MATCH` | Mevcut DB credential/passfile doğrulanamadı; parola değiştirilmez |
| `V2_EXPORT_CONFIG_AMBIGUOUS` / `TARGET_REJECTED` | Belirsiz veya izin verilmeyen bağlantı seçimi |
| `V2_EXPORT_*_UNSAFE` | Owner/mode/regular-file/link koruması reddetti |
| `V2_EXPORT_SOURCE_*` | Kaynak cluster/şema/hesap/kurulum/seal/scope/hash guard'ı reddetti |
| `V2_EXPORT_EXISTING_BUNDLE_*` | Mevcut artifact boş, bozuk veya süresi dolmuş; ezilmez |
| `V2_EXPORT_CONNECTION_FAILED` / `SQL_FAILED` | Beyaz listede olmayan hata; içerik açıklanmaz |

Kullanıcı VDS PG16.15 kümesinde 002–009'un tamamlandığını bildirdi; bunlar yeniden
çalıştırılmayacak. Bu oturumda SSH socket EPERM nedeniyle engellendi ve tekrar
denenmedi. Ofis salt okunur export denemesi de başarısız oldu. Gerçek export/import,
bağımlılık kurulumu, servis ve HTTP kabulü **BLOCKED**; aşağıdakiler hazırlıktır.

Ofis bilgisayarının normal terminalinde tek komut:

```bash
cd /home/suatpc/Codex-Projects/mikrotik-manager-v2 && python3 deploy/cebeci-v2-pilot/complete-office.py
```

`complete-office.py` temiz commit'in kaynak arşivini kullanır. Bağlantıyı yalnız V2
env/repo yapılandırması ve repo altında çalışan süreçlerden seçer. Mevcut owner-only
PGPASSFILE/.pgpass tercih edilir; yoksa mevcut config parolası geçici 0600
PGPASSFILE'a yazılır ve dosya sonunda kaldırılır. Export guard'ları değişmedi.
Kaynak PostgreSQL zaten çalışıyor olmalıdır; ofis servisi başlatılmaz/değiştirilmez.
Özel bundle yalnız 24 saatlik pencere içinde tekrar kullanılabilir; eski/güvensiz
hedef otomatik ezilmez. SSH host key önceden doğrulanmış olmalı; VDS sudo parolası
gerekirse yalnız gerçek TTY'de istenir. ADMIN parolası istenmez.

SFTP yeni 0700 staging kullanır ve dosyaları 0600'a sabitler. `complete-vds.py`
yalnız root olarak exact V2 kök/küme/sürüm/socket/HBA'yı kabul eder; DB init,
migration, seed, first-admin veya DB restart içermez. App root-owned yeni dizine
açılır; mevcut app yalnız arşivdeki her dosya birebir aynıysa benimsenir. Root-owned
arşiv/build işaretleri aynı kaynak için kaldığı yerden devam etmeyi sağlar.

Boş hedefte import bir kez çalışır. Tekrarda `verify-admin.psql` ve bundle ile
hesap/hash/revision/grants/özgün seal eşitliği zorunludur; değişmiş kimlik ezilmez.
`identity-access.psql` dar app izinlerini kurar; app rolünde sahiplik, yüksek yetki
veya rol üyeliği varsa durur. DB parolası yalnız private API config yoksa üretilir,
SCRAM verifier olarak yalnız v2_local'a atanır; mevcut config parolası korunur.
ADMIN parolası/hash'i değiştirilmez. Ayrı root-owned venv ve npm ci/build kurulur.
API nologin hesabı ve private config/log/.local dizinleriyle çalışır.

İki gate false zorunludur. Son ADMIN kontrolü geçmeden API başlatılmaz. Yalnız
yeni API unit'i başlatılır; ready, DB health, app rolüyle kimlik ve kapalı options,
demo login 401, HTML ve yalnız 127.0.0.1:18080 listener kontrol edilir. Başarıdan
sonra yalnız exact VDS handoff/staging kaldırılır; ofis bundle'ı private karantinada
kalır. Hata aşama adıyla, sır/SQL/DSN/traceback dökmeden durur; otomatik retry/reset
yoktur. Gerçek ADMIN parola login'i **UNTESTED** yazılır. Router/RADIUS/IPsec/V1'e
erişim veya değişiklik yapılmaz. Aşağıdaki önceki hazırlık kaydı tarihsel bağlamdır.

---

**Hazırlık tamam; VDS'ye uygulanmadı. İki bağlantı kapısı kapalı.**
Temel: main / 64eee0d (c9b36eb ADMIN altyapısını ve son güvenli giriş düzeltmesini içerir).
Bu paket kurulum onayı değildir; servis/DB/SSH/cihaz bağlantısı, migration ve dağıtım çalıştırılmadı.

Kullanıcı ofis V2 PostgreSQL'de `suatciftci` LOCAL ADMIN hesabını,
`v2-user-b72c04eb-8000-4f2c-a41a-bc4909cddb92` operatör ID'sini ve kapanmış demo
girişlerini doğruladı. Bu oturum hesabı/hash'i okumadı. **Hesap VDS'ye taşınmış sayılmaz.**
VDS kaynağı 10.250.0.1, hedef 10.250.0.19:8729 ve eski API-SSL PASS kullanıcı
kanıtıdır; yeniden SSH/TCP/login araştırması yapılmaz. Ofis IP taklidi veya API 8728 fallback yoktur.

## İzole kurulum bileşenleri

| Bileşen | Kesin hedef / sahip | Güvenlik sınırı |
| --- | --- | --- |
| Uygulama | `/srv/mikrotik-manager-v2-pilot/app`, onaylı commit | V1 veya eski pilot checkout'u güncellenmez; kod servis hesaplarınca salt okunur |
| Python ortamı | `/srv/mikrotik-manager-v2-pilot/venv` | Yeni V2 bağımlılıkları; V1/CLI venv'i kullanılmaz |
| API + built UI | `127.0.0.1:18080`, `mikrotik-v2-pilot` | Aynı origin; public listener, Vite veya V1 proxy yok |
| API unit | `mikrotik-v2-cebeci-pilot.service` | Factory `app.pilot_panel:create_app`; otomatik migration/polling/retry yok |
| PostgreSQL unit | `mikrotik-v2-cebeci-pilot-db.service`, `mikrotik-v2-db` | Ayrı PG16 kümesi; sistem/V1 PostgreSQL kullanılmaz |
| DB / uygulama rolü | `mikrotik_manager_v2` / `v2_local`, `127.0.0.1:55432` | SCRAM; yeni özel DB parolası, örnek `v2_local` parolası kabul edilmez |
| DB bakım rolü | `v2_pilot_maint` | Yalnız yeni kümenin private Unix socket'inden peer map ile `mikrotik-v2-db`; API'ye verilmez |
| PG data / socket | `/srv/mikrotik-manager-v2-pilot/postgres`, `postgres-socket` | `mikrotik-v2-db`, 0700; API ham PG dosyalarını okuyamaz |
| API config | `config/api/database.env`, `config/api/onboarding.env` | API sahibi; dizin 0700, dosyalar 0600 |
| PG config | `config/postgres/postgresql.conf`, `pg_hba.conf`, `pg_ident.conf` | DB sahibi; dizin 0700, dosyalar 0600; API config'i paylaşılmaz |
| API logları | `logs/api/output.log`, `error.log` | Ayrı API sahibi; 0700 dizin/0600 dosyalar, append; HTTP access log kapalı |
| PG logları | `logs/postgres/output.log`, `error.log` | Ayrı DB sahibi; 0700/0600, append; statement/parameter/DETAIL dökümü kapalı |
| ADMIN aktarım karantinası | `maintenance/admin-transfer.jsonl` | Yalnız DB sahibi, 0700/0600; Git/app/.local/HTTP dışında |
| Public CA / leaf | `app/.local/cebeci-pilot/trust/ca.pem`, `leaf.pem` | API sahibi; 0700/0600; private key taşınmaz |
| Cihaz credential dosyaları | `app/.local/cebeci-pilot/secrets/username`, `password` | API sahibi 0700/0600; alias `CEBECI_TOWERS_RO`, yalnız `v2-cebeci-ro` |
| Registry secret alanı | `app/.local/router-registry/secrets` | 0700/0600; DB/API/audit'e credential değeri yazılmaz |

Tüm göreli yollar `/srv/mikrotik-manager-v2-pilot` altındadır. Üst `config`/`logs`
dizinleri root sahibi 0711 olabilir; iki ayrı sahibin alt dizinlerine 0700 uygulanır.
Kod/venv üst yolları DB bakım hesabınca okunabilir, servis hesaplarınca yazılamaz.
Unit/env/PG taslakları `deploy/cebeci-v2-pilot/` içindedir; kurulmadı, source edilmedi.
PG16 ve systemd `append:` desteği, portların boşluğu, yeni UID/dizin sahipleri,
disk ve saat uygunluğu kurulum operatörünün ön koşuludur. Çakışmada STOP; başka
servis/port/config değişmez. V1'in PostgreSQL'i, kullanıcıları, env'i, IPsec/RADIUS'u
ve `/home/mikadmin/mikrotik-v2-pilot` kaynağı yeniden kullanılmaz veya durdurulmaz.

## Onaydan sonra uygulanacak tek kapalı kurulum değişiklik paketi

1. Yeni V2 OS hesaplarını/dizinlerini ve onaylı commit'in kod/venv/frontend build'ini
   yukarıdaki kökte hazırla. Yeni olmayan veya sahibi belirsiz hedefte overwrite
   yapma. Log dosyalarını yeni sahiplerinde 0600 önceden oluştur. V1'e dosya/symlink
   veya servis bağımlılığı ekleme; VDS DNS/ağ/IPsec/firewall değiştirme.
2. Yalnız yeni PG kümesini, bootstrap sahibi `v2_pilot_maint` ile hazırla. PG HBA,
   ident ve logging taslaklarını ilk başlangıçtan önce kendi konumlarına koy.
   API ve router kapıları henüz kapalıdır. V1 PostgreSQL servisini veya 5432'yi kullanma.
   Bakım rolü sadece bu kümede yetkilidir; API rolü LOGIN/NOSUPERUSER/NOCREATEDB/
   NOCREATEROLE/NOREPLICATION/NOBYPASSRLS olur. DB parolası operatörün güvenli
   TTY/secret yöntemiyle ayarlanır; SQL/argv/rapor/Git'e yazılmaz.
3. **Önce yeni bağlı kümenin gerçek data_directory, DB/rol/port kimliğini doğrula.**
   Yalnız boş yeni DB'de, bakım rolüyle şu dosyaları gözden geçirilmiş sırada uygula:
   `002_demo_storage.sql`, `003_demo_alarm_actions.sql`, `004_demo_identity.sql`,
   `005_demo_settings.sql`, `006_router_registry.sql`, `007_router_workspace.sql`,
   `008_subscriber_workspace.sql`, **`009_first_local_admin.sql`**. `001`, wildcard,
   down migration, seed, `users-init` ve `first-admin.sh` çalıştırma. Bunların yerel
   WSL owner/cluster korumalarını VDS için gevşetme. Kısmi/mevcut şemada STOP.
   006 nesneleri `public`, workspace nesneleri kendi V2 şemalarında kalır.
   İmport sırasında PG logging `terse`, statement/parameter dökümü kapalı olmalıdır;
   app rolüne verilen DB parolası da yalnız yeni V2 kümesine aittir.
4. Aşağıdaki mevcut ADMIN aktarımını tamamla. Yeni kullanıcı ID/parola/hash üretme,
   demo hesabını ADMIN'e çevirme veya farklı VDS hesabını aynı kişi varsayma.
5. API rolüne yalnız V2 şemalarında gerekli çalışma izinlerini ver: şema USAGE;
   kullanıcı/kurulum marker'ları SELECT; users INSERT ve yalnız name/email/role/
   active/permissions/revision kolonlarına UPDATE; user_audit SELECT/INSERT.
   **schema_state ve first_admin_setup üzerinde UPDATE/INSERT/DELETE verme.**
   Diğer V2 iş tabloları için mevcut servislerin gereken SELECT/INSERT/UPDATE
   izinlerini, sentetik router CRUD için records DELETE iznini ayrı değerlendir.
   API rolü tablo/şema sahibi olmaz, CREATE/DDL veya bakım rolü üyeliği alamaz;
   public schema CREATE/PUBLIC yetkisi kaldırılır. V1 DB/rolüne GRANT yapılmaz.
6. Eski pilotun bilinen CA/leaf ve username/password dosyalarını kaynak sahibi
   `mikadmin` altında owner/no-symlink/izin kontrolünden geçir; kaynakları değiştirme.
   Yalnız yeni V2 API hesabına owner-only kopyaları oluştur. Taramayla farklı sır
   bulma, kaynak chmod/chown, parola yenileme veya özel anahtar aktarımı yoktur.
   Mevcut API-SSL adapter chain + IP SAN + pin + bound source + read allowlist
   kontrollerini aynen uygular; bu hazırlık hiçbir cihaz oturumu açmaz.
7. `database.env.example` gerçek, URL-encoded V2 DB parolasıyla yalnız private
   `config/api/database.env` kopyasına çevrilir; public örnek/WSL env aynen taşınmaz.
   `onboarding.env.example` private API config'e kopyalanır. Profil `cebeci-vds`;
   yalnız bildirilen operatör ID, 10.250.0.19/32, 8729, 10.250.0.1 ve incelenmiş pin.
   **V2_ROUTER_ONBOARDING_ENABLED=false ve V2_CEBECI_API_SSL_ENABLED=false kalır.**
8. Yeni DB'de aşağıdaki salt okunur aktarım sonu kontrolü geçmeden API başlatma.
   Yalnız ayrı kurulum onayı varsa yeni unit'leri kurup başlat; Restart=no kalır.
   `/api/ready`, yerel DB sağlığı ve SSH-tünelli panel oturumu doğrulanır. Servis
   başlangıcı, GET veya panel açılışı cihaz okuması başlatmaz. Router Test Et/Kaydet/
   Salt Okunur Detay düğmeleri bu kurulum kabulünde çalıştırılmaz.

## Mevcut ADMIN'in güvenli aktarımı (şu an çalıştırılmadı)

Aktarım **tek kullanıcı satırı + özgün first_admin_setup kapanış kaydı** içindir.
Kaynak kullanıcı/audit/demo verileri salt okunur kalır; bütün DB dump'ı veya tüm
demo kullanıcılarını taşımak uygun değildir. Aynı ID/username/role/active/origin,
revision, permissions ve scrypt hash aynen korunur. Parola istenmez, yeniden hash
edilmez. VDS'de yeni ilk-ADMIN bootstrap akışı kullanılmaz.
Bu tek seferlik snapshot aktarımıdır; ofiste daha sonra yapılan parola/rol/aktiflik
değişikliği VDS'ye otomatik yansımaz. Yetki iptali iki ayrı V2 deposunda ayrıca
yönetilir; VDS oturumları her istekte yalnız kendi güncel DB yetkisini doğrular.

- Ofis WSL'de, mevcut repo/PG sahibi yeni `.local/admin-transfer` dizinini 0700
  oluşturur; varsa STOP. Shell tracing/terminal kaydı kapalı, umask 077 olmalıdır.
  `admin-transfer.jsonl` dosyasını noclobber ile yeni/boş 0600 oluşturur; symlink,
  hardlink, farklı owner veya mevcut içerikli hedef reddedilir. PSQL CWD bu dizindir.
- Yalnız 127.0.0.1:55432 / mikrotik_manager_v2 / v2_local için mevcut güvenli 0600
  PGPASSFILE kullanılır; PGPASSWORD veya URL/argv içine parola konmaz. `psql -X -q`
  ile repo `export-admin.psql` dosyası açık bakım işlemi olarak çalıştırılır.
  Script gerçek ofis PG dizinini, kapanmış kurulumu, seçili LOCAL/aktif/tam kapsamlı
  ADMIN'i ve güçlü hash biçimini doğrular; repeatable-read READ ONLY snapshot'tan
  **yalnız sabit mutlak .local dosya yoluna** yazar; yanlış CWD repo köküne dosya
  düşürmez. JSON/hash/hesap kaydı stdout'a dökülmez. Handoff adı ayrıca Git-ignore'dur.
- Handoff dosyası gizlidir: cat/tee/clipboard/email/chat/Git veya CI artifact yoktur.
  SSH StrictHostKeyChecking=yes ile mevcut doğrulanmış VDS host key'i kullanılarak
  SFTP ile yalnız operatörün yeni 0700 staging alanına aktarılır. SFTP/SSH burada
  açılmaz. Root operatör hedef kopyayı yeni `maintenance` dizininde DB sahibine
  0600 yerleştirir; eski kaynak/credential dosyaları ve mevcut hedefler değişmez.
- Hedef dosyanın regular/no-symlink/nlink=1/owner=DB hesabı/mode=0600 özelliklerini,
  bütün üst özel dizinlerin 0700 olduğunu doğrula. Örnek hash veya kendi seçilen
  yeni parola kullanma; dosyayı editörde açma. Export en fazla 24 saat geçerlidir,
  beş dakikadan ileri saat veya belirsiz zaman STOP üretir.
- Yeni kümenin OS sahibi `mikrotik-v2-db`, private Unix socket/55432 üzerinden
  `v2_pilot_maint` olarak, DB adı mikrotik_manager_v2 ile `psql -X -q` kullanıp
  `import-admin.psql` dosyasını çalıştırır. pg_ident peer eşlemesi zorunludur.
  Bu script yalnız boş yeni kimlik deposunu kabul eder; shared advisory lock ve
  schema-state satır kilidi altında tek satırı, özgün kapanış kaydını, ayrı
  FIRST_ADMIN_IMPORT audit'ini ve closed flag'ini aynı transaction'da yazar.
  Dosya/şema/ID/hash biçimi/tarih hatası STOP ve rollback olur; overwrite/reset/
  otomatik retry yoktur. Tekrar import da kapalı/boş olmayan hedefte STOP eder.
- Kaynak kapanış kaydındaki UID ve completed_at **ofisteki özgün kurulumun**
  kanıtıdır, VDS'nin OS kimliği değildir. Import audit'inin actor'u doğrulanmış
  peer bakım rolüdür; kaynak UID/zamanı açıkça source olarak ayrı kaydedilir.
  Audit'e parola/hash girmez. Mevcut kullanıcının ID'si korunur, başka hesap üretilmez.

Aktarım sonu bakım kontrolü yalnız şu public kanıtları üretir: users içinde seçili
ID/username için tek LOCAL/aktif/tam kapsamlı ADMIN; identity_initialized=true ve
first_admin_initialized=true; singleton seal aynı ID; tam bir FIRST_ADMIN_IMPORT
audit'i; hiçbir demo login hesabı yok. Hash kolonu, parola veya bundle sorgulanıp
terminale yazılmaz. Uygulama rolüyle login/auth/me ve options bu ID'yi doğrular;
demo girişlerinin 401, izinli gerçek ADMIN için connection_enabled=false olduğu
kontrol edilir. Handoff kopyaları gerekliyse süreli owner-only karantinada tutulur;
kalıcı çalışma yedeği veya log gibi kullanılamaz. Temizleme ayrıca sahipli exact
artifact kapsamıyla yapılır; kaynak kullanıcı/audit/CA/credential dosyaları silinmez.

## Çalışma zamanı koruması ve panel

VDS factory, backend'i yüklemeden önce profil/kök/port/secret **referans yolları** ve
özel PostgreSQL URL kapsamını denetler; sır dosyası okumaz, DB/socket açmaz. Yanlış
root/host/DB/rol/port, örnek parola, farklı pin/source/CIDR/operator veya kısmi gate
fail-closed'dur. Profil yeni VDS unit'inde zorunludur; normal ofis geliştirmesi aynı
eski akışı korur. Onboarding policy her okumada da profil kapsamını denetler.
Yalnız exact operatör ID + mevcut DB'den taze LOCAL/closed/ADMIN/tam kapsamlı oturum
uygun olabilir; env'deki ID tek başına hesap veya izin yaratmaz. API-SSL read-only
allowlist ve mevcut TLS zinciri/IP SAN/leaf pin/source doğrulamaları değişmedi.
VDS profili altında kurulum kapanış kaydı eksik/açık ise login fail-closed'dur;
eski varsayılan demo hesabına geri dönülmez. Kapalı marker olsa bile aktarılmamış
ID için kullanıcı satırı uydurulmaz. Normal ofis bootstrap davranışı değiştirilmez.
VDS profili genel `/verify` ve `/{id}/check` yollarını reddeder; mevcut sabit
`/pilot/cebeci/verify` ve ayrı onaylı `/{id}/read-only` akışı kullanılır. Taşıma
katmanı da hedef/IP/port, identity/model/sürüm, kullanıcı ve incelenmiş pin'i
ayrıca eşleştirir; genel formdan farklı CA/pin/kimlik verilerek pilot kapsamı
aşılamaz. İki flag açıkça birlikte etkinleştirilmedikçe bu kapsam dahi bağlanamaz.

Kurulum onayından sonra ofis paneli yalnız SSH port tüneliyle 127.0.0.1:18080'e
bağlanır; public HTTP/Vite veya V1 proxy değişikliği yoktur. Örnek tünel:

```bash
ssh -N -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes -L 127.0.0.1:18080:127.0.0.1:18080 mikadmin@185.139.5.51
```

Bu komut burada çalıştırılmadı. **Panel/DB kurulumu, router bağlantısı onayı değildir.**
İleride ayrıca onaylanırsa mevcut Test Et → Kaydet → ayrı onaylı Salt Okunur Detay
akışı kullanılır; yeni script/PPPoE/Hotspot/RADIUS/config yazma veya polling yoktur.

## STOP / geri dönüş ve kabul sınırı

Yanlış identity/hesap/cluster/port/owner, kaynak/TLS/pin uyuşmazlığı, V1 etkisi,
yeni olmayan hedef veya gizli veri dökümü riski: STOP. Yeni servisler bile
başlatılmadan önce kapsam kontrol edilir. Onaylı uygulamada sorun çıkarsa yalnız
bu paketin yeni V2 unit'leri durdurulur; gate false kalır, yeni V2 alanı/audit ve
kanıtlar private karantinada korunur. V1'e stop/restart, SQL drop/down veya credential
reset yapılmaz. Burada geri dönüş de çalıştırılmadı.

Yerel kanıt: 18 backend/profile/auth/config/TLS güvenlik kontrolü, 3 VDS frontend
render/kapalı gate/hata açıklaması kontrolü ve TypeScript/Vite build PASS.
SQL aktarım dosyaları kontrat incelemesinden geçti;
gerçek PostgreSQL import/export ve VDS unit/port/DB/HTTP/login kabulü **BLOCKED / uygulanmadı**.
Önceki PG/loopback engelleri yeniden denenmedi; eski geniş testler tekrarlanmadı.
Hazırlanan profil ve taslak dosyalar bağımsız onay olmadan canlıya uygulanamaz.

Yapılandırma dayanakları: [systemd dosyaya append log yönlendirmesi](https://www.freedesktop.org/software/systemd/man/256/systemd.exec.html),
[PG16 log parametreleri](https://www.postgresql.org/docs/16/runtime-config-logging.html)
ve [peer kullanıcı eşlemesi](https://www.postgresql.org/docs/16/auth-username-maps.html).
Bu belgeler VDS'deki kurulu sürüm veya gerçek yetkilerin bu oturumda doğrulandığı anlamına gelmez.
