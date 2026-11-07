# V2.6 SETTINGS_SCHEMA_MISSING — kök neden ve güvenli uygulama planı

2026-11-07 · temel `main-guncel/8bbd0c3` · **yerel hata/düzeltme PASS;
canlı nesne teşhisi ve uygulama BLOCKED**. Kullanıcı canlı
`GET /api/v1/preferences` için HTTP503 ve SETTINGS_SCHEMA_MISSING bildirdi.
Çalışan build SHA, DB/profil ve katalog çıktısı bu bildirimle verilmedi.
Canlıya bağlanılmadı, bu yanıt burada yeniden alınmadı.

## Kesin teknik anlam ve kaynak zinciri

`api/v1/system.py::preferences` → `system_settings.effective(user.id)` →
`identity.adapter()` → REPEATABLE READ / READ ONLY transaction → seçilen
adaptörün synthetic marker doğrulaması → `ready()` → default ve kişisel kayıt
okuması. `SettingsStateError` merkezi exception handler ile tam bildirilen
HTTP503/code/detail gövdesine dönüştürülür. GET/startup migration veya seed
çalıştırmaz; sessiz bellek/default fallback yoktur.

**8bbd0c3 kaynak sürümünde bu hata kodunun kesin koşulu:**

```sql
SELECT to_regclass('v2_demo.settings_records') IS NOT NULL
   AND to_regclass('v2_demo.settings_audit') IS NOT NULL;
```

Sonuç false ise kod SETTINGS_SCHEMA_MISSING üretir: aynı bağlantının DB'sinde
bu iki nitelikli ilişkiden en az biri çözümlenmiyordur. Şemanın tamamının
olmaması da aynı koşuldur. Kod tek başına hangisinin eksik olduğunu söylemez.
Bu kontrol fiziksel tablo tipi, kolonlar, index/constraint veya
settings_initialized değerini doğrulamaz; to_regclass bir view'i de bulabilir.

| Durum | Bu kaynakta beklenen ayrım |
| --- | --- |
| settings_records veya settings_audit ilişkisi yok | SETTINGS_SCHEMA_MISSING |
| İlişkiler var, `id='default'` yok | DEFAULT_SETTINGS_MISSING |
| Kayıt payload'ı Values/Personal sözleşmesine aykırı | SETTINGS_RECORD_INVALID |
| Sorgu/bağlantı/SQLAlchemy hatası, ör. gerekli kolon yok | Genellikle genel DATABASE_UNAVAILABLE; bu özel code kolonu teşhis etmez |
| settings_initialized kolonu/flag'i yok | ready() bunu okumaz; tek başına bu özel code'u üretmez |
| Oturum/yetki reddi | Ayrı 401/403; SETTINGS_SCHEMA_MISSING parola veya ADMIN yokluğu kanıtı değildir |

Aynı yanıtın canlıda hangi fiziksel nesneden kaynaklandığı ancak **çalışan
sürüm + seçilen schema/DB + mevcut katalog** birlikte doğrulanınca kesinleşir.
Burada kod yolunun anlamı kesin; canlı eksik nesnenin adı henüz kesin değildir.

## Kanıtlanan yerel ürün kusuru

Kimlik adaptörü `v2_demo` veya `v26_acceptance` seçebilir. `aa77855` ile kimlik
sorguları seçili şemaya bağlanmıştır; ayar servisi ise `v2_demo` sabitinde
kalmıştır. Yalnız v26_acceptance içinde eksiksiz ayar tabloları/default varken
eski preferences kodu aynı SETTINGS_SCHEMA_MISSING hatasını üretir. Tersine,
v26_acceptance ayarları eksikken diğer şemadaki tablolar eski hatayı maskeler
ve yanlış depodan ayar dönebilir. Her iki durum yeni testte düzeltme öncesi
başarısız oldu; bu varsayımsal bir kusur değildir.

Minimal yerel düzeltme: runtime settings ready/record/load/effective/save/
rejected/audit sorguları **adaptörün şema adı allowlist doğrulamasından geçmiş
store.schema değeriyle** nitelendirilir. Böylece okuma, aktör/yetki, yazma ve
audit aynı depoda kalır. Kullanıcı girdisi schema seçemez; bilinmeyen/enjekte
edilmiş schema SQL/bağlantıdan önce reddedilir. v2_demo davranışı korunur.

Salt GET düzeltip POST/audit'i eski şemada bırakmak yapılmadı. İzin, onay,
UUID/revizyon ve transaction/audit sınırları değiştirilmedi. Açık yerel
`initialize/prepare_acceptance` bakımının mevcut V2 demo hedef kapıları
korundu; V2.6 için kendiliğinden bakım veya yeni canlı CLI eklenmedi.

**Bu yerel kusur canlıda aynı durumun yaşandığını tek başına kanıtlamaz.**
Canlıda seçili v26_acceptance tabloları da gerçekten eksik olabilir. Yerel
patch mevcut olmayan tablo/default oluşturmaz; böyle durumda 503 sürer.

## Model ve migration sözleşmesi

Ayar deposu SQLAlchemy ORM tablo modeli değil, açık SQL + Pydantic
`Values/Personal` kullanır. Asıl DDL `005_demo_settings.sql` dosyasıdır
(ilk ekleme 80ca788; özel hata ayrımı d7ba0cb). Dosya `v2_demo` niteliklidir:

| Nesne | Gerekli biçim |
| --- | --- |
| settings_records | id text PK; payload jsonb NOT NULL; revision integer NOT NULL DEFAULT0/CHECK>=0; updated_at timestamptz NOT NULL DEFAULT now() |
| settings_audit | id uuid PK; record_id/actor_id text NOT NULL; previous_values jsonb nullable; new_values jsonb NOT NULL; result text NOT NULL CHECK SUCCESS/REJECTED; fingerprint text, response jsonb, occurred_at timestamptz NOT NULL, son alan DEFAULT now() |
| schema_state | settings_initialized boolean NOT NULL DEFAULT false; migration version1 satırını true yapar |
| Index | settings_audit(record_id, occurred_at DESC, id) |

005 tek başına zorunlu default kaydını eklemez. Yerel initialize veya Fresh
Pilot kurucusu bunu açık ayrı adımda yapar. V2.6 first-admin kurulumu yalnız
004/009 kimlik yükseltmelerini seçili şemaya uyarlar; 005 ayar kurulumunun
kanıtı değildir. Başarılı ADMIN login, ayar tabloları/default var demek değildir.
CREATE TABLE IF NOT EXISTS mevcut yanlış/kısmi kolonları onarmaz.

## Canlı erişim ve salt okunur ön kontrol

Belgelenen kabul adresi VDS loopback'idir; bu makinede doğrulanmış erişilebilir
canlı DB/HTTP oturumu yok. SSH/kimlik bilgisi/session dosyası kullanılmadı;
SQL/HTTP/socket denemesi, migration veya restart yapılmadı. Yeni DNS/socket
hatası yaşandı iddiası yok. Canlı nesne envanteri **BLOCKED**.

Hazırlanan [salt okunur katalog SQL'i](../tools/inspect-v26-settings-readonly.sql)
bağlantı kurmaz. Yalnız önceden doğru hedefi doğrulanmış yetkili operatör
oturumunda incelenmek içindir: READ ONLY/REPEATABLE READ, timeout, yalnız
DB/rol/port ve iki schema için ilişki/kolon/constraint/index/SELECT yetkisi,
sonunda ROLLBACK. Ayar, kullanıcı, parola/hash, abone veya audit satırı okumaz.
Bu SQL burada PostgreSQL üzerinde çalıştırılmadı; statik kontrolü PASS.

Uygulama öncesi gerekli kanıt:

1. Çalışan API/build ve yüklenmiş settings kaynak hash'i; gerçek deployment
   profili ve adaptör schema'sı. Disk SHA tek başına çalışan süreç kanıtı değil.
2. Gerçek DB/rol/port/PGDATA ve marker, önceki V2.6 hedef kapılarıyla eşleşmeli.
   İzole V2.6 profili ise DB mikrotik_v26_acceptance / rol v26_acceptance /
   port55433 / schema v26_acceptance beklenir. Fresh Pilot/V2.5 veya ofis
   DB'siyle karıştırılırsa STOP; bunlara bağlanıp kurulum yapılmaz.
3. Katalog SQL'iyle her iki tablonun varlığı ve tam DDL şekli. Tablo varsa,
   **yalnız seçilmiş şemada**, yetkili read-only transaction içinde default
   varlığı/revizyonu ve settings_initialized durumu ayrıca incelenebilir;
   payload sır/kişisel veri içerebileceğinden ham gövde rapora alınmaz.
4. Sonuç, kullanıcı 503'ünün saati/build'i ile ilişkilendirilmeli. Farklı
   örnek/sürüm veya önceki HTTP200 güncel 503'ün nedenini kapatmaz.

## Veri kaybı oluşturmayan uygulama kararları — henüz uygulanmadı

| Katalog sonucu | Gerekli işlem / duruş |
| --- | --- |
| Seçili v26_acceptance ayarları tam/valid, çalışan kod hâlâ v2_demo sabitinde | Yerel patch'in onaylı hedefe yayınlanması gerekir; DB migration gerekmeyebilir. Çalışan koda alma/deploy ve restart gerekiyorsa ayrıca açık onay. Diğer şemada kopya ayar deposu oluşturma. |
| Seçili şemada tablolar hiç kurulmamış ve önceki ayar/audit geçmişi olmadığı doğrulanmış | Doğrulanmış yedek sonrası 005'in yalnız allowlist seçili schema prefix'ine uyarlanmış additive sürümünü, incelenmiş default + bakım audit'iyle tek transaction'da uygula. Mevcut kayıtta ON CONFLICT DO NOTHING; asla overwrite. |
| settings_initialized=true ama tablo eksik veya geçmiş bekleniyor | Otomatik boş tablo/default/empty audit oluşturma. Eksik nesne/veriyi doğrulanmış yedekten seçici kurtarma planı; restore ayrıca kapsam/onay gerektirir. |
| Bir tablo var diğeri eksik, veya kolon/tip/constraint kısmi | IF NOT EXISTS ile kör ilerleme. Önce drift ve veri geçmişi belirlenir; eklemeli onarım/geri yükleme ayrı gözden geçirilir. Mevcut payload/revizyon/audit korunur; tahmini backfill yok. |
| Tablolar tam fakat default eksik/geçersiz | Bu farklı hata sınıfıdır. Şema migration'ı yerine ayrı onaylı default kurtarma; mevcut kullanıcı tercihleri ve özelleştirmeler korunur. Geçersiz kaydı otomatik silip varsayılan yazma. |
| Hedef/build/marker/yetki uyuşmuyor | STOP; otomatik GRANT, rol/parola değişimi, başka DB'ye yönelme veya güvenlik kapısı gevşetme yok. |

### Gelecekte onaylanacak transaction ve geri dönüş

- Önce doğru V2.6 DB için benzersiz/private, checksum'lı ve listesi doğrulanmış
  yedek; ayar nesneleri ile korunan kullanıcı/abone/audit için tutarlı ön-imaj
  özetleri. Yedek veya ham veriler Git'e/çıktıya alınmaz. Eski yedek ezilmez.
- Kesin SQL katalogdan sonra dondurulur; bu belge kör çalıştırılabilir bir
  canlı migration değildir. Fresh Pilot `preferences-repair-approved.py`
  yalnız kendi hedefi/v2_demo için eksik default onarır; V2.6 şema kurulumuna
  uygulanmaz. Mevcut ADMIN veya first-admin kurulumu tekrarlanmaz.
- Onaylı bakım: kısa lock/statement timeout, aynı v2-settings advisory lock,
  hedef/marker/schema/ADMIN doğrulaması, yalnız gerekli eksik DDL. Önce mevcut
  ayarlar/audit yeniden okunur; eşzamanlı değişiklik/driftte durulur. Seçili
  schema'daki Values-valid default ve audit birlikte doğrulanmadan COMMIT yok.
- **COMMIT öncesi hata:** ROLLBACK; eklenen DDL/default/audit/flag aynı
  transaction'da geri alınır. Eski veri ve diğer şemalar değişmemelidir.
- **COMMIT sonrası hata:** otomatik DROP/DELETE/tüm-DB restore yapılmaz.
  Sonradan yazılmış tercih/audit varken eski imaja dönmek veri kaybettirir.
  Veriler korunur; ayrı onayla kod/config ön-imajına dönüş veya ileri düzeltme
  seçilir. Önceki kod 503 veriyorsa bu kabul edilen güvenli BLOCKED geri dönüş
  durumudur, başarı değildir. Yedekten seçici kurtarma ancak değişen kayıtlar
  karşılaştırılıp ayrıca onaylanmış planla yapılır.
- Son kabul: mevcut yetkili oturumdan preferences HTTP200/storage_ready ve
  beklenen schema/build; GET öncesi/sonrası yazma/audit farkı0; kimlik/abone/
  diğer schema özetleri korunmuş; kayıtlar/UUID/revizyon/audit tutarlı. Eksik
  kanıtı PASS yapmak için default fallback veya yetki gevşetme yok.

## Dashboard geçmiş FAIL ile ilişki

Bu yeni kullanıcı 503 bildirimi güncel ve ayrı bir kanıttır. fffac4a olayında
preferences200/storage_ready ve Dashboard ERR_ASSERTION öncesi başarılı
preferences kontrolü kayıtlıdır. O özgün olayın nedeni SETTINGS_SCHEMA_MISSING
olarak değiştirilemez. Bugün aynı 503 olursa yeni runner'ın preferences.valid
HTTP200 kapısını düşürebilir; bu, geçmiş Dashboard assertion'ıyla aynı olay
veya aynı build/DB durumu değildir. NaN ve saat-yarışı düzeltmeleri korunur.

## Yerel doğrulama ve onay sınırı

- 9 yeni gerçek private SQLite ilişki testi: V2.6-only tablolar, yanlış şema
  maskesi, v2_demo izolasyonu, her eksik tablo, eksik default, invalid payload,
  presence-only kapısı ve schema injection reddi. İki routing senaryosu
  düzeltme öncesi FAIL/ERROR, sonrasında PASS.
- SQLite catalogue fonksiyonu, READ ONLY/REPEATABLE READ uyarlaması ve JSON
  decoding açık test shim'idir; PostgreSQL veya gerçek HTTP/auth kabulü değil.
  Gerçek route fonksiyonu/merkezi hata handler'ı bildirilen 503 gövdesini üretir.
  Yapılandırılmış PG engine connect/begin çağrıları testte yasaktır.
- 3 yeni v26 SQL-routing/audit/replay/rollback modeli testi PASS. Doğrudan
  etkilenen mevcut 8 transaction ve 2 initialize/migration-comment testi PASS.
  Toplam 22 hedefli kontrol; AST/read-only SQL/diff kontrolleri PASS.
  İki eski PG/HTTP test fixture'ına gerçek adapter gibi schema metadata'sı
  eklendi; o socket suite'leri çalıştırılmadı. Önceki Dashboard PASS tekrarı yok.

**Gereken canlı onay:** önce mevcut salt-okunur kapsamda hedef/katalog kanıtı;
ardından kesin nesneleri belirlenmiş V2.6-only yedek + gerekli additive bakım/
seçici kurtarma için yeni açık onay. Kod yayını ve gerekiyorsa servis restartı
ayrıca açıkça kapsanmalı. Bu görev bu işlemleri yapmaz veya onay istemeden
başlatmaz; canlı nesne belirlenmeden migration onayı uygulanabilir sayılmaz.
