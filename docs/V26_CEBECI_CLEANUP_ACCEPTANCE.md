# CEBECI_TOWERS V2.6 cleanup — 2026-11-17

Durum: yerel kontroller PASS / commit BLOCKED. Dal: `cleanup/cebeci-v26-reset-20261117`.
Başlangıç HEAD: `4f10df0`. Mevcut staged/unstaged cleanup korundu.

CEBECI özel ekran, onboarding, registry verify/read uçları ve standalone
preflight/migration plan artefaktları kaldırıldı. Genel router kayıt/probe,
PPPoE gözlemleri, Hotspot abone filtreleri, kaydedilmiş snapshot gösterimi,
TLS CA/IP SAN/pin ve transport sınırları korundu. Ortak kullanım nedeniyle
`cebeci_api_ssl`/`cebeci_access` gibi düşük seviye modüller silinmedi; bu modül
adlarının kalması CEBECI V2.6 yeteneğinin açık olduğu anlamına gelmez.
V26 capability artık eski enabled/operator ayarlarını reddeder. Registry
storage sınırındaki V26 kimlik/izolasyon guard'ı korunur.

Doğrulama:

- Backend unittest: test_router_registry, test_router_api_ssl,
  test_registry_pilot (yalnız kendi wire testleri), test_router_center,
  test_router_secret_vault, test_pppoe_api_ssl, test_pppoe_readonly,
  test_pppoe_api, test_pilot_runtime ve yeni test_cebeci_cleanup.
  İlk turdaki iki hata düzeltildi; yalnız başarısız kapsam yeniden çalıştı.
  Yeni guard testinin mock context-manager hatası MagicMock ile düzeltildi.
  Sonuç: ilgili bütün testler PASS.
- Frontend: routerRegistry, routerCenter, routerInventory,
  routerOnboardingPreview, pppoeObservations, systemCenter test dosyaları PASS.
  CSS bundle harness hatası düzeltildi; kaldırılmış CEBECI görünümü artık
  özel sekme/API üretmediğini doğrular. Genel arayüz testleri korunur.
- `npm run build`: TypeScript + Vite production build PASS (1714 modül).
- `git diff --check`: PASS.

İlk build bağımlılık yokluğu nedeniyle çalışmadı; npm registry DNS erişimi
başarısız oldu. Yalnız V2 ofis kopyasının mevcut node_modules bağımlılıkları
bu çalışma kopyasına kopyalandı; backend aynı V2 venv yorumlayıcısıyla ve
bu deponun PYTHONPATH'iyle çalıştı. Ofis kaynakları/config/verileri değişmedi.
Fixture wire testi `/add` alt dizgesini `/ip/address` ile karıştırıyordu;
artık sabit read komutlarının tamamını ve frame sayısını doğrular.

Push, fetch, deploy, canlı bağlantı, kalıcı DB yazımı, migration, restart veya
router/RADIUS değişikliği yapılmadı. Yalnız testlerin geçici sentetik memory
SQLite işlemleri kullanıldı. V1/eski V2/Fresh Pilot ve gerçek veriler korunur.
Önceki canlı BLOCKED kararları sürer. Sonraki adım cleanup commit incelemesi;
yayın veya veri işlemi bu kabulün kapsamında değildir.

Commit sonucu: git add ve git commit `.git/index.lock: Read-only file system`
hatasıyla engellendi. Commit oluşmadı; HEAD `4f10df0` olarak kaldı. Mevcut
staged değişiklikler ve çalışma ağacı korundu. Gerekli tek sonraki eylem:
Git yazma yetkili ortamda aynı cleanup dalında yerel commit oluşturmak.
