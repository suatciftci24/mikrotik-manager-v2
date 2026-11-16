# V2.6 tek merkez çalışma sözleşmesi — 2026-11-16

Tek panel/yayın adresi: **https://v26.mikmanager.com.tr/**.
Tek geliştirme checkout'u: VDS **/srv/mikrotik-v26-next**, **main-guncel**.
Tek mevcut merkezi geliştirme DB'si: **127.0.0.1:55433/mikrotik_v26_acceptance**,
rol **v26_acceptance**, cluster **/var/lib/postgresql/16/v26**.
Ev ve ofis bu panelin istemcileridir. Yerel Git aynası yalnız kontrol/CLI içindir;
yerel panel/DB ile veri senkronizasyonu veya üretim verisi kopyalama yapılmaz.

Kullanıcının bu görevdeki kurulum ve kontrollü V26 yayın yetkisi kullanılır;
aşamalar için tekrar onay istenmez. Bu yetki V1/V2.5/router/RADIUS/IPsec,
veri silme, parola/rol sıfırlama veya otomatik DB restore yetkisi değildir.

## Ofis WSL — tek idempotent uygulama komutu

```bash
python3 ~/Codex-Projects/mikrotik-manager-v2/tools/central-v26-office.py --apply
```

Mevcut ADMIN bilgileri gizli terminal girdisidir; SSH stdin içinde taşınır,
argv/Git/manifest/receipt'e yazılmaz. Tek SSH oturumu ve iki aşamalı çerçeveli
stdin protokolü kullanılır; bağlantı hatası tekrar denenmez. Ofis client HTTP
kontrolünü kendi ağından yapar. Aynı sürüm kuruluysa kurulum tekrar çalışmaz;
servis restartı, backup/restore tekrarı veya Git değişimi yapmadan doğrular.
Kısmi/tanımsız release ya da scope drift varsa veri ezmek yerine BLOCKED olur.

## Koruma ve uygulama kapıları

1. Gerçek VDS kaynak HEAD/clean status ve stash listesi/OID'leri doğrulanır.
   İlk kurulum yalnız bildirilen b4e78a4 tabanından; sonraki kurulum private
   merkezi manifest ve gerçek çalışan release'e bağlıdır. Normal fetch/ff-only
   kullanılır; reset/clean/force/stash pop/drop yoktur. Güncel ofis HEAD'i immutable
   yayın adayıdır. Değişen dependency sözleşmesi otomatik kurulum yerine BLOCKED.
2. Domain'in mevcut Nginx TLS/15173 web/18996 API proxy eşlemesi, tam iki V26 unit,
   mikadmin User/Group, başlangıç komutları ve runtime DB/profile doğrulanır.
   Birimlerin simple/control-group ve yan etkili hooksuz olması gerekir.
   Yeni unit/panel/port/DB oluşturulmaz. Paylaşılan dış Nginx yapılandırılmaz veya
   reload edilmez. Exact sudo komut yetkileri hizmet durmadan salt okunur listelenir.
3. Merkezi DB kimliği ayrıca PG system_identifier+DB OID/port/path ile hash'e
   bağlanır. Kalıcı instance UUID bu DB'ye bağlıdır; başka cluster/DB'ye sessiz
   yönelme yoktur. Kullanıcı/ADMIN ve bütün mevcut tabloların tam veri snapshot'ı
   hash'lenir; raw satır veya hash çıktıları basılmaz. Yerel ofis/ev DB'sine dokunulmaz.
4. Private staging'de build/source hash'leri doğrulanır, API kodu ve statik dist
   değişmez release kopyasına hazırlanır. Bunlar Git checkout değildir; tek .git
   kaynak checkout'u aynı kalır. Mevcut runtime venv değiştirilmez; ayrı dev-venv
   kopyası hazırlanır, Python prefix'i doğrulanır. Kimlik bilgisi/ENV örneği yeniden
   yazılmaz; API'ye yalnız release PYTHONPATH, secure cookie ve canonical mutable
   state yolu için nonsecret son EnvironmentFile eklenir.
5. Servisler çalışırken yeni private DB dump alınır; SHA256/archive ve ayrı
   Unix-only cluster'a restore doğrulanır. 011 iki kez yalnız bu restore'da
   kabul edilir. Canlı paket şeması READ ONLY kontrolünden geçer; canlı DDL yoktur.
6. Hedef commit ayrı retained `attempt-*/test-source` Git worktree'sinde,
   dev-venv ve temizlenmiş test env'iyle sınanır; çalışan checkout değiştirilmez.
   DB/stash/HEAD/temiz çalışma ağacı tekrar doğrulanır. Sonra yalnız iki V26
   unit durdurulur, kesinti başlangıcında veri snapshot'ı alınır ve checkout
   fast-forward güncellenir. Online yedek sırasında normal veri değişiklikleri
   bu kesinti snapshot'ıyla karıştırılmaz. Yedek kesinti başlangıcından eskidir;
   otomatik DB restore zaten yapılmaz.
7. Yalnız iki V26 unit'e kendi 80-v26-central.conf drop-in'i kurulur. API aynı
   18996'da -P/--app-dir ile değişmez release/backend'den çalışır. Çalışma dizini
   aynı checkout root'udur. Existing .local router-secret/pilot/simulator verileri
   canonical eski yolda kalır; taşınmaz/çoğaltılmaz ve guard gevşetilmez. Fotoğraf
   deposunun sabit V26 yolu değişmez.
8. Web aynı mikadmin unit ve 15173 portunda private yapılandırılmış statik Nginx'e
   geçer. Vite kapandıktan sonra portun boş olduğu doğrulanır; aynı portta ikinci
   servis/reuseport/fallback yoktur. /src, /@vite, gizli yollar kapalıdır. Root yalnız
   release/dist'tir; başka statik release'in aynı adlı/farklı içerikli asset'i
   collision sayılır; eski hash'li asset'ler açık tarayıcılar için korunur.
9. HTTPS/API/admin login/session, dashboard/router/abone/paket GET'leri, statik
   index/assets/MIME/header ve API repo/build kimliği doğrulanır. DB ve stash
   korunması kontrol edilir. `current.json` henüz değiştirilmez: setup.lock
   tutulurken ofis HTTPS gözlemi için en fazla 180 saniye beklenir. Geçerli
   sürüm/instance/DB/build bağlı receipt gelince DB tekrar kontrol edilir,
   başarı manifest'i atomik yayımlanır. Ev receipt'i eksikliği, başarılı ofis
   kabulünden sonra yayın rollback'i değil genel görev için BLOCKED sonucudur.
10. Ofis reddi açık CLIENT_REJECTED ile aynı SSH kanalından iletilir; kopma,
    eksik/bozuk receipt ve tam satır zaman aşımı da hata sayılır. Kendi unit/
    drop-in ve ilk checkout için güvenli rollback uygulanır; DB restore yoktur.
    Öncesinde DB/stash/HEAD/checkout ve kendi drop-in içeriğinin beklenen
    önceki/yeni içerikten biri olduğu doğrulanır. Drift varsa geri dönüşe
    zorlanmaz: BLOCKED/rollback NOT_VERIFIED. Dönüşten sonra baseline sağlık,
    veri hash'leri, DB ve stash doğrulanır; ancak o zaman BASELINE_VERIFIED
    kanıtı yazılır. Ofis bu kanıtı bekler ve reddi yine BLOCKED olarak bildirir.
    Hazırlık hatası servis değiştirmemişse rollback NOT_REQUIRED olur.
    SIGKILL/sunucu kaybında otomatik rollback tamamlanması garanti edilemez;
    kanıt yoksa başarı varsayılmaz. Worktree/yedek/release/kanıtlar silinmez.

Sudoers veya servis scope'u uyuşmazsa yetki verilmez, kontrol atlanmaz; sistem
ön kapıda BLOCKED döner. İlk aşamanın eksik hazırlanmış release'i korunur ve
otomatik ezilmez; tamamlanmış aynı sürümün tekrar uygulaması idempotenttir.

## Gerçek ev/ofis kabulü

Kurulum ve yalnız VDS/ofis gözlemi tüm görevin PASS'i değildir. Statik yanıtın
nonsecret X-V26-Instance/Release/Database başlıkları gerçek merkezi profile bağlıdır.
API build_id, bütün sayfalardaki router/abone/paket ve dashboard özetinin fingerprint'i
istemci belleğinde hesaplanır. Parola, token, raw JSON veya satır receipt'e yazılmaz.

Ofis apply komutu kendi ofis receipt'ini gönderir. Evde gerçek bağımsız makinede
aynı kontrol aracı yalnız doğrulama moduyla çalıştırılır:
`python3 ~/Codex-Projects/mikrotik-manager-v2/tools/central-v26-office.py --verify-location home`.
Bu, onay sorusu değildir; eksik fiziksel istemci gözlemini sağlamaktır. Ev makinesinin
mevcut VDS SSH erişimi gerekir. Kaynak/DB kurulumu bu modda tekrarlanmaz; yayınlanmış
release doğrulanır. Aynı VDS source checkout geliştirme için ilerlese de yayın receipt'i
published release'i gösterir. Ofiste gerekirse --verify-location office ile aynı
salt panel kontrolü yapılır; sunucuda yalnız yeni private doğrulama receipt'i saklanır.

PASS için 10 dakika içindeki iki farklı makinenin origin/instance/release/database,
API build ve görünür veri fingerprint'leri eşit olmalıdır. Tek makinenin home/office
etiketleri PASS olmaz. Eksik, eski, farklı sürüm/veri veya iki aynı makine gözleminde
üst durum BLOCKED kalır; setup=VERIFIED ayrı raporlanabilir. CLI verisi coğrafi
konum ispatı değildir; home/office seçimi ilgili gerçek bilgisayarda kullanıcı
çalıştırma beyanına dayanır, makine hash'i bağımsızlığı kontrol eder.

## Geliştirme/test — yalnız VDS terminali

Tek checkout'ta geliştirme yapılır. Test için
`python3 tools/central-v26-tests.py backend.tests.test_v26_central_development`
mevcut dev-venv'yi ve yeni sentetik fixture'ları kullanır. Mevcut merkezi DB'ye test
mutation'ı yapılmaz; gerçek DB'den test için ev/ofise restore veya account transferi yoktur.
Değişiklikler hedefli testlerden sonra normal commit/push; yayın yalnız kontrollü
aynı uygulama komutuyla ve bütün kapılarla yapılır. .venv runtime'a pip install yoktur.

Bu oturum: SSH EPERM nedeniyle yeni kurulum/publication gerçek VDS'de uygulanmadı;
istemci home/ofis ortak veri kabulü alınmadı. Yerel testler kurulum PASS'i sayılmaz.

### Başarısız kabulü güvenli teşhis

Ofis WSL, repo güncel ve temizken:

```bash
python3 ~/Codex-Projects/mikrotik-manager-v2/tools/central-v26-office.py --diagnose-attempt attempt-pcpsra2q
```

Mevcut admin bilgisi yalnız SSH stdin üzerinden aktarılır. Komut dağıtım veya
servis değişikliği yapmaz; aday ASGI incelemesi port açmaz ve DB bağlantılarını
zorunlu salt okunur tutar. Uzak kanıtı yeniden yazmaz. HTTP gövdeleri/parolalar
raporlanmaz. Rollback sonrası HTTPS/loopback ölçümleri eski başarısız adayın
kanıtı değildir. Eski kayıtta kaybolan neden journal veya aday probe ile de
kanıtlanamazsa UNKNOWN olarak kalır; üst BLOCKED/exit 1 beklenen sonuçtur.
Yeni dağıtımlarda failure.json ilk başarısız aşamayı korur; yalnız geçici ready
hatası beklenir, panel/login/statik kimlik hatası tekrarlarla gizlenmez.

### Statik teslim kabulü

Bayt/hash eşitliğine ek olarak API JSON, index HTML, JS JavaScript ve CSS doğru
Content-Type ile sunulmalıdır. Yeni private statik config nosniff, SAMEORIGIN,
strict-origin-when-cross-origin ve no-store üretir. Remote kabul ve bağımsız
ev/ofis gözlemleri bu başlıkları X-V26 instance/release/database ile birlikte
zorunlu doğrular. Bunlar yalnız araç koduna eklenmiştir; mevcut VDS yapılandırması
bu geliştirme sırasında değiştirilmemiştir. Gerçek HTTPS kabulü alınmadan
araç testlerinin geçmesi canlı yayın PASS'i değildir.
