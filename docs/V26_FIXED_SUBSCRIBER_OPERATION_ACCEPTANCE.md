# PPPoE tekli işlem girişini sabitleme — 2026-11-15

Temel temiz main-guncel/0368f9a; GitHub SHA eşitliği doğrulandı. AGENTS/Altın
Kurallar, güncel PROGRESS ve son paket/sonuç kabulü okundu. Korunacak yerel
fark yoktu. Önceki görsel/PG/AAA kabul engelleri kapatılmış sayılmaz.

- SubscriberDailyActions açık fixedAction parametresiyle tekli menü girişini,
  mevcut initialAction ile seçim tabanlı genel/toplu girişi ayırır. Tür yalnız
  satır sayısından çıkarılmaz: toplu seçim bir aboneyle açıldığında da genel
  seçici korunur. Abone listesi, detay ve günlük rapor menü çağrıları sabit
  türü doğrudan iletir; kaynak/hash metninden işlem türü tahmin edilmez.
- Sabit tür modal girişinde tutulur, parent props yenilenmesiyle başka türe
  kaymaz. Tekli sabit girişte yanlış kayıt adedi prepare aşamasında reddedilir.
- Tekli PLAN başlığı Paket Değiştir, STATUS Hesabı Kapat/Aç; tekrar İşlem
  select'i gösterilmez. Aç/Kapat hedefi mevcut kayıt durumunun tersinden alınır,
  hedef durumu da değiştirilebilir ikinci select yerine sabit bilgi olarak
  gösterilir. Onay ve eski/yeni önizleme korunur.
- Menüdeki uzatma mevcut ayrı SubscriberRenewal yolunu kullanmaya devam eder:
  Abonelik Uzat başlığı, süre/özel tarih seçimi aynı. Genel günlük EXTEND ve
  toplu EXTEND/STATUS, ayrıca bir kayıtlı genel akışın diğer mevcut işlemleri
  korunur. İşlem seçimi, gerçek seçim akışında açık kalır.
- Yalnız sabit giriş formunda küçük aralık düzenlemesi; 44px kontroller, başlık
  ilişkisi, dialog/klavye ve sentetik işareti korunur. Backend veya komut/receipt
  sözleşmesi değişmedi; katalog, paket/hız, onay/audit/idempotency ve yenileme aynı.

PASS: subscriberQuickWorkflow, subscriberDailyManagement, subscriberRenewal,
subscriberRenewalRecovery ve operationGetRecovery hedef dosyaları. Yeni testler
sabit başlık/select yokluğu, status hedefi, parent refresh'te PLAN'ın STATUS'a
kaymaması ve onay sonrası PLAN payload'ı; tek/çok seçili genel modun seçicisi,
karttan sabit tür/bulk ayrımı ve ayrı renewal yolunu doğrular. Mevcut paket,
çift gönderim, kayıp yanıt/same UUID GET ve karışık sonuç regresyonları korundu.
Son TypeScript/Vite production build ve git diff --check PASS.

BLOCKED: Chromium crashpad setsockopt Operation not permitted/SIGTRAP ile
başlamadı; gerçek 320–430px/masaüstü görsel/layout kabul PASS değildir. Sandbox
gevşetilmedi, indirme veya canlı browser erişimi yok.

Yalnız frontend ve test/dokümantasyon değişti. PostgreSQL/veri/kullanıcı/şema,
migration, backend, VDS deploy/restart, V1/V2.5/gerçek MikroTik/RADIUS/IPsec veya
canlı veri işlemi yok. Ayrı onaylı frontend yayını yeterli; yeni backend veya
migration gerekmez. Tek commit/push ve HEAD eşitliği teslimde bildirilir.
