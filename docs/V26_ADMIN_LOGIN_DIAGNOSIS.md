# V2.6 ADMIN login401 — 2026-11-06

Başlangıç main-guncel/9980701. Kullanıcı kanıtı: health200, DB bağlı,
LOCAL/ADMIN/active kayıt, iki initialized bayrağı true ve doğrudan PASSWORD_MATCH.
SSH denenmedi; VDS, hesap, parola, DB ve servis değiştirilmedi.

## Kaynağın gösterdiği sınır

`POST /api/v1/auth/login` → `security.login_demo` → `identity.find_user` →
adapter `_verify` + `inspect_setup` → tam eşitlikli username sorgusu →
`verify_password` → bellekte session → `current_demo_user(token)` ile ID sorgusu.
`find_user` doğrulanan adapter şemasını kullanır; v26 profili v26_acceptance seçer.

- `login_demo` kullanıcı None, active=false veya verify_password=false ise401.
  Username büyük/küçük harf, boşluk ve e-posta bakımından normalize edilmez.
  Yalnız mühür kapanmamış demo profilinde belgeli demo e-posta alias'ı vardır.
- Kapalı mühürde demo-user veya LOCAL olmayan kayıt filtrelenir: None →401.
- Login route'u tokenı cookie'den geri okumaz; doğrudan current_demo_user'a verir.
  Burada ID sorgusu None/pasif dönerse ayrıca401. Secure cookie, istemcinin cookie
  saklamaması veya sonraki /me isteği sorunu bu ilk POST401'i açıklamaz.
- SQLAlchemy/storage/şema hatası ve eksik/çelişkili kurulum mühürü normalde503'tür.
  İki initialized bayrağı tek başına first_admin_setup/admin_id/marker bütünlüğü
  kanıtı değildir. Health DB ping'i kimlik şemasını doğrulamaz.
- Güncel verify_password scrypt N=131072, r=8, p=1, salt16/digest32 ve
  maxmem256MiB destekler. ValueError/TypeError false olur; PASSWORD_MATCH başka
  yorumlayıcı, farklı kod/veri/parametre veya başka girdiden geldiyse API ile
  eşdeğer kabul edilemez. API venv'i yerine sistem Python'unda sqlalchemy
  bulunmaması API hatası değildir.

Verilen kanıtlar çalışan API'nin aynı username/parola, şema, kaynak sürümü ve
aynı kayıtla doğrulama yaptığını henüz göstermiyor. Kesin VDS kök nedeni BLOCKED.
Parola kontrolünü/kimlik filtresini gevşetecek ürün değişikliği yapılmadı.

## Hedefli yerel doğrulama

Yeni test_admin_login_diagnosis içinde beş ağsız test PASS: gerçek N131072
sentetik hash ile sealed LOCAL ADMIN, gerçek find_user/inspect_setup/login route
ve ID yeniden okuması; tam username eşitliği; yanlış parola/pasif401;
kapalı mühürde non-LOCAL401; unsealed acceptance/SQL hatası storage unavailable.
SQL yanıtları sentetiktir; HTTP socket, gerçek PG veya VDS PASS değildir.
Önceki PASS testleri/genel suite tekrarlanmadı. Ürün kusuru yeniden üretilemedi.

## Sonraki tek adım: VDS gerçek TTY'sinde salt okunur tanı

Aşağıdaki tek komut yalnız mevcut izole API sürecinin V2 ortamını belleğe alır;
çıktıya sır, username, hash, DSN veya exception ayrıntısı yazmaz. HTTP login/session
oluşturmaz, DB bağlantıları read-only ve çıkışta rollback'tir. Mevcut API'nin
bellekte yüklediği Python kodunu okuyamaz: diskteki kodla sonucu gösterir;
sonuç başarılıysa eski süreç kodu/gerçek HTTP girdisi farkı hâlâ dışlanmış olmaz.
Hedef süreç/izin/konfigürasyon uyuşmazlığında otomatik alternatif veya retry yoktur.

**VDS terminali** (dosya oluşturmaz; mevcut ADMIN bilgileri yalnız gizli TTY sorularına):

```bash
/tmp/mikrotik-v26-acceptance/.venv/bin/python -I -B - <<'PY'
import os, sys, getpass, warnings, hashlib
from pathlib import Path

root = Path('/tmp/mikrotik-v26-acceptance')
engine = None
try:
    warnings.simplefilter('error', getpass.GetPassWarning)
    if root.resolve() != root:
        raise RuntimeError()
    candidates = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            if (process / 'cwd').resolve() != root:
                continue
            args = (process / 'cmdline').read_bytes().split(b'\0')
            if any(b'uvicorn' in arg for arg in args):
                candidates.append(process)
        except OSError:
            continue
    if len(candidates) != 1:
        print('BLOCKED: API_PROCESS_NOT_UNIQUE_OR_UNREADABLE')
        raise SystemExit(1)
    values = {}
    for item in (candidates[0] / 'environ').read_bytes().split(b'\0'):
        key, sep, value = item.partition(b'=')
        if sep and key.startswith(b'V2_'):
            values[key.decode()] = value.decode()
    for key in list(os.environ):
        if key.startswith('V2_'):
            del os.environ[key]
    os.environ.update(values)
    if values.get('V2_DEPLOYMENT_PROFILE') != 'v26-isolated-acceptance':
        raise RuntimeError()
    os.chdir(root)
    sys.path.insert(0, str(root / 'backend'))
    from app.services import identity
    from app.core.database import engine
    engine.update_execution_options(postgresql_readonly=True,
                                    isolation_level='REPEATABLE READ')
    store = identity.adapter()
    if store.schema != 'v26_acceptance':
        raise RuntimeError()
    print('SCHEMA_V26', True)
    for name in ('app/core/security.py', 'app/services/identity.py',
                 'app/services/identity_setup.py', 'app/api/v1/auth.py'):
        print('SOURCE_SHA256', name,
              hashlib.sha256((root / 'backend' / name).read_bytes()).hexdigest())
    with open('/dev/tty', 'r+') as tty:
        username = getpass.getpass('Mevcut ADMIN kullanıcı adı: ', stream=tty)
        password = getpass.getpass('Mevcut ADMIN parolası: ', stream=tty)
    user = identity.find_user(username, by_username=True)
    print('FIND_BY_EXACT_USERNAME', user is not None)
    if user is not None:
        print('LOCAL_ADMIN_ACTIVE', user.get('account_origin') == 'LOCAL'
              and user.get('role') == 'ADMIN' and user.get('active') is True)
        print('SETUP_CLOSED', user.get('bootstrap_closed') is True)
        print('SOURCE_VERIFY_PASSWORD', identity.verify_password(password, user['password_hash']))
        again = identity.find_user(user['id'])
        print('ID_REREAD_ACTIVE', again is not None and again.get('active') is True)
    del username, password
    print('READ_ONLY_DIAGNOSIS_COMPLETE; HTTP login kabulü değildir.')
except (Exception, KeyboardInterrupt):
    print('BLOCKED: READ_ONLY_DIAGNOSIS_NOT_COMPLETED; ayrıntılar gizlendi.')
finally:
    if engine is not None:
        engine.dispose()
PY
```

Yerel karşılaştırma SHA256 (başlangıç 9980701; ürün kodu değişmedi):

- `app/core/security.py`: `92cbcb93e9140a2cbda120c4a13d4020bbf89a182f29df102dfc4fcf7cf84b6f`
- `app/services/identity.py`: `e2f632acaf441f86662995aa793c3a2d0dd78ecaa367ae7d3160ab81f0af94e8`
- `app/services/identity_setup.py`: `af711d795cdef8aa91eea5c62990cf252a8006506e11fb61c207f78c53d561ac`
- `app/api/v1/auth.py`: `2983fa671dd0407c56f001c736b8cf63eedb0bff532d88c1347cdae000974fcd`
