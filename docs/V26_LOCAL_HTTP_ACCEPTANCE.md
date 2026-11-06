# V2.6 izole yerel PostgreSQL/HTTP kabulü — 2026-11-06

Sonuç: **BLOCKED**. Ürün hatası kanıtlanmadı; ürün kodu değiştirilmedi.

Başlangıç: main-guncel / 78e2c1d6836be1385272dce7ce69f99eccb33f86.
Kullanıcının belirttiği 9eca386 yerel Git nesnelerinde çözümlenemedi; bu
çalışmanın o GitHub sürümüyle aynı olduğu doğrulanamadı.

AGENTS.md, güncel PROGRESS, V26_ISOLATION_ACCEPTANCE,
V26_IDENTITY_SETUP ve mevcut V26 kabul kayıtları incelendi. Tarihsel VDS
PGDATA uyuşmazlığı ve Dashboard BLOCKED/ROLLBACK bu yerel görevle kapanmadı.
Önceki kimlik, PostgreSQL ve ASGI PASS testleri tekrar çalıştırılmadı.

## Ortam kanıtı

- PostgreSQL16 initdb ve repo .venv/bin/python mevcut.
- Tek AF_INET/SOCK_STREAM 127.0.0.1:0 bind denemesi:
  PermissionError / errno 1 / Operation not permitted.
- AF_UNIX socket nesnesi oluşturulabildi; Unix socket bind veya PostgreSQL
  başlatılması denenmedi. Bu kontrol PostgreSQL kabulü değildir.
- Mevcut test_v26_identity_postgres altyapısı yalnız yeni özel küme ve
  127.0.0.1:55433 kullanır. Loopback engelinden sonra cluster/API başlatma,
  mevcut veritabanına yönelme veya aynı başarısız kontrolü tekrarlama yapılmadı.

## Çalıştırılamayan kritik senaryolar

Gerçek loopback HTTP üzerinden ADMIN login/me/logout, anonim ve rol yetkileri,
UUID ile işlem sonucu sorgulama, sentetik abonelik oluşturma/düzenleme/uzatma
ve toplu işlem kısmi sonuç/idempotency kabulü: **BLOCKED; çalıştırılmadı**.
Önceki ASGI veya PostgreSQL PASS kayıtları bu uçtan uca kabul yerine sunulmadı.

## Koruma ve teslim

Mevcut izlenmeyen bileşen/yedek dosyaları korunur. PROGRESS mevcut içeriği
korunarak yalnız bu görevin kaydı eklenir. DB/ADMIN/parola oluşturulmadı;
migration, SSH, servis restartı, deploy, VDS, V1/V2.5 veya gerçek cihaz/veri
üzerinde işlem yapılmadı. Güvenlik kontrolleri değiştirilmedi.

GitHub DNS tek getent ahosts github.com denemesinde exit 2 verdi. Uzak SHA
ve branch güvenliği doğrulanamadı; push ön koşulları sağlanmadığı için push
çalıştırılmadı. Tekrar döngüsü yok.

Sonraki tek hedef: loopback izni olan izole yerel ortamda, doğrulanmış
main-guncel sürümüyle eksik PostgreSQL/gerçek HTTP kabulünü tamamlamak.

## Güncel yerel hazırlık — d9370e9 sonrası, 2026-11-06

Yukarıdaki kayıt tarihsel eafe41b sonucudur. d9370e9 entegrasyonu ile
9eca386 ve eafe41b aynı geçmişte korunur. Gerçek PG/HTTP kabulü hâlâ **BLOCKED**;
bilinen loopback izin hatası bu görevde tekrar denenmedi.

Yeni ağsız test, workspace guard'ının V2.6 profili altında varsayılan
`v2_demo` şemasıyla `Invalid V2.6 acceptance schema` hatası verdiğini kanıtladı.
Guard artık mevcut demo adaptörüyle aynı profil seçimini kullanır:
V2.6 için `v26_acceptance`, diğer desteklenen yerel profiller için `v2_demo`.
URL/DB/rol/port, kapalı cihaz erişimi ve sentetik marker doğrulaması aynıdır.
Yanlış hedefte bağlantı öncesi ret; yanlış marker/cihaz kapısında ret korunur.
Bu ağsız doğrulama, gerçek PG/HTTP başarısı olarak sunulmaz.

Eksik ağsız kontroller: yeni çalışma alanı profil/marker kontrolleri (3) ve
yeni gerçek HTTP kabul aracının güvenli durma/transport kontrolleri (6) PASS.
Eski PASS suite/build tekrarlanmadı. Mevcut fixture import'undaki TestClient
bağımlılığı yalnız eski istemci fabrikasına taşındı; yeni gerçek HTTP yolu
standart kütüphane kullanır, kurulu olmayan httpx için paket kurulumu gerekmez.

### İzinli yerel ortamda tek çalıştırma adımı

**Ev WSL terminali, suat@DESKTOP-MT2JS7H, proje kökü:**

```bash
cd /home/suat/Codex-Projects/mikrotik-manager-v2 && PYTHONPATH=backend .venv/bin/python -m backend.tests.v26_http_acceptance --run
```

Bu komut burada ÇALIŞTIRILMADI. Aracın syntax/import ve ağsız güvenlik
kontrolleri doğrulandı; tam fixture/runtime başarısı henüz doğrulanmadı.

- Root kullanıcı, farklı cwd, eksik PG16 araçları veya mevcut kabul kökü
  (bozuk symlink dahil) güvenli ret verir. Mevcut kökü silmeyin/taşımayın.
- API için 127.0.0.1:18996 tek kez exclusive bind edilir; dolu/yasak portta
  PG kurulumu başlamaz. Başka listener'a istek/kimlik bilgisi gönderilmez.
- Önceki `V2_*`/`PG*` hedef ve kimlik bilgileri kullanılmaz. Mevcut exclusive
  fixture yalnız yeni private `/tmp/mikrotik-v26-acceptance/postgres-test`
  PG16 kümesini, 127.0.0.1:55433 ve sentetik kabul DB/rolünü oluşturur.
  Gerçek kullanıcıdan parola alınmaz; yalnız geçici sentetik hesaplar vardır.
- Güncel DisposableClusterGuard yalnız oluşturulan kümenin yol/UID/izin/PG16/
  device-inode kimliğini test süresince doğrular. Ürün PGDATA kapısı değişmez.
  Test tabloları sadece yeni kümede hazırlanır; mevcut DB üzerinde migration,
  veri yazımı veya servis yönetimi yoktur. İlk kimlik şeması mevcut fixture'ın
  test kurulumudur; üretim kurulum komutları çağrılmaz.
- Yeni senaryo gerçek uvicorn/HTTP cookie login, anonim401, LOCAL ADMIN/me,
  eksik işlem başlığı403, PPPOE/HOTSPOT create, edit, tekil uzatma ve toplu
  kısmi SUCCESS/FAILED sonucunu sınar. Özgün UUID receipt'leri sonraki
  değişikliklerden sonra okunur; tablo snapshot'ı GET'lerin yazmadığını
  doğrular. Eksik UUID UNKNOWN, VIEWER403, yabancı ADMIN için UNKNOWN ve
  logout sonrası401 beklenir. Gerçek auth/üretim workspace guard kullanılır;
  oturum dependency override veya no-op guard yoktur. Yalnız test kümesinin
  session factory'si route servislerine bağlanır.
- Yalnız yeni socket senaryosu seçilir; eski beş PASS testi çalıştırılmaz.
  HTTP proxy/redirect/otomatik POST retry yoktur. Cookie/sır/DSN/response gövdesi
  yazdırılmaz. Sonuç ve başarısız aşama adı raporlanır. Cleanup hatası PASS
  değildir; yalnız bu aracın başlattığı API/küme kapatılıp kendi kökü temizlenir.

Gerçek komut PASS olmadan genel PG/HTTP BLOCKED kapanmaz. Browser veya canlı
sistem kabulü bu komutun kapsamı değildir. Push PASS olmadan yeni geliştirme
görevine geçilmez.
