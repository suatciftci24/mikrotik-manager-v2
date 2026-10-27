# MikroTik Manager V2 — İlerleme

Son güncelleme: 2026-10-27. Proje yolu: `/home/suatpc/Codex-Projects/mikrotik-manager-v2`.

## Kod ve Git geçmişinden doğrulanan durum

- Branch: `main`. Bu belge görevinin başlangıcında çalışma ağacı temizdi.
- Son ürün geliştirme commit'i: `fa1c03b` — ortak modül altyapısı ve envanter detay merkezleri. Öncesindeki `7512239`, GitHub deposunu V2 README korunarak birleştiriyor.
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

## Sıradaki işler — henüz başlanmadı

- Kullanıcının sonraki açık geliştirme talimatını bekle; bu belge görevi ürün geliştirmesi başlatma yetkisi vermez.
- Gelecek görevde önce `AGENTS.md`, bu belge ve güncel Git durumunu oku; mevcut detay merkezlerini ve ortak altyapıyı yeniden yapma.
- Eksik veri alanlarının tamamlanması istenirse önce sentetik adaptörler ve ortak API sözleşmeleriyle kapsamı ele al. Canlı router/RADIUS, gerçek abone verisi, deploy, canlı migration ve servis restartı için açık ve kapsamı belirli onay gerekir.
- İptal edilmiş veya ertelenmiş bir işi yeni açık talimat olmadan yeniden başlatma.
