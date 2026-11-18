# #50 V2.6.4 uçtan uca senaryo kabulü — BLOCKED

18 Kasım 2026. Ofis WSL2, `suatpc@DESKTOP-VD5T7VG`,
`~/v26-transfer/mikrotik-v26-next`, `development/v2.6.2-pppoe`.
İnceleme başlangıcı `817b73c` ve temiz çalışma ağacı. Kabul kapsamı izole
sentetik V2. Güncel Ofis uçtan uca çalıştırması ve önceki kanıtların kapsamı
tabloda ayrı sütunlarda gösterilir.

| Senaryo | Geçerli kanıt ve durumu | Güncel Ofis uçtan uca durumu |
| --- | --- | --- |
| Giriş, yenileme sonrası oturum, çıkış, korumalı adrese dönüş | **PASS** — önceki izole API kabulü ve yerel ADMIN HTTP login/me/logout kaydı kendi ortamında korunuyor. [API oturum kaydı](V26_HTTP_LOGIN_FINAL_CHECK.md), [HTTP kabul geçmişi](PROGRESS.md). | **BLOCKED** — #20 tarayıcı akışı ilk sayfaya ulaşamadı. [Chromium kanıtı](V262_BROWSER_21_ACCEPTANCE.md). |
| Router Merkezi liste, kaynak ve detay | **PASS** — önceki sentetik router kaynak ve Home WSL Chromium görünümü. Exact router bağı ve dönüş yolu için hedefli frontend kabulü mevcut. [Router kaynak kaydı](V26_ROUTER_SOURCE_ACCEPTANCE.md), [Günlük gezinme kabulü](V26_WORKSPACE_DAILY_NAVIGATION_ACCEPTANCE.md), [Ev WSL kapsamı](V26_ISOLATED_INTEGRATION_ACCEPTANCE.md). | **BLOCKED** — güncel Ofis liste/detay ekranı gerçek tarayıcıda açılmadı. [#21](V262_BROWSER_21_ACCEPTANCE.md). |
| PPPoE oluşturma, bilgi düzenleme, paket, aç/kapat ve uzatma | **PASS** — #39'daki 45 hedefli menü/işlem testi ve #50'deki beş sentetik form kontrolü. #39 paket ve durum işlemlerini ayrı menüye yönlendiriyor. [#39](PROGRESS.md), [PPPoE sözleşme kabulü](V262_PPPOE_ACCEPTANCE.md). | **BLOCKED** — güncel tarayıcı + HTTP/PG işlem zinciri çalıştırılamadı. [Ofis izole kabul kaydı](V26_OFFICE_ISOLATED_ACCEPTANCE.md). |
| Yetkilendirme ve kaynak sınırları | **PASS** — önceki ASGI/SQLite kapsamı rol ve router kapsamını sınadı. #39 UI kanıtı yetkisiz ve kaynak bağı belirsiz kayıtta yazma denetimini koruyor. [Router yetki kabulü](V26_OPERATOR_ROUTER_ACCESS_ACCEPTANCE.md), [PPPoE yetki/sayım](V262_PPPOE_ACCEPTANCE.md). | **BLOCKED** — gerçek güncel oturum ve rol altında uçtan uca yetki reddi çalıştırılmadı. [Ofis izole kabul kaydı](V26_OFFICE_ISOLATED_ACCEPTANCE.md). |
| Önizleme ve açık onay | **PASS** — #50 oluşturma ve bilgi düzenlemede onay öncesi sıfır istek ve onay sonrası tek POST doğruladı. Paket ve durum önizlemelerinin #39 kanıtı korundu. [Kapsam ve test kaydı](PROGRESS.md). | **BLOCKED** — gerçek tarayıcı ve kalıcı demo zinciri çalıştırılmadı. [#21](V262_BROWSER_21_ACCEPTANCE.md). |
| Audit geçmişi, aktör, eski/yeni değer ve sonuç | **PASS** — #39 detay/audit gösterimini kapsıyor. Önceki izole Ev WSL HTTP/PG kabulü ve atomik audit vakaları kendi kapsamlarında geçerli. [Özellik koruma](V26_FEATURE_PRESERVATION_ACCEPTANCE.md), [Ev WSL HTTP kabulü](V26_ISOLATED_INTEGRATION_ACCEPTANCE.md). | **BLOCKED** — yeni işlemin kalıcı audit kaydının Ofis oturumunda tarayıcıdan okunması doğrulanmadı. [Ofis izole kabul kaydı](V26_OFFICE_ISOLATED_ACCEPTANCE.md). |
| Hata yönetimi, kayıt 404, çakışma 409, kayıp yanıt ve UUID | **PASS** — #38 rota 404 teşhisi ve özgün kayıt hatası, #39 kayıp yanıtın aynı UUID ile okunması ve #50 sentetik 409'un başarıya dönüşmemesi. [Geçmiş ve yeni test kaydı](PROGRESS.md), [Kayıp yanıt kabulü](V26_PENDING_RECOVERY_ACCEPTANCE.md). | **BLOCKED** — güncel gerçek HTTP/tarayıcı hata ve kurtarma zinciri çalıştırılmadı. [Ofis izole kabul kaydı](V26_OFFICE_ISOLATED_ACCEPTANCE.md). |

## Bu görevde doğrulanan fark

İlk hedefli deneme **FAIL (0/1)**. `subscriberSaveRecovery.test.mjs` içindeki
eski test #39'da Düzenle formundan ayrılan kayıtlı paket seçicisini arıyordu
ve `AssertionError: control exists` ile duruyordu. Düzenleme senaryosu
güncel form üzerinden başlangıç tarihini değiştiriyor. Paket seçimi ve durum
kontrollerinin formda bulunmadığını, onay öncesi istek gönderilmediğini ve
onaylı isteğin mevcut paket, paket revizyonu, durum ve bitiş tarihini
koruduğunu doğruluyor. Uygulama kodunda değişiklik yapılmadı.

Son koşu **PASS (5/5)**. Sentetik Node fixture'larında oluşturma önizlemesi ve
onay, paket özeti ve tarihler, bilgi düzenlemesi ve onay, geçersiz router/tarih
reddi ve 409 hata sonucu kontrol edildi. Günlükler
`.local/e2e-50-before.log` ve `.local/e2e-50-targeted.log`.

Bilinen Chromium başlangıç izin hatası ve loopback EPERM aynı koşullarda
yeniden denenmedi. Uygun izole ortamda açık Ofis uçtan uca senaryoları
tamamlanabilir. Canlı V1/V2.5/V2.6.1, router, RADIUS, PostgreSQL veya üretim
servisine erişilmedi. Deploy, restart, migration ve push yapılmadı.
