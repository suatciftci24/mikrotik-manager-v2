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
