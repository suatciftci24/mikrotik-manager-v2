# Abone ekranları ve Dashboard sadeleştirme — 2026-11-15

Temel temiz main-guncel/3d57942, GitHub SHA eşitliği doğrulandı. AGENTS/Altın
Kurallar, güncel ilerleme ve son responsive kabul esas alındı. Önceki görsel,
PG/AAA veya canlı kabul engelleri bu görevle kapatılmış sayılmaz.

- Abone listesinde arama/ekle/yenile tek başlık araç alanında; gereksiz ikinci
  başlık ve sentetik açıklama tekrarları azaltıldı. Yenile mobilde filtre açmaya
  gerek kalmadan erişilir. Filtreler, router kapsamı, seçim/toplu işlem ve ortak
  satır/mobil işlem menüsü korunur. Mevcut mobil kartlar ve 5'li sayfalama aynı.
- Abone özetinde ad/durum, kullanıcı, paket/hız, router, bitiş ve kalan gün önde.
  Paket sürümü/fiyat/profil, başlangıç ve veri deposu/revizyon Teknik bilgiler
  altında. Kaynak belirsizliği/eksik tür uyarıları ve güncel/tarihsel kaynak ayrımı
  korunur. Hız kayıtlı snapshot'tan gelir, yoksa Veri yok.
- İşlemler sekmesindeki AAA fixture açıklamaları Teknik önizlemeler altında;
  mevcut paket/uzatma/durum ve onay/receipt akışları değişmez. Bağlantı sekmesinde
  router ve bilinmeyen oturum önde, teknik IP/zaman/ID'ler kapalı alandadır.
  Geçmiş, audit kimlikleri ve routera dönüş linkleri korunur.
- Kalıcı workspace Dashboard'ında dört ana kart: Routerlar, Toplam aboneler,
  Yaklaşan bitişler (7 gün) ve bugünkü PPPoE işlemleri. Tekrarlanan günlük/kısayol
  kartları azaltıldı. Alarm/WAN, router durumları ve diğer bitiş aralıkları Durum
  ve bitiş ayrıntıları altında erişilir. 24 saat rapor ve diğer merkezlere erişim
  korunur. Audit yükleyicisi/SQL/sayım, bugün/24 saat/dönem hesapları değiştirilmedi.
- Mobil üst bar kontrolleri native Ara ve görünüm bölümünde isteğe bağlı açılır;
  masaüstü aynı tema/arama/bildirim kontrollerini açık tutar. Görünür SENTETİK
  işareti korunur. V26 araç alanı/özet/kart CSS'i 320–430px için saran düzen,
  iki sütun, min-width:0 ve mevcut 44px kontrol alanlarını korur.

PASS: dashboardExpiryRefresh, dashboardOverview, workspaceDashboard,
managementReport, subscriberCenter, subscriberQuickWorkflow, operationsNavigation,
compactSubscribers, compactHeader hedef kapsamları; paket, subscriberDailyManagement,
subscriberRenewal ve subscriberSaveRecovery regresyonları. Yeni kontroller dört
tekil kart/değişmeyen audit değeri/yetkili link, öncelikli özet ve mobil menü
kontrol davranışını doğrular. Backend veya mevcut PostgreSQL kullanılmadı.

İlk Dashboard harness'i CSS loader eksikliğiyle açılmadı; düzeltildi. Eski ve yeni
Dashboard testleri onNavigate callback'inin hash'i değiştirdiğini varsayıyordu;
callback parametreleri doğrudan doğrulanacak şekilde düzeltildi. Kaynak ayrımı
testinin bulduğu güncel kaynak/tür etiketi korunarak düzeltildi. Yalnız başarısız
kapsamlar tekrarlandı. Son TypeScript/Vite production build ve diff kontrolü PASS.

BLOCKED: yerel Chromium crashpad setsockopt Operation not permitted/SIGTRAP ile
başlamadı. Hazır 320/360/390/430/1280px browser senaryosu çalışmadı; gerçek layout,
taşma veya görsel masaüstü/mobil kabulü PASS değildir. Sandbox gevşetilmedi,
indirme veya canlı tarayıcı bağlantısı yok. SSR/handler testleri görsel kanıt değildir.

Frontend dışında değişiklik yok: rol/router yetkileri, kaynak/DB seçimi, katalog,
PPPoE mutasyonları, audit ve idempotency iş mantığı aynı. PostgreSQL veri/kullanıcı/
şema yazımı, migration, VDS deploy/restart, V1/V2.5/cihaz/RADIUS/IPsec işlemi yok.
Ayrı onaylı frontend yayını yeterli; yeni backend veya migration gerekmez.
Commit/normal push sonucu teslimde bildirilir.
