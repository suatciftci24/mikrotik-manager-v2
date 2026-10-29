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
