# Abone Detay Merkezi

Mevcut Abone Merkezi arama/kaynak/paket/router/hesap/EXPIRE filtrelerini ve eski
sentetik PPPoE ekleme/yenileme işlemlerini korur. Yeni **Kalıcı sentetik PPPoE /
Hotspot** sekmesi, merkezi ADMIN için kalıcı sentetik routerlara bağlı yeni
aboneler sağlar. İki veri kaynağı listede ve detayda açıkça ayrıdır.

Yeni çalışma alanında ad/kullanıcı adı araması, erişim türü/hesap/router ID
filtreleri ve sunucu sayfalaması vardır. Ekleme ve düzenleme yalnız yerel V2
PostgreSQL kaydı ve audit oluşturur. Hesap adı, plan, durum ve EXPIRE düzenlenebilir;
kullanıcı adı, router ID, erişim türü ve tek yetkili kaynak düzenlemede korunur.
Kaynak aktarımı ve gerçek provisioning yapılmaz. Kullanıcı adları bu ayrı
çalışma alanında büyük/küçük harf duyarsız tekildir. Tekrar gönderilen aynı
istek/aktör/revizyon ikinci audit veya kayıt üretmez; eski revizyon reddedilir.

## Kaynak ve router ilişkisi

Yeni `v2_subscriber_workspace.subscribers` tablosu yalnız `demo-managed-router-*`
ID'lerine bağlanır. Foreign key `v2_router_workspace.records(id)` için DELETE
RESTRICT uygular. Servis ayrıca parent türünün DEMO_ROUTER olduğunu transaction
kilidi altında doğrular; gerçek cihaz ve TRUST_PROFILE reddedilir. Abonesi olan
routerın silinmesi/audit'i geri alınır. Router adı veya yönetim IP'si join anahtarı
değildir. Eski demo kayıtta ID yoksa isim eşleşse de güvenli router bağlantısı
üretilmez. Bu paket eski demo/gerçek envanter/grant kayıtlarını değiştirmez.

Yeni alanın yetkisi merkezi ADMIN ve mutasyonlar için ayrı
`X-V2-Demo-Action: subscriber-workspace` başlığıdır. Eski abonelerde mevcut router
scope ve yönetim kuralları aynen korunur. Parola/credential alanları kabul edilmez.

## Detay sözleşmesi

`GET /api/v1/subscriber-center/{id}` iki sentetik kaynağı ayrı projekte eder:
`PERSISTENT_WORKSPACE` ve `LEGACY_DEMO`. Ad/kullanıcı adı, router ID/adı, erişim
türü, tek LOCAL/RADIUS kaynağı, plan, hesap durumu ve EXPIRE gösterilir. Oturum
durumu UNKNOWN, son bağlantı null kalır; hesap ACTIVE olması veya last_seen
bağlantı kanıtına çevrilmez. Varsa eski sentetik IP/son örnek ayrıca etiketlenir.

Genel Bakış, Profil/Paket, EXPIRE, İşlem Geçmişi, Bağlantı Geçmişi sekmeleri ortak
Router Detay Merkezi'nin tema ve erişilebilir tab düzenini kullanır. Son 50
kayıt audit'i gösterilir; bağlantı kaynağı yoksa geçmiş uydurulmaz. Eski demo
raporları/işlemleri Genel Bakış açılır bölümünden erişilebilir kalır. Listeye
ve router ID detayına geçiş hash üzerinden yapılır; filtreler korunur.

## Açık yerel hazırlık ve doğrulama

Migration 008 yalnız yeni `v2_subscriber_workspace` şemasını oluşturur; eski
subscriber/router tablolarına seed/UPDATE yapmaz. Başlangıç migration çalıştırmaz.
Normal yerel WSL'de `./accept-subscriber-postgres.sh`, repo sahibi V2 kümesi,
rol/marker/destination/data_directory doğrulandıktan sonra 007/008 hazırlığını ve
ayrı UUID router/subscriber şemalarında hedefli PostgreSQL kabulünü çalıştırır.
Eski demo ve kalıcı router baseline'ı korunur. Cihaz/RADIUS adaptörü yoktur.
Soket engelinde ilk kontrolde durur; PG/browser PASS iddiası üretilmez.

API'ler `/subscriber-workspace` GET/POST ve `/subscriber-workspace/{id}` POST'tur.
Tipli Pydantic sözleşmeleri, explicit onay, optimistic revision, idempotency,
audit/record atomikliği ve literal UNKNOWN oturum modeli test edilir. Geçici
SQLite testleri gerçek PostgreSQL kabulü olarak sunulmaz. Mevcut canlı aboneler
ve production migration/deployment bu paketin dışındadır.

## Kompakt tablo ve abonelik uzatma

Eski listede kaynak, paket ve router/işlem bilgileri korunur. Aylık tutar paketin
altına, abonelik durumu bitiş tarihinin altına alınır; ayrı gereksiz sütunlar
kaldırılır. 1550 px alt sınır yerine 1040 px ve sınırlı/saran ad-paket-router
alanları kullanılır. Mobilde tablo kendi alanında yatay kayar. Yeni kalıcı listede
de hesap, kaynak, tarih/abonelik, kalan gün ve detay alanları ayrı gösterilir.
Arama/filtre/seçim işlemleri değiştirilmez.

**Hesap: Aktif** ile **Abonelik: Süresi dolmuş** birlikte geçerli olabilir.
Takvim tarihi hesap veya oturum durumunu değiştirmez. Bitiş bilinmiyorsa durum
üretilmez; mevcut Europe/Istanbul takvim günü ve bitiş günü dahil kuralları korunur.

Eski Hızlı İşlemler penceresi eski/yeni tarih önizlemesini korur. Sonuçta sunucunun
yanıtındaki kaydedilmiş tarih gösterilir; tüm işlemler başarılıysa tekrar düğmesi
kapanır. Kayıp/eksik sonuçlar aynı istek kimliğiyle alınabilir. Router ID varsa
önizleme bunu esas alır; isimle lookup yalnız tek bir eşleşmede kullanılabilir.

Kalıcı sentetik abonenin EXPIRE sekmesindeki **Hızlı İşlemler · Aboneliği uzat**
7/15/30 gün veya özel tarih, eski/yeni önizleme ve ayrı onay sunar.
`POST /api/v1/subscriber-workspace/{id}/renew` yalnız bitiş tarihini değiştirir.
Aktör, kaynak, eski tarih, revizyon ve server-side Türkiye günü önizlemesi
kontrol edilir; kayıt ve RENEWAL audit'i tek transaction'dadır. Aynı istek yeniden
uygulanmaz; payload/aktör/revizyon uyuşmazlığı ve audit hatası değişiklik yapmaz.
Bilinmeyen eski tarihte yalnız özel tarih mümkündür. Hesap durumu korunur.

Detay İşlem Geçmişi eski tarih, yeni tarih, UTC saklanan işlem zamanının İstanbul
gösterimi ve Uygulandı sonucunu sunar. Yalnız tamamlanmış kayıt audit'i gösterilir;
başarısız denemeler başarı geçmişine eklenmez. Credential veya ham audit JSON'u
projeksiyona taşınmaz. Mevcut JSON/audit şemaları kullanılır; yeni migration/seed
gerekmez. PostgreSQL kabul betiğine üç hedefli uzatma/retry/rollback senaryosu
eklenmiştir; sandbox engelindeki SKIPPED sonuçlar PG PASS değildir.

## Router ↔ Abone ilişkisi

Router Detay Merkezi PPPoE/Hotspot sekmeleri
`GET /api/v1/router-center/{id}/subscribers` sözleşmesini kullanır. `access_type`
zorunlu PPPOE/HOTSPOT, query/status/page/page_size kontrollüdür. Kalıcı sentetik
kaynakta router ID/tür doğrulaması, COUNT ve tek JOIN'li sayfa okuması yapılır;
sorgu sayısı abone sayısıyla artmaz (guard marker'ı dahil en fazla dört SELECT).
Router adı/modeli aynı JOIN'den gelir; satır başına detail sorgusu yoktur.

Eski demo kaynağında mevcut router grant'i önce doğrulanır ve yalnız açık
router_id + erişim türü eşleşmeleri gösterilir. İsim benzerliği, eksik erişim
türü veya geçmiş sayaçlardan ilişki tahmin edilmez. Gerçek envanter için mevcut
operator allowlist korunur; bağlı abone kaynağı yokken total=null / Hazırlanıyor
döner. Sentetik hesaplar gerçek cihaz sekmesine taşınmaz.

Router sekmesindeki abone adı ve abone özetindeki router adı ID tabanlı çift
yönlü bağlantıdır. Özet ayrıca router modelini ve kayıt kimliğini gösterir.
Bağlantı geçişleri tek seviyeli, yalnız uygulama içi `return_to` bağlamı taşır;
geri düğmesi önceki detay/sekme/arama/durum/sayfa bağlamını geri getirir. Harici
URL'ler ve iç içe dönüş zincirleri kabul edilmez. İlişki paneli yalnız GET yapar;
aktif hesaplar çevrimiçi oturum olarak sunulmaz.

Mevcut FK DELETE RESTRICT korunur: bağlı abonesi olan routerın silinmesi reddedilir,
router/subscriber/audit transaction'ı yarım uygulanmaz. Aboneler cascade ile
silinmez. Eski/import edilmiş bozuk bir bağ varsa yetkili detay ekranı stored
router_id'yi korur, ad/model uydurmaz ve Router kaydı bulunamadı gösterir; link
üretilmez. Merkezi ADMIN eski orphan kayıtları görebilir; sınırlı kullanıcıların
router scope 404 sınırı delinmez. Router değişikliği hâlâ mevcut immutable ilişki
kuralına tabidir; düzenleme ile yetki/kaynak aktarımı yapılamaz.

Yeni tablo/migration yoktur. `accept-subscriber-postgres.sh` içindeki mevcut
opt-in PostgreSQL sınıfı kalıcı ilişki, iki erişim türü, filtre/sayfa, model JOIN'i
ve sabit sorgu sayısı kabulünü de içerir. Testler ayrı UUID şemalarındadır; mevcut
router/abone kayıtlarına yazmaz. Orphan gösterimi yalnız disposable SQLite
bozulma fixture'ında sınanır; uygulama FK koruması gevşetilmez.
