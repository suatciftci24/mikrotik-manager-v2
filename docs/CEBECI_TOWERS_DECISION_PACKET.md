# CEBECI_TOWERS — Aşama 26 operasyonel pilot karar paketi

**NO_GO / NOT CONNECTED / APPROVAL REQUIRED.** Başlangıç `b4cf665`.
Kullanıcı Aşama 25 için **12/12 gerçek tarayıcı PASS** bildirdi. Bu yerel V2 ekran
kabulüdür; router erişimi, TLS, minimum hesap veya gerçek pilot onayı değildir.
Bu aşamada canlı V1/VDS/router/RADIUS/üretim erişimi veya değişiklik yapılmadı.

## Tek görünüm, mevcut kaynaklar

ADMIN pilot ekranının başında birleşik karar görünümü yer alır. Eski teknik
bölümler erişilebilir kalır. Aynı GET `/api/v1/system/cebeci-pilot` kullanılır;
yeni intake, onay, hesap oluşturma, bağlantı, test veya deploy endpoint'i yoktur.

| Kanonik kaynak | Karar görünümündeki kullanımı |
| --- | --- |
| Aşama 22 access_preparation / AccessPlan | TLS zorunluluğu, kapalı ağ/dispatch ve backend ADMIN sınırı |
| Aşama 23 prerequisites.matrix | Dokuz başlık; sorumlu rolü, gereken kanıt ve STOP açıklaması |
| Aşama 24 manual_review | Sekiz manuel bildirim, bilinmeyen gözlem zamanı, risk ve A/B güvenlik boyutları |
| Aşama 25 account_preparation | Sekiz hazırlık durumu ve yirmi bağımsız alanın kaynak/zaman/durum/gerekçesi; taşıma kararı |
| Aşama 26 decision_packet | Yalnız türetilmiş referanslar, kategori indeksleri, engeller ve güvenli operatör soruları/adımları |

Yeni bir kanıt, hesap veya değerlendirme deposu oluşturulmadı. Etiketler, durumlar,
manuel değerler ve policy sözleşmesi eski kaynaklarında kalır. Matris çapraz bağları
sadece mevcut ID'leri eşleştirir; bir başlıkta birden çok alan/grup olabilir.

| Dokuz matris başlığı | Yirmi alana referanslar |
| --- | --- |
| IDENTITY | ROUTER_IDENTITY, ROS6_LAB |
| ADDRESS | SOURCE_ACCOUNT, SOURCE_SERVICE, SOURCE_FIREWALL, IPSEC_PATH |
| ISOLATION | IPSEC_AUTH, IPSEC_PATH, V1_IMPACT |
| CERTIFICATE | TLS_CLIENT, TLS_CHAIN, TLS_NAME, TLS_VALIDITY, TLS_PIN |
| PRIVILEGE | ACCOUNT_SEPARATE, ACCOUNT_AUTH, POLICY_EXACT, ROS6_LAB |
| READ_SCOPE | ROS6_LAB, POLICY_EXACT |
| SECRET_PROTECTION | ACCOUNT_AUTH, AUDIT |
| AUDIT | AUDIT |
| STOP | STOP_OWNER, ROLLBACK, OPERATOR_REVIEW |

Sekiz grup mevcut FIELDS/GROUPS üyeliklerinden bağlanır; alan/yetki tanımları
kopyalanmaz. Yirmi alanın hepsi en az bir matris başlığına bağlıdır. Yeni frontend
testi de bu gerçek offline API sözleşmesini okuyarak sahte ikinci 9/8/20 model
kurmaz; Python domain fixture'ı socket kullanımı yasaklanarak üretilir.

## Kanıt sınıfları ve açıklama

- **Eksik:** mevcut Aşama 25 MISSING alan referansları; şu anda 20.
- **Manuel:** Aşama 24 OPERATOR_REPORTED_MANUAL bildirimleri; şu anda 8. Manuel
  kaynaklı domain test iddiaları ayrıca aynı kategoriye girebilir. Manuel eşleşme
  güncel bağımsız kimlik/TLS/yol doğrulaması değildir.
- **Doğrulanmış:** gerçek doğrulanmış kanıt yok; **0**. Bu faz doğrulanmış/live
  kanıt kabul eden bir yol eklemez. Desteklenmeyen VERIFIED iddiası kaynak bütünlüğü
  hatasıdır; gerçek doğrulama sayılmaz. Tam sentetik PASS de bu bölüme girmez.
- **Süresi geçmiş:** kanonik kaynakta STALE olan alan/bildirimler; şu anda 0.
  Gözlem tarihi UNKNOWN olduğu için bugünkü manuel kayıtlar STALE yapılmaz.
- **Doğrulanmamış:** UNKNOWN/UNVERIFIED/BLOCKED/CONFLICT veya desteklenmeyen alan
  durumları ve manuel bildirimler. Olumsuz manuel bulgular risklerden çıkarılmaz.
- **Sentetik inceleme:** yalnız SYNTHETIC_FIXTURE + SYNTHETIC_REVIEW_PASS referansları;
  gerçek kanıt veya operatör onayı değildir.
- **Zamanı UNKNOWN:** null gözlem zamanlı alan/bildirimler; şu anda 28. Doküman,
  ithal/commit tarihi veya API yanıt saati gözlem zamanı yapılmaz.

Kaynak ve güncellik ayrı boyutlardır: aynı manuel kayıt hem manuel hem stale veya
unknown-time olabilir. Kategori sayıları toplanarak benzersiz kanıt sayısı
çıkarılmaz. Aşama 25 mevcut süre/durum kararı otoritedir; bu özet yeni collector,
yeni saat veya ikinci bir freshness hesaplayıcısı eklemez.

Kaynak ID sayısı/çakışması, beklenen alan/grup/matris/manuel referanslar,
desteklenmeyen veya yanlış kaynaklı PASS, TLS kontratı, onay/yürütme/ağ/transport
kapalılığı uyumsuzsa `sources_complete=false` ve sabit integrity code gösterilir.
Bu kontrol gerçek rapor doğruluğunu/imzasını doğrulamaz. Kaynaklar tutarlı olsa bile
teknik uygunluk NOT_VERIFIED ve karar NO_GO kalır. Hesap paketi hash'i Aşama 25
politika/alan sözleşmesine referanstır; tüm gerçek kanıtların imzalı onayı veya yeni
bir yürütme token'ı değildir. Kaynakta olmayan credential/raw bilgi taşınmaz.

## Operatör ne sağlamalı, hangi kararları vermeli?

1. Mevcut onaylı offline envanter/lab/topoloji incelemelerinin gizli olmayan
   özetini, atanmış sorumlu rolünü ve gerçek UTC/ofset gözlem zamanını sağlayacak
   süreci belirlemeli. Henüz yetki yokken canlı sorgu yapılmamalı; eksik UNKNOWN kalmalı.
2. Tek hedef kimlik/model/6.49.19 build, yönetim adresi ve cihazın gördüğü V2 kaynak
   /32 bağımsız incelenmeli. Geçmiş 10.250.0.19 / V1 kaynak 10.250.0.1/32 otomatik
   hedef veya V2 izinli kaynak değildir. Account/service/input kaynak kanıtları ayrıdır.
3. Ayrı minimum V2 hesabı ve exact read,api özel grup adayı için tam ROS6 build
   lab, dosya/alan/yan etki ve dar print sınırı raporu gerekir. Mevcut webpanel
   write/test hesabı veya admin/reception kullanılamaz/değiştirilemez. read,api
   yeterliliği hâlâ kanıtlanmış değildir; eksik menü için policy artırılmaz.
4. A seçeneği için CA zinciri, SAN/IP, geçerlilik/kullanım/iptal, public pin ve
   TLS istemci lab kanıtları; ayrıca IPsec peer auth/yol ve V1 etkisizliği ayrı
   incelenmeli. Sertifikasız/kapalı API-SSL bildirimi bu kanıtları sağlamaz.
5. B seçeneği için IPsec auth/selector/NAT/iki yön/fail-closed yol, hesap/source,
   V1 ve STOP/geri dönüş kanıtları planlanmalı; fakat bu bir TLS istisnası değildir.
   Seçenek kararı ve güvenlik politikası/risk incelemesi ayrı insan sürecidir;
   UI'da seçim/onay verilmez.
6. Audit baseline, timebox/okuma bütçesi, STOP/iptal sorumlusu ve sadece yeni V2
   erişimine ait geri dönüş haritası incelenmeli. Güvenli yedeğin kurtarılabilirlik
   inceleme özeti gerekir; V2 yedek/export/private key toplamaz. V1 ve abone/audit
   kayıtları korunmalı; toplu restore planlanmamalı.
7. Gerçek pilot için aday/kapsam/yöntem/süre/change/iptal sorumluluğuna bağlı ayrıca
   açık kullanıcı/operatör onayı ve ayrı dar execution uygulaması/incelemesi gerekir.
   Teknik plan hazır olması bu onay veya yetki değildir. Bu faz onay almaz/saklamaz.

## Karar tablosunun güvenlik sınırı

| Karar boyutu | A — API-SSL 8729 | B — IPsec / API 8728 |
| --- | --- | --- |
| Mevcut teknik karar | NO_GO_APPROVAL_AND_LIVE_VERIFICATION_REQUIRED | BLOCKED_BY_CURRENT_TLS_CONTRACT |
| Politika | Doğrulanmış TLS şartı korunur; sertifika yok/servis kapalı bildirimi çözülmüş sayılmaz | Mevcut API_SSL/8729 sözleşmesi B'yi reddeder; otomatik istisna/fallback yok |
| Kanıt kapsamı | Mevcut Aşama 25 yirmi alan | Mevcut B kontrol listesi; TLS alanının listede olmaması TLS muafiyeti değildir |
| Operatör kararı | Ayrı PKI/servis change planı ve onayları | Önce ayrı güvenlik politikası ve risk kabulü incelemesi; burada izin verilmez |
| Onay / erişim | NOT APPROVED / CONNECTION DISABLED | NOT APPROVED / CONNECTION DISABLED |

Şifreleme, kimlik doğrulama, kaynak izolasyonu, ROS6, V1 etkisi ve operasyonel risk
karşılaştırma metni doğrudan Aşama 24 kaynaklarından gösterilir; yeni teknik
varsayım veya güvenlik muafiyeti eklenmez. [Ana pilot belgesi](CEBECI_TOWERS_PILOT.md)
ve [hesap/taşıma sözleşmesi](CEBECI_TOWERS_ACCOUNT_PREPARATION.md) geçerlidir.

Üç bağımsız kapı da kapalıdır: **teknik uygunluk NOT_VERIFIED**, **operatör onayı
NOT_RECORDED**, **gerçek yürütme DENIED**. Kaynak tutarlılığı veya tam sentetik
kontrol bu kapılardan hiçbirini açmaz. İlk kimlik/source/permission/TLS/IPsec/V1/
audit/rollback sorunu STOP; yeni gerçek okuyucu çalışsaydı yalnız onu durdurmak,
kayıtları korumak ve ayrı yetkiyle yalnız yeni V2 erişimini iptal etmek gerekirdi.
Bu görev hiçbir gerçek okuyucu/servis başlatmadı ve böyle bir iptal/change yapmadı.

## Aşama 26 salt okunur kabul

Yeni exclusive Playwright dalı yalnız bu birleşik görünümü kontrol eder; Aşama
21–25 kabul fonksiyonları çalıştırılmaz. Önceki teknik bölümler korunur. Kanıt
kategorileri/referanslar, A/B tablo, engeller, operatör soruları, safe next steps,
320/390/1440px ve yerel reload/baseline eşitliği denetlenir. Credential/hesap/fixture
veya başka veri oluşturulmaz; ortak kapanış eski abone/audit eşitliğini denetler.
Normal ofis WSL tek komut:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_PACKET_ONLY=1 ./browser-accept-demo.sh
```

Bu komut yerel V2 demo kabulüdür; CEBECI/V1/VDS'ye bağlanmaz, gerçek pilot başlatmaz.

## Aşama 27 — kritik kanıtlar için kabul ve tamamlama sözleşmesi

Başlangıç `a0aba30`. Kullanıcı Aşama 26 için **12/12 BROWSER PASS** bildirdi;
bu tarihsel yerel kabul, güncel cihaz veya gerçek yürütme onayı değildir.
Yeni sayfa, kanıt deposu veya ikinci karar modeli oluşturulmadı. Aynı ADMIN
paketindeki açılır kanıt alanları, mevcut yirmi kanonik alanın aşağıdaki özelliklerini
okur. 9 matris / 8 durum / 20 alan ve Aşama 22 kapalı dispatch sözleşmesi korunur.

Tek tanım `cebeci_account_preparation.EVIDENCE_RULES` içindedir; metadata aynı
`account_preparation.evidence_fields` satırına eklenir:

- `evidence_required`: önceden var olan beklenen kanıt, yeniden tanımlanmaz.
- `acceptance_criteria`: hangi eşleşme/kapsam/bağımsız incelemenin gerektiği.
- `expected_source`: kanıtı sağlaması gereken yetkili rol/rapor türü; gerçek kişi
  atanmış veya rapor alınmış sayılmaz. Kullanıcı adı veya credential istenmez.
- `completion_method`: mevcut onaylı offline kayıtlarla güvenli inceleme yöntemi;
  yeni gerçek sorgu veya change bu aşamada yapılmaz.
- `approval_requirement`: offline plan/rapor incelemesi ile ayrıca açık canlı
  doğrulama/change onayının ayrımı. Bu bir onay kaydı/endpoint'i değildir.
- `validity_seconds`: mevcut üst sınır **300 saniye**; eksik/gelecek zaman UNKNOWN,
  beş dakika veya daha eski STALE. İlgili değişiklik daha erken yeniden inceleme
  gerektirir; otomatik drift izlemesi yoktur. Eski matrisin lab raporu için daha
  uzun metadata süresi bu yirmi alanın 300 saniyelik kontrolünü gevşetmez.
- `stop_condition`: alana özel belirsizlik/uyuşmazlık/yan etki/ayrı onay eksikliği.

Kurallar `CEBECI_EVIDENCE_ACCEPTANCE_V1` revizyonuyla mevcut politika paketinin
hash'ine bağlanır. Kabul ölçütü/kaynak/yöntem/onay/STOP değişince eski iddianın paket
referansı CONFLICT olur; son kayıt kazanır veya sessiz onay yoktur. Mevcut karar
paketi, alan metadata'sının kanonik tanımla birebir eşleşmesini ve TTL'yi denetler;
eksik/değiştirilmiş kural `EVIDENCE_ACCEPTANCE_RULES_INVALID` ve kaynak bütünlüğü
BLOCKED üretir. Kurallar evidence input'u üzerinden değiştirilemez.

### Sekiz güvenlik gereksinimi ve operatörün tamamlayacağı kanıt

| Gereksinim | Alanlar ve kabul odağı | Kaynak / güvenli tamamlama | STOP |
| --- | --- | --- | --- |
| Ayrı V2 hesabı | ACCOUNT_SEPARATE, ACCOUNT_AUTH: V1 paylaşılmadan ayrı aday/kapsam/iptal sahibi ve sır almadan auth süreci | Hesap/güvenlik sahibinin mevcut maskeli envanter ve auth süreç incelemesi | Ortak V1 hesabı, credential talebi veya yetkisiz kullanıcı oluşturma |
| RouterOS 6 minimum API yetkisi | POLICY_EXACT, ROS6_LAB: exact özel read,api adayı ve tam 6.49.19 beş metadata/dosya/yan etki lab raporu | Mevcut kapsam/lab raporunu offline karşılaştır; üretimde negatif write testi yok | Ek write/policy/sensitive/password/reboot/test/başka policy veya lab/build eksikliği |
| TLS sertifikası/güven | TLS_CLIENT, TLS_CHAIN, TLS_NAME, TLS_VALIDITY, TLS_PIN: istemci/zincir/SAN-IP/zaman-kullanım-iptal/public pin ayrı | Tam build lab ve güvenlik sahibinin public metadata inceleme sonuçları; ham sertifika/private key alınmaz | Anonymous DH/bypass/legacy fallback, zincir/isim/pin uyuşmazlığı veya certificate=none |
| IPsec sınırları | IPSEC_AUTH, IPSEC_PATH: peer kimliği/auth ve iki yön/selector/NAT/tünel dışına kaçmama ayrı | Yetkili ağ/güvenlik sahibinin mevcut maskeli peer/yol incelemesi; ping/API/SA sorgusu yok | Active/ph2-count'u yeterli sayma, yanlış peer/yol veya PSK/SA talebi |
| Kaynak IP kısıtı | SOURCE_ACCOUNT, SOURCE_SERVICE ve ROUTER_IDENTITY: tek güncel V2 /32, hedef/kimlik/build, V1 etkisi ayrı | Mevcut bağımsız envanter/hedef-source inceleme raporları; geçmiş adres endpoint yapılmaz | Geniş/yanlış/UNKNOWN source veya eski V1 /32'yi otomatik devralma |
| V1 izolasyonu | V1_IMPACT: mevcut hesap/API/IPsec/abonelerin korunması ve etkisizlik baseline incelemesi | V1 izolasyon sahibinin zaten onaylı offline etki/baseline raporu; V1'e bağlanılmaz | V1 etkisi, ortak auth/yol veya baseline belirsizliği |
| Firewall | SOURCE_FIREWALL: tam input sıra/default politika/yol/yönetim source kapsamı | Yetkili firewall sahibinin mevcut sır içermeyen inceleme özeti; raw export veya kural değişimi yok | Görülen kısmi input kurallarından genel güvenlik sonucu çıkarma |
| Audit/STOP/geri dönüş | AUDIT, STOP_OWNER, ROLLBACK, OPERATOR_REVIEW: redaction/baseline/zaman, sorumlu/bütçe, yedek kurtarılabilirlik/yalnız yeni V2 iptal planı, ayrı onay/yürütme | Mevcut audit/operasyon/restore raporlarını masa başında incele; backup dosyası alınmaz | Eksik sorumlu/bütçe/audit, global/V1 restore veya plan incelemesini gerçek onay sayma |

Alan bazında ayrıntılı kaynak, kabul, TTL ve STOP ifadeleri doğrudan kanonik API
metadata'sından gösterilir; bu tablo ikinci bir makine karar modeli değildir.

### Hangi işlemler ayrıca açık onay gerektirir?

**OFFLINE_REPORT_REVIEW:** ACCOUNT_AUTH, POLICY_EXACT, ROS6_LAB, TLS_CLIENT,
AUDIT, STOP_OWNER, ROLLBACK için yalnız mevcut onaylı rapor/süreç incelemesi.
Bu kategori yeni sorguya veya canlı işlemlere izin vermez. Yeni lab/rapor veya
üretim verisi gerekiyorsa kapsam ayrıca incelenir; gerçek sisteme erişim yine ayrı
onay bekler. Tamamlandı diye işaretleme/sorumlu atama veya onay alımı bu UI'da yoktur.

**EXPLICIT_APPROVAL_BEFORE_LIVE_VERIFICATION_OR_CHANGE:** ACCOUNT_SEPARATE,
IPSEC_AUTH, IPSEC_PATH, SOURCE_ACCOUNT, SOURCE_SERVICE, SOURCE_FIREWALL,
ROUTER_IDENTITY, TLS_CHAIN, TLS_NAME, TLS_VALIDITY, TLS_PIN, V1_IMPACT.
Mevcut onaylı offline raporlar incelenebilir; yeni gerçek sorgu veya herhangi bir
hesap/sertifika/API/IPsec/firewall değişikliği gerekiyorsa **önce ayrı açık
kullanıcı/operatör onayı** şarttır. Bu görev o onayı almaz ve hiçbirini çalıştırmaz.

**SEPARATE_EXPLICIT_USER_APPROVAL_AND_EXECUTION_REVIEW:** OPERATOR_REVIEW.
Aday/kapsam/yöntem/timebox/change/iptal sorumluluğunun plan incelemesi, gerçek pilot
onayı değildir. Gerçek onay ayrı insan süreci ve dar yürütme uygulaması/incelemesi
gerektirir; onay/yürütme bayrakları bu tipin girdisi değildir.

### Değerlendirme sınırı ve taşıma kararı

Kabul metni tanımlamak, cihazdan kanıt almak veya TLS zincirini kriptografik olarak
uygulamada doğrulamak değildir. Gerçek kanıt intake/verifier eklenmedi. Tek karar
kaynağı olan mevcut `prepare` sonuçları ve `decision_packet` projeksiyonu kullanılır.
Manual/offline PASS hâlâ UNVERIFIED; eski manual tarihleri null/UNKNOWN; verified=0.
Tam sentetik kriter listesi bile NO_GO / NOT_VERIFIED / NOT_RECORDED / DENIED kalır.

A API-SSL yirmi alanın güncel teknik incelemesini ve ayrı onayı bekler; sertifikasız/
kapalı servis bildirimi çözülmüş sayılmaz. B IPsec/API 8728, IPsec/source/V1 kanıtı
gösterilse dahi **BLOCKED_BY_CURRENT_TLS_CONTRACT**; TLS istisnası/fallback değildir.
Aşama 22 API_SSL/8729 ve zorunlu chain/hostname sınırları gevşetilmedi.

Gerçek bağlantı, credential girişi, onay, hesap oluşturma, API test/deploy kontrolü,
migration/restart veya router komutu/script'i yoktur. Demo/audit kayıtlarına yazılmaz.

### Aşama 27 kabulü

Yalnız yeni salt okunur dal, aynı karar görünümündeki yirmi açılır kuralın
kanıt/kabul/kaynak/TTL/yöntem/onay/STOP içeriğini API'yle eşleştirir; önceki
senaryolar çalıştırılmaz. 320/390/1440px, UNKNOWN ve NO_GO, kapalı kontroller,
reload ve yönetim/abone/audit baseline korunması denetlenir. Normal ofis WSL:

```bash
cd ~/Codex-Projects/mikrotik-manager-v2 && V2_BROWSER_CEBECI_REQUIREMENTS_ONLY=1 ./browser-accept-demo.sh
```
