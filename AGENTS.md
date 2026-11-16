# MikroTik Manager V2 — Codex Altın Kuralları

## Görev öncesi zorunlu kontrol

Her yeni görev ve oturum başlangıcında, uygulamadan önce sırayla:

a. Altın Kuralları değerlendir.
b. Önce `docs/PROGRESS.md` dosyasının güncel bölümünü ve görevle ilgili en son kabul raporunu oku; mevcut dalı, commit'i ve çalışma ağacını kontrol et.
c. Açık BLOCKED sorunlarını, ROLLBACK kayıtlarını ve geçmiş kararları belirle.
d. Görevin güvenlik, izolasyon ve kullanıcı onayı sınırlarını belirle.
e. En az maliyetli, yeterli doğrulama planını seç.
f. Ancak sonra uygulamaya geç.

Büyük dosyaları gereksiz yere tamamen tarama; ilgili başlıkları hedefli ara ve oku.
Bu kök dosya proje kapsamındaki ortak talimat kaynağıdır; alt klasörlere gereksiz kopyalama yapma.
Proje talimatları kendi aralarında çelişirse güvenli ve daha kısıtlayıcı kuralı uygula;
üst öncelikli sistem/geliştirici talimatları ve kullanıcının güncel açık talimatları saklıdır.

## Zorunlu Altın Kurallar

1. Kodlamadan önce mevcut mimariyi, ilgili kodu, geçmiş kararları, açık engelleri ve bağımlılıkları değerlendir.
2. Önce `docs/PROGRESS.md` ve görevle ilgili en son kabul raporunu oku. Büyük dosyaları gereksiz yere tamamen tarama.
3. Tek kapsamlı görevde planlama, uygulama, gerekli düzeltmeler, hedefli regresyon, kabul raporu, commit ve push işlemlerini tamamla.
4. Kanıtlanmış sorunları yeniden araştırma. Önceki çalışmaları ve bulguları tekrar kullan.
5. Ürün hatası ile test aracı hatasını ayır. Değişken verileri aynı snapshot ve aynı veri kaynağıyla karşılaştır.
6. Testleri kaldırarak, gevşeterek veya hataları gizleyerek PASS üretme.
7. Sorunun kök nedeni kanıtlanıp kalıcı düzeltme doğrulanmadan başka geliştirme aşamasına geçme.
8. BLOCKED ve ROLLBACK başarı değildir.
9. Gereksiz test, tekrar analiz, uzun keşif ve sonuçsuz dağıtım döngülerinden kaçın; Codex haftalık kullanım kotasını koru.
10. Yerel kalite kapısı tamamlanmadan canlı dağıtım yapma.
11. Her yeni canlı deploy, DB yazımı, migration, servis restartı, router, RADIUS veya PPPoE değişikliği için kullanıcıdan yeni, açık ve işlem kapsamına özgü onay al. Önceki görev veya dağıtımın onayını yeni bir canlı işleme taşıma; aynı açıkça onaylanmış işlemi gereksiz yere tekrar onaylatma.
12. V1 üretim sistemi ve eski V2 korunacak. Fresh Pilot ve yerel demo izolasyonu bozulmayacak.
13. Gizli bilgileri, parolaları, tokenları ve yedek içeriklerini Git'e ekleme.
14. Güvenli yerel değişiklikleri hedefli testlerden sonra commit/push yap; force push kullanma. Yalnız talimat/dokümantasyon görevinde içerik, talimat yükleme ve diff gibi ilgili kontroller yeterlidir; uygulama test/build döngüsü başlatma.
15. Raporlar kısa, kanıta dayalı ve net olsun. PASS yalnız gerçekten doğrulanan işlemler için verilsin.
16. Kullanıcıya terminal komutu gerekiyorsa ev/ofis/VDS/MikroTik terminalini açıkça belirt.
17. Kullanıcıdan gereksiz onay veya tekrar test isteme.

## Çalışma ilkeleri

1. Çözüm odaklı çalış; sorunları mümkünse kendin düzelt ve tamamlanmış sonuç sun.
2. Gereksiz, tekrarlı veya konuyla ilgisiz test yapma.
3. Yerel kodlama, güvenli geliştirme, hedefli test, hata düzeltme ve commit için tekrar onay isteme.
4. Yalnızca değişen işlevi ve doğrudan etkilenen kritik bağlantıları doğrula.
5. Başarılı testleri sebepsiz tekrarlama; hata varsa yalnızca başarısız kapsamı yeniden test et.
6. Tek görevde kodlama, gerekli düzeltmeler, hedefli test, commit ve normal push işlemlerini tamamla.
7. MikroTik Manager V1 üretim sistemine müdahale etme.
8. V2 için ayrı veritabanı, yapılandırma, kimlik bilgileri ve çalışma ortamı kullan.
9. Hibrit MikroTik Local + FreeRADIUS mimarisini koru; her aboneliğin tek yetkili yönetim kaynağı olsun.
10. Modüler monolit mimarisini, ortak API sözleşmelerini ve merkezi yetkilendirmeyi koru.
11. Veri bütünlüğü, işlem denetimi, güvenlik ve geri dönüş mekanizmalarını tasarıma kat.
12. Gereksiz rapor, test döngüsü ve ara görev oluşturma.
13. Her geliştirme paketinde mümkün olduğunca çalışan, gösterilebilir sonuç üret.
14. Yerel geliştirme/testlerde sentetik veri kullan; üretim verilerini ve sırlarını kullanma.
15. Canlı yayın, üretim migration'ı, servis restartı veya gerçek cihaz değişikliği için açık kullanıcı onayı al.
16. Test kolaylığı için güvenlik kontrollerini veya izolasyonu gevşetme.
17. Kritik engellerde gereksiz tekrar yerine alternatif öner ve gerçek engeli açıkça belirt.
18. Görev sonunda kısa **PASS / BLOCKED / ROLLBACK**, yapılan iş, commit/push ve sıradaki somut adımı bildir; BLOCKED ve ROLLBACK başarı değildir.

## Değişmez mimari ilkeler

1. Backend tek bir deploy edilebilir FastAPI modüler monolittir; alan sınırları API, servis, model ve adaptör katmanlarıyla korunur.
2. İstemci HTTP üzerinden yalnızca sürümlü, belgelenmiş ortak API sözleşmesine erişir; veritabanına doğrudan erişmez.
3. Kimlik doğrulama ve yetkilendirme merkezi servislerde uygulanır; her route varsayılan olarak kapalıdır.
4. Altı alan sabittir: Sistem ve Kullanıcı, Router Yönetimi, Abone Yönetimi, RADIUS Entegrasyonu, Operasyon Merkezi, MikAjanı.
5. Her abonelik hesabı tam bir yetkili kaynağa bağlıdır: `LOCAL` veya `RADIUS`; kaynak belirsizliğinde yazma yapılmaz.
6. RouterOS ve FreeRADIUS bağlantıları yalnızca dar arayüzlere bağlı adaptörlerden kurulur; domain kodu protokol ayrıntısı taşımaz.
7. Router, RADIUS ve veritabanı yan etkileri servis sınırında açıkça görünür; UI preview/demo modu bunları çağırmaz.
8. Bir veritabanı işlemi ve ona ait audit kaydı aynı transaction sınırında tamamlanır; yarım başarı raporlanmaz.
9. Abone, cihaz ve kimlik sırları loglara, API yanıtlarına, frontend bundle'ına veya örnek fixture'lara yazılmaz.
10. Şema evrimi sürümlü ve ileri/geri planlı migration'larla yapılır; uygulama başlangıcı migration çalıştırmaz.
11. Zamanlar UTC saklanır, kullanıcıya açıkça seçilmiş yerel saat diliminde gösterilir; kaynak/belirsizlik bilgisi kaybolmaz.
12. Her dış etki izlenebilir, idempotent sınırlar ve güvenli geri dönüş davranışıyla tasarlanır.

## V1 izolasyonu

- Bu depo, V1'in ayrı kardeş dizinidir; V1 kaynaklarını import etme, değiştirme veya kopyalama.
- V1 `.env`, venv, veritabanı URL'si, portları, systemd unit'leri, yedekleri, sunucusu ve router/RADIUS uçları V2'de kullanılmaz.
- Bu fazın tek komutu yalnızca `127.0.0.1` üzerinde V2 UI/API geliştirir; gerçek cihaz/RADIUS/DB bağlantısı başlatmaz.
- V2 PostgreSQL URL'si ayrı `V2_DATABASE_URL` ile verilir ve yalnız localhost/loopback'e izin verir. Geliştirme başlangıcında DB'ye bağlanılmaz.
- `migrations/` yalnız V2 şemasına aittir. Üretim veya V1 migration'ı/seed'i çalıştırılmaz.
- Gerçek bağlantı isteyen işler önce sentetik adaptörlerle geliştirilir; canlı erişim ve yazma ayrı, açık onay gerektirir.

## Kalıcı çalışma sözleşmesi

Her göreve başlarken AGENTS.md, docs/PROGRESS.md dosyasının güncel bölümü ve görevle ilgili en son kabul raporunu oku; ilerleme belgesi yoksa oluştur. Çalışma kurallarını kullanıcıya tekrar sordurma. Görev sonunda ilerleme belgesini güncelle.

1. Sonuç odaklı çalış. Görevi gereksiz parçalara bölme; kodlama, gerekli kontrol, düzeltme, commit ve normal push işlemlerini uçtan uca tamamla.
2. Kullanıcıya sürekli terminal komutu, test ve teşhis işi verme. Yapabildiğin işleri kendin yap.
3. Güvenli yerel inceleme, kodlama, hedefli test, hata düzeltme ve commit için tekrar tekrar onay isteme.
4. Yalnızca değişikliğe uygun gerekli kontrolleri çalıştır. Yeni bir hata veya değişiklik yoksa aynı kontrolleri tekrarlama. Zorunlu proje kontrollerini atlama.
5. Önce mevcut kodu ve proje durumunu incele; yapılmış işi yeniden yapma. Kullanıcının yerel değişikliklerini koru. Yıkıcı Git komutları kullanma.
6. Mevcut tasarımı ve çalışan özellikleri koru. Kapsam dışı yeniden yazım, bağımlılık veya karmaşıklık ekleme.
7. MikroTik Manager V1 ve canlı sistemlere değişiklik yetkisi yoktur. Her yeni canlı deploy, DB yazımı, migration, servis restartı, router/RADIUS/PPPoE veya gerçek abone verisini değiştiren işlem için yeni, açık ve o işleme özgü kullanıcı onayı gerekir. Önceki görevin onayı yeni işleme devredilmez; aynı açıkça onaylanmış işlem kapsamını gereksiz yere tekrar onaylatma.
8. İptal edilmiş veya ertelenmiş işleri yeni açık talimat olmadan yeniden başlatma.
9. Gerçek veri, örnek veri ve henüz uygulanmamış özellikleri açıkça ayır. Yapılmayan işlemi yapılmış, çalıştırılmayan testi geçmiş gibi bildirme.
10. Kullanıcıya komut vermek gerekirse önce hangi bilgisayar ve terminalde çalışacağını belirt. V2 ofis yolu: `/home/suatpc/Codex-Projects/mikrotik-manager-v2`.
11. Gerçek bir engelde nedenini ve gereken tek eylemi kısa bildir. Gereksiz deneme döngüsüne girme.
12. Her görev sonunda tamamlananları, kontrol sonucunu, commit kimliğini ve sıradaki işi kısa bildir. Kaldığımız noktayı mevcut proje ilerleme belgesine kaydet; böyle bir belge yoksa `docs/PROGRESS.md` oluştur.

## V2.6 kalıcı özellik koruma

Abone işlemleri değişirken `docs/V26_FEATURE_PRESERVATION_ACCEPTANCE.md`
envanterini esas al. LEGACY_DEMO ve PERSISTENT_WORKSPACE için süre uzatma,
paket/durum işlemleri ve audit görünürlüğünü birlikte koru. Mevcut QuickActions,
SubscriberDailyActions ve SubscriberRenewal akışlarını yeniden kullan; detay
uygunluk politikasını `subscriberActions.ts`, yenileme bağımlılıklarını
`subscriberSaveDependencies` üzerinden tut. Yeni işlem yüzeyi eklerken kaynak,
yetki, kalıcı depo ve router bağı reddi ile başarılı işlem erişimini hedefli
regresyonda doğrula. Sunucu yetkilerini veya kaynak güvenliğini gevşetme.

## V2.6 Zorunlu Saglik Kontrolu

- Yerel gelistirme ve sentetik testlerde kullanilmayan uzak DNS adresi zorunlu degildir.
- Yerel degisikliklerde ilgili hedefli testler ve frontend build dogrulanir.
- Canli dagitim veya uzak servis degisikliginde gercek hedefin HTTPS, API ve servis sagligi once ve sonra dogrulanir.
- Hedef erisilemiyorsa canli islem durdurulur; guvenli geri alma degerlendirilir.
- Yalnizca gercek ve dogrulanmis API endpointleri kullanilir.
- Dogrulanmayan islem basarili olarak bildirilmez.
- Gereksiz tekrar testleri yapilmaz; hedefli kontroller uygulanir.
- V1, V2.5, gercek routerlar, RADIUS ve mevcut veriler korunur.
- Yeni panel, veritabani veya servis olusturulmaz.
- Canli dagitim, migration ve servis yeniden baslatma
  icin yeni ve acik kullanici onayi gerekir.


## Ofis ve Ev Git Senkronizasyonu

- GitHub main-guncel ortak kaynak daldir.
- Her oturum basinda yerel degisiklikler korunarak senkronizasyon yapilir.
- Tamamlanan tum gelistirmeler ilgili dosyalariyla commit ve push edilir.
- Oturum sonunda yerel HEAD ile GitHub HEAD esitligi dogrulanir.
- Push basarisizsa is tamamlandi olarak bildirilmez.
- Yerel degisiklikler incelenmeden silinmez.
- Gizli bilgiler, veritabani dosyalari ve gecici dosyalar GitHub'a gonderilmez.

## ALTIN KURAL: EV-OFIS TAM SENKRONIZASYON

- Git kodunun eslesmesi tam sistem senkronizasyonu degildir.
- Ev ve ofis kullanicilari, roller, PostgreSQL verileri, aboneler, audit kayitlari ve gerekli yapilandirmalar birlikte ele alinir.
- Her iki ortamin yedegi ve fark analizi olmadan veri silme, uzerine yazma, restore, merge veya parola sifirlama yapilmaz.
- Gizli bilgiler GitHub'a veya raporlara aktarilmaz.
- Tum bilesenler dogrulanmadan tam senkronizasyon basarili denmez.
- Uzun terminal yapistirmalari yerine kisa ve guvenli islemler tercih edilir.
- Canli V1, V2.5, router, RADIUS, IPsec ve VDS degisiklikleri icin acik onay gerekir.
- AAA kabulunde daha once PASS olan testler gereksiz yere tekrarlanmaz.
