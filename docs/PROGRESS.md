# MikroTik Manager V2 — İlerleme

Son güncelleme: 2026-10-27. Proje yolu: `/home/suatpc/Codex-Projects/mikrotik-manager-v2`.

## Kod ve Git geçmişinden doğrulanan durum

- Branch: `main`. Bu belge görevinin başlangıcında çalışma ağacı temizdi.
- Detay merkezlerinin temel commit'i: `fa1c03b` — ortak modül altyapısı ve envanter detay merkezleri. Öncesindeki `7512239`, GitHub deposunu V2 README korunarak birleştiriyor.
- Ortak frontend altyapısı: `useResource`, `useDetailNavigation`, `PageHeading`, `ResourceState`, `DetailSection`, `Facts` ve `MissingData` mevcut.
- Router ve abone listelerinden salt okunur detay merkezlerine erişim mevcut. Liste filtreleri korunuyor; URL fragmenti detay kimliğini taşıyor. Kaynak kodunda geri dönüş, yükleniyor, hata, tekrar deneme ve boş veri durumları bulunuyor.
- `/api/v1/routers/{item_id}` ve `/api/v1/subscribers/{item_id}` merkezi demo oturum kontrolünü ve Pydantic yanıt sözleşmelerini kullanıyor; bulunamayan kayıtlar 404 döndürüyor.
- Veriler mevcut sentetik demo envanterinden geliyor. Router'a atanmış sentetik abone listesi, toplam sayaç ve aktif oturumlardan ayrı açıklanıyor. LOCAL/RADIUS yetkili kaynak bilgisi korunuyor.
- Router arayüzleri, trafik, canlı oturum, abonelik bitişi/kalan süre ve abone işlem geçmişi için bağlı veri kaynağı bulunmuyor; detay ekranları bunu açıkça belirtiyor. Bu alanlar tamamlanmış entegrasyon değildir.
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

## Sıradaki işler — henüz başlanmadı

- Kullanıcının sonraki açık geliştirme talimatını bekle; bu belge görevi ürün geliştirmesi başlatma yetkisi vermez.
- Gelecek görevde önce `AGENTS.md`, bu belge ve güncel Git durumunu oku; mevcut detay merkezlerini ve ortak altyapıyı yeniden yapma.
- Eksik veri alanlarının tamamlanması istenirse önce sentetik adaptörler ve ortak API sözleşmeleriyle kapsamı ele al. Canlı router/RADIUS, gerçek abone verisi, deploy, canlı migration ve servis restartı için açık ve kapsamı belirli onay gerekir.
- İptal edilmiş veya ertelenmiş bir işi yeni açık talimat olmadan yeniden başlatma.
