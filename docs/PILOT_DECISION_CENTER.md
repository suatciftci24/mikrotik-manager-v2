# Pilot öncesi karar merkezi — politika synthetic-pilot-review-v1

Bu aşama salt okunur değerlendirmedir. DEMO / SYNTHETIC, NOT CONNECTED ve APPROVAL
REQUIRED etiketleri korunur. Gerçek kaynak okunmaz, bağlantı/onay/pilot/rollback
başlatılmaz. Mevcut Aşama 19 mapping sözleşmesi ve Aşama 18 kayıtlı simülasyon raporu
kullanılır; yeni approval, migration, ingest veya business audit deposu yoktur.

## Kontrol listesi: PASS neyi kanıtlar?

| Kriter | Kaynak | Sonuç ve kapsam |
| --- | --- | --- |
| IDENTITY_MAPPING | Aşama 19 sentetik mapping | Fixture kimlik alanları tutarlıysa PASS; çakışma/eksik BLOCKED, değerlendirme yok UNKNOWN |
| REQUEST_AUTHORIZATION | Bu backend isteğinin require_router(can_view_reports) kontrolü | PASS yalnız güncel V2 isteğinin router scope'unu kanıtlar; cihaz hesabı erişimini kanıtlamaz |
| SOURCE_VALIDATION | Gerçek cihaz gözlemi yok | UNKNOWN; fixture ya da simülatör gerçek kaynak doğrulaması değildir |
| FRESHNESS | Gerçek kaynak gözlem zamanı yok | UNKNOWN; audit olay zamanı veya deterministik simülasyon saati güncellik ölçümü yapılmaz |
| AUDIT_MAPPING | Sentetik actor/time/result lineage | Alan sözleşmesi doğrulanırsa PASS; eksik/uyumsuz BLOCKED, veri yok UNKNOWN; canlı audit zinciri sertifikası değildir |
| ROLLBACK_PLAN | Aşama 19 plan tanımı ve rollback_executable=false | PASS yalnız planın tanımlı olduğunu gösterir; hedefe özgü prova ayrı UNKNOWN kriteridir |
| ISOLATION | Dış adaptör/write/execution=false ve NOT CONNECTED yapılandırması | PASS yalnız uygulama kapalı konfigürasyonu; çelişki BLOCKED ve NO_GO |
| SIMULATOR | Aynı owner routerın Aşama 18 kayıtlı run'ı | Varsa WARNING: sentetik saat/arıza senaryosu, canlı kanıt değil. Yoksa UNKNOWN. Başka routerın run'ı kanıt sayılmaz |
| ADMIN_APPROVAL | Gerçek onay kaydı yok | BLOCKED / APPROVAL_ABSENT; bu ekranda onay verme yok |
| PILOT_SCOPE | İmzalanmış tek-router hedef kapsamı yok | UNKNOWN; UI router filtresi imzalanmış kapsam değildir |
| TIMEBOX | Onaylı süre/durdurma sahibi yok | UNKNOWN; belgede önerilen süre uygulanmış politika değildir |
| ACCESS_LIMIT | Cihaz hesabı/tam salt okunur capability ölçülmedi | UNKNOWN; V2 ADMIN rolü cihaz yetkisi değildir |
| ROLLBACK_REHEARSAL | Hedefe özgü ölçülmüş prova yok | UNKNOWN; plan veya genel simülasyon sonucu prova olarak otomatik kabul edilmez |

UNKNOWN, WARNING veya BLOCKED koşullar sayısal puanla PASS'e çevrilmez. Ölçüm yokluğu
başarı, arıza veya bağlantı erişilebilirliği şeklinde yorumlanmaz.

## Veri karşılaştırması

Aşama 19 strict SYNTHETIC_FIXTURE doğrulaması yeniden kullanılır. Altı alan grubu:
router/management identity; PPPoE account/username/backend; profile; EXPIRE;
session; audit lineage. Her sonuç kaynak, gerekçe kodları ve PASS/WARNING/BLOCKED/
UNKNOWN taşır. İlgili domain count sıfırsa alan PASS sayılmaz. Session zamanı eksik
olabilir: WARNING/SESSION_TIME_UNKNOWN, hesaplanmış süre yoktur.

Çakışma, eksik alan/FK, tip/şema hatası ve LOCAL/RADIUS uyuşmazlığı mevcut validator'da
BLOCKED olur. DATE yalnız açık takvim günü, UNLIMITED açık null, UNKNOWN ayrı karardır.
Bozuk fixture sabit MAPPING_FIXTURE_INVALID kodu üretir; değer veya hata metni sızmaz.
Gerçek V1 alanları/DB/API veya V2 business kayıtları karşılaştırılmadı; canlı uyumluluk
iddiası yoktur. Alan tablosu ve pilot/rollback planı INTEGRATION_MANAGEMENT.md içindedir.

Validator fixture_digest ekler: strict fixture'ın kanonik JSON'undan SHA-256. Sır veya
raw fixture değerleri API'ye eklenmez. Karar evidence_hash politika, mapping digest,
source sonuçları, scoped simülasyon run kimliği ve gerekçeleri bağlar. Aynı kanıt aynı
sonucu/hash'i verir; örneğin EXPIRE günü değişse ve durum hâlâ PASS olsa bile hash
farklıdır. Hash imza, onay kaydı veya cihaz doğrulaması değildir; kalıcı review geçmişi
bu aşamada üretilmez. Mevcut rapor/audit geçmişine yazılmaz.

## Riskler ve karar

Riskler (severity, code, criterion) sırasıyla deterministik sıralanır. Aynı code/criterion
bir kez gösterilir. P1 kimlik çakışması veya izolasyon çelişkisi; P2 yapısal mapping
engeli/eksik gerçek onay; P3 eksik veya ölçülmemiş kanıt ve session belirsizliği;
P4 yalnız mevcut simülatörün cihaz kanıtı olmadığını hatırlatan uyarıdır. Bilinmeyen
mapping engeli de NO_GO üretir; yeni issue kodu sessizce uygunluğa düşmez.

| Karar | Hesaplama | Yetki anlamı |
| --- | --- | --- |
| NO_GO | Mapping BLOCKED, herhangi bir karşılaştırma BLOCKED veya izolasyon kanıtı çelişkili | İlerleme yok; engeller incelemeye alınmalı |
| REVIEW_REQUIRED | Değerlendirme eksik, domain UNKNOWN veya sentetik insan-review işareti tamam değil | Eksik kanıt/inceleme gerekli |
| ELIGIBLE_FOR_REVIEW | Altı sentetik domain PASS/WARNING ve Aşama 19 sentetik review işareti tamam | Yalnız **sentetik paketin insan incelemesine uygunluğu**; pilot uygunluğu/izni değildir |

ELIGIBLE_FOR_REVIEW sonucunda gerçek source/freshness/access/rehearsal hâlâ UNKNOWN ve
ADMIN_APPROVAL BLOCKED olabilir ve açıkça gösterilir. Bu sonuç eksik kanıtları kaldırmaz
ve pilot için kullanılabilecek GO değildir. Motorun GO durumu yoktur. execution_authorized
ve external_writes her sonuçta false'dur; hiçbir karar aktifleştirici olarak tüketilmez.

## Yetki, veri koruma ve arayüz

İki GET /system/pilot-decisions endpoint'i mevcut current_admin guard'ını kullanır.
VIEWER ve sınırlı ADMIN global metadata alamaz. Alt servis her router için
can_view_reports'ı plan/artefakt okumadan önce uygular; filtre/count/paging yalnız bu
scope'tadır. Görünmeyen hedef 404, görünen fakat rapor izinsiz hedef 403'tür. Her istek
mevcut auth tarafından güncel DB grant'leriyle çözülür; kararlarda oturum grant cache'i yoktur.

Plan/scoped simülasyon özeti dışında kaynak okunmaz. Uygun router yoksa artefakt bile
okunmaz. Mevcut 14 abone, kullanıcı, ayar, alarm, audit ve simülasyon rapor geçmişine
write yoktur. Alanlarda secret-reference, token, parola veya bağlantı endpoint'i yoktur.
Ekran yalnız filtre/sayfa ve readonly detay açar; kaynak/pilot/onay/deploy/migration
butonu veya POST endpoint'i eklenmedi. 60 saniye/focus/visibility yenilemesi yalnız GET'tir.

## Kabul ve sonraki kapı

Aşama 20 yalnız `V2_BROWSER_PILOT_ONLY=1 ./browser-accept-demo.sh` ile ayrı çalışır;
eski başarılı kabul paketlerini çalıştırmaz. Hazırlık/seed/approval yazması gerekmez.
Kararlar/UNKNOWN/risk sırası, scope paging/filtre, kanıt hash'i, readonly detaylar,
320/390/1440px ve mevcut admin/ayar/tercih/abone-audit baseline'ı kontrol edilir.
Gerçek browser çalışmazsa PASS değildir.

Gelecekte tek-router salt okunur pilot için belgelenmiş kapsam, süre, erişim, stop sahibi,
secret/TLS incelemesi, kaynak mapping ve baseline/rollback kanıtı ayrı doğrulanmalıdır.
İnsan review kararı yanında ayrıca açık dar yürütme yetkisi gerekir. Bu aşama bu
izinleri toplamaz veya verilmiş saymaz; canlı V1 geçişi başlamaz.
