# Preferences 503 — hazırlanan kalıcı çözüm ve canlı onarım

Durum: **LOCAL PASS / LIVE PENDING**. Bu belge canlı uygulama yetkisi değildir.
503 kapanışı ancak mevcut Fresh Pilot üzerinde aşağıdaki gerçek kabul geçince
verilebilir. V2.6 veya başka dağıtım bu çalışmanın parçası değildir.

## Kök neden ve çalışma sözleşmesi

`1a53a93` salt okunur kanıtı: Fresh Pilot bağlantısı uygulama rolüyle başarılı,
ayar tabloları mevcut, zorunlu `settings_records/default` yok. Kurulu okuyucu
`DemoStorageUnavailable` fırlatıyor; `/api/v1/preferences` uygulama kaynaklı JSON
503 veriyor. Eski V2.6 rollback kaydı bu ayrıntıyı saklamadığından tarihsel
rollback'in aynı hata olduğu kesinleştirilmez.

`bbab921` yeni boş kurulumda migration 005 sonrasında `Values` default'unu
ADMIN/audit/ledger ile aynı transaction'da ekler. Kurulum `verify` aşaması
varlık ve payload doğrulamasını zorunlu tutar; eksik/bozuk kurulum kabul edilmez.
Migration SQL/checksum'ları değiştirilmez. Mevcut kurulum için tekrar migration,
`settings-init`, seed, schema reset veya yeni installer çalıştırılmaz.

Uygulama import/başlangıcı DB'ye bağlanmaz, migration veya onarım yapmaz.
GET'ler yalnız READ ONLY transaction kullanır ve kayıt oluşturmaz. Yeni yerel
API sürümünde güvenli 503 kodları:

| Durum | Kod |
| --- | --- |
| Gerekli ayar tabloları yok | `SETTINGS_SCHEMA_MISSING` |
| Zorunlu default yok | `DEFAULT_SETTINGS_MISSING` |
| Kayıt modelle uyumsuz | `SETTINGS_RECORD_INVALID` |
| Gerçek erişim/SQL hatası | `DATABASE_UNAVAILABLE` |

Eksik şema için başarılı varsayılan yanıtla saklama arızası gizlenmez.
Kişisel ayar yazımı da geçerli default gerektirir. ADMIN/oturum/yazma başlığı,
revizyon, idempotent request ve audit kontrolleri korunur. Yeni kodlar yereldir;
mevcut pilotun kodunu güncellemek bu onarım için gerekli değildir.
`/api/health.database_connected` bağlantı sağlığıdır, ayar hazır olma garantisi
değildir; gerçek preferences HTTP kabulü ayrıca zorunludur.

## Onarım ve idempotence

`backend/app/services/preferences_repair.py` yalnız çağıranın açık transaction'ı
içinde çalışır. Runtime veya HTTP route'a bağlı değildir. Mevcut ayar yazımıyla
aynı advisory lock, iki ayar tablosunda süre sınırlı write lock ve PK/unique
çatışma güvencesi kullanılır. API/diğer DB tabloları için geniş kilit alınmaz.

- Yetkili mevcut LOCAL ADMIN ve kalıcı ilk ADMIN mühürü transaction'da yeniden
  okunur. Rol/yetki genişletilmez, yeni kullanıcı oluşturulmaz.
- Geçerli default zaten varsa ayar/audit yazımı olmadan no-op; özelleştirilmiş
  değer, revision ve updated_at aynen kalır.
- Geçersiz mevcut kayıt varsa açık hata; overwrite/upsert/reset yoktur.
- Eksikse yalnız default eklenir. `ON CONFLICT DO NOTHING` ve son doğrulama
  çoğaltmayı engeller; oluşturma ile tek `DEFAULT_SETTINGS_REPAIR` audit'i aynı
  transaction'da tamamlanır. Audit başarısızsa ekleme de rollback olur.
- Yedek hash'i audit'te tutulur. Normal ayar düzenlemeleri veya audit satırları
  yeniden yazılmaz. Her HTTP isteğinde onarım veya otomatik retry yapılmaz.

## Ayrı onayla uygulanacak tam kapsam

Makine: **Ofis WSL, suatpc@DESKTOP-VD5T7VG**. Proje:
`/home/suatpc/Codex-Projects/mikrotik-manager-v2`.
Hedef: yalnız `mikadmin@185.139.5.51` üzerinden
`/srv/mikrotik-manager-v2-fresh-pilot`, DB `mikrotik_manager_v2_fresh_pilot`,
uygulama rolü `v2_fresh_app`, loopback `127.0.0.1:55442`.

1. Yerelde `prepare-preferences-repair.py --output <yeni özel yerel dosya>` ile
   gözden geçirilen araçları tek stream halinde paketle ve SHA256 kaydet.
   Hazırlama SSH/DB çağırmaz, araçları çalıştırmaz.
2. Ayrı açık kullanıcı onayından sonra mevcut yönetici SSH ile bu stream'i
   mevcut Fresh venv Python'a `-I -B -` üzerinden ver. Argümanlar:
   `apply --approved-live-default-repair --request-id <yeni UUID>`.
   Bayrak kullanıcı onayının yerine geçmez. Remote dosya/uygulama deploy edilmez;
   onarım modülü yalnız bu geçici Python sürecinin belleğinde yüklenir.
3. Root/path/sır dosyası sahipliği, loopback DB/rol/marker, kurulu manifest ve
   ledger, tam katalog şema imzası, app rol yetkileri, geçerli `Values` modeli,
   mevcut LOCAL ADMIN/mühür, API/DB ve timer durumlarını doğrula. Kurulu eski
   manifest kullanılır; yeni yerel manifest eski installation receipt'iyle
   değiştirilmez. Uygulama rolüne ledger yetkisi verilmez: yalnız ledger ve
   hedef owner metadatası mevcut owner peer bağlantısıyla READ ONLY okunur.
4. Mevcut ADMIN handoff kimliğini yalnız bellekte kullan. Default geçerliyse
   no-op; yoksa önce root-private
   `backups/preferences-default-<request UUID>/` altında eksik satırın ön-imajı,
   mevcut tablo hash'leri, dosya/unit durumu ve tam `database-before.dump` al.
   Yedek mevcut owner peer transport ile, parola/env/argv sırrı olmadan,
   aynı transaction'dan export edilen snapshot üzerinden alınır. Başarılı dump,
   archive-list, SHA256 ve fsync zorunludur; başarısızlıkta INSERT'e geçilmez.
5. Tek transaction'da yalnız eksik default + bir settings_audit ekle. Diğer tüm
   uygulama tabloları ve mevcut ayar/audit kayıtlarının PostgreSQL'de hesaplanan
   hash'leri değişmemeli. Tabloların satırları/sırlar receipt'e çıkarılmaz.
   Şema/owner/ledger/dosya/API-DB PID/timer durumları korunmalı; beklenmeyen
   durumda transaction commit edilmez.
6. Commit sonrasında gerçek ADMIN GET `/api/v1/preferences` **200**,
   `storage_ready=true`, `Values` geçerliliği ve default varlığı zorunludur.
   Gerçek 9/9 envanter kimlik metadatası, korunan tablo hash'leri ve
   API/DB/timer durumları tekrar eşleşmelidir. Yeni kaynak örneklerinin doğal
   gelişimine izin verilir; ölçüm zamanı API okuma zamanıyla değiştirilmez.
7. Logout **200**, ardından auth/me **401**; cookie yalnız bellekte, kalıcı ADMIN
   oturumu yok. Gerçek kabul receipt'i kaydedilmeden nihai PASS yok.

Bu yazma kapsamı **henüz uygulanmadı**. İzin bekleyen iş yalnız default + audit
INSERT ve buna ait yedek/koruma/HTTP kabulüdür. V1/eski V2/router/PPPoE/RADIUS/IPsec,
servis/timer değişikliği, kod dağıtımı, migration veya restart içermez.

## Geri dönüş ve hata davranışı

Transaction içi herhangi bir hata default ve audit'i birlikte geri alır.
Commit sonrası kabul hatası `transaction_committed=true`, `BLOCKED` olarak
kaydedilir; araç başarı uydurmaz, otomatik DELETE veya tam DB restore yapmaz.

Koşullu geri dönüş aracı da hazırdır; **ayrı açık rollback onayı** gerektirir:
`rollback --approved-live-default-repair --request-id <yeni rollback UUID>
--repair-id <oluşturma UUID>`. Önce yeni private yedek alınır. Yalnız ilgili
onarım audit'inin oluşturduğu, payload/revision/updated_at değeri değişmemiş
default silinebilir. Sonraki bir ayar düzenlemesinde güvenle durur. Orijinal
audit korunur, telafi audit'i eklenir. Tüm DB'yi geri yüklemek veya kullanıcı
ayarlarını sıfırlamak araçta yoktur. Başlangıçtaki eksik durum/503'e dönüş
`ROLLBACK_VERIFIED` olarak raporlanır; çözüm PASS'ı sayılmaz.

Tam dump için `pg_restore --list` gerçek restore provası diye raporlanmaz.
Yedek/restore mekanizması bu görevde yalnız ayrı geçici sentetik PG16 DB'sine
restore edilerek doğrulandı. Canlı dump/restore henüz çalıştırılmadı.

## Hedefli yerel kanıt

25 test PASS, atlanan test yok:

- 11 yeni test: açık onay kapısı, gerçek sentetik PG'de eksik→onarım→HTTP200,
  sekiz eşzamanlı onarım→bir kayıt/bir audit, tekrar/özelleştirilmiş değeri koruma,
  geçersiz kayıt/eksik şema ayrımı, gerçek başarısız bağlantı→503, gerçek oturum ve
  ADMIN/yazma başlığı/kişisel tercih akışı, audit hatasında atomic rollback,
  koşullu rollback/sonraki düzenlemeyi koruma, custom dump'ın ayrı sentetik
  DB'ye restore edilmesi, boş kurulumun default oluşturması.
- 14 doğrudan bağlı kontrol: üç önceki preferences kabul testi; gerçek PG
  single-user modunda tam 001–009 installer/ADMIN/ledger/default ve rollback;
  sekiz mevcut settings transaction testi; iki initialization koruma testi.

Sentetik küme yalnız `/tmp/v2-preferences-synthetic-*` içinde, Unix socket/peer
kimliğiyle çalıştı; TCP dinlemedi, mevcut yerel veya canlı DB kullanılmadı.
Test sonunda küme kapatılıp geçici dosyalar kaldırıldı. Frontend build, genel
test paketi, canlı bağlantı veya gerçek HTTP kabulü çalıştırılmadı.
