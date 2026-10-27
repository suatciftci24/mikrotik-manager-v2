# V2 yerel demo kabul ve dağıtıma hazırlık raporu

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
