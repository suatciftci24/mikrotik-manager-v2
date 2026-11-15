# PPPoE paket seçimi ve sade işlem sonucu — 2026-11-15

Başlangıç temiz main-guncel/9583419; GitHub SHA eşitliği doğrulandı. AGENTS/Altın
Kurallar, güncel PROGRESS ve son ortak işlem kabulü okundu. Önceki görsel/PG/AAA
engelleri bu görevle kapatılmış sayılmaz; korunacak yerel değişiklik yoktu.

- PLAN diyalogunda tek kayıtlı aktif paket seçimi vardır. İkinci Paket/profil
  metin alanı kaldırıldı. Mevcut paket/hız kayıtlı abone snapshot'ından; yeni
  paket/hız doğrulanmış katalogdan gösterilir. Bilinmeyen eski hız Veri yok.
- UI seçimi ve prepare kontrolü sentetik ID, pozitif revizyon, aktiflik, ad,
  geçerli hız/süre ve profil alanı türünü doğrular. Pasif/bozuk/yabancı paketler
  seçilmez; yükleme/hata veya geçersiz ID halinde review/POST oluşmaz.
- Komut aynı dailyEntries sözleşmesini kullanır: value=katalog paket adı,
  package_id ve package_revision aynı biçimde gönderilir. Profil eşlemesi
  backend'in bu ID/sürümle çözdüğü katalog snapshot'ında kalır; bağımsız metin
  girişiyle katalog/profil eşlemesi ezilmez. Hız önizleme için review'da tutulur.
- Oluşturma/düzenlemede de atanmış paket için gereksiz disabled profil alanı
  gizlendi. Mevcut metin paketlerinin düzenleme/suggestion uyumluluğu korunur;
  değiştirilmeden tutulan eski/pasif atama yeni atama olarak değerlendirilmez.
  Yeni paket atama kontrolü aktif kayıtla eşleşmek zorundadır.
- Sonuç sunumu SubscriberOperationResults ile doğrulanmış başarılı/başarısız ve
  ayrıca doğrulanamayan kayıt sayılarını, abone adını, işlemi ve ilgili yeni
  değeri gösterir. Object.values ile dahili paket alanlarını yazdırma kaldırıldı.
  Başarısız değer Uygulanmadı; bilinmeyen sonuç başarı/başarısızlık sayılmaz.
- Tam receipt, UUID/paket/aktör/router kimlikleri ve ham hata kapalı Teknik
  detaylar içinde korunur. Aynı UUID ile sorgulama yalnız sonucu belirsiz,
  reddedilmemiş ve tamamlanmamış isteklerde bu bölümde görünür. Tamamlanan
  sonuçlarda sorgu düğmesi yoktur. save/readOperationResults ve gönderim/GET
  seçimi korunur; yeni otomatik retry veya ikinci POST yolu eklenmedi.
- Uzatma ve oluşturma/düzenleme belirsiz sonuç sorguları da teknik bölümdedir.
  Onay kutusu/önizleme, response eşleşmesi, audit ve resource invalidation
  korunur. Sonuç metinleri sarılır; receipt kendi sınırlı kaydırma alanındadır.

PASS: packages, subscriberCenter, subscriberDailyManagement,
subscriberQuickWorkflow, subscriberSaveRecovery, subscriberRenewal,
subscriberRenewalRecovery, operationGetRecovery ve yeni subscriberOperationResults
hedef kapsamları. Aktif/pasif/bozuk seçim, tek input, onaysız POST reddi, katalog
ID/sürüm/ad payload'ı, kayıp yanıt sonrası aynı UUID'li GET, tamamlanınca sorgu
kaldırılması, teknik kimliklerin gizlenmesi ve bilinmeyen sonucu ayrı sayma
kanıtlandı. Mevcut receipt/idempotency/çift gönderim/mixed-result regresyonları
korundu. Eski raw PLAN input, disabled tamamlanmış sorgu düğmesi ve yeni kayıt
profil datalist beklentileri yeni UI sözleşmesine uyarlandı; legacy önerileri
ayrıca korundu. Yalnız başarısız/etkilenen kapsam tekrarlandı.

İlk build'deki PLAN dalından kalan TypeScript daraltma ve nullable router adı
hataları düzeltildi. Son TypeScript/Vite production build ve diff PASS.
BLOCKED: Chromium crashpad setsockopt Operation not permitted/SIGTRAP ile
başlamadı; gerçek 320–430px/masaüstü modal görsel/taşma kabulü PASS değildir.
Sandbox gevşetilmedi, browser indirilmedi.

Yalnız frontend/test/dokümantasyon değişti. Backend/API sözleşmesi, PostgreSQL
veri/kullanıcı/şema, migration, VDS deploy/restart, V1/V2.5/gerçek MikroTik/RADIUS/
IPsec veya canlı veri işlemi yok. Ayrı onaylı frontend yayını yeterli; yeni
backend veya migration gerekmez. Commit/push/HEAD eşitliği teslimde bildirilir.
