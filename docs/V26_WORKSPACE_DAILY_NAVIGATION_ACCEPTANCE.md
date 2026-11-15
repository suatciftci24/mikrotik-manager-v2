# V2.6 router–abone günlük akışı — 2026-11-15

Temel temiz main-guncel/b4e78a4; GitHub SHA eşitliği doğrulandı. AGENTS/Altın
Kurallar, güncel PROGRESS, son aktör/geçmiş kabulü ve mevcut özellik koruma
kararları esas alındı. Önceki PG/AAA/canlı kabul engelleri kapatılmış sayılmaz.

- Kalıcı router detayının üst özetinde Bağlı aboneleri aç bağlantısı vardır.
  Exact router ID + PERSISTENT workspace + ALL erişim türü seçilir. Router alt
  liste arama/durum filtreleri ve varsa önceki workspace arama/durum bağlamı
  taşınır; yeni kapsam sayfa 1'den başlar. Tek seviyeli mevcut return_to koruması
  kullanılır. Abone listesinde Önceki görünüme dön bağlantısı vardır.
- Abone detay özetinde router adı doğrudan ilgili routerı açar. Liste router
  hücresi ve mobil kart da aynı doğrulanmış subscriberRouterHash bağını kullanır.
  Kaydı eksik/belirsiz router için link uydurulmaz. İsim eşleşmesiyle kayıt veya
  yetki tahmini yapılmaz. Abone filtreleri geri dönüş hash'inde korunur.
- Abone ekle gelişmiş filtrelerin dışındadır. Liste başlığı ve tekrarlı açıklama,
  satır başına ölçülmeyen oturum metni ve adı zaten detayı açan satırdaki ikinci
  Detay düğmesi sadeleştirildi. Toplu işlem kontrolleri seçim varken görünür.
- Mobil kartlar masaüstündeki aynı SubscriberQuickButtons menüsünü kullanır:
  uzatma, paket, durum ve geçmiş mevcut modal/callback/politikaya yönlenir.
  İkinci bir işlem akışı veya mutasyon API'si yoktur. Yetkisiz/readonly veya
  kaynak/router bağı eksik kayıtta yazma callback'i verilmez. Mobilde kart
  altındaki router ve menü için saran düzen ve 44px tıklama alanı vardır.
- V26 kaynak seçicisinde yalnız Aboneler/İşlem geçmişi vardır; eski LEGACY demo
  seçeneği gösterilmez. ADMIN dahil geçmiş workspaceOnly açılır. Eski runtime
  özellikleri korunur; veri kaynakları birleştirilmez, V1'e erişim eklenmez.

PASS: beş frontend hedef dosyasının ilgili senaryoları: routerCenter,
subscriberCenter (24 senaryo), compactSubscribers, subscriberQuickWorkflow,
operationsNavigation. Yeni kapsam çift yönlü exact ID/kaynak/return filtreleri,
ALL kapsamı, readonly mobil menü, oluşturma düğmesinin görünürlüğü, mevcut işlem
callback'leri ve V26 kaynak ayrımını doğrular. Eski Geçmiş testi router ID'nin
href'te bulunmasını görünür teknik metin sanıyordu; assertion görünür metne
uyarlandı ve yalnız başarısız senaryo tekrar geçti. Yeni kaynak testi ayrıca PASS.
Son TypeScript/Vite production build ve git diff --check PASS.

Görsel tarayıcı kabulü BLOCKED: mevcut yerel Chromium başlatılırken crashpad
setsockopt Operation not permitted/SIGTRAP verdi. Ağsız 320/390/1280px kabul
senaryosu tests/workspaceDailyNavigation.browser.mjs hazırdır; çalışmış veya
PASS sayılmaz. Öncesindeki esbuild sync/plugins araç hatası async build ile
giderildi. Sandbox gevşetilmedi, indirme veya canlı browser bağlantısı yok.

Değişiklikler frontend kapsamındadır. Backend yetkileri/audit/iş kuralları,
mevcut PostgreSQL verisi/kullanıcı/şema, migration, VDS deploy/restart, V1/V2.5,
gerçek router/RADIUS/IPsec değiştirilmedi. Gerçek PG/HTTP yazma testi yapılmadı.
Etkinleşmesi için ayrı onaylı frontend yayını gerekir; yeni migration veya
backend değişikliği gerekmez. Commit/push teslim raporunda bildirilir.
