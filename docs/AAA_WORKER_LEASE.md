# AAA outbox worker lease ve fencing — v1 fixture

2026-11-11 · `AAA_WORKER_LEASE_V1_FIXTURE`. Yalnız
`app.simulation.aaa_worker.LeasedMemoryOutbox`; mevcut kanonik plan ve memory
atomic UoW kullanılır. API, daemon, timer, DB, üretim worker veya provider yoktur.
Önceki AAA/demo kabul testleri tekrarlanmaz; RADIUS canlı bağlantı yok bilgisi korunur.

## Sahiplik ve süre sözleşmesi

| Alan | Kural |
| --- | --- |
| Lease anahtarı | Tenant+request; plan hash ve sıralı outbox event UUID'sine bağlı. Aynı operation'ın tek aktif teslim/reconciliation sahibi vardır. |
| Worker kimliği | Güvenilir fixture WorkerContext.worker_id+tenant; can_deliver varsayılan false. Mevcut PreviewScope/aktör/transition izni ayrıca her işlemde denetlenir. |
| Teslim denemesi | Çağıranın açık attempt UUID'si; operation kapsamında bir daha kullanılamaz. Aynı aktif worker/attempt claim tekrarında yeni olay üretilmez. |
| Fencing token | İlk claim1; her yeni claim/devralma/sonraki olayda önceki token+1. Event değişince sıfırlanmaz. Account-owner fence'den ayrıdır; ikisi de korunur. |
| Lease süresi |1–300 saniye; varsayılan30. Repository'nin açık FakeLeaseClock UTC zamanı kullanılır. now>=expires_at anında lease geçersizdir. Geriye saat hareketi reddedilir. |
| Yenileme | Yalnız mevcut aktif ve süresi dolmamış worker/attempt/token. Token değişmez, süre kısaltılmaz; expired lease diriltilemez. Eski handle süresi yerine repository'deki güncel süre denetlenir. |
| Kapalı lease | ACK/NACK sonrası DONE, güvenli retry sonrası RELEASED. Yeni deneme yeni token ister; eski lease yeni olayda kullanılamaz. |

Handle imzalı yetki tokenı değildir. WorkerContext bu fazda açık test girdisidir;
gerçekte kimlik ve grant sunucu/service sınırından türetilmelidir. Caller'ın
saat/worker id beyanına güvenen bir HTTP endpoint eklenmedi.

## Teslim ve çökme davranışı

1. Producer aynı memory UoW'de owner CAS+journal+audit+outbox rezervasyonunu yapar.
2. Worker claim yalnız sıradaki olayı alır. Aktif başka lease varken LEASE_BUSY.
3. `dispatch` süresi/sahibi/token/attempt/plan/event/operation CAS'ini doğrular,
   olası dış çağrı başlangıcını işaretler ve **yalnız fixture metadata döndürür**.
   Tek lease ile ikinci dispatch reddedilir; hiçbir sağlayıcı çağrılmaz.
4. ACK için dispatch şarttır. Journal/owner CAS, outbox ACK ve worker lease DONE
   audit ile aynı lock/copy/publish sınırında oluşur. Aynı ACK yalnız hâlâ güncel,
   süresi dolmamış lease ile no-op olabilir; expired ACK tarihsel olsa da reddedilir.
5. Dispatch başlamadan çökmede expired lease yeni attempt/token ile aynı event'e
   verilir. Dispatch başladıktan sonra çökmede provider sonucu bilinmiyor sayılır:
   UNKNOWN+journal RECONCILIATION ve yeni **RECONCILE** lease atomik oluşur.
   Yeni worker dış etkiyi tekrar göndermez. Geç gelen eski ACK kabul edilmez.
6. COMMIT_OWNER_CAS yalnız yerel UoW işlemidir; pending kalması commit olmadığını
   gösterir. COMPENSATED yalnız bildirimdir. Bu iki olayın expired teslimi aynı
   event ID ve yeni token ile tekrarlanabilir; provider intent'i sayılmaz.

`retry` yalnız dispatch edilmediği bilinen durumda lease'i bırakır; eski worker
tekrar ilerleyemez. Dispatch sonrası retry reddedilir. NACK yalnız NOT_APPLIED
veya UNKNOWN kabul eder; önceki atomic modelin fail-closed uzlaştırma kuralını
kullanır. Özel notification NACK'i tamamlanmış telafiyi geri açmaz.

Her ACK/NACK/retry/yenileme/dispatch/telafi aynı doğrulayıcıdan geçer. Operation
revision, owner reservation revision ve owner fence farkı teslimi durdurur.
Eski `settle` ve `next_event` girişleri leased sınıfta kapalıdır; yeni worker
unfenced yazma yoluna yönlendirilmez. Üretim runtime'ına bağlanmamış önceki
MemoryAtomicUnit yalnız eski atomiklik fixture'ı olarak kalır.

## Uzlaştırma, telafi ve audit

RECONCILE lease dış teslim/ACK/NACK yapamaz. Yalnız salt okunur inceleme sınırı
ve ayrı can_compensate izniyle, mevcut CompensationEvidence doğrulandığında
memory telafi commit'i kullanılabilir. Eski telafi worker'ı veya expired
reconciliation lease, doğru kanıt sunsa bile reddedilir. Yeni lease aynı owner/
operation revision ve fence kanıtlarını yeniden kontrol eder; revizyon geri sarılmaz.
Eski intent'ler iptal edilir, COMPENSATED bildirimi yeni claim ile teslim edilir.

Worker audit tenant/request/event/plan hash, worker/attempt/token, operation
revision, aşama ve logical UTC zamanı tutar. Claim/renew/dispatch/ACK/NACK/retry/
telafi audit'i işleme bağlıdır. Base journal/audit/outbox sırası değiştirilmez;
copy/publish fault'ta lease ve journal beraber eski duruma döner. RLock yalnız
bu fixture instance'ındaki thread'ler içindir; SQL isolation kanıtı değildir.

## İzole kanıt ve sonraki sınır

13 yeni test: tek claim kazananı, idempotent claim, exact expiry, tüm stale
mutator'ların reddi, attempt reuse/foreign/tampered handle, renewal, güvenli
retry, dispatch sonrası crash, geç ACK ve sıralama, ayrı telafi yetkisi, final
owner+lease audit atomikliği, operation drift/unfenced giriş reddi, eşzamanlı
eski/yeni dispatch+ACK ve recovery rollback. Socket/PG/SQLite connect yasaktır.

Fencing bellekte monotoniktir; süreç kaybında kalıcılık garantisi verilmez.
Gerçek DB claim/lease transaction'ı ve durable counter uygulanmadı. Provider'a
gitmiş eski paketin yalnız yerel ACK reddiyle durdurulacağı iddia edilmez.
Gerçek sağlayıcı/idempotency sınırının da fence'i doğrulaması veya stale
komutu engelleyen eşdeğer mekanizma sağlaması gerekir; yoksa canlı geçiş kapalı.

Sonraki tek teknik öncelik: gerçek bağlantı açmadan sahte provider tarafında
fencing reddi ve UNKNOWN sonuçların kanıta dayalı uzlaştırılmasını sınamak.

[Provider fencing ve kanıt uzlaştırma devamı](AAA_PROVIDER_RECONCILIATION.md)
aynı fake lease'i etki öncesinde tekrar doğrular, provider receipt'ini journal/
owner/outbox geçmişiyle karşılaştırır. Tam kanıt bile otomatik resume veya gerçek
operation başarısı üretmez; mevcut gerçek bağlantı sınırı korunur.
