# V26 operatör router okuma yetkisi — 2026-11-14

Başlangıç: temiz main-guncel/4058844. AGENTS.md/Altın Kurallar, güncel PROGRESS
ve V26_ROUTER_SOURCE_ACCEPTANCE okundu. Önceki uzak DNS/PG/ROLLBACK kayıtları
bu görevde kapatılmadı. Canlı v26test hesabına veya VDS'ye bağlanılmadı.

Kök neden: 4058844 workspace kaynağını seçti fakat workspace liste/detay ve
router-center kalıcı kayıt dalı hâlâ current_admin gerektiriyordu. Frontend
kaynak seçeneklerini ve managed detayını admin ile sınırlıyordu. Dashboard
loader'ı da operatöre kapalı subscriber-workspace çağrısı yapıyordu. Statik
ROUTERS tabanlı allowed() kalıcı grant ID'lerini kapsamına almaz; bu legacy
sınırını genişletmek kaynakları karıştırırdı.

Çözüm: ayrı merkezi workspace_scope; mevcut merkezi ADMIN kapsamı korunur.
V26 ADMIN/OPERATOR/VIEWER için diğer okumalar yalnız açık can_view grant'i
olan demo-managed-router ID'lerine bağlıdır. SQL ID filtresi arama/count ve
sayfalama öncesinde uygulanır. Detay kimliği okunmadan yetkilendirilir; restricted
router-center audit veya abone verisi taşımaz. Mutasyonlar, trust profilleri,
abone yönetimi ve provider observation uçları mevcut ADMIN kapısını korur.
Legacy allowed() ve kullanıcı/parola/permission kayıtları değişmedi.

Frontend operatöre Yetkili sentetik routerlar kaynağını sunar; managed liste ve
detay salt okunurdur. Ekle/düzenle/sil kontrolleri yoktur. Abone/provider bileşeni
restricted detayda mount edilmez. Dashboard yalnız yetkili routerları okur;
yetkisi olmayan abone verisini sıfırmış gibi göstermez, statik demo ile karıştırmaz.

PASS:
- Backend 43 hedef test: yeni 4 ASGI/SQL kabulü, mevcut router workspace 7,
  router center 9, workspace inventory 5, identity permissions 18.
- ASGI: izinli liste/detay/count, filtrelenmiş sayfalama, gizli/eksik ID 404,
  grant kaldırılınca sıfır/404, VIEWER scoped okuma ve ADMIN regresyonu.
  Mutasyonlar/profiller/abone ve provider yolları 403; write/provider dispatch yok.
- Frontend 19 hedef test: workspaceDashboard 4, routerWorkspace 4, routerCenter 11.
  Menü, salt okunur kontroller, router-only Dashboard, hatada fallback reddi,
  admin işlem akışı ve legacy Hotspot davranışı doğrulandı.
- Son TypeScript/Vite production build ve git diff --check PASS.

İlk TestClient denemesi eksik httpx2 nedeniyle başlamadı; dependency eklenmedi.
Soketsiz ASGI harness'te ortamın worker-thread zaman aşımı görüldü; testte yalnız
worker scheduler inline çalıştırıldı, gerçek dependency/auth/route/response ve SQL
akışı korundu. İlk TS build eksik PageHeading eyebrow alanını yakaladı, düzeltildi.
Frontend eski UNMEASURED fixture regresyonu üzerine engel PREPARING ile sınırlandı;
başarısız senaryo ve yeni restricted senaryo yeniden geçti. Başarılı testler
nedensiz tekrarlanmadı. Canlı HTTP/browser/PostgreSQL kabulü iddia edilmez.

Remote: git ls-remote origin refs/heads/main-guncel DNS hatası; remote HEAD
belirlenemedi ve push yapılmadı. Yerel commit teslim edilir. Etkinleşmesi için
ayrı onaylı backend + frontend deploy gerekir; migration gerekmez. V1/V2.5,
VDS/PostgreSQL/kullanıcı/parola, gerçek cihaz/RADIUS/IPsec, deploy/migration/
servis restartı değişikliği yoktur.

## 98a45c9 sonrası oturum yanıtı düzeltmesi — 2026-11-14

Başlangıç temiz main-guncel/98a45c9. Kullanıcının canlı deploy/HTTPS ve başarılı
kullanıcı audit kanıtı esas alındı; VDS'ye bağlanılmadı. Önceki kabulde eksik
kalan sınır gerçek /auth/login ve /auth/me response_model serileştirmesiydi.

Kanıtlanan kök neden: identity.public_user router_inventory_source üretmesine
rağmen UserResponse alanı tanımlamıyordu. FastAPI alanı iki HTTP yanıtından da
atıyordu. Frontend eksik alanı kalıcı kaynak olarak seçmediğinden operatör yalnız
Demo envanter görüyordu; ADMIN menüsü başka koşulla açıldığı için sorun admin'de
maskeleniyordu. Yeniden giriş de aynı şemadan geçtiği için çözüm olmuyordu.

Üretim düzeltmesi yalnız backend/app/schemas/auth.py içinde literal kaynak
alanının eklenmesidir. Eski profil için LEGACY_DEMO varsayılanı korunur. Rol,
grant filtresi, SQL, frontend veya oturum güvenlik politikası değiştirilmez.

Yeni ASGI regresyonu önce gerçek login JSON'unda KeyError: router_inventory_source
ile başarısız oldu; düzeltme sonrası geçti. Sentetik identity deposu ve geçici
SQLite workspace kullanır; security/current_demo_user override edilmeden gerçek
login cookie ve response_model ile /me, liste, yetkisiz detay ve Dashboard
kontrol edilir. Aynı cookie'de can_view kaldırılınca /me ve liste hemen güncellenir,
detay 404 olur; yeniden verilince sayaç 1 olur, ADMIN/profile erişimi 403 kalır.
HTTP harness yalnız worker scheduler'ı inline çalıştırır; oturum/yetki ve
serileştirme yürütülür. Canlı hesap/DB veya PostgreSQL kabulü değildir.

PASS: workspace_operator_access 5, acceptance_security 7, pilot_operator_identity 6
= 18 backend test; routerWorkspace 4 + workspaceDashboard 4 = 8 frontend test;
production TypeScript/Vite build ve diff kontrolü. AcceptanceSecurity'deki eski
rol-etiketi-only fixture, mevcut role_code sözleşmesine göre düzeltildi; başarısız
tek senaryo tekrar geçti. Üretim guard'ı gevşetilmedi.

Değişenler: auth.py yanıt şeması, iki backend test dosyası, bu rapor ve PROGRESS.
İstek yalnız yerel commit kapsamındadır; push/deploy/restart/migration yapılmadı.
Etkinleşmesi için ayrı onaylı backend yayını gerekir; frontend değişmedi ve
migration gerekmez. V1/V2.5/VDS/DB/kullanıcı/parola/cihaz/RADIUS/IPsec korunur.
