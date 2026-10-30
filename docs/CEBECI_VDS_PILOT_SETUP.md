# CEBECI_TOWERS: kapalı VDS pilot kurulum paketi

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


## Tamamlayıcı izin ve kabul dosyaları

Migration konumu `migrations/versions/` altıdır; yalnız listelenmiş forward dosyalar
uygulanır. ADMIN importundan sonra aynı private peer bakım bağlantısında
`psql -X -q -f deploy/cebeci-v2-pilot/identity-access.psql` çalıştırılır.
Yeni V2 DB PUBLIC bağlantı/TEMP izinleri kaldırılır, kimlik kolon izinleri ve
mevcut V2 iş tablolarının çalışma izinleri verilir. İçindeki `verify-admin.psql`
kimlik/seal/audit ve efektif rol/kolon/DDL izinlerini commit öncesi doğrular.
Hata halinde bağlantı kapatılır; GRANT transaction'ı rollback olur. Beklenmeyen
sahiplik, rol üyeliği veya kolon grant'inde otomatik onarım yerine STOP edilir.
Bağımsız kabul aynı bakım rolüyle `PGOPTIONS='-c default_transaction_read_only=on'
psql -X -q -f deploy/cebeci-v2-pilot/verify-admin.psql` kullanır. Yalnız sabit
PASS kodu çıkar; hesap/hash çıktısı yoktur. API rolüyle mevcut ADMIN panel girişi,
auth/me ve options kabulü ayrıca gerekir. Parola yalnız giriş formuna yazılır.

Geri dönüş sırası: yalnız yeni API unit'ini, ardından yalnız yeni PG unit'ini
durdur; kurulmuşsa yalnız bu iki unit'in enable durumunu kaldır. Yeni kökü ve
private audit/transfer kanıtını karantinada koru. DROP/down migration, hesap reseti,
V1/proxy/ağ değişikliği yoktur. Tekrar kurulum öncesi küme kimliği ve kapalı flag'ler
kabul edilir; aynı import tekrarlanmaz. Burada bu işlemler uygulanmadı.
