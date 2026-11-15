# Abone geçmişi: okunabilir aktör ve sade sonuç — 2026-11-15

Temel temiz main-guncel/70226cf; uzak dal aynı SHA. AGENTS/Altın Kurallar,
güncel PROGRESS, son Dashboard audit kabulü ve özellik koruma envanteri okundu.
Önceki PG/AAA/canlı kabul engelleri bu görevle kapatılmış sayılmaz.

Abone Detay Merkezi'nin yetki kontrolü ve tarihsel router filtresi tamamlandıktan
sonra yalnız dönen en fazla 50 audit aktörü için kullanıcı adları toplu okunur.
Mevcut identity adaptörü, şema doğrulaması ve kurulum/origin sınırları korunur.
Sorgu yalnız id/username seçer; kullanıcı dizini endpoint'i veya frontend kullanıcı
listesi çağrısı eklenmez. V26'da legacy şemadan veya bootstrap kimliğinden isim
alınmaz. Bulunamayan/silinmiş aktör veya identity depo hatasında isim uydurulmaz;
audit okunabilir kalır. actor_username yanıt projeksiyonudur; audit actor_id,
UUID, revizyon, snapshot ve veritabanı kaydı değiştirilmez. İsim güncel kullanıcı
adıdır, tarihsel kullanıcı adı snapshot'ı olarak sunulmaz.

Geçmiş satırında işlem, İstanbul tarih/saat, çözülen kullanıcı adı ve yalnız
farklı eski→yeni alanlar görünür. İsim yoksa uzun kimlik ilk 8/son 4 karakterle
Kullanıcı (…) biçiminde kısalır; kısa mevcut kimlik aynen kalır. Tam aktör kimliği,
UUID/revizyon, kaynak, router ve tam snapshot kapalı Teknik detaylar içindedir.
Başarı metni burada korunur; her satırda tekrar gösterilmez. Başarısızlık ve
belirsiz sonuç görünür kalır. Gereksiz audit açıklaması kaldırıldı.

PASS:
- 15 backend hedef testi: test_audit_actor_names + test_pppoe_workspace_access.
  Minimal toplu SELECT, kurulum/origin/şema reddi, yetki kontrolünden sonra isim
  çözme, response-model alanı, ham audit korunması, grant iptaliyle sorgu yokluğu,
  depo hatasında audit'in korunması ve mevcut scoped PPPoE regresyonları.
- subscriberCenter: 23 frontend senaryosu. İsim/kısa kimlik, tam kimliğin kapalı
  detayda korunması, değişmeyen alanın gizlenmesi, başarı tekrarının kaldırılması,
  başarısız sonuç, eski→yeni tarihler, legacy/kaynak/readonly akışları.
  Yeni test ilk koşuda işlem başlığındaki 'Sentetik kayıt düzenlendi'yi tekrar
  sonuç metni sanıyordu; assertion tam sonuç ifadesine daraltıldı ve yalnız
  başarısız senaryo tekrar geçti. Ürün kontrolü gevşetilmedi.
- TypeScript/Vite production build ve git diff --check PASS.

Testler sentetik mock/ASGI/geçici SQLite kullanır. Mevcut PostgreSQL'e bağlantı,
veri/kullanıcı/şema değişikliği, migration, gerçek browser/canlı kabul yapılmadı.
VDS deploy/restart, V1/V2.5/router/RADIUS/IPsec işlemi yok. Etkinleşmesi için ayrı
onaylı backend + frontend yayını gerekir; bu değişiklik için migration gerekmez.
Commit/normal push ve uzak HEAD eşitliği teslim raporunda bildirilir.
