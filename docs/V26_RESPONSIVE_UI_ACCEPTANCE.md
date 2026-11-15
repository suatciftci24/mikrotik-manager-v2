# V2.6 kapsamlı arayüz sadeleştirme — 2026-11-15

Başlangıç temiz main-guncel/704ce45 ve GitHub SHA eşitliği doğrulandı. AGENTS ve
tüm Altın Kurallar, güncel PROGRESS, son günlük gezinme kabulü ve özellik koruma
envanteri okundu. Önceki canlı/PG/AAA engelleri kapatılmış sayılmaz. İstek masaüstü
ve mobil ekran görüntülerine atıf yapıyor, ancak bu oturumda görüntüler mevcut
değildi; maddeler ve kaynak kod esas alındı, görüntü karşılaştırması yapılmadı.

## Tamamlanan kapsam

1. Router Merkezi: tekrar eden başlık açıklaması kaldırıldı; kaynak açıklaması
   kapalı Teknik bilgiler altında. Kalıcı liste başlığı kısaltıldı. V26 stilinde
   başlık/kaynak/arama aralıkları azaltıldı. Mobil router listesinde etiketli
   arama tam satır, ekle/yenile kontrolleri iki sütun düzenine alındı.
2. Router Detay: CPU/RAM sıfır uydurulmadan Veri yok kalır; eksik son bağlantı
   Veri yok, tekrar güncellik satırı kaldırıldı. Metadata/ID/RouterOS/uptime ve
   ölçüm açıklamaları kapalı Teknik bilgiler altında. Sentetik WAN IP/erişim/
   trafik Veri yok alanlarıyla gösterilir; yönetim IP'si WAN yerine geçmez.
   Sentetik PPPoE sekmesindeki işlevsiz gerçek gözlem açıklaması kaldırıldı;
   kayıtlı gerçek cihazın ayrı gözlem akışı değiştirilmedi. Bağlı abonelere üst
   özetten geçiş korunur. Router olaylarında ham aktör/revizyon kapalı detayda.
3. Router Aboneler: masaüstü tablo korunur; 650px ve altında tablo yerine aynı
   doğrulanmış yanıtın kartları vardır. Ad, kullanıcı adı, paket, hesap durumu,
   bitiş, kalan gün, Detay ve aynı PERSISTENT/LEGACY exact ID/return bağları.
   Arama/durum/sayfalama, hata/loading ve yanlış router/kaynak reddi aynı kalır.
4. Abone Merkezi/Detay: mevcut tek ortak işlem menüsü ve karşılıklı router
   bağlantıları korunur. Teknik kayıt/depo/revizyon alanları Abonelik'te kapalı
   bölüme taşındı. İşlem açıklaması kısaldı. V26 mobil sekmeler, etiketli filtre,
   kart, düğme, form/dialog ve önizleme genişliği düzenlendi; onay ve receipt
   kurtarma dahil işlem handler'ları değiştirilmedi.
5. Dashboard/Geçmiş: V26 boşlukları/kart aralıkları azaltıldı, dönem açıklaması
   açılır bölümde. Merkezi geçmiş ve işlem detayında tam UUID/aktör/revizyon/
   router kimliği kapalı Teknik detaylar içinde; sonuç/hata ve eski/yeni kanıt
   korunur. İşlem detayı aktöründe mevcut güvenli kısa gösterim kullanılır.
6. Genel V26 mobil stil: 320–430px için saran üst bar/tema/buton alanları,
   44px dokunma hedefleri, taşabilen sözcükler, min-width:0, duyarlı formlar,
   dört sütun detay sekmeleri ve odak halkası. Mobil ana menü düğmesine erişilebilir
   ad eklendi. Native details, sekme klavye handler'ları ve menü davranışı korunur.
   Arayüzde kaynak ve sentetik işareti görünür kalır; gizlenen teknik bilgi silinmez.

## Doğrulama

PASS: routerCenter, routerSubscriberLinks, subscriberCenter,
subscriberQuickWorkflow, compactSubscribers, dashboardOverview, workspaceContext,
operationsNavigation hedef dosyaları. Yeni kart testinde useRef/useCallback
stub'ı eksik olan harness düzeltildi; yalnız başarısız yeni senaryo tekrar geçti.
Yeni testler mobil kart içerikleri/masaüstü tablo, exact workspace linkleri,
kapalı teknik metadata, eksik CPU/RAM/WAN ve kapalı işlem UUID'sini doğrular.
Merkezi geçmiş/işlem detayı değişikliğinden sonra ilgili history/audit kapsamları
ayrıca doğrulandı. Başarılı ilgisiz testler tekrar çalıştırılmadı.

PASS: subscriberDailyManagement, subscriberRenewal, subscriberSaveRecovery ve
packages hedef testleri; yetki/kaynak reddi, paket akışı, eski/yeni onay, UUID ve
kayıp yanıt/idempotency korunması. Son TypeScript/Vite production build ve
 git diff --check PASS. Backend/mutasyon/model/API yetki değişikliği yoktur;
üretim veya mevcut PostgreSQL testi yapılmadı.

BLOCKED: yerel mevcut Chromium, crashpad setsockopt Operation not permitted
(SIGTRAP) ile başlamadı. 320/360/390/430/1280px görsel/gerçek layout/taşma kabulü
çalışmadı; PASS sayılmaz. Mevcut ağsız browser senaryosu yeni V26 CSS ve genişliklerle
hazırdır. Sandbox gevşetilmedi, indirme veya canlı tarayıcı bağlantısı yok.
Ekran görüntülerindeki bütün kusurların görsel olarak kapandığı iddia edilmez.

## Sınırlar ve yayın

Yalnız frontend sunumu ve test/dokümantasyon değişti. Rol/router yetkileri, kaynak
seçimi, kalıcı depo, paket/PPPoE mutasyonları, audit ve idempotency iş mantığı
korundu. PostgreSQL verisi/kullanıcı/şema, migration/seed, VDS deploy/restart veya
V1/V2.5/gerçek router/RADIUS/IPsec işlemi yapılmadı. Ayrı onaylı frontend yayını
gerekir; yeni backend veya migration gerekmez. Commit/push teslimde bildirilir.
