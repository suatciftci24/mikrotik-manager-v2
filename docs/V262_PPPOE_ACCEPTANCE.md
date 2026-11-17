# V2.6.2 PPPoE Abone Merkezi — yerel kabul

Durum: READY v2.6.2 (yerel). Canlı yayın yapılmadı.
Dal: development/v2.6.2-pppoe. Uygulama tabanı: 75c27df/v2.6.1.
Dal doğrudan bu commit'ten açıldı; sonraki teşhis/yayın betiği commit'leri
ve bu betiklerin dosyaları taşınmadı. Canlı 2.6.1 bilgisi kullanıcı kanıtıdır;
canlı panele/DB'ye doğrulama veya değişiklik erişimi yapılmadı.

Kök neden ve çözüm:

- Legacy listede birleşik arama/kaynak filtresi zaten vardı. Kalıcı listede
  yalnız kullanıcı/ad substring araması ve sunucu sayfalaması vardı; yalnız
  görünür sayfaya frontend filtre uygulamak eksik sonuç/sayım üretecekti.
- Aynı GET /subscriber-workspace sözleşmesine isteğe bağlı grouped, source ve
  expiry_group parametreleri eklendi. Eski parametreler/default sayfalama ve
  yanıt alanları korunur; expiry_groups/as_of_date ek alanlardır. Yetki/router
  SQL kapsamı aynı kalır. Gruplama modu yalnız yetkili kapsamı bellekte arar,
  sayar ve seçilen grubu sayfalar; büyük yetkili listelerde maliyet kayıt
  sayısıyla artar. Yeni sorgu veya arama indeksi/migration gerektirmez.
- Kalıcı arama kullanıcı adı, abone adı, router adı, paket, kayıtlı IP ve ID
  üzerinde Türkçe harf/case/aksan normalize eder; bütün sözcükler birlikte
  eşleşir. %, _ gibi karakterler literal metindir. Kaynak/tür/durum/router
  ve bitiş grubu aynı kayıtta kesişir; LOCAL/RADIUS/bilinmeyen ayrımı korunur.
- Gruplar ayrık: geçmiş, bugün, 1–3, 4–7, 8–30, 30 günden fazla, bilinmeyen.
  Grup toplamları mevcut arama/kaynak/tür/durum/router kapsamındadır ve seçili
  gruba göre daralmaz. Legacy'de mevcut kümülatif bitiş filtresi de ayrıca
  korunur; legacy grup sayıları o filtreyle de kesişir. Mevcut 7 gün içinde
  gibi filtrelerin toplamalı anlamı değiştirilmedi.
- Kalıcı listede gruplama/sıralama sayfalamadan önce yapılır. Grup/kaynak/arama
  değişimi sayfayı sıfırlar; detay dönüşü URL bağlamını korur. Mobil 5 ve
  masaüstü 25 kayıt sayfalaması, mevcut satır menüleri ve aksiyonlar aynı.
- Türkiye takvim günü backend Europe/Istanbul, frontend useTurkeyToday ile
  hesaplanır. Kalıcı liste as_of_date kullanır ve Türkiye günü değişince
  yeniden okur. Takvim tarihleri saat dilimi kaydırması olmadan gösterilir.
  Eksik/geçersiz tarih ve yıl0000 bilinmeyendir. Bozuk kayıt tarihi yalnız
  okuma projeksiyonunda null olur; depoya düzeltme/tahmini tarih yazılmaz.
- Listeye 44px, saran, klavye seçimi görünen tekil grup kontrolleri eklendi.
  Detayda hesap durumu yanında abonelik bitiş rozeti; bilinmeyen tarihte açık
  açıklama bulunur. Router, tarih, paket, hesap durumu ve mevcut işlemler
  korunur. Kaynak uyarıları ve teknik/audit detayları kaldırılmadı.

Hedefli doğrulama:

- Backend test_subscriber_center + test_workspace_operator_access: 21 test
  PASS; ek grouped API yetki/sayım izolasyonu testi PASS (toplam22).
  Geçici sentetik SQLite fixture'ları kullanıldı; PostgreSQL'e bağlanılmadı.
  İlk tekil test çağrısı yanlış sınıf adıyla açılamadı; doğru OperatorAccess
  sınıfındaki yalnız yeni test çalıştırıldı ve PASS oldu.
- Frontend sekiz dosya PASS: subscriberExpiryGroups, subscriberFilters,
  expiry, subscriberCenter, compactSubscribers, subscriberQuickWorkflow,
  subscriberRenewal, subscriberDailyManagement. Yeni workspace grup/kaynak/
  arama/sayfa callback testi ayrıca tek başına PASS. Oluşturma, düzenleme,
  etkin/pasif, uzatma, onay/UUID/recovery ve yetkisiz işlem reddi korunur.
- TypeScript + Vite production build PASS (1717 modül).
- Merkezi release/paket/lock ve CHANGELOG 2.6.2; release check ve diff PASS.
- Gerçek Chromium/viewport görsel kabulü yapılmadı. Önceki socket/ağ engeli
  tekrar denenmedi; SSR/handler testleri görsel kabul olarak sunulmaz.

Silme veya yeni toplu işlem eklenmedi. API mutasyonları, revizyon/onay,
audit/idempotency ve router/RADIUS/TLS iş mantığı değiştirilmedi. CEBECI
entegrasyonu geri getirilmedi. V1/V2.5/router/RADIUS/IPsec, canlı DB/veri/
rol/kullanıcı veya eski panel işlemi yok. Deploy/restart/migration/seed/reset/
tag yok. Bilinen ağ/DNS engeli nedeniyle push tekrarlanmadı. Yayın ayrıca
kullanıcı onayı gerektirir; yeni sürüm ortak panele henüz aktarılmadı.
