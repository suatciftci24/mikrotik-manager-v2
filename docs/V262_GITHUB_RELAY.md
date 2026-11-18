# Ev ve Ofis Git aktarım standardı

Tek kaynak GitHub deposu `suatciftci24/mikrotik-manager-v2`. Normal yol,
doğrulanmış checkout'tan doğrudan `origin` üzerinden Git aktarımıdır.
Mevcut çalışan GitHub SSH anahtarı, ajanı veya HTTPS credential helper'ı
kendi ortamında kalır. Protokol değişikliği, yeni anahtar veya token gerekmez.

| Terminal | Checkout | Geliştirme hedefi |
| --- | --- | --- |
| Ofis WSL `suatpc@DESKTOP-VD5T7VG` | `~/v26-transfer/mikrotik-v26-next` | `refs/heads/development/v2.6.2-pppoe` |
| Ev WSL `suat@DESKTOP-MT2JS7H` | `~/Codex-Projects/mikrotik-manager-v2` | `refs/heads/main-guncel` |

Ortak entegrasyon dalı `main-guncel`. İki dalın uçları ayrı ayrı ölçülür.
Ofis HEAD'i doğrudan ortak dalın yerine geçirilmez. Ortak dala alınacak
değişiklik için ayrı ve açık bir entegrasyon hedefi gerekir.

Her checkout'ta aktarım öncesi çevrimdışı kontrol:

```bash
bash tools/check-git-transfer.sh
```

Kontrol #48 terminal ve checkout doğrulamasını kullanır. Git'in URL rewrite
ve pushurl sonrası etkin okuma/yazma hedeflerini denetler. Birden fazla adres,
başka depo, URL içi kimlik bilgisi ve mirror yapılandırması reddedilir.
Yalnız doğrulama sonucu gösterilir. Bağlantı, fetch, pull veya push yapılmaz.

Ayrıca yetkilendirilmiş gerçek aktarımda, gönderilecek commit aralığını sırlar,
yerel yapılandırma, dump ve yedekler için gözden geçir. Amaçlanan tek tam ref'i
açıkça belirt. Normal fast-forward kullan, tag, mirror ve force aktarımı
yapma. Başarıyı aynı uzak ref'in SHA'sını doğruladıktan sonra bildir. Ağ
hatasında gerçek aktarım BLOCKED kalır. Aynı koşulda başka protokole veya VDS
relay'ine otomatik geçiş yapılmaz.

`https://v26.mikmanager.com.tr/` merkezi panel adresidir. Git aktarımı,
uygulama yayını veya DB senkronizasyonu değildir. Yerel kullanıcılar,
PostgreSQL, yapılandırma ve kimlik bilgileri taşınmaz.

## Tarihsel V2.6.2 VDS relay istisnası

Aşağıdaki prosedür yalnız geçmişte pinlenen V2.6.2 commit'inin ayrıca
yetkilendirilmiş aktarımı içindir. Normal ev/ofis aktarımında kullanılmaz.
Betik açık `--execute-pinned-relay` bayrağı olmadan aktarımı reddeder.
Önce yukarıdaki yerel hedef kontrolünü çalıştırır. Bu belgede gerçek
relay veya GitHub bağlantısı doğrulanmadı.

Yerel doğru/temiz development/v2.6.2-pppoe dalı ve origin kontrol edilir;
kaynak tam b41deae94be7ed2d3790d0a1ecd9cad1c6b06f93 olmalıdır. Kaynak doğrudan
75c27df/v2.6.1 tabanından gelir. Pack yalnız bu commit ve atalarını içerir;
yerel HEAD'deki sonraki aktarım aracı/dokümantasyon commit'leri gönderilmez.
Yerel branch/HEAD/index/upstream değiştirilmez; source değişiklikleri silinmez.

WSL mevcut mikrotik_manager_ed25519 anahtarıyla mikadmin@185.139.5.51'e
BatchMode/StrictHostKeyChecking ile bağlanır. Şifre/anahtar/token kopyalanmaz,
sudo yoktur. VDS'nin GitHub HTTPS kimlik doğrulaması mevcut ve yazma yetkili
olmalıdır; eksikse BLOCKED, yeni kimlik bilgisi oluşturulmaz veya istenmez.

VDS sistem Python'u stdin'deki hashlenmiş Git pack'i yalnız yeni 0700
/tmp/v262-git-transfer-* altındaki geçici bare depoda strict index-pack ile
okur. Commit/parent/release.json tekrar doğrulanır. Canlı proje klasörüne,
çalışma ağacına, Git HEAD/index'ine veya servislere erişilmez.

Yalnız https://github.com/suatciftci24/mikrotik-manager-v2.git hedefindeki
refs/heads/development/v2.6.2-pppoe ref'ine exact kaynak SHA normal push edilir.
URL başka hedefe rewrite ediliyorsa durur. Git hooks çalıştırılmaz. Tag/ref
mirror veya force yoktur. Var olan farklı uzak dal fast-forward değilse
korunur ve BLOCKED verilir. Kaynak zaten uzaktaysa idempotent doğrulanır.
Gönderim sonrası ls-remote exact SHA eşitliği zorunludur. Geçici depo başarı
veya yakalanan hata sonunda temizlenir; kesintide artakalan /tmp deposu canlı
uygulamaya bağlanmaz. Git hatalarının hassas içerikleri yazdırılmaz.

Başarı: PUSHED v2.6.2 + SHA. Hata: BLOCKED; otomatik tekrar/force yok.
Bu çıktı canlı panelin sürümünün değiştiği anlamına gelmez. Tek ortak panel
https://v26.mikmanager.com.tr/ ve mevcut v2.6.1 yayını korunur. Deploy/tag/
restart/DB/diğer panel/V1/V2.5/router/RADIUS/IPsec işlemi yoktur.

Doğrulama: üç çevrimdışı test. Gerçek kaynak Git pack'i yalnız geçici yerel
bare hedefe gönderildi: yeni dal, aynı SHA için idempotence, çakışan ref'in
korunması ve bozuk pack'in Git/ağ işleminden önce reddi. Başka ref/tag
oluşmaması ve geçici relay temizliği doğrulandı. Uygulama testi/build gereksiz
olduğundan tekrarlanmadı. Bu testler gerçek GitHub gönderimi kanıtı değildir.
