# V2.6 HTTP401 son ayrım

## Güncel değerlendirme — 2026-11-06 / b9683e8 sonrası

- ADMIN mevcut; kullanıcı doğrulaması ve önceki LOCAL/ADMIN/active/sealed,
  PASSWORD_MATCH/ID_REREAD sonuçları kabul edilir, tekrarlanmaz.
- 2026-11-04 kaydındaki503 kimlik tabloları/kurulum eksikliğine aittir. Bu eski
  gözlem bugünkü DB'nin eksik olduğu anlamına gelmez. Yeni503 kanıtı yoktur.
- Sonraki401 için kesin neden bulunmadı; son başarılı doğrudan kimlik
  tanısından sonra aynı çalışan API/build ve istekle yeniden üretilmiş sonuç
  kaydı yok. Disk hash eşitliği yüklenmiş süreç kodunun eşitliği değildir.
- En yeni beş yerel `accept-api-*/api.log` dosyasında kayıtlı login200 ve
  /me200 var. Örneğin `accept-api-vtdkolo2/api.log` son değişim zamanı
  2026-11-05 21:10:46 UTC; login200:1, me200:130, me401:3. Bu access logları
  hesap origin/ADMIN, DB/şema veya build kanıtı içermez; güncel V2.6 kabulüne
  bağlanamaz. /me401, POST login401 ile aynı olay değildir. Ham log/kimlik
  bilgisi rapora alınmadı; API veya DB bağlantısı kurulmadı.
- Kaynakta yeni ürün hatası kanıtlanmadı. Kimlik/parola/cookie kuralları
  değiştirilmedi; eski PASS testleri yeniden çalıştırılmadı.

### Eksik tek kabul kanıtı ve en kısa salt okunur kontrol

Eksik kanıt, **hedefi/build'i doğrulanmış çalışan V2.6 API'de mevcut ADMIN
oturumunun gerçek HTTP üzerinden yetkili ve kimlik deposuna bağlı olduğudur**.
Mevcut ADMIN oturumu açık olan izinli yerel istemcide aynı API origin'inde
tek `GET /api/v1/auth/me` yanıtının HTTP200 ve `account_origin=LOCAL`,
`role_code=ADMIN`, `active=true`, `bootstrap_closed=true`,
`can_manage_users=true` verdiği kaydedilmelidir. Hedef/build kimliği henüz
doğrulanmamışsa aynı origin'den bir `GET /api/ready` ile repo/build/port kimliği
eşleştirilir; ready tek başına DB kabulü değildir. Cookie/token/parola/yanıt
gövdesi kaydedilmez; yalnız HTTP kodu ve bu koşulların boolean sonucu gerekir.
Ready DB/şema göstermez; sonuç önceki doğrulanmış v26 DB/şema hedefiyle
eşleştirilemiyorsa o atıf BLOCKED kalır, yeni SQL/kurulum denenmez.

Bu kontrol yalnız GET ve mevcut oturumu kullanır; login/logout, yeni oturum,
hesap/DB yazımı, kurulum veya servis işlemi yapmaz. Mevcut oturum yoksa ya da
hedef doğrulanamıyorsa BLOCKED kalır; otomatik login/kurulum denenmez. GET401
parolanın yanlışlığını kanıtlamaz,503 depolama/kimlik hazırlığı sınıfıdır.
GET200 bu oturumun güncel kabulüdür; eski POST401'in kök nedenini veya genel
abone işlem/UUID/PostgreSQL kabulünü tek başına kapatmaz.

Burada socket kontrolü veya HTTP isteği yapılmadı. Hedef VDS ise bu görevde
kontrol yapılmaz; yeni açık VDS izni gerekir. Aşağıdaki tek GET komutu yalnız hazırlanmıştır;
VDS'de bu görev kapsamında çalıştırılmayacaktır.

## Tarihsel süreç/istek tanısı — bu görevde çalıştırılmadı

7c30737 sonrası kullanıcı tanısı: aynı disk hash'leri, v26 şeması, bulunan
aktif LOCAL ADMIN, kapalı mühür, PASSWORD_MATCH ve ID yeniden okuması başarılı.
Bu kontroller tekrarlanmadı. Önceki HTTP401 güncel tanıdan sonra yeniden üretilmedi.
Kesin kök neden BLOCKED; kanıtlanmış ürün düzeltmesi yok.

Kaynak incelemesi: yalnız CORS middleware'i var, auth middleware401 yok.
Eksik/bozuk JSON veya alan doğrulaması422; storage503; login401 kimlik/parola
veya route içindeki ID yeniden okumasından gelebilir. Cookie Secure ayarı
ilk POST401'i açıklamaz. Disk SHA eşitliği çalışan sürecin yüklediği kodla
aynılık değildir. /api/ready build_id süreç import'unda sabitlenir.

## Tek hazırlanmış VDS kontrol komutu — salt okunur, çalıştırılmadı

2026-11-06 / a65290a sonrası: frontend username/password değerlerini JSON ile
`/api/v1/auth/login` yoluna değiştirmeden gönderir; credentials=include kullanır.
Backend tam username eşitliği, scrypt N32768/N131072, aktiflik/LOCAL/mühür ve
ID yeniden okuması yapar. Adaptör v26 profiline göre v26_acceptance seçer.
Bu kaynak yolu önceki PASS testleriyle uyumludur; yeni ürün hatası kanıtlanmadı.
Eski503 kimlik şeması gözlemi güncel401'in nedeni olarak kullanılmadı.

Önceki POST login/logout komutu salt okunur kapsamdan çıkarıldı. Aşağıdaki
**tek komut VDS terminali, mevcut kabul kopyasının sahibi, gerçek TTY içindir**;
burada VDS'ye bağlanılmadı ve komut çalıştırılmadı. Yeni VDS çalışma izni içermez.
Mevcut ADMIN tarayıcı oturumunun `v2_session` değeri yalnız gizli TTY sorusuna
girilir; terminal komutuna, environment'a, dosyaya veya sohbet çıktısına yazılmaz.
Mevcut oturum yoksa boş bırakılır ve BLOCKED kalır; yeni login/ADMIN oluşturulmaz.

Komut aynı sahibin tek 127.0.0.1:18996 listener'ını, cwd/PID/start kimliğini,
başlangıç V2 profil/DB hedefini ve running build=disk=incelenen kaynak eşitliğini
kontrol eder. Hedef/build uyuşmazlığında cookie sorulmadan durur. Yalnız bir
GET ready ve bir GET me; proxy, yönlendirme veya retry yoktur. Uygulama kodu
import edilmez, SQL bağlantısı açılmaz, login/logout/kurulum çağrılmaz.

```bash
/tmp/mikrotik-v26-acceptance/.venv/bin/python -I -B - <<'PY'
import getpass, hashlib, http.client, json, os, re, subprocess, warnings
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path('/tmp/mikrotik-v26-acceptance')
EXPECTED_BUILD = 'a63dcea53f16c94a1797a19583f0fb880c768ac741fad7c2a2b90e1f9b3115ef'

class Blocked(Exception):
    pass

def process():
    if os.getuid() <= 0 or os.getuid() != os.geteuid() or ROOT.resolve() != ROOT:
        raise Blocked('OWNER_OR_ROOT_UNVERIFIED')
    result = subprocess.run(['ss', '-H', '-ltnp', 'sport = :18996'],
                            capture_output=True, text=True, timeout=5, check=True)
    rows = result.stdout.strip().splitlines()
    if len(rows) != 1 or '127.0.0.1:18996' not in rows[0].split():
        raise Blocked('LISTENER_UNVERIFIED')
    pids = set(re.findall(r'pid=(\d+)', rows[0]))
    if len(pids) != 1:
        raise Blocked('LISTENER_NOT_UNIQUE')
    pid = next(iter(pids))
    proc = Path('/proc') / pid
    if proc.stat().st_uid != os.getuid() or (proc / 'cwd').resolve() != ROOT:
        raise Blocked('PROCESS_TARGET_UNVERIFIED')
    start = (proc / 'stat').read_text().rsplit(') ', 1)[1].split()[19]
    return pid, start

def configuration(pid):
    values = {}
    for item in (Path('/proc') / pid / 'environ').read_bytes().split(b'\0'):
        key, sep, value = item.partition(b'=')
        if sep and key.startswith(b'V2_'):
            values[key.decode()] = value.decode()
    required = dict(V2_DEPLOYMENT_PROFILE='v26-isolated-acceptance',
                    V2_ENVIRONMENT='v26-acceptance', V2_API_HOST='127.0.0.1',
                    V2_API_PORT='18996', V2_ROUTER_ONBOARDING_ENABLED='false',
                    V2_CEBECI_API_SSL_ENABLED='false')
    target = urlsplit(values.get('V2_DATABASE_URL', ''))
    password = unquote(target.password or '')
    valid = (all(values.get(k) == v for k, v in required.items())
             and not values.get('V2_ROUTER_ONBOARDING_OPERATOR_IDS', '')
             and target.scheme == 'postgresql+psycopg'
             and target.hostname == '127.0.0.1' and target.port == 55433
             and target.path == '/mikrotik_v26_acceptance'
             and unquote(target.username or '') == 'v26_acceptance'
             and len(password) >= 20 and not any(ord(c) < 32 for c in password)
             and 'REPLACE_' not in password and 'PLACEHOLDER' not in password
             and not target.query and not target.fragment)
    if not valid:
        raise Blocked('V26_CONFIGURATION_UNVERIFIED')

def disk_build():
    digest = hashlib.sha256()
    paths = sorted((ROOT / 'backend/app').rglob('*.py'))
    if not paths:
        raise Blocked('SOURCE_UNVERIFIED')
    for path in paths:
        if path.is_symlink():
            raise Blocked('SOURCE_UNVERIFIED')
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(b'\0'); digest.update(path.read_bytes()); digest.update(b'\0')
    return digest.hexdigest()

def get(path, cookie=None):
    if path not in ('/api/ready', '/api/v1/auth/me') or (cookie and path != '/api/v1/auth/me'):
        raise Blocked('HTTP_TARGET_REJECTED')
    connection = http.client.HTTPConnection('127.0.0.1', 18996, timeout=5)
    try:
        headers = {'Cookie': 'v2_session=' + cookie} if cookie else {}
        connection.request('GET', path, headers=headers)
        response = connection.getresponse()
        data = response.read(65537)
        if len(data) > 65536:
            raise Blocked('HTTP_RESPONSE_TOO_LARGE')
        return response.status, json.loads(data) if response.status == 200 else None
    finally:
        connection.close()

def existing_cookie():
    warnings.simplefilter('error', getpass.GetPassWarning)
    with open('/dev/tty', 'r+') as tty:
        value = getpass.getpass('Mevcut ADMIN v2_session (gizli; yoksa boş): ', stream=tty)
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', value):
        raise Blocked('EXISTING_SESSION_REQUIRED')
    return value

def main():
    try:
        before = process()
        configuration(before[0])
        code, ready = get('/api/ready')
        if (code != 200 or ready.get('service') != 'mikrotik-manager-v2'
                or ready.get('api_port') != 18996
                or ready.get('repo_id') != hashlib.sha256(str(ROOT).encode()).hexdigest()):
            raise Blocked('READY_TARGET_UNVERIFIED')
        matches = ready.get('build_id') == disk_build() == EXPECTED_BUILD
        print('RUNNING_BUILD_MATCHES_REVIEWED', matches)
        if not matches or process() != before:
            raise Blocked('BUILD_OR_PROCESS_MISMATCH')
        cookie = existing_cookie()
        code, user = get('/api/v1/auth/me', cookie)
        del cookie
        if process() != before:
            raise Blocked('LISTENER_CHANGED')
        print('HTTP_ME', code)
        if code == 401:
            raise Blocked('SESSION_OR_ID_REREAD; PASSWORD_NOT_TESTED')
        if code == 503:
            raise Blocked('STORAGE_CLASS; OLD_SCHEMA_CAUSE_NOT_PROVEN')
        accepted = (code == 200 and user.get('account_origin') == 'LOCAL'
                    and user.get('role_code') == 'ADMIN'
                    and all(user.get(k) is True for k in
                            ('active', 'bootstrap_closed', 'can_manage_users', 'is_demo')))
        print('HTTP_CURRENT_LOCAL_ADMIN', accepted)
        if not accepted:
            raise Blocked('CURRENT_ADMIN_SESSION_UNVERIFIED')
        print('PASS: CURRENT_ADMIN_GET_ONLY; OLD_POST401_CAUSE_UNPROVEN')
        return 0
    except Blocked as error:
        print('BLOCKED:', str(error))
    except (Exception, KeyboardInterrupt):
        print('BLOCKED: CONTROL_INCOMPLETE; details hidden')
    return 1

raise SystemExit(main())
PY
```

Build sabiti a65290a kaynak ağacından hesaplandı; farklı sürüme uyarlamak için
otomatik değiştirilemez. Process environment yalnız başlangıç yapılandırmasını
gösterir; çalışan engine'in iç durumunu veya DB/şema satırlarını ayrıca ölçmez.
GET200 yalnız mevcut oturum/kimlik okuma kabulüdür; yeni parola girişini veya
eski POST401'in nedenini kanıtlamaz. GET401 eksik/eski cookie, süreç belleği veya
ID yeniden okuması sınıfında kalır; yanlış parola/ADMIN yokluğu sonucu çıkarılmaz.
GET503 depolama sınıfıdır; eski şema eksikliği yeniden kanıtlanmış sayılmaz.
Build mismatch tek başına eski401'in nedeni değildir; restart/deploy önerilmez.

Yalnız yeni komutun syntax ve ağsız kontrol akışı doğrulanır. Gerçek VDS/HTTP
sonucu alınmadığından HTTP401 kök nedeni ve gerçek kabul **BLOCKED** kalır.
