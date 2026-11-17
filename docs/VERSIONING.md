# Kalıcı sürüm yönetimi

Tek kaynak kökteki `release.json` dosyasıdır. Kararlı sürümler SemVer
`MAJOR.MINOR.PATCH` kullanır: uyumsuz ortak API/davranış değişikliği MAJOR,
geriye uyumlu özellik MINOR, geriye uyumlu hata düzeltmesi PATCH artırır.
MINOR artırılınca PATCH, MAJOR artırılınca MINOR/PATCH sıfırlanır.
Bu araç kararlı sürümler içindir; ön sürüm/build ekleri kullanılmaz.
API yolu `/api/v1` sözleşme neslidir; ürün sürümünden bağımsızdır.

Frontend bu kaydı derlemede alır; alt bilgi tarayıcıdaki arayüz derlemesinin
sürümünü gösterir. Backend kaydı süreç başlangıcında alır; FastAPI/OpenAPI
sürümü ve salt okunur `/api/ready` yanıtındaki `app_version` bunu gösterir.
Eski sekme veya farklı dağıtımda iki sürüm farklı olabilir; alt bilgi backend
sürümünü doğruladığını iddia etmez. Dağıtım paketi `release.json` dosyasını da
korumalı; frontend yeni sürüm için yeniden derlenmelidir. Eksik/geçersiz backend
kaydı başlangıcı durdurur, tahmini sürüme düşülmez.

Her sonraki güncellemede, yerel proje kökünde:

1. Mevcut dal/HEAD, temiz çalışma ağacı, release.json, CHANGELOG ve mevcut
   etiketleri incele. Değişiklik kapsamına göre SemVer artışını seç.
2. Örneğin `python3 tools/release.py patch --note "Hata düzeltmesinin açıklaması"`
   çalıştır. `minor` veya `major` aynı biçimde kullanılır. Araç merkezi kayıt,
   frontend paket/lock sürümleri ve CHANGELOG'u günceller; başka işlem yapmaz.
   CHANGELOG maddelerini gerçek değişiklik ve uyumluluk ayrıntılarıyla tamamla.
3. `python3 tools/release.py check`, ilgili hedefli testler, frontend değiştiyse
   `npm --prefix frontend run build` ve `git diff --check` çalıştır. AGENTS.md
   zorunlu build kontrolünü uygula. PROGRESS/kabul kanıtını güncelle.
4. İncelenmiş dosyaları stage ederek yerel commit oluştur. Etiketlenecek HEAD'in
   doğrulanmış commit olduğunu ve çalışma ağacının temiz olduğunu kontrol et.
5. `release.json` sürümüne göre `git tag -a vX.Y.Z -m "MikroTik Manager X.Y.Z"`
   ile açıklamalı etiket oluştur. Önce `git tag --list vX.Y.Z` ile yokluğunu
   doğrula; mevcut etiketi asla taşıma/silme veya `-f` kullanma.
6. `git show --no-patch vX.Y.Z` ile etiketi ve commit'i doğrula. Commit ve etiket
   push işlemleri yalnız görev kapsamı izin veriyorsa yapılır. Etiket oluşturmak
   canlı deploy yetkisi vermez. Deploy/restart/migration ayrı açık onay gerektirir.

`v2.6-clean-baseline-20261117` tarihsel cleanup etiketidir; SemVer etiketi
olarak yeniden adlandırılmaz. Bu görevde yeni v2.6.0 etiketi oluşturulmaz;
sürüm kaydı yerel commit ile başlatılır. Sonraki sürüm artışlarında yukarıdaki
etiket adımı tamamlanır.
