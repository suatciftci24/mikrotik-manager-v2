# V2.6 genel kabul değerlendirmesi

Tarih: 2026-11-07. İncelenen temel: `main-guncel/d027064`; başlangıç çalışma
ağacı temiz. **Belge/kaynak incelemesi PASS; V2.6 bütünsel kabul ve V2.7'ye
kabul edilmiş sürüm olarak geçiş BLOCKED.** Bu görev yalnız belge değiştirir.

Bu karar yeni bir çalışma zamanı arızası teşhisi değildir. Kaynakta mevcut
özellik, geçmiş test kanıtı ve henüz doğrulanmamış entegrasyon ayrı tutuldu.
Önceki PASS testleri/build çalıştırılmadı; PostgreSQL/HTTP/socket/tarayıcı veya
VDS bağlantısı denenmedi. Canlı durum yerel kaynak ağacından çıkarılmadı.

## Özellik ve kanıt matrisi

| Alan | Tamamlanan yerel işlev | Mevcut kanıt ve kabul sınırı |
| --- | --- | --- |
| Dashboard | Sentetik genel durum, bitiş ve günlük PPPoE/WAN özeti, filtreli merkez bağlantıları; rapor yetkisi ve Türkiye günü; V1 sağlık görünümü ayrı kaynak. Beş sağlık sınıfı, eskilik/bilinmeyen veri ayrımı, 60 sn okuma ve kaynak izolasyonu mevcut. | [Yerel Chromium kabulü](V26_LOCAL_BROWSER_ACCEPTANCE.md) ve [sağlık kabulü](V26_HEALTH_ACCEPTANCE.md) sentetik PASS. Tarihsel gerçek V2.6 Dashboard kabulü başarısız ve rollback doğrulanmış; tarihsel assertion operandları bilinmiyor. Yeni yerel düzeltmeler bu canlı engeli kapatmaz. Ana sentetik Dashboard kalıcı workspace toplamı değildir. |
| Router Merkezi | Demo envanter, kalıcı sentetik router CRUD/audit, kayıtlı cihaz/onboarding ve V1 aktarım snapshot'ı ayrı; kaynak/ADMIN kapıları, detay sekmeleri, bağlı abone görünümü ve güvenli bağlantı akışı var. | [Yönetim UI kabulü](V26_MANAGEMENT_UI_ACCEPTANCE.md): dört kaynak ve yetkisiz hash reddi, sentetik tarayıcı PASS. Registry metadata veya kayıtlı okuma snapshot'ı güncel cihaz bağlantısı değildir. Gerçek kaynakta hesap yazma kapalı; yeni cihaz/pilot kabulü bu incelemeyle verilmez. |
| PPPoE Abone Merkezi | LEGACY ve PERSISTENT_WORKSPACE ayrımı; liste/arama/filtre, PPPoE/Hotspot, oluşturma/düzenleme, router ID bağı, detay sekmeleri, geçmiş ve raporlar. LOCAL/RADIUS tek yetkili kaynak; hesap aktifliği oturum bilgisine dönüştürülmez. | [Özellik koruma envanteri](V26_FEATURE_PRESERVATION_ACCEPTANCE.md) ve [abone kabulü](V26_PPPOE_SUBSCRIBER_ACCEPTANCE.md) yerel PASS. Bilinmeyen/eksik router veya kaynakta yazma reddi mevcut. Gerçek oturum/cihaz yazma ve FreeRADIUS işletimi tamamlanmış özellik değildir. |
| Abonelik işlemleri | LEGACY QuickActions: gün/özel tarih, paket ve aktif/pasif. Workspace: yenileme ve günlük/toplu paket/durum/ad/tarih/router işlemleri. Önizleme/onay, expected revision/source/router, UUID ve yetki kontrolleri mevcut. | [v26-test-001 kabulü](V26_TEST001_FUNCTIONAL_ACCEPTANCE.md): SQLite/ASGI ve LEGACY bellek senaryoları PASS; önceki geçici PG tutarlılık testleri [ayrı kapsamda](V26_PPPOE_SUBSCRIBER_ACCEPTANCE.md) PASS. Bunlar güncel gerçek HTTP kabulü değildir. `d027064` yalnız yeni HTTP test aracını onarır; Ev WSL sonrası başarı sonucu bildirilmedi. |
| Audit ve sonuç kurtarma | İşlem+audit aynı transaction; eski/yeni paket/tarih, aktör/UTC ve İstanbul gösterimi, başarısız receipt, replay; kayıp yanıtta manuel GET; aktöre bağlı pending UUID ve sekme/kimlik değişimi kontrolü. | [Pending kabulü](V26_PENDING_RECOVERY_ACCEPTANCE.md) ve abone kabulündeki handler/SSR/DB testleri PASS. Güncel HTTP, gerçek tarayıcı reload/sekme ve süreç yeniden başlatma zinciri tümüyle kanıtlanmış değil. Pool dispose sonrası yeni bağlantı testi süreç restart kabulü değildir. |
| Uyarılar ve operasyon | Abonelik bitiş kartları/filtreleri; P1–P4 merkezi alarmlar, kaynak/episode, ACK ve kişisel READ ayrımı, audit, kanıt, WAN olayları ve MikAjanı bağlantıları. Eksik IPsec/ölçümde alarm uydurulmaz; ACK arızayı çözmez. | [PROGRESS](PROGRESS.md), “Aşama 13 doğrulanmış WSL durumu”: kullanıcı 20 tarihsel tarayıcı kontrolü PASS bildirmiş. Yönetim UI fixture kabulü de var. Güncel V2.6 kimlik/şema üzerinde alarm ACK/READ HTTP kalıcılık-audit bütünleşmesi için yeni kapanış kanıtı yok; tarihsel PASS silinmez. Abone kabul betiği alarm kabulünü kapsamaz. |
| Mobil arayüz | Responsive kaynak seçiciler, menü/filtreler, saran etiketler, kart/tablo düzeni, yerel kaydırma, modal/Escape/odak ve tema düzenleri mevcut. | Yönetim UI 1440/375 px Beyaz/Gece; sağlık/rapor kayıtlarında 1440/390/320 px ve Sistem teması sentetik PASS. Güncel gerçek oturumla oluşturma/uzatma/paket/durum, audit, hata ve recovery'nin mobil uçtan uca kabulü yok. Masaüstü mock/SSR bu kanıtın yerine geçmez; fiziksel mobil cihaz kabulü iddia edilmez. |

## Kabulü doğru yorumlamak için mevcut sınırlar

- **ADMIN giriş/oturum PASS korunur.** [Son kullanıcı doğrulaması](V26_HTTP_LOGIN_FINAL_CHECK.md)
  izole VDS'de ready200, çalışan/disk SHA eşitliği, login200, cookie ve me200
  bildirir. Kesin ölçülen SHA değeri ayrıca verilmemiştir; `d027064` ile
  çalışma zamanı eşitliği varsayılmaz. Eski 401/503 kayıtları güncel arıza
  sayılmaz; kullanıcıdan yeniden ADMIN oluşturması istenmez.
- **Yeni PostgreSQL+HTTP zinciri açık.** [Betik kabul kaydı](V26_TEST001_HTTP_ACCEPTANCE.md):
  eski `.text` eksikliği dört alt testte AttributeError üretiyordu; genel
  rapor gerçek hatayı gizliyordu. Beş offline regresyonla düzeltildi.
  Betiğin bulunması, statik PASS veya eski dört genel hata çıktısı API/audit
  başarı kanıtı değildir. Yeni betik tek sentetik workspace abonesini kapsar;
  LEGACY HTTP/UUID, alarm ve tarayıcı kabulünü topluca kapatmaz.
- **Gerçek bağlantılar tamamlanmış sayılmaz.**
  [PPPoE okuma servisi](../backend/app/services/pppoe_readonly.py)
  varsayılan `disabled_binding` ile kapalıdır; demo ölçümünden gerçek oturum
  üretilmez. [Router detayı](../frontend/src/components/RouterDeviceCenter.tsx)
  kayıtlı cihaz hesaplarında salt okunur sınır gösterir.
  [RADIUS ekranı](../frontend/src/screens/Modules.tsx) açıkça hazırlıktır.
  Kaynak devri, canlı RADIUS yönetimi ve cihaz provisioning'i eksik kapsamdır;
  bu inceleme bunları geliştirme veya bağlantı açma yetkisi vermez.
- **Dışa aktarım uygulanmamıştır.**
  [Abone ekranındaki](../frontend/src/screens/Subscribers.tsx) düğme yalnız
  devre dışı açıklaması gösterir; gerçek dosya/export kabulü yoktur.
- **Yerel aday ile yayın eşitliği kanıtı ayrı.** Önceki kopyalanmış 109 dosya
  ve seçici overlay koruma karşılaştırması tarihsel yerel kanıttır.
  [Son paket incelemesi](V26_QUICK_ACTIONS_PACKAGE_REVIEW.md) eksik
  source/config/public/dist girdileri nedeniyle dağıtıma hazır paketi BLOCKED
  bırakır. Bu kayıt güncel VDS dosyalarının eksik olduğunu kanıtlamaz.
  Dashboard rollback hedefi Fresh Pilot, ADMIN kabul hedefi izole V2.6'dır;
  ortamların kaynak/şema/kabul sonuçları birbirine taşınmaz.

## Gerçek riskler ve V2.7 öncesi öncelikler

P0 kabul edilmiş V2.6 tabanını engeller; P1 ilgili işlevin genel kabulünü
engeller. P2 ölçek veya kapsam kararına bağlıdır. Eksik kanıt otomatik ürün
kusuru olarak işaretlenmez; test beklentileri gevşetilerek kapatılmaz.

| Öncelik | Açık risk / zorunlu iş | Kapanış ölçütü ve en dar sonraki kapsam |
| --- | --- | --- |
| P0 | Güncel PostgreSQL + gerçek HTTP transaction/audit zinciri kapanmadı. Test aracı onarımı başarı sanılırsa V2.7 yanlış kabul tabanına oturur. | İzinli Ev WSL'de mevcut disposable `accept-v26-test001-http.sh` sonucunu d027064 tabanına atfet; yalnız kendi kümesinde dört işlem, revision/audit/replay, rollback/ret ve temizlik PASS. Başka hata varsa yalnız raporlanan aşamayı düzelt; önceki PASS suite'i tekrarlama. |
| P0 | Dashboard sağlık gerçek kabulü tarihsel FAIL/ROLLBACK; eski operandlar yok. Yeni sentetik örnek eski hatanın nedeni sayılamaz. | Mevcut yerel karşılaştırma/tanı düzeltmelerini koru; aynı kaynak/snapshot/zaman ve assertion adımı/operand tanısı bulunan kabul kanıtı olmadan gerçek sağlık yayınına hazır deme. Yeni canlı doğrulama gerekiyorsa ayrı kapsam/onay; bu görevde yayın veya yeniden deneme yok. |
| P1 | LEGACY ve workspace'in güncel gerçek oturumla liste/detay/audit/GET receipt ve mobil akışı birlikte kanıtlanmadı. Yanlış kaynak, eski ekran veya belirsiz sonucun ikinci kez uygulanması riski. | Mevcut PASS handler/policy testlerini yeniden koşmadan, yalnız eksik gerçek HTTP+browser zincirini izole sentetik kayıtlarla doğrula: create/edit, uzatma/paket/pasif/aktif, GET sonucu, reload/pending, bağlı ekran yenileme, VIEWER/kaynak reddi. 320/390px, tema, modal/odak ve hata durumunu dahil et. |
| P1 | Güncel alarm ACK/READ şema/kimlik/HTTP kalıcılık-audit kanıtı eksik. `storage_ready=false` kaynak okunurken işlem engeller; ACK ile çözülme karıştırılabilir. | Yalnız yeni izole sentetik alarmda ACK ve READ ayrımı, occurrence/UUID replay, rollback, kişisel okundu/yetki, yeniden okuma ve kaynak kaybını doğrula. Abone/işlem geçmişi korunmalı. Mevcut DB'ye bakım uygulamak bu değerlendirme kapsamında değildir. |
| P1 | Kabul adayı, yayın paketi ve hedef sürüm/config/dist eşitliği belirsiz. Eski veya eksik baseline üzerine paketleme özellik kaybı doğurabilir. | V2.6 sürüm kapanışında aday SHA ve manifesti kaydet; mevcut özellik koruma envanteriyle yalnız değişen kaynakları karşılaştır. Gerekli baseline/önceki test edilmiş paket yoksa yayın hazır sayma. Canlı check/apply ayrıca açık onay ister. |
| P2 | [Günlük özet loader'ı](../frontend/src/lib/dailySummary.ts) her abone için detay isteğini `Promise.all` ile açıyor. [Rapor loader'ı](../frontend/src/lib/managementReport.ts) tüm workspace sayfalarını okuyor; hata/değişen toplamda bilinmiyor döndürüyor. | Küçük demo için mevcut tasarım; kanıtlanmış performans arızası yok. Büyük envanter hedeflenecekse önce eşzamanlı istek/yük/bellek ölçümü, gerekirse sınırlı paralellik veya sunucu agregasyonu. Bundle >500 kB uyarısı aynı ölçüm planına alınmalı; tek başına kabul hatası değildir. |
| P2 | RADIUS yönetimi, gerçek cihaz hesap yazması/kaynak devri ve export henüz tam ürün kapsamı değil. | V2.7 kapsamını açıkça belirle; mevcut hazırlık/devre dışı etiketlerini koru. Bu alanlar vaat edilecekse ayrı tasarım, yetki/adaptör/transaction/rollback ve sentetik kabul gerektirir. Yokluklarını güvenlik kapısını açarak giderme. |

## V2.7 hazırlık kararı

**V2.7 planlama ve tasarımına başlanabilir; kabul edilmiş V2.6 tabanı ve
canlıya hazır sürüm olarak geçiş HAZIR DEĞİL / BLOCKED.** İlk adım yeni özellik
veya deploy değil, mevcut disposable PostgreSQL+HTTP sonucunun kapanışıdır.
Ardından yalnız yukarıdaki açık P0/P1 kapsamlar ele alınır. Tarihsel rollback
silinmez; ADMIN PASS ve önceki sentetik/PG/arayüz PASS kapsamları yeniden açılmaz.
Gerçek cihaz/RADIUS işlevi V2.7 hedefi yapılırsa ayrıca onaylı ayrı kapsamdır.

Bu görevde VDS/SSH, V1/V2.5, router/RADIUS/IPsec, mevcut veritabanı, migration,
servis start/restart/deploy veya stash işlemi yoktur. Kod/test/bağımlılık ve
kullanıcı dosyaları değiştirilmedi; yalnız bu belge ve PROGRESS güncellendi.
Doğrulama belge bağlantıları, kapsam/kanıt tutarlılığı ve `git diff --check` ile
sınırlıdır; yeni uygulama/test/build PASS iddiası yoktur.

## f21cedf sonrası Dashboard/rollback yerel ek kabulü — 2026-11-07

[Sağlık kabulünün son bölümü](V26_HEALTH_ACCEPTANCE.md): eksik ölçüm zamanında
NaN eşitliğinin kararlı frame'i sürekli reddetmesi düzeltildi; tam ölçüm kapısı
gevşetilmedi. Gerçek Dashboard karşılaştırıcısının sayaç FAIL'iyle geçici
frontend üzerinde sağlık kapısı/rollback, kaynak/dist hash geri dönüşü,
korunan yedek, drift/bozuk yedekte güvenli duruş doğrulandı. 7 yeni test ve
11 doğrudan ilgili mevcut kontrol PASS; yeni browser/PG/HTTP veya canlı kabul
yok. Frontend/backend ürün sınıflandırması değişmedi.

P0'ın **yerel sağlık başarısızlığında rollback kanıtı** kısmı tamamlandı.
Özgün fffac4a receipt'inde operand yok; tarihsel Dashboard nedeni ve canlı
kabul BLOCKED kalır. Yeni kütüphane sağlık kapısı canlı dağıtım akışına
bağlanmadı. PG/HTTP ve diğer açık kabul maddeleri değişmez; V2.7'ye kabul
edilmiş sürüm olarak geçiş hâlâ hazır değildir.

## a7458b2 sonrası özgün Dashboard kanıtı araştırması — 2026-11-07

[Sağlık kabul raporunda](V26_HEALTH_ACCEPTANCE.md) özgün fffac4a FAIL/rollback
receipt'leri, metadata ve SHA256 kimlikleri kaydedildi. Özgün hata-anı API/DOM,
PNG, stack veya operand bulunmadı. Eski runner snapshot'ı assertion'lardan
sonra yazıyor ve catch operandları/konumu atmaktaydı; kayıt kaybı kaynakla
kanıtlandı. İlk denemenin yerel kanıt dizini bu kopyada yok; sonraki sentetik
ve V2.5 adapter artefaktları ayrı tutuldu.

Yeni kesin ayrım: frameStable d733ba8'de, özgün ikinci denemeden sonra eklendi;
a7458b2'nin NaN düzeltmesi fffac4a'nın başarısız assertion'ının doğrudan nedeni
olamaz. Tarihsel gerçek neden yine BLOCKED; önceki yerel PASS ve canlı kabul
engelleri değişmez. Yeni test/bağlantı yapılmadı. Sonraki tek kanıt kaynağı,
varsa özgün test bilgisayarındaki bağımsız yerel hata-anı arşividir; aynı yerel
aramalar veya yeni yayın bu boşluğu kapatmaz.
