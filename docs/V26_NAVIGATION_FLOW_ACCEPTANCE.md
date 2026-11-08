# V2.6 merkezler arası navigasyon kabulü — 2026-11-08

Başlangıç `main-guncel/749c9b6`, temiz çalışma ağacı; uzak dal aynı SHA ile
salt okunur doğrulandı. Altın Kurallar, güncel PROGRESS, genel kabul ve özellik
koruma raporları esas alındı. Yerel hedefli doğrulama **PASS**.

- Dashboard bağlantısı mevcut Günlük Yönetim Merkezi'ni açık DEMO kaynağı,
  LAST_24 dönemi ve PPPOE filtresiyle açar. Önceki commit'in kaydırması bu
  merkezde kullanılmayan RecentOperations içindeydi; hedef mevcut rapor
  bölümüne eklendi. Doğrulanmış veri render edildikten sonra kaydırma/odak
  uygulanır; boş sonuç da hedeflenir, yükleme/hata/V1 hedeflenmez. Hash
  değişimleri dinlenir. Takvim günü yerine tam 24 saat; alt sınır dahil,
  gelecek ve erişim türü belirsiz işlemler PPPoE listesine alınmaz.
- Mevcut OperationDetails abone, doğrulanmış router bağı ve abonenin mevcut
  İşlem Geçmişi sekmesine geçer; dialog geçişten önce kapanır. Router bağı
  yoksa bağlantı üretilmez. SubscriberDeviceCenter yalnız bilinen sekmeleri
  hash'ten kabul eder. Mevcut API ve sunucu yetki kapıları korunur.
- Alarm router/abone hedefleri sentetik kaynaklarını açık seçer; boş router
  kimliği bağlantı üretmez. MikAjanı ve operasyon raporu bağlantıları ortak
  router yetki politikasını kullanır; yetkisizlik açıklanır. Olay kimliği ve
  rapor kategorisi korunur. MikAjanı'nda bulunamayan doğrudan kanıt sessiz
  kalmaz. Yenilenen alarm detayı yükleme sırasında eski içeriği göstermez.
- Kalıcı geçmişin kısmi hatası ve merkezi yönetim yetkisi gereksinimi işlem
  listesinde görünür. Gerçek V1 geçmişi oluşturulmaz; kaynaklar birleşmez.
  API, bağımlılık, yeni bileşen veya menü eklenmedi; mobil düzen korunur.

## Doğrulama

Ağsız, sentetik fixture/React SSR ve hook kontrolleri: 42 hedefli test PASS:
`managementReport.test.mjs` (15), `managementReportView.test.mjs` (6),
`alarmCenter.test.mjs` (6), `subscriberCenter.test.mjs` (12),
`operationsNavigation.test.mjs` (3). Node v24 için
`--experimental-transform-types` kullanıldı. İlk strip-only çalıştırma TS
parameter property nedeniyle araç hatası verdi; transform ile giderildi.
Yeni hook fixture'ında useContext ve CSS loader eksikleri düzeltildi.
Eski alarm testi kaynakta bulunmayan ACK açıklamasını bekliyordu; açıklama
mevcut ACK davranışıyla uyumlu biçimde dialog'a eklendi. Yetkisiz fixture
rapor linki yerine açık ret, ayrı yetkili fixture gerçek hedefleri doğrular.
Assertion kaldırılmadı; kaynak/izin kontrolleri gevşetilmedi.

Son kaynakla TypeScript/Vite build PASS; mevcut >500 kB bundle uyarısı sürer.
İlk ara build de çalıştı; sonraki ürün değişiklikleri nedeniyle son build
tekrarlandı. `git diff --check` PASS. Gerçek tarayıcı/mobil cihaz veya canlı
uçtan uca kabul iddiası yok; önceki genel kabul/sağlık/PG-HTTP engelleri açık.
V1/V2.5/VDS/cihaz/RADIUS/IPsec/veritabanı/deploy/restart/migration/veri silme
veya gerçek abone işlemi yapılmadı.

Normal `git push origin main-guncel` denendi; `Could not resolve host:
github.com` nedeniyle push BLOCKED. Başlangıç ls-remote başarılıydı; push
anındaki DNS engeli uzak güncelleme kanıtı değildir. Ağ erişiminde normal
push gerekir; force push kullanılmadı.

## 0c72519 sonrası akış tamamlama — 2026-11-08

Başlangıç main-guncel/0c72519 ve temiz ağaç doğrulandı. Altın Kurallar,
güncel ilerleme ve özellik koruma kaydı okundu. Kullanıcının önceki HTTP200
ve VDS'deki yedi kaynak dosyasının 0c72519 ile eşitlik çıktısı korunur;
bu çıktı tarayıcı kabulü veya sunulan bundle eşitliği sayılmaz. Bu görevde
VDS'ye erişilmedi. Kesinti sonrası aynı 11 yerel değişiklik korundu; son
commit yine 0c72519, uzak main-guncel de ls-remote ile aynı SHA doğrulandı.

Tamamlanan mevcut LAST_24/PPPOE bağlantısı ve veri sonrası kaydırma yeniden
yazılmadı. Bulunan eksikler mevcut yardımcılar üzerinden düzeltildi:

- Detayların Geri dön düğmesi artık günlük rapor veya operasyon raporunun
  filtre/sayfa/bölümünü, alarm merkezinin seçili alarm ve filtrelerini korur.
  linkedDetailHash ve detailReturnHash kullanılır; aynı uygulama hedefleri
  sınırlıdır, dış URL/izin verilmeyen merkez ve 4000 karakter üstü dönüş
  reddedilir; return_to zinciri iç içe çoğaltılmaz. Kaynak açık seçilir.
- Abone sekmesi ortak useListFilter ile URL'ye yazılır; yenileme ve hash
  değişiminde doğrulanmış sekme korunur. LOCAL/RADIUS, workspace/legacy ve
  yazma politikaları değiştirilmedi. İki detay merkezinde geri düğmesi etiketi
  gerçek dönüş davranışını kapsar; mobil yerleşim/CSS değiştirilmedi.
- Operasyon raporu audit dialog'u da mevcut abone/router/geçmiş geçişlerini
  sağlar; yükleme sırasında eski dialog gösterilmez. Alarm kimliği değişince
  dialog yeniden kurulur; önceki alarmın onay durumu/istek kimliği taşınmaz.

### Doğrulanan sınır

**Yerel hedefli kabul PASS; gerçek Chromium kabulü BLOCKED.** Mevcut
`managementCenter.browser.mjs --v23-final` yerel sunucu başlangıcında
`listen EPERM: operation not permitted 127.0.0.1` verdi. Sunucudan bağımsız
Chromium başlangıcı da yerel kurulu chromium-1248'de
`setsockopt: Operation not permitted` / SIGTRAP ile engellendi. İzinleri
gevşetme, kişisel profile bağlanma veya canlı hedefe geçme yapılmadı.
Bu nedenle DOM tıklama, gerçek kaydırma ve mobil görünüm için yeni Chromium
PASS/screenshot kanıtı yoktur. Eski browser PASS kayıtları silinmedi.

6 dosyada toplam **39 hedefli sentetik test PASS**:
operationsNavigation (5), routerSubscriberLinks (5), managementReportView (6),
alarmCenter (6), operationReport (5), subscriberCenter (12).
React SSR/hook/URL düzeyinde son24 veri sonrası kaydırma, kaynak hatası/boş/
yükleme ayrımı, router ve geçmiş geçişleri, sekme URL'si, dönüş bağlamı,
yetkisiz alarm bağlantıları ve mevcut kaynak/yazma politikaları doğrulandı.
Bu testler tarayıcı veya gerçek backend yetkilendirme kabulünün yerine geçmez.
Yeni çok hedefli Back testindeki tek hata, HashChangeEvent taklidinin ilk
hedef sonrası erken kaldırılmasıydı; finally döngünün dışına alındı, gerçek
assertion'lar korundu ve ilgili testler PASS. Kesinti öncesi başlayan tek
`npm run build` oturumunun tamamlanmış exit0 sonucu kesinti sonrası alındı:
TypeScript/Vite PASS, mevcut >500kB bundle uyarısı sürer. Ürün kaynakları
sonrasında değişmedi; başarılı build tekrarlanmadı. Diff kontrolü PASS.

Yeni API/bileşen/menü veya bağımlılık yok. V1/V2.5/VDS/router/RADIUS/IPsec/
veritabanı/migration/veri silme/deploy/restart işlemi yapılmadı. Tarihsel genel
kabul, Dashboard rollback ve güncel PG/HTTP kanıt engelleri kapatılmadı.

Bu devam görevinin normal `git push origin main-guncel` denemesi de
`Could not resolve host: github.com` ile BLOCKED kaldı. Yerel commit hazır;
ağ erişiminde normal push gerekir. Force push veya canlı işlem yapılmadı.

## 89af9ce sonrası operasyonel kullanılabilirlik — 2026-11-08

Başlangıç main-guncel/89af9ce, temiz çalışma ağacı. Altın Kurallar, güncel
ilerleme ve özellik koruma envanteri okundu; uzak main-guncel ls-remote ile
aynı tam SHA olarak doğrulandı. Mevcut demo listesi/filtreleri, son24 raporu,
veri sonrası kaydırma ve detay sekmeleri yeniden yazılmadı.

Tamamlanan eksikler:

- Kalıcı sentetik liste, mevcut URL filtre yardımcılarıyla arama/router/
  erişim türü/hesap durumu/sayfayı korur; arama ve filtre değişiminde sayfa1,
  filtreleri temizle işleminde yalnız liste kapsamı sıfırlanır. Query/router
  uzunluğu ve sayfa API sınırında tutulur. Legacy filtre anahtarları ayrı kalır.
- Merkezi İşlem Geçmişi'nin kaynak/abone/işlem/sonuç/sayfa filtreleri URL'de
  korunur; abone/router bağlantıları kendi doğru deposuna gider ve geçmiş
  filtresine dönüş taşır. Liste dönüşleri ortak bounded-return politikasına
  açık LEGACY/PERSISTENT/HISTORY kapsamında eklendi. Dış/recursive dönüş
  kuralları korunur. Alarm ve operasyon raporunda kaynak merkeze dönüş vardır;
  rapor/alarm filtresi değiştirilse veya temizlense de dönüş korunur.
- Günlük işlem dialog'unda router alarmları ve kaydın Türkiye gününe/abonesine/
  routerına bağlı audit raporu açılır. Alarm için can_view, rapor için
  can_view_reports+can_view gerekir. Bağsız/yetkisiz hedef üretilmez. Kalıcı
  workspace olayı legacy audit raporuna taşınmaz; mevcut kendi abone geçmişi
  bağlantısı ve kaynak açıklaması kullanılır. Yeni API/bileşen/menü yok.
- Kalıcı liste/geçmişte is_demo doğrulanmazsa içerik gizlenir. Yüklemede
  eski sonuç/toplam gösterilmez; toplu işlem düğmesi loading/error sırasında
  kapalıdır. Boş sayfa ve tamamen boş filtre sonucu ayrıldı; eksik router ve
  bilinmeyen hesap/kaynak doğru etiketlenir. Ağ/401/403 için ortak kaynak
  görünümünde anlaşılır Türkçe mesajlar vardır; diğer hata metinleri korunur.
- Mevcut satır bitiş uyarıları/LEGACY uyarı kartları korunur. Mobil kalıcı
  tabloda odaklanabilir yatay kaydırma, açıklaması ve sabit abone sütunu;
  44px dokunma hedefleri, saran filtreler/sayfalama ve işlem dialog'unda
  dar ekranda taşmayan değerler eklendi. Tüm envanter yerine yalnız sayfa
  kaydının uyarısı olduğu açıkça belirtilir; sahte genel toplam üretilmez.

### Kontroller

**Yerel hedefli kabul PASS; Chromium kabulü BLOCKED.** 8 dosyada 54 test:
operationsNavigation9, operationReport6, managementReportView6, alarmCenter6,
subscriberCenter12, subscriberFilters4, subscriptionAlerts6,
routerSubscriberLinks5. Sentetik fixture/SSR/hook kontrolleri; gerçek API/DB
veya tarayıcı kabulü değildir. Yeni test fixture string'indeki tırnak syntax
hatası düzeltildi; assertion/kaynak/yetki kapıları gevşetilmedi. Başarılı
kapsam yalnız yeni test/değişiklik gerektiğinde yeniden çalıştırıldı.

Tek `npm run build` (tsc -b + Vite) PASS. Ana bundle 607.28kB, mevcut >500kB
uyarısı sürer. Diff kontrolü PASS; gerçek veri/credential kullanılmadı.

Chromium engeli sınırlı araştırıldı: /proc/self/status NoNewPrivs1/Seccomp2;
loopback TCP bind/listen EPERM, yerel IPC socket oluşturma mevcut. Kurulu
chromium_headless_shell-1248 normal Playwright başlatması bir kez denendi:
`content/browser/sandbox_host_linux.cc:41 ... shutdown: Operation not permitted`
ve SIGTRAP; sayfa açılmadı. Bu gözlem belirli bir seccomp kuralına kesin atıf
sağlamaz; ortam kısıtı uygulama arızası sayılmadı. Sistem politikası, uygulama
kodu, browser bayrakları veya kişisel profil değiştirilmedi; indirme/canlı
hedef/tekrarlı browser denemesi yok. Yeni Chromium kaydırma/tıklama veya mobil
layout PASS/screenshot kanıtı iddia edilmez.

LOCAL/RADIUS tek yetkili kaynak modeli ve mevcut yazma/revision/onay/audit
akışları korunur. V1 verileri sentetik kaynağa katılmadı. V1/V2.5/VDS/router/
RADIUS/IPsec/DB/migration/silme/deploy/restart işlemi yok; tarihsel Dashboard
rollback ve güncel PG/HTTP bütünleşme kabul engelleri bu görevle kapanmaz.

- Bu görevde normal `git push origin main-guncel` denendi: BLOCKED,
  `Could not resolve host: github.com`. Uzak okuma başarılı olsa da push
  DNS aşamasında durdu. Yerel tek commit korunur; ağ erişiminde normal
  push gerekir. Force push yapılmadı.
