# V2.6 router veri kaynağı — 2026-11-14

Yerel PASS; push BLOCKED (GitHub DNS). Başlangıç main-guncel/73ec462,
çalışma ağacı temiz. AGENTS.md, PROGRESS, kullanıcı yetkilendirme, özellik
koruma ve yönetim UI kabul raporları okundu. Önceki canlı/PG BLOCKED ve
ROLLBACK kayıtları bu görevle kapatılmadı.

- V26 API kimliği kalıcı envanter kaynağını bildirir. Dashboard mevcut
  /router-workspace/routers ve /subscriber-workspace GET uçlarını sayfalayarak
  okur; sabit demo API'lerine fallback yok. CPU/durum/oturum bilinmiyor;
  envanterden audit geçmişi üretilmez, geçmiş mevcut değil olarak işaretlenir.
- Router Merkezi DEMO ve Abone Merkezi LEGACY varsayılan/eski kaydedilmiş
  seçimleri V26'da kalıcı kaynaklara yönelir. Eski profiller korunur.
- /users router seçenekleri yalnız DEMO_ROUTER kayıtlarından gelir. Grant
  doğrulaması kalıcı ID'leri kabul eder; eski grant'ler kaybolmaz. Merkezi ADMIN,
  rol ve kendini/son yöneticiyi koruma politikaları değiştirilmez. Kullanıcıya
  veya parolaya yazma yapılmadı. API depo hatası 503; statik listeye dönüş yok.
- /dashboard/summary uyumluluk yanıtı da V26'da aynı workspace servislerini
  kullanır; sıfır abone ve bilinmeyen ölçümleri doğru ayırır.

Doğrulama: router workspace 7 test, identity permissions 18 test, yeni veri
kaynağı kabulü 5 test PASS. Frontend workspaceDashboard, dashboardOverview,
userManagement üç hedef test dosyası PASS. İlk strip-only Node çalıştırması
parametre property sözdizimini desteklemedi; transform-types ile düzeldi.
TypeScript/Vite production build PASS; git diff --check PASS.
Sentetik tek V26 Test Router + sıfır abone, 101 router sayfalama, kaynak reddi,
depo hatası ve yetki politikası koruması doğrulandı. Canlı VDS API/DB veya gerçek
tarayıcı kabulü çalıştırılmadı; mevcut canlı kayıt sayısı burada doğrulanmış sayılmaz.

V1/V2.5, router/RADIUS/IPsec, canlı DB, kullanıcı/parola, migration, deploy ve
servis restartı işlemi yok. Etkinleşmesi için backend + frontend ayrı onaylı
yayın gerekir; migration gerekmiyor. Remote HEAD DNS nedeniyle doğrulanamadı,
push denenmedi. Güvenli yerel commit teslim edilir.
