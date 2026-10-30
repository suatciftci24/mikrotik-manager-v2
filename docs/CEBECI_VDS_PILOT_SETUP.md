# CEBECI_TOWERS panel pilotu: onay için izole VDS kurulum planı

**Durum: hazırlanmış taslak; uygulanmadı. Bağlantı kapısı kapalı.**
Mevcut merkezi VDS, 10.250.0.1 kaynak adresi, 10.250.0.19:8729 erişimi ve önceki
API-SSL PASS kullanıcı tarafından doğrulandı; yeniden SSH/TCP/router testi yapılmadı.
Ofis WSL'nin bu adresi taklit etmesi veya TLS/source kontrollerinin değiştirilmesi
çözüm değildir. Mevcut native V2 backend kaynak adresinin bulunduğu VDS'de çalışır;
ofis tarayıcısı yalnız panel/API'ye SSH tüneli üzerinden erişir.

## Tek uygulama paketi: ancak ayrı açık kurulum onayından sonra

| Bileşen | Kesin hedef | İzolasyon |
| --- | --- | --- |
| Yeni uygulama kökü | `/srv/mikrotik-manager-v2-pilot/app` | Yalnız bu V2 reposunun onaylanmış commit'i |
| Python ortamı | `/srv/mikrotik-manager-v2-pilot/venv` | V1 ve eski CLI venv'i kullanılmaz |
| API + built UI | `127.0.0.1:18080` | Tek ASGI servis, aynı origin; Vite/public port açılmaz |
| API servis hesabı | `mikrotik-v2-pilot` | Yeni, etkileşimli girişsiz Linux servis kullanıcısı |
| API servisi | `mikrotik-v2-cebeci-pilot.service` | Taslak repo `deploy/cebeci-v2-pilot/` altında |
| PostgreSQL servisi | `mikrotik-v2-cebeci-pilot-db.service` | Ayrı `mikrotik-v2-db` Linux hesabı, PG16 gereksinimi |
| DB portu / adı / rolü | `127.0.0.1:55432` / `mikrotik_manager_v2` / `v2_local` | Ayrı küme, özel parola; V1 DB/rol/socket kullanılmaz |
| PG veri / Unix socket | `/srv/mikrotik-manager-v2-pilot/postgres`, `postgres-socket` | DB servis hesabı, 0700; API hesabı raw PG dosyalarını okuyamaz |
| Özel servis yapılandırması | `/srv/mikrotik-manager-v2-pilot/config` | API hesabına ait 0700 dizin; env dosyaları 0600 |
| Public CA / leaf | `app/.local/cebeci-pilot/trust/ca.pem`, `leaf.pem` | API hesabına ait 0700/0600; private key taşınmaz |
| Pilot hesap referansları | `app/.local/cebeci-pilot/secrets/username`, `password` | Alias `CEBECI_TOWERS_RO`, yalnız ayrı pilot hesabı |
| Registry secret deposu | `app/.local/router-registry/secrets/` | 0700/0600; API/DB/audit'e credential değeri yazılmaz |

PG16 binary'sinin mevcut olması, 18080/55432'nin boş olması ve yeni hesap/yolların
başkasına ait olmaması kurulum ön koşuludur; bu görev bunları VDS'de ölçmedi.
Çakışmada STOP; V1 portu/kullanıcısı/dosyası/servisi değiştirilmez. V1'in system
PostgreSQL servisi, IPsec ve RADIUS yeniden kullanılmaz veya yeniden başlatılmaz.

1. Onaylı işletim görevlisi yalnız yeni V2 hesap/dizinlerini hazırlar. V2 kodunu
   sabitlenmiş onaylı commit ile yeni köke, V2 bağımlılıklarını ayrı venv'e ve
   frontend build'ini `app/frontend/dist` altına kurar. V1 veya eski çalışan
   `/home/mikadmin/mikrotik-v2-pilot/` checkout'u güncellenmez.
2. Aynı VDS'de eski pilotun doğrulanmış public CA/leaf ve korumalı username/password
   dosyaları **yerel olarak kopyalanır**. Kaynaklar önce mevcut mikadmin kimliği altında eski pilot okuyucusunun
   owner/izin/no-symlink kontrolleriyle doğrulanmalıdır; bilinmeyen konum taranmaz.
   Kaynak içerikler/parolalar terminale, rapora, Git'e veya ofise aktarılmaz;
   kaynak dosyalara chmod/chown/yazma yapılmaz. Yalnız yeni kopyalar yeni API
   hesabına 0600, private dizinler 0700 atanır. Hedeflerde mevcut farklı dosya
   varsa overwrite yerine STOP. API bridge kodu yeni checkout kökünden bu aynı
   göreli yolları bulur; ayrı router script'i veya kod değişikliği gerekmez.
3. Yalnız yeni PG kümesi için loopback 55432, ayrı data/socket, private local
   bakım erişimi ve uygulama rolü için SCRAM kimlik doğrulaması hazırlanır.
   Uygulama rolüne superuser/role oluşturma/başka DB erişimi verilmez. Yalnız
   yeni V2 DB için `002_demo_storage.sql`, `003_demo_alarm_actions.sql`,
   `004_demo_identity.sql`, `005_demo_settings.sql`, `006_router_registry.sql`,
   `007_router_workspace.sql`, `008_subscriber_workspace.sql` sıralı, gözden
   geçirilmiş şema kapsamıdır; `*.down.sql` veya wildcard migration çalıştırılmaz.
   Mevcut/kısmi şemada kör tekrar veya onarım yerine STOP. Yeni küme kimliği,
   port/DB/rol/data_directory doğrulanmadan SQL uygulanmaz. Bu adım burada yapılmadı.
   WSL'ye özel `dev-db.sh`/repair/`local_router_registry --apply` komutları VDS'ye
   kopyalanıp çalıştırılmaz; onların WSL küme/password korumaları gevşetilmez.
4. Yetkili operatör **mevcut V2 kullanıcı sisteminden doğrulanmış** seçili ADMIN
   hesabını aynı ID/rol/aktiflik/izinler ve korumalı hash ile, onaylanmış özel
   kimlik aktarım süreciyle yeni V2 DB'ye taşır. Bu aktarım V1'e gitmez; tüm demo
   verileri kopyalanmaz. Parola/hash raporlanmaz, yeni kimlik/grant uydurulmaz;
   `users-init` ile bilinen varsayılan demo hesabı üretmek çözüm değildir.
   Kimlik aktarımı için de bu görevde işlem yapılmadı. Geçerli mevcut hesabın
   kimliği belirlenemezse kurulum/onboarding kabulü BLOCKED kalır.
5. `config/database.env` yalnız yeni V2 DB'nin `V2_DATABASE_URL` değerini içerir;
   bağlantı loopback:55432, DB/rol yukarıdakiyle eşleşmelidir. Gerçek özel DB
   parolası yalnız bu owner-only env dosyasında tutulur; örnek/public demo parolası,
   V1 env'i veya CLI argümanı kullanılmaz. `config/onboarding.env`, repodaki
   `deploy/cebeci-v2-pilot/onboarding.env.example` taslağından hazırlanır. Ofisteki
   env dosyası mutlak WSL yollarıyla VDS'ye aynen kopyalanmaz.
6. Yalnız doğrulanmış ID `V2_ROUTER_ONBOARDING_OPERATOR_IDS` içine yazılır;
   `V2_ROUTER_ONBOARDING_ENABLED=false` ve `V2_CEBECI_API_SSL_ENABLED=false`
   **korunur**. CIDR yalnız `10.250.0.19/32`, port yalnız `8729`, kaynak
   `10.250.0.1` kalır. TLS chain/IP SAN/reviewed SHA-256 pin değişmez.
7. Yalnız ayrı kurulum onayı varsa yeni iki unit kurulup başlatılır. Hazırlanmış
   unit'ler `Restart=no`, loopback-only API/DB, private yazma alanları ve ayrı OS
   kullanıcıları kullanır. Repository bu unit'leri otomatik kurmaz/başlatmaz.
   Servis başlangıcı, GET veya sayfa açılışı router bağlantısı başlatmaz. Bu görev
   VDS'de unit kurmadı, servis/DB başlatmadı ve migration/deploy yapmadı.

Kurulum onayından sonra yalnız panel erişim tüneli (router bağlantısı değildir):

```bash
ssh -N -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes -L 127.0.0.1:18080:127.0.0.1:18080 mikadmin@185.139.5.51
```

Tarayıcı `http://127.0.0.1:18080` kullanır. API ve frontend aynı origin'dedir;
credential/panel oturumu SSH ile şifreli taşınır, public HTTP/Vite servisi yoktur.
Bu tünel burada açılmadı. TLS doğrulaması routera kadar backend'de zorunludur.

## Operatör kimliği ve panel akışı

`/api/v1/auth/me` ve `/router-registry/options` mevcut V2 auth mekanizmasını
kullanır. Her istekte kullanıcı DB'den yeniden okunur. Yeni `operator_candidate`
yalnız aktif, merkezi yetkili, bootstrap olmayan ADMIN'in ID/revizyonunu döndürür;
username/email/password/hash veya secret yolu içermez. Bu **yetki verme değildir**.
Aday ID env allowlist'inden türetilmez; UI'de salt-okunur olarak gösterilir.
`demo-user`, VIEWER ve sınırlı/pasif ADMIN eligible değildir. Mevcut auth/CSRF/
allowlist güvenlik kapıları korunur.

Bu görevde mevcut V2 kullanıcı deposuna yapılan **tek** salt-okunur okuma
`V2_IDENTITY_DATABASE_UNAVAILABLE` verdi. Kimlik yok denmedi; gerçek ID seçilemedi,
allowlist doldurulmadı ve yeni hesap oluşturulmadı. Önceki ofis private profil ve
pilot materyaline dokunulmadı; hazırlık template'i kapalı ve operator listesi boştur.

Kurulum ve **ayrı gerçek pilot onayı** tamamlandıktan sonra panelde:

- Gerçek Router / Salt Okunur Pilot → açık onayla **Test Et**: bir identity/resource
  oturumu; kaynak, TLS chain, IP SAN, pin ve sabit kimlik/model/sürüm kontrolü.
- **Kaydet**: aynı actor'a ait süreli doğrulamayı transaction/audit ile kalıcı
  kaydeder; ikinci cihaz bağlantısı açmaz. Aynı istek tekrarında çift kayıt yoktur.
- Router detay / Güvenli Bağlantı → ayrı onaylı **Salt Okunur Detay**: tek oturumda
  izinli sabit metadata descriptor'ları; PPP/Hotspot kullanıcı adı/parola veya
  IPsec SA istenmez. Önceki snapshot başarısız yeni okumada korunur. PPPoE/Hotspot
  yazma, IPsec/RADIUS/config değişikliği, otomatik polling/retry yoktur.

Kapıyı açma veya bu gerçek üç adımı çalıştırma bu görevin kapsamı değildir.
Yerel testler yeni statik panel/API sıralaması, path/symlink izolasyonu, kapalı
unit/env, actor projection ve mevcut mocked Test→Kaydet→Detay sözleşmesini kapsar.
Gerçek VDS kurulum/HTTP/PG/panel kabulü **BLOCKED / çalıştırılmadı**.
