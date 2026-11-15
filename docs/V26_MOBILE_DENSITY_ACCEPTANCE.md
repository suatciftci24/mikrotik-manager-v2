# V2.6 mobil yerleşim yoğunluğu — 2026-11-15

Başlangıç temiz main-guncel/0db276e; GitHub aynı SHA. AGENTS/tüm Altın Kurallar,
güncel PROGRESS ve son Abone/Dashboard kabulü okundu. Önceki görsel/PG/AAA/canlı
kabul engelleri kapatılmış sayılmaz.

- Yalnız mobil V26 kabuk CSS'inde navigasyon başlığı ve kapalı üst araç bölümü
  aynı satırdadır. Açıldığında araçlar ayrı tam satıra geçer. Mevcut native toggle,
  tema/arama/bildirim ve navigasyon handler'ları aynı kalır. Görsel arama etiketi
  gizliyken de erişilebilir Hızlı arama adı vardır; 44px kontroller korunur.
- Ortam kutusunda mobil kısa V2.6 etiketi, görünür SENTETİK işareti ve açılabilir
  ortam açıklaması vardır. Masaüstü uzun etiket değişmez; tam ortam adı mobilde
  de erişilebilir ad olarak korunur.
- Dashboard ana kartlarının iki sütunu korunur; mobil boşluklar azaltıldı.
  Sayımlar, kaynaklar ve tarih filtresi kodu değişmedi.
- Abone filtreleri mobilde tür/durum için iki sütun, router için tam satır;
  arama/ekle/yenile hizası ve kontrol aralıkları sıkılaştırıldı. Mevcut filtre
  state'i, URL ve istek parametreleri değişmedi.
- Mobil abone kartında seçim, ad/durum, paket/tarih ve router/İşlemler bölümleri
  tutarlı grid ile hizalanır. Uzun metinler sarılır, kesilmez. Hesap durumu ve
  bitiş alanları etiketlidir. Tekrarlanan üst kayıt/sayfa satırı yalnız mobilde
  gizlenir; mevcut tek kart sayfalaması ve live status kalır. Masaüstü tablo,
  sayfalama ve kaynak/işlem yetkileri değişmez.

PASS: compactHeader, compactSubscribers, subscriberQuickWorkflow,
operationsNavigation ve dashboardExpiryRefresh hedef frontend dosyaları.
Yeni kontroller kısa/tam ortam adı ve sentetik işareti, erişilebilir arama,
card alanları ve tek pager'ı doğrular; mevcut filtre/işlem callback/readonly,
router link ve gün/24 saat Dashboard kontrolleri korunur. Tek production
TypeScript/Vite build ve git diff --check PASS. Backend/DB testi gerekmedi.

BLOCKED: mevcut yerel Chromium crashpad setsockopt Operation not permitted /
SIGTRAP ile başlamadı. Ağsız senaryo 320/360/390/430/1280px, gerçek mobil üst bar
kontrolleri, görünür tek sayfalama ve kart/menü/taşma kontrolleriyle güncellendi;
gerçek görsel/layout PASS sayılmaz. Sandbox gevşetilmedi, yeni browser indirilmedi.

Yalnız frontend sunumu/testler ve bu kabul kaydı değişti. API/yetki/iş mantığı,
PostgreSQL/veri/kullanıcı/şema/migration, VDS deploy/restart, V1/V2.5/gerçek router/
RADIUS/IPsec işlemi yok. Etkinleşmesi için ayrı onaylı frontend yayını gerekir;
yeni backend veya migration gerekmez. Commit/push/HEAD sonucu teslimde bildirilir.
