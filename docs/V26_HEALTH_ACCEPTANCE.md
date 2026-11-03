# V2.6 Router Sağlık Uyarıları — kabul ve dağıtım kaydı

Son canlı sonuç: **ROLLBACK_VERIFIED — V2.6 canlı kabul HAYIR.**
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
