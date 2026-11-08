# V2.6 bitiş uyarıları ve günlük rapor tutarlılığı — 2026-11-08

Başlangıç main-guncel/df45e7a, temiz çalışma ağacı; uzak dal aynı SHA ile
ls-remote üzerinden doğrulandı. Altın Kurallar, güncel ilerleme, son recovery
kabulü ve özellik koruma envanteri okundu. **Yerel hedefli kabul PASS.**

Mevcut Türkiye takvim günü, bugün dahil3/7/30 gün aralıkları, tekil uyarı
birleşimi ve bilinmeyen tarih ayrımı doğruydu; yeniden yazılmadı. Aynı UUID
kanıtı/GET-only recovery, yetki ve mevcut yazma akışları korundu.

## Tamamlanan eksikler

- Dashboard useResource'un temizlediği eski özeti lastData ref'iyle yeniden
  gösterebiliyordu. Fallback kaldırıldı; loading sırasında önceki bitiş/günlük
  sayıları gösterilmez. Güncel, hata ve loading ayrımı açık Türkçedir.
  Mevcut7 ve3 gün geçişlerine bugün/30 gün/bilinmeyen kısa kapsam bağlantıları
  eklendi; yeni menü/bileşen yok. Bugün/3 gün ortak buildSubscriptionAlerts
  sonucundan türetilir; aralıklar iç içedir ve toplanmayacağı açıklanır.
- Günlük rapordaki mevcut expirySummary görünür oldu: bugün/3/7/30 gün,
  tarihi bilinmeyen ve tekil uyarı sayısı. Bitiş tablosu LOCAL/RADIUS kaynağını
  gösterir. Raporun yeni yetkili kaynak filtresi abone işlemlerine/bitişlere
  uygulanır; router/WAN olaylarının LOCAL/RADIUS'a ait olmadığı açık yazılır.
  Filtre URL'de reloadable kalır; V1 kaynağı sentetik veriden ayrı kalır.
- İlgili abone listesi bağlantısı artık router ID+kaynak+bitiş filtresini
  taşır. Mevcut listede opsiyonel router_id kapsamı, ad filtresinden bağımsız
  kesin ID eşitliğiyle uygulanır. Aynı adlı routerlar birbirine karışmaz.
  Uyarı kartları da aynı scope'u kullanır; router seçimi/filtre temizleme
  ID kapsamını kaldırır. Detay/back URL bağlamı mevcut helper'larda korunur.
- Gerçek okuma yükleyicisinde abone detay ID'si istenen ID ile eşleşmelidir;
  detay sentetik, revizyonu geçerli olmalı ve listede bilinen revizyondan
  geride olmamalıdır. Yanlış/eski/eksik yanıtla toplam yayımlanmaz; retry
  mesajı gösterilir. Legacy listeden eski bitiş alanı kullanılmaz; detail
  yanıtı esas alınır. Global snapshot/replica freshness garantisi iddia edilmez.
- Kalıcı raporda yalnız recorded=true/success=true işlemler sayılır. Receipt
  revizyonu güncel hesabı aşamaz; aynı revizyonda değişen alanlar hesapla
  eşleşmelidir. Uyuşmazlıkta sahte başarılı toplam veya kısmi gizli başarı
  yerine hata gösterilir. Daha eski meşru audit revizyonu güncel kaydı ezmez.
- Mobilde yeni kapsam bağlantıları44px hedeflerle sarar; uzun bitiş kapsamı
  metni taşmaz. Mevcut responsive tablolar korundu; görsel browser kabulü yok.

Bitiş özetleri mevcut legacy demo kapsamıdır; kalıcı çalışma alanı işlemleri
ayrı metadata ile raporlanır. Kalıcı abonelerin satır bitiş uyarıları kendi
Abone Merkezi'ndedir. Kaynaklar veya gerçek V1 snapshot'ı birleştirilmedi.
Paket/durum değişimi bitişi değiştirmiş gibi yorumlanmaz; bilinmeyen tarih
ne süresi dolmuş ne geçerli sayılır. Başarı mesajı/belirsiz sonuç state'i
özet sayısından türetilmez; UUID audit kanıtı yolu değişmedi.

## Hedefli doğrulama

53 frontend test PASS: expiry6, subscriptionAlerts7, subscriberFilters4,
dailySummary6, dashboardOverview5, managementReport17, managementReportView6,
resourceReconciliation1, dashboardExpiryRefresh1.

- Bugün/3/7/30 ve null/geçersiz tarihler, tekil union, duplicate/non-demo ret,
  Türkiye gece yarısı ve LOCAL/RADIUS kapsamı korunur.
- Kaynak × bitiş filtresi matrisi rapor satırlarını ID kapsamlı listeyle
  eşleştirir; aynı adlı router için r1/r2 karışmaz. Filtre reload'u doğrulanır.
- API mock'unda yalnız GET ile yenileme/paket/durum/oluşturma sonrası güncel
  revizyon okunur; Dashboard/rapor/liste sayıları eşleşir. Onaylanmamış yerel
  yeni değer özete girmez; RADIUS bilinmeyen tarih ayrı kalır.
- Loading esnasında eski Dashboard sayısı görünmez; error sahte boş/sıfır
  üretmez. Stale/mismatched ID/revizyon okuması ve ileri receipt revizyonu
  reddedilir. Mevcut kaynak/hata/boş ve V1 ayrım SSR kontrolleri PASS.

Network fixture'larındaki eksik revision alanları gerçek sözleşmeye uygun
0/1/5 ile tamamlandı; assertion veya ürün guard'ı gevşetilmedi. Başarılı
kapsam yalnız yeni fixture/test veya ilgili ürün değişikliğinde tekrarlandı.
Tek tsc/Vite build PASS; ana bundle620.53kB, mevcut >500kB uyarısı sürer.
Diff kontrolü PASS. Backend değiştirilmedi; gereksiz backend/PG suite'i yok.

Chromium önceki EPERM nedeniyle BLOCKED; yeni browser/socket/güvenlik
denemesi yok. Gerçek mobil/HTTP/PG genel kabulü iddia edilmez. Eski/eksik
revizyon döndüren backend yanıtı güvenli hata olur; tarihsel Dashboard ve
güncel PG/HTTP genel kabul engelleri kapanmış sayılmaz.
V1/V2.5/canlıVDS/router/RADIUS/IPsec/canlıDB/deploy/restart/migration/silme
ve gerçek veri işlemi yapılmadı. Yalnız yerel kod ve sentetik/mock testler.

- Normal `git push origin main-guncel` denendi; push BLOCKED:
  `Could not resolve host: github.com`. Yerel tek commit korunur.
  Uzak okuma başarılıydı; ağ erişiminde normal push gerekir. Force push yok.

## Merkezi operasyon bütünlüğü — 2026-11-08 / 5df920f sonrası

Başlangıç main-guncel/5df920f, temiz; yerel remote tracking ile aynı SHA,
bekleyen commit yok. İlk normal push DNS nedeniyle BLOCKED. Önceki bitiş,
UUID GET-only uzlaştırma ve revizyon korumaları yeniden yazılmadı.

### Gerçekten tamamlanan düzeltmeler

- Mevcut management history API'sinin saklanan receipt'i doğrudan döndürme
  açığı kapandı. UUID, abone, actor, audit kolonundaki revizyon/tür/zaman,
  previous/new public değişiklikleri, recorded/success ve router değişimi
  eşleşmeden geçmiş yayımlanmaz (409). Salt okunur doğrulama; yeni endpoint,
  tablo veya migration yok. Tekil UUID recovery kanıtı değiştirilmedi.
- Günlük rapor kayıtlı başarısız kalıcı PPPoE audit'lerini atlamaz; başarıdan
  ayrı gösterir. Başarılı PPPoE kartı yalnız APPLIED sayar. Başarısız satır
  denenmiş değerleri uygulanmış gibi sunmaz. Aynı UUID replay'i tekildir;
  çelişen kopya, geçersiz kimlik/revizyon/sonuç hata verir. Unrecorded receipt
  toplam üretmez. Belirsiz isteklerin global audit sayım kaynağı yoktur:
  'Sayım kaynağı yok' açıkça gösterilir, başarı veya sıfır türetilmez.
- Başarılı/başarısız sayıları yalnız erişilen kayıtlı audit kapsamıdır.
  Legacy geçmiş yalnız başarılı işlemleri sağlar; geçmişte kaydedilmemiş
  başarısız/belirsiz denemelerin küresel toplamı çıkarılamaz. Bu sınır kapalı
  sayılmaz. Workspace alınamazsa kesin toplam yerine Veri yok korunur.
- Mevcut MikAjanı olay açma/kapama URL'ye taşındı. Bilinen router + can_view
  ile router/alarm bağlantıları; bounded return_to üzerinden olay/priority
  bağlamına dönüş. Alarm→MikAjanı geçişi de kaynak merkeze dönebilir.
  Yetkisiz/bilinmeyen hedefe link yok. Ayrı senaryo bulgularından kayıtlı
  routerlara link yok; olmayan abone ilişkisi üretilmedi.
- Raporun abone/router lookup'ları Map ile indekslendi: her receipt için
  accounts/routers.find taraması kaldırıldı. Yeni bağımlılık/bileşen/menü yok.
  Sayısal süre/bundle küçülmesi iddiası yok; ana bundle 622.39kB, gzip179.34.

### Bu görevde doğrulama

PASS: 68 frontend test (9 dosyada benzersiz kapsam): managementReport18,
managementReportView7, mikaContextNavigation3, alarmCenter6,
operationsNavigation10, mikajani3, pendingSubscriberOperations12,
subscriptionActions8, resourceReconciliation1. Bunlar mock/hook/SSR kabulüdür.
Yeni başarısız satır eklenince eski testte ilk workspace satırının başarı
olduğu varsayımı kalktı; açık APPLIED satırı seçildi. Güvenlik assertion'ları
gevşetilmedi. Test komutundaki cwd hatası düzeltilerek gerekli kapsam çalıştı.

PASS: 5 backend test: HistoryAuditIntegrity (11 kanonik alan bozulması +
başarısız receipt), DailyManagement partial failure/replay ve router move,
UUIDAuditEvidence bulk audit/source uyuşmazlığı ve >50 kayıt sonrası tekil
salt okunur UUID kanıtı. Yalnız private sentetik SQLite/mock; canlı DB yok.
PASS: tek `npm run build` (tsc + Vite), diff kontrolü. >500kB uyarısı açık.

BLOCKED: Chromium EPERM; socket/tarayıcı tekrar denenmedi, güvenlik ayarı
gevşetilmedi. Gerçek mobil/touch/odak, HTTP/PG ve tüm modüllerin üretim kabulü
iddia edilmez. Bu görev geniş envanterdeki mevcut tamamlanmış işlevleri
koruyarak kanıtlanan audit/rapor/navigasyon eksiklerini kapatır; bütün ürünün
üretime hazır olduğu anlamına gelmez. Tarihsel genel kabul engelleri açık.
V1/V2.5/canlı VDS/gerçek cihaz/RADIUS/IPsec/canlı DB'ye erişim veya değişiklik,
deploy/restart/migration/veri silme yok. Geliştirmeler canlıya aktarılmadı.

- Görev sonu normal push da BLOCKED: `Could not resolve host: github.com`.
  Tek yeni yerel commit korundu; main-guncel tracking dalından bir commit
  ileride. Ağ düzeldiğinde normal push gerekir; force push yapılmadı.

## Kalan teknik işler — çalışma devam ediyor

Global belirsiz işlem sayısı mevcut kalıcı şemadan üretilemez: audit yalnız
atomik olarak kaydedilmiş denemeleri tutar; gönderimden önce/sonra bağlantısı
kopmuş ancak audit'i yazılmamış istekler listelenmez. Actor bazlı UUID GET bu
tek isteği kanıtlar, global envanter sunmaz. Bu nedenle belirsiz toplam
bilinmiyor/null olmalı. Kalıcı ve tam sayım için en küçük sözleşme,
POST'tan önce UUID+actor+account+router+source+expected revision içeren
idempotent intent/attempt kaydı, terminal APPLIED/FAILED atomik audit bağı ve
TTL sonrası unresolved durumudur. Bu şema/depo değişikliği migration ve
atomiklik tasarımı gerektirir; mevcut görevde eklenmedi. Başarı yanlış
üretilmemelidir.

Bundle değişikliği ve test/build sonuçları aşağıdaki görev kaydında izlenir.

## Lazy loading doğrulaması — 2026-11-08

`frontend/src/App.tsx` içindeki mevcut React.lazy/Suspense yapısı TypeScript ve
React derlemesinden geçti. İlk build `src/App.tsx(4,9): error TS2440: Import
declaration conflicts with local declaration of 'SystemCenter'.` hatası verdi;
lazy SystemCenter tanımını gölgeleyen eski statik import kaldırıldı. İkinci
`npm run build` PASS: tsc ve Vite; giriş chunkı 286.90 kB (gzip 89.02 kB),
önceki 622.39 kB (gzip 179.34 kB). Dashboard 73.15 kB, Subscribers 65.15 kB,
Routers 25.99 kB, Mikajani 8.70 kB, AlarmCenter 12.64 kB ayrı chunk oldu.
Rapor Operations içinden bölünüyor; ana girişte 500 kB uyarısı kalmadı.

BLOCKED: Lazy import chunk'ı ağ/yükleme hatasıyla reddedilirse uygulama
seviyesinde görünür kurtarma/yeniden deneme arayüzü yok. Suspense yalnız beklerken
yükleme durumu sağlar; hata boundary değildir. Kullanıcı talimatı gereği bu
kurtarma eklenmedi, başarılı code-splitting kabulü iddia edilmez. Chromium
EPERM bilinen engeli nedeniyle denenmedi. Test/browser kabulü çalıştırılmadı.
Bu oturumda commit veya push yapılmadı.
