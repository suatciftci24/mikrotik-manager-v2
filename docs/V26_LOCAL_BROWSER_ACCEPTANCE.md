# V2.6 — izole yerel Chromium kabulü

2026-11-03 · main-guncel · başlangıç e50dd02 · **LOCAL PASS**.

`frontend` dizininde `node tests/v26LocalAcceptance.browser.mjs` çalıştırıldı.
Mevcut Playwright ve browserRuntime seçicisi kullanıldı; yeni bağımlılık yok.
Gerçek App geçici bundle ile yalnız dinamik 127.0.0.1 portunda sunulur.
API istekleri sentetik yanıtlarla karşılanır; farklı origin, GET dışı yöntem
ve beklenmeyen API isteği testi başarısız yapar. Service worker kapalıdır.
Backend, DB veya gerçek kimlik bilgisi kullanılmaz. Süreç sonunda Chromium,
HTTP sunucusu ve geçici bundle temizlenir; başarısızlık receipt'e yazılır.

- Sekiz sentetik satır: Normal 1, Dikkat 2, Kritik 2, Eski veri 1, Veri yok 2.
  CPU/RAM eşikleri, sıfır CPU, eski yüksek metrik ve eksik kaynak doğrulandı.
- Öncelik sırası Kritik → Dikkat → Eski veri → Veri yok; aynı öncelikte
  ad sırası, ilk beş uyarı ve toplam yedi uyarı bağlantısı doğrulandı.
- Saat taklidi/hızlandırma, manuel yenileme veya reload olmadan doğal
  60 saniyelik interval: **59999 ms**, toplam iki okuma, max_active=1.
  İkinci yanıtta tüm durum/sayaç/sıralama yeniden doğrulandı; ölçüm zamanları
  değişmedi. Beklenmeyen istek/HTTP hatası/pageerror/requestfailed yok.
- Hedefli `routerHealth.test.mjs`, `dashboardV1Health.test.mjs`,
  `v1Inventory.test.mjs`: 3 dosya PASS, fail/skip yok.
- `npm run build`: PASS; mevcut >500 kB bundle uyarısı sürüyor.
- `git diff --check`: PASS; mevcut `v26-browser-acceptance.mjs` değişmedi.

İlk sandbox denemesi loopback listen EPERM ile durdu; aynı yerel test
izinli çalıştırılarak tek tam geçişte PASS oldu. Ürün hatası bulunmadı.
Kanıt: `.local/browser-acceptance/v26-local/result.json` ve `dashboard.png`
(Git dışı). Receipt `synthetic_only=true`, `real_nine_router_acceptance=false`.

V1/V2.5 Fresh Pilot/VDS/router/RADIUS/canlı DB erişimi yapılmadı.
Gerçek 9-router kabulü tamamlanmadı; tarihsel BLOCKED/ROLLBACK değişmedi.
Push hedefi mevcut upstream `origin/main-guncel`; URL proje GitHub deposu,
`git ls-remote` sonucu başlangıç e50dd02 ile eşleşti. Force push yok.
