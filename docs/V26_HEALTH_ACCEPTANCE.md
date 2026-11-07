# V2.6 Router Sağlık Uyarıları — kabul ve dağıtım kaydı

Son canlı sonuç: **ROLLBACK_VERIFIED — V2.6 canlı kabul HAYIR.**
Son kök neden görevi: **BLOCKED**; tarihsel Dashboard alt assertion ve
operandları geri kazanılamadı. Kanıtlanmış ayrı kusurlar yerelde düzeltildi.
Üçüncü dağıtım için teknik engel kaldırılmış sayılmaz.
Aşağıdaki yerel kabul ve plan tarihsel hazırlık kaydıdır; canlı deneme sonucu
belgenin son bölümündedir.

2026-11-03 · başlangıç main-guncel / 4890735 · LOCAL PASS.
Yalnız yerel sentetik doğrulama; yeni canlı dağıtım veya gerçek 9/9 V2.6
nihai kabulü yapılmadı. Ürün kodunda yeni hata bulunmadı, yeniden yazılmadı.

## Kabul matrisi

| Alan | Beklenti / kanıt | Sonuç |
|---|---|---|
| Fonksiyon | Beş ayrı sayaç; 1 Normal / 1 Dikkat / 1 Kritik / 3 Eski veri / 3 Veri yok sentetik dağılım; kritik önce, ilk beş uyarı ve tümüne bağlantı | PASS |
| CPU / RAM | Dikkat CPU ≥70 veya RAM ≥80; Kritik CPU ≥90 veya RAM ≥95; sıfır ve kesirli sınırlar | PASS |
| Güncellik | Tam 600000ms güncel; 600001ms eski; eski yüksek CPU Kritik sayılmaz; API freshness/okuma saati ölçümü tazelemez | PASS |
| Eksik veri | Eksik kaynak/ölçüm ID/zaman, gelecekte veya saat dilimsiz zaman, eksik/geçersiz metrik Normal olmaz | PASS |
| Router Merkezi | Ortak sağlık sınıflandırması, gerekçe/yaş, İstanbul zamanı, detay ve Escape | PASS |
| Gerçek / demo | source=V1_INVENTORY_EXPORT ve is_demo=false zorunlu; demo reddi; kaynak değişince bekleyen istek ve polling temizliği | PASS |
| Yetki | VIEWER gerçek kaynağa erişemez; envanter/demo isteği veya demo fallback yok | PASS |
| Yenileme | 60000ms, tek eşzamanlı istek; unmount abort; hata sonrası sonraki tick ile toparlanma | PASS |
| Hata / boş | Eski satır, sayaç ve uyarılar hata/yüklemede gizli; boş envanter açık; tekrar deneme | PASS |
| Masaüstü / mobil | Gerçek App + Chromium; Beyaz/Gece/Sistem Dashboard 1440/390/320px taşmasız; Router Merkezi 390px hücre gerekçeleri sığıyor; masaüstü Dashboard ve mobil Router görüntüleri incelendi | PASS |
| Frontend paket | TypeScript + Vite production build | PASS; mevcut >500kB uyarısı |
| Preferences onarımı | 4890735 ilerleme kaydında gerçek HTTP200/storage_ready ve korunan 9/9 ölçüm kanıtı | Önceki LIVE PASS; tekrar araştırılmadı |
| Fresh Pilot nihai V2.6 | Yeni aday hash'leri + gerçek ADMIN + 9/9 API/UI + sıfır beklenmeyen HTTP/pageerror + gerçek 60sn | FAIL → ROLLBACK_VERIFIED; aşağıdaki canlı kayıt |

Çalıştırılan hedefli test komutu (frontend dizininde):
`node --test tests/routerHealth.test.mjs tests/dashboardV1Health.test.mjs tests/v1Inventory.test.mjs`
Üç dosya PASS (4 + 6 + 6 tanımlı kontrol); skip/fail yok.
`npm run build` PASS.

`node tests/routerHealth.browser.mjs`: ilk beş tarayıcı kontrol grubu PASS.
Son VIEWER assertion, aynı context içindeki açık ADMIN demo sayfasının gerçek
polling isteklerini de saydığı için FAIL oldu. Ürün erişim açığı değildi.
ADMIN sayfası ölçümden önce kapatıldı; VIEWER pageerror, disabled seçici ve
uyarı yokluğu kontrolleri de eklendi. `--viewer-only` ile yalnız başarısız
kapsam yeniden çalıştırıldı: PASS. Başarılı kapsam tekrarlanmadı. Bu kayıt
tek kesintisiz full-run PASS iddiası taşımaz. Ayrı scope receipt'i FULL ile
karıştırılmaz. İlk loopback EPERM sonrası yalnız sentetik tarayıcı izinli çalıştı.

Yerel sentetik PNG/receipt: `.local/browser-acceptance/v26-health/` (Git dışı).
Yerel PostgreSQL, ADMIN, aboneler, seed ve demo DB'ye erişim/yazma yapılmadı.
503 beklentisi veya güvenlik kontrolü gevşetilmedi. Açık ürün hatası yok.

## Fresh Pilot — yalnız frontend dağıtım planı (hazırlık kaydı)

Hazırlık durumu: açık onayla kontrollü dağıtım denemesine EVET; canlı nihai
kabul henüz yok. Hedef yalnız `/srv/mikrotik-manager-v2-fresh-pilot` içindeki
mevcut uygulamanın `frontend/dist` dizinidir. Hedefin gerçek/resolved yolu
kurulu sunumla doğrulanmadan yazılmaz. V1/eski V2 hedeflenmez.

1. Açık kullanıcı onayı aday commit, frontend-only yayın, başarısızlıkta
   frontend rollback ve gerçek ADMIN salt okunur kabulünü birlikte kapsamalı.
   Yeni deploy öncesi temiz dal/commit ve candidate build dosya SHA256
   manifesti kaydedilir; mevcut başarılı build aynı kaynak için tekrar edilmez.
   Paket yalnız dist içerir; backend/config/.env/sır/DB/migration içermez.
2. Mevcut V2.5 frontend ve preferences HTTP200/storage_ready, auth, gerçek
   envanter/sağlık 9/9 önkoşulları bir kez doğrulanır. Hata varsa yayın STOP.
   API/DB PID-start, backend/config/unit hash'leri ve snapshot timer durumu
   ön-imaj olarak kaydedilir; hiçbiri değiştirilmez veya tetiklenmez.
3. Yeni benzersiz root-private backup dizininde mevcut tüm dist arşivi ve
   dosya içerik/owner/group/mode/mtime manifesti alınır. Arşiv listesi ve her
   dosyanın checksum eşleşmesi zorunlu; eski rollback yedeği üzerine yazılmaz.
   Yedek doğrulanmadan frontend yazılmaz. DB yedeği/restore/migration gerekmez.
4. Güvenli staging'de regular/no-link aday dosyaları ve hash'leri doğrulanır.
   Önce hash'li yeni assetler yayımlanır, ortak theme.js ön-imajı korunur;
   index aynı dosya sisteminde atomik replace ile en son yayımlanır.
   Eski assetler kabul boyunca korunur. Restart/reload veya unit değişmez.
   Sunulan index, theme ve tüm aday assetlerin HTTP hash'leri doğrulanır.
5. Sürümlü `deploy/v1-inventory/v26-browser-acceptance.mjs` ile özel kanıt
   dizini ve geçici ADMIN oturumu kullanılır. HTTP/pageerror tanıları korunur;
   sıfır beklenmeyen hata şartı kaldırılmaz. Gerçek 9/9 API/UI satırı, beş
   sayaç, eşik/gerekçe/zaman, gerçek 60sn tek seri okuma, kaynak ayrımı ve
   masaüstü/mobil kontrol edilir. Canlı eşik aşımı üretmek için veri/cihaz
   değiştirilmez; uç eşik kanıtı yerel sentetik testlerdir.
6. Herhangi bir kabul hatasında yeni deneme yapmadan frontend geri alınır:
   yalnız denemeye ait değişmemiş aday dosyaları kaldırılır, yedek içerik ve
   metadata geri yüklenir; index atomik olarak son geri konur. Eşzamanlı başka
   yayın/değişiklikte üzerine yazılmaz ve STOP. HTTP index/giriş assetleri ve
   tam dist manifesti eski ön-imajla eşleşmeli; rollback receipt kaydedilir.
7. Başarı veya rollback sonrası API/DB PID-start ve korunan hash/timer
   durumları karşılaştırılır; doğal snapshot zamanı değişimi ayırt edilir.
   ADMIN logout200/me401, cookie/oturum ve yalnız göreve ait tünel temizliği
   zorunludur. Sırlar/gerçek satırlar Git'e alınmaz. Son receipt PASS veya
   ROLLBACK_VERIFIED olur; başarısız kabul PASS sayılmaz.

Canlı servis restartı, snapshot timer değişikliği, backend deploy, PostgreSQL
onarımı, ADMIN/abone yeniden oluşturma, router/PPPoE/RADIUS işlemi bu planın
dışındadır. Sonraki somut adım bu frontend-only plan için açık canlı onaydır.


## Onaylı fffac4a canlı denemesi — 2026-11-03

**SONUÇ: ROLLBACK. Fresh Pilot eski V2.5 frontend üzerinde.**
V2.6 kabulü verilmedi; ikinci dağıtım yapılmadı. Dal/commit başlangıcı
main-guncel/fffac4a ve çalışma ağacı temizdi. Önceki başarılı frontend
build tekrar edilmedi; dokuz dist dosyası kullanıldı, ürün kodu değişmedi.

- Önkoşullar PASS: doğru resolved Fresh hedef/dist, gerçek LOCAL ADMIN,
  preferences HTTP200/storage_ready ve kurulu Values modeli doğrulaması,
  gerçek kaynak/is_demo=false envanter ve geçerli CPU/RAM/zaman/kaynaklı
  sağlık 9/9. Anonim preferences/envanter/me 401. API DB bağlı ve device
  adaptörleri kapalı. Timer enabled/active/waiting.
- Yedek 16:59:47 UTC: root-private
  `/srv/mikrotik-manager-v2-fresh-pilot/backups/v26-fffac4a-20261103T165947Z-q52gigww`.
  `dist-before.tar` SHA256:
  `3cd20b5fe94c4d6ab97b73fd58afbd9e96de99b02c3632de72c53a521f96ccfa`.
  Her üyenin içerik/uid/gid/mode bilgisi ve tam frontend ön-imajı doğrulandı;
  before.json dosya mtime_ns bilgilerini de içerir. Önceki yedekler korunur.
- İlk yayın öncesi kapı PREIMAGE_CHANGED ile yazmadan durdu. Dar metadata
  karşılaştırması frontend ve tüm unit alanlarının aynı, değişen dosyaların
  yalnız timer'ın doğal `config/v1-inventory.json` ve
  `config/health-transfer-status.json` çıktıları olduğunu kanıtladı.
  Bunlar refresh_health.py içinde tanımlı değişken veri çıktılarıdır.
  Yalnız bu iki dosya sabit config hash karşılaştırmasından ayrıldı;
  backend/config/sır/unit ve PID güvenlik şartları korundu. Başarılı
  önkoşullar veya yedek tekrar üretilmedi. Bu duruşta frontend yazılmadı.
- Tek gerçek yayında dokuz aday dosya sunuldu; hash'li assetler önce ve
  index atomik olarak son yazıldı, eski assetler tutuldu. Sunulan dokuz
  dosyanın HTTP SHA256 eşleşmesi PASS; deployed.json kaydedildi. Backend
  deploy, DB doğrudan erişim/yazma/migration veya restart/reload yapılmadı.
- Gerçek Chromium ADMIN kabulünde auth ADMIN ve preferences HTTP200 /
  storage_ready / Europe-Istanbul PASS. Sonraki `dashboard.desktop`
  assertion FAIL: pageErrors=[] ve httpFailures=[]. Assertion'ın satırını
  veya operandlarını bu receipt kaydetmedi. Beş sayaç/CPU-RAM/zaman/öncelik
  kontrollerinden hangisinin durduğu ve ürün/araç ayrımı KANITLANMADI.
  Bu nedenle yanlış pozitif denmedi, hata gizlenmedi ve PASS üretilmedi.
  60sn, Router Merkezi ve mobil aşamalarına ulaşılmadı; bu denemede canlı
  mobil/masaüstü ve bütünsel sağlık uyarısı kabulü PASS değildir.
- Kabul başarısızlığından sonra yalnız frontend rollback uygulandı.
  Arşiv yeniden doğrulandı; eski dosyaların içerik/owner/group/mode/mtime_ns
  bilgileri tam eşleşti. Denemeye ait yeni assetler kaldırıldı. Eski tüm
  frontend dosyalarının HTTP hash'leri de ön-imajla eşleşti. Uzak
  `rollback.json` sonucu ROLLBACK_VERIFIED.
- Geri dönüş sonrası preferences HTTP200/Values/storage_ready ve sağlık
  9/9 PASS; anonim preferences/envanter/me401. ADMIN logout200, aynı
  cookie ile me401. Tarayıcı kapandı, yalnız göreve ait tünel sonlandı;
  session.json silindi ve prepare receipt'inden geçersiz token kaldırıldı.
- V1 PID1173; eski V2 API429918/DB387726; Fresh API857737/DB843217.
  Tüm PID/exec-start/active-enter alanları öncesiyle aynı. Timer hâlâ
  enabled/active/waiting ve active-enter aynı. Backend/sabit config/handoff/
  Fresh unit hash'leri aynı. Doğal timer çıktısı korunur; timer elle
  tetiklenmedi. V1/eski V2 dosyalarına veya gerçek cihaz/PPPoE/RADIUS/IPsec
  yapılandırmasına yazma yok. Yerel DB/ADMIN/aboneler/seed değişmedi.

Özel yerel kanıt ve dağıtım yardımcısı:
`.local/deployment/v26-approved-fffac4a/` (0700; dosyalar0600; Git dışı).
Uzak backup içinde before/candidate/deployed/rollback receipt'leri var.
Sır veya gerçek satır/DB yedeği Git'e alınmadı.

Gerekli yerel kabul aracı düzeltmeleri: aday sürüm fffac4a, açık preferences
kontrolü, gerçek kaynakta demo API isteği yokluğu ve failed-request kapısı.
Başarısız deneme sonrası yalnız yerel tanı geliştirildi: Dashboard alt
adımları ve güvenli sabit runner adı+sayısal satır/sütun; ham stack/operand/
URL/token yazılmaz. Bunlar canlıda yeniden çalıştırılmadı. Bir yeni sentetik
konum/sır koruma testi PASS; önceki dört diagnostic kontrolü de PASS.
Runner syntax ve diff kontrolü PASS. Ürün/build/genel suite tekrar edilmedi.

Tek açık engel: `dashboard.desktop` assertion nedeninin kanıtlanmamış olması.
Sonraki adım yerel dar tanıyla bu karşılaştırmayı belirlemek; yeni canlı
kabul gerekiyorsa geri alınmış yayını kendiliğinden tekrar dağıtmamak.


## Dashboard assertion tanısı ve yerel düzeltmeler — d3aee2e sonrası

2026-11-03 · SONUÇ **BLOCKED**, tarihsel kök neden kesinleşmedi.
Bu bölüm önceki dağıtım hazırlığındaki EVET kararını geçersiz kılar:
üçüncü dağıtım önerilmez ve bu görevde yapılmadı.

### İki rollback aynı arıza olarak kabul edilmez

| Kanıt | Başarısız assertion | Beklenen / gerçekleşen | Sınır |
|---|---|---|---|
| İlk V2.6 denemesi (1c9bfcd; 491f444 kayıt) | Son `assert.deepEqual(errors, [])` veya `assert.deepEqual(failures, [])` | Boş dizi / bilinmiyor | Diğer UI kontrolleri geçmişti; hangi son liste doluydu kaydedilmedi. Ev WSL'de eski özel kanıt dizini mevcut değil; sürümlü rapor esas alındı. |
| İkinci deneme (fffac4a; d3aee2e kayıt) | `dashboard.desktop` altında bir assertion | Tam alt kontrol ve iki operand bilinmiyor | Receipt yalnız ERR_ASSERTION + geniş adımı tuttu; pageErrors=[] / httpFailures=[]. Başarısız kontrolden önce API/DOM frame diske yazılmamış. |
| Bu görevde mevcut V2.5 salt okunur ortak alan tanısı | 0 tabanlı row_2 metrik `includes` sonucu | true / false | İlk uyuşmazlıkta metin operandları kaydedilmedi; tarihsel V2.6 hatasıyla eşitlenemez. |
| Yalnız başarısız satırın sonraki salt okunur kontrolü | row_2 metrik karşılaştırması | `13% / 4.7%` / `13% / 4.7%` | Eşleşti; örnek zamanı ilerlemişti. Daha sonra operandları kaydeden ortak-alan gözleminde 9/9 eşleşti. Bu değerler tarihsel başarısız operandlar değildir. |

Dolayısıyla ürün hatası / oturum-cache / veri zamanlaması / test yanlış
karşılaştırması arasında **tarihsel atıf kanıtlanmadı**. Artık çözülmüş 503
araştırılmadı. Bilinmeyen değerler yeni örnek veya tahminle doldurulmadı.

### Tekrarlanabilir olarak kanıtlanan ayrı kusurlar

1. Kaynak koddaki koşulsuz `useResource('/routers')`, gerçek Router Merkezi
   açıkken de demo endpoint'ine GET atıyordu. Dağıtılmamış, tamamen üretilmiş
   sentetik dokuz satır ve mevcut build ile eski canlı runner yerelde
   çalıştırıldığında Dashboard/metrik/zaman/sayaç ve sonraki görünüm
   kontrolleri geçti; `source.isolation` FAIL oldu. Receipt ayrıca Router
   Merkezi aşamasında `/api/v1/routers` 404 kaydetti (sentetik sunucuda demo
   endpoint'i özellikle sunulmuyordu). Bu gerçek kaynak izolasyonu kusurudur;
   fffac4a'nın daha önceki Dashboard hatasının nedeni olduğu iddia edilmez.
2. Eski araç alanları ayrı tarayıcı round-trip'leriyle okuyordu: API JSON,
   Date.now, sayaçlar, satırlar ve uyarılar farklı anlardan gelebiliyordu.
   Ürünün 1sn değerlendirme saati ile Node'un daha sonraki anı da ayrıydı.
   Bu yöntem sınır/yenileme yarışına açıktır; tarihsel yarış yaşandığına
   ilişkin receipt yoktur. Önceki tanı kaybı ise koddan kesin doğrulanır.

### Kalıcı yerel değişiklikler

- Router kaynağı yalnız DEMO olduğunda `/routers` yüklenir. Gerçek kaynak
  demo verisi istemez; açık DEMO geçişinin gerçek demo okuması korunur.
- Ortak `browser/health-comparison.mjs` eski satır-geneli `includes`
  kontrolleri yerine doğru kolonun CPU ve RAM değerlerini ayrı, sayısal
  karşılaştırır. İki metriğin yer değiştirmesi veya doğru metnin başka
  kolonda bulunması FAIL'dir. Yalnız biçimsel whitespace eşdeğerdir;
  geçerli bilimsel sayı gösterimi de sayısal olarak doğrulanır.
- Fetch/1sn timer yalnız gözlenir: yanıt, saat, interval veya veri değiştirilmez.
  Gözlem response generation ve o görünüme ait gerçek sağlık tick'inin alt/üst
  zamanını tutar. Yeni görünüm eski tick'i kullanmaz. İki render frame'inden
  sonra API + DOM + sayaç + uyarı tek browser evaluate ile alınır.
- İstek sürüyorsa/yükleme bitmediyse veya gözlenen tick tam yaş sınırını
  kesiyorsa yalnız lifecycle kararlılığı beklenir. Beklenen durumun ekranda
  görünmesine kadar assertion tekrarı yapılmaz. Kararlı frame'de yanlış
  CPU/RAM/sayaç/durum/gerekçe/ölçüm zamanı veya yaş anında FAIL üretir.
  60sn interval ve canlı kabulün gerçek süre koşulu korunur; sahte saat yalnız
  sentetik browser regresyonundadır.
- Bağımsız oracle mevcut eşikleri/provenance/saat dilimi/10dk kuralını
  uygular. Sayaç ve satırlar aynı API snapshot'ı ve aynı gözlenen saat
  aralığında karşılaştırılır. İki uçta sınıf veya dakika yaşı farklıysa
  karşılaştırma bir sonraki kararlı gözleme bırakılır; yanlış değer affedilmez.
- Frame, assertion'dan **önce** private kanıt dosyasına yazılır. Receipt tam
  alan adı ve yalnız izinli sayısal/bool/sabit durum beklenen/gerçek değerleri
  tutar. Ham DOM/API özel frame'de kalır; keyfi hata operandı, token, cookie,
  kullanıcı adı veya ham stack receipt'e kopyalanmaz. Kanıt dizini private
  olmak zorundadır; yeni dosyalar0600. Eski FAIL receipt'ler değiştirilmedi.

### Doğrulama ve kapsam

- 5 yeni hedefli karşılaştırma testi +5 mevcut diagnostic testi PASS:
  eşikler, tam 10dk, eksik kaynak, sıfır, in-flight ve yaş sınırı, kararlı
  yanlış render'da FAIL, swapped metrikler, yanlış kolon, yanlış sayaç/durum/
  gerekçe, karışık snapshot/demo reddi ve güvenli operand kaydı.
- Gerçek App / sentetik loopback Chromium yeni regresyonu PASS: atomik
  frame, tutulan yanıt sırasında yeni metrik/eski DOM karşılaştırılmaması,
  Dashboard→Router Merkezi demo isteği yokluğu. Sonradan eklenen tam
  gerekçe/yaş eşitliği sonrası yalnız ilgili browser kapsamı tekrarlandı.
- Ek iki hedefli browser scope PASS: açık DEMO geçişi hâlâ çalışıyor;
  yeni görünüm önceki tick'ten daha yeni örneği kendi saatiyle değerlendiriyor.
- Doğrudan ilişkili routerHealth/routerCenter/v1Inventory üç test dosyası
  (15 tanımlı test) PASS; TypeScript/Vite build PASS, mevcut >500kB uyarısı.
  Syntax/diff PASS. Geniş suite ve değişmeyen build tekrar çalıştırılmadı.
- Sentetik fixture'lar üretilmiştir; canlı veri Git/test fixture'larına
  kopyalanmadı. Ürün oracle'ı testten import edilmez; aynı kurallar bağımsız
  kontrollerle doğrulanır. Sentetik receipt'ler `synthetic_only=true` ve
  `real_nine_router_acceptance=false` taşır. İlk yerel incelemede eski canlı
  runner sentetik sunucuda yalnız yeniden üretim için çalıştırıldı; özel
  receipt'in canlı adlandırılmış PASS metinleri gerçek 9/9 kabulü değildir.
- Üç kısa Fresh Pilot SALT OKUNUR tanısında yalnız geçici ADMIN auth/GET ve
  logout kullanıldı; her birinde logout200/me401. V2.5 ortak metrik/zaman
  alanları okundu, V2.6 beş-sayaç kabulü çalıştırılmadı. Yeni dağıtım, DB
  doğrudan erişim/yazma/migration, restart, timer/cihaz/V1/eski V2 değişikliği
  yapılmadı. Sırlar yalnız bellekte, browser ve görev tünelleri kapatıldı.
- Özel kanıt `.local/v26-root-cause/`; yeni sentetik regresyon receipt'leri
  `.local/browser-acceptance/v26-comparison/`. Bunlar Git dışındadır.

**Tek açık engel:** ikinci rollback'in kesin alt assertion'ı ve başarısız
operandları geri kazanılamadı. Yukarıdaki düzeltmeler kanıtlanmış kusurları
ve gözlem risklerini giderir; tarihsel Dashboard kök nedeni FIXED değildir.
Yeni yayını denemek bu kanıt boşluğunu kapatmanın yerine geçmez. Sonraki
somut adım, varsa asıl başarısız API/DOM/stack artefaktını kurtarmak veya
ürün/dağıtım değişikliği olmadan aynı uyuşmazlığı operandlarıyla yakalamaktır.

## d733ba8 — sürüme uygun salt okunur kabul kanıtı — 2026-11-03

**SONUÇ: BLOCKED (eski Dashboard hatasının kesin kök nedeni).**
Bu görevde yeni bir Dashboard uyuşmazlığı oluşmadı. Başarılı yeni örnekler,
operandları eksik tarihsel FAIL'i açıklamaz ve FIXED kanıtı sayılmaz.

- Yeni `v25-dashboard-readonly.mjs`, d733ba8'in observer/frame/operand
  mekanizmasını kullanır. V2.5'in dört sayacı ve >5dk güncellik sözleşmesi
  ayrı adapter ile doğrulanır. V2.6'nın beş sağlık sayacı, eşikleri, >10dk
  sınıflandırması ve öncelikli uyarıları bu canlı sürümde **çalıştırılamaz**.
  İki sözleşmeyi birbirine uygulamak veya sonuçlarını eşitlemek yasaktır.
- Tek gerçek ADMIN oturumu, yalnız GET tarayıcı ağı; preferences200 /
  storage_ready, gerçek V1_INVENTORY_EXPORT / is_demo=false, 9/9 kimlik,
  kaynak/CPU/RAM/İstanbul ölçüm zamanı ve dört sayaç PASS. Doğal 60sn
  yenilemede tam bir yeni okuma ve max_active=1 PASS; manuel snapshot/timer
  tetiklenmedi. İki response readAt farkı 60036ms.

| Private frame | API okuma UTC / generation | Router / son5dk / eski / yok | SHA256 |
|---|---|---|---|
| frame-0.json | 17:54:29.847 / 1 | 9 / 0 / 9 / 0 | `21061bbe9c1212fb3906abad58fb5e82ffb27b9bed7c4b120f95e43d1c7095cf` |
| frame-1.json | 17:55:29.883 / 2 | 9 / 9 / 0 / 0 | `b71e082b10d9b3abc1563cd7096dfc9c2df1246a9e78902b4cabd9476e226b6c` |

- Her frame assertion öncesi0600 kaydedildi; API verisi, response generation,
  gerçek değerlendirme tick'i alt/üst zamanı, DOM textContent ve innerText,
  sayaçlar aynı referansta. Yeni sayısal metrik karşılaştırması ve eski
  satır `includes(cpu + RAM)` kontrolü **her iki frame'de 9/9 eşleşti**.
  Değişen sayaçlar ayrı snapshot'larla karıştırılmadı. Pageerror, beklenmeyen
  HTTP ve requestfailure yok; receipt V25_READ_ONLY/PASS ve
  v26_live_acceptance=false / UNSUPPORTED_ON_V25 olarak saklandı.
- ADMIN logout200 ve aynı oturumla me401; browser ve yalnız görev tüneli
  kapandı. Cookie/parola stdin/bellek dışında tutulmadı. Kanıt dizini:
  `.local/v26-dashboard-evidence-d733ba8/` (Git dışı); receipt + cleanup var.
- V2.6 için yalnız yerel, izole, üretilmiş fixture ile mevcut
  `healthComparison.browser.mjs` çalıştırıldı: beş sayaç/satır karşılaştırması,
  tutulan asenkron yanıt ve kaynak geçişinde demo isteği yokluğu PASS.
  Bu sentetik sonuç gerçek V2.6 9/9 canlı kabul değildir. Receipt
  `.local/browser-acceptance/v26-comparison/result.json` içinde ayrı tutulur.
- İki yeni V2.5 adapter regresyonu PASS: doğru dört-sayaç/5dk sınırı;
  V2.5 ve V2.6 sözleşmelerinin birbirini reddetmesi; yanlış metrik/sayaçta
  güvenli tam alan adı ve beklenen/gerçek operand kaydı. Eski substring
  kontrolü farklı sonuç verirse bunun bool operandı da kaydedilir.
  Syntax/diff PASS. UI/ürün kodu değişmedi; önceki build/genel testler
  tekrarlanmadı. Kanıtlanan yeni ürün veya karşılaştırma kusuru yok.
- Dağıtım, DB doğrudan erişim/yazma/migration, servis restartı veya
  router/RADIUS/PPPoE/V1/eski V2 değişikliği yapılmadı. Preferences 503
  yeniden araştırılmadı. Önceki rollback incelemesi tekrarlanmadı.

**Teknik karar:** üçüncü dağıtım engeli kaldırılmış sayılmaz. Mevcut
V2.5 ortak kontrolleri ve izole V2.6 kontrolleri PASS, tarihsel Dashboard
hatasının ürün/test/asenkron/kaynak ayrımı atfı hâlâ kanıtsızdır. Başarısız
karşılaştırma oluşmadığı için yeni bir başarısız beklenen/gerçek çifti yoktur.
Yeni canlı dağıtımla bunu denemek bu görevin kapsamı dışındadır.

## f21cedf sonrası — eksik ölçüm tanısı ve yerel sağlık rollback kapısı — 2026-11-07

**Yerel hedefli düzeltme PASS; tarihsel Dashboard kök nedeni ve canlı kabul
BLOCKED.** Bu bölüm önceki FAIL/ROLLBACK_VERIFIED kayıtlarını değiştirmez.

### Kanıt ayrımı ve kaynak incelemesi

- Mevcut özel `v26-approved-fffac4a/ui-receipt.json` salt okunur incelendi:
  status=FAIL, step=dashboard.desktop, AssertionError/ERR_ASSERTION;
  comparison/operand alanı yok. Private rollback receipt'i ROLLBACK_VERIFIED.
  Sırlar, gerçek API/DOM satırları ve kullanıcı dosyaları değiştirilmedi.
- Bu nedenle tarihsel hatanın ürün/karşılaştırıcı/zamanlama nedeni bugün
  kesinleştirilemez. Receipt kaybı bilinen gerçek kabul engelidir; yeni yerel
  başarı, o tarihteki karşılaştırmanın nedeni olarak sunulmaz.
- Backend `read_inventory` alanları null olabilen salt okunur handoff üretir;
  frontend validInventory/routerHealth/dashboardV1Health eksik ölçümü ayrı
  değerlendirir. ADMIN, kaynak, is_demo, 10dk eşikleri, gerçek örnek zamanı,
  tek seri 60sn okuma ve önceki kaynak izolasyonu düzeltmeleri korunur.
  Yeni frontend sınıflandırıcı/backend ürün kusuru kanıtlanmadı; değiştirilmedi.

### Yeni kanıtlanmış kabul aracı kusuru

`frameStable` eksik/null sampled_at için iki tarafta da dakika yaşını NaN
hesaplıyordu. NaN eşitliği false olduğundan kararlı Veri yok satırı sürekli
kararsız kabul ediliyor, asıl kontrol yerine 10sn stable-frame timeout'ına
gidiyordu. Bu, tarihsel ERR_ASSERTION'ın kanıtlanmış nedeni değildir.

Düzeltme yalnız zamanı geçersiz/eksik satırın olmayan dakika sınırını atlar;
sağlık sınıfı eşitliği, aktif istek, satır sayısı ve geçerli zamanın dakika/10dk
sınır kontrolleri korunur. Dokuz tam ölçüm isteyen gerçek kabul sözleşmesi
gevşetilmedi: eksik metrik yine numeric_schema expected=true/actual=false ile
FAIL olur; stabil yanlış DOM/sayaç yeniden denenerek PASS yapılmaz. Artık frame
kaydı ve alan bazlı tanı aşamasına ulaşabilir.

### Sağlık hatasında rollback

Seçici updater'a `accept_health_or_rollback` yerel kütüphane kapısı eklendi.
Önce/sonra aday hash doğrulaması yapar; çağıranın sağladığı sağlık kontrolü
**yalnız True** dönerse geçer. Exception/False/None/FAIL nesnesinde mevcut
rollback fonksiyonunu çağırır. Başarılı geri dönüşte de kabul başarısız kalır:
`HEALTH_ACCEPTANCE_FAILED_ROLLBACK_VERIFIED`. Drift veya bozuk yedekte
`HEALTH_ACCEPTANCE_FAILED_ROLLBACK_BLOCKED`; kullanıcı değişikliği ezilmez,
çalışan aday ve kalıcı yedek silinmez. Rollback başarılı diye PASS dönülmez.

Bu kapı kendisi HTTP, browser, subprocess veya servis başlatmaz. CLI'ya yeni
dağıtım yolu eklenmedi; mevcut hedef/onay kapıları ve yalnız QuickActions
seçici paket kapsamı aynıdır. Tarihsel Fresh Pilot dağıtım aracına bağlanmış
veya canlıda uygulanmış değildir. `verify` komutunun hash PASS'i uygulama
sağlığı PASS'i sayılmaz; bu ayrım önceki CLI davranışında da geçerlidir.

### Hedefli gerçek doğrulama

- 2 yeni socket-free JS regresyon PASS: null zamanın kararlılığı ve açık
  alan tanısı; in-flight/satır sayısı/10dk/dakika sınırı/stabil yanlış DOM reddi.
- Mevcut karşılaştırma dosyasından yalnız 2 doğrudan etkilenen observer ve
  V2.5 adapter testi seçildi: PASS. V2.5/V2.6 sözleşmeleri birleşmedi.
- 5 yeni geçici filesystem sağlık-kapısı testi PASS: gerçek Node Dashboard
  karşılaştırıcısında Normal sayacı beklenen1/gerçek0 hatası; tam kaynak/dist
  hash geri dönüşü; yedek/diğer özellik korunması; yalnız True kabulü;
  operatör drift ve bozuk yedekte güvenli duruş. Aynı keşifte updater'ın
  doğrudan ilgili 9 mevcut testi de PASS (toplam 14 Python test). Sonrasında
  import düzeni yalnız yeni sınıf keşfedilecek şekilde düzeltildi; test gövdeleri
  değişmedi ve başarılı testler yeniden çalıştırılmadı.
- Node syntax/Python AST/diff kontrolleri PASS. Uygulama bundle'ı veya geniş
  suite çalıştırılmadı; değişiklik üretim frontend TS/backend kodu içermiyor.
  PG/HTTP/browser/socket testi, SSH/VDS, DB/cihaz veya restart/deploy yok.

Sonraki tek kanıt işi: özgün başarısız API/DOM/stack artefaktını kurtarıp aynı
assertion'ın gerçek operandlarını karşılaştırmak. Artefakt yokken tarihsel
neden BLOCKED kalır; yeni yayın bu boşluğun yerine kullanılmaz. Ayrı bir güncel
V2.6 sürüm kabulü planlanacaksa önce yerel sentetik kapsam, ardından yalnız
ayrıca açık onaylı hedef kapsamı değerlendirilir; bu görev canlı yetki vermez.

## a7458b2 sonrası — özgün hata kanıtı araştırması — 2026-11-07

**İnceleme tamamlandı; tarihsel kesin neden BLOCKED.** Bu görev test veya yeni
üretim gözlemi değildir. Başlangıç `main-guncel/a7458b2`, çalışma ağacı temiz.
Yalnız mevcut yerel kayıtlar, bu dalın Git geçmişi ve belgeler okundu.

### Bulunan ve bulunamayan kanıt

| Kaynak | Gerçek bulgu | Kanıtın sınırı |
| --- | --- | --- |
| `.local/deployment/v26-approved-fffac4a/ui-receipt.json` | Özgün ikinci denemenin version=fffac4a, status=FAIL, step=dashboard.desktop, AssertionError/ERR_ASSERTION kaydı mevcut. pageErrors ve httpFailures listelerinin ikisi de boş. | failure alanında comparison, expected/actual, stack veya assertion konumu yok. Yalnız bir önceki kabul kontrolü kayıtlı; Dashboard başarısı yok. |
| Aynı dizindeki `private-prepare.json` ve `private-rollback.json` | Envanter hazırlık/geri dönüş metadata'sı ve ROLLBACK_VERIFIED mevcut. | inventory yalnız count/health_count/ids taşır; özgün hata anının CPU/RAM/zaman/API gövdesi veya DOM'u değildir. |
| Aynı özgün ikinci-deneme dizini | Kontrol/çalıştırma kaynakları ve beş JSON dosyası mevcut. | dashboard-api.json, dashboard-frame.json, Dashboard PNG, HTML/DOM dump veya Playwright trace/stack artefaktı bu dizinde yok. |
| `.local/deployment/v26-fresh-1c9bfcd/` | İlk denemenin eski kanıt yolu 491f444 ve sonraki PROGRESS kaydında geçiyor. | Bu yerel kopyada dizin yok. 1c9bfcd ağacında `v26-browser-acceptance.mjs` de sürümlü değil. Eski kayıtlar son iki runtime hata-listesi assertion'ını aday gösteriyor; hangi listenin/hatanın başarısızlığı kanıtlanmıyor. |
| `.local/v26-root-cause/synthetic-repro/` | API JSON ve dört Dashboard/Router PNG'si, `source.isolation` FAIL receipt'i mevcut; bu receipt'te bir HTTP hatası var. | Üretilmiş sentetik yeniden üretim, özgün ikinci-deneme Dashboard frame'i değil. source.isolation hatası dashboard.desktop hatasıyla eşitlenmez. |
| `.local/v26-dashboard-evidence-d733ba8/frame-0.json`, `frame-1.json`, `receipt.json` | Atomik API/DOM frame'leri mevcut; receipt PASS, v26_live_acceptance=false. | Sonraki V2.5 salt okunur adapter tanısının yerel artefaktları; tarihsel başarısız V2.6 operandları değildir. V2.5'e bu görevde erişilmedi. |
| `.local/v26-root-cause/live-*.json`, V2.6 sentetik browser receipt'leri ve anonim browser-run sonuçları | Sonraki tanı/başarı ve farklı kabul kapsamları mevcut. | Sonraki metrik eşleşmeleri ve sentetik PASS tarihsel nedeni kanıtlamaz. Diğer genel FAIL_OR_BLOCKED receipt'lerinde özgün iki commit veya dashboard.desktop atfı/stack alanı bulunmadı; ilişki uydurulmadı. |
| Yerel Git ve geçici dosya adları | main-guncel geçmişinde kaynak/doküman sürümleri bulundu; özel receipt yolları Git ignore kapsamındadır. Erişilebilen `/tmp` dosya adlarında ilgili özgün artefakt bulunmadı. | İncelenen dalın yol geçmişinde özgün API/DOM/trace/PNG commit'i bulunmadı. Git ignore tek başına geçmişte hiç commit edilmediğini kanıtlamaz; yol geçmişi ayrıca kontrol edildi. Stash veya başka bilgisayar/arşiv/uzak sunucu araştırılmadı. |

Yerel kanıt kimlikleri (yalnız SHA256; içerik/sır/gerçek satırlar rapora alınmadı):

- Özgün ikinci-deneme FAIL receipt'i:
  `74798ee98f15448772436dafdb1e54ed9f4b782f2838502fc94285d723f0a06b`.
- Özgün ikinci-deneme rollback receipt'i:
  `ed7dfcb96d25552b4760ab65f11f377e4d88366f584cd4d6e763238250487d54`.
- Ayrı sentetik yeniden üretimin FAIL receipt'i:
  `1f2d64e23fa15895c734481bc08300244f534dc85edc68b0d7b3cc849fce1410`.

### Git geçmişinin kanıtladığı kayıt kaybı

`fffac4a:deploy/v1-inventory/v26-browser-acceptance.mjs` içinde
`inspectDashboard` kaynak/sayaç/satır/metrik/zaman/uyarı assertion'larını
60–76. satırlarda yapıyor. `dashboard-api.json` ancak 77. satırda, PNG ancak
inspectDashboard başarıyla döndükten sonra 81. satırda yazılıyor. Hata bu
assertion grubunda oluştuğunda özgün API/DOM anı diske kaydedilmiyor.

Aynı sürümün `browser/acceptance-diagnostics.mjs` 38–42. satırları catch
sonucunda yalnız step, hata türü/code ve güvenli genel mesajı saklıyor;
assertion operandları/stack satırı yok. Bu kaynak davranışı, bulunan özgün
receipt'in neden kesin alt kontrolü açıklayamadığını kanıtlıyor. Eşzamanlı
olmayan API/saat/DOM okumaları kaynakta görülür; tarihsel yarış gerçekleştiği
bu kayıtlardan çıkarılamaz. İkinci denemedeki boş runtime hata listeleri de
ilk denemenin kayıp listelerini açıklamaz.

### NaN düzeltmesiyle kesin karşılaştırma

Git'te `frameStable` işlevi **d733ba8** ile, ikinci başarısız denemeden sonra
eklenmiştir. fffac4a runner'ı bu işlevi veya captureHealthFrame'i import/çağrı
olarak içermez; eski `inspectDashboard` akışını kullanır. a7458b2'nin düzelttiği
NaN dakika-eşitliği d733ba8'deki bu sonraki kararlılık kontrolündedir.

Dolayısıyla **a7458b2'de düzeltilen frameStable NaN kod yolu, özgün fffac4a
Dashboard assertion'ının doğrudan nedeni olamaz.** Bu, eski hatanın gerçek
nedenini belirlemez; eski örnekte eksik ölçüm veya başka bir uyuşmazlık olduğu
iddia edilmez. Yerel NaN/rollback PASS kendi kapsamını korur; tarihsel sağlık
hatası FIXED veya yanlış pozitif ilan edilmez.

### Karar ve sonraki tek işlem

Kabul raporu ve belge/diff kontrolleri PASS; özgün API/DOM/stack operandı
bulunamadığından tarihsel kesin neden ve canlı V2.6 kabulü BLOCKED kalır.
Mevcut yerel kanıtlarda aynı arama veya test yeniden yapılmamalıdır.

Sonraki tek işlem, **özgün testi çalıştıran bilgisayardaki bağımsız yerel
arşivden varsa hata-anı API/DOM/stack/trace kopyasını bu incelemeye almak**.
Yalnız aynı receipt'in kopyası eksik operandı tamamlamaz. Böyle bir arşiv de
yoksa tarihsel neden çözülememiş olarak kalır; yeni sürüm kabulü ayrı bir
karardır, eski olayın kanıtı yerine sunulmaz. Yeni canlı deneme/dağıtım istenmez.

Bu görevde test/build/browser/socket, canlı VDS/V1/V2.5, cihaz/RADIUS/IPsec,
veritabanı veya servis işlemi yok; stash okunmadı/değiştirilmedi. Özel yerel
artefaktlar yalnız okundu; hiçbirisi Git'e eklenmedi veya yeniden yazılmadı.

## 2e53ad0 sonrası — sürümlü yerel yeniden üretim ve tanılama — 2026-11-07

**Sentetik yeniden üretim/tanılama PASS; özgün olayın kesin kök nedeni BLOCKED.**
Bu görev, eksik özgün frame'i arama döngüsünü tekrarlamak yerine başarısız
sürümün kodunu yeniden kurup farklı hata koşullarını ayırdı. Varsayımsal
frontend/backend ürün düzeltmesi veya yeni canlı deneme yapılmadı.

### Olay ve uçtan uca zincir

İncelenen ana olay ikinci denemedir: `fffac4a02e26a9f309197adacbf119c9b2e79602`,
2026-11-03 Fresh Pilot frontend-only yayını; özgün receipt version=fffac4a,
FAIL/dashboard.desktop/AssertionError/ERR_ASSERTION. Hazırlık PREPARED,
yayın DEPLOYED, sonra ROLLBACK_VERIFIED; protected_unchanged=true. Hazırlık
ve geri dönüş metadata'sında envanter count=9/health_count=9. Bunlar hata
anının CPU/RAM/zaman/DOM operandlarını sağlamaz. İlk 1c9bfcd denemesinin son
runtime hata-listesi arızası bu olayla birleştirilmedi.

Kaynak zinciri incelendi: V1 export → şema/monoton ölçüm kontrolü ve atomik
handoff (`refresh_health.py`) → yalnız yerel dosyayı doğrulayan
`adapters/v1_inventory.py` → merkezi ADMIN GET `/v1-inventory` → kaynak ve
satır kontrolü/seri yenileme → Dashboard sınıflandırma/gerçek ölçüm zamanı →
yayımlanan frontend asset hash doğrulaması → tarayıcı API/DOM karşılaştırması
→ başarısız kabulde frontend rollback. Bu görevde export/adapter/DB/HTTP
çalıştırılmadı. Tarihsel kaynak ve metadata incelemesi yeni güncel VDS durumu
sayılmaz. Bilinen yetki/provenance/10dk/60sn sınırları değiştirilmedi.

### İzole yeniden oluşturma

Yeni `tools/reconstruct-v26-dashboard.py`, sabit tam commit'ten frontend
kaynaklarını ve orijinal runner'ı `git archive` ile yeni private `/tmp`
dizinine açar. Çalışma dalını, mevcut dosyaları veya stash'i değiştirmez;
bitince kendi dizinini temizler. Tarihsel package.json/package-lock.json ile
yerel dosyalar byte düzeyinde eşit bulundu; hazırlayıcı uyuşmazlıkta durur.
Kurulum/indirme yok; mevcut yerel React/esbuild kullanılır. Çalışan tarihsel
browser/OS/DB ortamının tamamının birebir kopyası olduğu iddia edilmez.

Orijinal runner kaynak SHA256:
`0130d1c30a7f0ce180a1cb9cc4884d0ed588bdf0fb3b341679dc243807728002`.
Orijinal `inspectDashboard`, classify ve stamp fonksiyonları değiştirilmeden
çıkarılıp gerçek eski Dashboard bileşeninin React SSR çıktısına uygulanır.
Yalnız beklenen router adları sentetik dokuz kimlikle beslenir; DOM adapter'ı
bu kontrollü HTML'i okur. Bu, browser innerText/layout/cache/transport veya
canlı 9/9 kabulü değildir; tam App sidebar kontrolü de bu modelle kanıtlanmaz.

| Hedefli koşul | Orijinal kod sonucu | Yorum |
| --- | --- | --- |
| Aynı sentetik API, render ve kontrol saati | PASS, başarı sonrası snapshot yazma noktasına ulaşır | İzole modelin tutarlı başlangıç kontrolü. |
| Bir örnek tam 600000ms yaşında render; kontrol saati +1ms | ERR_ASSERTION; snapshot yazımı 0 | Ekran Normal, sonradan hesaplanan oracle Eski veri. Aynı çağrı grubu ve hata türü yeniden üretildi; özgün olayın bu sınırda olduğu kanıtlanmadı. |
| Bir satırda ölçüm/zaman/provenance eksik | Başka bir ERR_ASSERTION; snapshot yazımı 0 | Veri yok davranışı ile eski runner'ın tam-ölçüm/metin beklentisi farklı. Ön/son metadata'daki 9 sağlık örneği nedeniyle özgün olaya atıf özellikle zayıf; eksikliğin olay anında yaşandığı bilinmiyor. |
| Aynı sınır vakasını mevcut snapshot'a bağlı oracle/render saatiyle kontrol | PASS: Normal8/Dikkat1/diğer0 | Mevcut d733ba8 sonrası karşılaştırma çözümü sentetik saat yarışı koşulunu zaten gideriyor. Bu görev yeni ürün düzeltmesi gerektirmedi; a7458b2 NaN kodu tarihsel akışta yoktur. |

Yeniden üretim komutu (yerel repo kökü; tamamen offline):
` .venv/bin/python tools/reconstruct-v26-dashboard.py `.
İlk harness hazırlığında Node spawnSync Git çağrısı EPERM verdi; socket
bağlantısı denenmedi. Hazırlık Python/native esbuild üzerinden ayrıldı.
SSR DOM adapter'ındaki `&lt;/&gt;` çözümlemesi düzeltildi; başlangıçtaki harness
assertion'ları ürün kusuru sayılmadı. Orijinal assertion'lar gevşetilmedi.

### Olası nedenlerin kanıt düzeyi

- **Kesin:** özgün runner API/saat/DOM'u ayrı okuyordu; başarısız assertion'dan
  önce snapshot yazmıyordu, catch operand/stack konumunu atmaktaydı. Kayıt
  kaybı bugün de özgün nedenin ayırt edilmesini engelliyor.
- **Sentetik koşulda kanıtlı, tarihsel atıf yok:** 1ms sınır/zaman yarışı ve
  eksik ölçüm ayrı ayrı aynı genel ERR_ASSERTION çıktısını üretebiliyor.
  Genel hata türü/step tek başına bunlardan birini seçmeye yetmez.
- **Tarihsel olarak doğrulanmamış:** başka render/yenileme yarışı, biçimsel
  innerText farkı, farklı satır/metrik uyuşmazlığı veya browser/cache etkisi.
  Bunlar için varsayımsal ürün değişikliği yapılmadı.
- **Bu olaya bağlanamaz:** sonraki sentetik source.isolation arızası,
  V2.5 adapter frame'leri, ilk denemenin kayıp runtime listeleri.
- **Doğrudan dışlandı:** daha sonra eklenmiş frameStable NaN kod yolu.
  İkinci receipt'teki boş pageErrors/httpFailures de belirli bir HTTP hatası
  iddiasına kanıt oluşturmaz. Rollback doğrulanması sağlık kabulü değildir.

### Gelecekteki kaybı önleyen yeni tanılama

`browser/health-evidence.mjs` mevcut onay kapılı runner'a bağlandı. Yeni canlı
çalıştırma yapılmadı. Mekanizma:

- Aynı atomik frame'in allowlist API alanları, DOM hücre/sayaç/uyarıları,
  clock/readAt/generation bilgisi **assertion öncesi** kaydedilir.
- Her çalıştırmada ayrı 0700 alt dizin, exclusive 0600 sıralı JSON ve SHA256
  referansları vardır; önceki ölçümler/kanıtlar üzerine yazılmaz. Eski ham
  frame dump'ları yerine kontrollü alan projeksiyonu kullanılır.
- Hata halinde orijinal tanı korunur; seçili sağlık görünümü için ek API/DOM
  snapshot'ı alınmaya çalışılır. Bu ek gözlem `atomic=false` ve
  CAPTURED_AFTER_FAILURE olarak ayrılır; hata anının önceki frame'i yerine
  sunulmaz. Sayfa kapalıysa CAPTURE_BLOCKED açıkça kaydedilir.
- Sabit runner/karşılaştırıcı dosyası+sayısal satır/sütun, güvenli typed
  karşılaştırma operandları ve diğer assertion'ların yalnız bool/sonlu sayı
  operandları saklanır. Ham exception mesajı, keyfi operand/stack yolu,
  cookie/auth gövdesi ve bütün sayfa HTML'i saklanmaz. Session cookie canary
  redaksiyonu test edildi; bilinmeyen API alanları dışarıda kalır.
- Runner SHA ve `/api/ready` repo/build/port kimliği ayrı kaydedilir; GET-only
  sınırı korunur. Build kimliğini kaydetmek hedeflenen yayınla eşitliği
  kendiliğinden kanıtlamaz; manifest/build karşılaştırması ayrıca gerekir.
- Yerel updater kütüphane sağlık kapısı private yedeğe ayrı
  `health-failure.json` ve `health-rollback.json` yazar. Sağlık FAIL, rollback
  PENDING/VERIFIED/BLOCKED ayrıdır. Kayıt arızası rollback denemesini atlamaz;
  eski kanıt ezilmez. Geri dönüş tamamlanıp kayıt eksikse EVIDENCE_BLOCKED
  eki verilir. CLI'ya yeni canlı deploy/sağlık çalıştırma yolu eklenmedi;
  tarayıcı ve updater kanıtları otomatik canlı orkestrasyon iddiası taşımaz.

### Bu görevin sonuçları

4 yeni tarihsel SSR/DOM karşılaştırma senaryosu, 3 yeni JS kanıt/redaksiyon
kontrolü ve 3 yeni Python rollback/kanıt kontrolü PASS. Doğrudan etkilenen
mevcut diagnostic dosyasından 2 güvenlik/exception testi ayrıca seçildi ve
PASS. Toplam 12 hedefli kontrol; syntax/AST/diff PASS. Başarılı kapsam yalnız
doğrudan ilgili kod değişince yeniden kontrol edildi. Genel suite/build,
PG/HTTP/socket/gerçek browser kabulü veya canlı sistem işlemi yok.

**Kök neden bulundu mu?** Kayıt kaybı ve sentetik koşullar kanıtlı; özgün
Dashboard olayının tam nedeni bulunmadı. Aynı genel hatayı yeniden üretmek
tarihsel nedeni bulmak değildir. V2.6 canlı kabul/V2.7 kabul tabanı BLOCKED.
Sonraki tek işlem: **normal Ev WSL'de yalnız güncel yerel sentetik Dashboard
browser kabulünü yeni tanılama kaydıyla tamamlamak**; yayın/DB/cihaz işlemi
olmamalı. Özgün hata-anı arşivi sonradan bulunursa ayrı tarihsel kanıt sayılır;
aynı eksik receipt araması tekrar edilmemeli.

Yerel sentetik `frontend/tests/healthComparison.browser.mjs` de aynı kanıt
katmanına bağlandı; her çalıştırma kendi yeni private kanıt alt dizinini açar.
API'ler interception ile üretilmiş fixture'dır; mevcut API/DB'ye bağlanılmaz.
Codex'te bilinen socket engeli tekrar denenmedi; bu yeni browser bağlantısının
çalışma zamanı kabulü burada yapılmadı (syntax kontrolü PASS). Sonraki tek
işlemin somut komutu, normal Ev WSL proje kökünden:
`cd frontend && node tests/healthComparison.browser.mjs`.
Bu komut mevcut yerel Playwright/Chromium gerektirir; canlı runner veya
--approved-read-only komutu bu görevin sonraki işlemi değildir.

## 1a018a1 sonrası — kimliksiz canlı erişim sınırı ve yeni yanıt/saat yarışı — 2026-11-07

**Yerel yanlış-FAIL düzeltmesi PASS; özgün kök neden ve güncel canlı sağlık
BLOCKED.** Önceki FAIL/ROLLBACK_VERIFIED ve PASS kayıtları esas alındı;
kullanıcının son 15 PASS kapsamı yeniden koşturulmadı. Önceki 12 tanılama
kontrolü de yeni canlı kabul olarak sunulmadı.

### Canlı durum: doğrulanamadı

Belgelenen V2.6 kabul adresi VDS'nin `127.0.0.1:18996` adresidir; bu makinenin
loopback'iyle eşitlenemez. Güncel, doğrulanmış anonim bir dış HTTP hedefi veya
bu ortamda kimliksiz kullanılabilen doğrulanmış tünel kaydı yok. Kaynakta
`GET /api/v1/v1-inventory` current_admin → current_demo_user zinciriyle
session cookie ister. Statik sayfanın veya ready200'ün varlığı bu korumalı
sağlık verisini doğrulamaz.

Kullanıcı talimatı gereği login, parola/cookie/token isteme veya kullanma,
eski session dosyası okuma ve yeni SSH/tünel açma yapılmadı. Yanlış hedefe
istek atılmadı. **Canlı HTTP isteği denenmedi; bu oturumda yeni DNS/socket
hatası gözlendiği de iddia edilmez.** Önceki ADMIN giriş/oturum PASS korunur;
canlı Dashboard bugün sağlıklı/arıza/erişilemez ilan edilmez. Ölçüm yaşı,
sayaçlar, çalışan build ve mevcut API/DOM eşitliği güncel olarak bilinmiyor.

### Mevcut kodda yeni kanıtlanan yanlış FAIL

Aynı görünümdeki asenkron yanıt, 1sn sağlık saati tick'inden bağımsız gelir.
`V1InventoryLiveView` yeni data props'unu mevcut `now` state'iyle render eder.
Yeni gerçek ölçüm `now` değerinden ileri, fakat yanıtın alınma `readAt`
saatinden geri olabilir. Ürün, eski değerlendirme saatiyle geçici Veri yok
ve gizli metrik/tarih gösterir; sonraki tick'te ölçüm normal değerlendirilir.
Bu kısa aralıkta eski `frameStable` iki clock ucunda da Veri yok bulup true
dönüyordu. Tam ölçüm isteyen comparator ise DOM metriklerinde Veri yok
bulup yanlış bir kalıcı uyumsuzluk gibi FAIL verebiliyordu.

Yeni sentetik örnek: ölçüm=t+500ms, response readAt=t+600ms, son clock=t.
Düzeltme öncesi yeni regresyon `frameStable=false` beklentisinde FAIL verdi
(gerçek=true). Sonraki t+1000ms tick'inde gerçek SSR görünümünde metrikler
yeniden mevcut; mevcut comparator Normal8/Dikkat1/diğer0 PASS verdi.
`DashboardV1Health`, `routerHealth`, `dashboardV1Health` dosyalarının kullanılan
sabit eski kaynakla eşitliği SSR testinde ayrıca doğrulandı; bu nedenle kanıt
mevcut render/classifier davranışına da aittir. Browser/HTTP kabulü değildir.

Minimal düzeltme yalnız kabul aracının `frameStable` fonksiyonundadır:
doğrulanmış provenance ve sonlu zamanla **clock.upper < sampled_at <= readAt**
ise sonraki gerçek tick beklenir. Ölçüm zamanı/API yanıtı/ürün saati veya
veriler değiştirilmez; metriklerin uyuşması beklenmez. `sampled_at > readAt`,
eksik/readAt'sız zaman ve kalıcı yanlış metrik bu koşulla affedilmez. Geçerli
saatte stabil yanlış DOM hâlâ anında FAIL'dir. CPU/RAM eşikleri, 10dk kuralı,
60sn seri okuma, yetki, tam ölçüm şartı ve V2.5 sözleşmesi değiştirilmedi.

Bu, **mevcut araçta kanıtlanmış ayrı bir kusurdur**. Özgün fffac4a olayında
frameStable bulunmadığından bu düzeltme o eski olayın nedeni veya kapanışı
olarak sunulmaz. Eski 10dk/+1ms koşulu ve eksik ölçüm sentetik olarak zaten
kanıtlıdır; hangisinin özgün olayda olduğu hâlâ bilinmiyor. Yeni ürün/API
kusuru kanıtlanmadı; frontend/backend ürün kodu değiştirilmedi.

### Hedefli doğrulama ve karar

- Yeni same-view saat testi önce FAIL, minimal düzeltmeden sonra PASS.
- Yeni future-invalid/eksik/readAt'sız zaman ve stabil yanlış metrik reddi
  PASS; değişen kapının olumsuz koşulları korunur.
- Yalnız yeni current-identical SSR senaryosu PASS: geçici Veri yok → gerçek
  sonraki tick → doğru metrikler/sayaçlar. Mevcut başarılı senaryolar seçilmedi.
- Toplam 3 yeni hedefli kontrol; JS syntax/diff ve belge kontrolleri PASS.
  Geniş suite, son 15 PASS, eski tekrar üretimleri, build veya browser yeniden
  çalıştırılmadı. Geçici kaynak ağacı dışında veri/sistem değişikliği yok.

Sonraki tek işlem: **mevcut yetkili ortamdan üretilmiş, oturum bilgisi
barındırmayan canlı API/DOM sağlık kanıtını incelemek**. Codex'e login/cookie
aktarımı veya erişim kontrolünün kaldırılması istenmez. Böyle bir kanıt
yokken güncel canlı sağlık ve tarihsel tam neden BLOCKED kalır; yeniden
bağlantı/dağıtım denemesi yapılmaz.
