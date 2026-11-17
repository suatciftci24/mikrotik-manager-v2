# V2.6.1 merkez arayüz düzeni — 2026-11-17

Yerel hedefli kontroller PASS. Başlangıç temiz 5b8649e/v2.6.0;
yerel geliştirme dalı development/v2.6.1-ui.

Dashboard, Router Merkezi ve Abone Merkezi mevcut yapıları incelendi.
Mevcut mobil kartlar, native filtre/işlem menüleri ve kaynak ayrımı korundu.
Ortak center-layout.css yalnız üç liste/özet merkezine uygulanır: boşluklar,
saran araç çubukları, okunabilir satır metni ve mobil abone adı/durum düzeni.
Mobil aksiyonlar en az 44px; Dashboard hızlı erişimi dar ekranda tek sütun.
Görünürlük, kaynak/yetki kararları veya işlem callback'leri değiştirilmedi.
Dashboard kapsam kutusundaki iki yinelenen UNKNOWN/WITHIN_30 bağlantısı
kaldırıldı; aynı filtrelerin durum/bitiş kontrolleri erişilebilir kalır.

Merkezi sürüm release.json, frontend paket ve lock sürümleri 2.6.1;
CHANGELOG güncel. Yeni bağımlılık veya backend değişikliği yok.

Hedefli doğrulama:

- dashboardOverview, workspaceDashboard: kaynaklar, hesaplar, audit sayımları.
- routerInventory: mevcut kayıtlı router durumu ve kaynak sözleşmeleri.
- compactSubscribers, subscriberQuickWorkflow: kompakt liste, işlem yetkileri,
  mevcut abone callback'leri ve kaynak sınırları.
- dashboardExpiryRefresh: gerçek Dashboard render/handler kontrolü; bugün,
  3/7/30/bilinmeyen tarih filtreleri, yenileme ve rapor bağlamı korunur.
- TypeScript + Vite production build PASS (1716 modül).
- tools/release.py check: 2.6.1; git diff --check PASS.

İlk test komutunda frontend çalışma dizini ve strip-only TypeScript modu
hatalıydı; yalnız başarısız dört dosya frontend dizininde
node --experimental-transform-types --test ile tekrarlandı ve PASS oldu.
RouterInventory başarılı kontrolü tekrar edilmedi. Son yazı boyutu düzeltmesi
sonrası build yenilendi. Testler veya güvenlik kontrolleri gevşetilmedi.

Gerçek browser/viewport görsel kabulü yapılmadı. Önceki kabulde belgelenmiş
Chromium sandbox engeli tekrar denenmedi; SSR testleri görsel kanıt değildir.
Mevcut mobil breakpoint/kart yapıları korunarak CSS iyileştirildi.

Backend/API, PPPoE/Hotspot/RADIUS/TLS iş mantığı ve kalıcı veriler değişmedi.
CEBECI_TOWERS entegrasyonu geri getirilmedi. GitHub push/tag, deploy/restart,
DB/migration veya canlı router/RADIUS/IPsec işlemi yapılmadı. Önceki canlı
BLOCKED kayıtları kapanmadı. Sonraki adım ayrı ortamda görsel kabul;
yayın ve GitHub işlemleri bu görevin dışında.
