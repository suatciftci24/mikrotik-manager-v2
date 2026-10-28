# Entegrasyon yönetimi ve güvenli geçiş planı — Aşama 19

Bu belge ve ekran yalnız tasarımdır. Kaynak SYNTHETIC_FIXTURE, bağlantı NOT CONNECTED;
RouterOS/RADIUS adaptörleri ve dış yazma kapalıdır. V1 DB/API/VDS sorgusu, veri aktarımı,
pilot başlatma, gerçek onay toplama veya rollback çalıştırması yoktur.

## Hazırlık envanteri

Envanter mevcut V2 router kimliklerini yalnız izin kapsamı olarak kullanır; gözlem
veya bağlantı bilgisi üretmez. Yönetim kimliği opaque fixture-management-* anahtarıdır;
adres/login/parola/PSK/API anahtarı/secret-reference alınmaz veya saklanmaz.

| Durum | Anlamı | Gerçek bağlantı/yürütme yetkisi |
| --- | --- | --- |
| DEMO_ONLY | Sentetik alan eşleştirmesi henüz değerlendirilmedi | Yok |
| READY_FOR_REVIEW | Sentetik bundle tutarlı, insan incelemesi bekleniyor | Yok |
| APPROVAL_REQUIRED | Yalnız fixture içindeki sentetik inceleme işareti tamam | Yok; ayrıca gerçek kapsamlı onay gerekir |
| BLOCKED | Eksik/çakışan/uyumsuz alan veya bozuk fixture | Yok |

Hiçbiri ONLINE, erişilebilir veya gerçek entegrasyona hazır olunduğunun kanıtı değildir.
Demo ilk router tutarlı/bekleyen, ikinci profil eksik ve LOCAL/RADIUS uyumsuz, üçüncü
henüz değerlendirilmemiş, dördüncü yalnız sentetik review işaretli örnektir.
Eksik pilot gereksinimleri tüm örneklerde açık kalır; gerçek onay kaydı yoktur.

## V1 / V2 alan sözleşmesi (yalnız sentetik örnek)

V1 alan adları kavramsaldır; canlı V1 şeması incelenmedi. Gerçek şemaya uyum iddiası
yoktur. İleride ayrı onaylı fixture/export incelemesinde bu sözleşme sürümlenmelidir.

| Kavramsal V1 alanı | V2 plan hedefi | Kural / belirsizlik |
| --- | --- | --- |
| router.identity | router.id | Açık bire bir mapping; IP, hostname veya ad benzerliğiyle otomatik kimlik çıkarma yok |
| yönetim kimliği | management_identity_plan | Yalnız opaque kimlik; credential veya bağlantı endpoint'i kapsam dışı |
| PPPoE account id + router | account_mapping_key | Kaynak ve hedef tekil; username tek başına kimlik değildir; router/account namespace açık |
| PPPoE username | plan kullanıcı kimliği | Eksik alan BLOCKED; aynı routerda çakışma BLOCKED |
| backend authority | LOCAL / RADIUS | Kaynak ve hedef aynı tek otorite; eksik/uyumsuz BLOCKED, otomatik radius→local dönüşümü yok |
| profil | profile_mapping_key | Açık eski/yeni profil eşlemesi; eksikse BLOCKED; cihazda profil oluşturulmaz |
| EXPIRE | expires_on + expiry_mode | DATE yalnız YYYY-MM-DD takvim günü; Europe/Istanbul gün sonu anlamı ayrı incelemeye tabi. Epoch/timestamp sessizce güne çevrilmez |
| limitsiz EXPIRE | expiry_mode=UNLIMITED | Tarih null olmalı; UNKNOWN ayrı ve BLOCKED; boş değer limitsiz sayılmaz |
| session id + account id | session lineage | Tekil kaynak session, account FK; başlangıç/bitiş timezone-aware UTC. Eksik zaman UNKNOWN, süre uydurulmaz; ters interval BLOCKED |
| audit id | audit lineage key | Tekil geçmiş olay kimliği, aktör/zaman/sonuç zorunlu; önceki audit yeniden yazılmaz |
| audit actor/time/result | tarihsel kanıt sözleşmesi | Kaynak aktör kimliği, UTC ve SUCCESS/REJECTED korunur; UNKNOWN/missing BLOCKED; kaynak kimliği V2 işlem yapan aktör gibi gösterilmez |

Router kaynak/hedef veya yönetim kimliği çakışması, account kaynak/hedef/aynı-router
username çakışması, session/audit ID tekrarı ve eksik FK'ler bundle doğrulamasında
BLOCKED olur. İki routerdan gelen aynı hedef account ID de reddedilir. Bundle yalnız
çağıranın izinli sentetik kapsamıdır; daha geniş veri incelemesi ayrıca izin ister.
NOT_EVALUATED ile sıfır hata sonucu birbirine karıştırılmaz. Eksik session zamanları
ayrı sayı olarak gösterilir, başarılı doğrulama bunları ölçülmüş yapmaz.

## Gelecekte tek-router salt okunur pilot ön koşulları

Aşağıdakiler bu aşamada yerine getirilmiş veya yetkilendirilmiş değildir:

1. Tam kapsamlı ADMIN tarafından **tek router** kimliği, salt okunur capability listesi,
   hedef ortam ve sorumlu operasyon kişisi açıkça belirlenmeli. İkinci router veya
   RADIUS kapsamı ayrıca onay gerektirir; ad benzerliğiyle hedef genişletilemez.
2. Eşleştirme sürümü/hash'i, çakışma çözümü, backend otoritesi ve EXPIRE anlamı insan
   incelemesinden geçmeli. Kaynak veri gerçek değilse gerçek kaynak uygunluğu UNKNOWN'dır.
3. Başlangıç/bitiş zamanı, durdurma sahibi ve erişim bütçesi yazılmalı. Önerilen ilk
   tasarım üst sınırı 15 dakikadır; bu runtime politikası veya verilmiş izin değildir.
4. Ayrı secret store/redaction/TLS/client timeout değerlendirmesi yapılmalı. Sır
   değerleri API/audit/log veya plan dosyasına konmamalı; bu faz resolver sağlamaz.
5. V2 mevcut kullanıcı/14 abone/ayar/alarm/audit baseline'ı onaylı yerel prosedürle
   alınmalı; yeni pilot kayıtları ayrı pilot_run_id namespace'inde karantinada olmalı.
6. Fixture üzerinde rollback provası ve timeout/access denied/yanlış kimlik testleri
   tamamlanmalı. Mevcut Aşama 16–18 sözleşme/revision/idempotency sınırları korunmalı.
7. Tasarım review kaydından **ayrı**, süreli ve dar kapsamlı açık yürütme yetkisi gerekir.
   Otomatik başlangıç, review sonucu veya bu belge bu yetkiyi vermez.

Gelecekteki review kaydı yalnız review_id, kapsam kimliği, sözleşme sürümü, süre,
inceleyen ve karar kanıtı taşıyabilir; credential taşımaz. REVIEWED/APPROVAL_REQUIRED
kaydı execution_authorized=true veya kullanılabilir bağlantı token'ı değildir.
Bu fazda approval tablosu, mutator endpoint'i, onay butonu veya gerçek izin kaydı yoktur.

## Durdurma ve geri dönüş matrisi (çalıştırılmamış plan)

| Tetikleyici | Gelecekte izinli pilot sırasında karar | Bu aşamadaki durum |
| --- | --- | --- |
| bağlantı kaybı / timeout | Yeni okumayı durdur; son başarılı snapshot'ı stale/fallback olarak ayır, DOWN uydurma | Plan; bağlantı yok |
| erişim/yetki hatası | Yeniden kimlik denemesi veya yetki genişletme yapma; pilotu durdur, ayrı inceleme iste | Plan; credential yok |
| veri tutarsızlığı / cursor-revision çakışması | Candidate commit etme; son başarılı namespace ve audit kanıtını koru | Mevcut offline reconcile/CAS yaklaşımı referans |
| yanlış router/account eşleştirmesi | Akışı durdur; yeni pilot kayıtlarını karantinaya ayır; global business verisine taşıma | Plan; aktarım yok |

Kavramsal sıra: okumayı durdur → dış adaptörleri kapalı tut → sır içermeyen
kanıt/cursor/revision ve orijinal audit'i koru → yalnız yeni pilot namespace'ini ayır →
pilot öncesi V2 baseline eşitliğini kontrol et → yeni review ve ayrı yürütme yetkisi
olmadan yeniden başlama. V1 otoritesi bu aşamada hiç değiştirilmez. Üretimde restore,
restart, migration veya kullanıcı/abone/audit silme komutu yoktur; gerekirse gelecek
ayrı kapsam ve onayda planlanmalıdır. Rollback geçmiş audit'i silmez veya sahte başarı
üretmez; REJECTED/FAILED kanıtı korunur.

Gelecekte idempotency anahtarı kaynak kimliği + router + kaynak event ID/revision
ve pilot namespace'ini kapsamalıdır. Aynı transaction'da candidate/source cursor,
projection ve audit birlikte commit/rollback edilmelidir. Mevcut reducer/ledger,
Aşama 18 simülatör provası ve scope sınırları yeniden kullanılmalıdır; bu faz kalıcı
canlı ingest veya exactly-once entegrasyon garantisi sunmaz.

## Salt okunur uygulama ve kabul

GET /system/integration-management ve /{router_id} mevcut current_admin guard'ını
kullanır; VIEWER/sınırlı ADMIN 403 alır. Alt servis owner can_view_reports kapsamını
filtre/sayfa/toplamdan önce uygular. Görünmeyen hedef 404, görünür fakat rapor yetkisiz
hedef 403. Her istek mevcut auth ile güncel yetkiyi alır. Scope dışı fixture okunmaz.
Bozuk fixture sabit MAPPING_FIXTURE_INVALID koduyla yalnız ilgili routerı BLOCKED yapar;
hassas hata metni veya gizli değer yanıtlanmaz.

Ekran yalnız görüntüleme, filtre, sayfa ve detay aç/kapat kontrolü içerir. Plan ekranı
GET/refresh sırasında audit/ayar/abone yazmaz. Aşama 19 kabulü:
`V2_BROWSER_MANAGEMENT_ONLY=1 ./browser-accept-demo.sh`.
Hazırlık/seed/fixture yazması gerekmez; yalnız bu ekran, mapping/pilot/rollback detayları,
320/390/1440px ve mevcut kullanıcı/ayar/tercih/abone-audit baseline'ı doğrulanır.
Gerçek browser çalışmazsa PASS sayılmaz.
