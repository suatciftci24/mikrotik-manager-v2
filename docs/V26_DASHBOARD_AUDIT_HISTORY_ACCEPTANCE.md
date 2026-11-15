# V2.6 Dashboard audit ve sade abone geçmişi — 2026-11-15

Başlangıç temiz main-guncel/70eb954; GitHub main-guncel aynı SHA ile doğrulandı.
AGENTS/Altın Kurallar, güncel PROGRESS, özellik koruma, PPPoE workspace ve paket
kabul raporları okundu. Önceki canlı/PG/AAA engelleri kapatılmış sayılmaz.

Kök neden: workspace Dashboard yükleyicisi yalnız envanter okuyor, audit'i
okumadan history_available=false döndürüyordu. Günlük raporun workspace kapısı
ADMIN'e bağlıydı ve rapor önce legacy envanter/olay kaynağını okuyordu.

- Kalıcı Dashboard mevcut workspace management/history API'sini report=true ile
  okur. ADMIN'in merkezi kapsamı korunur; diğer roller için can_view ve
  can_view_reports kesişimi SQL count/pagination öncesi uygulanır. Mevcut detay
  geçmişinin can_view sözleşmesi değişmez. Kullanıcı/grant verisi değiştirilmez.
- Kalıcı günlük rapor legacy/V1/subscriber demo veya router-events çağırmaz.
  Kaynak hatasında fallback yok. Tüm audit sayfaları tekil kimlik/sabit toplam
  denetimiyle okunur. Dashboard aynı envanter snapshot'ını audit doğrulamasında
  kullanır; ek envanter turu yapmaz. Oturum/telemetri üretilmez.
- Türkiye günü, Son24saat ve mevcut dönem filtreleri korunur. Bugün PPPoE
  sayacına yalnız uygulanmış, tarih/revizyon/hesap bağı doğrulanan kayıt girer;
  başarısız sonuçlar günlük raporda ayrı kalır. Boş veya erişilemeyen kalıcı
  audit Veri yok; mevcut audit'in seçili dönemde kaydı yoksa doğrulanmış 0 olur.
- Geçmişte işlem türü, İstanbul tarih/saat, aktör ve değişen alanların eski→yeni
  değeri öndedir. Değişmeyen snapshot alanları öne çıkarılmaz. UUID, revizyon,
  router ID, kaynak, tam eski/yeni snapshot ve hata açıklaması kapalı native
  Teknik detaylar içindedir. Audit/iş kuralları ve mutasyonlar korunur.

Doğrulama PASS:
- test_pppoe_workspace_access: 12 backend testi; ASGI + geçici sentetik SQLite.
  Yeni report testi iki görünür routerdan yalnız rapor izni verilen routerın
  audit/count kapsamını ve izin kaldırılınca 403'ü doğrular. Güçlendirilmiş yeni
  test tek başına tekrar geçti. Gerçek PostgreSQL/hesap/şema kullanılmadı.
- workspaceDashboard, managementReport, dashboardOverview, subscriberCenter ve
  managementReportView frontend hedef kapsamları PASS. Kaynak ayrımı, eski
  tarih/dönem, boş/ret durumu, değişmeyen alanların gizlenmesi, teknik disclosure,
  failed audit, legacy koruma ve mevcut tarih/sayfalama senaryoları doğrulandı.
  Eski tarih etiketini bekleyen iki UI assertion yeni tek eski→yeni gösterimine
  uyarlandı; başarısız senaryo tekrar geçti. Node transform-types kullanıldı.
- Son TypeScript/Vite production build ve git diff --check PASS.

Sınırlar: sentetik ağsız/ASGI testleridir; gerçek browser görsel kabulü, canlı API
ve PostgreSQL runtime kabulü yapılmadı. PostgreSQL verisi/kullanıcı/model/şema,
migration, VDS deploy/restart, V1/V2.5/router/RADIUS/IPsec işlemi yok.
Bu değişiklik için migration gerekmez; etkinleşmesi için ayrı onaylı backend ve
frontend yayını gerekir. 70eb954 paket kataloğunun önceki migration planı bu
çalışmanın kapsamı değildir. Commit/push sonucu teslim raporunda bildirilir.
