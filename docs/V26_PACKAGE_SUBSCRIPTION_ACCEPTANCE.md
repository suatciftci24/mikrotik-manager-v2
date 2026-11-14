# Paket Yönetimi ve sentetik PPPoE uçtan uca kabul — 2026-11-14

Başlangıç: temiz main-guncel/4f340a7. AGENTS/Altın Kurallar, PROGRESS ve önceki
PPPoE workspace kabulü okundu; mevcut özellikler yeniden yazılmadı. Önceki
canlı/PG/DNS/ROLLBACK durumları bu yerel kabul ile kapatılmış sayılmaz.

Kök neden: bağımsız paket modeli veya katalog ekranı yoktu. Abone plan metni ve
scoped profil önerileri paket oluşturma işlevi değildi. Statik demo paketleri
legacy depoya aitti; yeni kalıcı kataloğa kaynak yapılmadı.

Tamamlananlar:
- Sistem → Paket Yönetimi; Abone Merkezi'nde doğrudan Paket Yönetimi bağlantısı.
  ADMIN ad, indirme/yükleme Mbps, isteğe bağlı MikroTik profil eşleme etiketi,
  isteğe bağlı aylık TRY ücret, gün süresi ve aktif/pasif durum oluşturur/düzenler.
  Listeleme, revizyon, eski/yeni onay ve audit geçmişi vardır. Paket ticari
  abonelik tanımıdır; profil etiketi cihaz profili oluşturma/doğrulama değildir.
- Katalog mevcut PostgreSQL şemasında iki yeni ORM tablo kullanır. Ad casefold
  unique; request UUID/fingerprint, revision kontrolü ve paket+audit atomiktir.
  Kayıp yanıtta aynı onay/UUID tekrarı kayıt çoğaltmaz. Silme endpoint'i yoktur.
- OPERATOR/VIEWER yalnız router okuma kapsamı varsa aktif kataloğu okuyabilir;
  katalog oluşturma/düzenleme, pasif liste ve katalog audit'i ADMIN'dedir.
  Aboneye paket atama mevcut can_manage_pppoe/can_manage_hotspot + can_view
  ve canonical DEMO_ROUTER bağı ile korunur; OPERATOR'a ADMIN yetkisi verilmez.
- Yeni abone formu kayıtlı aktif paket seçer; düzenleme ve PLAN işleminde de
  kayıtlı paket seçilebilir. Tüm paket/router sayfaları okunur. Paket ID/sürümü
  backend'de aynı transaction'da kilitlenip doğrulanır; ad/hız/ücret/profil
  snapshot'ı istemciden alınmaz. Paket kimliği ve sürümü receipt'te eşleşmelidir.
- Katalog değişikliği mevcut aboneyi değiştirmez. Eski/pasif atanmış paketle
  tarih/isim/durum düzenleme korunur; pasif veya eski sürüm yeni atamaya kapalıdır.
  Aynı adlı paketin yeni sürümüne açık atama desteklenir. Paket değiştirme bitiş
  tarihini değiştirmez. İlk bitiş boşsa başlangıç + süre - 1 gün varsayılanıdır;
  başlangıç/bitiş doğrulaması ve tarih taşması kontrollüdür.
- Abonede ID/revision/snapshot mevcut JSON alanındadır. Eski metin paketleri ve
  UUID fingerprint/receipt kurtarma korunur; bu geriye uyumlu API yolu kaldırılmaz.
  Yeni UI oluşturmasında kayıtlı paket zorunludur. Mevcut yenileme, toplu işlemler,
  kaynak/kimlik kilidi, audit, Dashboard sayacı ve ortak invalidation kullanılır.

Hedefli PASS:
- Yeni test_package_subscription_flow: beş ASGI/SQL senaryosu. Paket → tek V26
  Test Router → abone/atama → başlangıç/bitiş → yenileme → paket değişimi → detay,
  kalıcı reload, receipt, audit ve Dashboard/liste eşitliği. UUID replay/çatışma,
  duplicate ad, stale/pasif paket, snapshot koruma/açık sürüm yükseltme, tarih/ücret/
  bool doğrulama, header/rol/router sınırları ve katalog/abone audit INSERT hatası
  rollback. Yeni veri yalnız geçici SQLite fixture'larındadır.
- Mevcut ilgili subscriber_renewal ve subscriber_daily_management 14 test;
  önceki UUID uyumluluğu ve PPPoE yaşam döngüsü iki hedef senaryo PASS.
- Frontend subscriberCenter 21, subscriberDailyManagement 3,
  subscriberSaveRecovery 33 ve yeni packages 4 hedef test PASS. Kayıp yanıt
  harness'i yeni kayıtlı paket seçimine uyarlandı; başarısız 7 create senaryosu
  tekrar geçti. Menü/ADMIN sınırı, paket oluşturma/onay/aynı UUID tekrar, süre,
  sayfalama, aynı adlı sürüm değişimi ve yanlış receipt reddi doğrulandı.
- Son TypeScript/Vite production build ve git diff --check PASS.

Doğrulama sınırları: ASGI test transport'u worker scheduler'ı inline çalıştırır;
gerçek dependency, response modeli, servis ve SQL transaction akışı yürür.
Canlı VDS/API, gerçek PostgreSQL, gerçek browser görsel kabulü veya MikroTik/
RADIUS provisioning yapılmadı; SQLite sonucu PostgreSQL runtime kabulü değildir.
Yeni frontend testinde Node'un uzantısız TS import'u esbuild bundle ile çözüldü;
asenkron save handler testi microtask tamamlanmasını bekler. Ürün yetkileri veya
beklentiler test için gevşetilmedi; başarılı kapsam sebepsiz tekrar edilmedi.

Dağıtım gereksinimi: yeni katalog tabloları için migration GEREKİR. Yalnız
V26_PACKAGE_CATALOG_MIGRATION_PLAN.md hazırlandı; çalıştırılabilir migration
veya canlı DDL uygulanmadı. Planın ayrı onayla uygulanması ve grant kontrolü
sonrasında backend + frontend yayını gerekir. Uygulama otomatik tablo/seed
oluşturmaz; mevcut veriler dönüştürülmez. V1/V2.5/VDS/canlı DB/kullanıcı/parola/
router/RADIUS/IPsec, deploy/restart/migration/veri silme işlemi yapılmadı.
GitHub ls-remote DNS hatası verdi; remote doğrulanamadı, push yapılmadı.
