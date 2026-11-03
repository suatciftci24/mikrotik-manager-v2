# Fresh V2 pilot — son kurulum bağlantısı

Bu belge **canlı uygulama onayı değildir**. Son hazırlık yereldir.

## Yetki sonucu

`v2-fresh-ops` mevcut root-owned forced-command ve sudoers sözleşmesiyle yalnız
iki fresh unit için is-active/start/stop/restart çağırabilir. SCP/SFTP, shell,
PTY, forwarding, dosya yazma, useradd, initdb, runuser, daemon-reload ve Python
komutu veremez. Dolayısıyla **bu hesapla ilk kurulum mümkün değildir**.
Mevcut e43f330 canlı kabulü ve paket kodu bu sonucu kanıtlar; aynı reddetme testleri
tekrarlanmadı. SSH/sudo yetkisi genişletilmez. İlk kurulum, açık canlı kurulum
onayından sonra mevcut yetkili yönetici oturumunda yapılmalıdır; işletim hesabı
sonrasında yalnız izinli servis işlemlerinde kullanılır. Servis işlemleri de
ilgili görevin açık onayına bağlıdır.

## Değişmez kurulum kapıları

- Boş ve önceden var olmayan `/srv/mikrotik-manager-v2-fresh-pilot`, iki yeni
  OS hesabı/grubu ve unit; dolu/mevcut hedefe devralma/reset yoktur.
- PG16 yalnız yeni `postgres`/`socket`/`backups`/`config` dizinleri; loopback
  55442. API/UI loopback 18090. V1/eski pilot kaynağı/env/rol/port kullanılmaz.
- Yönetici önce PG16 araçları ve venv desteğinin bulunduğunu doğrular. Yoksa
  durulur; bu paket apt veya varsayılan PostgreSQL cluster kurup başlatmaz.
- Staging manifest 001–009 checksum/sırası ve hazır frontend kontrolünü zaten
  yapar. Migration, boş katalog + kimlik + gerçek TTY ister; yeni LOCAL ADMIN,
  audit, ledger ve seal aynı transaction içindedir. Sırlar yalnız TTY/bellek/yeni
  private config içindedir; argv, aktarım paketi veya loglara konmaz.
- Boş ön-imaj, migration sonrası yedek ve kabulün verify+backup kapısı korunur.
  Restore provası yapılmış sayılmaz; dump/list/checksum bunu kanıtlamaz.

## Ofis WSL — yalnız yerel paket

Proje: `/home/suatpc/Codex-Projects/mikrotik-manager-v2`.

```bash
python3 deploy/fresh-v2-pilot/prepare-release.py --output .local/fresh-v2-release-<benzersiz-ad>
```

Komut committed backend/app + requirements, migrations ve mevcut fresh pilot
paketini alır; yalnız mevcut `frontend/dist` eklenir. Build ve test üretmez.
Kaynak değişikliği/izlenmeyen dosya varsa durur; private dosya/symlink/özel dosya
aktarmaz. Tar SHA256, kaynak commit, migration manifest hash'i ve frontend
hash'leri receipt.json içindedir. Önceden var olan çıktı dizini reddedilir.
Frontend çıktısının kaynakla eşdeğerliği bu adımda yeniden derlenerek
kanıtlanmamıştır; receipt bunu açıkça kaydeder. Kabulden önce build'in kullanılan
kaynağa ait olduğu incelenmelidir; paket hash'i bu incelemenin yerine geçmez.

## Daha sonra, ayrıca onaylı VDS yönetici oturumu

Aşağıdaki komutlar bu hazırlık görevinde **çalıştırılmaz**. Transfer yalnız mevcut
yetkili yönetici kanalıyla yapılır; ops hesabına dosya aktarımı yetkisi verilmez.
Ofis'te incelenmiş SHA256 ve commit'i bağımsız olarak karşılaştır. Tar içeriklerini
incele ve root-owned yeni 0700 staging dizinine aç; var olan dizine üzerine yazma.
Root çalıştırılacak kaynak/manifest ve tüm üst dizinler operatöre yazılamaz olmalı.

İncelenmiş paketin açıldığı kök `RELEASE_ROOT` olsun (henüz `/srv` hedefi değil).
Aşağıdaki sırada herhangi bir hata sonraki adıma geçilmesini engeller:

```bash
# Root yönetici TTY'si; RELEASE_ROOT onaylı yeni staging dizinidir.
/usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin /usr/bin/python3 "$RELEASE_ROOT/deploy/fresh-v2-pilot/stage-approved.py" --stage-approved
/usr/bin/systemctl daemon-reload
/usr/bin/systemctl start mikrotik-v2-fresh-pilot-db.service
/usr/sbin/runuser -u mikrotik-v2-fresh-db -- /usr/bin/env -i PATH=/usr/bin:/bin /srv/mikrotik-manager-v2-fresh-pilot/venv/bin/python /srv/mikrotik-manager-v2-fresh-pilot/app/deploy/fresh-v2-pilot/manage.py create-database-approved
/usr/sbin/runuser -u mikrotik-v2-fresh-db -- /usr/bin/env -i PATH=/usr/bin:/bin /srv/mikrotik-manager-v2-fresh-pilot/venv/bin/python /srv/mikrotik-manager-v2-fresh-pilot/app/deploy/fresh-v2-pilot/manage.py migrate-approved
/usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin /srv/mikrotik-manager-v2-fresh-pilot/venv/bin/python /srv/mikrotik-manager-v2-fresh-pilot/app/deploy/fresh-v2-pilot/accept-approved.py --accept-approved
/usr/bin/systemctl start mikrotik-v2-fresh-pilot.service
```

Her satırın başarısı kontrol edilmeden diğeri çalıştırılmaz; toplu paste edilmez.
DB başlatıldıktan sonra bind/port/data_directory ve systemd loopback egress
kısıtları doğrulanır; başarısızsa migration'a geçilmez. API sonrası loopback
HTTP/UI, yeni ADMIN girişi, demo girişinin kapalı olması ve router/RADIUS
kapılarının kapalı olması kabul edilir. Ops hesabı tünel açamaz; genel bind/proxy
veya yeni SSH yetkisi bu kurulumun parçası değildir.

## Geri dönüş

Hata sonrası kalıntıları/yedekleri koru; reset/drop/down/adoption yoktur. Gerekirse
yalnız yeni API unit'ini onaylı kapsamda durdur; eski sistemi restart etme veya
trafik geçirme. DB/yedekler silinmez. Restore için ayrı, boş recovery hedefi ve
ayrı onay gerekir. Ayrıntılı koşullar docs/FRESH_V2_PILOT_SETUP.md içindedir.

## Sunum tercihleri — boş hedef kurulum bütünlüğü

Yeni kurulum migration 005 sonrasında `settings_records/default` kaydını
`Values` sözleşmesiyle aynı kurulum transaction'ında oluşturur. Doğrulama
bu kaydın varlığını ve payload geçerliliğini de denetler. Çakışma reddedilir;
mevcut hedefe yeniden kurulum veya okuma sırasında otomatik onarım yapılmaz.
Bu düzeltme mevcut pilotu onarmaz. Migration SQL/checksum'ları değişmez;
`manage.py` asset hash'i ve dolayısıyla yeni paket manifest kimliği değişir.
Yeni manifest eski kurulum receipt'i yerine kullanılamaz; mevcut pilotun
veri onarımı ve paket geçişi ayrı açık onaylı çalışma gerektirir.
