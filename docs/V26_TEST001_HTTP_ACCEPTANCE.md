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
