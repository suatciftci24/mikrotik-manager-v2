# V1 envanteri salt okunur aktarım sınırı

Bu paket canlı entegrasyon kabulü değildir. V1'e DB/HTTP/SSH bağlantısı yoktur;
V1 kimlik bilgileri veya yeni DB grant oluşturulmaz. Yalnız V2'ye teslim edilmiş,
sırlardan arındırılmış tek JSON dosyası O_RDONLY ile okunur. V2_V1_INVENTORY_FILE
mutlak dosya yoludur; varsayılan kapalıdır. Symlink, hardlink, özel dosya,
1 MiB üzeri dosya, 2000 üzeri kayıt, tekrar ID ve sözleşme dışı alan reddedilir.
Dosyayı güncellemek bu uygulamanın işi değildir. Yetkili aktarım sağlayıcısı
ayrı onay gerektirir; burada kurulmaz. V1 dizini/.env/DB dosyası gösterilmemelidir.

Yerel şema incelemesi: public.routers metadata sağlar; enabled, last_seen_at ve
last_poll_at online kanıtı değildir. public.router_health_samples sampled_at,
cpu_load_percent, memory_used_percent sağlar. WAN/internet sonucu router online
olarak dönüştürülmez. Bu nedenle durum her zaman Veri yok kalır. Metadata zamanı
ölçüm zamanı yerine kullanılmaz. Ölçüm zamanı olmayan CPU/bellek bastırılır;
5 dakikayı aşan ölçüm Eski gösterilir. Kaynak etiketi gerçek veri doğrulaması
iddiası değildir; aktarımın kökeni yetkili sağlayıcı tarafından güvenceye alınmalıdır.

Sözleşme (yalnız sentetik örnek):
```json
{"source":"V1_INVENTORY_EXPORT","items":[{"id":"fixture-1","name":"Sentetik aktarım örneği","identity":null,"model":null,"routeros_version":null,"sampled_at":null,"cpu_load_percent":null,"memory_used_percent":null}]}
```

GET /api/v1/v1-inventory merkezi V2 ADMIN yetkisi gerektirir. Yapılandırma yoksa
NO_DATA; bozuk/okunamayan dosyada 503 ve temiz hata döner; demo fallback yoktur.
UI ayrı gerçek V1 sekmesindedir. Canlı erişim, export sağlayıcısı, VDS deployment
ve gerçek veri kabulü bu pakette BLOCKED kalır.

## Yerel sağlık sözleşmesi (072809d sonrası)

V1 kaynağı erişilebilir schema.sql içindeki public.router_health_samples ve
V1 mikajani_legacy_inventory_adapter.py sorgusuyla doğrulandı. Eşleşme yalnız
routers.id = router_health_samples.router_id; ad, IP, identity ile eşleşme yok.

Handoff artık isteğe bağlı health_samples listesi kabul eder. Her satırda id ve
router_id canonical pozitif tam sayı metni, sampled_at timezone içeren tarih;
cpu_load_percent, memory_used_percent ve internet_success nullable alanlardır.
Örnek: {"id":"17","router_id":"1","sampled_at":"2026-01-01T00:00:00Z",
"cpu_load_percent":0,"memory_used_percent":null,"internet_success":false}.
Yalnız en son satır sampled_at DESC, id DESC ile seçilir; geçmiş satırlardan
boşluk doldurulmaz. Eşleşmeyen, çift router örneği ve gelecek/naive tarih 503
ile kapatılır. Eski metadata-only aktarım geçerlidir, sağlık alanları Veri yoktur.

health-export.sql yalnız hazırlanmış SELECT sözleşmesidir; otomatik çağrılmaz.
Mevcut 072809d NOLOGIN rolünün sağlık SELECT yetkisi yoktur. Bu görev DB yetkisini,
export uygulayıcısını ve canlı handoff dosyasını değiştirmez. Sonraki ayrı onaylı
entegrasyonda gereken sütunlar: router_health_samples(id,router_id,sampled_at,
cpu_load_percent,memory_used_percent,internet_success). Yetki hatasında admin
fallback yasaktır. Yeni sorgu ve gerçek sağlık verisi canlıda test edilmedi.

API health_source ve health_sample_id ile ölçüm kaynağını korur. connection_status
LAST_PROBE_SUCCEEDED/FAILED yalnız tarihli internet denemesi sonucudur; router'ın
canlı ONLINE/OFFLINE durumu değildir. status NO_DATA kalır. Ölçüm 300 saniyeyi
geçince STALE, panelde Güncel değil gösterilir. Türkiye saati Europe/Istanbul'dur.
API ADMIN koruması ve sentetik kaynak ayrımı değişmez. Yerel testler sentetiktir.
