# Merkezi AAA bellek içi simülasyon kabulü

2026-11-11 · Yalnız sabit sentetik fixture'lar. Canlı geçiş veya servis kabulü değildir.

## Sınır ve çalıştırma

`app.simulation.aaa_transition` mevcut AAA snapshot, kapsam, namespace ve
PreviewProof sözleşmelerini kullanır. Yeni abone deposu/replica, ORM, endpoint,
FreeRADIUS/RouterOS adapter çağrısı, timer veya kalıcı ledger yoktur. Girdi/çıktı
immutable Pydantic nesneleridir. Var olan snapshot değiştirilmez; authority ve
revizyon farkları yalnız `planned_changes` ve `simulated_final_*` alanlarındadır.

Bağımsız fixture matrisi repo kökünde opsiyonel olarak çalıştırılabilir:

```bash
PYTHONPATH=backend .venv/bin/python -B -m app.aaa_simulation
```

Bu komut dosya, ortam yapılandırması, PostgreSQL veya canlı hesap okumaz.
Girdi dosyası, parola/secret argümanı, ağ hedefi veya canlı çalışma modu yoktur.
Yalnız `.invalid` realm ve `aaa-memory` isimli bellek fixture'ları oluşturur;
güvenli senaryo özeti stdout'a yazılır. RADIUS Merkezi'ne yeni UI eklenmedi.

## Veri akışı

1. `SimulationRequest`: mevcut AaaSnapshot/PreviewScope/PreviewProof, açık
   UTC logical clock, yetkili fixture peer'ları ve namespace-complete beyanı.
   Tamlık varsayılan false; bildirilmezse simülasyon bloke olur.
2. Mevcut kapsam kontrolü konu ve her peer üzerinde önce çalışır. Tenant,
   depo veya router ihlalinde plan ve gizli peer detayı verilmez.
3. Mevcut proof doğrulaması, revizyon/hash kontrolü, LOCAL/tür/abonelik/realm,
   NAS/profil fixture yeterliliği, namespace ve süre kontrolleri çalışır.
4. Tam fixture'da LOCAL→RADIUS ve revision+1 **planı** ile beklenen audit fazları
   döner. Bunlar hesap oluşturma veya kaynak güncelleme komutu değildir.
5. `SimulationReceipt` yalnız çağıranın elindeki geçici çıktı nesnesidir.
   UUID/proof ve dondurulmuş senaryo içeriği eşitse tarihsel sonuç tekrar
   kullanılır; yeni audit beklenmez. Anlık clock/konu revizyonunun ilerlemesi
   yeni bir uygulama değildir. Yetki ve kimlik sınırı tekrar kontrol edilir.

Namespace policy/realm/NAS bilinmiyorsa çakışma yok kabul edilmez. Yetkili
fixture'larda aynı explicit key risk olarak, aynı plan+tür+mapping revizyonuna
farklı profil/policy hedefi de profil çakışması olarak bloke edilir. Peer veya
failure/compensation fixture içeriği değişirse aynı UUID farklı senaryo olur.
Farklı logical clock ise tarihsel receipt'in süresini yeniden değerlendirmez;
replay güncel hesabın durumunu veya canlı hazırlığı ispatlamaz.

## PASS / BLOCKED matrisi

Her satır bağımsız bellek denemesidir. Yalnız replay satırları önceki geçici
receipt'i açıkça paylaşır; process-geneli/account-geneli kayıt veya ledger yoktur.
Beklenen BLOCKED senaryosu bir kabul başarısızlığı değildir: korumanın çalışmasıdır.

| Senaryo | Beklenen sonuç | Kanıt / blokaj |
| --- | --- | --- |
| Tam PPPoE fixture | PASS | Sentetik ön kontrol, LOCAL→RADIUS planı, rev3→4 |
| Tam Hotspot fixture | PASS | Tür kaynaktan ayrı; aynı güvenli akış |
| Realm eksik | BLOCKED | REALM_MISSING / namespace belirsiz |
| NAS eksik | BLOCKED | NAS_FIXTURE_MAPPING_MISSING |
| Profil eksik | BLOCKED | PROFILE_FIXTURE_MAPPING_MISSING |
| UNKNOWN kaynak | BLOCKED | NOT_A_LOCAL_TRANSITION_CANDIDATE |
| UNKNOWN erişim türü | BLOCKED | ACCESS_TYPE_UNKNOWN |
| Tenant ihlali | BLOCKED | SCOPE_DENIED; hesap ID'siz beklenen deny audit'i |
| Router okuma yetkisi yok | BLOCKED | SCOPE_DENIED |
| Yinelenen username/realm | BLOCKED | VISIBLE_NAMESPACE_CONFLICT_RISK |
| Profil çakışması | BLOCKED | PROFILE_MAPPING_CONFLICT |
| Süresi dolmuş hesap | BLOCKED | SUBSCRIPTION_EXPIRED; inclusive günün UTC sınırı |
| Beklenen revizyon farklı | BLOCKED | STALE_OR_MISMATCHED_PROOF |
| Aynı UUID/aynı istek | PASS / replay | Yeni audit yok, önceki receipt aynı |
| Revizyon ilerledikten sonra aynı UUID | PASS / replay | Tarihsel sonuç; yeni geçiş veya yeni süre kararı yok |
| Aynı UUID/farklı içerik | BLOCKED | IDEMPOTENCY_CONFLICT; ilk receipt korunur |
| Namespace tamlığı beyan edilmemiş | BLOCKED | SYNTHETIC_NAMESPACE_INCOMPLETE |
| Target staged sonrası hata | BLOCKED / telafi modeli | LOCAL rev3 kalır; target telafisi yalnız iz |
| Source switch sonrası hata | BLOCKED / telafi modeli | LOCAL rev5; commit edilmiş model revizyonu geriye sarılmaz |
| Telafi revizyon çatışması | BLOCKED | READ_ONLY_RECONCILIATION_REQUIRED; otomatik source flip yok |

Matris 20/20 beklenen sonucu doğrular: 4 PASS ve 16 kasıtlı BLOCKED.
Ek testler yetkisiz peer, logical clock ilerlemiş replay, audit korelasyonu,
request/receipt değişmezliği ve sır/live-mode girdisinin reddini de sınar.

## Audit ve geri dönüş anlamı

`ExpectedAudit.origin=SIMULATED_EXPECTATION`; event UUID'si request UUID+fazdan
deterministik üretilir. Aktör sunucu kapsamından, zaman açık logical clock'tan
gelir. Fazlar PRECHECK/TARGET_STAGED/SOURCE_SWITCH/FAILURE/COMPENSATION olarak
**MODELED** etiketlidir; gerçek audit tablosuna yazılmaz. Replay ek olay üretmez.
Kalıcı exactly-once garantisi yoktur; CLI yeniden başlatılınca geçmiş receipt
otomatik yüklenmez. Çıktılar gerçek API receipt'i veya imzalı yetki tokenı değildir.

Telafi, revizyonu geri sarma veya tüm DB restore değildir. Source switch modeli
rev4'e geldiyse telafi rev5 olarak modellenir. Enjekte edilen telafi çatışması
durumunda son bilinen model state korunur ve salt okunur uzlaştırma gerekir.
Gerçek source/target varlığı, drift ve oturumlar bu simülasyonda sorgulanmaz.
Gerçek provider hatalarının dağılımı, dayanıklılık, yeniden başlatma kurtarması,
namespace tamlığı veya canlı rollback davranışı bu testlerle kanıtlanmaz.

## Canlıdan önce açık kalan kapılar

Her sonuçta `live_ready=false`, `external_writes=false` zorunludur. PASS etiketi
yalnız **Sentetik simülasyon başarılı** olabilir. Gerçek kimlik/NAS/profil,
credential ve AAA yazma yetkisi kanıtları UNVERIFIED kalır. Mevcut iş günü/hesap
durumu politikaları, namespace/normalizasyon, profil sürümü, secret erişimi,
durable idempotency/outbox, distributed uzlaştırma ve audit saklama kararları
[ana teknik tasarımdaki](CENTRAL_AAA_CONTRACTS.md) gibi hâlâ gereklidir.

Canlı FreeRADIUS/NAS testi, gerçek veri/credential erişimi, DB yazımı, migration,
deploy veya geçiş için ayrı açık hedefe özgü kullanıcı onayı gerekir. Hiçbiri
bu simülasyon kabulünden türetilmez. Mevcut 11 abone/admin/audit/yedek üzerinde
işlem yapılmadı; socket EPERM yeniden denenmedi. Frontend değişmediği için
TypeScript/build tekrarlanmadı; ilgili görünürlük/önizleme regresyonları çalıştı.
