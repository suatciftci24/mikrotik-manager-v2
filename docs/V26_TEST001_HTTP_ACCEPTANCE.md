# Ev WSL PostgreSQL + HTTP kabulü

Repo kökünde tek komut: `bash ./accept-v26-test001-http.sh`.
Yerel `.venv` backend bağımlılıkları ve PostgreSQL 16 sunucu araçları gerekir.
Sudo/kurulum/servis komutu çalıştırmaz. PostgreSQL 16 sürümü mevcut kabul
profilinin ve cluster guard'ın zorunlu sözleşmesidir; otomatik konum keşfedilir.

Yeni private `/tmp/mikrotik-v26-acceptance` kümesi, yalnız loopback 55433 DB
ve sahip olunan socket üzerinde 18996 HTTP kullanılır. Dolu portlarda durur;
mevcut root/symlink asla kullanılmaz veya silinmez. Mevcut DB sorgulanmaz.
Gerçek login sonrası yalnız v26-test-001 workspace hesabı oluşturulur.
Uzatma/paket/pasif/aktif için API, yeni session ile DB, detay/audit, UUID replay;
yeni bağlantıda kalıcılık; yetki/onay/validation/stale ve audit rollback kontrolü
vardır. Sentetik router kaydı cihaz adaptörü açmaz. Tarayıcı/LEGACY üretim
kabulü iddia edilmez. Önceki SQLite/ASGI suite tekrar çalıştırılmaz.

Başarı veya hata sonrasında kendi HTTP ve PG kapatılır. PG stop başarısızsa
private dizin korunur ve BLOCKED verilir. Başka servis durdurulmaz. SIGKILL veya
makine kapanması cleanup çalıştıramaz; kalan root sonraki çalıştırmayı engeller.
BLOCKED aşama kodu verir, parola/DSN/yanıt gövdesi yazdırmaz.

Codex doğrulaması yalnız Bash syntax, Python AST ve diff kontrolüdür;
PostgreSQL/HTTP çalışma sonucu Ev WSL çalıştırmasında belirlenir.

## 5a664ef düzeltmesi — 2026-11-07

Ev WSL çıktısındaki dört genel hata için socket açmadan birebir yeniden üretim:
`LoopbackClient` yanıtı `status_code/json` sağlıyordu; ortak dört işlem testi
`assertEqual(response.status_code, 200, response.text)` çağırıyor. Python mesaj
argümanını da önce değerlendirdiği için HTTP 200 yanıtında bile eksik `text`
alanı her işlemde AttributeError üretir. Alt test `_SubTest` nesnesinde `stage`
yoktur; eski raporlayıcı traceback'i atıp dört kez genel aşama basıyordu.
Eski WSL çıktısı tek başına HTTP durumlarını veya audit assertion'larının
geçtiğini kanıtlamaz; yeni rapor bunları ayırt eder.

Yanıt artık gövde veya sır yazdırmayan `text` özeti sağlar. Yeni DiagnosticResult
alt testin parent aşamasını hata anında kaydeder; işlem, hata türü/mesajı ve
kaynak dosya/satırını bildirir. Fixture/cleanup holder hataları da korunur.
DB hataları SQLSTATE/şema/tablo/constraint veya bağlantı nedenini bildirir;
SQL/parametreler, URL, PG parolası ve cookie gizlenir. PG araç stderr'i yakalanır.
Kurulum aşamaları DB oluşturma/bağlantı/şema/router/login/abone olarak ayrıdır.
Ubuntu sürüm ekinin PG16 keşfini bozması ayrıca mock ile düzeltildi.

Kaynak incelemesi: DB URL yalnız yeni kümedir; demo marker migration'ı sonra
router tablosu, router audit, FK'li abone, abone event sırası korunur. Sentetik
router sonra HTTP abone oluşturulur. +30 gün tarih hesabı, revision+1, her adım
tek audit, aktör/zaman/eski-yeni alanlar, UUID replay ve yeni bağlantı kalıcılık
beklentileri değiştirilmedi. Gerçek auth/me LOCAL admin kontrolü eklendi.

PASS: beş hedefli offline regresyon (eski yanıt tam dört hata, düzeltilen yanıt
dört mevcut assertion, fixture tanısı, sır/SQL redaksiyonu, Ubuntu araç keşfi),
Bash syntax, Python AST ve diff kontrolü. Hiçbir socket/PG/HTTP çalıştırılmadı.
Gerçek PostgreSQL + HTTP kabulü BLOCKED/bekliyor; Ev WSL tek komutu değişmedi.
