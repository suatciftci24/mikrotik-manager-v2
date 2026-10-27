# MikroTik Manager V2 — Codex Altın Kuralları

## Çalışma ilkeleri

1. Çözüm odaklı çalış; sorunları mümkünse kendin düzelt ve tamamlanmış sonuç sun.
2. Gereksiz, tekrarlı veya konuyla ilgisiz test yapma.
3. Yerel kodlama, güvenli geliştirme, hedefli test, hata düzeltme ve commit için tekrar onay isteme.
4. Yalnızca değişen işlevi ve doğrudan etkilenen kritik bağlantıları doğrula.
5. Başarılı testleri sebepsiz tekrarlama; hata varsa yalnızca başarısız kapsamı yeniden test et.
6. Tek görevde kodlama, gerekli düzeltmeler, hedefli test ve commit işlemlerini tamamla.
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
18. Görev sonunda kısa **PASS / BLOCKED**, yapılan iş, commit ve sıradaki somut adımı bildir.

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

Her göreve başlarken AGENTS.md ve varsa docs/PROGRESS.md dosyasını oku. Çalışma kurallarını kullanıcıya tekrar sordurma. Görev sonunda ilerleme belgesini güncelle.

1. Sonuç odaklı çalış. Görevi gereksiz parçalara bölme; kodlama, gerekli kontrol, düzeltme ve commit işlemlerini uçtan uca tamamla.
2. Kullanıcıya sürekli terminal komutu, test ve teşhis işi verme. Yapabildiğin işleri kendin yap.
3. Güvenli yerel inceleme, kodlama, hedefli test, hata düzeltme ve commit için tekrar tekrar onay isteme.
4. Yalnızca değişikliğe uygun gerekli kontrolleri çalıştır. Yeni bir hata veya değişiklik yoksa aynı kontrolleri tekrarlama. Zorunlu proje kontrollerini atlama.
5. Önce mevcut kodu ve proje durumunu incele; yapılmış işi yeniden yapma. Kullanıcının yerel değişikliklerini koru. Yıkıcı Git komutları kullanma.
6. Mevcut tasarımı ve çalışan özellikleri koru. Kapsam dışı yeniden yazım, bağımlılık veya karmaşıklık ekleme.
7. MikroTik Manager V1 ve canlı sistemlere değişiklik yetkisi yoktur. Deploy, canlı migration, servis restartı, router/RADIUS veya gerçek abone verisini değiştiren işlemler için açık ve kapsamı belirli kullanıcı onayı gerekir. Aynı onaylı kapsam için yeniden onay isteme.
8. İptal edilmiş veya ertelenmiş işleri yeni açık talimat olmadan yeniden başlatma.
9. Gerçek veri, örnek veri ve henüz uygulanmamış özellikleri açıkça ayır. Yapılmayan işlemi yapılmış, çalıştırılmayan testi geçmiş gibi bildirme.
10. Kullanıcıya komut vermek gerekirse önce hangi bilgisayar ve terminalde çalışacağını belirt. V2 ofis yolu: `/home/suatpc/Codex-Projects/mikrotik-manager-v2`.
11. Gerçek bir engelde nedenini ve gereken tek eylemi kısa bildir. Gereksiz deneme döngüsüne girme.
12. Her görev sonunda tamamlananları, kontrol sonucunu, commit kimliğini ve sıradaki işi kısa bildir. Kaldığımız noktayı mevcut proje ilerleme belgesine kaydet; böyle bir belge yoksa `docs/PROGRESS.md` oluştur.
