# V26 mevcut yedek / 011 kabul devri — 2026-11-16

Altın Kurallar ve güncel main-guncel esas alındı. Kullanıcı
`/home/mikadmin/v26-predeploy-20261116T061246Z/database.dump` için izole restore
PASS bildirdi. Bu kanıt kabul edildi; burada bağımsız gözlem gibi raporlanmadı.
VDS b4e78a4 bildirimi sabit baseline'dır. Tek SSH denemesi socket EPERM verdi;
tekrar denenmedi. İlk GitHub HEAD sorgusu DNS hatası verdi; yerel temel 94cfec6.

Ofis WSL terminalinde tek komut:

```bash
python3 /home/suatpc/Codex-Projects/mikrotik-manager-v2/tools/check-v26-backup-migration.py --run-isolated
```

Launcher tam yerel commit'ten hem migration hem worker okur; bir SSH bağlantısı
kullanır, retry yapmaz. Mevcut SSH key/known_hosts kullanılır; parola veya sudo
kısıtları değiştirilmez. VDS kaynak HEAD'i tam b4e78a4 olmalı, çalışma ağacı temiz
olmalıdır. Beklenmeyen farkta durur.

Mevcut yetkiyle `sudo -n -u postgres psql -X` üzerinden yalnız BEGIN READ ONLY /
ROLLBACK içinde paket kolon/constraint/index metadata'sı okunur. Sabit DB,
55433 portu ve /var/lib/postgresql/16/v26 cluster yolu kontrol edilir. Bu mevcut
peer erişim yetkisi yoksa BLOCKED olur; hesap/rol/erişim ayarı oluşturmaz.

Yedek yeni 0700 `/home/mikadmin/v26-backup-011-*` dizinine kopyalanır; SHA256,
metadata değişmezliği ve pg_restore list kontrolü yapılır. Kaynak dosya silinmez
ve değiştirilmez. Aynı private dizinde sıfırdan PG16 test cluster'ı kurulur;
TCP listen kapalıdır, yalnız yeni private Unix socket ve açık DB/rol kullanılır.
Canlı PostgreSQL veya systemd servisine start/stop/restart gönderilmez.

Bu kopyaya restore edilen paket metadata'sı canlıdaki salt okunur snapshot'la
aynı değilse durur. Eski backup'tan canlı uyumu varsayılmaz. Kullanıcı/ADMIN
varlığı kontrol edilir; tüm mevcut user tabloları için ham veri stdout'a
çıkarılmadan içerik hash'leri alınır. 011 yalnız data_directory'si test dizinine
eşit olduğu doğrulanmış bu kopyada iki kez çalışır. İlk çalıştırmada mevcut
bütün tablo verileri, ikincide hem tüm veriler hem paket metadata'sı aynı
kalmalıdır. İlk çalışmada yalnız iki paket tablosunun eklenmesine izin verilir.
Sonunda canlı paket metadata'sı ve HEAD drift kontrolü tekrar yapılır; yalnız
script'in kendi test cluster'ı durdurulur, dosyalar silinmeden korunur.

PASS çıktısı backup/migration hash'i, kaynak/VDS commit'i, admin sayısı,
korunan tablo sayısı ve private result.json yolunu içerir. Ham tablo satırları,
hash/parola alanları, env veya pg_restore hata içerikleri terminale basılmaz.
Test cluster'ı durdurulamazsa önceki test sonucu PASS olsa bile BLOCKED olur.

Bu komut canlı migration/deploy/restart/cleanup içermez. PASS sonrası somut
adım result.json ve hash'leri inceleyerek aynı kaynak/migration için kontrollü
V26 yayın paketini hazırlamaktır. Son kullanıcı mesajı gereği bu aşamada canlı
uygulama yoktur. Şema drift reddinde otomatik düzeltme veya veri kayıplı restore
yoktur. Mevcut başarılı sentetik PG16/build testleri tekrar çalıştırılmadı.

Yerel hedefli kontrol: 4 offline handoff güvenlik testi PASS (veri değişimi,
bilinmeyen yeni tablo, yanlış canlı hedef, başarısız backup ön-kontrolünün
bağlantı açmaması ve satır/hata içeriğinin dışarı çıkmaması). Gerçek remote
restore/migration kabulü SSH engeli nedeniyle burada BLOCKED kaldı.
