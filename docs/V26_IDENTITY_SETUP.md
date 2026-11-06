# V2.6 kimlik kurulumu ve yerel kabul

## Kök neden ve kapsam

`/api/health` kimlik tablolarının/mührünün hazır olduğunu doğrulamaz. Dört temel
storage tablosu login için yeterli değildir. Adaptör `v26_acceptance` seçerken
identity sorguları/inspect_setup varsayılanı `v2_demo` kullanıyordu. İlk yönetici
CLI'si ise yalnız ofis DB/cluster hedefini kabul ediyordu. Önceden yapılmış iki
şema allowlist değişikliği korunarak sorgu, audit ve yönetim yolları tamamlandı.
Repo içinde `.v26-backup` bulunmadı; hiçbir yedek içeriği Git'e eklenmedi.

Yeni giriş noktası `app.v26_first_admin`, mevcut sürümlü
`004_demo_identity.sql` ve `009_first_local_admin.sql` dosyalarını yalnız seçilen
şemaya uyarlayarak çalıştırır; eski migration dosyaları değiştirilmedi.
Mevcut durum okunur; yalnız gerekli yükseltmeler uygulanır. Migration, ayrı LOCAL
ADMIN, audit ve kalıcı mühür tek transaction'dır. Demo hesap eklenmez/dönüştürülmez.
HTTP/startup migration çalıştırmaz. Kurulum yoksa login 503 vermeye devam eder.

Advisory transaction kilidi şema okunmadan alınır; böylece iki ilk kurulumun
ALTER TABLE için birbirini kilitlemesi önlenir. Tamamlanmış kurulum tekrar
çalıştırıldığında `FIRST_ADMIN_SETUP_CLOSED` ile yazmadan durur. Mühür silinmesi,
çelişkili işaretler veya eksik audit deposu otomatik tamir/reset edilmez.

## VDS prosedürü — HENÜZ UYGULANMADI

Bu bölüm yalnız hazırlıktır. Kod aktarımı, VDS migration/DB yazımı, ilk ADMIN
oluşturma ve gerekiyorsa süreç yenileme için yeni, açık, işlem kapsamına özgü
kullanıcı onayı gerekir. V1/V2.5/Fresh Pilot servislerine işlem yapılmaz.

1. Onaydan sonra doğrulanmış commit'i yalnız `/tmp/mikrotik-v26-acceptance`
   kabul kopyasına alın. Kaynak `backend/` ve `migrations/`, mevcut izole venv
   kullanılmalı; çalışma dizini tam bu kök olmalıdır. Symlink kabul edilmez.
2. Root olmayan kabul kopyası sahibi ile çalışın. Kök, backend ve migrations
   bu UID'ye ait olmalı; grup/diğer yazma kapalı olmalıdır. `8cd3a48` itibarıyla
   PGDATA yalnız `/var/lib/postgresql/16/v26`, gerçek `postgres` OS hesabı
   sahibi ve grup/diğer erişimleri kapalı gerçek dizin olabilir. Canonical yol
   eşitliği ve symlink reddi korunur; kabul kökü altındaki PGDATA reddedilir.
   Metadata okunamıyorsa durun; izin/sahip değiştirerek kapıyı atlamayın.
   API'nin açık transaction/istekleri
   varken yükseltme yapmayın; gerekli durdurma da ayrıca onay kapsamında olmalı.
3. Mevcut izole yapılandırmayı güvenli yoldan yükleyin; shell tracing, parola
   argv'si, terminale DSN yazdırma kullanmayın. Zorunlu değerler:
   `V2_DEPLOYMENT_PROFILE=v26-isolated-acceptance`,
   `V2_ENVIRONMENT=v26-acceptance`, `V2_API_HOST=127.0.0.1`,
   `V2_API_PORT=18996`, iki cihaz kapısı `false`, operatör listesi boş.
   `V2_DATABASE_URL` yalnız `postgresql+psycopg`, `127.0.0.1:55433`,
   DB `mikrotik_v26_acceptance`, rol `v26_acceptance`; güçlü mevcut DB sırrı,
   query/fragment yok. Bu araç DB/rol/parola oluşturmaz. Sunucudaki gerçek
   DB/rol/port ve `SHOW data_directory` ayrıca doğrulanır. Rol bu metadata'yı
   okuyamıyor veya DDL yetkisi yoksa durun; otomatik yetki genişletmeyin.
4. Yalnız bu DB'nin işlem öncesi özel custom-format `pg_dump` yedeğini alın;
   `umask 077`, benzersiz dosya adı, mevcut güvenli parola kanalı kullanın.
   `pg_restore --list` ile arşivi kontrol edin. Yedeği/logları Git'e koymayın.
5. **VDS terminali, izole kabul kopyasının OS sahibi, gerçek TTY:**

   ```bash
   cd /tmp/mikrotik-v26-acceptance
   PYTHONPATH="$PWD/backend" .venv/bin/python -m app.v26_first_admin --status
   PYTHONPATH="$PWD/backend" .venv/bin/python -m app.v26_first_admin --create
   PYTHONPATH="$PWD/backend" .venv/bin/python -m app.v26_first_admin --status
   ```

   Başlangıçta `FIRST_ADMIN_SETUP_NOT_COMPLETED` beklenir. `--create` ayrı hesap
   bilgileri ve gizli parola/tekrar ister; son `OLUSTUR` onayı olmadan yazmaz.
   Gerçek parola operatörce TTY'de girilir; bu görevde oluşturulmadı. Sonuç
   `FIRST_ADMIN_CREATED_SETUP_CLOSED`, son durum `FIRST_ADMIN_SETUP_CLOSED`.
   Hata varsa transaction geri alınır; kısmi şemayı elle silerek devam etmeyin.
6. Onay kapsamındaki güncel kodla yalnız kabul API'sini çalıştırın. Health200
   tek başına başarı değildir: yeni LOCAL ADMIN login200/me200, demo401,
   logout200/me401 ve mühür kapalı durumu doğrulanmalıdır. Parolayı HTTP komut
   satırına/loga koymayın. Şifre veya hash içermeyen sonuç raporu tutun.

Geri dönüş: transaction hatasında otomatik rollback; başarılı kurulumdan sonra
mührü silmek/flag'leri false yapmak veya tabloları DROP etmek yoktur. Süreci
kapalı tutun; geri yükleme gerekiyorsa yalnız izole DB için ayrıca onaylı
restore planı ve işlem sonrası veri farkı değerlendirmesi hazırlayın. V2.5'e
veya diğer PostgreSQL instance'larına yönelerek login sağlamayın.

## Yerel doğrulama

Güncel sabit VDS PGDATA kapısı için ofis deposunda ağsız hedefli test:

```bash
PYTHONPATH=backend .venv/bin/python -m unittest backend.tests.test_v26_cluster_guard -v
```

Eski `test_v26_identity_postgres` disposable fixture'ı kabul kökü altında
`postgres-test` oluşturur. Bu düzen `8cd3a48` sonrası sabit VDS kapısıyla
uyumlu değildir; aşağıdaki 2026-11-04 PASS kaydı önceki commit'e aittir.
Güncel kaynak için bu eski testin PASS olduğu veya gerçek PostgreSQL/HTTP
kabulünün yenilendiği iddia edilmez. Test uğruna üretim kapısına alternatif
PGDATA/UID eklenmez. Bu görevde ağ/DB testi çalıştırılmadı.

Yerel 503→kurulum→200 doğrulaması VDS'nin düzeldiği anlamına gelmez.
VDS migration ve gerçek giriş kabulü bu görevde yapılmadı.

## Kabul sonucu — 2026-11-04

- LOCAL PASS: 51 hedefli mevcut kimlik/yetki/ilk-admin testi; değişiklikten
  etkilenen ve başarısız kapsamlar gerektiği kadar tekrarlandı, genel suite yok.
- LOCAL PASS: gerçek geçici PostgreSQL16 üzerinde 5 yeni senaryo:
  health200/login503 → atomik kurulum → login200/me200/demo401; dolu storage
  kayıtlarını koruma ve tekrar kurulumda aynı snapshot; DDL+hesap rollback;
  eşzamanlı tek ADMIN ve bozuk mühürde503; yönetim/audit şeması, CLI status ve
  TTY reddi; yanlış profil/hedef/çalışma dizininde bağlantı öncesi ret.
- İlk test hazırlığında psycopg `%` yorumlama hatası test SQL yürütme yöntemiyle
  düzeltildi. Eşzamanlı testin bulduğu gerçek DDL kilit sırası hatası üründe
  düzeltildi; başarısız test yeniden PASS. Testler gevşetilmedi.
- Geçici cluster kapatıldı/silindi. Mevcut Starlette/httpx deprecation uyarısı
  bağımlılık değiştirilmeden kaydedildi. Diff kontrolü PASS.
- VDS erişimi, migration, restart, gerçek ADMIN parolası üretimi veya cihaz IO
  yapılmadı. VDS HTTP503 henüz giderilmiş/doğrulanmış sayılmaz.
