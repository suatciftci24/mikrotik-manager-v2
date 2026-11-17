# V2.6.2 — VDS üzerinden yalnız GitHub dal aktarımı

Normal Ofis WSL terminalinde tek komut:

```bash
cd ~/v26-transfer/mikrotik-v26-next && python3 -B tools/v262-push-via-vds.py
```

Bu komut deploy değildir. Codex oturumunda ağ/DNS/SSH/GitHub bağlantısı
çalıştırılmadı. Gerçek gönderim sonucu ancak normal WSL komutu çalışınca alınır.

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
