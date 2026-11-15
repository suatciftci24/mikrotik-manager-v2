# V2.6 sentetik abone ekleme akışı — 2026-11-15

Temel `main-guncel/cd1de72`; başlangıç ağacı temizdi. AGENTS/Altın Kurallar,
güncel PROGRESS, son abone işlem kabulü ve paket/workspace sözleşmeleri okundu.
Önceki Chromium sandbox engeli geçerli; görsel PASS varsayılmadı.

- Mevcut `/subscriber-workspace` create API, package binding, router yetkisi,
  transaction/audit, request UUID ve aynı UUID ile salt-okunur GET recovery
  korundu. Backend, şema, PostgreSQL kayıtları veya migration değiştirilmedi.
- Tek formdaki kayıt alanları ve sentetik güvenlik uyarısı korundu. Yeni
  kayıtta yalnız geçerli/yetkili sentetik router ve etkin katalog paketiyle
  önizlemeye geçilir. Abone adı, kullanıcı adı biçimi ve ISO takvim tarihleri
  gönderimden önce kontrol edilir; kullanıcı adı tekilliğinin yetkili kontrolü
  backend'de kalır, duplicate reddinde başarı üretilmez.
- Etkin paket seçilince adı, indirme/yükleme hızı ve tanımlı süre görünür.
  Yeni kayıt başlangıcı Türkiye gününe göre mevcut `packageEnd` kuralıyla
  başlatılır; süreye bağlı bitiş başlangıç değişince güncellenir, elle girilen
  bitiş korunur. Önizleme abone/kullanıcı, router, paket/hız/süre, hesap durumu
  ve başlangıç/bitiş değerlerini gösterir. UUID, router/paket kimlikleri ve
  paket revizyonu kapalı Teknik bilgiler altında kalır.
- Açık onay, frozen payload/UUID, receipt eşleşmesi ve doğrulanmış success
  sonrası liste/detay/Dashboard/rapor invalidation korunur. Başarılı create
  ilgili abone detayını açar ve kısa `Abone kaydedildi.` bildirimi verir.
  Mevcut abone düzenleme, paket değiştirme ve expiry koruma davranışı ayrıdır.
- Create/recovery: `subscriberSaveRecovery` 38 PASS (açık onay, paket/hız/süre,
  tarih hesabı/elle tarih, eksik router/geçersiz tarih, duplicate conflict,
  tek POST/GET recovery ve bağımlı kaynak yenileme). `subscriberCenter` 25
  PASS; `packages` 5 PASS. TypeScript/Vite production build ve
  `git diff --check` PASS.
- Gerçek 320–430px/masaüstü Chromium görsel kabul BLOCKED: bu ortamda Chromium
  daha önce crashpad `setsockopt: Operation not permitted`/SIGTRAP ile
  başlatılamadı; sandbox gevşetilmedi.

Bu görevde yalnız frontend ve kabul belgesi değişti. VDS deploy/restart,
backend, PostgreSQL, migration/veri değişikliği, V1/V2.5, gerçek router, RADIUS
ve IPsec işlemi yapılmadı. Değişikliği etkinleştirmek için ayrıca onaylı
frontend yayını gerekir; backend deploy veya migration gerekmez.
