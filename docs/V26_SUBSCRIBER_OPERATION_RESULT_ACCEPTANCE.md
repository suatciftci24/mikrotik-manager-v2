# V2.6 abone işlem sonuçları — 2026-11-08

Başlangıç main-guncel/fe0f31a, temiz ağaç; uzak dal aynı tam SHA ile
ls-remote üzerinden doğrulandı. Altın Kurallar, güncel PROGRESS, özellik
koruma ve v26-test-001 işlevsel kabul kayıtları okundu. **Yerel hedefli kabul
PASS; Chromium ve gerçek HTTP/PG kabulü bu çalışmada doğrulanmadı.**

## Kanıtlanan eksik ve düzeltme

Sunucuda kayıt+audit transaction'ı, actor/UUID idempotency, revizyon/kaynak/
router kontrolü ve hata rollback'i zaten vardır; yeniden yazılmadı. Eksik
frontend başarı doğrulamasındaydı: QuickActions yalnız sonuç abone ID'sine,
günlük receipt yalnız değişen değere, yenileme tarih/kaynak/revizyona bakıyordu.
Böylece doğru ID ile yanlış router/değer döndüren yanıt başarı gösterilebilirdi.

- QuickActions önizlemede beklenen kayıt/revizyon/router/kaynak/abone adı/
  kullanıcı/paket/fiyat/durum/bitiş değerlerini sabitler. Başarılı yanıtın
  is_demo/persistence ve bütün bu değerleri eşleşmeden sonuç/callback başarı
  sayılmaz. Yanıt 15 saniyede gelmezse abort ve Türkçe belirsiz sonuç mesajı;
  pencere kapanışında bekleyen okuma iptal edilir. Aynı önizleme/UUID ile
  mevcut idempotent endpoint'ten sonuç doğrulanır; yeni komut üretilmez.
  Eşzamanlı onay tıklamaları tek POST; tamamlanmış işlem yeniden gönderilmez.
- Kalıcı günlük receipt'te başarılı sonuç için expected_revision+1, önceki/
  sonraki router, değişen değer ve hatasız kayıt kontrol edilir. Kaydedilmiş
  receipt'in aktörü ve timezone içeren geçerli zamanı gerekir. Yanlış sonuç
  GET ile kurtarmada da başarı sayılmaz. Kayıtlı başarısız receipt'in güncel
  revizyonu/routerı beklenenden farklı olabilir; bu ret kanıtı korunur.
- Kalıcı yenileme router/kullanıcı/erişim türü/paket/durumun değişmediğini de
  dondurulmuş önizlemeden doğrular. Legacy oluşturma ve düzenleme, kayıt
  kaynak işaretini, plan fiyatını ve değişmemesi gereken tarih/hesap/router/
  kullanıcı alanlarını denetler. POST sonrası props yenilense de ilk komut
  doğrulanır; yeni request/yan etki oluşturulmaz. Mevcut create/edit recovery
  yalnız GET, legacy QuickActions ise mevcut idempotent POST replay kullanır.
- Ortak işlem hata metni ağ/zaman aşımı/bozuk JSON/401/403 durumlarında
  Türkçedir; iş kuralı hata açıklamaları korunur. İşlem dialog'ları aria-busy
  bildirir; uzun önizleme alanları mobilde sarar ve düğmeler en az44px olur.
  Toplu günlük işlemde her abonenin transaction'ının bağımsız olduğu ve bir
  abonenin başarısının diğerinin başarısını gerektirmediği açıkça yazılır.

Abone listesi/detay/Dashboard/rapor/uyarı yenilemesindeki ortak
subscriberSaveDependencies korundu; başarılı ve belirsiz sonuçta mevcut
invalidation akışı kullanılır. LOCAL/RADIUS kaynak devri veya gerçek cihaz
hesabı yazma eklenmedi. Yeni API/menü/bileşen/bağımlılık yok.

## Doğrulama

57 hedefli frontend sentetik test PASS:
subscriberSaveRecovery33, subscriberRenewalRecovery12, subscriptionActions6,
subscriberDailyManagement2, operationGetRecovery4. Bozuk router/kaynak/değer/
revizyon/fiyat/metadata yanıtı, bilinmeyen/403 GET, yanıt kaybı, aynı komut,
çift tıklama, sonuç öncesi başarı callback reddi ve bağımlı yenileme denetlendi.
Mevcut eski QuickActions fixture'ı hatalı tarih ve ilerlemeyen revizyon
üretiyordu; artık onaylanan komut tarihini ve revision+1'i döndürür. Eksik
router receipt ve is_demo/fiyat fixture alanları gerçek sözleşmeye uyarlandı;
ürün doğrulaması/assertion gevşetilmedi. Başarılı kapsam sadece yeni test veya
ilgili ürün değişikliğinde tekrarlandı; yeni fiyat testleri tekil seçildi.

9 hedefli backend test PASS (ürün backend'i değiştirilmedi):

- SubscriberTransactions: oluşturma/yeniden okuma/düzenleme/bitiş/audit;
  audit hatasında hesap ve router korunması (2).
- RenewalTests: tek receipt/replay ve stale/audit hatasında rollback (2).
- DailyManagement: çapraz router toplu kısmi sonuç/replay ve audit/UUID
  çakışmasında mutasyon olmaması (2).
- QuickActionsTests: oluşturma/paket/durum/aynı kullanıcı reddi; liste/detay/
  audit eşitliği ve replay; eşzamanlı replay'in yalnız bir değişiklik yapması (3).

Backend testleri yalnız private TemporaryDirectory içindeki SQLite ve bellek
sentetik depolarında çalıştı; mevcut/üretim DB veya cihaz kullanılmadı. Geçici
SQLite testleri güncel PostgreSQL+HTTP kapanış kanıtı değildir.

Tek `npm run build` (tsc -b + Vite) PASS. Ana bundle610.24kB; mevcut >500kB
uyarısı sürer. `git diff --check` PASS. Chromium için önceki EPERM kanıtı
kullanıldı; yeni browser/socket veya güvenlik gevşetme denemesi yapılmadı.
Gerçek mobil/browser PASS iddiası yok. Önceki Dashboard rollback, genel
kabul ve PG/HTTP engelleri bu görevin başarılı hedefli testleriyle kapanmaz.

V1/V2.5/VDS/router/RADIUS/IPsec/canlıDB/migration/silme/deploy/restart işlemi
ve credential kullanımı yok. Yalnız mevcut izole sentetik test depoları kullanıldı.

- Normal `git push origin main-guncel` denendi; push BLOCKED:
  `Could not resolve host: github.com`. Yerel tek commit korunur.
  Uzak okuma başarılıydı; push DNS aşamasında durdu. Sonraki aktarım
  ağ erişiminde aynı normal push işlemidir; force push yok.
