# V2 yerel demo kabul ve dağıtıma hazırlık raporu

**Güncel kanıt — 2026-10-28:** Aşama 9 gerçek WSL HTTP/PostgreSQL kabulü **110 kontrol PASS**, mevcut **9 abone korundu** (yerel kabul JSON'u doğrulandı). Aşağıdaki eski BLOCKED kayıtları tarihsel ortam sonuçlarıdır. Aşama 10 tarayıcı tıklama/otomatik yenileme kabulü henüz **BLOCKED**; üretim yayını kapsam dışıdır.

Tarih: 2026-10-27. İncelenen temel: `main`, `2089efc`; bu raporla birlikte eski Dashboard API tutarlılık düzeltmesi ve yedi hedefli güvenlik/tutarlılık testi eklenmiştir. Başlangıç çalışma ağacı temizdi. Kesin teslim commit'i Git geçmişindedir.

**Kabul kararı: BLOCKED. V2 üretime hazır değildir.** Soketsiz işlev ve güvenlik kanıtları vardır; gerçek PostgreSQL/HTTP, kalıcılık ve tarayıcı kabulü tamamlanmamıştır. Yerel demo kabulünün ileride geçmesi de tek başına üretim yayını yetkisi veya üretim güvenliği onayı sağlamaz.

## Son engel değerlendirmesi — 2026-10-27, temel `11d2b2c`

**Genel karar değişmedi: BLOCKED.** Bu devam görevinde yeni bir ürün testi veya gerçek entegrasyon PASS sonucu alınmadı. Aşağıdaki eski PASS kanıtları tarihsel kapsamlarıyla korunmuştur.

İzinli araç kataloğu ve süreç metaverisi incelendi: WSL2 çekirdeği üzerinde NoNewPrivs=1/Seccomp=2 sürüyor; kullanılabilir komut aracı aynı sandbox sınırında. Sandbox dışı WSL çalıştırma/yerel tarayıcı aracı yok; `chromium`, `chromium-browser`, `google-chrome`, `firefox` komutları bulunmadı. Bu, WSL hostundaki servislerin bozuk veya kapalı olduğunu kanıtlamaz. Önceden gözlenen soket EPERM/httpx eksikliği/ASGI timeout yeniden denenmedi; alternatif yetkisiz erişim veya bağımlılık kurulumu yapılmadı.

| Tek seferlik plan adımı | Son durum | Bu görevdeki işlem |
| --- | --- | --- |
| İzinli yürütme önkoşulu | BLOCKED | Araç/süreç incelemesinde yeni izinli dış yürütme yolu bulunmadı. Metadata incelemesi PASS; bağlantı testi değildir. |
| Gereksinimler ve prepare-demo/dev.sh | BLOCKED | Bilinen soket engeli devam ederken kurulum/seed/servis başlatma yapılmadı. httpx kurulum denemesi tekrarlanmadı. |
| Gerçek HTTP giriş/yetki/okuma | BLOCKED | HTTP/ASGI denemesi ve bellek tabanlı alternatif doğrulama başlatılmadı. |
| Gerçek seed idempotency ve veri karşılaştırması | BLOCKED | PostgreSQL erişimi doğrulanamadığı için kullanıcı verileri okunup değiştirilmedi; seed çalıştırılmadı. |
| PPPoE mutation/audit/rollback/reopen | BLOCKED | Opt-in DB/API testleri başlatılmadı; SKIP üretilip PASS sayılmadı. |
| Dashboard/Router/PPPoE/Alarm görsel kabul | BLOCKED | Yerel tarayıcı/uygulama erişimi yok; render testi görsel kabul yerine tekrarlanmadı. |

Yeni FAIL bulgusu veya hedefli kod düzeltmesi yok. Plan, izinli yerel V2 yürütmesi sağlanınca aşağıdaki sırayla bir kez uygulanabilir; bu oturumdan tamamlanamaz. Mevcut demo verisi, kod, bağımlılıklar, servisler ve güvenlik ayarları değişmedi. Bu devam görevinin tek değişikliği kabul/ilerleme durumunun kaydıdır.

## Durumların anlamı

| Durum | Anlam |
| --- | --- |
| PASS | Belirtilen sınırlı test/inceleme gerçekten geçti; daha geniş kapsamı kanıtlamaz. |
| FAIL | Somut kabul kriteri ihlali veya test başarısızlığı. Düzeltilmiş bulgular ayrıca belirtilir. |
| BLOCKED | Gerekli kontrol ortam/çalıştırma engeli yüzünden tamamlanamadı. SKIP, PASS değildir. |
| NOT TESTED | Bu çalışmada yürütülmeyen ve sonuç çıkarılmayan kapsam. |

## Kabul matrisi

Aşağıdaki önceki kanıtlar `docs/PROGRESS.md` ve depodaki testlerle ilişkilidir; bu çalışmada gereksiz tekrar edilmedi. Render/handler testi gerçek tarayıcı testi; SQL-kayıt mock'u gerçek PostgreSQL transaction testi değildir.

| Alan | Doğrulanan sınırlı kapsam ve kanıt | Bekleyen kabul |
| --- | --- | --- |
| Sentetik alarm otomasyonu | PASS (yeni, temel `9b011e4`): 11 reducer/metadata testine ek 6 seed ve 3 olay sözleşmesi regresyonu; 3 yeni frontend yaşam döngüsü testi ve mevcut 21 projeksiyon/render testi. Dashboard açık alarm sayısı, kaynak/zaman çizelgesi ve doğrulanmayan süreyi boş bırakma geçti. | BLOCKED: gerçek PostgreSQL metadata append/rollback/reopen testi (1 SKIP), HTTP ve tarayıcı kabulü. Eski kullanıcı olayları otomatik ölçüm gibi yorumlanmaz; canlı poller yok. |
| Merkezi İnternet Kullanım ve Bağlantı Raporları | PASS (yeni, temel `aa84d3d`): 7 dönem/tekilleştirme/hacim/filtre/oturum testi, 5 yeni ekran/grafik/menü/URL render testi; ilgili mevcut 17 frontend regresyon testi ve 4 soketsiz backend rapor sözleşmesi testi. TypeScript/Vite derlemesi geçti. | BLOCKED: gerçek HTTP/PostgreSQL ve tarayıcı kabulü. WAN trafik sayacı mevcut modelde yok; Veri yok gösterilir. Abone örnek hacimleri WAN trafiği değildir. |
| Merkezi Günlük Yönetim Raporu | PASS (yeni, temel `315b930`): 8 dönem/filtre/tekilleştirme/toplam/loader testi ve 3 gerçek React render testi; Dashboard görünümü, Bugün/Dün/Son 7 Gün, ortak merkez projeksiyonları, geri gelmenin kendi zamanı, boş/hata durumları ve detay bağlantıları. İlgili mevcut 20 regresyon testi ve TypeScript/Vite derlemesi de geçti. | BLOCKED: gerçek HTTP/PostgreSQL verisi ve tarayıcıda filtre/modal/geri gezinme/görsel kabul. Sayaçlar açıkça son kayıtlı durumdur; tarihsel durum snapshot'ı değildir. |
| Merkezi Dashboard | PASS (önceki): `centralDashboard`, `dailySummary`, `centralViews`; kayıtlı sayımlar, router durumları, PPPoE tür ayrımı, kart/filtre bağlantıları, 24 saat işlem ve alarm projeksiyonu. PASS (bu tur): eski API de kayıtlı sayımları kullanıyor. | BLOCKED: gerçek sunucudan aynı kayıtları okuma, kart tıklamaları ve görsel sonuç. |
| Router listesi/detayı | PASS (önceki): `routerReport`, `test_router_projection`, `centralViews`; router_id önceliği, eski ad eşleşmesi, ilişkili abone bağlantıları, sentetik kaynak/son görülme ayrımı. | BLOCKED: gerçek DB ilişkileri, WAN/olay geçmişi ve tarayıcı gezinmesi. |
| PPPoE abone yönetimi | PASS (önceki): `test_demo_management`, `subscriberFilters`, `subscriberManagement`; zorunlu alanlar, kaynak, birleşik arama/filtre, benzersizlik kuralları, paket/durum değişikliği, önceki/yeni değerler. PASS (bu tur): gerçek oturum/yetki fonksiyonları ve bellekten oluşturma reddi. | BLOCKED: HTTP üzerinden CREATE/PLAN_CHANGE/STATUS_CHANGE, kalıcı kayıt ve audit. |
| Abonelik takip/yenileme | PASS (önceki): `expiry`, `subscriptionAlerts`, seed/projeksiyon testleri; Türkiye günü, eşikler, tekil toplam, yenileme sonrası liste/detay/özet uyumu. | BLOCKED: HTTP RENEWAL, idempotent tekrar, gerçek audit/rollback ve yeniden açılış. |
| Kullanım/bağlantı raporu | PASS (önceki): `demoIntegration`, `subscriberReports`, `subscriberReportsView`, `subscriberObservation`; gerçek seed çıktısı, MiB, eksik yönü sıfır saymama, kapalı oturum süresi, aktif snapshot/son görülme ayrımı. | BLOCKED: hazırlanmış PostgreSQL kayıtlarından HTTP okuyup görsel ve dönem seçimi kontrolü. |
| Alarm merkezi | PASS (önceki): `routerEvents`, `connectionAlarms`, `centralViews`; açık kimlikle eşleşen kesinti/geri gelme, tek router, sıralı zaman, 24 saat/tarih/tür/durum filtreleri, bilinmeyen kapsam ve detay render. | BLOCKED: gerçek API olay kaynağı, filtreli kart geçişi ve native detay diyaloğu. |
| Demo seed/veri koruma | PASS (önceki): `test_demo_integration_seed`; 7 eski kayıt, 2 ek örnek, sabit kimlikler, kullanıcı adı çakışması, yeniden seed'de kullanıcı düzenlemelerini koruma. | BLOCKED: gerçek DB'ye seed uygulaması, ikinci seed karşılaştırması, disk kalıcılığı ve eşzamanlılık. |
| Erişilebilirlik/tema/mobil | PASS (önceki `2089efc`): 23 hedefli frontend testi ve derleme; modal handler/cleanup, hash dönüşü, etiketler, seçili renk çiftleri ≥4.5:1, Türkiye biçimi. | BLOCKED: Beyaz/Gece/Sistem, 320/390/768/1440 px gerçek ekran, taşma, Tab/Shift+Tab/Escape/native odak. Tam erişilebilirlik değerlendirmesi NOT TESTED. |

## Bu çalışmanın yeni sonuçları

- **PASS — 7 test:** `test_acceptance_security.py`. Demo girişinin yanlış bilgiyi reddetmesi; HttpOnly/SameSite=Strict/path=/api/8 saat çerez tanımı; `me`, logout ve sahte/eski token reddi; envanter ve mutation route'larında merkezi session bağımlılığı; iki yazma guard'ında rol/is_demo/eylem başlığı; kalıcı depo olmadan oluşturmanın 503 ile reddi; kayıtlı Dashboard sayımları; yanlış DB/şema hedefinin IO'dan önce reddi ve CORS whitelist tanımı ve router liste/detay varsayılan yanıt biçimi. Bunlar doğrudan fonksiyon/route-metadata testidir, HTTP middleware kabul testi değildir.
- **PASS — derleme:** TypeScript/Vite. İstemci uyumluluk tipinde desteklenmeyen eski telemetri alanları nullable yapıldı.
- **PASS — sınırlı statik tarama:** izlenen dosyalarda özel anahtar/AWS/GitHub token desenleri bulunmadı; `frontend/src`, `frontend/public` ve son üretilen `frontend/dist` içinde DB URL, V2 DB kullanıcı bilgisi veya özel anahtar deseni bulunmadı. Değerler loglanmadı. Bu desen taraması her tür sırrın yokluğunu kanıtlamaz.
- **PASS — fark kontrolü:** `git diff --check`.
- **FAIL → düzeltildi:** kullanılmayan eski `GET /api/v1/dashboard/summary` route'u hâlâ sabit 649 abone, uydurma online oturum ve grafik/aktivite fixture'ı döndürüyordu. Panel zaten `loadDailySummary` ile kayıtlı listeler/detaylar üzerinden projekte ediyordu. Uyumluluk endpoint'i de mevcut demo deposundan toplam/kaynak/aylık paket tutarı hesaplıyor; ölçüm/oturum/olay olarak doğrulayamadığı alanları `null` veriyor ve depo hatasında sabit veriye düşmüyor. `monthly_revenue` eski alan adı korunmuştur; tutar paket bedelleri toplamıdır, tahsilat değildir. Ayrıntılı alarm ve kullanım verilerinin mevcut kendi endpoint/sözleşmeleri korunmuştur.
- **FAIL → düzeltildi:** router detay modeli varsayılan `wan_snapshot: null` alanını üretirken router listesi ham fixture dönüyordu; bu fark mevcut liste/detay sözleşmesi karşılaştırmasını bozuyordu. Başarısızlık yeni regresyon testiyle gösterildi. Liste mevcut `RouterRecord` modeliyle serileştirildi; yalnız bu başarısız test tekrar çalıştırıldı ve geçti. Seed edilmiş WAN bilgileri detayda zenginleştirme olarak kalır; bu test WAN örneği olmayan eski kayıtların varsayılan biçimini kapsar.
- **BLOCKED — ASGI denemesi:** httpx eklemeden gerçek middleware/route çalıştırma denemesi beklemede kaldı; durduruldu. Süre sınırlı deneme de FastAPI/AnyIO `run_sync_in_worker_thread` beklemesinde TimeoutError verdi. Kök neden ayrıştırılmadı; ürünün veya WSL hostunun arızalı olduğu sonucuna varılmadı. Tekrar döngüsü yapılmadı; geçici ASGI harness teslim edilmedi. Yeni güvenlik testleri daha dar ve açıkça fonksiyon/metadata kapsamındadır.
- **BLOCKED — gerçek PostgreSQL/API ve tarayıcı:** önceden kaydedilmiş socket EPERM, eksik tanımlı httpx gereksinimi ve yerel tarayıcı yokluğu bu çalışmada yeniden araştırılmadı. Önceki SKIP sonuçları PASS olarak devralınmadı.
- **NOT TESTED:** üretim yükü/çok worker/uzun süre dayanıklılık, kapsamlı penetrasyon ve bağımlılık zafiyet taraması, üretim TLS/kimlik altyapısı/operasyonel yedek-geri dönüş, dağıtım ve canlı cihaz/RADIUS entegrasyonu. Bunlar bu demo kabulünün dışındadır; üretim uygunluğu çıkarılamaz.

## Statik güvenlik sınırları

| Sınır | İnceleme sonucu ve sınırı |
| --- | --- |
| Router/RADIUS/V1/VDS | PASS (statik): `modules/adapter_contracts.py` yalnız Protocol bildirir. Runtime modüllerinde bunları somutlayan/bağlantı başlatan router/RADIUS istemcisi veya V1 importu bulunmadı. Dev akışında uzak sunucu/deploy/cihaz yazma komutu yok. Gerçek ağ davranışı NOT TESTED. |
| Depo izolasyonu | PASS (statik + yeni negatif test): `PostgresDemoStore` yalnız loopback, port 55432, `mikrotik_manager_v2`, `v2_local`, `v2_demo` veya UUID'li `v2_demo_test_*` şemalarını kabul eder; marker sorgular. SQLAlchemy engine oluşturmak bağlantı açmaz. Gerçek DB erişimi BLOCKED. |
| Seed ve yazma | PASS (statik/önceki birim): seed açık bakım komutunda; startup migration/seed çalıştırmaz. Tablo/satır kilidi ve aynı transaction içinde kayıt+audit+retry yanıtı var. Belleğe mutation fallback'i yok. Transaction davranışının gerçek DB kanıtı BLOCKED. |
| Yetki | PASS (fonksiyon/metadata): session bağımlılığı; demo admin, eylem başlığı ve confirmed kapalı komut sözleşmesi. CORS yalnız 127.0.0.1:5173; bu tek başına yetkilendirme/CSRF sertifikasyonu değildir. Ağdan 401/403/422 testleri BLOCKED. |
| İstemciye veri | PASS (sınırlı inceleme): kullanıcı yanıt modeli yalnız demo kimlik alanları; frontend DB'ye doğrudan bağlanmıyor. Yönetim IP/örnek WAN/test ağ adresleri bilinçli sentetik envanterdir, sır değildir. Ekrandaki `demo/demo-only` halka açık yerel demo bilgisidir, gerçek kullanıcı sırrı değildir. |
| Üretim kimliği | NOT TESTED / demo tasarım sınırı: tek sabit demo hesabı, süreç içi session set'i ve HTTP yerel çalışma için Secure varsayılanının false olması üretim kimlik/oturum çözümü değildir. Server-side süre sonu, rate limiting ve üretim erişim yaşam döngüsü burada sertifikalandırılmadı. Dış ağa açılmamalıdır. |

Bu görevde DB/seed/test kaydı yazılmadı, veri silinmedi; servis başlatma/restart, migration, canlı bağlantı veya deploy yapılmadı. Sistem güvenliği değiştirilmedi, sandbox dışı yürütme/izin aşma denenmedi.

## Tek seferlik izinli yerel doğrulama planı

Bu plan bu görevde **uygulanmadı**. Yalnız izinli yerel WSL terminalinde, V2 proje dizininde (`~/Codex-Projects/mikrotik-manager-v2`; ofis makinesinde mevcut yol `/home/suatpc/Codex-Projects/mikrotik-manager-v2`) uygulanır. Canlı V1/VDS/router/RADIUS gerekmez. Bir adım başarısızsa durup çıktıyı kaydet; tekrar döngüsü veya güvenlik gevşetme yapma.

1. Mevcut `.venv` için yalnız proje gereksinimlerini bir kez sağla: `.venv/bin/python -m pip install -r backend/requirements-dev.txt`. `./dev.sh --prepare-demo` ile yalnız repo-owned V2 kümesini hazırla; mevcut şema/kullanıcı verisini sıfırlama. Bu script mevcut sunucuyu restart etmez. Ardından `./dev.sh` ile V2 uygulamasını ayrı terminalde aç.
2. Tarayıcı/HTTP istemcisiyle `127.0.0.1:5173`/`127.0.0.1:8000` üzerinden demo giriş/çıkış ve `/api/health` kontrolü yap. Yetkisiz okumada 401, yanlış yazma eyleminde 403, onaysız komutta 422 doğrula. Mevcut router/subscriber/detail/router-events kayıtlarını oku; sentetik işaretler ve kimlik ilişkilerini kontrol et. Uyumluluk Dashboard toplamını kayıtlı listeyle karşılaştır.
3. Mevcut abone detayları/geçmişleri/raporları ve olay yanıtlarının kopyasını al; `.venv` ile `PYTHONPATH=backend .venv/bin/python -m app.demo_storage init --examples` komutunu ikinci kez çalıştır. Aynı kayıt kimlikleri ve içeriklerinin değişmediğini, yeni çoğalma/silme olmadığını karşılaştır. Üretim/V1 kimlik bilgisi kullanma.
4. Yalnız var olan opt-in geçici şemalarda gerçek entegrasyon kapsamını bir kez çalıştır; ilk hatada dur:

   ```sh
   for suite in test_postgres_demo.py test_postgres_management.py test_demo_examples_postgres.py test_details.py test_demo_expiry.py; do
     V2_RUN_PG_TESTS=1 PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p "$suite" -v || exit 1
   done
   ```

   Bu paketler gerçek DB transaction/rollback/eşzamanlılık/idempotency, bağımsız uygulama süreçlerinden yeniden okuma, tam API management ve seed korumasını kapsar. DB yazan testler yalnız `v2_demo_test_*` şemalarını yönetir; mevcut kullanıcı şemasını silme. Aynı V2 test sunucusunda kullanıcı akışını tarayıcıdan da denemek gerekirse yalnız yeni, benzersiz sentetik test hesabı kullan; önceden var olan kayıtları değiştirme.
5. Beyaz/Gece/Sistem ve 320/390/768/1440 px genişliklerde Dashboard → filtreli router/abone/alarm listesi → detay → ilişkili abone → geri akışını kontrol et. Arama/filtre sıfırlama, uyarı kartları, CREATE/paket/durum/yenileme onay-iptal-hata-başarı, işlem/olay diyaloğu, MiB/süre, Veri yok/Bilinmiyor ve demo etiketlerini gözle doğrula. Tab/Shift+Tab/Enter/Escape, açıcıya odak dönüşü ve tablo kaydırması için ekran görüntüsü/sonuç kaydet. Yeni test hesabını mevcut kullanıcı verisine dokunmadan açıkça ayır.
6. Yalnız bu adımlara ait yeni sonuçları bu matrise ekle. HTTP, DB kalıcılığı ve görsel akışlar geçmeden BLOCKED kararını kaldırma; üretim kimliği/operasyonel güvenlik incelemesi ayrıca gerekir. Bu plan üretim dağıtımı veya servis restartı içermez.

## Aşama 8 — MikAjanı V2 kabul kapsamı — 2026-10-28

Aşama 8'in yerel kod ve soketsiz sözleşme kontrolleri geçti. Genel gerçek entegrasyon/üretim kabul kararı **BLOCKED** kalır; bu paket üretim yayını yetkisi vermez.

| Kriter | Sonuç / kanıt |
| --- | --- |
| Mevcut router/WAN/PPPoE sentetik kaynaklarının salt okunur projeksiyonu | PASS — kayıtlı kaynak zamanları korunur; PPPoE abone bazında; IPsec ölçümü yoksa Bilinmiyor |
| OPEN, UPDATED, RECOVERING, RESOLVED ve tekrar okumada tek olay | PASS — deterministik kimlik/replay; kanıt değişiminde güncelleme; 60 saniye aralıklı iki iyi gözlemle çözülme |
| P1–P4, neden/kanıt/router/öneri/güven/zaman | PASS — tipli bulgu sözleşmesi ve inceleme dialog'u; gelecekte/çelişkili/gerçek veri reddi |
| Tek router / ortak erişim ayrımı | PASS — 120 saniye içinde en az iki router koşulu; ortak neden düşük güvenli adaydır, kesin teşhis değildir |
| Veri güncelliği ve bilinmeyen kaynak | PASS — 15 dakika eşiği, domain bazında UNKNOWN, kaynak hatasında 503; sağlıklı varsayım veya sessiz fixture fallback'i yok |
| API kayıt, yetki ve salt okunur sınır | PASS — 7 GET ucu, merkezi oturum bağımlılığı, oturumsuz erişim kontrolü, OpenAPI Analysis yanıt sözleşmesi; mutasyon/AI client yok |
| Yedi sentetik senaryo | PASS — WAN/IPsec/router/PPPoE/merkezi erişim/iyileşme/belirsiz veri; ayrı sabit senaryo saati; kayıtlı kaynak değişmez |
| Frontend filtre/gezinme/sentetik sınırı | PASS — hedefli frontend test dosyası ve TypeScript/Vite build; tema/mobil düzen kodda korunur |
| Gerçek DB, HTTP/ASGI, tarayıcı/mobil görsel kabul | BLOCKED — mevcut ortam engelleri yeniden denenmedi; soketsiz testler bunların yerine PASS sayılmaz |
| Canlı router/RADIUS/AI/üretim işlemleri | Kapsam dışı — bağlantı/işlem yok; dağıtım, migration ve restart yapılmadı |

Backend kanıtı: 11 hedefli `test_mikajani` testi ve devam görevindeki ek OpenAPI testi (toplam 12). Frontend kanıtı: `frontend/tests/mikajani.test.mjs`, TypeScript/Vite build. Kaynak geçmişi değişmedikçe olay kimliği/geçmişi tekrar üretilebilir; kaynakta olmayan eski gözlemler veya ayrı bir MikAjanı kalıcı olay arşivi bu fazda sunulmaz.

## Aşama 9 — gerçek yerel demo kabulü — 2026-10-28, temel `5615d6b`

**Karar: BLOCKED.** Bu çalıştırmada ürün kaynaklı FAIL kanıtlanmadı; altyapı engelleri nedeniyle gerçek uçtan uca kabul tamamlanamadı. Önceki birim/sözleşme PASS sonuçları gerçek HTTP, PostgreSQL veya tarayıcı kabulü olarak devralınmadı.

| Kabul adımı | Sonuç | Bu görevdeki kanıt |
| --- | --- | --- |
| İzole DB hedefi | PASS (yalnız yapılandırma) | Mevcut adaptör kontrolü: loopback 55432, mikrotik_manager_v2, v2_local, v2_demo |
| PostgreSQL bağlantısı, demo şeması ve sentetik veriler | BLOCKED | Süre sınırlı tek bağlantı OperationalError / Connection unavailable; şema-marker ve kayıt sayımı sorgularına ulaşılamadı |
| FastAPI gerçek HTTP erişimi | BLOCKED | Uvicorn startup complete mesajından sonra curl ile loopback 8000 erişimi başarısız: curl 7 / HTTP 000; süreç bu görevin sonunda durduruldu |
| HTTP giriş, oturum/yetki, Dashboard ve detaylar | BLOCKED | API HTTP önkoşulu sağlanmadı; uygulama yanıtları alınamadı |
| PPPoE toplu uzatma, idempotency ve audit | BLOCKED | Gerçek DB/HTTP transaction akışı çalışmadı; mevcut abone değiştirilmedi |
| PPPoE yetki reddi ve kısmi başarısızlık | BLOCKED | Gerçek HTTP yanıtı alınamadı; tarihsel soketsiz testler bu kabulün yerine sayılmadı |
| Raporlar ve alarmlar | BLOCKED | Gerçek kayıt/HTTP okumasına ulaşılamadı |
| MikAjanı 7 senaryo, geçmiş ve salt okunur API sınırı | BLOCKED | Gerçek HTTP üzerinden doğrulanamadı; önceki Aşama 8 testleri yeniden çalıştırılmadı |
| Frontend başlatma | BLOCKED | Vite tek denemede listen EPERM: 127.0.0.1:5173 |
| Tarayıcı kritik akışları / mobil / temalar | BLOCKED | UI sunucusu açılamadı; yerel tarayıcı ve Playwright/Puppeteer yok; kurulum denenmedi |
| Veri ve üretim izolasyonu | Korundu | Yeni özellik, migration, init/seed, veri yazma/silme, üretim erişimi veya servis restartı yapılmadı |

Kabul sırasında yalnız mevcut V2 hedefi okuma amacıyla denendi; genel/system PostgreSQL veya farklı DB/port aranmadı. `--prepare-demo`/dev-db hazırlığı migration içerdiğinden çalıştırılmadı. Başlangıç öncesine denk gelebilen ilk HTTP isteğinin ardından yalnız bir startup-sonrası kontrol yapıldı; başarısız altyapı döngüsü, ASGI/httpx araştırması veya güvenlik gevşetme uygulanmadı. Ürün kodu değişmediği için geçmiş başarılı testler/build tekrar edilmedi. Gerekli sonraki koşul: izinli normal yerel ortamda mevcut V2 DB ve loopback HTTP erişimi; ardından yukarıdaki gerçek kabul adımları tamamlanmalıdır.

## Aşama 9 — yerel DB onarımı teslimi — 2026-10-28

**Gerçek DB/HTTP kabulü BLOCKED kalır.** Kullanıcının gerçek tarayıcısında UI/login çalışıyor; DB kullanan merkezlerin hata vermesi, API/UI başlangıcı ile ayrı PostgreSQL başlangıcının ayrılmasından kaynaklanabilir. Normal dev.sh'nin DB başlatmadığı ve bu ortamda repo kümesinin çalışmadığı gözlendi; WSL'deki DB/auth/şema durumu bağlantı kurulamadığı için kesinleştirilemedi.

| Kontrol | Sonuç |
| --- | --- |
| İzinli bağlantı hedefi ve repo küme durumu | Hedef doğrulandı; pg_ctl no server running; tek psycopg bağlantısı OperationalError ile engelli |
| Veri koruyan onarım yolu | Hazır: repair-demo.sh; yalnız repo sahibi küme, eksik DB/şema/örnekler; mevcut kayıt/history korunur |
| Rol/şema güvenliği | Her privilege ayrı denetlenir; yanlış küme/marker/rol/symlink reddi; otomatik GRANT/parola reseti/drop yok |
| Gerçek DB bağlantısı, marker, yetki ve seed | BLOCKED — normal WSL komutunun sonucuyla doğrulanacak |
| Dashboard/router/abone/MikAjanı ortak kaynak HTTP kabulü | BLOCKED — yardımcı gerçek HTTP ile aynı kimlik/atama/toplam/persistence ve 7 senaryoyu denetlemeye hazır |
| PPPoE oluşturma, toplu uzatma, idempotency, audit, kısmi hata | BLOCKED — --check-writes iki yeni PAUSED demo hesapla doğrular, eski aboneler değişmez; bu ortamda çalıştırılmadı |
| Onarım güvenlik testleri | PASS — 7 hedefli soketsiz test; shell syntax, --help, diff kontrolü |

Normal WSL terminalinde mevcut V2 dev.sh oturumu açıkken tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./repair-demo.sh --check-writes
```

Komutun yazma doğrulaması her çalıştırmada iki yeni, benzersiz sentetik kabul hesabını kalıcı bırakır; kimlikleri çıktıda gösterilir. Bayrağı çıkarmak yalnız onarım ve HTTP okuma doğrulamasını yapar. Yalnız bu açık bakım akışı gerekli yerel demo şemasını hazırlayabilir; üretim migration'ı veya uygulama başlangıcında otomatik migration yoktur. Yardımcının DB PASS / HTTP PASS / PPPoE PASS çıktıları alınmadan bu kabul matrisi PASS'e çevrilmez.

## Aşama 9 — son PPPoE kabulü, çalışan WSL ortamı — 2026-10-28

Kullanıcının WSL doğrulaması: PostgreSQL/API/UI çalışıyor; 4 router, 9 sentetik abone, 7 MikAjanı bulgusu. Codex'teki tek DB/HTTP denemeleri hâlâ engelli; bu iki ortamın sonuçları karıştırılmaz.

| Kapsam | Sonuç / kanıt |
| --- | --- |
| WSL veritabanı ve mevcut veri görünümü | PASS — kullanıcı bildirimi; bağımsız Codex DB kontrolü BLOCKED |
| Codex gerçek HTTP / DB PPPoE son kabulü | BLOCKED — OperationalError ve loopback HTTP erişim engeli; tekrar döngüsü yok |
| Oluşturma / paket-fiyat / ACTIVE–PAUSED / 7–15–30 gün / özel tarih | WSL komutu hazır; gerçek çalıştırma sonucu henüz yok, BLOCKED |
| Toplu uzatma / önizlemede yazmama / onay-yetki / idempotency / audit / kısmi hata | WSL komutu hazır; gerçek çalıştırma sonucu henüz yok, BLOCKED |
| Mevcut dokuz abonenin korunması | Çalıştırıcı bütün başlangıç kayıt/audit özetlerini karşılaştırır; yalnız iki yeni test kimliği yazma hedefi olabilir |
| Liste/detay/Dashboard DB-HTTP uyumu, uyarı ve günlük rapor projeksiyonları | WSL komutu gerçek HTTP kayıtlarıyla denetler; bu ortamda gerçek kabul BLOCKED |
| Tarayıcıda görünen önizleme/onay ve otomatik ekran yenilenmesi | BLOCKED — API/DB/projeksiyon testinin yerine geçirilmez; ayrı tarayıcı kanıtı gerekir |
| Kabul çalıştırıcısı güvenlik/regresyon testleri | PASS — 5 soketsiz test; gerçek entegrasyon olarak sayılmaz |

Normal WSL terminalinde V2 dev.sh oturumu çalışırken **onarım veya migration yapmadan**:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./accept-demo.sh
```

Komut her çalıştırmada iki yeni benzersiz pasif sentetik test abonesi bırakır; eski dokuz ve sonradan eklenmiş diğer kayıtlar değişmez. Gerçek API/DB alt kontrol sayısı başarı çıktısında, test kimlikleri ve mevcut kayıt koruma sonucu `.local/acceptance/<run-id>.json` raporunda bulunur. Bu ortamda tamamlanan gerçek PPPoE uçtan uca senaryo sayısı 0'dır. WSL komutunun sonucu alınmadan bu matris toplu PASS'e çevrilmez. Frontend hesapları gerçek HTTP verileriyle kontrol edilse de tarayıcı davranışı ayrıca doğrulanmalıdır.

## Aşama 9 — HTTP erişim engeli: hazır olma düzeltmesi — 2026-10-28

Kullanıcı WSL'de DB PASS, HTTP BLOCKED bildirdi. Port/adresler kodda aynıdır: API/kabul/Vite proxy `127.0.0.1:8000`. Önceki dev.sh hazır olmadan başarı duyuruyor, çocuklardan biri kapanınca diğerini kapatıyor ve logları siliyordu; kesin WSL kapanış nedeni eski log olmadan doğrulanamadı.

| Kontrol | Sonuç |
| --- | --- |
| API hazır sinyali / DB sağlığı ayrımı | PASS (sözleşme testi): /api/ready DB erişmez; /api/health ayrı DB kontrolüdür |
| accept-demo.sh yazma öncesi HTTP readiness | PASS (soketsiz): API hazır değilse baseline/DB/yazma başlamaz; anlaşılır hata ve tek komut önerilir |
| Yerel API başlatma ve süreç sahipliği | PASS (soketsiz): hazır mevcut API korunur, sadece boş portta yeni repo API'si açılır; yalnız kendi çocuk süreci kapatılır; yanlış servis/izin/timeout durdurur |
| Startup logları / dev.sh banner | Düzeltildi: hazır sinyalinden sonra banner, hata ve log konumu açık, loglar korunur |
| Hedefli testler | PASS: 10 readiness/yaşam döngüsü + 5 kabul çalıştırıcısı; shell syntax/--help/diff |
| Codex gerçek HTTP / PPPoE kabulü | BLOCKED: tek komut soket izin/sandbox engelinde durdu; tekrar, DB okuma veya abone yazması yapılmadı |
| Dokuz mevcut abone ve audit | Bu görevde değişmedi; gerçek kabul yazmaları yalnız yeni test kimlikleriyle sınırlıdır |

Normal WSL için **tek komut**:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./dev.sh --accept-demo
```

Komut Vite/şema/seed/migration başlatmaz. Gerekiyorsa sadece geçici yerel V2 API açar; kabul sonunda bu kendi çocuğunu kapatır. Hazır bir mevcut V2 API'sine dokunmaz. Eski API `/api/ready` sağlamıyorsa ya da port başka servise aitse durur; otomatik restart/kill yapılmaz. Gerçek HTTP ve yeni abonelerle PPPoE kontrol çıktısı alınmadan bu bölüm API/PPPoE PASS'e çevrilmez. Tarayıcı onay/refresh kabulü ayrı kapsam olarak BLOCKED kalır.


## Aşama 10 — detay merkezleri ve tarayıcı kabulü — 2026-10-28

| Kapsam | Sonuç / kanıt |
| --- | --- |
| Aşama 9 gerçek API/PostgreSQL | PASS — `.local/acceptance/db1f72cc-c538-4a6d-b620-87371d4c89b8.json`: api_db PASS, 110 kontrol, 9 başlangıç abonesi korundu |
| Router detay kimlik/model/RouterOS, ilişki özeti, WAN/IPsec/güncellik | Tamamlandı — mevcut kaynaklar ve MikAjanı; kaynak yoksa Bilinmiyor; eski aggregate ayrı |
| Trafik/arayıüz/bağlantı kanıtı sınırı | PASS (hedefli render/yardımcı testler) — trafik/oturum uydurma yok; gözlem ve canlı durum ayrıdır |
| Abone detay kimlik/kaynak/paket/ücret/durum/bitiş/uyarı/audit | Tamamlandı — mevcut rapor/geçmiş korunur, audit kimliği ve ilgili router bağlantıları açık |
| Paket/durum/7–15–30 gün/özel tarih ve toplu yönlendirme | Aynı QuickActions/API kullanılır; ikinci mutasyon altyapısı yok; onay/yetki/idempotency/audit mevcut backend'de |
| Modal ve URL bağlamının loading/error sırasında korunması | PASS (hedefli testler) — dialog aynı snapshot ile kalır; arama/router/paket bağlamı korunur; eksik kaynakta yazma kapalı |
| Hedefli frontend / derleme | PASS — 5 test dosyası (8 yeni detailCenter testi dahil), TypeScript/Vite build, JS/shell syntax ve diff |
| Gerçek tarayıcı tıklama/odak/otomatik yenileme/mobil görünüm | BLOCKED — tek readiness denemesi sandbox loopback engeline takıldı; veri veya servis değiştirilmedi |

Çalışan V2 UI/API ile normal WSL terminalinde tek tarayıcı kabul komutu:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./browser-accept-demo.sh
```

İlk kullanım yalnız `.local/browser-tools` içine test aracı/Chromium indirir; uygulama bağımlılığı/sistem paketi/servis/şema değiştirmez. Ağ/Chromium/işletim sistemi bağımlılık engeli BLOCKED kalır. Komut iki yeni benzersiz pasif sentetik test abonesi oluşturur; UI üzerinden yalnız kendi yeni kimliklerinde çalışır, başlangıçtaki bütün aboneleri/audit'i koruma karşılaştırmasına alır. Önizleme iptali, onay/replay, gerçek detay/liste/uyarı/Dashboard/rapor güncellemesi, filtreli geri dönüş ve 320/390 px kontrolleri hazırdır. Gerçek sonuç ve görüntüler `.local/browser-acceptance/<run-id>/` altındadır; betiğin varlığı veya statik render PASS'i tarayıcı PASS sayılmaz. Üretim, gerçek cihaz/RADIUS ve deploy/migration/restart kapsam dışı kalır.

## Aşama 10 — ABSENT sonrası ortak API başlatma düzeltmesi — 2026-10-28

**Kök neden:** Aşama 9 geçici API'si kabul sonunda kapanır. Eski tarayıcı wrapper'ı aynı API yöneticisini kullanmadan hazır bir API bekliyordu; ABSENT bu varsayımı açığa çıkardı.

| Kapsam | Sonuç |
| --- | --- |
| Aşama 9 ManagedAPI/readiness yeniden kullanımı | Tamamlandı — demo_api_runner --browser, aynı sınıf ve sahip olunan çocuk cleanup'ı; ikinci başlatma altyapısı yok |
| Hazır mevcut API korunması / yalnız kendi geçici API'si | Mevcut yaşam döngüsü korunur; yanlış servis/izin engelinde worker çalışmaz, restart/kill yok |
| Browser dispatch ve hata/cleanup | PASS — 5 yeni soketsiz hedefli test; Aşama 9 varsayılan dispatch de korunur |
| Shell/browser syntax | PASS |
| Gerçek tarayıcı, detaylar, QuickActions/audit/otomatik yenileme | BLOCKED — tek Codex denemesi ortak readiness'in sandbox izin engelinde durdu; HTTP/projeksiyon sonuçları browser PASS sayılmadı |
| Eski 9 abone/audit | Bu görevde veri erişimi/yazması yok; browser worker yalnız yeni test kimliklerinde çalışacak şekilde korunur |

Normal WSL terminalinde **UI çalışırken**, API kapalı olsa da tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./browser-accept-demo.sh
```

Komut hazır API'yi kullanır veya ortak yöneticiyle geçici V2 API açar. Yalnız kendi başlattığı API temizlenir; mevcut API/UI/DB'ye restart uygulanmaz. UI 5173 kapalıysa ayrı açık hata ile BLOCKED kalır. Gerçek browser result.json/görüntüleri alınmadan tarayıcı kabulü PASS'e çevrilmez; geçmiş Aşama 9 110 HTTP/PostgreSQL PASS kanıtı ayrı kalır.

## Aşama 10 — tek komutta API + UI hazırlığı tamamlandı — 2026-10-28

Önceki WSL API READY / UI erişilemiyor çıktısının nedeni UI'nin önceden açık varsayılmasıydı. Güncel akış bu varsayımı kaldırır.

| Kapsam | Sonuç / kanıt |
| --- | --- |
| API ve UI aynı sahiplik/cleanup/readiness altyapısı | Tamamlandı — ManagedUI mevcut ManagedAPI uygulamasını paylaşır; hazır süreçler korunur |
| Vite komutu / yapılandırması | Tek giriş: dev.sh --ui-only; normal dev ve browser aynı komutu çağırır; mevcut Vite config değişmedi |
| DB gate | Salt okunur data_directory/marker/yetki/kaynak ve API DB health; DB engelinde UI/araç/test yazması başlamaz; repair/seed/migration yok |
| Hedefli testler | PASS — 6 ManagedUI + 6 dispatch + 10 API/readiness = 22; syntax/compile/diff geçti |
| Codex gerçek API/UI/DB/browser | BLOCKED — tek API probe sandbox izninde durdu; sonraki adımlar çalışmadı, tekrar yok |
| WSL geçmiş kabul | API READY kullanıcı çıktısı ve 110 HTTP/DB PASS/9 abone koruma JSON'u tarihsel kapsamıyla geçerli; browser PASS değildir |
| Demo veri/audit korunması | Bu görevde gerçek veri erişimi/yazması yok; browser yalnız yeni iki test hesabında çalışır, başlangıç kayıtlarını karşılaştırır |

Normal WSL terminalinde **ayrı API/UI başlatmadan** tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && ./browser-accept-demo.sh
```

Sıra: API READY → DB READY (read-only) → UI READY → gerçek tarayıcı. Hazır mevcut servisler kapanmaz; yalnız komutun kendi başlattığı süreçler temizlenir. UI/DB/browser önkoşul hatası veya araç/Chromium yokluğu BLOCKED kalır; HTTP/projeksiyon sonucu browser PASS diye raporlanmaz. Gerçek `.local/browser-acceptance/<run-id>/result.json` ve ekran görüntüleri alınmadan tarayıcı kabulü tamamlanmış sayılmaz. Üretim servisleri, gerçek cihazlar/RADIUS/veriler ve migration kapsam dışıdır.


## Aşama 22 — kapalı CEBECI erişim sözleşmesi — 2026-10-29

| Kapsam | Sonuç / kanıt |
| --- | --- |
| Kimlik/model/sürüm/adres/kaynak, yetki/TLS/sertifika/minimum yetki, stale/unknown ve V1 izolasyonu | PASS — fail-closed offline sözleşme; eksik/olumsuz kanıt NO_GO |
| Yazma/credential/canlı SA/adapter erişimi | PASS — dar print allowlist, alan reddi, adapter'a dokunmadan backend 403; execution endpoint'i yok |
| Hedefli backend/frontend | PASS — 37 backend (17 yeni + 20 etkilenen); 26 frontend (4 yeni + 22 systemCenter) benzersiz test |
| TypeScript/Vite build, browser JS syntax | PASS |
| Gerçek browser 320/390/1440 | BLOCKED — tek Aşama 22 çağrısı loopback sandbox engelinde durdu; browser PASS kanıtı yok |
| Veri ve canlı erişim | Ağ/DB yazması yok; 14 abone/audit korunur; NOT CONNECTED / APPROVAL REQUIRED / SECURITY NOT VERIFIED |

Ayrı Aşama 22 salt okunur senaryosu önceki kabul paketlerini çalıştırmaz; kapalı
bayrakları, kanıt/STOP görünümünü, üç genişliği ve eski kayıt baseline eşitliğini
kontrol eder; hesap/fixture oluşturmaz. Normal WSL terminalinde tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_SECURITY_ONLY=1 ./browser-accept-demo.sh
```

Gerçek pilot onayı/cihaz bağlantısı kapsam dışıdır. Güvenlik koşulları ve eksik
kanıtlar için [pilot sözleşmesi](CEBECI_TOWERS_PILOT.md) esas alınır.

## Aşama 23 — ön koşul matrisi — 2026-10-29

- Aşama 22: kullanıcı normal WSL için 13/13 BROWSER PASS bildirdi; tarihsel UI kabulü, gerçek pilot güvenliği kanıtı değildir.
- PASS: 7 yeni backend + aynı hedefli yüklemede 17 etkilenen Stage 22 testi; 3 yeni frontend matris + 4 etkilenen güvenlik render kontrolü; TypeScript/Vite build, JS syntax ve diff kontrolü.
- NO_GO: dokuz kanıt varsayılan MISSING; receipt validasyonunda eksik/duplicate/uyuşmazlık/stale/yanlış rol/paket değişimi ve identity/TLS/policy/V1 kapıları kapalıdır. Teknik uygunluk/operatör onayı/yürütme ayrı; otomatik GO ve execution yok.
- Aşama 23 Browser BLOCKED: tek yeni salt okunur senaryo çağrısı ilk loopback sandbox engelinde durdu; eski browser kabulü çalıştırılmadı. 320/390/1440px gerçek browser sonucu henüz yok. Mevcut abone/audit verisine yazılmadı.
- Normal ofis WSL tek komut: `cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_PREREQUISITES_ONLY=1 ./browser-accept-demo.sh`.

## Aşama 24 — manuel güvenlik bulguları — 2026-10-29

- Aşama 23 için kullanıcı 10/10 BROWSER PASS bildirdi; tarihsel yerel UI kabulü, gerçek cihaz güvenliği değil.
- PASS: 9 yeni backend testi, 5 yeni frontend + 4 doğrudan etkilenen güvenlik paneli render kontrolü, TypeScript/Vite build, browser JS syntax/diff.
- Manuel rapor OPERATOR_REPORTED_MANUAL / MANUAL_OBSERVATION; zaman null/UNKNOWN. Dokuz başlıkta manuel eşleşme/risk ayrı, teknik kanıt MISSING; TLS yok ve mevcut write/test hesap uygun değil. Kısmi firewall/policy güvenlik garantisi değil. A/B onaysız; API/8728 mevcut TLS kontratında kapalı, ayrı inceleme/onay gerekir.
- Aşama 24 Browser BLOCKED: tek yeni salt okunur kabul çağrısı ilk loopback sandbox engelinde durdu. Önceki browser senaryoları çalıştırılmadı; 320/390/1440px sonucu bu ortamda doğrulanmadı.
- Gerçek router/V1 erişimi veya veri yazması yok; mevcut demo aboneleri/audit korunur. Plan doküman, NO_GO / NOT CONNECTED / APPROVAL REQUIRED; yeni execution/credential/onay endpoint'i yok.
- Normal ofis WSL tek komut: `cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_MANUAL_ONLY=1 ./browser-accept-demo.sh`.
