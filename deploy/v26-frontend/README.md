# V2.6 seçici frontend güncelleme aracı

`update.py` tek araçtır: `pack`, `check`, `apply`, `verify`, `rollback`.
Burada canlıda çalıştırılmadı. Kullanıcının dağıtım onayı yoktur; aşağıdaki
`apply`/`rollback` komutları yalnız ayrıca açık onay sonrası kullanılabilir.
SSH, git pull, npm install, backend, DB, migration, Nginx veya servis işlemi yok.

## Hazırlık — Ev/Ofis yerel proje terminali

Önceki test edilmiş e6e4aff seçici aday `.local/v26-legacy-review`, yeni aday
`.local/v26-legacy-actions` olarak korunur. Yeni aday pinli VDS referansından
`prepare-v26-legacy.mjs` ile üretildi; önceki 10 dosyalık entegrasyondan yalnız
`src/components/QuickActions.tsx` değişir. Diğer kaynaklar, public, package,
lockfile, index ve Vite/TypeScript config aynı olmalıdır. Yeni dependency yok.

```bash
python3 deploy/v26-frontend/update.py pack --baseline .local/v26-legacy-review --candidate .local/v26-legacy-actions --bundle .local/v26-legacy-update-final
```

Paket mevcutsa araç durur; yeniden hazırlamada yeni paket adı kullanılır.
Kaynak/config SHA256 önce/sonra, eski ve yeni build hash'leri paketin
`manifest.json` dosyasındadır. Paket yalnız bir kaynak dosyası ve derlenmiş
statik çıktıyı taşır. Önceki hashed assets açık tarayıcıların lazy import'ları
için pakette korunur. Aynı asset adında farklı içerik varsa hazırlık durur.
Paket/araç/manifest yetkili operatör tarafından aktarılmalı; manifest güvenilen
bu yerel paketle eşleştirilmelidir. Manifest kriptografik imza değildir.

## Kaynak bütünlüğü — VDS terminali, yalnız okuma

Aktarım dizini örneği `/tmp/v26-legacy-update-final`; araç yolunu aktarım
konumuna göre seçin. Sabit hedef yalnız `/srv/mikrotik-manager-v26/frontend`.
VDS'de `.git` gerektirmez. Kaynakların tamamı, config/public ve çalışan `dist`
önceki adayla byte düzeyinde aynı değilse durur; farklar körlemesine kabul
edilmez. Symlink hedefler/webroot bu araçla güncellenmez. Böyle bir driftte
tek sonraki iş yeni kaynak/config/dist snapshot'ıyla seçici aday hazırlamaktır.

```bash
python3 update.py check --bundle /tmp/v26-legacy-update-final
```

## Uygulama — yalnız ayrıca dağıtım onayından sonra, VDS terminali

```bash
python3 update.py apply --bundle /tmp/v26-legacy-update-final --backup /srv/mikrotik-manager-v26/frontend-backup-legacy-actions-01 --approved-v26-frontend-write
```

Araç yeni 0700 yedek dizininde eski kaynak, tam eski dist ve hash receipt'i
oluşturup doğrular. Eski yedeği ezmez. Directory flock ile eşzamanlı araç
çağrılarını engeller; bağımsız dosya yazan diğer deploy araçları yayın boyunca
çalıştırılmamalıdır. Hazırlanan dist Linux `renameat2(RENAME_EXCHANGE)` ile
atomik değiştirilir; destek yoksa durur. Tek kaynak dosyası atomik replace ile
güncellenir. Kaynak+dist birlikte bir filesystem transaction değildir; hata
halinde otomatik geri dönüş vardır, süreç kesilirse kalıcı yedekten rollback
kullanılır. Hiçbir servis yeniden başlatılmaz. Yalnız frontend/dist statik
hosting düzenine uygundur; farklı hosting hedefinde uygulanmaz.

## Yayın sonrası doğrulama ve rollback — VDS terminali

```bash
python3 update.py verify --bundle /tmp/v26-legacy-update-final
```

Mevcut V2.6 statik HTTP listener'ı doğrulanmışsa aynı `verify` komutuna
`--url http://127.0.0.1:PORT` eklenebilir. Yalnız index ve index'in JS/CSS
asset'leri GET ile byte/hash karşılaştırılır; API/DB isteği yok, redirect
reddedilir. Listener başlatılmaz. Tarayıcıda mevcut yetkili oturumla üç
pencere/işlem açıklaması ve audit görünümü salt okunur kontrol edilir; gerçek
abonede onay butonuna basılmaz. Kayıt kabulü yalnız izole sentetik testtedir.

Beklenmeyen durumda ayrıca yetkili operatör rollback uygular:

```bash
python3 update.py rollback --backup /srv/mikrotik-manager-v26/frontend-backup-legacy-actions-01 --approved-v26-frontend-write
```

Rollback yedek bütünlüğünü ve hedefin önce/sonra izinli hash durumlarını
kontrol eder; sonradan değişmiş kaynakları veya farklı build'i ezmez. Önceki
kaynak/dist geri yüklenip yeniden hash doğrulanır. Eski build'e dönüldüğünde
operatör tarayıcıyı yeniler. Yedekler otomatik silinmez.

## Yerel sağlık kapısı doğrulaması

`accept_health_or_rollback(target, bundle, backup, health_check)` kütüphane
fonksiyonu uygulanmış bir adayın hash'lerini ve çağıranın sağlık kontrolünü
birlikte kapılar. Yalnız açık `True` kabul edilir. Sağlık hatasında mevcut
rollback çalışır; başarılı geri dönüşte dahi fonksiyon
`HEALTH_ACCEPTANCE_FAILED_ROLLBACK_VERIFIED` hatası verir. Drift veya bozuk
yedekte `HEALTH_ACCEPTANCE_FAILED_ROLLBACK_BLOCKED` ile durur ve başka
operatörün düzenlemesini ezmez. Bu fonksiyon ağ/servis başlatmaz.

Bu yalnız yerelde sentetik filesystem testleriyle doğrulandı; mevcut CLI
`apply`/`verify` komutlarına otomatik browser/sağlık kontrolü bağlanmadı.
Hash doğrulamasının PASS olması Dashboard sağlığı kabulü değildir. Canlı
kullanım yeni açık onay gerektirir; bu değişiklik dağıtım yetkisi vermez.
Seçici QuickActions paket sınırı değişmedi; Dashboard'u yayınlayan yeni bir
araç veya Fresh Pilot deploy yolu değildir.

Sağlık kapısı artık private yedekte exclusive 0600 `health-failure.json` ve
`health-rollback.json` üretir. İlki sağlık FAIL ve güvenli kaynak satırını,
ikincisi rollback VERIFIED/BLOCKED durumunu saklar; ham hata/parola yazılmaz.
Tanı yazımı başarısızsa rollback yine denenir; önceki dosyalar ezilmez.
Geri dönüş başarılı fakat kayıt eksikse hata koduna `_EVIDENCE_BLOCKED` eklenir.
Bu kütüphane davranışı yalnız sentetik geçici ağaçlarda doğrulandı; canlı
CLI'ya otomatik browser/sağlık veya yeni dağıtım yetkisi eklenmedi.
