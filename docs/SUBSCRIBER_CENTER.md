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
