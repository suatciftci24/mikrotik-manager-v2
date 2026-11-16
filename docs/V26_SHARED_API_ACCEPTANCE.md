# V2.6 merkezi API / ev-ofis kullanımı — 2026-11-16

Başlangıç main-guncel/3ac1f2a, temiz çalışma ağacı, üç stash. Son PPPoE,
paket, abone oluşturma ve Dashboard kabul kayıtları esas alındı.

Ev ve ofis ortak kullanımında mevcut `https://v26.mikmanager.com.tr/`
origin'i tarayıcıda açılır. Ofis WSL repo kökünde `./dev.sh --central`
yalnız bu adresi ve mevcut hesapla giriş bilgisini gösterir; tarayıcı,
API, Vite veya PostgreSQL başlatmaz. Adres bu oturumda ağ üzerinden
teyit edilemedi; canlı kullanılabilirlik ve VDS sürüm eşitliği iddia edilmez.

Frontend `/api/v1` ve `credentials: include` kullanır; merkezi panelde
aynı origin üzerindeki API ve mevcut oturum geçerlidir. Yerel Vite proxy
loopback API'ye gider; yerel geliştirme ortak VDS veri oturumu değildir.
Merkezi oturum cookie'sini localhost'a taşımayın; DB URL'si veya yönetici
parolasını Git'e eklemeyin. Yeni hesap, parola sıfırlama veya veri aktarımı yok.
Git eşitliği DB eşitliği değildir; merkezi paneldeki sentetik workspace de
canlı RouterOS/RADIUS entegrasyon kanıtı değildir.

Tespit edilen yerel kalıntılar (yalnız dizin adı envanteri):
`.local/postgres-v2-demo`, `.local/postgres-v2-socket`, `.local/aaa-office-fixture`,
`.local/cebeci-pilot`, `.local/acceptance`, `.local/runtime` ve eski kabul/yayın
hazırlıkları. Bunlar abone/workspace satır sayısını veya çalışan DB kimliğini
kanıtlamaz. İçerikler ve mevcut yönetici hesabı korunur. Uygulamada LEGACY demo,
kalıcı subscriber/router workspace ve AAA fixture kaynakları hâlâ ayrıdır.
VDS'deki kalan demo workspace satırları bu oturumda doğrulanamadı; silinmedi.

Düzeltmeler: ortak panel erişimi yerel bootstrap'tan önce ayrıldı; geçersiz
başlatma argümanları bağımlılık/DB işlemlerinden önce reddedilir. Eksik abone
ve router API endpointleri 404 durumunu korur ve bağlı API adresi/sürümünün
kontrolünü ister; kullanıcıya koşulsuz servis yenileme yönlendirmesi vermez.

Hedefli doğrulama sonuçları PROGRESS.md görev kaydında. Üretim HTTP/PG veya
görsel kabul yok; deploy/restart/migration, veri silme veya cihaz işlemi yok.

## Merkezi hazırlık devamı — 2026-11-16

Temel 3b4f353. Bildirilen VDS b4e78a4 bu tabanın atasıdır (10 commit).
`git diff b4e78a4..3b4f353 -- backend/app migrations` boştur; UI ve başlatma/
belgeleme farkları vardır. Bu, VDS checkout'unun güncel doğrulaması değildir:
SSH socket EPERM ile engellendi. İlk fetch DNS hatası verdi.

Merkezi GET `/api/ready` bu oturumda başarılı: service=mikrotik-manager-v2,
runtime_profile=v26-isolated-acceptance, api_version=v1,
router_workspace_version=1, database_checked=false. Yanıttaki build_id Git SHA
olarak yorumlanmaz. Kimlikli oturum/DB/ev ve ofis tarayıcı kabulü yapılmadı.
Önceki aynı-origin `/api/v1`, cookie ve `--central` çözümü tekrar değiştirilmedi.

### Şema hazırlığı

Katalog ORM modelleri önceki commitlerde vardı; sürümlü SQL dosyası yoktu.
`011_package_catalog.sql` iki paket tablosu ve audit indeksini transaction içinde
oluşturacak açık migration artefaktıdır; bu görevde uygulanmadı. Kullanıcı,
rol, abone, router veya mevcut audit satırını değiştirmez. IF NOT EXISTS yoktur:
kısmi/uyuşmayan şemayı gizlemek yerine hata verir. Otomatik setup'a bağlanmadı.
007/008 ön koşuldur. Hedefte tablolar zaten varsa migration körlemesine
çalıştırılmaz; önce katalog doğrulaması gerekir. Eksik DB şeması Git diff'inden
çıkarılamaz; kaynak eşitliği kurulum eşitliği değildir.

Workspace 008 doğrulayıcısı artık yalnız iki geçerli tablo kümesini kabul eder:
subscribers/events veya bunlarla birlikte packages/package_events. Paketler
varsa kolon/tip/null, PK, unique ad, audit indeksi ve revision check doğrulanır.
Kısmi katalog veya bilinmeyen tablo hâlâ reddedilir.

### Salt okunur envanter ve temizlik önizlemesi

Yeni `app.v26_shared_preflight.inspect_target(engine)` URL'yi bağlantıdan önce
127.0.0.1:55433/mikrotik_v26_acceptance, v26_acceptance rolüne sabitler; URL
query override'larını reddeder. Tek REPEATABLE READ / READ ONLY transaction,
5s sorgu sınırı ve finally rollback kullanır. Sunucudan aynı DB/rol/port kimliği
tekrar doğrulanır. Router/abone/katalog şeması ve en az bir aktif ADMIN şarttır.
Çıktı yalnız workspace ID/revizyon/kind/router bağı ve aktif ADMIN sayısını
verir; parola/hash/oturum ve fields JSON alınmaz. Şema sonucu yalnız workspace
ve katalog kapsamındadır; auth şemasının tamamı veya canlı işlev kabulü değildir.

Gelecekte bu kaynak ayrı onaylı olarak VDS'ye alındıktan sonra, **VDS terminalinde**
mevcut V2.6 ortamıyla `PYTHONPATH=backend <V2.6-python> -B -m app.v26_shared_preflight --inspect`
yalnız okuma yapar. Varsayılan ofis DB'si reddedilir; başka DB fallback'i yoktur.
Bu komut bu görevde gerçek DB'ye karşı çalıştırılmadı.

`cleanup_preview(snapshot, router_ids=..., subscriber_ids=...)` yalnız açıkça
seçilmiş mevcut kayıtlar için revizyonlu gözden geçirme çıktısı üretir. Boş
seçim hiçbir aday seçmez. TRUST_PROFILE, bilinmeyen ID, ADMIN yokluğu ve seçilen
routera bağlı korunacak abone varsa reddeder. Abone canonical DEMO_ROUTER'a
bağlı olmalıdır. Kullanıcılar/user_audit, workspace audit/events ve paket
kataloğu korunur. Demo ID öneki veya ana demo tablosunun boşluğu silme kanıtı
sayılmaz. Çıktı SQL veya çalıştırılabilir komut içermez; execution_enabled=false.

Silme executor'ı bu pakette yoktur. Gelecekte uygulama istenirse ayrı açık canlı
onay, doğrulanmış yedekler, taze kimlik/ADMIN/revizyon kontrolü, tüm dış FK ve
JSON/referans bağlarının kontrolü, tek kilitli transaction ve atomik audit/geri
alma gerekir. Bu preview eski snapshot ile işlem yapma yetkisi vermez. VDS'de
kalan gerçek workspace sayıları SSH erişimi olmadan bilinmiyor; yerel dizin
adları bu kayıtların yerine geçirilmez. Bu nedenle uçtan uca merkezi kabul açık.

Doğrulama: 6 yeni offline test + 3 mevcut workspace doğrulama testi PASS;
package katalog drift/kısmi şema, salt okunur sıra/rollback, yanlış hedefin
bağlantı öncesi reddi, aktif ADMIN yokluğu ve temizlik referansları kapsandı.
Frontend değişmedi; önceki başarılı frontend test/build tekrarlanmadı. Gerçek
PG/migration/HTTP yazma veya browser testi yok. Üç stash kimliği korundu.

## Yayın provası devamı

011'in ilk sürümündeki duplicate halinde durma davranışı, gerçek PG16 izole
prova sonrası uyumlu tekrarda no-op, kısmi/drift halinde red olarak değiştirildi.
`--allow-missing-catalog` katalog yokken envanter/önizleme almayı sağlar; migration
hazır/uygulandı iddiası üretmez. Güncel yedek, rollback, paket artefaktı ve tek
canlı geçiş kararı: [Yayın dry-run kabulü](V26_RELEASE_DRY_RUN_ACCEPTANCE.md).
