# Yeni V2 pilot — uygulanmamış erişim paketi

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

Bu paket otomatik kurulum komutu içermez; şu anda VDS'ye dosya aktarılmadı.
Önce yönetici root yetkisiyle hesap/grup/yol/unit çakışmalarını ve mevcut sshd
politikasını inceler. Çakışmada devralma/üzerine yazma yapılmaz. Yeni pilot
henüz kurulmadıysa bu izinler servis kurmaz; servis kurulumu ayrı onaylı iştir.

1. Yeni hesabı parola kilitli, ek grupsuz ve root-owned home ile oluştur.
   Mevcut anahtarın **yalnız public** kısmını operatörün yerelde türettiği
   fingerprint ile eşleştir; özel anahtarı taşıma/gösterme/yenileme.
2. Forced-command dosyasını `/usr/local/sbin/mikrotik-v2-fresh-ssh` root:root
   0755 kur. Public anahtarı root:root 0600
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
