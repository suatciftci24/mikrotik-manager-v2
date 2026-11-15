# V2.6 üç mobil açılır alan düzeltmesi — 2026-11-15

Temel temiz main-guncel/ef28786; uzak SHA aynı. AGENTS/Altın Kurallar, güncel
PROGRESS ve son mobil yoğunluk kabulü okundu. Yerel değişiklik yoktu; silme,
reset veya stash işlemi yapılmadı. Önceki görsel/PG/AAA engelleri kapanmadı.

Yalnız 600px ve altındaki V26 frontend sunumu:
- Ortam kutusu üç sütun kompakt grid. V2.6 ve SENTETİK görünür, Çalışma ortamı
  summary'si 44px hedefini korur. Açılan içerik tam genişliğe geçer; kapalı
  durumdaki açıklama açıkça gizlenir, veri ve açıklama silinmez.
- Abone görünümü seçicisinin varsayılan alt marjı ve biriken boşlukları giderildi.
  Select ve Teknik bilgiler kapalıyken yan yana; teknik bilgi açılınca tam satır.
  Kontroller minimum 44px, metinler sarılır. Seçim handler'ı/URL kaynak state'i
  değişmedi.
- Yalnız kalıcı abone listesinin Filtreler disclosure'ına workspace-filters sınıfı
  eklendi. Kapalı toolbar display:none, açık toolbar grid kuralları ayrıldı;
  koşulsuz grid kuralının kapalı görünümle çelişmesi önlendi. Başlıkta açık/kapalı
  artı/eksi göstergesi ve native details klavye/toggle davranışı korunur. Tür,
  durum, router ve temizleme erişimi aynı. Arama/ekle/yenile ayrı başlık alanında.

PASS: compactHeader, compactSubscribers, subscriberQuickWorkflow ve
operationsNavigation hedef kapsamları. Yeni filtre testi mobil native toggle
state'ini aç/kapat ve masaüstü açık durumuyla doğrular; SourcePicker testi seçim
callback'i ve ayrı kapalı Teknik bilgiler alanını korur. Testin React child key
klonunu referans eşitliği sanan assertion'ı type/props karşılaştırmasına düzeltildi;
yalnız başarısız yeni senaryo tekrar geçti. Tek production TypeScript/Vite build
ve git diff --check PASS.

BLOCKED: mevcut Chromium crashpad setsockopt Operation not permitted / SIGTRAP
ile başlamadı. Ağsız 320/360/390/430/1280px senaryosu üç alanın görünürlüğü,
kompakt yükseklik, aç/kapat/Enter/Space, seçim/temizleme ve taşma kontrolleriyle
hazır; gerçek layout/klavye/görsel kabul PASS değildir. Sandbox gevşetilmedi.

Dashboard, masaüstü CSS, işlem/yetki/API/iş mantığı değiştirilmedi. Backend,
PostgreSQL veri/kullanıcı/şema, migration, VDS deploy/restart, V1/V2.5/gerçek
router/RADIUS/IPsec işlemi yok. Ayrı onaylı frontend yayını yeterli; yeni backend
veya migration gerekmez. Commit/push/HEAD eşitliği teslimde bildirilir.
