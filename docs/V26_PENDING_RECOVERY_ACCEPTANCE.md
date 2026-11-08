# V2.6 — aktöre bağlı kalıcı UUID recovery — 2026-11-06

Başlangıç: main-guncel / 455210f. Yerel kapsam PASS; gerçek PostgreSQL/HTTP
kabulü BLOCKED. Browser kabulü çalıştırılmadı. Canlı sistem işlemi yok.

Create/edit (legacy ve workspace), tekil renew ve toplu execute ilk POST'tan
önce işlem başına ayrı localStorage anahtarı yazar. İçerik yalnız actor, UUID,
kapalı işlem türü ve oluşturma zamanı; gövde/hedef abone/alanlar/receipt/token/
parola/cookie saklanmaz. Yedi gün sonunda, bozuk/ek alanlı kayıtta veya kesin
sonuçta anahtar silinir. Storage kapalıysa mevcut bellek akışı devam eder.

Yeniden açılışta doğrulanmış kimlikle ortak sonuç paneli kayıtları yükler.
Yalnız GET: auth/me, sabit türden türetilen receipt yolu, terminal sonuçtan
önce auth/me yeniden kontrolü. Otomatik POST/polling yok; belirsiz sonuç için
manuel sorgulama düğmesi var. Her sorgu 15sn ile sınırlı. Kesin sonuç panelde
UUID ve durumla görünür; bağlı liste/detay/geçmiş/Dashboard/raporlar yenilenir.
Backend'in mevcut aktör/ADMIN/router scope kontrolleri değiştirilmedi.

Kimlik/yetki değişimi kuşak kontrolüyle geç gelen sonucu reddeder, mevcut
kayıtları temizler ve UI ağacını yeniden kurar. Logout UI'ı hemen kapatır ve
sekmelere storage bildirimi gönderir. Anahtar başına yazma, bir sekmenin başka
UUID'yi ezmesini önler; silinen kaydı geri yazan snapshot birleştirmesi yok.
Sekmeler arası storage değişimi aktif recovery'yi iptal edip görünümü yeniler.

PASS: 7 yeni hedefli Node/esbuild testi: dört yol/reopen/minimal metadata/GET;
foreign actor/logout/VIEWER/inactive; server identity ve geç yanıt; bozuk/eski/
gelecek/ek alan/kapalı storage; kısmi belirsizlik ve bağımsız anahtarlar;
router yetki kaybı/abort; gerçek save hook'ta POST öncesi journal, kayıp yanıt,
tekPOST+GET ve terminal cleanup. İlk inactive testinde sorgu engeli eksikti;
active=false kontrolü eklendi ve yalnız başarısız kapsam tekrarlandı.
TypeScript/Vite build ve diff kontrolü PASS; mevcut >500kB uyarısı sürüyor.
İlk dosya yazma komutu yanlış cwd nedeniyle uygulanmadı; doğru proje kökünde
uygulandı. Önceki PASS suite'leri tekrarlanmadı.

Sıradaki hedef: izinli izole ortamda gerçek PostgreSQL/HTTP kabulü; bu görevde
BLOCKED bırakıldı. V1/V2.5/VDS/SSH/MikroTik/RADIUS/IPsec/gerçek veri/deploy/
migration/servis restartı yok. Kullanıcının PROGRESS eklemeleri korunur ve
commit dışında kalır.

## 819dc32 sonrası güvenli uzlaştırma — 2026-11-08

Başlangıç main-guncel/819dc32 temiz; Altın Kurallar, güncel PROGRESS, özellik
koruma ve son işlem sonucu kabulü okundu. Uzak dal ls-remote ile aynı tam SHA
olarak doğrulandı. **Yerel hedefli kabul PASS; Chromium/gerçek HTTP kabulü
BLOCKED/çalıştırılmadı.** Önceki atomik kayıt/revizyon/idempotency yeniden
uygulanmadı.

Somut eksikler: legacy QuickActions belirsiz sonuçtan sonra POST'u tekrar
ederken, genel pending paneli bazı nesneleri yalnız ID biçimiyle terminal
sayabiliyordu. Atomik geçmişi ve güncel revizyonu kontrol etmeden “tamamlandı”
demek bu görevde kaldırıldı.

- QuickActions ilk onayda tek POST ve mevcut minimal actor/UUID journal'ı
  kullanır. Yanıt kaybı, timeout, bozuk/mismatched sonuç, UNKNOWN veya sonraki
  GET hatasında aynı UUID'nin mevcut `/subscribers/demo-requests/{id}` GET'i
  okunur; ikinci POST yok. Onay önizlemesi ve beklenen alanlar sabittir.
- Mevcut adapter sonuç okuyucusu QuickActions EXTEND'in RENEWAL/DATE_EDIT
  audit kayıtlarını da yalnız action=EXTEND ise okur. Actor ve güncel router
  scope denetimi, requests-events JOIN ve READ ONLY transaction korunur.
  Yeni endpoint, migration veya veri yazımı yok. Normal action'sız RENEWAL
  hâlâ bu yoldan okunmaz; kapsam keyfi genişletilmedi.
- Legacy başarı yanıtında kaynağı doğrulanmış kalıcı sentetik kayıt, pozitif
  revizyon ve aynı UUID'nin geçerli zaman/aktör/kaynak içeren audit olayı
  zorunludur. İlk POST'un kesin 400/401/403/404/409/422 reddi ve kaydedilmeyen
  503/belirsiz sonuç ayrı gösterilir. Bilinen terminal kayıtlar yeniden
  sorgulanmaz; başarı callback'i aynı sonuç için yeniden çağrılmaz.
- Yeniden açılış uzlaştırması kimliği önce/sonra doğrular, mevcut receipt'i
  okur ve başarıdan önce güncel aboneyi GET ile alır. Legacy'de aynı audit
  UUID'si, workspace'te aynı aktör/revizyon/uygulanan işlem geçmişi aranır.
  Current revision gerideyse, aynı revizyonda alanlar farklıysa, kaynak veya
  audit doğrulanamıyorsa UNKNOWN ve journal korunur. Daha yeni geçerli
  revizyon kabul edilir; eski receipt alanları güncel kayda yazılmaz.
- Kayıtlı başarısız receipt ayrı FAILED'dır; başarısızlığı yeni bir yazmayla
  “tamamlama” yapılmaz. Terminal journal silindiğinde aynı sekmedeki mevcut
  panel bildirilir. Ortak invalidation liste/detay/günlük rapor/Dashboard'u
  kendi yetkili kaynaklarından yeniden okutur; UNKNOWN sorgusunda da güncel
  görünümler yenilenir. Sentetik workspace toplamı legacy Dashboard toplamına
  katılmaz. Bütün ekranlar için tek global snapshot/transaction iddiası yok.
- UI başarı mesajı geçmiş işlemde kaydedilen değeri belirtir; bunu daha
  sonraki değişiklikleri içeren “güncel değer” diye sunmaz. Başarılı/başarısız/
  belirsiz sayıları ayrıdır; sorgu düğmesi açıkça kayıtlı sonucu okuduğunu
  söyler. Mevcut LOCAL/RADIUS, ADMIN/router ve actor kapıları korunur.

### Gerekli kontroller

31 frontend sentetik test PASS: subscriptionActions8,
pendingSubscriberOperations9, subscriberRenewalRecovery12,
resourceInvalidation2. QuickActions timeout+UNKNOWN+sonra geçerli GET,
UUID'nin reload metadata'sı, dört işlemde bozuk alan/audit yanıtı ve yalnız
tekPOST; kesin ret, aktör/yetki değişimi, revizyon/audit reddi, daha yeni
meşru current ve terminal cleanup kapsanır. Yeni pending fixture'ında eksik
is_demo ve receipt/current nesnesinin yanlış paylaşımı düzeltildi; assertion
ve ürün kapıları gevşetilmedi. Başarılı kapsam yalnız ilgili değişiklikte
tekrarlandı.

Backend LegacyReceiptTests'te üç hedefli mock test PASS: Quick EXTEND GET
kapsamı, actor/router reddi, VIEWER/yetki kaybı ve yalnız SELECT/SET READ ONLY
SQL kontrolü. Testte gerçek DB bağlantısı veya veri yazımı yapılmadı.

Tek tsc/Vite build PASS; ana bundle614.63kB, mevcut >500kB uyarısı sürer.
Diff kontrolü PASS. Chromium EPERM bilinen ortam engeli olarak korundu;
yeni socket/browser veya güvenlik gevşetme denemesi yok. Gerçek PostgreSQL/
HTTP, reload/mobil Chromium kabulü iddia edilmez. Çok eski işlem mevcut
workspace detayının son50 geçmişinden çıkmışsa güvenli UNKNOWN kalabilir;
eksik kanıt başarıya çevrilmez.

V1/V2.5/VDS/router/RADIUS/IPsec/DB/deploy/restart/migration/silme veya gerçek
veri işlemi yok. Yalnız kod ve ağsız sentetik/mock testler değişti. Tarihsel
Dashboard rollback ve genel PG/HTTP kabul engelleri kapanmış sayılmadı.

- Normal `git push origin main-guncel` denendi: push BLOCKED,
  `Could not resolve host: github.com`. Yerel tek commit korunur; ağ
  erişiminde normal push gerekir. Force push yapılmadı.

## 907e1cc sonrası tekil UUID audit kanıtı ve son50 sınırı — 2026-11-08

Başlangıç main-guncel/907e1cc temiz. Altın Kurallar, güncel ilerleme, özellik
koruma ve önceki recovery kabulü okundu; uzak main-guncel aynı SHA olarak
ls-remote ile doğrulandı. Kullanıcının önceki push başarı kaydı korunur.
**Yerel hedefli kabul PASS.** Önceki bölümün son50 nedeniyle UNKNOWN kalma
sınırı, bu bölümdeki aynı sürüm backend/frontend sözleşmesiyle giderildi.

### Kök neden ve çözüm

UUID lookup zaten Event primary key'iyle tekil ve yetkili yapılıyordu.
Sorun pending frontend'in bu sonucu son50 ile sınırlı detay geçmişi içinde
tekrar aramasıydı. Geçmiş limiti büyütülmedi, geçmiş tarayan yeni API yapılmadı.

- Mevcut save/renew/management request GET yanıtlarına opsiyonel, tipli
  `audit` kanıtı eklendi. İstek UUID, abone, aktör, router, LOCAL/RADIUS,
  revizyon, işlem, zaman, sonuç ve PERSISTENT_WORKSPACE/is_demo kapsamını
  taşır. Hassas alan, komut gövdesi veya ham audit changes dönmez.
- Backend kanıtı doğrudan aynı UUID audit satırı ve aynı read-only snapshot'ta
  güncel abone üzerinden kurar. Cached save/renew yanıtı audit abone/revizyon/
  router metadata'sı ve değişen alanlarla eşleşir; source mevcut hesabın
  değiştirilemez yetkili kaynağı ve fields.source ile doğrulanır. Aynı
  revizyonda güncel alanlar da eşleşmelidir. Sonraki meşru revizyonlar eski
  receipt'i bozmaz ve eski değerler güncel kayda yazılmaz.
- Management receipt'i audit kolonları, zaman, işlem, aktör, previous/new
  alanları ve router geçişiyle karşılaştırılır. Router değişmeyen işlemde
  previous_router_id=router_id şartı geçmiş revizyonlarda da korunur. Yanlış
  abone/router/source/revizyon, eksik cached sonuç veya audit yoksa UNKNOWN;
  eldeki benzer geçmişten başarı üretilmez. ADMIN/actor/izole depo guard'ları
  değiştirilmedi. Lookup yalnız SELECT; PG read-only transaction korunur.
- Pending frontend doğrudan UUID kanıtını yanıtla karşılaştırır; workspace
  detay geçmişinde arama yapmaz. Güncel abone kaynağı/revizyonunu ve aynı
  revizyonda alan eşitliğini okumaya devam eder. Legacy'nin mevcut tekil
  UUID lookup'ında dönen atomik cached audit kanıtı korunur; güncel listenin
  geçmişinde yeniden arama şartı kaldırılır. GET dışı recovery yok.
- Yerel 7 günlük takip süresi dolduğunda persisted metadata yine silinir;
  aynı oturumda yalnız minimal metadata ile “Takip süresi doldu; sonuç
  belirsiz” bildirimi tutulur. Yeniden sorgu/POST yapılmaz; kimlik değişimi
  bildirimi temizler. Reload sonrasında temizlenen metadata geri üretilmez.
  Bulunamayan/geçersiz server receipt'i UNKNOWN kalır, journal korunur.
- Yeni endpoint/menü/bileşen, migration, history-limit veya yazma akışı yok.
  Ortak invalidation liste/detay/günlük rapor/Dashboard'un kendi yetkili
  kaynaklarını yeniler. Workspace toplamları legacy Dashboard'a karıştırılmaz.

### Kanıt ve sınırlar

22 hedefli frontend test PASS: pendingSubscriberOperations12,
subscriptionActions8, resourceInvalidation2. Son50'de bulunmayan kayıt ve boş
current history ile geçerli kanıt başarıyla doğrulanır; yanlış proof alanları,
aktör/yetki kaybı, daha eski/current drift revizyonu, expired/missing receipt,
tekPOST+yalnızGET recovery, metadata temizliği ve kaynak yenilemesi denetlendi.
Yeni bulk fixture'ına gerçek sözleşmenin router_id alanı eklendi; doğrulama
ve assertion kapıları gevşetilmedi.

16 hedefli backend test PASS: 3 yeni UUIDAuditEvidence testi, mevcut 6
SaveReceiptTests ve 7 GetRecovery testi. Yeni testte oluşturma, yenileme,
paket ve durum işleminden sonra55 değişiklik yapıldı; detay geçmişinde yalnız
son50 var ve eski dört olay yok. Aynı dört UUID lookup'u doğru orijinal
kanıtı döndürür; SQL dinleyicisi yalnız SELECT doğrular. Cached/audit abone,
revizyon, router, source, paket, aktör, işlem ve values sapmaları reddedilir.
Mevcut endpoint yetki, readonly, rollback, replay ve foreign-actor testleri
korunur. Eski tam yanıt assertion'ı eski tüm alanlar+tam audit alanlarıyla
güncellendi. Yeni fixture tarihleri mevcut string-only sözleşmeye uyarlandı;
ürün kuralları gevşetilmedi. Başarılı kapsam gereksiz tekrarlanmadı.

Backend testleri yalnız private TemporaryDirectory SQLite/sentetik fixture'ları
kullandı; mevcut veya canlı DB'ye bağlanılmadı. Test fixture yazımları dışı DB
işlemi yok. PG/HTTP/Chromium kabulü değildir.

Tek tsc/Vite build PASS; ana bundle615.51kB ve mevcut >500kB uyarısı sürer.
Diff kontrolü PASS. Chromium bilinen EPERM nedeniyle BLOCKED; tekrar
başlatma/socket/güvenlik gevşetme denemesi yapılmadı. Eski backend audit
kanıtını dönmezse yeni frontend güvenli UNKNOWN kalır; son50 düzeltmesinin
tamamı aynı sözleşmeyi destekleyen backend/frontend gerektirir.

V1/V2.5/canlıVDS/router/RADIUS/IPsec/canlıDB/deploy/restart/migration/silme
veya gerçek veri işlemi yapılmadı. Tarihsel Dashboard rollback ve genel
PG/HTTP kabul engelleri bu hedefli PASS'lerle kapanmış sayılmaz.

- Normal `git push origin main-guncel` denendi; push BLOCKED:
  `Could not resolve host: github.com`. Yerel tek commit korunur; ağ
  erişiminde normal push gerekir. Force push yapılmadı.
