# V2.6 kalıcı sentetik PPPoE Abone Merkezi — 2026-11-14

Başlangıç temiz main-guncel/93e23c9. AGENTS/Altın Kurallar, PROGRESS,
V26_FEATURE_PRESERVATION_ACCEPTANCE, V26_PPPOE_SUBSCRIBER_ACCEPTANCE ve son
V26_OPERATOR_ROUTER_ACCESS_ACCEPTANCE okundu. Önceki canlı/PG/DNS/ROLLBACK
kayıtları bu yerel görevle kapatılmış sayılmaz.

## Mevcut özellikler ve tamamlanan eksikler

Oluşturma/düzenleme, UUID receipt kurtarma, durum/paket/EXPIRE, 7/15/30/60/90
ve özel tarih yenileme, günlük/toplu işlemler ve audit zaten mevcuttu. Bu akışlar
ve aynı PostgreSQL ORM tabloları korundu; ikinci abone deposu oluşturulmadı.

- Workspace liste, detay, router-abone listesi, profil önerileri, audit ve receipt
  okumaları can_view verilen DEMO_ROUTER ID'leriyle sınırlandı. Liste/count SQL
  filtresi sayfalama öncesindedir. USER/ADMIN veya legacy sabit router grant'leri
  kalıcı envanterle birleştirilmez; merkezi ADMIN'in mevcut kapsamı korunur.
- ADMIN/OPERATOR yazımı ilgili router için can_manage_pppoe veya
  can_manage_hotspot gerektirir. VIEWER yazamaz. Kaynak/tür/router bağı gerçek
  kilitli kayıttan kontrol edilir; expected_router_id tek başına yetki değildir.
  OPERATOR router taşıyamaz; mevcut ADMIN taşıma özelliği korunur.
- Toplu komutlarda tüm üyelerin yetki ön kontrolü yazmadan önce yapılır;
  her kalıcı değişiklik ve kendi audit'i aynı transaction'dadır. Mevcut bulk
  sözleşmesi abone başına atomiktir; tüm batch için tek transaction değildir.
  İş kuralı/revizyon hataları mevcut per-item receipt davranışını korur.
- İsteğe bağlı started_on mevcut JSON fields içinde kalıcıdır. Bitiş başlangıçtan
  önce olamaz; oluşturma, edit, EXPIRE/EXTEND ve yenileme kontrol eder. Eski tarih
  bilinmiyorsa tahmin edilmez. started_on göndermeyen eski istemci mevcut tarihi
  silmez; eski UUID fingerprint ve receipt'leri geriye uyumlu kalır.
- Paket/profil seçimi yalnız yetkili mevcut abonelerde saklanan profil adlarını
  önerir; ilk/yeni sentetik profil adı girilebilir. Bu bir RouterOS/RADIUS profil
  kataloğu veya cihaz profil doğrulaması değildir. Ayrı global profil tablosu yok.
- Frontend kalıcı görünümü operatör ve okuyucuya açar; server can_manage alanı
  satır/detay/günlük işlem uygunluğuna katılır. Oluşturma router listesi yönetim
  iznine göre daralır; mevcut workspace API'sindeki tüm sayfalar okunur. Salt
  okunur kullanıcıda oluşturma ve değişiklik kontrolleri kapalıdır.
- Dashboard tüm roller için aynı yetkili subscriber-workspace kayıtlarını okur;
  boş durumda toplam 0 olur. Yenileme/paket/durum sonrası mevcut ortak kaynak
  invalidation akışı liste/detay/Dashboard/raporları yeniler. Audit oturum veya
  canlı trafik olarak sunulmaz. Legacy işlemleri ve fotoğraf yetkileri korunur;
  workspace fotoğraf/provider/gerçek entegrasyon kapıları genişletilmedi.
- Abone taşınmışsa artık yetkisiz eski router'a ait audit, POST replay veya GET
  receipt içeriği operatöre verilmez. Tarihsel kimlikler bugünkü routerdan tahmin
  edilmez. Başarısız/yetkisiz istek abone değişikliği olarak kaydedilmez.

## Hedefli doğrulama

PASS, sentetik ve soketsiz:
- test_pppoe_workspace_access: altı yeni ASGI/SQLite senaryosu. Operatör tam
  oluşturma/edit/PLAN/STATUS/yenileme döngüsü; cold reload; aynı UUID replay;
  scoped profil/history, Dashboard/liste eşitliği ve boş sıfır. Salt okunur ve
  VIEWER reddi, yabancı/forged router, Hotspot izni ayrımı, pagination/search,
  batch ön kontrolü, ADMIN-only router taşıma, taşınmış kayıt audit/receipt reddi.
  SQLAlchemy audit INSERT hatasında create/edit/daily değişiklik rollback;
  eski started_on'suz istemci/UUID/receipt uyumluluğu.
- Mevcut subscriber_center, subscriber_renewal, subscriber_daily_management,
  workspace_operator_access, workspace_inventory_views ilgili kontrolleri PASS.
- Frontend subscriberCenter, subscriberDailyManagement, subscriberRenewal,
  subscriberSaveRecovery, workspaceDashboard hedef kapsamları PASS. İki yeni
  frontend senaryosu readonly callback reddi, yönetilebilir router seçenekleri,
  scoped profil ve başlangıç tarihi alanlarını doğrular. Kayıp/bozuk yanıt ve
  UUID kurtarma testleri korundu.
- Son production TypeScript/Vite build ve git diff --check PASS.

İlk bazı Python test import'ları backend/tests PYTHONPATH eksikliğinden açılmadı;
yalnız ilgili kapsam doğru yolla tekrarlandı. Frontend harness'lerinde yeni
useIdentity için sentetik context eklendi. Önceden eskimiş doğrudan edit/menu
seçicisi mevcut ortak QuickButtons/menuitem yapısıyla doğrulandı; yetki veya
beklenti gevşetilmedi. Başarılı kapsam sebepsiz tekrar edilmedi. ASGI test worker
scheduler'ı inline'dır; gerçek session/dependency/response modeli ve SQL çalışır.
Gerçek PostgreSQL, canlı VDS/API veya tarayıcı görsel kabulü çalıştırılmadı;
SQLite sonucu PostgreSQL çalışma zamanı kabulü olarak sunulmaz.

## Dağıtım ve sınırlar

PostgreSQL model/tablo/FK/migration dosyası değiştirilmedi. Yeni migration gerekmez;
mevcut workspace 007/008 şemalarının hazır olduğu kurulum esas alınır. Otomatik
migration/seed veya veri dönüştürme yok. Başlangıç tarihi mevcut JSON alanına
istek anında yazılır; eski satırlar topluca güncellenmez.

Etkinleşmesi için ayrı onaylı backend + frontend deploy gerekir. Gerçek PPPoE
provisioning, bağımsız merkezi paket kataloğu ve cihaz profil eşlemesi bu sentetik
kapsamın dışındadır. V1/V2.5/VDS/canlı PostgreSQL/kullanıcı/parola/gerçek router/
RADIUS/IPsec'e erişim veya yazma, deploy/restart/migration/veri silme yapılmadı.
Remote ls-remote DNS hatası verdi; uzak HEAD doğrulanamadığı için push yapılmadı.
Güvenli yerel commit teslim edilir.
