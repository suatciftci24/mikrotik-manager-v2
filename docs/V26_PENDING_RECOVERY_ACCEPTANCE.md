# V2.6 — aktöre bağlı kalıcı UUID recovery — 2026-11-06

Başlangıç: main-guncel / 455210f. Yerel kapsam PASS; gerçek PostgreSQL/HTTP
kabulü BLOCKED. Browser kabulü çalıştırılmadı. Canlı sistem işlemi yok.

Create/edit (legacy ve workspace), tekil renew ve toplu execute ilk POST'tan
önce işlem başına ayrı localStorage anahtarı yazar. İçerik yalnız actor, UUID,
kapalı işlem türü ve oluşturma zamanı; gövde/hedef abone/alanlar/receipt/token/
parola/cookie saklanmaz. Yedi gün sonunda, bozuk/ek alanlı kayıtta veya kesin
sonuçta anahtar silinir. Storage kapalıysa mevcut bellek akışı devam eder.

Yeniden açılışta doğrulanmış kimlikle ortak sonuç paneli kayıtları yükler.
Yalnız GET: auth/me, sabit türden türetilen receipt yolu, terminal sonuçtan
önce auth/me yeniden kontrolü. Otomatik POST/polling yok; belirsiz sonuç için
manuel sorgulama düğmesi var. Her sorgu 15sn ile sınırlı. Kesin sonuç panelde
UUID ve durumla görünür; bağlı liste/detay/geçmiş/Dashboard/raporlar yenilenir.
Backend'in mevcut aktör/ADMIN/router scope kontrolleri değiştirilmedi.

Kimlik/yetki değişimi kuşak kontrolüyle geç gelen sonucu reddeder, mevcut
kayıtları temizler ve UI ağacını yeniden kurar. Logout UI'ı hemen kapatır ve
sekmelere storage bildirimi gönderir. Anahtar başına yazma, bir sekmenin başka
UUID'yi ezmesini önler; silinen kaydı geri yazan snapshot birleştirmesi yok.
Sekmeler arası storage değişimi aktif recovery'yi iptal edip görünümü yeniler.

PASS: 7 yeni hedefli Node/esbuild testi: dört yol/reopen/minimal metadata/GET;
foreign actor/logout/VIEWER/inactive; server identity ve geç yanıt; bozuk/eski/
gelecek/ek alan/kapalı storage; kısmi belirsizlik ve bağımsız anahtarlar;
router yetki kaybı/abort; gerçek save hook'ta POST öncesi journal, kayıp yanıt,
tekPOST+GET ve terminal cleanup. İlk inactive testinde sorgu engeli eksikti;
active=false kontrolü eklendi ve yalnız başarısız kapsam tekrarlandı.
TypeScript/Vite build ve diff kontrolü PASS; mevcut >500kB uyarısı sürüyor.
İlk dosya yazma komutu yanlış cwd nedeniyle uygulanmadı; doğru proje kökünde
uygulandı. Önceki PASS suite'leri tekrarlanmadı.

Sıradaki hedef: izinli izole ortamda gerçek PostgreSQL/HTTP kabulü; bu görevde
BLOCKED bırakıldı. V1/V2.5/VDS/SSH/MikroTik/RADIUS/IPsec/gerçek veri/deploy/
migration/servis restartı yok. Kullanıcının PROGRESS eklemeleri korunur ve
commit dışında kalır.
