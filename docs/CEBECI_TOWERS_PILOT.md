# CEBECI_TOWERS — tek cihaz salt okunur pilot hazırlığı

**PLANLAMA / SYNTHETIC — NOT CONNECTED — HISTORICAL DATA — APPROVAL REQUIRED.**
Bu aşama pilot veya erişim izni değildir. API, SSH, SNMP, ping, IPsec test veya V1
sorgusu yapılmadı. Gerçek hesap, servis, firewall, admin/V1 bağlantısı değiştirilmedi.

## Geçmiş aday profili ve yetki

| Alan | Kullanıcının verdiği geçmiş bilgi | Güncel doğrulama |
| --- | --- | --- |
| Identity | CEBECI_TOWERS | UNKNOWN |
| Model | RB3011UiAS | UNKNOWN |
| RouterOS | 6.49.19 | UNKNOWN |
| Önceki merkezi yönetim adresi | 10.250.0.19 | UNKNOWN; bağlantı hedefi değil |
| Önceki IPsec merkez adresi | 10.250.0.1 | UNKNOWN; izinli API kaynak adresi varsayılmaz |

Bu bilgiler yalnız korumalı plan metadata'sıdır; connect_host/endpoint/servis ayarı
oluşturmaz. CEBECI_TOWERS mevcut demo envanterine veya demo-router-* izinlerine
bağlanmadı. Aday binding UNASSIGNED, cihaz erişimi NOT_GRANTED. Planı yalnız mevcut
full-scope ADMIN görebilir. VIEWER/sınırlı ADMIN 403; farklı aday ID 404 alır.
Mevcut ADMIN rolü veya dört demo router grant'i CEBECI cihaz yetkisi vermez.
Gelecekte doğrulanmış tek-router kaydı ve can_view/can_view_reports scope'u ayrı
onaylanmadan DEVICE_READ/EXECUTE/APPROVE amacı backend'de reddedilir.

## RouterOS 6 API/TLS değerlendirmesi

Resmi eski API-SSL belgesi, özelliğin 6.1'den itibaren bulunduğunu; sertifikasız
modda anonymous DH, sertifikalı modda TLS kullanıldığını belirtir. Bu **6.49.19'un
mevcut sertifikasını, TLS sürümünü veya modern istemci uyumluluğunu kanıtlamaz**.
[Resmi eski API-SSL belgesi](https://wiki.mikrotik.com/Manual:API-SSL).

API belgesi 6.43 sonrası login mesajında parolanın gönderildiğini ve .proplist'in
istenen alanları belirlediğini açıklar; yanıt ek alanlar içerebilir. Bu nedenle
tasarım çıkarımı: doğrulanmış TLS olmadan login yok, alan listesi tek başına sır
koruması değildir. API-SSL handshake/certificate/hostname/chain/cipher uyumu ve
süre sınırlı client davranışı ayrı lab incelemesi gerektirir. Düz API'ye fallback,
sertifika doğrulamasını kapatma veya eski şifre takımlarını zorla etkinleştirme yoktur.
[Resmi API belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API).

REST API v7.1beta4'ten itibaren belgelenir; RouterOS 6 pilotunun fallback'i değildir.
Bu aşamada firmware yükseltme veya servis etkinleştirme de yapılmaz.
[Resmi REST API belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API).

## Gelecekteki ayrı API hesabı: aday minimum politika

Öneri yalnız custom group içinde `read,api` başlangıç adayını değerlendirmektir;
henüz bir hesap/grup oluşturulmadı. Varsayılan `read` grubunu kullanmak minimum
sayılmaz: resmi belge bu grupta sensitive/reboot gibi yetkiler bulunduğunu ve
politika/file-operation sınırlamalarının dikkatle ele alınmasını belirtir. Bu yüzden
özel grup bile tam per-menu/per-field ACL veya sıfır yan etki garantisi değildir.
[Resmi kullanıcı/policy belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User).

Tasarım gereği write,policy,test,sensitive,reboot,ftp,password,ssh,winbox,telnet,
local,web,sniff,romon verilmez; script/file/export/listen/monitor araçları uygulama
okuma planında bulunmaz. Bir alan veya menü read/api ile okunamıyorsa privilege
artırılmaz: STOP/PERMISSION_MISMATCH, kapsam yeniden incelemeye gider. 6.49.19
üzerinde özellikle dosya ve yönetim politikası davranışı lab'da doğrulanmalıdır.
Mevcut admin hesabı, V1 hesabı/grubu veya çalışan servisler değiştirilmez.

Gelecekte kaynak kısıtlama prosedürü (bu aşamada uygulanmadı):

1. Onaylı merkezi yönetim sunucusunun **cihazın gördüğü** kaynak IP'si routing/NAT/
   IPsec topolojisiyle doğrulanmalı. Geçmiş 10.250.0.1 değeri API kaynak allowlist'i
   diye kullanılmamalı; henüz onaylı güncel kaynak/CIDR yoktur.
2. Ayrı pilot hesabının kaynak kısıtı, API-SSL service address sınırı ve input firewall
   yaklaşımı birlikte gözden geçirilmeli; yalnız onaylı merkezi kaynak /32 ve
   doğrulanmış servis/port hedeflenmeli. Varsayılan API/API-SSL portları endpoint
   doğrulaması yerine geçmez. Bu belge canlı kural/servis komutu vermez.
3. Değişiklik gerekirse V1/admin erişimine etkisi ve geri dönüşü ayrıca açıkça
   onaylanmalı. Çalışan V1 servisini kapatma/taşıma veya mevcut kuralı değiştirme yok.
4. Credential ayrı onaylı secret store'da çözülmeli; bu repoda/API/log/audit'te
   parola/PSK/key/secret-reference saklanmamalı. Bu faz resolver sağlamaz.

## Gelecekteki alan listesi ve V1/V2 karşılaştırma sözleşmesi

Aşağıdaki menüler yalnız metadata descriptor'dır; hiçbir RouterOS komutu çalışmadı.
Tam 6.49.19 build için alan kullanılabilirliği ROS6_LAB_VERIFICATION_REQUIRED'dır;
güncel v7 belgelerindeki alanlar otomatik devralınmaz. İzinli alan listesi boş veya
genişletilmişse descriptor reddedilir. Okuma planı komut runner'ına bağlı değildir.

| Menü | İzinli alanlar | V2 plan anlamı / karşılaştırma |
| --- | --- | --- |
| /system/identity | name | CEBECI_TOWERS exact aday kimliği; farklıysa STOP; geçmiş değer canlı doğrulama değil |
| /system/resource | board-name, version, uptime, cpu-load, total-memory, free-memory | Model/6.49.19 sürüm karşılaştırması; board-name alias'ları ancak ayrı incelenmiş sözleşmeyle kabul edilebilir |
| /interface | .id, name, type, disabled, running | İsim/tür/state; WAN rolü ad benzerliğinden çıkarılmaz |
| /ip/route | .id, dst-address, gateway, distance, active, disabled | v6 route alanları; v7 routing-table otomatik istenmez; default route yokluğu tek başına WAN_DOWN değildir |
| /ip/ipsec/active-peers | state, ph2-total, last-seen | Faz1 ve göreli son mesaj bilgisi; boş/yetkisiz/eksik kaynak ayrıdır |
| /ip/ipsec/installed-sa | state, auth-algorithm, enc-algorithm, current-bytes | Sadece durum/algoritma/sayaç; hiçbir key alanı istenmez |
| /ppp/secret | .id, name, service, profile, disabled | Hesap metadata'sı; password/comment/script dahil değil. EXPIRE native alan diye varsayılmaz; önceki mapping DATE/UNLIMITED/UNKNOWN incelemesi gerekir |
| /ppp/active | .id, name, service, uptime | Oturum metadata'sı; account ACTIVE olmak oturum aktifliği değildir; uptime mutlak başlangıç saati sayılmaz |

IPsec belgesi installed-sa'nın anahtar bilgileri de içerebildiğini ve active-peers
istatistiklerini açıklar. Tasarım çıkarımı: auth-key/enc-key/PSK/certificate/private
key dönen ham cevap asla loglanmaz; receiver ikinci allowlist projection uygular.
Beklenmeyen hassas alan yalnız sabit SENSITIVE_FIELD_RETURNED STOP kodu üretir,
değeri veya ham payload yanıtlanmaz. Alanlar erişilemiyorsa sensitive yetkisi
verilmez. [Resmi IPsec belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/11993097/IPsec).

PPP local hesaplar ve RADIUS kaynakları farklıdır; local secret var/yok bilgisi tek
başına abonelerin tüm otoritesini belirlemez. Pilot karşılaştırması backend'i UNKNOWN
bırakır; RADIUS sorgusu veya local/radius dönüşümü yapılmaz.
[Resmi PPP AAA belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/132350049/PPP+AAA).

Sentetik karşılaştırıcı yalnız SYNTHETIC_FIXTURE kabul eder; header ve row kimlik/
model/sürüm çelişkileri STOP olur. Account adı veya kaynak .id çakışması ile session
.id çakışması ayrı raporlanır; aynı kullanıcı için farklı session ID'leri olabilir.
ROS6 string boolean (true/false,yes/no) değerlendirilir; uygunsuz tipler sabit
DATA_INCONSISTENCY üretir. Eksik alan UNKNOWN/WARNING, boş liste UNKNOWN'dır;
alan eksikliği yetki/menü yokluğuyla aynı gerçek durum varsayılmaz.

Güncellik: observed_at/captured_at UTC-aware olmalı, eksik/gelecek/ters zaman UNKNOWN;
5 dakikadan eski sentetik gözlem STALE, farklı kaynak/capture zamanı ayrı uyarıdır.
Bu eşik plan karşılaştırması içindir; canlı SLA veya NTP doğrulaması değildir.
RouterOS uptime/last-seen göreli süreleri collector saatinden kesin olay zamanına
çevrilmez. V1 karşılaştırma tarafı da yalnız fixture'dır; mevcut V1 DB/API okunmadı.
API profilindeki deterministik 2026-10-28 kaynak saati güncel gözlem sayılmaz.

## STOP ve geri dönüş (çalıştırılmamış)

Yanlış identity/model/sürüm, erişim hatası, privilege uyumsuzluğu, beklenmeyen yazma
isteği, hassas alan dönüşü, tutarsız veri, V1 etkisi, TLS belirsizliği veya desteklenmeyen
alan/menü STOP'tur. Kimlik yanlışsa IP/ad üzerinden başka cihaza yeniden bağlanma yok.
Otomatik retry/polling/listen yok; future pilot manuel ve süre/kayıt bütçesi ayrı onaylı
olmalı. Süre ve kaynak erişimi kanıtlanmadan bir read bile başlatılmaz.

Planlanan sıra: isteği durdur → yeni okuyucu/kanalı durdur → yalnız redacted kanıtı
(run/candidate/command sınıfı/capture zamanları/field count/sabit hata kodu) koru →
yeni candidate namespace'ini karantinada tut → mevcut V1/V2 baseline etkisini incele →
taze review ve ayrı açık yürütme onayı olmadan devam etme. Business audit/aboneler
silinmez, eski admin/V1 ayarı geri alınmaya çalışılmaz, routerda rollback çalıştırılmaz.
Gerekli canlı bir değişiklik/geri dönüş ayrıca kapsamlı onay gerektirir.

## UI, test ve kabul

GET /system/cebeci-pilot yalnız plan döndürür; endpoint'e farklı candidate_id 404,
VIEWER/sınırlı ADMIN 403. Başlat/onay/test/connect/migration mutator'ı yoktur.
Read-only ekran geçmiş/UNKNOWN/risk/alan/onay/STOP ayrımını ve 320/390/1440px'i korur.
Aşama 21 ayrı kabulü: `V2_BROWSER_CEBECI_ONLY=1 ./browser-accept-demo.sh`.
Sadece V2 loopback kullanır; bu komut CEBECI'ye ulaşmaz. Mevcut admin/ayar/tercih/router
ve abone/audit baseline'ı korunur. Gerçek browser çalışmazsa PASS değildir.

Kaynak notu: resmi help/manual sayfaları farklı güncel sürümlere ait olabilir;
yalnız yukarıdaki sınırlı protokol/policy bilgileri kullanıldı. CEBECI'nin gerçek
6.49.19 davranışı, sertifikası, alanları ve erişimi bu belgelerden doğrulanmış sayılmaz.
