# V2.6 özellik koruma ve bütünleştirme — 2026-11-06

Yerel başlangıç: `main-guncel/8abfd51`. AGENTS.md, güncel PROGRESS,
V26_HTTP_LOGIN_FINAL_CHECK, V26_MANAGEMENT_UI_ACCEPTANCE ve frontend Git
geçmişi incelendi. Önceki ADMIN HTTP kabulü kullanıcı kanıtıdır; burada tekrarlanmadı.
Önceki genel PostgreSQL/abone UUID entegrasyon engelleri kapatılmış sayılmaz.

## Korunacak özellik envanteri

| Alan | Mevcut altyapı / koruma |
| --- | --- |
| LEGACY demo abone | Liste, arama, birleşik router/paket/kaynak/durum/EXPIRE filtreleri, uyarılar, seçim, aynı routerda toplu uzatma, oluşturma, düzenleme, raporlar ve detay korundu. |
| LEGACY işlemler | QuickActions: 7/15/30/60/90 gün veya özel tarih, paket/fiyat ve aktif/pasif; önizleme, onay, revizyon, router ve kaynak doğrulaması, aynı UUID davranışı korundu. Yeni detayda üç doğrudan giriş var. |
| Kalıcı sentetik abone | PPPoE/Hotspot liste, oluşturma/düzenleme, kilitli kimlik/kaynak, SubscriberRenewal ve SubscriberDailyActions korundu. Günlük işlemler: uzatma, durum, ad, paket, EXPIRE ve router; toplu işlem sınırları aynı. |
| Detay ve audit | Beş sekme, router ID bağı, bilinmeyen oturum ayrımı, önceki/yeni değerler, başarısız sonuç, aktör ve İstanbul saati; eski demo işlemleri/raporları açılır bölümü korundu. |
| Belirsiz sonuçlar | Tekil kayıt/yenileme, toplu receipt sorgusu, aktöre bağlı pending UUID ve GET ile kurtarma korundu. |
| Router | Demo envanter, kalıcı sentetik yönetim, registry/onboarding, pilot girişleri ve V1 aktarım snapshot görünümü değiştirilmedi. |
| Diğer merkezler | Dashboard, RADIUS hazırlık, Operasyon alarm/WAN, MikAjanı analiz/senaryo/kanıt, sistem/yetki ekranları değiştirilmedi. |
| Demo sınırları | İşlevsiz dışa aktarım ve planlanan kaynak devri uygulanmış özellik sayılmaz. Sentetik audit oturum kanıtı değildir. |

Geçmiş dayanakları: `372d620` kaynak ayrımı, `85c4849` legacy audit,
`3cb542b` paket/yenileme tutarlılığı, `159c50b`, `455210f`, `9eca386`
UUID kurtarma. Hiçbir çalışan özellik kaldırılmadı; mevcut kullanıcı yedekleri ve
izlenmeyen SubscriberAuditChanges.tsx görev kapsamına alınmadı.

## Kalıcı düzenleme

`subscriberActions.ts` detay yüzeyleri için ortak uygunluk politikasını taşır.
LEGACY işlemleri abonenin yetki bilgisini kendi `/subscribers/{id}` yanıtından
okur; workspace verisini legacy komutuna dönüştürmez. Kaynak, kalıcı depo,
is_demo, kayıt kimliği ve router bağı zorunludur. Workspace işlemleri merkezi
yönetici, geçerli sentetik router ve PPPoE/Hotspot gerektirir. Sunucu merkezi
yetkilendirmesi, kaynak/revizyon/onay kontrolleri değiştirilmedi.
QuickActions ortak `subscriberSaveDependencies` ile detay, geçmiş, liste,
Dashboard ve raporları yeniler. İşlem geçmişi her iki kaynakta mevcut sekmede
okunur; depolar birleştirilmez.

## Doğrulama ve engeller

- Frontend hedefli regresyon: 53 test PASS (ilk seçimin 42 testi, doğru frontend
  cwd/TypeScript transform seçeneğiyle kalan 10 test ve yeni toolbar testi).
- Yeni testler: legacy üç işlem yönlendirmesi, yetkisiz düğme/dialog reddi,
  ortak kaynak/depo/yetki politikası, workspace sekmelerinde işlemlere erişim.
- Eski Hotspot fixture başarılı yanıtta değişen alanları ve yeni revizyonu artık
  döndürür; ürün yanıt doğrulaması gevşetilmedi.
- TypeScript/Vite build PASS. Mevcut >500 kB bundle uyarısı devam ediyor.
- Testler ağsız sentetik mock kullanır; gerçek DB/HTTP veya tarayıcı kabulü değildir.
- VDS karşılaştırması BLOCKED: yerelde `/srv/mikrotik-manager-v26` yok.
  Yapılandırılmış SSH hedefinde yalnız bu klasörün kaynak SHA256 envanterini
  okuyacak komut bağlantı aşamasında `socket: Operation not permitted` ile
  reddedildi. Uzak komut çalışmadı; `.git` olduğu varsayılmadı. Çalışan VDS
  sürümüyle eşitlik veya VDS'ye özel değişikliklerin korunması doğrulanamadı.
- Push kontrolü BLOCKED: `git ls-remote origin refs/heads/main-guncel`,
  `Could not resolve host: github.com` ile başarısız. Uzak uç doğrulanmadan
  push denenmedi; force push yok.
- V1, V2.5 pilot, router, RADIUS, IPsec, canlı aboneler/DB, migration,
  servis restartı ve deploy işlemi yapılmadı.

Kalan somut adım: ağ erişimi olan ortamda VDS kaynaklarını salt okunur hash/diff
ile karşılaştırmak ve uzak dal doğrulamasından sonra normal push yapmak.
