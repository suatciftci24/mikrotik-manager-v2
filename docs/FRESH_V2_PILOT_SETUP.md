# Bağımsız temiz V2 pilot — yerel hazırlık

Durum: yerel hazırlık PASS; VDS kurulumu ve canlı kabul YAPILMADI.
Esas karar: [eski pilot yükseltmesi BLOCKED](PILOT_LEGACY_UPGRADE_DECISION.md).
Bu belge uzak kurulum yetkisi değildir. Eski native installer/updater kullanılmaz.

## Sabit ve bağımsız hedef

| Kaynak | Yeni temiz pilot |
| --- | --- |
| Profil | `fresh-v2-pilot` |
| Kök / veri | `/srv/mikrotik-manager-v2-fresh-pilot` / `postgres` |
| PostgreSQL | 16; yalnız `127.0.0.1:55442`, bağımsız `socket` dizini |
| DB / sahip / API rolü | `mikrotik_manager_v2_fresh_pilot` / `v2_fresh_owner` / `v2_fresh_app` |
| OS hesapları | `mikrotik-v2-fresh-db`, `mikrotik-v2-fresh` |
| Servisler | `mikrotik-v2-fresh-pilot-db.service`, `mikrotik-v2-fresh-pilot.service` |
| UI + API | aynı origin, yalnız `127.0.0.1:18090`; ayrı UI servisi gerekmez |
| Bağımsız dosyalar | yeni kökte `config`, `venv`, `app/.local`, `backups` |

V1 ve eski V2 kökleri, `.env`, OS hesapları, DB/rol, PostgreSQL cluster/socket,
portlar, unit'ler, yedekler ve sırlar kullanılmaz veya okunmaz. Eski veriler,
ADMIN/parola hash'i, migration geçmişi aktarılmaz. Yeni ADMIN TTY'den oluşturulur.
Gerçek router API, onboarding, PPPoE taşıyıcısı ve RADIUS kapalıdır. API/DB unit'leri
systemd ağ kısıtıyla yalnız loopback erişimine sahiptir; kapıları açma yolu sunulmaz.
Bu kısıtın host systemd/cgroup desteği ileride doğrulanmalıdır.

## Hazırlanan mekanizma

`deploy/fresh-v2-pilot/` altındaki dosyalar:

- `profile.json`, bağımsız iki `.service`, `postgresql.conf`, `pg_hba.conf`,
  `pg_ident.conf`: ayrı kimlikler; TCP'de yalnız API'nin SCRAM rolü, Unix socket'te
  yalnız DB OS kullanıcısının peer eşlemesi. Sahip rolü TCP'ye açılmaz.
- `stage-approved.py`: varsayılanı salt yerel manifest kontrolüdür. Yalnız ayrıca
  yetkilendirilmiş hostta `--stage-approved` root aşaması disk/OS hesabı/venv/unit
  hazırlar; servis çalıştırmaz, enable/daemon-reload/restart yapmaz. Kök dizin
  **boş bile olsa önceden varsa BLOCKED**. Hesap/grup/unit çakışması ve meşgul port
  BLOCKED. Kök atomik oluşturulur. Hata sonrası kalıntılar korunur; resume/reset yoktur.
  Kaynakta hazır `frontend/dist` gerekir; ayrı venv bağımlılık kurulumu o hostta yapılır.
  Kaynak kökleri ve kopyalanacak içerik önceden incelenir; symlink, FIFO ve diğer
  özel dosyalar reddedilir. Hazır UI, PG16 araçları ve Python venv/ensurepip
  kontrolü hedef/hesap oluşturma öncesindedir. Paket inceleme ve staging boyunca
  kaynak ağacı değiştirilmemelidir; bu kontroller kaynak imzası yerine geçmez.
- `manifest.json`: açık 001–009 forward sırası, SHA256 ve profil/runner varlık hash'leri.
  `002_demo_storage.down.sql` dışarıdadır. Manifest güven kökü gözden geçirilmiş
  dağıtım paketidir; hash tek başına kaynak kimliği veya imza kanıtı değildir.
- `manage.py check`: standart Python ile DB, socket, SSH veya servis erişmeden kontrol.
- `manage.py create-database-approved`: yalnız yeni DB OS hesabıyla, sabit yeni
  socket/port/data_directory doğrulanarak, cluster'da yalnız standart `postgres`
  veritabanı varsa yeni DB oluşturur. Var olan DB'yi kabul etmez/silmez/değiştirmez.
- `manage.py migrate-approved`: gerçek TTY, hedef kimliği ve boş katalog zorunlu.
  Kullanıcı şeması/tablo/tip/fonksiyon/extension/large-object/default-ACL/event-trigger/
  foreign-server/publication/subscription veya önceden ledger/API rolü varsa BLOCKED.
  Boş ön-imaj dump'ı alınır. Kilit ve sabit search_path ile 001–009, her revision'ın
  sıra/hash/UTC zamanı, yeni LOCAL ADMIN, audit, kalıcı seal, minimum API rolü ve
  kurulum kaydı **tek transaction** içinde tamamlanır. 009 tek başına commit edilmez.
  Başarısız SQL/şema/audit/grant doğrulaması her DB değişikliğini geri alır.
  Tekrar çalıştırma dolu hedefte BLOCKED; stamp/adoption/legacy resume yoktur.
- `ledger.sql`: `v2_migrations.applied` ve `installation`; API rolüne kapalıdır.
  Eski `schema_state.version=1` migration head sayılmaz.
- `schema.sql` + `schema.expected.json`: PG16 referans katalog imzası; yalnız tablo
  adları değil kolon sırası/tipi/null/default, PK/FK/unique/check, index, RLS,
  routine, trigger, policy, extension ve şemalar karşılaştırılır. Referans 001–009
  ve ledger'ın yerel, boş, socket'siz PG16 uygulamasından üretilmiştir.
  Şema bekleneni otomatik yeniden öğrenmez; değişiklik ayrı inceleme gerektirir.
  Sahiplik, PUBLIC grant'leri ve API rolünün yetki sınırı ayrıca doğrulanır.
- `manage.py verify`: salt okunur transaction'da hedef + şema + tam ledger +
  manifest + ADMIN/seal/audit + rol/izin doğrulaması; hata BLOCKED.
- `manage.py backup`: yalnız doğrulanmış yeni hedef için dump + arşiv listesi
  kontrolü + SHA256 receipt. `accept-approved.py --accept-approved`: ileride root
  olarak verify ve yeni backup geçince root-owned kabul dosyası oluşturur;
  servis başlatmaz. `runtime_check.py`: başlangıçta kabul dosyası, manifest,
  kapalı profil, TCP kimliği, şema ve seal zorunlu; migration çalıştırmaz.

İlk sır yalnız yeni makinede üretilir. DB URL'si `config/database.env` içine
exclusive-create ile yazılır; mode 0640 ve setgid config dizini ile yalnız yeni DB
OS sahibi/API grubu okuyabilir. Önceden dosya varsa durur. Parola argv/log/JSON
raporuna verilmez; SQL hataları ham basılmaz. SQL başarılı olup dosya/yedek adımı
başarısızsa kurulum başarılı bildirilmez; otomatik yeniden uygulama yapılmaz.

## Daha sonra ayrıca yetkilendirilecek host işlemleri

Bu oturumda aşağıdaki aşamaların **hiçbiri çalıştırılmadı**. SSH otomasyonu yoktur.
Onay; yalnız yeni hedefte OS hesabı/disk/DB oluşturma ve yeni servis başlangıcını
ayrıca kapsamalıdır. Eski pilot veya V1 servislerine işlem yapılmaz.

1. İncelenmiş kaynak + manifest aktarımı ve ayrı frontend build. Paket bütünlüğünü
   Ofis WSL'deki gözden geçirilmiş hash ile karşılaştır; sır/`.local`/eski DB aktarma.
2. Yetkili host root terminalinde `stage-approved.py --stage-approved`.
   Hazırlık hata verirse dur; dizinleri silip tekrar deneme.
3. Yalnız yeni unit'ler için daemon-reload ve `mikrotik-v2-fresh-pilot-db.service`
   başlangıcı. Eski servisi restart/stop etme. Yeni port ve egress izolasyonunu doğrula.
4. Yeni DB OS hesabıyla, yeni venv Python'uyla kurulu `manage.py` üzerinden sırayla
   `create-database-approved`, sonra gerçek TTY'de `migrate-approved`.
   Bakım komutlarını `PG*`, `V2_DATABASE_URL` veya eski env dosyaları devralmadan çalıştır.
5. `verify` ve yedek kabulünden sonra root olarak `accept-approved.py --accept-approved`.
   Yalnız yeni API servisini başlat; loopback HTTP sağlık, gerçek yeni LOCAL ADMIN
   girişi, demo girişinin kapalı olması ve router/PPPoE kapalı durumunu doğrula.
   Dış erişim ancak ayrı yetkili tünel/erişim planıyla; genel bind/proxy ekleme.

Kurulu araç kökü:
`/srv/mikrotik-manager-v2-fresh-pilot/app/deploy/fresh-v2-pilot/`.
Python: `/srv/mikrotik-manager-v2-fresh-pilot/venv/bin/python`.
Tüm adımlar yeni hedef içindir; mevcut pilot üzerinden yerinde çalıştırılmaz.

## Yedek ve geri dönüş

- İlk migration öncesinde boş ön-imaj, migration sonrası ve her kabul öncesinde
  tam yeni DB custom dump'ı alınır. Kayıtlar yeni `backups/<UTC>-<random>/` altında;
  dizin 0700, dump/receipt 0600. Salt yeni socket kullanılır, inherited `PG*`
  kaldırılır. `pg_dump` ve `pg_restore --list` başarısı ile dump SHA256 kaydedilir.
  Bu kontrol **restore provası değildir**; receipt `NOT_PERFORMED` bildirir.
- Dump sır ve kişisel veri içerebilir. Git'e/loga/stdout'a koyma; kopyası yalnız
  ayrıca onaylı güvenli yedek deposuna, erişim ve şifreleme politikasıyla alınır.
  Yeni app kaynak paketi, manifest, profil, unit ve yeni config ayrıca erişimi
  sınırlı yedeklenmeli; DB dump'ı rol parolasını veya uygulama dosyalarını içermez.
- SQL/009/audit hatasında transaction geri alınır; DB boş kalır. Disk/OS/config
  kalıntısı korunur, otomatik cleanup/drop/down/reset/resume yapılmaz. Hata sonrası
  aynı hedefe kurulum tekrar denenmez; salt okunur inceleme ve yeni karar gerekir.
- Commit sonrası sorun çıkarsa yalnız yeni API trafiğini durdur ve yeni API'yi
  stop etme yetkisi al. Eski pilot zaten değiştirilmediğinden eski yapılandırma,
  veri ve servisler olduğu gibi kalır; otomatik switch/restart yapılmaz.
  Yeni DB ve yedekler teşhis için korunur. İlk kurulum kabulü trafik geçişi değildir.
- Veri geri yükleme gerekirse **başka bir boş recovery cluster/DB/port/data dizini**
  için ayrı profil ve açık yetki hazırlanır. Önce receipt SHA256, arşiv listesi,
  PG major, kaynak manifest/şema doğrulanır. Onaylı recovery rolü/DB'si oluşturulup
  `pg_restore --exit-on-error --single-transaction` ile yalnız recovery DB'ye
  yüklenir; `--clean`, eski hedefe restore veya DROP yoktur. Ardından catalog,
  ledger/checksum, ADMIN/seal/audit ve uygulama invariants doğrulanır; ayrı HTTP
  kabulü tamamlanmadan trafik açılmaz. Recovery kimliği bu sabit yeni pilot
  runner'ına taklit ettirilmez. Restore provası bu görevde yapılmadı.

## Yerel doğrulama ve sınırlar

Sentetik unittest'ler boş/dolu hedef kapısını, checksum/sıra, kapalı profil,
eski hedef reddi, sırsız backup çağrıları ve staging çakışmasını kontrol eder.
PG16 single-user testi gerçek runner SQL'ini uygular; 009 sonrası kasıtlı hatada
ledger/şema/ADMIN'in toplu rollback'ini, başarılı 9 kaydı/audit/seal'i ve şema
sapmasının tespitini doğrular. Mevcut first-admin ve eski pilot guard testleri
ayrıca çalıştırılır. TCP/Unix-socket, systemd, gerçek dump/restore, VDS kurulum ve
HTTP kabulü yapılmış sayılmaz. Yerel Unix-socket engelinden sonra tekrar denenmedi;
SSH/socket EPERM teşhisi başlatılmadı. Önceki 33 test tekrarlanmadı. Son hazırlıkta
yalnız 3 yeni bağımlılıksız staging regresyon testi ve çevrimdışı manifest kontrolü
çalıştırıldı; symlink/FIFO/eksik build reddi ve hata öncesi sıfır hedef değişikliği
doğrulandı. Yerel Git commit/push sonucu ilerleme belgesinde ayrıca kaydedilir.

Sonraki tek uygulanabilir **Ofis WSL terminali** komutu (yalnız yerel kontrol):

```bash
python3 /home/suatpc/Codex-Projects/mikrotik-manager-v2/deploy/fresh-v2-pilot/manage.py check
```

## Son kurulum bağlantısı

[Yetki ayrımı, yerel release ve yönetici kurulum sırası](../deploy/fresh-v2-pilot/INSTALL.md)
son hazırlığı tamamlar. Sınırlı v2-fresh-ops hesabı ilk kurulum yapamaz;
yetki genişletilmez. Mevcut hazır frontend çıktısı yeniden üretilmez.
