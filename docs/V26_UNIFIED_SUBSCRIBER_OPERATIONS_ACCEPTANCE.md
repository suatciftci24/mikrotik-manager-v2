# Abone Merkezi ortak işlem akışı — 2026-11-15

Başlangıç temiz main-guncel/802e0c0; GitHub SHA eşitliği doğrulandı. AGENTS/Altın
Kurallar, güncel PROGRESS, son mobil kabul ve özellik koruma envanteri okundu.
Önceki görsel/PG/AAA/canlı kabul engelleri kapatılmış sayılmaz.

Mevcut SyntheticSubscriberEditor, SubscriberRenewal, SubscriberDailyActions ve
useSubscriberSave/receipt akışları incelendi; endpoint, command/UUID/revizyon,
transaction, audit ve backend iş mantığı yeniden yazılmadı.

- Kart ve kalıcı abone detayında aynı SubscriberQuickButtons menüsü kullanılır.
  Detay menüsü özet alanına taşındı; sekmelerde ikinci menü oluşturulmadı.
  Paket/uzatma/hesap durumu/düzenleme/geçmiş aynı callback'lere gider. Listeye
  düzenleme callback'i aynı canChangeWorkspaceItem yetki/kaynak kontrolüyle
  bağlandı. Readonly/yabancı/eksik router veya belirsiz kaynak yazamaz.
- Yeni kayıt henüz bir aboneye ait olmadığından mevcut tek Abone ekle girişi
  korunur. Toplu seçim akışı ayrı ve aynı per-item sonuç sözleşmesiyle kalır.
- Ortak SubscriberOperationPreview yalnız sunum bileşenidir: abone/kullanıcı,
  router, eski→yeni değişiklikler ve gelecekteki beklenen sonuç. CREATE/UPDATE,
  PLAN/STATUS ve uzatma mevcut review değerlerini aynı görünümde gösterir.
  Teknik ID/sürüm bilgileri açılır alanda korunur; aynı adlı paket sürümü
  değişikliği önizlemede görülebilir. Oluşturma/düzenlemede incelenen form
  tekrar gösterilmez; Formu düzelt ile aynı güvenli akışa dönülür.
- Oluşturma/düzenlemede onay kutusu review sonrasında görünür. Mevcut guard
  onay yoksa POST göndermez. Günlük işlemlerin onay kutusu ve uzatmanın açık
  Onayla ve uygula düğmesi korunur. Önizleme tek başına kayıt değiştirmez.
- Uzatma preview kimlik/router bağlamı da review anında tutulur; arka planda
  props yenilense bile önceki onaylanmış istek başka kayda dönüştürülmez.
- Başarı yalnız doğrulanmış response/receipt sonrasında gösterilir; red ve
  belirsizlik mevcut anlaşılır hata/aynı UUID ile salt okuma kurtarmasını korur.
  Ortak invalidation bağımlılıkları zaten liste/detay/Dashboard/rapor/geçmiş
  kaynaklarını kapsar; ikinci cache/başarı yolu eklenmedi.

PASS: subscriberOperationPreview, subscriberCenter, subscriberQuickWorkflow,
subscriberRenewal, subscriberRenewalRecovery, subscriberDailyManagement,
subscriberSaveRecovery ve packages hedef kapsamları. Yeni onaysız CREATE testi
POST olmamasını, sonra tek doğrulanmış yazım + subscriber-workspace/center,
Dashboard ve reports yenilenmesini doğrular. Tek menü/her sekme, readonly menü,
eski→yeni ve beklenen sonuç; mevcut kayıp/bozuk yanıt, çift gönderim, UUID,
karışık per-item başarı/başarısızlık ve katalog regresyonları korundu.

Eski testlerde menünün overview'da bulunmaması ve 'Eski: ... Yeni: ...' metni
beklentisi yeni davranışa uygun tek menü ve aynı değer çiftini doğrulayacak
şekilde güncellendi; yalnız başarısız senaryolar tekrar geçti. Başarılı kapsamlar
sebepsiz tekrar edilmedi. Son TypeScript/Vite production build ve diff PASS.

BLOCKED: mevcut Chromium crashpad setsockopt Operation not permitted/SIGTRAP ile
başlamadı. 320–430px ve masaüstünde gerçek görsel/layout kabul PASS değildir.
Sandbox gevşetilmedi; ağsız frontend testleri PG veya canlı sistem kanıtı değildir.

Yalnız frontend + test/dokümantasyon değişti. PostgreSQL sentetik kayıtları,
kullanıcı/şema, migration/veri taşıma/silme, VDS deploy/restart, V1/V2.5/gerçek
MikroTik/RADIUS/IPsec işlemi yok. Etkinleşmesi için ayrı onaylı frontend yayını
 gerekir; backend veya migration gerekmez. Commit/push teslimde bildirilir.
