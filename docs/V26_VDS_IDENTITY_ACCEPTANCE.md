# V2.6 VDS kimlik kurulumu ön kontrolü — 2026-11-04

Sonuç: **BLOCKED**, kurulum veya HTTP503 çözümü doğrulanmadı.

- Başlangıç: main-guncel, temiz ağaç, aa77855. GitHub main-guncel tam SHA
  aa77855538e7226e38615f63b491ff74e8f50fd9; kurulum belgesi/kod uyumlu.
- Onay kapsamı: yalnız izole V2.6 kimlik migration/ilk ADMIN; gerektiğinde
  yalnız izole API süreci. Kullanıcı hedef uyuşmazlığında durulmasını istedi.
- VDS bağlantısı mevcut mikadmin anahtarıyla doğrulandı. Kabul kökü
  /tmp/mikrotik-v26-acceptance, mikadmin sahibi, 0700. backend/migrations 0775;
  mevcut owner koruması bunları reddeder. Yeni v26_identity.py ve
  v26_first_admin.py VDS kabul kopyasında bulunmuyor; dosya aktarılmadı.
- Dinleyiciler: 127.0.0.1:55433 var; 18996 üzerinde API dinleyicisi yok.
- Yalnız 55433 Unix socket'i üzerinden mikrotik_v26_acceptance DB'sinde
  BEGIN READ ONLY / ROLLBACK ile metadata okundu. DB sahibi v26_acceptance;
  v26_acceptance şema sahibi aynı rol. Rol login açık, superuser değil.
  Şemada events, requests, schema_state, subscribers mevcut; kimlik tabloları yok.
- **Engel:** gerçek data_directory /var/lib/postgresql/16/v26. aa77855
  V26FirstAdminStore yalnız /tmp/mikrotik-v26-acceptance altındaki gerçek,
  aynı non-root OS UID'sine ait PGDATA'yı kabul eder. Bu, belgelenen cluster
  hedefiyle uyuşmuyor. Koruma kaldırılmadı; başka role/DB'ye yönelinmedi.
- Hiçbir VDS dosyası değiştirilmedi; migration/DDL/DB yazımı, ADMIN/parola
  oluşturma, API başlatma/restart, diğer servis veya cihaz işlemi yapılmadı.
  DB yalnız metadata düzeyinde okundu; abone/envanter satırları alınmadı.
- HTTP login200, anonim401, gerçek envanter korunumu için önce/sonra kabulü
  YAPILMADI; HTTP503 çözülmüş sayılmaz. Önceki yerel PASS canlı PASS değildir.
- Sonraki gereken adım: gerçek izole PGDATA düzenini destekleyen dar kurulum
  tasarımının ayrıca talimatlandırılması ve doğrulanması. Mevcut korumayı
  atlayarak manuel SQL uygulamak veya cluster taşımak bu göreve eklenmedi.


## Kaynak-kayıt uzlaştırması — 2026-11-06

Yukarıdaki kayıt 2026-11-04 VDS gözlemidir; yeni VDS gözlemi değildir.
`8cd3a48` yerel kaynakta eski aynı-UID/kabul-kökü şartını, yalnız tam
`/var/lib/postgresql/16/v26` + postgres sahibi + özel izin + canonical yol
şartıyla değiştirmiştir. Başlangıç `9a7c47f` bu değişikliği içerir.
Bu nedenle PGDATA yol desteği kaynakta eksik değildir. VDS PGDATA OS sahibi
ve izinleri eski raporda kanıtlanmamıştır; yalnız yolun eşleşmesi yeterli değildir.
Kabul kopyasının backend/migrations 0775 olması ayrı owner kapısına aykırıdır.

Kimlik tablolarının yokluğu login 503 için kayıtlı nedendir; health200 bu
kurulumu ölçmez. Son gözlemde API18996 dinlemiyor ve yeni kurulum modülleri
kabul kopyasında yoktu. Bu üç bulgu ayrı tutulmalıdır; güncel VDS HTTP
sonucu veya yeni bir SQL hatası elde edilmedi. Kaynağın düzelmesi VDS kurulumu
veya 503 çözümü değildir. Kapılar gevşetilmedi; VDS'ye bağlantı kurulmadı.

Güncel pilot ön koşulları ve tek sonraki adım:
[V26_PILOT_READINESS.md](V26_PILOT_READINESS.md).
