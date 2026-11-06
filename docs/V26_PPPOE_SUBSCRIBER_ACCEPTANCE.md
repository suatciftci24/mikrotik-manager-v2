# V2.6 PPPoE abone yönetimi — yerel kabul — 2026-11-05

LOCAL PASS: paket/uzatma/audit tutarlılığı. Başlangıç `main-guncel`,
`85c48498679cc11b72dadea2777ca8182c095400`. Kullanıcının mevcut izlenmeyen
bileşeni ve operatör yedekleri korunur, commit kapsamına alınmaz.

Paket değişikliğinde eski/yeni paket ve o andaki bitiş; tarih değişikliğinde
eski/yeni bitiş ve o andaki paket mevcut JSON audit alanlarında birlikte tutulur.
UTC işlem zamanı ve sunucunun yetkilendirdiği aktör ID'si korunur. Eski düz ve
structured audit alanları tek güvenli projeksiyonda birleştirilir; detay ve merkezi
geçmiş aynı kanıtı kullanır. Eksik tarihsel paket güncel hesaptan tahmin edilmez.
Detayda tarih değişince paket satırının gizlenmesi kaldırıldı. İstanbul gösterimi
UTC gün sınırını geçen `21:30Z → ertesi gün 00:30` örneğiyle doğrulandı.

Gün bazlı uzatma `max(mevcut bitiş, Europe/Istanbul bugünü) + gün` kuralını,
server preview/revizyon/kaynak kontrolünü, merkezi ADMIN ve ayrı işlem başlığını
korur. Bilinmeyen bitişte özel tarih/onay gerekir; arayüz doğrudan özel tarih
seçer. Bozuk tarih, yıl taşması ve geçersiz süre kontrollü hata üretir.
Eski quick özel tarih işlemi `DATE_EDIT` sözleşmesini korur; özel tarih düzenleme
ile gün bazlı uzatma aynı işlem türü olarak sunulmaz. Paket işlemi tarihi değiştiremez.
Eski/yeni snapshot biçimleri desteklenir; paket audit'indeki tarih değişimi reddedilir.

Doğrulama:

- Mevcut 40 hedefli backend kontrolü: `test_subscriber_renewal`,
  `test_subscriber_daily_management`, `test_subscriber_center`,
  `test_demo_management`, `test_quick_actions`. Başarısız kapsam düzeltildikten
  sonra yalnız ilgili 18 test tekrar edildi ve geçti.
- Yeni `test_v26_subscriber_consistency`: dört senaryo hem disposable SQLite
  hem PostgreSQL 16 üzerinde, toplam sekiz PASS. Tüm ASGI middleware/route,
  şema ve merkezi yetkilendirme zinciri kullanıldı; yalnız oturum kimliği
  sentetik dependency ile sağlandı. Gerçek login veya HTTP socket kabulü değildir.
- API paket → uzatma → detay/merkezi geçmiş, UTC/aktör, bilinmeyen tarih,
  taşma, yetkisiz/başlıksız/onaysız ret, kalıcı retry ve audit rollback PASS.
  Gerçek SQL audit INSERT hatasında kayıt/revizyon/geçmiş değişmedi; aynı istek
  hata kalkınca bir kez uygulandı. SQLite, PostgreSQL yerine sunulmadı.
- PostgreSQL `/tmp/v26-subscriber-*` altında yeni, private Unix socket kullanan
  geçici kümedir; mevcut URL/DB/14 demo abone kullanılmadı. Sadece ORM metadata
  ile test tabloları oluşturuldu; migration dosyası çalıştırılmadı. Küme test
  bitiminde durdurulup geçici dizin temizlendi.
- Beş hedefli frontend dosyası PASS: subscriberCenter, subscriberRenewal,
  subscriberDailyManagement, subscriberManagement, quick. React etkileşim/SSR
  testleri gerçek tarayıcı görsel kabulü değildir. Eski test aracının CSS loader
  eksikliği ve değişiklik yapmadan kayıt bekleyen fixture'ı düzeltildi.
- TypeScript/Vite build PASS; mevcut >500 kB bundle uyarısı devam eder.
- `git diff --check` PASS.

Sınırlar: ek eski `test_demo_expiry` paketi bu ortamda eksik `httpx2` nedeniyle
import edilemedi; PASS sayılmadı. Yeni ASGI kabul aracı harici HTTP istemcisi
gerektirmez. Sandbox asyncio worker bekleme engeli sonrasında aynı sentetik
kabul izinli çalıştırıldı; güvenlik kontrolü/test beklentisi gevşetilmedi.
Tarayıcı görsel kabulü, gerçek login, canlı API/DB/cihaz kabulü yapılmadı.

V1, V2.5 pilot, V2.6 VDS, router/RADIUS, mevcut DB/veriler, servis ve deploy
üzerinde işlem yok. Migration/seed uygulanmadı. Önceki VDS kimlik kurulumu
PGDATA uyuşmazlığı ve tarihsel Dashboard BLOCKED/ROLLBACK kayıtları değişmedi.
Sonraki adım gerekirse ayrı yetkili tarayıcı görsel kabulüdür; canlıya geçiş bu
paketin tamamlanma koşulu veya yetkilendirmesi değildir.


## Günlük işlemde belirsiz sonuç ve bağlı görünüm yenilemesi — 2026-11-06

Başlangıç 963c453. Yerel UI eksikliği: kayıp/bozuk POST yanıtında yalnız hata
metni kalıyor, düğme yeniden uygula diyordu ve bağlı kaynaklar invalidate
edilmiyordu. İşlem sunucuda uygulanmış olabileceğinden açık belirsizlik mesajı
ve aynı UUID'lerle sonuç alma eklendi; her deneme sonunda kaynaklar yenilenir.
Sayfalı liste adreslerinin query yüzünden invalidate olmaması da düzeltildi.

PASS: üç yeni gerçek React handler/SSR senaryosu (kayıp yanıt, bozuk JSON,
uyuşmayan receipt), iki yeni kaynak yolu sınırı testi; TypeScript ve Vite build,
diff kontrolü. Retry gövdesi birebir aynı, otomatik retry yok, sahte receipt
modelinde tek uygulama ve belirsizliğin sonuç alınca kalkması doğrulandı.
Fetch/receipt sentetiktir; gerçek DB atomikliği, socket veya tarayıcı kabulü
değildir. Eski başarılı testler tekrarlanmadı; typecheck yeni hook değişikliğinden
sonra tekrarlandı. Mevcut >500kB bundle uyarısı sürer. Canlı/SSH/DB/servis yok.
ADMIN doğrulaması PASS, gerçek PostgreSQL/HTTP kabulü BLOCKED kalır.


## Tekil uzatmada güvenli sonuç alma — 2026-11-06

Başlangıç cfe1638. Önizleme istek alanlarını sabitler; kayıp/bozuk/eşleşmeyen
sonuç belirsiz gösterilir. Sonuç ID/tarih/kaynak/artan revizyonla doğrulanır;
bağlı görünümler başarısız yanıt dahil her gönderimden sonra invalidate edilir.

PASS: altı yeni React handler/SSR kurtarma senaryosu (yanıt kaybı, bozuk JSON,
yanlış abone/tarih/kaynak/revizyon); doğrudan etkilenen mevcut tek uzatma testi1;
TypeScript/Vite build ve diff. Eski fixture yanıtı gerçek backend sözleşmesindeki
artan revizyonla düzeltildi. Yenilenen props'a rağmen retry body aynı; otomatik
retry/çift tıklamayla ikinci gönderim yok. Receipt modeli tek uygulama gösterir;
gerçek DB/HTTP/browser PASS değildir. İlk yeni test dosyası yanlış çalışma
diziniyle yazılamadı; yol düzeltildi ve yalnız eksik yeni altı test çalıştırıldı.
Önceki günlük/PGDATA/ADMIN PASS testleri tekrarlanmadı. Bundle >500kB uyarısı sürer.
ADMIN doğrulaması PASS, gerçek PostgreSQL/HTTP kabulü BLOCKED korunur.


## Oluşturma/düzenlemede gerçek receipt sorgulama — 2026-11-06

Başlangıç d0a1e03. İki editör de UUID/hedef/tam JSON'u önizlemede sabitler;
belirsizlikte yalnız GET ile aynı UUID receipt'i sorgulanır. Kaybolan/15sn timeout/
bozuk/uyuşmayan yanıt başarısız sayılmaz; formu değiştirerek yeni POST kapalıdır.
İlk POST'un kesin istemci reddi FAILED, eşleşen receipt SUCCESS, eksik/okunamayan
sonuç UNKNOWN/UNCERTAIN'dir. Read401/403 ilk POST'un sonucu olarak yorumlanmaz.

Kalıcı sentetik save yanıtı aynı transaction'da mevcut audit JSON'una kaydedilir;
UUID+aktör+hedef+komut fingerprint'i farklı isteği reddeder, özgün receipt sonraki
editlerden sonra da okunur. Legacy requests/events yanıtı yeniden kullanılır.
İki GET güncel yetkiyi ve aktörü kontrol eder; legacy router scope ve rapor geçmişi
projeksiyonu korunur. Eski auditler değiştirilmez; eksik receipt bilinmiyor kalır.

PASS: 15 yeni frontend handler/SSR testi (iki depo x create/edit x kayıp/bozuk/
uyuşmayan yanıt =12; UNKNOWN/read403, kesin422, abort timeout =3). Tek POST,
manuel GET, sabitUUID, çift tıklama engeli, başarı sonrası yazmama ve bağlı
Dashboard/liste/detay/geçmiş invalidation doğrulandı. 9 yeni backend kontrolü:
özgün create/edit receipt ve replay; başka aktör/UUID/komut; audit rollback;
merkezi ADMIN; legacy readonly SQL ve scope; VIEWER; receipt UPDATE arızası
rollback; SELECT-only lookup; legacy izin iptali. Workspace disposable SQLite,
legacy SQL mock'tur. Gerçek PostgreSQL/socket/tarayıcı PASS iddiası yoktur.

TypeScript kontrolündeki generic undefined daraltması düzeltildi; sonraki kontrol
ve TypeScript/Vite build PASS, diff PASS. Önceki PASS testleri tekrarlanmadı.
Yeni backend kontrolleri 6+2+1 olarak yalnız eklenen kapsamlarla çalıştırıldı.
Mevcut >500kB bundle uyarısı sürer. ADMIN PASS, gerçek PG/HTTP BLOCKED korunur.
V1/V2.5/VDS/SSH/gerçek router/RADIUS/IPsec/veri/parola/migration/restart/deploy yok.


## Toplu işlem ve tekil uzatmada yalnız GET receipt — 2026-11-06

Başlangıç159c50b. İki akışın kayıp/timeout/bozuk HTTP yanıtından sonra aynı UUID
ile yeniden POST gönderme davranışı kaldırıldı; yalnız aktöre/yetkiye bağlı GET
sonuçları kullanılır. Toplu işlem kesin satırları korur, yalnız belirsizleri en
fazla5 eşzamanlı GET ile okur. Tekil uzatma özgün yanıtı mevcut audit JSON'una
aynı transaction'da kaydeder; sonraki edit sonrası da orijinal sonuç okunur.
Yeni tablo/migration/backfill yok; oluşturma/düzenleme recovery kodu değişmedi.

PASS: 7 yeni backend senaryosu: uzatma özgün receipt/replay/sonraki edit;
foreign/unknown/başka tipUUID; aynıUUID farklı komut/aktör reddi; receipt UPDATE
arızasında tarih/revizyon/audit rollback; toplu SUCCESS/FAILED/UNKNOWN salt okunur
okuma; uzatma SELECT-only/tip ayrımı; güncel ADMIN/aktör route kontrolü.
Disposable SQLite kullanıldı; gerçek PG veya socket sonucu değildir.

PASS: 16 değişen/yeni frontend senaryosu: 7 uzatma recovery (6 eski POST-replay
beklentisi GET'e uyarlandı + timeout1), uzatma önizleme/GET1, toplu kesin sonuçta
tekrar göndermeme1, toplu kayıp/bozuk/yanlış receipt/timeout4, kısmi sonuç/bozuk
GET/en fazla5 concurrency-abort3. Gövdesiz GET, sabitUUID, tekPOST, doğru durumlar
ve kaynak invalidation kanıtlandı. Genel eski suite/PGDATA/ADMIN/create-edit
PASS testleri tekrarlanmadı. TypeScript ve son Vite build/diff PASS.
Mevcut >500kB bundle uyarısı sürer.

İlk backend fixture'ında strict tarih alanına date nesnesi ve editte farklı
username verilmesi araç hatasıydı; fixture düzeltildi, yalnız başarısız testler
tekrarlandı. Eski frontend beklentilerini güncelleyen ilk komut yanlış cwd'de
çalışmadı; yollar düzeltildi. Native Node extensionless TS import aracı esbuild
ile düzeltildi. Test beklentileri yeni GET sözleşmesine uyarlandı, gevşetilmedi.
ADMIN PASS; gerçek PostgreSQL/HTTP kabulü BLOCKED; canlı sistem/SSH işlemi yok.
