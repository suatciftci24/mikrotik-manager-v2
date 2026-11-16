# V26 mevcut yedek / 011 kabul devri — 2026-11-16

Altın Kurallar ve güncel main-guncel esas alındı. Kullanıcı
`/home/mikadmin/v26-predeploy-20261116T061246Z/database.dump` için izole restore
PASS bildirdi. Bu kanıt kabul edildi; burada bağımsız gözlem gibi raporlanmadı.
VDS b4e78a4 bildirimi sabit baseline'dır. Tek SSH denemesi socket EPERM verdi;
tekrar denenmedi. İlk GitHub HEAD sorgusu DNS hatası verdi; yerel temel 94cfec6.

Ofis WSL terminalinde tek komut:

```bash
python3 /home/suatpc/Codex-Projects/mikrotik-manager-v2/tools/check-v26-backup-migration.py --run-isolated
```

Launcher tam yerel commit'ten hem migration hem worker okur; bir SSH bağlantısı
kullanır, retry yapmaz. Mevcut SSH key/known_hosts kullanılır; parola veya sudo
kısıtları değiştirilmez. VDS kaynak HEAD'i tam b4e78a4 olmalı, çalışma ağacı temiz
olmalıdır. Beklenmeyen farkta durur.

Mevcut yetkiyle `sudo -n -u postgres psql -X` üzerinden yalnız BEGIN READ ONLY /
ROLLBACK içinde paket kolon/constraint/index metadata'sı okunur. Sabit DB,
55433 portu ve /var/lib/postgresql/16/v26 cluster yolu kontrol edilir. Bu mevcut
peer erişim yetkisi yoksa BLOCKED olur; hesap/rol/erişim ayarı oluşturmaz.

Yedek yeni 0700 `/home/mikadmin/v26-backup-011-*` dizinine kopyalanır; SHA256,
metadata değişmezliği ve pg_restore list kontrolü yapılır. Kaynak dosya silinmez
ve değiştirilmez. Aynı private dizinde sıfırdan PG16 test cluster'ı kurulur;
TCP listen kapalıdır, yalnız yeni private Unix socket ve açık DB/rol kullanılır.
Canlı PostgreSQL veya systemd servisine start/stop/restart gönderilmez.

Bu kopyaya restore edilen paket metadata'sı canlıdaki salt okunur snapshot'la
aynı değilse durur. Eski backup'tan canlı uyumu varsayılmaz. Kullanıcı/ADMIN
varlığı kontrol edilir; tüm mevcut user tabloları için ham veri stdout'a
çıkarılmadan içerik hash'leri alınır. 011 yalnız data_directory'si test dizinine
eşit olduğu doğrulanmış bu kopyada iki kez çalışır. İlk çalıştırmada mevcut
bütün tablo verileri, ikincide hem tüm veriler hem paket metadata'sı aynı
kalmalıdır. İlk çalışmada yalnız iki paket tablosunun eklenmesine izin verilir.
Sonunda canlı paket metadata'sı ve HEAD drift kontrolü tekrar yapılır; yalnız
script'in kendi test cluster'ı durdurulur, dosyalar silinmeden korunur.

PASS çıktısı backup/migration hash'i, kaynak/VDS commit'i, admin sayısı,
korunan tablo sayısı ve private result.json yolunu içerir. Ham tablo satırları,
hash/parola alanları, env veya pg_restore hata içerikleri terminale basılmaz.
Test cluster'ı durdurulamazsa önceki test sonucu PASS olsa bile BLOCKED olur.

Bu komut canlı migration/deploy/restart/cleanup içermez. PASS sonrası somut
adım result.json ve hash'leri inceleyerek aynı kaynak/migration için kontrollü
V26 yayın paketini hazırlamaktır. Son kullanıcı mesajı gereği bu aşamada canlı
uygulama yoktur. Şema drift reddinde otomatik düzeltme veya veri kayıplı restore
yoktur. Mevcut başarılı sentetik PG16/build testleri tekrar çalıştırılmadı.

Yerel hedefli kontrol: 4 offline handoff güvenlik testi PASS (veri değişimi,
bilinmeyen yeni tablo, yanlış canlı hedef, başarısız backup ön-kontrolünün
bağlantı açmaması ve satır/hata içeriğinin dışarı çıkmaması). Gerçek remote
restore/migration kabulü SSH engeli nedeniyle burada BLOCKED kaldı.

## LIVE_TARGET_REJECTED parser düzeltmesi — 2026-11-16

Kullanıcı PostgreSQL kimliğini kesin doğruladı:
`mikrotik_v26_acceptance:55433:/var/lib/postgresql/16/v26`.
Eski parser stdout'u tam iki satır varsayıyordu. json_agg(record) çıktısındaki
çok satırlı katalog bu varsayımı bozup kimlik doğru olsa da yanlış ret üretir.
Yeni parser tam kimlik satırından sonra tek JSON değerini tüm uzunluğuyla
çözer. Başta isteğe bağlı tek BEGIN, sonda isteğe bağlı tek ROLLBACK ve boşluk
kabul edilir. Yanlış DB/port/cluster, banner, bozuk JSON, ikinci JSON, beklenmeyen
trailing çıktı veya farklı command tag reddedilir. Katalog anahtarları ve
list/null şekli de doğrulanır; hata metnine ham çıktı eklenmez.

Yedi offline handoff testi PASS. Gerçek VDS acceptance bu görevde çalıştırılmadı;
VDS stash/DB/servis değişmedi. Ofis WSL tek komutu yukarıdakiyle aynıdır ve yeni
commit'teki worker'ı gönderir. Başarılı gerçek izole migration sonucu ayrıca
alınmalıdır; parser testi migration PASS sayılmaz.

## Aşama bazlı güvenli tanı — 2026-11-16

Kullanıcı d1dbe5a için COMMAND_FAILED:psql ve
`/home/mikadmin/v26-backup-011-33_uy6u6` evidence dizinini bildirdi. Eski genel
hata kaydı hangi SQL'in başarısız olduğunu kanıtlamaz; bu dizin değiştirilmedi
ve SSH yeniden denenmedi. SQL kök nedeni henüz doğrulanmadı.

Yeni worker her dış komuta sabit aşama atar. PostgreSQL sırası:
ISOLATED_DATABASE_CREATE → ISOLATED_TARGET_VERIFY → ISOLATED_RESTORE →
RESTORED_PACKAGE_CATALOG → SNAPSHOT_BEFORE_TABLE_LIST / TABLE_n →
RESTORED_ADMIN_CHECK → MIGRATION_011_FIRST → SNAPSHOT_AFTER_FIRST_* →
PACKAGE_CATALOG_AFTER_FIRST → MIGRATION_011_SECOND → SNAPSHOT_AFTER_SECOND_* →
PACKAGE_CATALOG_AFTER_SECOND. Canlı katalog başta LIVE_CATALOG, sonda
LIVE_CATALOG_RECHECK olarak ayrılır; yalnız read-only kalır.

Başarısız komut JSON'unda failed_stage, tool, failure, exit_code ve yalnız
bilinen SQLSTATE varsa sqlstate bulunur. Örnek:
`{"failed_stage":"RESTORED_ADMIN_CHECK","tool":"psql","exit_code":3,"sqlstate":"42P01"}`.
Bu örnek gerçek hata teşhisi değildir. Psql VERBOSITY=sqlstate kullanır;
stdout/stderr, SQL, argümanlar, satırlar, parola/hash veya tablo isimleri
rapora alınmaz. Snapshot TABLE_n yalnız sıra numarasıdır. Timeout ve executable
başlatma hataları aynı güvenli biçimde ayrılır. Bilinmeyen SQLSTATE basılmaz.

Kendi cluster'ını durdurma başarısız olursa cleanup_failure ayrıca eklenir;
ilk SQL'in reason/failed_stage alanı korunur ve durum BLOCKED kalır.
Private result.json ile stdout aynı güvenli raporu taşır. Eski evidence'e
üzerine yazılmaz; yeni çalıştırma yeni private dizin oluşturur.

10 offline hedefli test PASS: eski parser/kimlik sınırı, sekiz SQL aşamasında
hata enjeksiyonu, ilk hata+stop hatasının birlikte korunması, private rapor,
exit/SQLSTATE tanısı ve timeout/secret sızıntısı reddi. Gerçek izole kabulün
geçtiği iddia edilmez. Ofis WSL tek komutu değişmedi; yeni JSON hangi SQL
adımının başarısız olduğunu gösterecektir. Canlı migration/deploy/restart/silme
ve VDS stash işlemi yoktur.

## Snapshot tablo 14 / JSON bütünlüğü — 2026-11-16

Bildirilen kanıt: a0c2cd7, SNAPSHOT_BEFORE_TABLE_14, exit_code=3,
`/home/mikadmin/v26-backup-011-jd2df7o8`. Bu kayıt tablo adını veya SQLSTATE'i
vermiyor; VDS'ye bağlanılmadı ve mevcut evidence/yedek/stash değiştirilmedi.
Dolayısıyla üretimdeki 14. tablo için kesin kök neden henüz gözlemlenmedi.

Yeni private PG16 single-user testinde eski to_jsonb(t)/jsonb_agg sorgusunun
geçerli JSON içindeki escaped U+0000'ı 22P05 ile reddettiği kanıtlandı.
Bu, eski snapshot kodunda somut bir uyumluluk hatasıdır. Ayrıca JSONB ham JSON
anahtar sırasını ve yinelenen anahtarları normalize eder. Bu davranışı satır
atlayarak veya kolon/JSON alanını çıkararak aşmak bütünlük garantisini bozar.

Yeni sorgu row_to_json/json_agg kullanır, satırın tam metnine COLLATE "C"
ile deterministik sıralama uygular. JSONB dönüşümü yoktur; bütün alanlar,
ham JSON temsili, yinelenen satırlar ve boş tablolar hash'e dahildir. Hash ve
ham satırlar raporlanmaz. Format row-json-text-v1; tüm before/after karşılaştırma
aynı yeni formatla yapılır, eski snapshot hash'leriyle karşılaştırılmaz.

SNAPSHOT_BEFORE_TABLE_14 hatası olursa table_ordinal ve güvenli table_identity
rapora eklenir. Bilinen uygulama şemalarında sıradan ASCII tablo adları yalnız
metadata olarak açıklanır; diğer kimlikler SHA256 ile temsil edilir. Kontrol
karakteri/yabancı şema/ham SQL veya satır sızmaz. 22P05/22021 ve kaynak limit
kodları tanı allowlist'ine eklendi; başarısız yeni snapshot hâlâ BLOCKED.

Gerçek sebebi doğrulamak için yalnız ilk snapshot'ın 14. tablosunda, yalnız
restore kopyasında eski JSONB sorgusu bir tanı probu olarak çalışır. Sonuç
snapshot_diagnostics içinde probe_only=true, kimlik ve güvenli SQLSTATE ile
kaydedilir. Eski probun başarısızlığı yeni veri snapshot'ının yerine geçmez:
yeni sorgu bütün tabloyu başarıyla okumazsa hiçbir kabul PASS olmaz. Probun
başarısı da geçmiş hatanın sebebini kanıtlamaz. Veri kaybı/atlama fallback'i yok.

Hedefli kanıt: 14 offline handoff testi + 1 yeni gerçek PG16 regresyon testi.
PG16 testinde 22P05 reproduksiyonu, yeni ham JSON okuma, yinelenen anahtar ve
satır korunumu, deterministik tekrar, veri mutasyonunun hash girdisini değiştirmesi
ve boş tablo doğrulandı. Test cluster'ı /tmp/v26-snapshot-json-3442puno altında
kapalı olarak korundu. Canlı/ev-ofis DB, VDS servis veya stash işlemi yok.
