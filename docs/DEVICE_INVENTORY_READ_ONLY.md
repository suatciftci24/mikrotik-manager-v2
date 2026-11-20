# V2 RouterOS salt okunur gözlemler

Router Merkezi, Abone Merkezi ve Dashboard içindeki **Gerçek cihaz · RouterOS**
kaynağı merkezi yönetici içindir. `GET /api/v1/device-inventory` eski dosya modunda yalnız
`V2_DEVICE_INVENTORY_FILE` ile işaretlenen V2 dosyasını okur. Dosya
yapılandırılmadığında liste boştur. V2.6.16 için yönetilen tüketim modu ve
izole kurulum [systemd işletim adımlarında](../deploy/cebeci-observer/README.md)
yer alır. Hatalı dosyada HTTP 503 döner. Dosya mutlak
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

## Metin ve kapasite

API çerçevesi bayt olarak okunur. Gözlemci yalnız sabit sorgu ve alan
adlarını tanır. Geçerli UTF-8 metinler normalizasyon uygulanmadan
korunur. Çözülemeyen isteğe bağlı alan bilinmiyor kalır. Cihaz kimliği,
model, sürüm veya PPP hesabı/oturumu adı çözülemezse çevrim reddedilir.
Böylece farklı bayt dizileri aynı kullanıcı adı altında birleşmez.
Tanı kaydı yalnız sabit sorgu ve alan adını içerir. RouterOS sürümünden
karakter kodlaması çıkarılmaz. CEBECI_TOWERS'ın kesin kodlaması ve
canlı hataya yol açan alan doğrulanmadı.

WAN adı yapılandırılmışsa durum ve sayaçlar tek `/interface/print`
istatistik sorgusuyla istenir. Yanıtta bulunmayan ölçümler bilinmiyor
kalır. WAN adı yoksa arayüz sorgusu gönderilmez. Envanter için 256
yanıt cümlesi ve 256 KiB, sorgu başına 128 satır, cümle başına 32
sözcük ve sözcük başına 4096 bayt sınırı geçerlidir. Kimlik, kaynak ve
bitiş cümleleri de bütçeden düşer. WAN kapalıyken iki PPP sorgusunun
toplam üst sınırı normal yanıt biçiminde 250 satırdır. WAN yanıtı,
boş yanıt işaretleri ve bayt bütçesi bu kapasiteyi azaltabilir.
Sınır aşımında kısmi envanter başarı olarak yayımlanmaz. Cihazdaki
gerçek satır sayısı bu çalışmada ölçülmedi.

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

## CEBECI_TOWERS işletim hazırlığı

Depodaki onaylı tarihsel hedef `10.250.0.19:8729`, kaynak
`10.250.0.1`, kimlik `CEBECI_TOWERS`, model `RB3011UiAS`, sürüm
`6.49.19` ve V2'ye özel `v2-cebeci-ro` hesabıdır. Mevcut VDS/IPsec
yolunda kaynak/hedef politikasının bu ikiliyi taşıdığı, API-SSL dinleyicisi,
yetki, CA zinciri, IP SAN ve incelenmiş leaf SHA-256 pini ayrıca
doğrulanmalıdır. WAN arayüzü, güncel IPsec erişilebilirliği ve sunumda
kullanılan sertifika bu görevde ölçülmedi. V1 sağlık aktarımı salt okunur
dosya handoff olarak incelendi. Çalışan V1 poller ve kimlik bilgileri
yeniden kullanılmaz.

V2.6 profilindeki CEBECI yetkisi emekliye ayrıldı.
`v26_cebeci.validate` eski etkinleştirme ve operatör değerlerini reddeder.
Normal profil kapalıdır. Kullanıcı onayı bu kod kapısını değiştirmez.
Başka profil ile çalıştırma yetkili bir alternatif oluşturmaz.

`app.services.device_poller.poll` ayrı yetkilendirilmiş örnekleyici için
60 saniyelik seri döngü sağlar. Tek üretici kilidi vardır. Çıktı
`0700` özel dizinin içinde `0600` geçici dosyadan fsync ve atomik
yeniden adlandırma ile `device-inventory.json` olarak üretilir. Çıktıya
yalnız DTO yazılır. Ayrı çalıştırıcı bu modüle yetkili `sample_device`
çağrısını vermelidir. Profil kapalıyken bu bağlantı kurulmaz. VDS'de
servis/timer, ortam ayarı veya dosya kurulmadı. API'ye dosya tanıtmak
ayrıca V2.6.14 dağıtımı ve yetkili çalışma ortamı değişikliği gerektirir.

V2.6.14 işletim modülü olan ayrı, yetkili VDS checkout'unda
`PYTHONPATH=backend V2_DEPLOYMENT_PROFILE=v26-isolated-acceptance python3 -B -m app.services.device_poller --preflight`
mevcut kapıyı salt okunur kontrol eder. Bağlantı komutu mevcut profilde
kullanılamaz. Bu komut parola okumaz ve soket açmaz.


## Bağımsız V2.6.14 CEBECI gözlemcisi

Eski profil bağlı kalır. Yeni yetki yalnız ayrı `app.cebeci_observer`
ön plan işlemi içindir. HTTP uçlarına, registry'ye ve uygulama
başlangıcına eklenmez. Kök kullanıcıyla veya eski uygulama profili/cihaz
bayraklarıyla çalışmaz. Hedef, kaynak, port, kimlik, model, RouterOS sürümü,
hesap, router ID ve gözden geçirilmiş leaf pini kodda sabittir.

Yetkili VDS operatörü, ayrı V2.6.14 checkout'unda ve ayrı root olmayan
işletim hesabıyla `.local/cebeci-pilot/v2614-observer/` altında üç özel
dosya hazırlar. Dizinler ve dosyalar aynı hesaba ait olmalı. Özel dizinler
`0700`, dosyalar `0600` olmalı. Bağlantılar, ortak yazılabilir depolar
ve sürüm kontrolü kullanılmaz.

- `approval.json` yalnız `scope: "V2614_CEBECI_TOWERS_READ_ONLY"` ve
  `expires_at` alanlarını gerektirir. Zaman gelecekte, UTC ve en fazla 24
  saat ileride olmalı. Doğrulanmışsa isteğe bağlı `wan_interface`
  eklenebilir. Alan yoksa WAN ölçümü bilinmiyor kalır.
- `ca.pem` onaylı public CA zinciridir. `password` sabit salt okunur
  hesabın parolasını içerir. Parolaya satır sonu eklenmemeli. Parola
  komut satırına, ortam değişkenine ve Git'e yazılmamalı.
- Mevcut IPsec yolu, kaynak `10.250.0.1` ile hedef `10.250.0.19:8729`
  arasındaki trafiği taşımalı. Hedefin API-SSL dinleyicisi ve hesabın
  yalnız gerekli okuma yetkileri ayrı doğrulanmalı. Bu görevde ölçülmedi.

Normal VDS terminalinde **ayrı yetkili checkout** kökünden, gerekli Python
bağımlılıkları olan V2 yorumlayıcısıyla:

```bash
PYTHONPATH=backend python3 -B -m app.cebeci_observer preflight
PYTHONPATH=backend python3 -B -m app.cebeci_observer run
```

`preflight` yalnız yerel onayı doğrular. `run` onayı doğruladıktan sonra
sırları özel dosyalardan okur ve 60 saniyelik döngüyü başlatır. Onay
her ölçümden önce tekrar kontrol edilir. Silme veya süre dolması sonraki
çevrimi kapatır. Etkin ölçüm TLS taşıyıcısının süre sınırına tabidir.
Çıktı aynı dizinde `device-inventory.json` olarak atomik yazılır.
Bu dosyayı API'ye tanıtmak ayrı, onaylı işletim değişikliğidir.
