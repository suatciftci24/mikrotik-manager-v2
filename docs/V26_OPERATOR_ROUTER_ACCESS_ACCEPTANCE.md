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
