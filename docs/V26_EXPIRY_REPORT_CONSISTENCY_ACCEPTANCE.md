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
