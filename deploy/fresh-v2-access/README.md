# Yeni V2 pilot — erişim paketi

2026-11-02: Ofis WSL mevcut HTTPS Git kimliğiyle `git ls-remote origin HEAD`
başarılı; mevcut SSH anahtarıyla BatchMode/StrictHostKeyChecking açık VDS girişi
başarılı (`mikadmin@185.139.5.51`). Push yazma yetkisi test edilmedi.
Anahtar, parola, token okunmadı/değiştirilmedi; credential helper değiştirilmedi.
SSH salt okunur kontrolünde `v2-fresh-ops` hesabı bulunmadı. Yeni pilot kökü ve
planlanan yetki dosyaları ABSENT_OR_INACCESSIBLE döndü; bu root düzeyinde
yokluk kanıtı değildir. Mevcut hesabın sudo kapsamı veya sır dosyaları okunmadı.

## Hazır kapsam

- Yeni `v2-fresh-ops`: sudo/admin grubu üyeliği yok, parola kilitli, yerel
  home root-owned 0755 ve yazılamaz; `/bin/sh` yalnız sshd forced-command için.
  Uygulama/DB hesaplarından ayrıdır; mevcut hesap/anahtar izinleri değiştirilmez.
- Yalnız `mikrotik-v2-fresh-pilot.service` ve
  `mikrotik-v2-fresh-pilot-db.service` için is-active/start/stop/restart.
  DB stop/restart API'yi etkileyebilir; bu eylemler ayrıca görev onayı gerektirir.
  Sudoers yetkisi kullanıcı onayının yerine geçmez.
- `/srv/mikrotik-manager-v2-fresh-pilot` altında **hiçbir doğrudan okuma/yazma
  veya grup yetkisi verilmez**. Kaynak, venv, config, DB, yedek ve sırlar kapalıdır.
  Unit, executable ve tüm üst dizinler root-owned ve operatöre yazılamaz olmalı.
- SSH shell, SFTP/SCP, PTY, agent/X11/TCP/Unix forwarding ve kullanıcı rc/env
  kapalıdır. Panel tüneli bu hesabın kapsamı değildir. Genel SSH ayarları korunur.
- sudo shell/python/editör/cp/chown/chmod/runuser/journalctl/daemon-reload,
  enable, migration, kurulum ve genel root yetkisi içermez.

## Yalnız ayrıca onaydan sonra yönetici uygulaması

İlk hazırlıkta paket VDS'ye uygulanmamıştı; güncel canlı sonuç aşağıdadır.
Önce yönetici root yetkisiyle hesap/grup/yol/unit çakışmalarını ve mevcut sshd
politikasını inceler. Çakışmada devralma/üzerine yazma yapılmaz. Yeni pilot
henüz kurulmadıysa bu izinler servis kurmaz; servis kurulumu ayrı onaylı iştir.

1. Yeni hesabı parola kilitli, ek grupsuz ve root-owned home ile oluştur.
   Mevcut anahtarın **yalnız public** kısmını operatörün yerelde türettiği
   fingerprint ile eşleştir; özel anahtarı taşıma/gösterme/yenileme.
2. Forced-command dosyasını `/usr/local/sbin/mikrotik-v2-fresh-ssh` root:root
   0755 kur. Public anahtarı root:v2-fresh-ops 0640
   `/etc/ssh/authorized_keys/v2-fresh-ops` içine `restrict` önekiyle koy;
   parent root:root 0755. Account'un authorized_keys değiştirmesine izin verme.
3. Sudoers'ı önce `visudo -cf` ile doğrula, yalnız yeni dosyayı root:root 0440
   kur; ardından bütün politika için `visudo -c`. Önceden var olanı değiştirme.
4. Match bloğunu mevcut Include/Match sırası incelendikten sonra ekle.
   `sshd -t` ve `sshd -T -C user=v2-fresh-ops,host=<office>,addr=<office-ip>`
   ile etkili kısıtları doğrula; mevcut yönetici/V1/eski pilot kullanıcılarının
   etkili ayarlarının değişmediğini kontrol et. Yönetici oturumunu açık tut.
   SSH reload da canlı değişikliktir ve açık onaya tabidir.
5. Yeni hesapla yalnız `is-active` kabulünü yap; başka unit/shell/forwarding ve
   dosya yazma reddini doğrula. Start/stop/restart kabulü ayrıca onay gerektirir.
   Rollback yalnız yeni hesabı kilitleyip bu pakete ait yeni yetki dosyalarını
   kaldırır; mevcut kullanıcı/anahtar/unit/dizin/DB'yi değiştirmez.

Yerel kontrol (Ofis WSL, proje dizini):
`python3 -m unittest discover -s deploy/fresh-v2-access/tests -v`

Yerel sudoers sözdizimi kontrolü VDS'nin mevcut birleşik politikasını veya
sshd sürüm uyumluluğunu kanıtlamaz. Canlı hesap/SSH/sudo/servis kabulü yapılmadı.

## Onaylı uygulama sonucu — 2026-11-02

**BLOCKED**: e397f95 paketi VDS'nin `sshd -t -f` kontrolünde reddedildi:
`PermitUserEnvironment` yönergesi `Match` bloğunda kullanılamıyor.
Kontrol atlanmadı; canlı tekrar veya otomatik düzeltme yapılmadı.

- Yeni hesap/home/authorized_key/sudoers/forced-command oluşturulmadı.
- Etkin sshd_config, V1/eski pilot ve mevcut kullanıcı yetkileri değişmedi;
  SSH reload, pilot servis işlemi, deployment veya migration yapılmadı.
- Yalnız `/etc/ssh/sshd_config.v2-fresh-access-before` ve
  `/etc/ssh/sshd_config.v2-fresh-access-candidate` root:root 0600 bırakıldı.
  Yedek ile etkin yapılandırma bayt düzeyinde eşit doğrulandı.
- `apply-approved-vds.py` gözden geçirilmiş commit içeriklerini bellekte taşıyan
  yönetici SSH oturumunda kullanıldı; sır içermez ve bağımsız çalıştırılmaz.
  Anahtar yalnız public dosyadan alındı; fingerprint eşleşti. Bu yardımcı
  mevcut hedeflerde durur; bırakılmış aday/yedek nedeniyle tekrar çalıştırılmaz.
- Sonraki tek adım: paketin Match uyumsuzluğunu yerelde düzeltmek; ortam değişkeni
  kısıtını etkin global `permituserenvironment no` ile doğrulamadan ilerlememek.
  Bu sonuç mevcut onayı iptal etmez; bu görev hata sonrasında güvenle durmuştur.

## SSH uyumluluk düzeltmesi — 2026-11-02

**PASS (yerel düzeltme ve hedef SSH doğrulaması)**; canlı kurulum yapılmadı.
`PermitUserEnvironment` Match bloğundan çıkarıldı. Genel SSH ayarına yönerge
eklenmez/değiştirilmez: uygulayıcı, hedef hesap için mevcut etkin
`permituserenvironment no` değerini aday/yedek dosyalarını yazmadan önce zorunlu
kontrol eder. `yes`, değişken allowlist'i veya eksik sonuçta BLOCKED olur.
Adayın etkin değerinin de `no` kalması zorunludur. Python `-I`, temiz execve
ortamı, root-owned home/authorized_keys, PermitUserRC=no, ForceCommand ve
forwarding kısıtları korunur. Sudo ve iki unit sınırı değişmedi.

`check-ssh-office.py` yalnız salt okunur doğrulama yapar; uygulayıcı ana akışını
çağırmaz. Mevcut config + düzeltilmiş Match bloğunu `/dev/stdin` üzerinden hedef
sshd'ye verir, uzak dosya oluşturmaz. `sshd -t`, etkin yeni hesap kısıtları ve
40 mevcut hesabın üç adres bağlamında tüm `sshd -T` çıktılarının eşitliği PASS.
Etkin config ve iki eski root erişimli yedeğin içerik/mode/owner/mtime bilgileri
korundu. İki doğrudan ilgili yerel test PASS; sudo/komut testleri tekrarlanmadı.

Ofis WSL, proje dizini için salt okunur kontrol komutu:
`python3 deploy/fresh-v2-access/check-ssh-office.py`

Sonraki tek adım: ayrı canlı uygulama talimatı geldiğinde düzeltilmiş paketi
kurmak. Önceki aday/yedekler yerinde korunur; mevcut uygulayıcının bu yolları
çakışma sayan kapısı atlanmaz. Canlı uygulama öncesinde bu kayıtları koruyan
ayrı yeni kanıt yolları seçilmelidir. Bu görevde hesap/anahtar/sudo kurulumu,
SSH config yazması veya reload yapılmadı.

## Düzeltilmiş paketin canlı denemesi — 2026-11-02

**BLOCKED (SSH hesap kabulü)**. 7c90491 şablonu ve sudo politikası kullanıldı.
Uygulayıcı bu deneme için atomik, root:root 0700 yeni kanıt dizini oluşturdu:
`/etc/ssh/v2-fresh-access-a9s28fvf`. Önceki iki 0600 kanıt dosyası korunur.
Aday SSH/sudoers sözdizimi ve 40 mevcut hesabın 3 bağlamda etkin SSH politika
eşitliği geçti. Yeni hesabın sudo shell/id/başka servis/daemon-reload yetkileri
reddedildi. SSH reload sonrası mevcut yönetici erişimi korundu.

Yeni hesabın gerçek SSH girişi publickey reddiyle durdu. Neden: root:root 0600
public-key dosyası, sshd'nin kimlik doğrulama sırasında geçici olarak geçtiği
hedef kullanıcı tarafından okunamıyor. Hedef journal kaydı ve yeni hesapla
salt okunur erişim kontrolü bunu doğruladı. Komut kısıtları/forwarding/PTY/SFTP
canlı kabulüne geçilmedi; bunlar PASS bildirilmez.

Güvenli geri dönüş tamamlandı:

- Etkin sshd_config yeni denemenin `sshd_config.before` dosyasına bayt düzeyinde
  geri alındı; sshd -t geçti ve SSH yeniden yüklendi. Reload sonrası geçici
  active-state kontrolü başarısız oldu; yalnız bu kontrol yeni yönetici SSH
  bağlantısıyla tekrarlandı: SSH active ve erişim PASS. Restart yapılmadı.
- Yeni key `/etc/ssh/authorized_keys/v2-fresh-ops.disabled` olarak kapalıdır.
  Yeni sudoers dosyası kanıt dizinindeki `sudoers.disabled` konumuna taşındı;
  etkin sudoers dizininde yoktur. Birleşik sudoers kontrolü geçti.
- Parolası kilitli `v2-fresh-ops` hesabı ve özel grubu, root-owned home,
  forced-command dosyası ve root-owned authorized_keys üst dizini korunur.
  Yeni anahtar/sudo yetkisi etkin değildir. Bu kalıntılar otomatik devralınmaz.
- Yeni kanıt dizininde before/candidate/sudoers.candidate/receipt.json ve
  acceptance-blocked.json vardır; sır içerikleri raporlanmadı.
- V1/eski pilot/mevcut kullanıcı politikaları, diğer servisler ve uygulama/DB
  kurulumu değişmedi. Yeni pilot servisi kurulmadı/başlatılmadı.

Sonraki tek adım: public-key okuma modelini yerelde root sahipliği + yalnız yeni
hesabın grubuna okuma (0640) ile düzeltmek; yazma yetkisi vermemek. Canlı tekrar
bu görevde yapılmadı. Uygulayıcının ACCOUNT_EXISTS kapısı korunur.

## Güncel canlı kabul — 2026-11-02 — PASS

Public key artık **root:v2-fresh-ops 0640**; dosya atomik/exclusive 0600 açılır,
fd üzerinden sahip/grup ve 0640 ayarlanır. UID/GID/mode/normal dosya/tek hardlink,
ek ACL yokluğu, tüm üst dizinlerde root sahipliği/yazma kısıtı ve hesapla
traversal/read/no-write kontrolleri zorunludur. Grup yalnız bu hesaba aittir.
Parola kilidi, ek grup yokluğu ve root-owned home korunur.

Önceki başarısız denemenin hesabı yalnız açık kullanıcı talimatı ve tam kayıt
kontrolüyle kullanıldı: sabit eski kanıt yolu, rollback kaydı, config ön-imajı,
üç paket SHA256, wrapper/policy/disabled public key, hesap/home/shell/özel grup
bütünlüğü eşleşti. Diğer mevcut hedefler/hesaplar devralınmaz. Eski kanıtlar ve
.disabled dosyası yerinde korunur. Yeni rollback anahtar/sudo dosyalarını yalnız
bu denemenin ayrı kanıt dizinine kapatır; eski dosyaların üzerine yazmaz.

Yeni kanıt dizini: `/etc/ssh/v2-fresh-access-8oc0glqm` (root:root 0700).
Before/candidate/sudoers.candidate/receipt.json/acceptance.json yalnız root
okur. SSH ve sudoers aday/live kontrolleri PASS; 40 diğer hesabın 3 bağlantı
bağlamında tüm etkin SSH ayarları aynı kaldı. Yalnız SSH reload yapıldı.

Canlı hedefli kabul PASS:

- Yeni SSH kimliğiyle iki exact V2 servis durum sorgusu başarılı; servisler
  kurulu değil ve aktif değil. Start/stop/restart çağrılmadı.
- Kabuk, diğer servis ve dosya yazma komutları; SFTP, PTY ve forwarding reddedildi.
  SFTP reddi stderr metni vermediği için ilk test beklentisi düzeltildi; yalnız
  o ve henüz çalışmayan kapsam devam ettirildi. Güvenlik ayarı değiştirilmedi.
- Yeni yönetici SSH bağlantısı/sudo, kilitli parola, root-owned dosyalar ve
  key grubu, tam 8 exact sudo komutu ve başka sudo komutlarının reddi doğrulandı.
- Üç key/resume testi, iki doğrudan etkilenen rollback testi ve eski disabled
  kanıtı koruyan yeni rollback testi PASS. Genel ürün testleri tekrarlanmadı.

Bu yalnız erişim kurulumudur: V1/eski V2/diğer kullanıcı ve servisler değişmedi;
uygulama dağıtımı, migration veya PostgreSQL kurulumu/başlangıcı yapılmadı.
Sonraki tek adım: yeni V2 pilotunun ayrı uygulama kurulum kapsamını hazırlamak.
