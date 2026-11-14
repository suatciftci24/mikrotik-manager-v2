# Paket kataloğu migration planı — UYGULANMADI

Kapsam: yalnız V2.6 izole veritabanındaki mevcut v2_subscriber_workspace şeması.
Yeni veritabanı/servis yok. Bu belge çalıştırılabilir migration dosyası değildir;
uygulama başlangıcı veya deploy sırasında DDL çalıştırılmaz. Canlı uygulama için
ayrı, işlem kapsamına özgü kullanıcı onayı gerekir.

Ön koşullar: hedef kimliği/runtime/DB rolü ve mevcut 007/008 şemaları salt okunur
kontrol edilmeli; yedek ve geri dönüş planı doğrulanmalı. Başka checkout'ta 011
ayrılmış olabileceğinden migration sürüm numarası uygulama öncesinde seçilmeli.
Mevcut kullanıcı/parola, router, abone ve audit kayıtları değiştirilmez veya seed
edilmez. Statik demo paketleri içeri aktarılmaz; katalog boş başlar.

İleri planın DDL taslağı (ORM modelleriyle eşleşir):

```sql
CREATE TABLE v2_subscriber_workspace.packages (
    id VARCHAR(64) PRIMARY KEY,
    name_key VARCHAR(360) NOT NULL UNIQUE,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    fields JSON NOT NULL
);
CREATE TABLE v2_subscriber_workspace.package_events (
    id VARCHAR(36) PRIMARY KEY,
    package_id VARCHAR(64) NOT NULL,
    actor_id VARCHAR(80) NOT NULL,
    occurred_at VARCHAR(40) NOT NULL,
    revision INTEGER NOT NULL,
    changes JSON NOT NULL
);
CREATE INDEX ix_v2_subscriber_workspace_package_events_package_id
    ON v2_subscriber_workspace.package_events (package_id);
```

name_key uygulamanın casefold anahtarıdır; 120 karakter adın Unicode genişlemesi
360 karakterlik alana sığar. fields; ad, Mbps hızları, isteğe bağlı profil eşleme
etiketi/aylık TRY ücreti, gün süresi ve active içerir. Para Decimal doğrulanır ve
JSON'da ondalık metin saklanır. İşlem zamanı UTC ISO metnidir. Audit changes içinde
önceki/yeni alanlar, request fingerprint ve idempotent yanıt bulunur.

Yeni tablolara yalnız mevcut V2 uygulama rolünün gerekli SELECT/INSERT/UPDATE
izinleri, mevcut deployment sahiplik/grant düzeni incelenerek verilmelidir;
rol adı tahmin edilmez ve yeni rol oluşturulmaz. Silme endpoint'i yoktur.
Mevcut subscribers.fields JSON'una package_id, package_revision ve
package_snapshot yalnız açık bir abone işlemi sırasında yazılır; toplu backfill,
mevcut metin paketleri için otomatik eşleme veya tablo ALTER işlemi yoktur.
Paket bağı, aynı transaction'da kilitli aktif katalog kaydıyla doğrulanır;
aboneliğin tarihsel snapshot'ı sonraki katalog değişikliğinde korunur.

Yayın sırası: ayrı onaylı DDL + grant doğrulaması → backend/frontend yayını →
HTTPS/API ve izole sentetik kabul. Tablolar eksikse katalog 503 ve migration-planı
mesajı verir; bellek deposu veya sabit demo fallback'i yoktur. Eski metin-paket
abone API akışı katalogya bağlanmadan çalışmaya devam eder.

Geri dönüş: sorun halinde eski uygulama sürümüne dönüp yeni katalog tablolarını
korumak tercih edilir. Yeni alanlar eski CenterSubscriber projeksiyonunda göz ardı
edilebilir; canlı eski sürümün yeni kayıtları yeniden yazması ayrı değerlendirilir.
Paket tablolarını veya abonelerdeki JSON alanlarını otomatik silme yoktur. Veri
oluştuysa DDL geri alma/silme ancak ayrı onay, yedek ve bağımlılık analiziyle
planlanır. Bu görevde ileri veya geri migration uygulanmadı.
