# AAA kanonik plan ve atomik işlem sözleşmesi

2026-11-11 · `AAA_ATOMIC_PLAN_V1` / `AAA_JOURNAL_V2_FIXTURE`.
Yalnız `app.simulation.aaa_atomic` içinde caller-owned bellek modeli. API,
production repository, worker, migration veya gerçek adaptör eklenmedi.

## Mevcut sözleşmelerle ilişki

Önceki hazırlık yalnız adım öneriyordu; IsolatedJournal v1 plan hash veya account
CAS/outbox saklamıyordu. V1 ve demo UI değiştirilmez. `plan_from_preparation`
mevcut fixture preflight'ını yeniden doğrular; yalnız STAGE_DISABLED_TARGET
kararıyla yeni plan kurar ve karar fingerprint'ini bağlar. Hash yetki tokenı
değildir. Güncel sunucu kapsamı ve ayrı fixture izni her repository çağrısında,
idempotent replay dahil kontrol edilir. Gerçek yetki/kanıt denetimi uygulanmadı.

Yeni memory UoW, mevcut hesap sahibinin tek satırını temsil eden sentetik owner
fixture'ı kullanır; ikinci gerçek abone deposu değildir. Mevcut PostgreSQL veya
subscriber repository okunmaz. `origin=AAA_ATOMIC_MEMORY_ONLY`, `live_ready=false`
ve `external_writes=false` sonuç sınırıdır.

## Kanonik hash ve anahtarlar

Plan JSON'u tüm varsayılanlar/null değerler dahil model_dump(mode=json),
recursive sort_keys, separators=(',', ':'), ensure_ascii=true, allow_nan=false
ile ASCII byte dizisine çevrilip SHA-256 alınır. String case/Unicode
normalizasyonu yapılmaz; UUID/tarih biçimini mevcut strict sözleşme belirler.
Float/keyfi attributes/credential alanı yoktur. Bilinmeyen sürüm reddedilir.

| Hash kapsamı | Bağlanan bilgi |
| --- | --- |
| Sözleşme | AAA_ATOMIC_PLAN_V1 ve sıralı sabit adımlar |
| Tenant/abone | tenant + mevcut snapshot store/account/subscription kimliği; tenant eşitliği zorunlu |
| Sahiplik/revizyon | LOCAL→RADIUS, expected_account_revision (snapshot ile eşit), source/target provider revision |
| Kimlik/eşleme | Tüm frozen snapshot: EXACT identity/realm, NAS/profil mapping revizyonları, policy/süre ve mevcut referanslar |
| Ön koşullar | Preparation fingerprint, namespace ve authorization policy revision |

Plan hash request UUID/aktör/korelasyondan bağımsızdır. İstek fingerprint'i ise
journal sürümü + plan hash + aktör + korelasyon + aware UTC logical fixture
zamanını bağlar. Böylece aynı plan farklı request'lerde eşit hash taşır; farklı
aktör/korelasyonun aynı idempotency anahtarını kullanması kabul edilmez.

Journal v2 tasarım PK `(tenant,request_uuid)`; immutable plan hash/fingerprint,
operation revision, owner reservation revision ve monoton fence tutar. Aynı
anahtar+aynı envelope tarihsel journal sonucunu döndürür, yeni audit/outbox
üretmez. Değişen içerik CONFLICT. Farklı UUID aynı account'u atlayamaz: account
CAS ve aktif operation bağı vardır. Hash idempotency anahtarının yerine geçmez.
V1 satırları v2 olarak yorumlanmaz; gerçek şema evrimi ayrıca tasarlanmalıdır.

## Account-owner CAS ve transaction sınırı

1. Kapsam/izin doğrula; `(tenant,store,account)` sahibi ve LOCAL kaynak okunur.
2. `revision=expected AND active_operation IS NULL AND authority=LOCAL` CAS ile
   rezervasyon alınır; owner revision ve fence artırılır, kaynak LOCAL kalır.
3. Aynı transaction'da journal RESERVED + metadata audit + sıralı outbox oluşur.
4. Her teslim/sonuçta operation CAS, aynı aktif request, rezervasyon revision ve
   fence tekrar doğrulanır. Fark varsa yeni teslim/başarı yok; read-only uzlaştırma.
5. Önceki adımların açık APPLIED fixture sonuçlarından sonra COMMIT_OWNER_CAS,
   owner'ı RADIUS ve revision+1 yapar; kilidi kaldırır. Journal MODELED, ilişkili
   audit ve son outbox ACK **aynı transaction** içindedir. MODELED canlı başarı değil.

Örneğin owner rev3 LOCAL → rezervasyon rev4 LOCAL → tamamlanma rev5 RADIUS.
Eşzamanlı ikinci UUID tek owner CAS'te kaybeder. Sadece account_revision başına
unique ledger yeterli değildir: revision ilerlerken aktif operation bağı da
korunmalıdır. Journal anahtarları silinip yeniden kullanılmaz; otomatik purge yok.

Memory UoW tek RLock ve private kopyayı tek seferde yayınlar. OWNER/JOURNAL/
AUDIT/OUTBOX fault injection yayın öncesinde tüm candidate'ı atar. Bu, gerçek
SQL transaction rollback'i veya farklı DB bağlantılarındaki isolation testi değil.

## Outbox teslimi, sıralama ve telafi

- Outbox immutable ID'si request UUID + tenant + plan hash + sequence'den üretilir;
  tenant/request/correlation/plan hash ve fixture UTC zamanı taşır. Sonuç/ACK
  durumu ayrıca ilerler. Her operation için sequence1..4 sabittir:
  kapalı hedef hazırlama → LOCAL fence → RADIUS etkinleştirme → owner CAS.
  Sonuncusu yerel repository işlemidir, sağlayıcıya komut değildir.
- İlk ACK bekleyen kayıt teslim edilir. ACK kaybolursa aynı ID tekrar gelir;
  sonraki kayıt önceki ACK olmadan işlenmez. Aynı sonuçla tekrar ACK no-op;
  farklı sonuç, eski operation revision veya sıra dışı ACK reddedilir.
- At-least-once teslim vardır, exactly-once dış etki yoktur. Gerçek worker için
  claim/lease+fencing, provider idempotency ve stale worker reddi gerekir.
  Her gerçek sağlayıcı adımı ayrıca önceki hazırlıktaki çift kaynak koşullarını
  güncel kanıtla doğrulamalıdır; memory ACK bunları sağladığını ispatlamaz.
- NOT_APPLIED veya UNKNOWN/timeout, journal'ı RECONCILIATION'a taşır; sonraki
  teslimler durur, account rezervasyonu tutulur. Aynı request retry bu tarihsel
  durumu döndürür; kör yeniden çalıştırma veya LOCAL fallback başlatmaz.
- Telafi ayrı fixture permission ister. Plan hash, owner/operation revision ve
  fence eşitliği ile dış sonuç biliniyor + hedef kapalı + LOCAL geri getirildi
  kanıtları olmadan ilerlemez. Bunlar sahte kanıt beyanıdır, gerçek cihaz işlemi yok.
- Kabul edilen telafi owner revision+1 LOCAL, journal COMPENSATED, audit ve
  COMPENSATED outbox bildirimiyle tek commit olur. Eski ACK almamış intent'ler
  CANCELLED olur; eski ENABLE_RADIUS yeniden teslim edilmez. Bildirim teslim
  hatası tamamlanmış telafiyi geri açmaz; aynı bildirim ID'si tekrar teslim edilir.
- Owner commit sonrasında bu planla otomatik geri dönüş desteklenmez. Yeni
  owner/revizyon/kanıt ve ayrı sürümlü geri dönüş planı gerekir; revizyon geri
  sarılmaz. Veri drift'inde restore/overwrite yerine salt okunur uzlaştırma gerekir.

## Kanıt ve açık kalan tek aşama

11 yeni hedefli memory testi: canonical hash/JSON, preparation bridge, atomik
rezervasyon,4 fault sınıfı, replay/conflict, eşzamanlı tek CAS kazananı, sıra/tekrar
ACK, final owner commit rollback, owner drift, partial/UNKNOWN ve kontrollü telafi.
Socket/PostgreSQL/SQLite connect testlerde yasaktır. Eski AAA/demo testleri yok.

Gerçek journal v2/migration, PostgreSQL row lock/RLS, crash recovery/retention ve
worker/provider garantileri uygulanmadı. Sonraki tek öncelik: bağlantı açmadan
outbox worker lease/fencing ve stale teslim reddi sözleşmesini sahte adaptörle sınamak.
