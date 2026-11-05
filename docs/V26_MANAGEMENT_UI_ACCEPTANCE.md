# V2 yönetim arayüzü sadeleştirme — 2026-11-05

LOCAL PASS. Başlangıç `main-guncel/3cb542b`. AGENTS.md, güncel ilerleme,
PPPoE kabulü, Router V2.1 kabul kaydı, onboarding ve entegrasyon mimarisi incelendi.
Mevcut operatör yedekleri ve izlenmeyen SubscriberAuditChanges.tsx korunur.

## Kaynak haritası ve sadeleştirme

| Merkez / görünüm | Mevcut veri kaynağı | Korunan sınır / yeni yerleşim |
| --- | --- | --- |
| Router / Demo envanter | `/routers`, eski sentetik envanter ve raporlar | Mevcut liste, arama, filtre, detay ve rapor korunur. |
| Router / Sentetik yönetim | `/router-workspace/routers` | Ayrı kalıcı sentetik depo; mevcut ekle/düzenle/sil ve audit. Tek ekleme düğmesi. |
| Router / Kayıtlı cihazlar ve pilot | `/router-registry`, mevcut onboarding/pilot formları | Gerçek cihaz metadata'sı ve bağlantısız kayıt korunur. Pilot ayrı bir veri kaynağı sekmesi olmaktan çıkar; bu kaynakta açılabilir işlem grubudur. Bağlantı onayları ve sunucu politikaları değişmedi. |
| Router / V1 aktarılmış envanter | `/v1-inventory`, V2'de kayıtlı aktarım/sağlık snapshot'ı | Salt okunur. V1'e yazma veya yeni ölçüm yok. Mevcut tablo/modal, zaman/freshness ve tek istekli 60 sn okuma korunur. Ekleme/pilot düğmesi gösterilmez. |
| Abone / Mevcut demo | `/subscribers` | Mevcut demo kayıtları, paket/uzatma/durum, tüm filtreler, toplu işlemler, detay ve audit korunur. LOCAL/RADIUS çalışma ortamı değil, hesabın yetkili kaynağıdır. |
| Abone / Kalıcı sentetik | `/subscriber-workspace` | Ayrı PPPoE/Hotspot deposu; merkezi yönetici, kayıt/uzatma/günlük işlemler ve router bağları korunur. |
| Abone / İşlem geçmişi | `/subscribers/demo-history` veya `/subscriber-workspace/management/history` | Kendi kaynak filtresiyle audit; depolar ve sorgular birleştirilmez. |
| RADIUS | Mevcut hazırlık ekranı | Canlı liste veya yönetim API akışı yok. Planlanan kapsam açılır bölümde; doğrulanmamış PostgreSQL durum iddiası kaldırıldı. |
| Operasyon | `/alarms`, `/router-events`, `/routers` | Merkezi alarmlar ana içerik. Mevcut WAN olayları/router kapsamı/kanıt ayrıntıları açılır bölümlerde. ACK/okundu ve ayrı yetkileri değişmedi. |
| MikAjanı | `/mikajani/analysis`, `/mikajani/scenarios` | Salt okunur analiz, filtreler, kanıt/geçmiş dialog'u korunur. Router sağlık ayrıntısı ve analiz sınırları açılır bölümlerde; ayrı senaryo kayıtları değiştirmez. |

Router ve Abone üst kaynak sekmeleri ortak native select düzenine geçirildi.
Kaynak, erişim kapsamı ve açıklaması görünür; URL anahtarları ve eski derin linkler
korundu. Yetkisiz ileri kaynak hash'i demo listeye sessiz fallback yapmaz; açık
ret verir. Abone ileri görünümünde ilgisiz eski demo listesi artık otomatik okunmaz.
Yetkisiz/bilinmeyen kaynaklı abone işlemleri gizlenir; sunucu kontrolleri aynıdır.

Üst bar, yan menü ve mobil banner aynı seçili veri bağlamını gösterir. Sunucu adresi
`location.host` ile açık gösterilir. Koşulsuz “Yerel ortam hazır”, “Harici bağlantılar
kapalı”, sabit dört-router sayacı ve işlevsiz çalışma alanı değiştirici görünümü
kaldırıldı. Sunucu bir deployment sınıfı sağlamadığından host'tan VDS/pilot/üretim
etiketi tahmin edilmez. Bu görev yeni deployment metadata API'si eklemedi.
RADIUS gezinmesinin hash'te kaybolup yenilemede Dashboard'a dönmesi düzeltildi.

## Doğrulama

- Yedi hedefli frontend test dosyası PASS: workspaceContext, uxAccessibility,
  routerInventory, subscriberCenter, subscriberFilters, alarmCenter, mikajani.
- Tam App ile yerel Chromium kabulü PASS: dört router kaynağı, tek sentetik
  ekleme düğmesi, kayıtlı cihazla sınırlı pilot grubu, V1 salt okunurluğu;
  üç abone görünümü ve kaynak filtreli işlem geçmişi; RADIUS ana menü/hash/reload;
  Operasyon açılır içerikleri ve eski filtreli olay linkinde otomatik açılma; MikAjanı sağlık, senaryo ve kanıt dialog'u.
- VIEWER sentetik oturumunda abone yazma düğmeleri gizli; doğrudan REGISTERED
  hash'i ret verir ve registry okuması başlatmaz.
- Beş ekranda 1440/375 px ve Beyaz/Gece temalarında sayfa yatay taşması yok;
  ortam/yetki etiketi mobilde de görünür. Native select ve details klavye
  davranışını korur. Kanıt dialog'u aç/kapat kontrol edildi.
- Tüm API yanıtları Playwright route interception ile sentetiktir. Test yalnız
  kendi loopback statik sunucusunu kullanır. GET dışı yöntem ve harici origin
  reddedilir; sıfır mutation/harici istek/beklenmeyen API/tarayıcı hatası.
- Kanıt: `.local/browser-acceptance/management-centers/summary.json` ve dört
  masaüstü/mobil tema ekran görüntüsü (Git dışı). Runner:
  `frontend/tests/managementCenters.browser.mjs`.
- İlk tarayıcı seçicisi mevcut V1 başlığını yanlışlıkla region olarak aradı;
  test düzeltildi. VIEWER fixture geçişi yeni auth oturumu için reload yapacak
  şekilde düzeltildi; ürün yetki kontrolü gevşetilmedi. Sandbox loopback EPERM
  sonrası aynı izole test izinli çalıştırıldı.
- Son TypeScript/Vite build ve `git diff --check` PASS. Mevcut >500 kB bundle
  uyarısı sürer. Backend/DB değişmediği için backend/DB testleri tekrarlanmadı.

## Birleştirilmeyen ve doğrulanmayan alanlar

Gerçek V1 aktarımı, kayıtlı gerçek cihaz/pilot, demo ve kalıcı sentetik kayıtlar
birleştirilmedi. Sistem altındaki sentetik Pilot Karar Merkezi ve CEBECI hazırlık
akışları taşınmadı; gerçek bağlantı onayıyla aynı şey değildir. API, audit,
yetkilendirme, veritabanı, migration ve veri değişmedi. Mevcut 14 demo aboneye
bağlanılmadı/yazılmadı. V1, V2.5 pilot, V2.6 VDS, gerçek MikroTik/RADIUS,
servis/restart/deploy işlemi yoktur. Gerçek login, canlı veri ve gerçek bağlantı
kabulü iddia edilmez. Önceki VDS kimlik PGDATA BLOCKED ve Dashboard ROLLBACK
kayıtları aynen geçerlidir.

Sıradaki somut adım: kullanıcı yerel arayüzü inceleyebilir; canlıya taşıma bu
pakette uygulanmaz ve ayrı açık onay gerektirir.
