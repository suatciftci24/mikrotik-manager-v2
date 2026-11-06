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

## Kopyalanmış VDS kaynaklarıyla gerçek karşılaştırma — ac90735 sonrası

2026-11-06: `/home/suat/Codex-Projects/v26-vds-reference/src` yerelde okundu.
109 dosyanın tamamı `189a717357a7136c83ccf5958a7d136c3f90303f` Git içeriğiyle
birebir eşleşiyor; bu commit ac90735'in ortak atasıdır. ac90735'e göre 22
değişmiş ve 9 eklenmiş tracked kaynak yolu bulunuyor. Yalnız kullanıcıya ait
izlenmeyen SubscriberAuditChanges.tsx bu Git karşılaştırmasına dahil değildir.
Kaynak kopyası değiştirilmedi; önceki SSH BLOCKED bu yerel karşılaştırmayı
artık engellemiyor. VDS'nin şu anda aynı kaynakları sunduğu iddia edilmez.

LEGACY detay işlemleri ac90735'te zaten mevcut. Bunları VDS tabanına taşımak
için tüm frontend'i geri almak veya güncellemek gerekmedi. `QuickActions`
yalnız yenileme listesi için recovery hook'una bağımlıydı; liste yeni
`subscriberDependencies.ts` modülüne ayrıldı. Hook eski export'u korur.
Böylece eski VDS `api.ts` üzerinde bulunmayan ApiError/pending recovery
zinciri seçici pakete zorunlu bağımlılık olmaz. Yeni npm paketi veya lockfile
değişikliği yok; aday yerel kilitli paketlerle derlendi.

### Seçici aday ve özellik koruması

Yeni `frontend/scripts/prepare-v26-legacy.mjs` yalnız yerel `.local` altında
yeni bir aday oluşturur. Pinli `v26-vds-reference.json` 109 SHA256 değerini
doğrular; farklı/eksik/ek dosyada, symlink'te veya mevcut çıktı dizininde durur.
Git, SSH, npm install, backend veya DB süreci başlatmaz. Source/manifest
kontrolü bitmeden dosya kopyalamaz; referansı ve mevcut çıktıları değiştirmez.

Overlay'in tamamı (6 mevcut dosya güncellenir,4 dosya eklenir):

```text
components/SubscriberDeviceCenter.tsx
components/LegacySubscriberActions.tsx
components/QuickActions.tsx
screens/Details.tsx
lib/subscriberActions.ts
lib/subscriberDependencies.ts
lib/quick.ts
lib/resourceEvents.ts
lib/useResource.ts
styles/subscriber-edit-highlight.css
```

| Korunan VDS özelliği | Kanıt / entegrasyon |
| --- | --- |
| Liste, kaynak sekmeleri, filtreler, seçim, oluşturma, raporlar | Subscribers/App kaynakları dahil overlay dışındaki 103 dosya byte düzeyinde aynı. |
| Workspace PPPoE/Hotspot edit, günlük/toplu işlemler ve yenileme | SyntheticSubscribers, SubscriberEditor, SubscriberDailyActions ve SubscriberRenewal VDS sürümleri aynı; güncel paket ve 7/15/30/60/90/özel tarih regresyonu PASS. |
| Router/Operasyon/alarm/MikAjanı/sistem ekranları | Bu kaynaklar değiştirilmedi; adayın tüm kaynak ağacı derlendi. |
| Abone beş sekme/router bağı/legacy rapor açılır bölümü | DeviceCenter/Details regresyonu; workspace edit/renew/manage callback'leri mevcut toolbar'da kalır. Eski yinelenen header edit düğmesinin işlevi toolbar üzerinden korunur. |
| LEGACY süre/paket/aktif-pasif | Yetkili canonical detaydan QuickActions; source/router/revision/onay korunur. Mevcut demo-quick, demo-options, routers ve subscriber GET sözleşmeleri kullanılır; yeni backend endpoint'i yok. |
| Audit | Paket+tarih birlikte, eski/yeni değerler, aktör/İstanbul saati ve başarısız sonuç korunur. |
| Bağlı veri yenilemesi | Ayrı dependency modülü ve query'li kaynak invalidation; detay/liste/router/Dashboard/rapor yenilenir. |

Aday: `.local/v26-legacy-review`. `preservation.json` önce/sonra kaynak ve
overlay hash'lerini, lockfile hash'ini içerir; `build-acceptance.json` yerel
sonuçları ve üretilen dist hash'lerini kaydeder. Bu dosyalar Git dışındadır.
Referans dışında index/public/Vite yapılandırması sağlanmadığından aday bunlar
için yerel frontend girdilerini kullanır; VDS HTML/public/config eşitliği
doğrulanmış sayılmaz. Yayın öncesi bu sınır ayrıca kontrol edilmelidir.

### Hedefli kabul

- Yerel frontend: 43 hedefli test PASS; yeni entegrasyon/dependency, detay,
  QuickActions, yenileme, GET save recovery, kaynak yetkisi ve invalidation.
- VDS tabanlı seçici aday: 10 test PASS; üç gerçek React handler akışı,
  yetki/kaynak reddi, beş sekme, audit, workspace yenileme, dosya koruma ve
  drift/mevcut çıktı dizini reddi. Ağ istekleri sentetik fetch mock'udur.
- Her iki ağaçta `npm run build` (TypeScript + Vite) PASS; mevcut >500 kB
  bundle uyarısı sürer. Gerçek HTTP/DB veya VDS browser kabulü yapılmadı.
- Eski subscriptionActions harness'ına CSS loader eklendi; eski ikinci POST
  beklentisi mevcut tekPOST+UUID GET receipt sözleşmesine uyarlandı. Bir yeni
  link assertion'ı nested Facts render'ına düzeltildi. Yalnız başarısız
  kapsamlar tekrar çalıştırıldı; ürün güvenliği/test assertion'ları gevşetilmedi.

### Güvenli VDS güncelleme yöntemi — burada uygulanmadı

1. Ayrı dağıtım onayı sonrası yalnız V2.6 frontend'in güncel kaynak hash'lerini
   `preservation.json.before` ile karşılaştırın. Fark varsa durun; yeni
   snapshot üzerinde entegrasyon gerekir. V1/V2.5 kökleri ve webroot'ları
   bu yayın hedefi olamaz. index/public/base-path ve mevcut API sözleşmesini
   ayrıca salt okunur karşılaştırın; bu görevde bunların VDS kopyası yoktu.
2. Yeni bir yerel aday üretip aynı test/build'i çalıştırın. Referans klasörüne
   ve kullanıcı dosyalarına yazmayın. Örnek **Ev WSL proje kökü** komutu:

   ```bash
   node frontend/scripts/prepare-v26-legacy.mjs --reference /home/suat/Codex-Projects/v26-vds-reference/src --output /home/suat/Codex-Projects/mikrotik-manager-v2/.local/v26-legacy-new
   ```

3. Yalnız test edilmiş adayın statik `dist` çıktısını ve bütünlük manifestini
   ayrı sürümlü V2.6 frontend release dizinine hazırlayın; mevcut statik
   sürümü rollback için koruyun. Dizin, sunum yolu ve dosya hash'leri
   doğrulandıktan sonra mevcut hosting düzeninin desteklediği atomik webroot
   geçişini kullanın. Kaynak dosyalarını tek tek canlıya kopyalamayın; tam
   repo pull'ı, backend aktarımı, servis restartı, migration veya DB değişimi
   bu güncellemenin parçası değildir. HTML/public farkı varsa körlemesine
   yerel index/public kullanmayın; önce aday girdileriyle uzlaştırın.
4. Yayın sonrası mevcut yetkili oturumla salt okunur görünüm/asset ve kaynak
   doğrulaması yapın. Beklenmeyen eksiklikte önceki statik release'e dönün;
   gerçek abone/cihaz üzerinde test yazımı yapmayın. Gerçek yazma senaryoları
   yalnız ayrıca izinli sentetik kabul hedefinde doğrulanabilir.

VDS bağlantısı, dağıtım, servis/DB/ADMIN/parola/migration ve gerçek cihaz
işlemi yapılmadı. Genel PostgreSQL/UUID kabul boşlukları bu UI testiyle kapanmaz.
