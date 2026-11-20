# V2 RouterOS salt okunur gözlemler

Router Merkezi, Abone Merkezi ve Dashboard içindeki **RouterOS · Salt okunur**
kaynağı merkezi yönetici içindir. `GET /api/v1/device-inventory` yalnız
`V2_DEVICE_INVENTORY_FILE` ile işaretlenen V2 dosyasını okur. Dosya
yapılandırılmadığında liste boştur. Hatalı dosyada HTTP 503 döner. Dosya mutlak
yolda, normal, tek bağlantılı ve yalnız sahibine açık olmalı. API süreci veya
root dosyanın sahibi olmalı. V1 aktarımı ve sentetik çalışma alanları kendi
uçlarını kullanır. Bu kaynak veritabanı migration'ı gerektirmez.

Aktarım biçimi `DeviceInventory` sözleşmesindeki
`{"source":"ROUTEROS_READ_ONLY","routers":[...]}` yapısıdır. Yalnız
doğrulanmış ve sır içermeyen gözlemleri, ayrı V2 dizininde atomik dosya
değişimiyle yayımlayacak yetkili bir üretici gerekir. HTTP yolu poll başlatmaz.
Arayüz gözlem dosyasını düzenli olarak yeniden okur.

- Başarılı ölçümde kimlik, model, sürüm, CPU, RAM ve uptime gösterilir.
  WAN arayüzü üreticinin onaylı hedef tanımından gelir. Arayüz durumu
  ve kümülatif RX/TX bayt sayaçları ayrı gösterilir. Arayüz durumu internet
  erişimini ölçmez. Sayaçlar hız veya dönemsel tüketim olarak yorumlanmaz.
  [MikroTik arayüz sayaçları](https://help.mikrotik.com/docs/spaces/ROS/pages/139526175/Interface%2Bstats%2Band%2Bmonitor-traffic)
- Hesap etkinliği PPP kaydının `disabled` alanından gelir. Oturum,
  adres ve bağlantı süresi PPP aktif tablosundan gelir. Yerel kayıtla
  eşleşmeyen PPPoE oturumları ayrı gösterilir. Bunlara RADIUS otoritesi
  atanmaz. `service=any` yalnız gözlenen bir PPPoE oturumuyla birlikte
  gösterilir. Salt okunur EXPIRE çözümlemesi YYYY-MM-DD tarihini ve varsa
  HH:MM saatini doğrular. Ham yorum aktarılmaz.
- Son bağlantı denemesi ile son başarı farklı zamanlardır. Bağlantı
  kurulurken hedefe erişilememe çevrimdışı gözlemi olarak gösterilir.
  TLS, yetki, zaman aşımı ve doğrulama hatalarında durum bilinmiyor kalır.
  Beş dakika ve üzerindeki gözlem eski olarak işaretlenir. Sayaçlar ve
  hesap/oturum satırları güncel görünümden çıkarılır.

## Gerçek bağlantı ön koşulları

Yetkili tek çevrim girişi `sample_device`, mevcut API-SSL istemcisini kullanır.
Ana uygulama, HTTP uçları ve başlatma kodu bu girişi çağırmaz. Üretici veya
zamanlayıcı kurulmadı. Mevcut pilot hedef, ağ ve kimlik kapıları uygulanmaya
devam eder. Başka bir cihaz için var olan pilot kısıtları ayrı güvenlik
incelemesi olmadan genişletilmemeli.

Cihaz bağlantısı için hedef ve kaynak IP/portu, cihaz kimliği, model ve sürüm
ayrı olarak onaylanmalı. Doğrulanmış TLS 1.2+, hedef IP SAN, CA ve sertifika
parmak iziyle, ayrı asgari yetkili API salt okunur hesabı kullanılmalı.
Kimlik bilgileri yalnız yetkili üreticide korunmalı. Kodda, JSON aktarımında,
uygulama kayıtlarında veya tarayıcıda yer almamalı. Sabit `print` komutları
ve özellik listeleri dışındaki komutlar backend'de reddedilir. [RouterOS API](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API)

RouterOS 6.49.x ve 7.x protokol yanıtları yerel sahte TLS akışında denendi.
Gerçek donanım kabulü ayrı açık cihaz bağlantısı onayı gerektirir.
