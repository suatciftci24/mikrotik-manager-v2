# MikroTik Manager V2 — İlerleme

Son güncelleme: 2026-10-27. Proje yolu: `/home/suatpc/Codex-Projects/mikrotik-manager-v2`.

## Kod ve Git geçmişinden doğrulanan durum

- Branch: `main`. Bu belge görevinin başlangıcında çalışma ağacı temizdi.
- Detay merkezlerinin temel commit'i: `fa1c03b` — ortak modül altyapısı ve envanter detay merkezleri. Öncesindeki `7512239`, GitHub deposunu V2 README korunarak birleştiriyor.
- Ortak frontend altyapısı: `useResource`, `useDetailNavigation`, `PageHeading`, `ResourceState`, `DetailSection`, `Facts` ve `MissingData` mevcut.
- Router ve abone listelerinden detay merkezlerine erişim mevcut; abone bitiş tarihi düzenleme/yenileme akışı yalnız V2 yerel PostgreSQL demo şemasında kalıcı olarak saklanıyor. Liste filtreleri korunuyor; URL fragmenti detay kimliğini taşıyor. Kaynak kodunda geri dönüş, yükleniyor, hata, tekrar deneme ve boş veri durumları bulunuyor.
- `/api/v1/routers/{item_id}` ve `/api/v1/subscribers/{item_id}` merkezi demo oturum kontrolünü ve Pydantic yanıt sözleşmelerini kullanıyor; bulunamayan kayıtlar 404 döndürüyor.
- Veriler mevcut sentetik demo envanterinden geliyor. Router'a atanmış sentetik abone listesi, toplam sayaç ve aktif oturumlardan ayrı açıklanıyor. LOCAL/RADIUS yetkili kaynak bilgisi korunuyor.
- Router arayüzleri, trafik ve canlı oturum için bağlı veri kaynağı bulunmuyor; abone işlem geçmişi yalnız sentetik demo tarih değişikliklerini içeriyor ve ayrı V2 geliştirme şemasında saklanıyor; detay ekranları bunu açıkça belirtiyor. Abonelik bitişi/kalan gün takibi aşağıdaki yeni paketle sentetik tarihler üzerinden sağlanıyor; canlı entegrasyon değildir.
- README yerel demo çalışma biçimini ve test komutlarını belgeliyor. `backend/tests/test_details.py` hedefli API testlerini içeriyor. Test dosyasının varlığı, bu belge görevinde çalıştırıldığı anlamına gelmez.

## Önceki belge görevi — `c5b263c`

- Mevcut kök `AGENTS.md` okundu; mevcut proje, mimari ve V1 izolasyon talimatları korunarak 12 maddelik kalıcı çalışma sözleşmesi ve görev başlangıcı/sonu okuma-güncelleme talimatı eklendi.
- Önceden ilerleme belgesi bulunmadığı için bu dosya oluşturuldu.
- Ürün kodu değiştirilmedi; canlı sistem işlemi yapılmadı.
- Kontrol kapsamı: belge farkları, mevcut talimatların korunması ve yalnız `AGENTS.md` ile `docs/PROGRESS.md` dosyalarının commit kapsamına alınması. Ürün testi veya derleme bu belge görevi için çalıştırılmadı.
- Bu belge değişikliklerinin commit kimliği Git geçmişinden görülebilir; belge kendi commit kimliğini içermez.

## `fa1c03b` geliştirmesinde doğrulanan kontrol sonuçları

Aşağıdaki sonuçlar aynı konuşmadaki önceki geliştirme görevinin gerçek araç çıktılarından kaydedildi; bu belge güncellemesinde ürün testleri tekrarlanmadı.

- Frontend: `npm --prefix frontend run build` başarılı; TypeScript ve Vite derlemesi geçti.
- API: `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v` ile 4 test geçti. Oturumsuz erişimin reddi, OpenAPI yanıt sözleşmeleri, sentetik router–abone eşleşmesi, abone kaynak/son görülme bilgilerinin korunması ve bilinmeyen kayıtların 404 sonucu doğrulandı. Sağlık yanıtında veritabanı ve cihaz adaptörü bağlantıları kapalıydı.
- Yerel Chromium kontrolleri: detay içerikleri, sentetik sayaç ile kısmi atama listesinin ayrımı, filtre/odak korunması, tarayıcı geri/ileri gezinmesi, detay URL'siyle yeniden yükleme, listeye dönüş, 404 ve yükleniyor/hata/tekrar deneme/boş veri durumları geçti.
- Mobil: 390 px görünüm ve 320 px dar ekran kontrol edildi. Bulunan 360 px body alt sınırı 320 px olarak düzeltildi; son kontrolde 320 px genişlikte taşan öğe kalmadı. Aynı modül menüsüyle detaydan listeye dönüş geçti; router ve abone mobil ekran görüntüleri incelendi.
- Tarayıcı kontrol araçları ve ekran görüntüleri geçici `/tmp/v2-ui-check` dizininde kullanıldı; depoya kalıcı bir tarayıcı test paketi eklenmedi. Bu sonuçlar canlı veri veya cihaz entegrasyonu doğrulaması değildir.

## Son belge kontrolü ve gönderim kapsamı

- `AGENTS.md` ve bu ilerleme belgesi görev başlangıcında okundu. 12 altın kural ve görev başında belge okuma/görev sonunda ilerleme güncelleme talimatı eksiksiz bulundu; mevcut talimatlar korunarak `AGENTS.md` değiştirilmedi.
- `fa1c03b` içeriği Git geçmişinden incelendi; önceki geliştirmede alınan gerçek kontrol sonuçları yukarıya eklendi. Bu görevde yalnız belge kontrolleri yapıldı; ürün geliştirmesi veya canlı sistem işlemi yapılmadı.
- Bu güncellemenin commit kapsamı yalnız `docs/PROGRESS.md` dosyasıdır. Ardından `main` branch'i `origin` üzerindeki `suatciftci24/mikrotik-manager-v2` deposuna normal push ile gönderilecek; force push kullanılmayacak. Gönderim sonucu henüz gerçekleşmeden başarılı sayılmaz; kesin sonuç Git push çıktısından doğrulanır.

## Yerel görsel inceleme hazırlığı — 2026-10-27

- Başlangıçta `AGENTS.md` ve bu belge okundu; branch `main`, HEAD `9fe15f8`, çalışma ağacı temizdi. Önceki normal push çıktısı `9fe15f8` commit'inin `origin/main` üzerine gönderildiğini doğruladı.
- Belgede başlanması açıkça belirlenmiş bir geliştirme bulunmadığından yeni özellik veya ürün kodu değişikliği yapılmadı.
- Mevcut `./dev.sh` ile yalnız `127.0.0.1` üzerinde V2 UI ve API başlatıldı. Sandbox'ın port açma kısıtı nedeniyle aynı komut sandbox dışında çalıştırıldı; uygulama izolasyonu değiştirilmedi.
- Panel: `http://127.0.0.1:5173/`. Yerel sentetik giriş: `demo` / `demo-only`. Router ve Abone Merkezi listelerindeki adlardan detaylara erişilebilir.
- Hedefli erişim kontrolü geçti: UI HTML yanıtı, UI proxy üzerinden API sağlık yanıtı, sentetik giriş/çıkış, router ve abone listeleri ile birer detay yanıtı doğrulandı. Sağlık yanıtında veritabanı ve cihaz adaptörleri bağlı değildi. Önceden geçen derleme ve kapsamlı testler tekrarlanmadı; bu görevde yeni görsel tarayıcı testi yapılmadı.
- Yerel servisler bu görevin sonunda inceleme için çalışır bırakıldı; bu ifade gelecekteki oturumlarda hâlâ çalıştıkları garantisi değildir. Gerçek engel bulunmadı. V1, VDS, router, RADIUS ve gerçek abone verilerine müdahale edilmedi.
- Sıradaki somut adım: kullanıcının panelde Router ve Abone Detay Merkezlerini görsel inceleyip sonraki geliştirme kapsamını belirtmesi.

## Beyaz / Gece / Sistem tema seçimi — 2026-10-27

- Görev başında `AGENTS.md` ve bu belge okundu; başlangıç çalışma ağacı temizdi. Mevcut yerel V2 demo servisleri kullanıldı; canlı sistemlere müdahale edilmedi.
- Üst çubuğa ve giriş ekranına ortak, klavyeyle kullanılabilen tema seçici eklendi. Düğmelerin erişilebilir adları ve `aria-pressed` seçili durumları var; mobilde simgelerle kullanılabiliyor.
- Ortak semantik tema paleti `frontend/src/theme.css` içinde tanımlandı. Mevcut yerleşim korunarak sayfalar, detaylar, tablolar, formlar, pencereler, SVG grafikler ve yükleniyor/boş/hata yüzeylerinin renkleri ortak değişkenlere taşındı. Paket veya backend değişikliği yapılmadı.
- `frontend/public/theme.js`, HTML head içinde senkron çalışarak React ve sayfa gövdesinden önce kayıtlı temayı uygular. Tercih `mikrotik-manager-v2.theme` anahtarında saklanır; ilk kullanımda Sistem seçilidir. Sistem modunda işletim sistemi değişimi izlenir; açık tercih sistem değişiminden etkilenmez. Sekmeler arası eşitleme ve depolama engellendiğinde bellek içi seçim desteklenir.
- Hedefli yerel Chromium kontrollerinde varsayılan sistem tercihi, Beyaz/Gece/Sistem geçişleri, işletim sistemi değişimi, yeniden yükleme/yeniden açma kalıcılığı ve sekmeler arası eşitleme doğrulandı. Başlangıç betiğinin gövde/React oluşmadan önce kayıtlı Gece tercihini uyguladığı ayrı kontrolle doğrulandı.
- Dashboard, Router/Abone listeleri ve detayları, diğer dört modül ve arama penceresi iki temada kontrol edildi. Yükleniyor/hata/tekrar deneme/boş veri yüzeyleri, klavye seçimi ve localStorage erişimi engelli senaryo geçti. Tema test araçları ve ekran görüntüleri yalnız geçici `/tmp/v2-ui-check` dizinindedir.
- 320 px Dashboard kontrolde bulunan mevcut kart taşması giderildi; son kontrolde her iki temada sayfa genişliği 320 px, taşan öğe sayısı sıfırdı. İki temanın Dashboard ve detay ekran görüntüleri ile mobil ekran incelendi.
- Ortak ana metin, ikincil metin, durum ve eylem renk çiftlerinin hesaplanan kontrastı her iki palette en az 4.5:1; tüm stil değişkenlerinin tanımlı olduğu kontrol edildi. Bu, tüm arayüz için kapsamlı erişilebilirlik sertifikasyonu değildir.
- Son frontend TypeScript/Vite derlemesi ve belge/kod fark kontrolü geçti; derleme çıktısında tema betiğinin modül betiğinden ve gövdeden önce bulunduğu, dosyanın çıktıya aynen kopyalandığı doğrulandı. Önceki API testleri, backend değişmediği için tekrarlanmadı.
- Sıradaki somut adım: kullanıcının yerel panelde tema görünümünü incelemesi; yeni bir özellik kapsamı belirlenmedi.

## Genel yazı okunabilirliği — 2026-10-27

- Başlangıçta `AGENTS.md` ve bu belge okundu; çalışma ağacı temiz, HEAD `5194889` idi. Önceki tema commit'i değiştirilmedi.
- Yalnız `frontend/src/styles.css` içinde küçük 7–12 px yazılar ortak rem ölçeğine taşındı: yardımcı metinler en az 12 px, küçük içerikler 13 px, menüler ve temel içerikler 14 px; form girişleri 16 px, panel başlıkları 16 px. Tema paleti ve tema seçim/kayıt kodu korunuyor.
- Daha büyük yazılar için tablo satırları, düğmeler, araç çubukları, alt bilgiler ve açılır pencere satırları esnek yüksekliğe alındı. Mobilde router özetleri ve yardımcı satırlar sarılıyor; kenar çubuğu gerektiğinde kaydırılabiliyor.
- Tek hedefli yerel Chromium kontrol kapsamı: gerçek hesaplanan yazı boyutları, masaüstü ve 390/320 px Dashboard, Router/Abone listeleri ve detayları, giriş formu ve arama penceresi. Yerleşim oturduktan sonra yatay taşma olmadığı ve tema seçiminin çalıştığı doğrulandı; kontrol geçti. 320 px Dashboard ekran görüntüsü incelendi.
- CSS değişikliği için derleme ve önceki API/tema test paketleri ayrıca çalıştırılmadı. Yeni paket, backend veya canlı sistem işlemi yok.
- Sıradaki somut adım: kullanıcının yerel panelde büyütülen yazıları görsel incelemesi.

## Abonelik bitiş tarihi ve kalan gün takibi — 2026-10-27

- Görev başında kurallar ve ilerleme kaydı okundu; branch `main`, HEAD `11b5868`, çalışma ağacı temizdi. Mevcut tema ve okunabilirlik düzeltmeleri korundu.
- Abone API liste ve detay sözleşmelerine nullable ISO takvim tarihi `expires_on` eklendi; liste yanıtı da belgelenmiş Pydantic sözleşmesi kullanıyor. Bu fazın verisi yalnız sentetik bellekte tutuluyor; veritabanı modeli veya migration değiştirilmedi.
- Demo API başlangıcındaki Türkiye gününe göre açık örnekler: -3, +5, +20, +60, 0, bilinmiyor ve +30 gün. Eksik tarihler katılım tarihinden türetilmiyor; demo yeniden başlatılınca örnek tarihler yeniden üretiliyor.
- Abone listesine bitiş tarihi, kalan gün ve ayrı bitiş durumu sütunları; detaya belirgin tarih/durum/kalan gün özeti eklendi. Bilinmeyen tarihler açıkça “Bitiş tarihi bilinmiyor” gösteriliyor.
- Süresi dolmuş, 7 gün, 30 gün, aktif ve bilinmeyen bitiş filtreleri mevcut kaynak/durum/arama ile birleşiyor; sıfırlama ve detaydan dönüşte seçim korunuyor. 30 gün filtresi 0–7 gün grubunu da kapsıyor; dolmuş/bilinmeyen kayıtları kapsamıyor.
- Hesaplama ortak frontend yardımcısında Europe/Istanbul takvim günü üzerinden yapılıyor; bitiş günü dahil (0 gün), geçmiş gün dolmuş, 0–7 / 8–30 / 30 üzeri ayrı gösteriliyor. Gün değişimi 30 saniyelik kontrol ve sekme odağı/görünürlük değişiminde güncelleniyor; saat farkı veya katılım tarihiyle tahmin yok.
- Kontroller geçti: frontend TypeScript/Vite derlemesi, `npm --prefix frontend run test:expiry` tarih sınırları/eksik-geçersiz tarih/Türkiye gece yarısı/artık gün/yıl geçişi/filtre semantiği kontrolleri ve 5 sentetik API testi.
- Yerel Chromium ile filtre sayıları/birleşimi/sıfırlama, bilinmeyen tarih, liste–detay uyumu, Beyaz/Gece/Sistem temaları ve 320 px taşmasız görünüm doğrulandı. Son gece yarısı kontrolünde yalnız gizli liste ve detay arasındaki test seçicisi daraltıldı; Türkiye gece yarısında detayın otomatik “bugün bitiyor”dan “1 gün önce doldu”ya geçtiği kontrolü geçti. Mobil bitiş özeti görüntüsü incelendi.
- Yalnız yerel V2 demo süreçleri yeni API verisi için yeniden başlatıldı. V1, VDS, router, RADIUS ve gerçek abone verilerine dokunulmadı; uzatma/değiştirme, canlı bağlantı veya deploy eklenmedi.
- Sıradaki somut adım: kullanıcının yerel panelde bitiş filtreleri ve detay özetini incelemesi; canlı entegrasyon veya abonelik düzenleme için yeni kapsam gerekir.

## LOCAL / RADIUS abone ayrımı — 2026-10-27

- Görev başında `AGENTS.md`, bu belge, domain modeli, API ve UI incelendi; branch `main`, HEAD `8b98e21`, çalışma ağacı temizdi. Mevcut kaynak rozetleri ve filtresi zaten bulunduğundan yeniden kurulmadı.
- Detay merkezine yetkili yönetim kaynağının açıklaması eklendi: LOCAL atanmış MikroTik üzerindeki yerel kullanıcı kaydı, RADIUS FreeRADIUS kullanıcı kaydıdır. Router atamasından LOCAL sonucu çıkarılmaz. Açıklamalar ve kayıtlar açıkça sentetik olarak etiketlidir.
- Salt okunur kaynak alanı nullable yapıldı: eksik/geçersiz/belirsiz değerler API projeksiyonunda null; UI'de “Bilinmiyor” gösteriliyor. Ortak kaynak yardımcısı rozet/filtre/açıklama için aynı davranışı sağlar; beklenmeyen değerler ham olarak gösterilmez veya tahmin edilmez.
- Kaynak filtresine Bilinmiyor seçeneği, erişilebilir ad ve bilinmeyen kayıt sayacı eklendi. Mevcut kaynak/durum/bitiş/arama filtreleri ve sıfırlama korunuyor. Sentetik örnek dağılımı 3 LOCAL, 3 RADIUS, 1 bilinmeyen (Eda Öz).
- Kalıcı domain `AuthoritativeSource` enum'u ve tek yetkili kaynak DB kısıtı değiştirilmedi; bilinmeyen kaynak yalnız eksik salt okunur envanter durumu, üçüncü bir yönetim kaynağı değildir. Abone oluşturma/değiştirme, kaynak devri veya canlı bağlantı eklenmedi.
- Kontroller geçti: TypeScript/Vite derlemesi, `node --test frontend/tests/source.test.mjs` ile bilinen/eksik/geçersiz/belirsiz kaynak ayrımı ve filtre/açıklama kontrolleri; 6 sentetik API testi ile sözleşme ve doğrudan etkilenen liste/detay/router ataması doğrulandı. Önceki tarih ve kapsamlı tema testleri tekrarlanmadı.
- Yerel Chromium kontrolü geçti: rozet ve sayaçlar, LOCAL/RADIUS/Bilinmiyor filtreleri ve detay anlamları, filtre birleşimleri/sıfırlama, arama, detaydan dönüşte seçim korunması, Beyaz/Gece/Sistem ve 320 px taşmasız görünüm. Gece temalı bilinmeyen kaynak detay görüntüsü incelendi.
- Yalnız yerel V2 demo süreçleri yeni sentetik örnek için güncellendi; canlı V1, VDS, router, RADIUS veya gerçek abone verisine dokunulmadı.
- Sıradaki somut adım: kullanıcının panelde kaynak filtrelerini ve detay açıklamalarını incelemesi; yeni yazma veya canlı entegrasyon kapsamı belirlenmedi.

## Demo abonelik yenileme ve bitiş tarihi düzenleme — 2026-10-27

- Görev başında kurallar, ilerleme kaydı, veri/audit modelleri ve API incelendi; branch `main`, HEAD `1335034`, çalışma ağacı temizdi. Veritabanı kalıcılığı kullanılmadığından işlem yalnız mevcut sentetik demo altyapısında geliştirildi.
- Abone detayına tarih girişi, işlem türü (yenileme/tarih düzenleme), mevcut/yeni tarih özeti ve ayrı açık onay adımı eklendi. İptal kaydetmez; boş/geçersiz/geçmiş/aynı tarihler ve ileri gitmeyen yenileme reddedilir. Türkiye'de bugün geçerli bir bitiş günüdür.
- Merkezi demo yönetici oturumu ve özel demo eylem başlığıyla korunan `POST /api/v1/subscribers/{id}/demo-expiry` eklendi. Kaynak bilinmiyorsa değişiklik kapalı; istek mevcut kaynak, tarih ve revizyonla eşleşmelidir. Gövde yalnız açıkça izin verilen alanları kabul eder.
- Kayıt, UTC zamanlı işlem geçmişi (işlemi yapan, tür, önceki/yeni tarih ve kaynak) ve tekrar-istek sonucu kilit altında tek bellek durumu olarak yayımlanır. İşlem öncesi hatada değişiklik kalmaz; eşzamanlı eski sürümler reddedilir; aynı UUID ile yeniden gönderim ikinci değişiklik/geçmiş üretmez.
- LOCAL/RADIUS kaynağı ve hesap yaşam döngüsü durumu korunur. Başarı sonrası ortak veri erişimi bildirimi listeyi, detayı ve router atama okumalarını günceller; hesaplanan bitiş durumu/kalan gün yeni tarihe yansır.
- Tarih ve geçmiş yalnız tek demo API sürecinin ortak belleğindedir: tarayıcı yenilemesinde kalır, API yeniden başlatılınca sıfırlanır. Bu sınır giriş/onay, başarı ve geçmiş alanlarında açıkça belirtilir; kalıcı işlem veya gerçek abonelik işlemi olarak sunulmaz.
- Kontroller geçti: son TypeScript/Vite derlemesi ve 15 sentetik backend testi (onay/yetki, tarih doğrulama, kaynak/okuma tutarlılığı, tekrar gönderim, eski sürüm/eşzamanlılık, yayın öncesi hata atomikliği, Türkiye gün sınırı dahil). Önceki bağımsız tarih/kaynak frontend testleri değişmediği için tekrarlanmadı.
- Yerel Chromium'da istemci doğrulaması, mevcut/yeni tarih onayı, POST göndermeyen iptal, LOCAL yenilemesi ve liste/bitiş durumu/geçmiş güncellemesi doğrulandı. Sunucunun uyguladığı fakat yanıtı kaybolan isteğin tekrarında tek geçmiş kaydı oluştu.
- RADIUS tarih düzenleme, bugün bitişi, sayfa yenilemede geçmiş, bilinmeyen kaynak engeli geçti. İşlem türü alanının erişilebilir adı netleştirilip kalan kapsam doğrulandı. Beyaz/Gece/Sistem onay penceresi 320 px'de kontrol edildi; Gece mobil görüntüsü incelendi.
- Yeni bağımlılık, kalıcı şema/migration, deploy, üretim erişimi veya RouterOS/FreeRADIUS yazması yok. Yalnız yerel V2 demo süreçleri güncel kodla başlatıldı; V1/VDS/gerçek abone verilerine dokunulmadı.
- Sıradaki somut adım: kullanıcının yerel panelde demo yenileme/onay/geçmiş akışını incelemesi; kalıcı veya canlı işlem kapsamı ayrıca belirlenmelidir.

## Demo abonelik ve işlem geçmişi kalıcılığı — 2026-10-27

- Görev başlangıcında kurallar/ilerleme kaydı okundu; branch `main`, HEAD `7fe301a`, çalışma ağacı temizdi. SQLAlchemy/psycopg ve yerel PostgreSQL 16 zaten mevcuttu; yapılandırılmış 127.0.0.1:55432 uç noktası çalışmıyordu. Yeni paket/Docker veya başka bir kalıcılık ürünü eklenmedi.
- Mevcut bellek API'sinden 7 sentetik abone ve 2 işlem olayı `.local/demo-import.json` içine alındı. Repo altında ayrı `.local/postgres-v2-demo` geliştirme kümesi hazırlandı; yalnız loopback 55432 ve V2 veritabanı `mikrotik_manager_v2` kullanıldı. Başlatma sırasında bakım erişimi yalnız bu yeni, repo sahibi geliştirme kümesinde V2 DB oluşturmak içindi; mevcut/sistem PostgreSQL servisleri değiştirilmedi.
- Mevcut veri erişimi sözleşmesi korunarak dar PostgreSQL adaptörü eklendi. Veriler `v2_demo` şemasında ayrı abone, olay ve tekrar-istek tablolarında; demo kimliği/is_demo kısıtlarıyla saklanıyor. Adaptör bağlantı kurmadan önce V2 geliştirme kullanıcı/host/port/DB hedefini doğrular; V1/harici/farklı DB hedeflerini reddeder.
- Açık sürümlü `002_demo_storage.sql` ve veri kaybı sınırı belgelenmiş `.down.sql` eklendi. `./dev.sh --prepare-demo` yalnız açık hazırlık modudur; normal UI/API başlangıcı DB'ye bağlanmaz, şema oluşturmaz veya migration çalıştırmaz. Mevcut işaretli demo şeması yeniden seed edilmez/üzerine yazılmaz.
- Eski bellek snapshot'ı transaction içinde aktarıldı; tarihler, revizyonlar ve geçmiş korundu, eski işlem UUID'leri için tekrar-istek sonuçları yeniden kuruldu. Son karşılaştırmada eski API değişmemişti ve 7 kayıt/2 olay PostgreSQL ile birebir eşleşiyordu. `.local/` Git dışında tutulur.
- Tarih güncellemesi, UTC audit olayı ve tekrar-istek sonucu tek PostgreSQL transaction'ında tamamlanır. Satır kilidi/revizyon denetimi, tutarlı detay okuması ve kalıcı idempotency korunur. DB başarısızlığı 503 döndürür; bellek fallback'i veya commit öncesi başarı yoktur. LOCAL/RADIUS ve hesap durumları korunur.
- UI onay, başarı, geçmiş ve demo açıklamaları kalıcı sentetik saklamaya uyarlandı. Tarihler/geçmiş sayfa yenilemesi ve yeni API sürecinde korunur; gerçek abone işlemi olarak gösterilmez. Eski `process-memory` API'si algılanırsa geçici yazma düğmesi kapanır; güncel API'nin sonraki normal açılışı gerekir.
- Kontroller geçti: frontend TypeScript/Vite derlemesi, shell sözdizimi/fark kontrolleri, 24 backend testi (8 gerçek geliştirme PostgreSQL entegrasyonu dahil) ve sonrasında eklenen 1 snapshot doğrulama testi. İki ayrı gerçek uygulama sürecinde kayıt/geçmiş/UUID tekrarı; DB rollback, ayrı bağlantılarda eşzamanlılık, hedef izolasyonu, eksik şemada 503/otomatik migration olmaması, seed/import ve sentetik işaret kısıtları doğrulandı. Naif audit zamanı ve tutarsız aktarım reddediliyor; audit zamanları UTC'ye normalize edilir.
- Tarayıcıda yalnız geçici test şemasını kullanan ayrı loopback test API'siyle kalıcı onay/kaydetme, yenileme sonrası liste ve bitiş durumu, sayfa yenilemesinde geçmiş, üç tema/320 px ve eski bellek API'sine yazma engeli doğrulandı. Test API'si ve yalnız kendisine ait geçici şema temizlendi; gerçek demo şeması korunuyor.
- Kullanıcının servis restartı yasağına uyuldu: çalışan eski V2 API dahi yeniden başlatılmadı. Yeni kalıcılık kodu güncel API sonraki kez açıldığında devrededir; mevcut eski API arayüzde açıkça tanınır ve kalıcı olmayan düzenleme engellenir. Canlı migration, deploy, V1/VDS/router/RADIUS veya gerçek abone verisi işlemi yapılmadı.
- Sıradaki somut adım: güncel V2 API'nin sonraki izinli yerel açılışında kalıcı demo panelini incelemek; kalıcı depo hazır ve eski veriler aktarılmıştır. Servis aktivasyonu bu görevde yapılmadı.

## Yerel kalıcılığı etkinleştirme girişimi — BLOCKED — 2026-10-27

- Görev başlangıcında kurallar/ilerleme kaydı okundu; branch `main`, HEAD `db6901c`, çalışma ağacı temizdi. Kullanıcının açık yetkisi yalnız ofis bilgisayarındaki V2 API'sini yeniden başlatmayı kapsıyor; UI veya başka servis restartı kapsam dışı.
- Salt okunur süreç/port incelemesiyle API kesin olarak belirlendi: bu repo cwd'sinde `.venv/bin/python3 .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`; inceleme anında API PID 89596, ortak `bash ./dev.sh` çalıştırıcısı PID 89586 idi. UI aynı çalıştırıcının npm/Vite alt sürecidir (inceleme anında Vite PID 89609).
- Gerçek engel: mevcut `dev.sh` sonundaki `wait -n` herhangi bir çocuk bitince tamamlanır; `EXIT` cleanup'i hem API'yi hem UI'yi kapatır. Dolayısıyla bu mevcut çalıştırma yöntemiyle API'yi sonlandırmak UI'yi de durduracaktır. Çalışan parent sürece müdahale/orphan bırakma gibi güvenli olmayan yöntemler denenmedi.
- Kullanıcının yalnız API sınırını aşmamak için hiçbir sürece sinyal gönderilmedi ve hiçbir servis yeniden başlatılmadı. Kalıcılık etkinleştirilmiş veya restart sonrası kontrol geçmiş gibi bildirilmez; mevcut API hâlâ önceki bellek sürümündedir.
- Mevcut duruma ait salt okunur doğrulama geçti: eski yerel API'nin 7 sentetik kaydı ve 2 geçmiş olayı V2 yerel PostgreSQL'deki aktarılmış kayıtlarla birebir eşleşiyor. Abone ve olay kimlikleri ayrı ayrı tekil; yinelenen kayıt yok. Yeni abonelik/test işlemi yapılmadı; temizlenecek yeni sentetik kayıt oluşturulmadı.
- Önceki derleme/test paketleri tekrarlanmadı. V1, VDS, router, RADIUS, gerçek abone verileri ve başka servisler değişmedi. Yalnız bu ilerleme belgesi güncellendi.
- Gereken tek eylem: mevcut bağlı yerel V2 UI/API çalıştırıcısının birlikte yeniden başlatılmasına açık kullanıcı izni. Böylece projenin `./dev.sh` yöntemiyle yeni kalıcı API açılıp Abone Merkezi'nde restart sonrası koruma kontrolü tamamlanabilir. Bu izin henüz yoktur.

## Yerel V2 UI/API kalıcılık etkinleştirmesi — PASS — 2026-10-27

- Görev başında `AGENTS.md`, ilerleme kaydı ve Git durumu okundu; branch `main`, HEAD `5b197f2`, çalışma ağacı temizdi. Kullanıcı önceki API-only sınırını yalnız ofis PC'deki bağlı yerel V2 UI/API ikilisini bir kez yeniden başlatacak şekilde açıkça genişletti; önceki BLOCKED engeli bu izinle giderildi.
- Salt okunur inceleme ile API'nin repo venv'inden 127.0.0.1:8000 üzerinde çalıştığı, Vite UI ile aynı `bash ./dev.sh` parent'ına bağlı olduğu yeniden doğrulandı. Başlangıçta 7 kayıt/2 olay PostgreSQL aktarımıyla eşleşiyordu.
- Kimliği doğrulanan eski V2 `dev.sh` çalıştırıcısı kendi cleanup'iyle güvenli kapatıldı ve projenin normal `./dev.sh` komutuyla UI/API ikilisi tam bir kez açıldı. PostgreSQL, sistem/üretim servisi veya başka bir servis yeniden başlatılmadı; migration/seed/hazırlık modu çalıştırılmadı.
- Gerçek panel http://127.0.0.1:5173/ üzerinden Chromium ile açılıp Abone Merkezi yenilendi. Yenilemenin Genel Bakış'a dönmesi nedeniyle kontrol Abone Merkezi yeniden seçilerek tamamlandı; ikinci servis restartı veya deneme döngüsü yapılmadı.
- Doğrulama PASS: sağlık yanıtı `demo_persistence=local-postgresql-demo`, `database_connected=true`, `device_adapters_connected=false`. Liste 7 kayıt/7 tekil ID; tüm detaylarda toplam 2 geçmiş/2 tekil olay ID'si var. Her abone alanı, tarih, revizyon, LOCAL/RADIUS/bilinmeyen kaynak ve geçmiş içeriği yeniden başlatma öncesi snapshot ile birebir eşleşiyor; yinelenen kayıt veya olay oluşmadı.
- Ayşe ve Mert detaylarında birer geçmiş olayı ekranda görüldü; kalıcı demo düzenleme düğmeleri etkin. Yeni abonelik/yenileme test işlemi yapılmadı, temizlenecek sentetik veri oluşturulmadı. Oturum kontrolü yalnız sentetik demo hesabıyla yapıldı.
- UI/API güncel kalıcı sürümle çalışır bırakıldı. V1, VDS, üretim, router, RADIUS ve gerçek abone verilerine dokunulmadı. Ürün kodu veya yapılandırma değiştirilmedi; yalnız bu belge güncellendi.
- Sıradaki somut adım: kullanıcının panelde etkin kalıcı demo akışını incelemesi; açık başka geliştirme veya servis işlemi kapsamı yok.

## Sıradaki işler — henüz başlanmadı

- Kullanıcının sonraki açık geliştirme talimatını bekle; bu belge görevi ürün geliştirmesi başlatma yetkisi vermez.
- Gelecek görevde önce `AGENTS.md`, bu belge ve güncel Git durumunu oku; mevcut detay merkezlerini ve ortak altyapıyı yeniden yapma.
- Eksik veri alanlarının tamamlanması istenirse önce sentetik adaptörler ve ortak API sözleşmeleriyle kapsamı ele al. Canlı router/RADIUS, gerçek abone verisi, deploy, canlı migration ve servis restartı için açık ve kapsamı belirli onay gerekir.
- İptal edilmiş veya ertelenmiş bir işi yeni açık talimat olmadan yeniden başlatma.
