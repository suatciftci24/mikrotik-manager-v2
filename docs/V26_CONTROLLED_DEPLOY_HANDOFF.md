# V26 kontrollü canlı yayın devri — 2026-11-16

Kullanıcı source 69279d2 için gerçek izole restore/migration PASS bildirdi:
011 iki kez başarılı, paket şeması uyumlu, 17 mevcut tablo ve ADMIN korundu.
Yedek: /home/mikadmin/v26-predeploy-20261116T061246Z/database.dump.
Hedef uygulama yalnız /srv/mikrotik-v26-next; baseline b4e78a4.
Bu görevde tek SSH denemesi socket EPERM verdi; tekrar denenmedi. Canlıya
bağımsız erişim olmadığından burada deployment PASS veya güncel VDS HEAD iddiası yok.

## Ofis WSL — tek uygulanabilir komut

```bash
python3 ~/Codex-Projects/mikrotik-manager-v2/tools/deploy-v26-office.py --apply-approved
```

Bu komut kullanıcının bu görevde verdiği V26 yayın yetkisini kullanır. Mevcut
ADMIN kullanıcı adını/parolasını terminalde ister; parola gizli alınır, dosyaya,
argv'ye veya Git'e yazılmaz. SSH stdin üzerinden şifreli taşınır; bir bağlantı
kullanılır, retry yoktur. Kayıtlar/satırlar ve ham hata içerikleri basılmaz.

## Sabit kapsam ve kapılar

- Canlı hedef commit tam 69279d22c0f31ef3624a2676ce4edd9eb1863bf7'dir;
  yeni launcher commit'i değil, izole kabulü geçen uygulama yayımlanır.
- Ofiste aynı hedefin kaynak kopyasından build alınır veya aynı commit/migration
  ve source/dist SHA256 değerleri doğrulanan private build tekrar kullanılır.
- VDS HEAD tam b4e78a4 ve çalışma ağacı temiz olmalıdır. Tam stash listesi ve
  v26-vds-predeploy-20261116T062025Z kaydının OID'si önce/sonra aynı kalır.
  Stash pop/drop, reset/clean/rebase veya force push yoktur.
- Private result.json içindeki PASS/source/VDS/migration SHA/iki koşu/17 tablo/
  ADMIN bilgisi ve verilen backup'ın SHA256'i doğrulanır. Başka kaynak/backup
  kabul edilmez. Gerçek DB kimliği mikrotik_v26_acceptance:55433:
  /var/lib/postgresql/16/v26 olarak salt okunur kontrol edilir.
- V26 service adı, WorkingDirectory, ExecStart, reload kapalı oluşu ve çalışan
  sürecin V26 profil/DB URL'si doğrulanır. Yalnız /srv hedefindeki V26 unit'leri
  kabul edilir; tek V26 API servisi gerekir. Belirsiz veya farklı scope'ta durur.
  V1/V2.5/DB/router/RADIUS/IPsec servislerine restart verilmez.
- HTTPS profili, mevcut ADMIN login/session ve webroot'un hedef dist/index ile
  byte eşitliği güncellemeden önce kontrol edilir. Tüm DB tablolarının ham JSON
  snapshot'ları sır/ham satır/hash dışarı çıkmadan korunma karşılaştırmasına girer.

## Uygulama ve rollback

APP/.git altında yeni 0700 evidence dizini, baseline Git bundle ve yeni build
hazırlanır. APP/.git/backend/frontend yol bileşenlerinde symlink kabul edilmez.
Kullanıcı .env/venv veya systemd tanımı değiştirilmez. Uygulama yapılandırması
çalışan VDS ortamında kalır. Kaynak Git fetch + merge --ff-only ile sabit hedefe
ilerler. Frontend dist Linux renameat2 exchange ile atomik değiştirilir; eski
hashed assets açık tarayıcılar için korunur, eski dist evidence'de tutulur.

Mevcut katalog varsa 011 aynı sabit DB/rol üzerinde READ ONLY transaction ile
uyum doğrulaması yapar, canlı DDL uygulanmaz. İki tablo da yoksa ve kabul/kimlik/
yedek kapıları PASS ise yalnız izin verilmiş 011 uygulanır. Kısmi veya drift
şemada durur. Apply sonucu belirsizse ATTEMPTED_RECHECK_REQUIRED raporlanır;
DB restore/down migration/silme yapılmaz.

Yalnız doğrulanmış V26 unit'leri restart edilir. HTTPS/API, yeni ADMIN oturumu,
Dashboard/router/abone/paket GET sözleşmeleri, index/JS/CSS byte eşitliği,
DB verileri, stash ve çalışan servis scope'u kontrol edilir. Panel kabulü
HTTP_READ_ONLY_PASS'tır; görsel tarayıcı testi veya abone yazma işlemi değildir.

Kod sonrası kritik hatada, HEAD ve dist hash'leri beklenen durumdaysa eski Git
commit'e detach ile ve atomik eski dist değişimiyle kod rollback yapılır. Yalnız
V26 tekrar başlatılır; HTTPS, ADMIN ve eski webroot/stash doğrulanır. Eşzamanlı
kod/dist değişikliği varsa üzerine yazılmaz, rollback BLOCKED olur. Gerçek Git
HEAD raporlanır. DB tablo değişikliği görülürse inceleme bayrağı konur; otomatik
DB restore veya veri silme yoktur. Başarılı rollback bile yayın PASS sayılmaz.

## Yerel doğrulama

11 hedefli offline test PASS: stash pinleri, symlink/hash/servis scope reddi,
başarılı yayın, 011 no-op/absent yolu, panel hatasında güvenli kod+dist rollback,
concurrent drift reddi, gerçek HEAD raporu, backup/kanıt hash bağları, private
artefakt tekrar kullanımı ve HTTP200 hata gövdesinin kabul edilmemesi.
69279d2'nin kaynak kopyasında TypeScript/Vite build PASS; private artefakt:
.local/v26-release-dry-run/69279d22c0f3-v4zb1lx2/manifest.json.
Gerçek canlı adımlar bu ortamda çalıştırılmadı; ofis komutunun JSON sonucu beklenir.
