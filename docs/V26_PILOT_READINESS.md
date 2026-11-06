# V2.6 pilot hazırlığı — 2026-11-06

Başlangıç `main-guncel/9a7c47f`. Sonuç: yerel dar düzeltme PASS;
canlı pilot BLOCKED. Yeni VDS gözlemi, DB/HTTP kabulü veya dağıtım yok.
ACK/READ kimlik düzeltmesi tamamlanmış kullanıcı girdisidir; yeniden açılmadı.
PROGRESS içindeki önceki teşhis kaydı tarihsel kanıt olarak korundu.

## Kök neden ve yerel düzeltme

[VDS ön kontrolü](V26_VDS_IDENTITY_ACCEPTANCE.md) kimlik tabloları eksik,
API18996 dinlemiyor, yeni CLI modülleri kabul kopyasında yok ve kaynak
dizinleri 0775 diyor. Login503'ün kayıtlı şema nedeni ile dinlemeyen API'nin
bağlantı sonucu aynı olay değildir. Health200 kimlik hazırlığı kanıtı değildir.

`8cd3a48` PGDATA yol desteğini zaten düzeltmiş: yalnız
`/var/lib/postgresql/16/v26`, postgres OS sahibi, grup/diğer erişimleri kapalı,
canonical gerçek dizin. Eski belgeler ve geçici PostgreSQL fixture'ı önceki
kabul kökü/same-UID şartında kalmış. Belge güncellendi; mevcut koruma korunur.
PGDATA sahibinin/izinlerinin VDS'de gerçekten uygun olduğu henüz kanıtlanmadı.

Yerel düzeltme filesystem/OS hesabı metadata hatalarını ayrıntı sızdırmadan
`V26_CLUSTER_METADATA_UNAVAILABLE` ile ayırır. Yanlış yol/UID/izin/symlink
`V26_CLUSTER_REJECTED` olarak kalır. DB/rol/port ve sentetik marker kontrolü
korunur. Hata halinde migration veya hesap oluşturulmaz.

## Kanıt ve açık ön koşullar

| Alan | Mevcut kanıt | Kalan pilot engeli / kabul boşluğu |
| --- | --- | --- |
| Kimlik | [Yerel kimlik kabulü](V26_IDENTITY_SETUP.md): önceki commit'te 51 regresyon + 5 geçici PG senaryosu | Güncel kodun izole kopyada varlığı, owner/izin kapıları, 004/009 hazırlığı, tek LOCAL ADMIN+mühür+audit ve login/me/logout kabulü VDS'de doğrulanmadı. |
| DB | Son VDS metadata kaydı: doğru DB/rol/şema, dört storage tablosu | PGDATA sahiplik/izinleri, özel yedek ve geri dönüş hazırlığı; kimlik tabloları eksik. Kayıtlar güncel sunucu durumu sayılmaz. |
| Alarm | `9a7c47f` ACK/READ kimlik düzeltmesi tamamlandı | VDS'de alarm şeması ve güncel kimlikle HTTP kalıcılık/audit kabul kanıtı bu kayıtlarda yok. Yeni hata iddiası yok; işlem yalnız sentetik kapsamda. |
| PPPoE | [PPPoE kabulü](V26_PPPOE_SUBSCRIBER_ACCEPTANCE.md): atomiklik/idempotency/audit, geçici PG ve ASGI PASS | Gerçek login/socket ve tarayıcı uçtan uca kabulü yok; ASGI dependency kimliği gerçek oturum yerine geçmez. Gerçek abone/cihaz yazma yetkisi yok. |
| Yönetim merkezleri | [Arayüz kabulü](V26_MANAGEMENT_UI_ACCEPTANCE.md): sentetik Chromium, yetki/kaynak ve responsive PASS | GET fixture kabulü gerçek API/DB entegrasyonu değildir; mevcut sürümün gerçek oturumla kabul kanıtı yok. |
| Dashboard / sağlık | [Sağlık kabulü](V26_HEALTH_ACCEPTANCE.md): yerel PASS, V2.5 salt okunur örnek PASS | Tarihsel başarısız assertion operandları/kök nedeni BLOCKED; ROLLBACK_VERIFIED sürer. V2.5 dört sayaç sonucu V2.6 beş sayaç/9-router kabulü değildir. |

Bu boşluklar yeni özellik gereksinimi veya kanıtlanmış ürün hatası değildir.
Eski PASS testleri tekrarlanmadı. Eski opt-in PG testi güncel sabit VDS yolu
ile uyumsuzdur; VDS yolunu test için genişletmek veya testin eski PASS sonucunu
güncele taşımak yoktur. Loopback errno=1 kanıtı korunur; yeni bağlantı denemesi yok.

## Bu görevin doğrulaması

`test_v26_cluster_guard`: 3 ağsız test PASS. Tam sabit yolun kabulü;
yanlış hedef/UID/izin/symlink ve canonical yol reddi; erişilemeyen/kayıp metadata
tanısı; yanlış DB/cluster sonrası marker aşamasına geçilmemesi doğrulandı.
Filesystem ve bağlantı nesneleri mock'tur; gerçek PG/HTTP PASS değildir.
Diff kontrolü PASS. Genel suite/build çalıştırılmadı.

## Sonraki tek somut adım

Ayrı açık onayla yalnız izole VDS kabul ortamında **salt okunur güncel ön kontrol**:
aday commit/modül varlığı, kabul kopyası owner/izinleri, sabit PGDATA owner/izinleri,
DB kimliği/kimlik şeması durumu ve API dinleyicisi. Sırlar ve satır verileri
alınmadan sonuç kaydedilmeli. Uyuşmazlıkta durulmalı; bu onay aktarım, chmod/chown,
migration, ADMIN oluşturma, DB yazımı, deploy veya restart yetkisi içermez.
Sonraki yazma işlemi ancak bu kanıttan sonra ayrıca açık onayla planlanabilir.
