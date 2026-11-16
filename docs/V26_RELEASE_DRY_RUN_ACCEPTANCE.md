# V2.6 yayın dry-run / canlı geçiş planı — 2026-11-16

Başlangıç main-guncel/60d949b temiz. Altın Kurallar ve son shared API kabulü
okundu. VDS b4e78a4 ve 17 tablo / 2 kullanıcı / 2 workspace abonesi / 12 workspace
işlemi / 1 router bilgisi **kullanıcı beyanıdır**; canlıdan tekrar ölçülmedi.
17 tablo sayısı tek başına paket tablolarının varlığını veya şema uyumunu kanıtlamaz.

## İzole prova

Yeni /tmp/v26-release-dryrun-* sahibi-private PG16 cluster kullanıldı.
PostgreSQL single-user modu ağ/socket açmadan çalıştı; mevcut DB'ler, servisler,
router/RADIUS/IPsec veya VDS ile bağlantı yok. Fixture 2 sentetik kullanıcı,
2 abone, 12 event ve 1 DEMO_ROUTER içerir; VDS verisinin kopyası değildir ve
17 tablonun tamamının simülasyonu sayılmaz. Başarılı fixture'lar silinmeden,
backend'ler kapalı olarak korundu.

Gerçek PG16'da 011 ilk kurulum ve mevcut paket satırıyla tekrar çalıştırma PASS.
Yanlış DB, kısmi katalog ve varchar kolon sapması reddedildi; tablo kısmen
oluşmadı. Yönetici hash/aktiflik/rolü ve 2/2/12/1 sayıları korundu. Durdurulmuş
cluster kopyasından ayrı absent-only PGDATA'ya geri dönüş provası PASS; paket
öncesi durum doğrulandı. Bu, canlı pg_dump yedeğinin restore testi değildir.

011 artık sabit DB/rol kontrolü, transaction/advisory lock, lock/statement timeout,
hem-yok oluşturma / hem-var doğrulama / kısmi-var reddi kullanır. Mevcut uyumlu
şema tekrarında veri veya tablo değiştirmez. Kolon/tip/null, PK/unique/revision
CHECK ve audit indeksini doğrular; uyumsuz objeyi otomatik onarmaz. SQL yalnız
bilinen paket objelerini inceler; geniş DB uyumu ayrıca preflight gerektirir.

`--allow-missing-catalog` ile salt okunur preflight katalog yokken de workspace
ve ADMIN envanterini raporlar; catalog_status=migration-required olur. Bu durum
uyumlu katalog veya migration başarısı sayılmaz. Kısmi/bilinmeyen şema reddi sürer.
Temizlik çıktısı her durumda execution_enabled=false; canlı silme kodu yok.

## Dağıtım artefaktı

Ofis WSL repo kökünde `python3 tools/prepare-v26-dry-run.py --dry-run` yalnız
.local altında yeni private artefakt üretir: commit'e sabit git archive,
SHA256 manifest, kaynak kopyasında frontend build ve hash'li dist arşivi.
Arşiv backend/app, migrations ve tracked frontend içerir; VDS .env/venv,
yönetici hesabı, DB veya mevcut ortam yapılandırması taşınmaz. Yerel bağımlılık
kurulumu, SSH, deploy, restart veya migration çalıştırmaz. Script uncommitted
kod paketlemez; commit'ten çalışır. Manifest source_only=true kaynak arşivini
belirtir; frontend-dist ayrı artefakttır. deploy_enabled=false'dur.

## Yedek ve rollback planı — uygulanmadı

1. Canlıya geçişte önce sabit VDS uygulama yolu/HEAD, V26 profil/port/DB/rol,
   tam katalog şeması, tüm 2 kullanıcı ve aktif ADMIN'ler yeniden doğrulanır.
   Aynı-origin merkezi HTTPS/API ve kimlikli ev/ofis oturumu kabulü yapılır.
   Preflight başarısızsa dağıtım ve migration durur; fallback DB yoktur.
2. Yalnız V26 için kısa yazma bakım penceresi alınır; kod, özel ortam ayarları,
   unit/çalıştırma tanımı ve mevcut frontend artefaktı sahiplik/izinleriyle ayrı
   private dizine yedeklenir. VDS yapılandırması repo örneğiyle değiştirilmez.
3. VDS'de umask 077 ve mevcut özel kimlik bilgisi mekanizmasıyla PostgreSQL16
   pg_dump custom-format yedeği yalnız 127.0.0.1:55433/mikrotik_v26_acceptance,
   v26_acceptance rolünden alınır. Parola komut satırına/Git'e yazılmaz. Tüm
   V26 DB şemaları/verileri/users/audit içerilir; başka DB veya cluster-geneli
   roller için dump/DDL yapılmaz. Backup dosyası, SHA256, boyut ve pg_restore
   --list doğrulanır; liste tek başına restore başarısı sayılmaz.
4. Bu gerçek backup ayrı ve yeni izole restore hedefine geri yüklenip katalog,
   ADMIN dahil iki hesabın tüm değerleri, 2 abone, 12 işlem, 1 router ve yeni
   sayım/bağlar doğrulanmadan canlı geçiş PASS denmez. Sayılar beyana göre zorla
   eşitlenmez; farklıysa durulur ve yeni snapshot değerlendirilir. Yedekler
   private tutulur; bu görevde canlı dump alınmadı/restore yapılmadı.
5. Yalnız 011 gerektiği metadata ile kanıtlanırsa, onaylı bakım penceresinde
   aynı DB/rol/port ve yedek kimliği pinlenerek tek migration uygulanır. Katalog
   zaten uyumluysa no-op doğrulama; kısmi/drift varsa BLOCKED. Yeni kod/UI, mevcut
   VDS ortamını koruyarak yayımlanır; yalnız V26 servisi için onaylı reload/restart
   ve gerçek HTTPS/API/kimlikli okuma doğrulaması yapılır. Bu adımlar burada yok.
6. Kod/sağlık kabulü başarısızsa önceki doğrulanmış kod + UI ve VDS ayarlarıyla
   V26 kod rollback'i yapılır. 011 additive tablolar bırakılır; eski b4e78a4
   zaten aynı paket ORM modellerini içerir. DROP/TRUNCATE/down migration yok.
   Migration SQL hatasında transaction rollback olur. Commit edilmiş DB verisini
   geri almak gerekiyorsa otomatik restore yapılmaz: sonraki yazılar/yeni paketler
   için kayıp analizi, tekrar yedek ve ayrı kapsamlı restore onayı gerekir.

## Demo temizlik önizlemesi ve hesap koruması

Gerçek ID/revizyon snapshot'ı bulunmadığı için canlı seçim **boş**: 0 silme,
2 kullanıcı, 2 abone, 12 işlem, 1 router korunacak. Beyan edilen 2 workspace
abonesi ve 1 router yalnız inceleme kapsamıdır, otomatik silme adayları değildir.
Taze snapshot sonrası açık ID seçimiyle iki abone + bağlı DEMO_ROUTER için plan
üretilebilir; korunan abone routera bağlıysa router seçimi reddedilir. Kullanıcı,
user_audit, tüm workspace event/audit, paketler ve trust profilleri korunur.
Ad/ID/demo öneki silme yetkisi değildir; hesap/parola/rol değişikliği yoktur.
Temizlik canlı yayın onayına dahil değildir.

## Sonuç ve gereken tek karar

Yerel PG16 migration/geri dönüş provası ve offline preflight testleri PASS.
Canlı DB şeması, gerçek yedek/restore ve kimlikli ev/ofis kabulü BLOCKED/bekliyor.
Canlı geçiş için tek karar: bu rapordaki kontroller ve doğrulanmış yedek/restore
şartıyla **yalnız V2.6 kod/UI yayını + gerekiyorsa 011 + yalnız V26 restartı**
için kapsamlı bakım penceresi onayı. Demo silme ve DB restore bu karara dahil
edilmez. Onay bu görevde istenmedi veya kullanılmış sayılmadı.
