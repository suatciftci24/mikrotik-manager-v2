# V26 statik web yayını planı — uygulanmadı — 2026-11-16

Mevcut bilinen düzen: HTTPS v26.mikmanager.com.tr → mevcut Nginx →
127.0.0.1:15173 Vite dev; API → 127.0.0.1:18996. Gerçek Nginx snapshot'ı yeni
salt okunur preflight ile doğrulanmadan bu topoloji canlıda yeniden ölçülmüş
sayılmaz. Vite dev kimlik PASS'i üretim yayın kabulü değildir.

## Hata ayrımı

f72cc67 iki VITE_DEV_HTML_IDENTITY_REJECTED verdiği kullanıcı tarafından
bildirildi. O sürüm alt koşulları raporlamadığı için bu olayların gerçek nedeni
eski kayıttan çıkarılamaz. Yerel Vite 6 kaynak processNodeUrl fonksiyonu HMR
sonrasında script URL'sine t=<lastHMRTimestamp> ekler; eski tam-string eşitliği
bu meşru varyantı yanlış reddeder. Bu kod kusuru düzeltildi. VDS'de bunun gerçek
olay nedeni olduğu, yeni diagnostics gözlemlenmeden iddia edilmez.

Yeni rapor expected/checks, script türleri, root sayısı, content-type, byte
uzunluğu ve HTTPS/loopback/local index SHA256 bilgilerini içerir. URL query'si,
inline HTML, nonce, token, cookie veya ham script/HTML basılmaz. Bilinmeyen URL
yalnız hash olarak temsil edilir. Yalnız tek sayısal t parametresi kabul edilir;
başka query/fragment/host/path çözümleme veya normalizasyonu yapılmaz. Module
tipi ve tek root mount şartları korunur/sıkılaştırılır. Domain/PID/cwd/Nginx/
loopback ve tam kaynak byte eşitliği kontrolleri devam eder.

- source_entry_module=false, geçerli sayısal t görülürse yeni kodun bu varyantı
  kabul etmesi gerekir; hâlâ false ise başka entry/type/path sorunu vardır.
- no_built_assets=false ise Vite süreci compiled asset HTML'i sunmaktadır;
  bu sayfa dev-source kimliği sayılamaz, kontrol gevşetilmez.
- unique_root_mount=false ise beklenen DOM yoktur veya yinelenmiştir.
- upstream_bytes_equal=false ise HTTPS ile doğru loopback aynı HTML'i sunmaz.
- Local index source/built sayıları ve hash, yerel giriş dosyası ile sunulan
  yanıtın farklı modlarını güvenli ayırır. Hash farkı tek başına transformed
  HTML için hata değildir; içerik eşitliği HTTPS/loopback arasında zorunludur.

## Üretim için ayrı statik plan — yeni canlı onay ve kabul gerektirir

1. Önce domain/API/web listener ve ilgili iki unit/config'in güvenli snapshot'ı,
   stash OID'leri ve doğrulanmış DB yedeği korunur. Yeni preflight diagnostics
   incelenir; gerçek topoloji farklıysa burada varsayılan plan uygulanmaz.
2. Kabul edilmiş kaynak commit'inden build alınır; manifest kaynak ve dist
   SHA256'leriyle private staging'e konur. Release dizini V26'ya ayrılır;
   statik yayın için frontend kaynakları, .env, node_modules, .git veya yedekler
   webroot yapılmaz. Mevcut backend/DB bu frontend planında değiştirilmez.
3. Paylaşılan dış Nginx ve diğer domain/vhost'ları değiştirmeden mevcut V26 web
   unit'i için ayrı, minimal statik Nginx yapılandırması hazırlanır. Bu süreç
   mikadmin/mikadmin olarak mevcut aynı 127.0.0.1:15173 portunu kullanır;
   pid/log/temp yolları V26-private olur. Root yalnız hash'li release/dist olur;
   SPA fallback kontrollüdür. /src, /@vite, gizli dosya ve traversal reddedilir.
   API dış Nginx'teki mevcut 18996 yönlendirmesinde kalır.
4. Yeni unit oluşturulmaz, ikinci port/servis başlatılmaz. Syntax ve izole
   static HTTP kabulünden sonra yalnız mevcut V26 web unit'inin ExecStart
   değişimi planlanır. Vite durdurulur, tam kendi listener PID'sinin kapandığı
   ve 15173'ün boş olduğu doğrulanır; sonra aynı unit statik Nginx ile başlatılır.
   Böylece iki servis aynı portta yarışmaz; reuseport/fallback port kullanılmaz.
   Bu unit değişimi/daemon-reload/start için ayrı açık canlı kapsam gerekir.
5. Yeni üretim servis validator'ı ayrı exact-static-mode sözleşmesiyle hazırlanır;
   bugünkü npm-dev kontrolü sessizce genişletilmez. Dış Nginx config/reload gerekmez.
   Statik HTTPS index/JS/CSS hash'leri, SPA route, cache başlıkları, Vite dev
   endpointlerinin kapalı olması, API ve mevcut ADMIN login/GET panel kabulü
   doğrulanır. Eski dev oturumlarının HMR yerine sayfa yenilemesi gerekir.
6. Bu frontend planının manifest'i UI kaynak sürümünü gösterir; backend Git HEAD'i
   aynı kaldıysa tüm uygulama bu commit'e geçti denmez. Backend yayını/migration
   ayrıca kapsamlandırılır. V1/V2.5/router/RADIUS/IPsec/DB/hesaplar değişmez.
7. Hata halinde yalnız V26 web unit/config ve eski release seçimi doğrulanmış
   yedekten geri alınır; kendi portu kapatılıp eski tek listener geri getirilir.
   Eski Vite'a dönüş üretim PASS sayılmaz. Git stash/yedekler silinmez; DB restore
   veya herhangi bir veri silme bu planda yoktur.

Bu plan uygulanmadı; mevcut apply motorunun VITE_DEV_CUTOVER_NOT_ENABLED kapısı
korundu. Salt okunur doğrulama komutu:

```bash
python3 ~/Codex-Projects/mikrotik-manager-v2/tools/deploy-v26-office.py --preflight-only
```
