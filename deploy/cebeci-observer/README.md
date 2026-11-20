# CEBECI_TOWERS V2.6.16 salt okunur gözlemci

Güncel IPsec uyumlu pilot için [V2.6.17 kurulum yolu](VDS-V2617.md) geçerlidir.

Kurulum **yetkili VDS terminalinde**, mevcut V2.6.16 API biriminin adı ve
ayrı canlı işlem onayı doğrulandıktan sonra uygulanır. Bu hazırlıkta hiçbir
birim kurulmadı. Gözlemci tek süreçte 60 saniyelik çevrim kullanır.
Kendi Linux hesabı ve sanal ortamı vardır. Router hedefi, kaynak IP,
sertifika pini ve salt okunur komut listesi uygulamada sabittir.
API süreci yalnız snapshot dosyasını okur ve cihaz bağlantısı açmaz.

## Kurulum

1. Ayrı, taze kurulum için hesap, grup, hedef dizin, `/run/mikrotik-v2-cebeci-observer` ve gözlemci unit adının
   boşta olduğunu kontrol edin. Korumalı başka bir sürüm veya servis için
   bu adımları uygulamayın. Root ile aşağıdaki kaynakları oluşturun.

   ```sh
   groupadd --system mtv2-cebeci-read
   useradd --system --gid mtv2-cebeci-read --no-create-home \
     --home-dir /nonexistent --shell /usr/sbin/nologin mtv2-cebeci-observer
   install -d -m 0755 /opt/mikrotik-v2-cebeci-observer
   ```

2. Doğrulanmış `v2.6.16` commit'inin `backend/app` ağacını ve
   `backend/requirements.txt` dosyasını bu dizine özgün yollarıyla
   yerleştirin. Kod ve bağımlılıklar root'a ait olmalı, gözlemci ve API
   bu dizine yazamamalıdır. Burada ayrı `python3 -m venv venv` oluşturun
   ve onaylı paket kaynağından
   `venv/bin/python -m pip install -r backend/requirements.txt` çalıştırın.
   Başka checkout'un sanal ortamını veya ayarlarını kopyalamayın.

3. Root olarak gözlemcinin özel girdi dizinini oluşturun.

   ```sh
   cd /opt/mikrotik-v2-cebeci-observer
   install -d -m 0700 -o mtv2-cebeci-observer -g mtv2-cebeci-read \
     .local .local/cebeci-pilot .local/cebeci-pilot/v2614-observer
   ```

   Son dizine gözlemciye ait `0600` üç normal dosya yerleştirin.
   `ca.pem` incelenmiş CA zinciri, `password` mevcut özel salt okunur
   hesabın satır sonu içermeyen parolasıdır. `approval.json` biçimi
   `{"scope":"V2614_CEBECI_TOWERS_READ_ONLY","expires_at":"<UTC ISO-8601>"}`
   şeklindedir. Gelecekte en fazla 24 saatlik, işlem kapsamında onaylanmış
   bitiş zamanı girin. Yönetilen mod WAN alanı kabul etmez. Parolayı
   komut argümanına, ortama veya Git'e koymayın. Onayı uzatmak için yeni
   açık onayla dosyayı atomik değiştirin. Süre dolduktan sonra servisi
   yeniden başlatmak için ayrıca işlem onayı alın.

4. Sürümdeki `mikrotik-v2-cebeci-observer.service` dosyasını
   `/etc/systemd/system/` altına kurun. Ayrı doğrulanmış V2.6.16 API birimi
   için bu dizindeki `api-snapshot.conf` dosyasını birimin
   `/etc/systemd/system/<V2.6.16-API-birimi>.d/60-cebeci-snapshot.conf`
   dosyası olarak kurun. Mevcut drop-in dosyalarının üzerine yazmayın.
   API ve gözlemci farklı Linux kullanıcılarıyla çalışır. API yalnız bu
   birimde okuyucu grubunu alır. Grupla paylaşılan tek veri
   `/run/mikrotik-v2-cebeci-observer/device-inventory.json` dosyasıdır.

5. Unit'i `systemd-analyze verify` ile kontrol edin. Onaylı kapsamda
   `systemctl daemon-reload`, ardından
   `systemctl enable --now mikrotik-v2-cebeci-observer.service` ve
   doğrulanmış V2.6.16 API birimine restart uygulayın. RouterOS kaynağını
   merkezi yönetici oturumuyla Router Merkezi, Abone Merkezi ve Dashboard'da
   açın. Kaynak, son gözlem, kapsam, WAN bilinmiyor durumu ve salt okunur
   görünümü kontrol edin. Journal ve kabul kaydına abone satırı kopyalamayın.

## Durdurma ve geri dönüş

İptalde, ayrı doğrulanmış VDS terminalinde
`systemctl disable --now mikrotik-v2-cebeci-observer.service` uygulayın.
Systemd geçici snapshot dizinini kaldırır. Bitiş zamanı geçince API de
snapshot'ı gizler. Yalnız onay dosyası geri çekildiyse gözlemci bunu bir
sonraki çevrimde algılar. Hemen kesmek için birimi durdurun.

Yalnız bu kurulumun oluşturduğu API drop-in dosyasını kaldırıp
`systemctl daemon-reload` çalıştırın ve onaylı kapsamda aynı V2.6.16 API
birimini yeniden başlatın. Gözlemci unit dosyasını kaldırın ve daemon-reload
uygulayın. Bu adımların ardından kendine ait özel malzeme ve hesabı,
saklama politikasına göre ayrı olarak kaldırabilirsiniz. Geri dönüş için
veritabanı, router, RADIUS veya IPsec değişikliği gerekmez.

[systemd çalışma dizini ve işlem izolasyonu](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
