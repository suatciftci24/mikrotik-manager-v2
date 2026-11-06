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
kontrol yapılmaz; yeni açık VDS izni gerekir. Aşağıdaki eski POST login/logout
tanısı ayrı kapsamdır; bu görevde salt okunur GET kontrolünün yerine çalıştırılmaz.

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

## Tek sonraki işlem — VDS gerçek TTY'sinde

Aşağıdaki tek komut DB'ye doğrudan bağlanmaz, disk kaynaklarını import etmez,
health/parola/kimlik SELECT testlerini tekrarlamaz. Yalnız hedef dinleyiciye
ready ve tek login isteği; oturum cookie'si gönderilebiliyorsa logout yapar.
Login/logout yalnız mevcut uygulamanın bellek oturumunu etkiler; hesap/parola
ve servis değişikliği yoktur. Kimlik bilgileri, payload/yanıt gövdesi/cookie ve
süreç argv/environment değerleri gösterilmez veya dosyaya yazılmaz.

Birden fazla/görünmeyen listener PID'sinde durur. PID tespiti listener sahibini
kanıtlar; dış proxy/worker zincirindeki her isteğin worker kimliğini kanıtlamaz.
BUILD_MATCH false ise eski yüklenmiş kod ihtimali kanıtlanır, tek başına401
nedeni kanıtlanmaz. POST200 ise bu yeni istekte401 yeniden üretilmemiştir;
eski isteğin nedeni yine kesinleşmez. POST401 ve aynı build/PID ise çalışan
süreç içi kimlik/parola/ID okuma farkı kalır; otomatik restart önerilmez.

```bash
/tmp/mikrotik-v26-acceptance/.venv/bin/python -I -B - <<'PY'
import getpass, hashlib, http.cookiejar, json, re, subprocess, warnings
from pathlib import Path
import urllib.request as u
from urllib.error import HTTPError

root = Path('/tmp/mikrotik-v26-acceptance')
base = 'http://127.0.0.1:18996'
jar = http.cookiejar.CookieJar()
class NoRedirect(u.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
client = u.build_opener(u.ProxyHandler({}), NoRedirect(), u.HTTPCookieProcessor(jar))

def process():
    result = subprocess.run(['ss', '-H', '-ltnp', 'sport = :18996'],
                            capture_output=True, text=True, timeout=5, check=True)
    pids = set(re.findall(r'pid=(\d+)', result.stdout))
    if len(pids) != 1:
        raise RuntimeError()
    pid = next(iter(pids))
    proc = Path('/proc') / pid
    if (proc / 'cwd').resolve() != root:
        raise RuntimeError()
    start = (proc / 'stat').read_text().split(') ', 1)[1].split()[19]
    return pid, start

def call(path, data=None):
    req = u.Request(base + path, data=data,
                    headers={'Content-Type': 'application/json'})
    try:
        with client.open(req, timeout=15) as response:
            return response.status, response.read(65536)
    except HTTPError as error:
        code = error.code
        body = error.read(65536)
        error.close()
        return code, body

attempted = False
try:
    warnings.simplefilter('error', getpass.GetPassWarning)
    if root.resolve() != root:
        raise RuntimeError()
    before = process()
    code, body = call('/api/ready')
    if code != 200:
        print('BLOCKED: READY_HTTP', code)
        raise SystemExit(1)
    ready = json.loads(body)
    if (ready.get('service') != 'mikrotik-manager-v2'
            or ready.get('api_port') != 18996
            or ready.get('repo_id') != hashlib.sha256(str(root).encode()).hexdigest()):
        print('BLOCKED: TARGET_IDENTITY_MISMATCH')
        raise SystemExit(1)
    digest = hashlib.sha256()
    for path in sorted((root / 'backend/app').rglob('*.py')):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b'\0'); digest.update(path.read_bytes()); digest.update(b'\0')
    print('RUNNING_BUILD_MATCHES_DISK', ready.get('build_id') == digest.hexdigest())
    print('LISTENER_PID', before[0])
    with open('/dev/tty', 'r+') as tty:
        username = getpass.getpass('Mevcut ADMIN kullanıcı adı: ', stream=tty)
        password = getpass.getpass('Mevcut ADMIN parolası: ', stream=tty)
    payload = json.dumps({'username': username, 'password': password}).encode('utf-8')
    print('PAYLOAD_EXACT_JSON', json.loads(payload) ==
          {'username': username, 'password': password})
    del username, password
    attempted = True
    code, body = call('/api/v1/auth/login', payload)
    del payload
    print('POST_LOGIN_HTTP', code)
    if code == 401:
        try:
            detail = json.loads(body).get('detail')
        except (ValueError, AttributeError):
            detail = None
        category = {'Giriş bilgileri geçersiz': 'CREDENTIAL_GATE',
                    'Oturum gerekli': 'SESSION_OR_ID_REREAD'}.get(detail, 'OTHER_401')
        print('REJECTION_CATEGORY', category)
    elif code == 200:
        user = json.loads(body)
        print('HTTP_LOCAL_ADMIN', user.get('account_origin') == 'LOCAL'
              and user.get('role_code') == 'ADMIN')
    print('LISTENER_PROCESS_UNCHANGED', process() == before)
except (Exception, KeyboardInterrupt):
    print('BLOCKED: HTTP_DIAGNOSIS_INCOMPLETE; ayrıntılar gizlendi.')
finally:
    if attempted and list(jar):
        try:
            req = u.Request(base + '/api/v1/auth/logout', data=b'{}')
            jar.add_cookie_header(req)
            if req.has_header('Cookie'):
                print('CLEANUP_LOGOUT_HTTP', call('/api/v1/auth/logout', b'{}')[0])
            else:
                print('BLOCKED: COOKIE_POLICY_PREVENTS_SESSION_CLEANUP')
        except Exception:
            print('BLOCKED: SESSION_CLEANUP_UNVERIFIED')
    jar.clear()
PY
```

Komut yalnız syntax açısından kontrol edildi; VDS'de çalıştırılmadı. Eski PASS
suite çalıştırılmadı; gerçek HTTP sonucu bekleniyor. SSH denemesi yapılmadı.
