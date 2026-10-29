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

**Aşama 22 ayrımı:** Aşağıdaki sekiz menü Aşama 21'in yalnız sentetik karşılaştırma
tanımlarıdır; gerçek erişim allowlist'i değildir. Aşama 22 aşağıda tanımlanan beş
metadata menüsüne daralır. `/ppp/secret` ve **tüm IPsec SA/peer kaynakları** gelecekteki
pilot erişim sözleşmesinden çıkarılmıştır. Geçmiş tablo hiçbir credential/SA
okumasını veya cihaz bağlantısını yetkilendirmez.

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


## Aşama 22 — kapalı güvenli erişim sözleşmesi

**NOT CONNECTED / APPROVAL REQUIRED / SECURITY NOT VERIFIED / NO_GO.**
`CEBECI_CLOSED_ACCESS_V1`, yalnız offline hazırlık sözleşmesidir. Planın teknik olarak
tanımlı olması ile gerçek bağlantı yetkisi ayrıdır. Herhangi bir gerçek bağlantı,
ping, TLS handshake, API login, lab cihaz sorgusu, SA toplama veya polling yapılmadı.
Aşama 22 gerçek pilotu onaylayamaz veya başlatamaz; ayrı açık kullanıcı onayı zorunludur.

### Resmi gereksinim ve doğrulama sınırı

Resmi [API belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API),
varsayılan API/API-SSL portlarını 8728/8729 ve 6.43 sonrası ilk login mesajındaki
parola alanını açıklar. Bu nedenle bizim sözleşmemiz login'den **önce** doğrulanmış
TLS ister; düz API, REST, otomatik port/cihaz arama veya protokol fallback'i yoktur.
Aynı belge `.proplist` dışında alan dönebileceğini belirtir: alan isteği, güvenli
cevap veya yetki garantisi değildir. Bu faz transport uygulaması sağlamaz.

[Eski API-SSL belgesi](https://wiki.mikrotik.com/Manual:API-SSL) sertifikasız anonymous
DH seçeneğini de tanımlar. Biz bunu reddederiz; `api-ssl` adı/portu veya IPsec yolu
sunucu kimliğini/güvenliğini kanıtlamaz. Modern istemciyle minimum TLS 1.2, güvenli
şifre takımı, handshake ve tam 6.49.19 build uyumu ayrıca kanıtlanmalıdır. TLS 1.3
desteği varsayılmaz. Uyumsuzlukta eski cipher/anonymous DH açılmaz: STOP/NO_GO.

[Resmi sertifika belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/2555969/Certificates)
SAN, kullanım, güven ve geçerlilik özelliklerini açıklar. Bizim istemci gereksinimi:
gözden geçirilmiş CA trust store + eksiksiz zincir + hedef SAN/IP eşleşmesi + zaman/
server-auth kullanım/iptal incelemesi. Hostname veya certificate verification
kapatılamaz. Public SHA-256 pin ek kontrol olabilir, zincir/SAN incelemesinin yerine
geçmez. Private key/PEM/PKCS12 alınmaz. Bu repoda CA yükleme, TLS context/client,
credential veya secret resolver yoktur; default public pin de null'dır.

Bu sayfalar güncel/frozen genel dokümantasyondur; CEBECI'nin mevcut RouterOS 6.49.19
TLS sertifikası, alan uyumu veya grup etkisini doğrulamaz. Kaynaklar 2026-10-29'da
public web üzerinden incelendi; gerçek cihaz, V1 veya VDS incelenmedi.

### Minimum hesap ve kaynak tasarımı — oluşturulmadı

[Resmi kullanıcı/policy belgesi](https://help.mikrotik.com/docs/spaces/ROS/pages/8978504/User)
yetkilerin gruplarla belirlendiğini, `api` ile giriş ve `read` ile geniş okuma
haklarını ayırır. Varsayılan `read` grubu ek güçlü yetkiler içerir; dosya işlemleri
ayrıca dikkate alınmalıdır. Bu nedenle **özel `read,api` yalnız başlangıç adayıdır**;
per-menu/per-field ACL veya sıfır yan etki garantisi değildir. Tam v6 build üzerinde
minimum yetki/dosya/alan davranışının ayrı lab kanıtı olmadan MINIMUM_PRIVILEGE UNKNOWN
kalır. `sensitive`, `test`, `write`, `policy`, `reboot`, file/script/export/monitor
ve başka erişim policy'leri eklenmez. Erişim yetersizse yetki artırmak yerine STOP.

Gelecekteki hesap V1/admin'den ayrı, tek cihaz ve yalnız onaylanmış kaynak için
olmalıdır. Bu faz kullanıcı/grup adı, parola, PSK, credential reference veya özel
anahtar toplamaz/saklamaz ve hesap oluşturma komutu vermez. Kimlik doğrulama planı
ayrı hesap ve auth incelemesi boolean kanıtlarına bağlıdır; gerçek resolver yoktur.

İzinli kaynak cihazın NAT/routing/IPsec sonrasında **gördüğü adres** olmalıdır.
Geçmiş IPsec merkez adresi otomatik allowlist değildir. Tek unicast IPv4 /32,
hesap adres sınırı + API-SSL servis kaynak sınırı + input firewall incelemesi birlikte
kanıtlanmalıdır; /0, geniş CIDR, loopback/multicast/unspecified kabul edilmez. Bu
belge firewall/service/IPsec veya V1 ayarını değiştirmez. Gerekli bir canlı değişiklik
ayrıca kapsamlı açık onay ister. Source/network yolu belirsizse NO_GO.

### Tipli, tek router ve kapalı varsayılanlar

`backend/app/integrations/cebeci_access.py`:

- `AccessPlan`: frozen/extra-forbid; aday/identity CEBECI_TOWERS, model RB3011UiAS,
  incelenecek exact sürüm 6.49.19. Yönetim pini **null**, kaynak /32 **null**, public
  sertifika pini **null**. Geçmiş 10.250.0.19 ancak ayrı incelenmiş pin olarak
  tanımlanabilir; endpoint/connect_host oluşmaz. Diğer aday/model/sürüm/adres veya
  API/8728, verification bypass, network/poll/retry enable girişleri reddedilir.
- `OfflineEvidence`: yalnız OFFLINE_UNVERIFIED veya SYNTHETIC_FIXTURE. Credential,
  ham cevap/certificate/SA veya arbitrary evidence dictionary alanı yoktur. Kaynak
  zamanı timezone-aware olmalı; epoch/naive/gelecek kanıt doğrulanmış güncellik olmaz.
  Yapısal hata sabit/redacted koddur; hata input'u veya ham payload döndürülmez.
- Identity/model/version/yönetim/kaynak eşleşmesi, cihaz can_view/can_view_reports,
  TLS/chain/SAN/pin/geçerlilik, minimum hesap/ROS6 lab, freshness, V1 izolasyonu,
  audit ve STOP owner/bütçe checklist'e bağlıdır. Yanlış değer BLOCKED, eksik UNKNOWN,
  beş dakikadan eski STALE olur. UNKNOWN/BLOCKED/STALE gerçek pilot için NO_GO'dur.
- Tüm offline/sentetik kontroller PASS olsa bile EXPLICIT_EXECUTION_APPROVAL BLOCKED,
  security_status SECURITY NOT VERIFIED, live_observation_verified false,
  execution_authorized/connection_allowed false ve decision NO_GO kalır. Tam paket
  yalnız offline review tamamlığıdır; gerçek onay kaydı değildir.
- `dispatch_pilot_read` adapter'a dokunmadan mevcut backend aday yetki kontrolünü
  uygular. Mevcut full ADMIN bile DEVICE_READ/EXECUTE/APPROVE yetkisi alamaz. Gelecekte
  yetki denetimi genişlese de bu fazın dispatcher'ı ayrıca koşulsuz 403 üretir.
  CEBECI demo envanterine/grant'lerine eklenmez. Plan getter'ı execution API değildir.

### Dar salt okunur capability

`ReadIntent` yalnız exact menü + `print` + açık, boş olmayan, tekrarsız alan tuple'ı
kabul eder. Yol prefix'i, arbitrary command/query, listen/streaming, wildcard veya
broad detail/getall yoktur. İmmutable allowlist:

| Menü | Gelecekte ayrıca incelenebilecek metadata |
| --- | --- |
| /system/identity | name |
| /system/resource | board-name, version, uptime, cpu-load, total-memory, free-memory |
| /interface | .id, name, type, disabled, running |
| /ip/route | .id, dst-address, gateway, distance, active, disabled |
| /ppp/active | .id, service, uptime; auth username/name yok |

**Bu menülerin hiçbiri bu aşamada sorgulanamaz.** `/ppp/secret`, tüm IPsec installed-sa/
active-peers, certificate/user/file/export/script/firewall/NAT/config ve restart
kaynak/eylemleri dışlanır. PPPoE yazma/silme/değiştirme veya RADIUS erişimi yoktur.
`PilotReadAdapter` yalnız dar `read_metadata` protocol'üdür; genel RouterOSAdapter
ve onun yazma fonksiyonları bu pilot capability'si değildir. Transport/future gerçek
adapter henüz uygulanmadı; geniş adapter enjekte edilse bile mevcut dispatcher hiçbir
attribute/metot erişimi yapmaz.

`project_synthetic_metadata` canlı kaynak satırına bakmadan LIVE kaynağını reddeder;
yalnız sentetik test satırında önce sensitive/ek alan kontrolü, sonra mevcut allowlist
projection ve istenen alan alt kümesi uygulanır. Hassas/öngörülmeyen alan STOP'tur,
ham değer veya exception input'u çıkarılmaz. Alan adı filtresi tek başına gizli bir
değerin güvenli olduğunu ispatlamaz; gerçek alıcı ancak ayrıca gözden geçirilmiş
transport, bu boundary ve veri incelemesiyle gelecek ayrı aşamada tasarlanabilir.
Canlı IPsec SA veya credential hiçbir collector/storage/model'e eklenmedi.

### STOP, redacted audit ve eksik kanıt

STOP: kimlik/model/build uyuşmazlığı; hedef veya görünen kaynak mismatch; eksik/yanlış
yetki; TLS/sertifika bilinmeyen/mismatch; stale/unknown zaman; beklenmeyen write;
canlı SA/credential alma talebi; V1 etkisi; audit/süre/STOP sorumlusu belirsizliği.
İlk STOP'ta yeni okumayı başlatma; başka adres/hesap/port deneme; privilege artırma;
retry/polling çalıştırma. Gelecekte açılmış yalnız yeni okuyucu/kanal için durdurma ve
aday namespace karantinası planlanır. V1/admin/abone/audit geri alınmaz veya silinmez;
gerçek rollback/change de ayrıca onay ister.

İzinli kanıt/audit metadata'sı candidate_id, policy_version, packet_digest,
criterion, fixed_reason_code ve review_time'dır. Secret/raw response/SA/credential
loglanmaz. Packet digest yalnız offline paketin değişimini izler; kriptografik
attestation veya gerçek erişim onayı değildir. Bu faz kalıcı audit yazmaz.

Eksikler varsayılan kontrol listesinde açıktır: gerçek identity/model/build/yönetim
binding'i, can_view/can_view_reports scope'u, onaylı güncel /32 ve yol, TLS/client/CA/
SAN/validity/pin, ayrı hesap ve v6 minimum yetki/alan lab kanıtı, güncel kaynak,
V1 baseline, redacted audit, STOP owner/timebox ve ayrı açık yürütme onayı. Bu listede
eski sentetik eşleşme veya ADMIN olmak canlı kanıt yerine kullanılamaz.

### Aşama 22 UI ve ayrı kabul

Mevcut full-scope ADMIN `GET /api/v1/system/cebeci-pilot` yanıtı additive
`access_preparation` taşır. Yeni config yazma/credential/start/test/connect/approve/
deploy endpoint'i yoktur. VIEWER/sınırlı ADMIN mevcut backend'de 403 alır. Ekran
NO_GO / NOT CONNECTED / APPROVAL REQUIRED / SECURITY NOT VERIFIED, eksik kanıt,
engelleyici kod, kapalı ayarlar, dar read scope ve STOP/audit planını gösterir.
Önceki sekiz menü yalnız sentetik karşılaştırma açıklamasıyla korunur.

Ayrı salt okunur Playwright senaryosu (önceki aşama kabulünü çalıştırmaz):

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_SECURITY_ONLY=1 ./browser-accept-demo.sh
```

Bu yalnız V2 loopback planını okur; CEBECI'ye bağlanmaz. 320/390/1440px, async
veri-ready güvenlik checklist'i, NO_GO/kapalı bayraklar, credential/SA kapsam dışı,
UI'da mutator olmaması, sayfa write isteği olmaması, profil/envanter/admin/ayar/tercih
ve bütün eski abone/audit baseline eşitliği denetlenir. Seed/fixture/account yazması
yoktur. Gerçek browser çalışmazsa sonuç BLOCKED; birim test/build/sentetik proof
browser veya gerçek pilot PASS değildir.

## Aşama 23 — gerçek pilot ön koşulları ve kanıt matrisi

Başlangıç `93b9501`. Kullanıcı Aşama 22 için **13/13 BROWSER PASS** bildirdi;
bu yalnız yerel plan/UI kabulüdür, gerçek CEBECI erişimi/TLS/yetki kanıtı değildir.
Bu aşama üretim cihazında hiçbir komut, ping, handshake, API sorgusu, hesap/servis/
firewall/IPsec değişikliği veya veri toplama yapmaz. Aşağıdaki süreler **inceleme
politikası üst sınırıdır**, RouterOS ürün garantisi değildir.

### Kanıt matrisi

| Başlık | Kabul edilebilir kanıt türü / doğrulama yöntemi | En fazla geçerlilik | Sorumlu rol | STOP |
| --- | --- | --- | --- | --- |
| IDENTITY | Ayrı envanter kaydı ve tam build lab raporu; identity/model/RouterOS eşleşmesini iki kayıt üzerinden karşılaştır | 5 dakika | NETWORK_OWNER | Kimlik/model/build farklı, eksik veya çelişkili |
| ADDRESS | Güncel yönetim hedefi, NAT sonrası cihazın gördüğü merkezi kaynak /32 ve yol incelemesi; iki sorumlu eşleştirir | 5 dakika | NETWORK_OWNER | Hedef/kaynak/yol belirsiz veya farklı |
| ISOLATION | Maskeli IPsec yönetim topolojisi ve V1 etki/baseline inceleme özeti; ayrı V2 yetki/kaynak sınırını incele | 5 dakika | ISOLATION_OWNER | V1 etkisi/ortak credential/belirsiz izolasyon |
| CERTIFICATE | Public SHA-256 fingerprint, CA zinciri/SAN-IP/zaman/kullanım/iptal inceleme sonucu ve tam ROS6 build TLS lab raporu | 5 dakika; ayrıca sertifika süresi üst sınır | SECURITY_REVIEWER | TLS/zincir/isim/pin uyuşmazlığı veya kanıtlanmamış uyumluluk |
| PRIVILEGE | Ayrı hesap/policy tasarım ve tam build lab negatif test özeti; read,api/dosya/yan etki sınırlarını incele | 24 saat; politika/build değişirse hemen geçersiz | SECURITY_REVIEWER | Ek policy, ortak hesap veya lab kanıtı eksik |
| READ_SCOPE | Aşama 22 exact beş menü/alan/print sözleşmesi revision hash ve lab kapsamı | 24 saat; kapsam/build değişirse hemen geçersiz | SECURITY_REVIEWER | Ek kaynak/alan, write/getall/listen gereksinimi |
| SECRET_PROTECTION | Redaction/retention ve ayrı credential yönetimi tasarım sonucu; raw yanıt depolanmadığını incele | 24 saat | SECURITY_REVIEWER | Parola/PSK/private key/SA talebi veya sızıntı |
| AUDIT | UTC-aware kaynak zamanı, redacted inceleme kaydı ve korunmuş baseline hash özeti | 5 dakika | AUDIT_OWNER | Eksik audit, gelecek/stale/çelişkili zaman veya veri |
| STOP | Sorumlu rol, süre bütçesi, durdurma ve ayrıca onay gerektiren erişim iptal runbook incelemesi | 24 saat | INCIDENT_OWNER | Sorumlu/bütçe/iptal prosedürü eksik |

API matrisi aynı sabit politika satırlarından üretilir. Her satır kanıt türü, yöntem,
süre, sorumlu rol, STOP ve mevcut MISSING/INVALID/STALE/CONFLICT/BLOCKED gerekçesini
gösterir. Güncel kanıt yok: default dokuz satır **MISSING**, zamanlar UNKNOWN.
**Geçmiş 10.250.0.19 adresi güncel hedef veya erişim kanıtı değildir.** Eski IPsec
merkez adresi de güncel/NAT sonrası izinli kaynak değildir. Gerçek adreslerin
atanması bu aşamada yapılmaz; eski AccessPlan null varsayılanları korunur.

Her ilgili değişiklik, süre dolmasa bile kanıtı geçersizleştirir. İnceleme kaydı
Stage 22 politika/config/offline kanıt paketinin SHA-256 özetiyle bağlıdır; farklı
paket CONFLICT olur. Genel değişikliklerin (yol/topoloji/build/policy/CA/audit-owner)
takibi gelecekte yetkili sorumlunun görevidir; bu kod otomatik değişiklik izleme
veya gerçek kanıt doğrulayıcı değildir. Tüm Stage 22 güvenlik kapılarının geçerliliği
ayrıca zorunludur; dolayısıyla 24 saatlik lab raporu tek başına 5 dakikalık güncel
kaynak kapısını karşılamaz. Sertifika süresi/iptal incelemesi boolean attestation'dır,
otomatik PKI doğrulaması değildir; eksikse NO_GO.

### İleride yetkili operatörün salt okunur doğrulama prosedürü

Bu runbook **şimdi çalıştırılmayacak**, hiçbir üretim komutu içermeyen inceleme
planıdır. V1 veya CEBECI'de mevcut kayıtlara bakmak dahi bu görevde yapılmaz.

1. Önce ayrı kapsam ve kanıt toplama yetkisini belgele; onaylı mevcut offline
   envanter/topoloji/public metadata/lab raporlarını kullan. Henüz onaylanmamış
   gerçek cihaz sorgusuyla eksik kanıtı tamamlamaya çalışma. Harici kanıtı yoksa UNKNOWN.
2. Envanterdeki identity/model/tam RouterOS sürümünü bağımsız kayıtla eşleştir.
   Zamanı ve inceleyen rolü kaydet; eski planı mevcut cihaz durumu diye işaretleme.
3. Yetkili ağ sorumluları yönetim hedefini, cihazın göreceği NAT sonrası /32'yi,
   IPsec yönetim yolunu ve V1 izolasyonunu mevcut onaylı diyagram/baseline üzerinde
   incelesin. SA/PSK/config export alma; V1 sorgulama, tunnel açma veya trafik üretme.
   Yol/hesap/firewall değişikliği gerekirse bu inceleme STOP; ayrı değişiklik onayı gerekir.
4. Güvenlik sorumlusu public sertifika metadata'sının CA/zincir/SAN-IP/validity/
   kullanım/iptal inceleme sonucunu ve lab TLS 1.2+ raporunu karşılaştırsın. API-SSL
   adı/portu güvenlik kanıtı değildir. Hostname/chain kontrolü kapatılamaz; anonymous
   DH/plain API/legacy cipher fallback yok. Gerçek handshake bu fazda yapılmaz.
5. Tam aynı RouterOS 6 build için önceden hazırlanmış izole lab negatif test
   raporunu incele: ayrı özel read,api aday hesabının geniş read/dosya etkileri,
   ek alan dönüşü ve yalnız izinli metadata'nın alınabilirliği. Güncel resmi
   doküman eski build'in davranışını kanıtlamaz. Ek yetki gerekiyorsa artırma: STOP.
   Gerçek hesap adı/parola veya credential reference bu repoya verilmez.
6. Beş exact metadata menü/alan listesini karşılaştır. PPP secret, authentication
   name, IPsec SA/peer, user/certificate/file/export/firewall/NAT/script ve bütün
   mutasyonlar dışarıda kalır. Alan filtreleme tek başına sır koruma garantisi değil;
   beklenmeyen alanın redacted STOP sonucu gerekir. Üretimde negatif write testi yapma.
7. Kaynak zamanı UTC-aware, gelecekte değil ve 5 dakika içinde olsun. Aynı başlıkta
   iki kayıt varsa sonuncuyu seçme: CONFLICT. Süre/rol/paket binding'ini kontrol et.
   Veri kaynağı veya kanıt belirsizse boş başarı yerine NO_GO raporla.
8. İki bağımsız sorumlunun incelemesi ve STOP timebox/irtibat/iptal runbook'u masa
   başında doğrulansın. V2 okuyucu açılmışsa gelecekte ilk STOP'ta sadece o okuyucu
   durdurulmalı; retry/alternatif hesap/port/yol denenmemeli. Hesap/servis/firewall
   iptali canlı değişikliktir, ayrı açık yetkili operatör onayı ve sorumlusu olmadan
   yapılmaz. V1, aboneler ve audit geçmişi geri alınmaz/silinmez.

### Maskeleme, sorumluluk ve kanıt kaydı sınırı

- Parola, PSK, özel anahtar, cookie/token, raw export/cevap, canlı SA bilgisi veya
  private certificate dosyası **istenmez/alınmaz/saklanmaz**. Bunların ekran görüntüsü
  veya hash'i de kanıt diye alınmaz. Gizli veri görülürse kopyalamadan STOP ve yalnız
  sabit olay koduyla sorumluya bildirim prosedürü uygulanır; otomatik bildirim yoktur.
- Yerel public/offline raporu paylaşmadan önce hesap/abone isimleri, seri numarası,
  MAC, kullanıcı bilgisi, diğer router IP/rotaları ve ilgisiz altyapı bilgileri çıkarılır.
  Topolojiye rol etiketleri verilir; kaynak/hedef eşleşmesi yetkili sorumlu tarafından
  yerinde incelenir, uygulamaya raw topoloji aktarılmaz. Public sertifika metadata'sı
  da gereksiz SAN/organizasyon alanları ayıklanarak inceleme özeti haline getirilir.
- `EvidenceReceipt` sadece dokuz sabit başlık, sonuç kodu, izinli reviewer rolü,
  maskelenmiş **gizli olmayan raporun** hash'i, politika paketi hash'i, zaman aralığı
  ve SYNTHETIC_FIXTURE/OFFLINE_UNVERIFIED kaynağı içerir. Hash rapor içeriğinin
  doğruluğu veya imza/kimlik doğrulaması değildir. Rol adı da sorumlu kişinin gerçekten
  inceleme yaptığına ilişkin kanıt değildir. Kişi ataması ayrıca yönetilen dış süreçte
  yapılmalı; mevcut sorumlular henüz atanmış sayılmaz.
- Bu aşama receipt alım/yükleme/düzenleme API'si, onay deposu veya persistent audit
  yazması eklemez. Typed receipt sadece offline domain testlerinde kullanılır; ADMIN
  GET varsayılan eksik matrisi üretir. Yeni sır depolama veya gerçek collector yoktur.

### Teknik uygunluk, operatör kararı ve yürütme yetkisi

1. `technical_suitability`: NOT_VERIFIED veya yalnız OFFLINE_REVIEW_READY. Her receipt
   ve bağlı Stage 22 kapısı geçerli olmadan hazır olmaz. Yanlış kimlik, TLS mismatch,
   geniş policy veya V1 riski BLOCKED; değişen paket/çift kanıt CONFLICT; eksik MISSING;
   yanlış rol/zaman INVALID; süresi geçmiş STALE. Hepsi fail-closed NO_GO.
2. `operator_approval`: NOT_RECORDED. Teknik uygunluk insan onayı değildir; bu aşama
   onay almaz/vermez/saklamaz. Sentetik/offline PASS gerçek güvenlik doğrulaması değil.
3. `execution_authority`: DENIED. `decision=NO_GO`, `automatic_go=false`,
   `connection_allowed=false`; NOT CONNECTED / APPROVAL REQUIRED korunur.

Gelecekte insan tarafından GO değerlendirilebilmesi için **birlikte** gerekenler:
güncel bağımsız doğrulanmış bütün teknik kanıtlar, tam build lab uyumu, gizlilik ve
V1 izolasyonu, atanmış sorumlular ve süre/bütçe/STOP/iptal planı, aynı aday/kapsam/
paket/süreye bağlı ayrı açık kullanıcı pilot onayı ve ayrıca gözden geçirilmiş dar
execution capability/yetki sınırı. Bu şartların listelenmesi GO veya execution
vermez. Mevcut dispatcher adapter'a dokunmadan 403 vermeye devam eder. Bu fazda GO
üreten yol, bağlantı/başlat/test/credential/deploy butonu veya endpoint yoktur.

### Aşama 23 kabulü

Yalnız yeni salt okunur Playwright kapsamı; önceki aşamaların kabulünü çalıştırmaz.
Dokuz kanıt/TTL/sorumlu/STOP, karar ayrımı, kapalı kontroller ve 320/390/1440px,
reload ve yönetim/abone/audit baseline eşitliğini denetler. Seed veya fixture yazmaz.
Normal **ofis WSL** terminalinde tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_PREREQUISITES_ONLY=1 ./browser-accept-demo.sh
```
