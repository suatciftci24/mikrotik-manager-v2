# Merkezi AAA entegrasyon hazırlığı — v1

2026-11-11. **Yalnız izole fixture hazırlığı; canlı entegrasyon uygulanmadı.**
Backend, masaüstü,390px ve klavye demo kabulü kullanıcı kanıtı olarak korunur;
tekrarlanmaz. RADIUS Merkezi'nin “Gerçek AAA işlemleri bağlı değil” bilgisi ve
mevcut GET/demo akışı değişmez. Yeni endpoint, executor, migration veya job yok.

## Mevcut mimariye eklenen sınır

`app.simulation.aaa_integration_preparation` mevcut immutable AAA snapshot,
PreviewScope/Proof ve simülasyon ön koşullarını yeniden kullanır. Yalnız açık
`FakeAaaReadAdapter` kabul edilir; başka adaptörün read metodu çağrılmaz.
Adaptör sabit immutable gözlem döndürür. Hazırlayıcı **tek sonraki adımı önerir**;
öneriyi çalıştırmaz, hesabı veya journal'ı değiştirmez. Import/çalıştırma sırasında
config, credential, ağ, dosya veya DB erişimi yoktur. Yeni abone deposu yoktur.
`live_ready=false` ve `external_writes=false` değişmez.

## Gerçek entegrasyondan önce gereken sözleşmeler

| Sınır | Zorunlu sahiplik ve kanıt |
| --- | --- |
| Hesap/kimlik | Mevcut account sahibi; tenant+store+account+revision ve açık subscription ilişkisi. EXACT username/realm ve sürümlü namespace policy. Router adı/IP veya paket adından kimlik çıkarılmaz. Namespace çapında rezervasyon ve güncel collision kanıtı gerekir. |
| Yetki | Sunucunun mevcut oturum/tenant/router okuma kapsamı ile ayrı AAA geçiş yetkisi; kaynak ve hedef kapsamı, aktör, izin policy revizyonu ve hedefe özgü onay birlikte bağlanmalı. UI preview/proof veya fixture permission gerçek izin değildir. |
| NAS | Tenant kapsamlı router↔NAS ID/identifier eşlemesi, mapping revizyonu ve sağlayıcıdaki kimlik kanıtı. Yönetim IP'si NAS kimliği yerine geçmez. |
| Profil/süre | Mevcut plan↔AAA profil ID, mapping revizyonu, attribute-policy sürümü, erişim türü ve açık expiration/session politikası. Paket adı tek başına kanıt değildir; hesap etkinliği oturum bilgisi değildir. |
| Credential | Sahip servis ve aktarım uygunluğu açık olmalı; sır çözümleme yalnız gelecekte ayrı adaptör sınırında. Hazırlık sözleşmeleri parola, secret ref veya attribute dump taşımaz. Bu faz credential çözümlemez. |
| Kaynak | Tek account owner, source/target revision ve sağlayıcı gözlemi. Hedef kapalı staging ve eski kaynağı kalıcı biçimde devre dışı tutan, istek/hesap/revizyona bağlı fence kanıtı şart. Desteklenmiyorsa geçiş kapalı kalır. |
| Audit | Tenant/request/correlation, aktör/yetki revizyonu, hesap/depo, eski/yeni sahiplik ve revizyonlar, policy/mapping/plan hash, güvenli provider receipt özeti, UTC zaman ve APPLIED/REJECTED/UNKNOWN kanıtı. Ham sır/attribute loglanmaz. Owner+event+request aynı transaction'da olmalı. |

FixtureGates snapshot hash, aktör/tenant, aware son geçerlilik zamanı,
namespace/NAS/profil revizyonlarını bağlar. Güvenlik kapıları varsayılan false.
Credential sahipliği, kapalı hedef desteği, source fencing ve owner+audit atomikliği
fixture beyanıdır; gerçek provider kabiliyeti veya gerçek yetki kanıtı sayılmaz.
Gelecekte bu kanıtlar güvenilir sunucu/provider okuyucusundan gelmeli ve kaynak,
hedef, policy, namespace ve fence süreleriyle yeniden doğrulanmalıdır.

## Çift etkin kaynağı önleyen sıra

| Faz / doğrulanan fixture durumu | Önerilen tek adım |
| --- | --- |
| PREPARE: LOCAL açık, RADIUS yok | Hedefi **kapalı** hazırla |
| TARGET_STAGED: LOCAL açık, RADIUS kapalı | LOCAL'i devre dışı bırak ve fence kanıtını al |
| SOURCE_FENCED: iki taraf kapalı, fence aynı request'e bağlı | RADIUS'u etkinleştirme önerisi |
| TARGET_ENABLED: LOCAL kapalı/fenced, RADIUS açık | Mevcut owner revizyonu CAS + ilişkili audit commit önerisi |
| İki taraf açık / bilinmeyen durum / yanlış faz / fence yok | Yalnız salt okunur uzlaştırma |

Etkin iki kaynak hiçbir aşamada kabul edilmez. İki tarafın geçici kapalı olması
fail-closed kesinti modelidir; otomatik LOCAL fallback yoktur. Auth yanıtı ve
açık oturumların etkisi ayrı kanıt gerektirir; bu model oturum sonlandırmaz.

Gerçek router ve FreeRADIUS aynı transaction'da değildir. Okuma sonrasında
kaynak yeniden açılabiliyorsa tek seferlik “kapalı” gözlemi yeterli değildir.
Her gerçek adım, güncel revision/ETag ve kalıcı operation fence ile koşullu
olmalı; tek worker lease/fencing ve provider idempotency gerekir. Bunların
sağlayıcıda uygulanabildiği kanıtlanmadan bu sıra canlı güvenlik garantisi değildir.
Eski `FreeRadiusAdapter.create_identity` taslağı bu koşulları sağlamaz; canlı
executor olarak bağlanmayacak. Hedef sürüm/SQL/API/transport seçilmedi.

## İdempotency, journal ve hata davranışı

- Hazırlık fingerprint'i tüm request, proof, evidence, korelasyon, beklenen
  operation/source/target revision ve gözlemi bağlar. Event UUID aynı request,
  operation revision ve fingerprint için deterministiktir; gerçek audit değildir.
- `compare_prepared_steps`: aynı request+operation revision+içerik MATCH;
  değişen kanıt/sonuç CONFLICT; farklı operation revision DIFFERENT_STEP;
  farklı request UNRELATED. Karşılaştırma yetki, TTL veya kalıcı replay sağlamaz.
- Mevcut IsolatedJournal tenant/request PK, account-revision rezervasyonu,
  operation CAS ve atomik event sınırı korunur. JournalRequest şu anda yeni
  hazırlık fingerprint'ini saklamaz. Gerçek yürütücü öncesi sürümlü plan hash/
  evidence bağlama ve account-owner CAS transaction tasarımı gerekir. Yeni
  hazırlık çıktısı mevcut journal'a körlemesine uygulanamaz; ikinci ledger yoktur.
- Source/target/account/namespace revizyonu veya snapshot farkında uzlaştırma;
  izin/eksik/stale evidence veya eski proof durumunda öneri NONE. Adaptör
  okunmadan kapsam ve kanıt kontrol edilir. Timeout/UNKNOWN başarıya veya
  “uygulanmadı”ya çevrilmez; kör yeniden gönderim yapılmaz.
- COMPENSATING önce RADIUS'u kapatmayı, ancak kapalı hedef+geçerli source fence
  kanıtından sonra LOCAL'i açmayı önerir. Owner revizyonu geriye sarılmaz.
  Owner CAS sonrasında revizyon değişmişse otomatik restore yoktur: uzlaştırma
  ve ayrı geri dönüş planı gerekir. Tüm DB restore veya otomatik source flip yok.
- Restart/crash recovery, PostgreSQL lock/RLS/rol, outbox/lease, gerçek provider
  idempotency ve append-only audit dayanıklılığı bu testlerle kanıtlanmaz.

## İzole doğrulama ve sonraki kapı

8 yeni hedefli test: ileri adım sırası/fence, ayrı yetki+tenant+aktör, eksik/stale
kanıt, çift kaynak/UNKNOWN, source-target-account-namespace drift, güvenli telafi,
fingerprint/korelasyon/step karşılaştırması, gerçek adaptör ve sır/live input reddi.
Testlerde socket, PostgreSQL ve SQLite connect çağrıları yasaktır. Önceki AAA/demo
suite'leri tekrarlanmaz. 14 demo abone, kullanıcı, PostgreSQL ve audit okunmaz/yazılmaz.

Sonraki tek teknik öncelik: gerçek bağlantı açmadan, hazırlık plan hash'i ile
mevcut journal ve account-owner CAS/outbox sınırının sürümlü atomiklik tasarımı.
Canlı bağlantı, credential veya migration bu hazırlıktan yetki türetmez.
