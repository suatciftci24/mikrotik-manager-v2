#!/usr/bin/env python3
"""Install the approved CEBECI V2.6.16 pilot on its fixed VDS."""
import ctypes
from datetime import datetime, timedelta, timezone
import fcntl
import getpass
import grp
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path('/srv/mikrotik-v26-next')
OBSERVER_ROOT = Path('/opt/mikrotik-v2-cebeci-observer')
RUNTIME = Path('/run/mikrotik-v2-cebeci-observer')
API = 'mikrotik-v26-api.service'
WEB = 'mikrotik-v26-web.service'
OBSERVER = 'mikrotik-v2-cebeci-observer.service'
UNIT = Path('/etc/systemd/system') / OBSERVER
DROP = Path('/etc/systemd/system') / (API + '.d') / '60-cebeci-snapshot.conf'
USER = 'mtv2-cebeci-observer'
GROUP = 'mtv2-cebeci-read'
HOST = 'v26.mikmanager.com.tr'
IP = '185.139.5.51'
REPO = 'https://github.com/suatciftci24/mikrotik-manager-v2.git'
OLD = 'eafa2473b1ab82c99e9f58607be8dacdecad7423'
NEW = '433e2ba99a7f4a24ba904b14db98b57f30709f9e'
PATHS = ('backend/app', 'frontend/dist', 'release.json')
MATERIAL_SUFFIX = ('.local', 'cebeci-pilot', 'v2614-observer')


def require(condition):
    if not condition:
        raise RuntimeError('CHECK_REJECTED')


def command(*args, cwd=None, env=None, capture=False, timeout=60):
    return subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=timeout,
                          check=True).stdout


def system(*args, capture=False):
    return command('systemctl', *args, capture=capture, timeout=120)


def prop(unit, name):
    return system('show', '--property=' + name, '--value', unit, capture=True).decode().strip()


class PanelConnection(http.client.HTTPSConnection):
    def __init__(self):
        super().__init__(HOST, port=443, context=ssl.create_default_context(), timeout=6)
        self._create_connection = lambda _address, *args: socket.create_connection((IP, 443), *args)


def request(path, *, cookie=None, credentials=None, status=200):
    conn = PanelConnection()
    headers = {'Cache-Control': 'no-cache'}
    if cookie:
        headers['Cookie'] = cookie
    body = None
    if credentials:
        body = json.dumps(dict(zip(('username', 'password'), credentials)))
        headers['Content-Type'] = 'application/json'
    try:
        conn.request('POST' if credentials else 'GET', path, body, headers)
        response = conn.getresponse()
        require(response.status == status)
        data = response.read(16 * 1024 * 1024 + 1)
        require(len(data) <= 16 * 1024 * 1024)
        return data, dict(response.getheaders())
    finally:
        conn.close()


def api_get(path, *, cookie=None):
    return json.loads(request(path, cookie=cookie)[0])


def login(credentials):
    data, headers = request('/api/v1/auth/login', credentials=credentials)
    user = json.loads(data)
    require(user['role_code'] == 'ADMIN' and user['can_manage_users'] is True)
    cookies = SimpleCookie(headers.get('set-cookie') or headers.get('Set-Cookie') or '')
    token = cookies['v2_session'].value
    require(re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token))
    return 'v2_session=' + token


def build_id():
    digest = hashlib.sha256()
    for path in sorted((ROOT/'backend/app').rglob('*.py')):
        digest.update(str(path.relative_to(ROOT)).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def health(version, commit=None):
    for unit in (API, WEB):
        system('is-active', '--quiet', unit)
    ready = api_get('/api/ready')
    require(ready['service'] == 'mikrotik-manager-v2' and ready['api_version'] == 'v1'
            and ready['runtime_profile'] == 'v26-isolated-acceptance'
            and ready['app_version'] == version and ready['build_id'] == build_id()
            and ready['repo_id'] == hashlib.sha256(str(ROOT).encode()).hexdigest())
    require(json.loads((ROOT/'release.json').read_bytes())['version'] == version)
    require(api_get('/api/health')['database_connected'] is True)
    dist = ROOT/'frontend/dist'
    index = request('/')[0]
    require(index == (dist/'index.html').read_bytes())
    if commit:
        require(re.search(rb'<meta[^>]+name="mikrotik-app-version"[^>]+content="2\.6\.16"', index)
                and commit.encode() in index)
    assets = set(re.findall(rb'["\'](/assets/[A-Za-z0-9_.-]+\.(?:js|css))["\']', index))
    require(assets and any(asset.endswith(b'.js') for asset in assets))
    for asset in assets:
        path = asset.decode()
        require(request(path)[0] == (dist/path.removeprefix('/')).read_bytes())


def wait_for(check, seconds):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return check()
        except (RuntimeError, OSError, KeyError, ValueError, http.client.HTTPException, subprocess.SubprocessError):
            if time.monotonic() >= deadline:
                raise RuntimeError('ACCEPTANCE_TIMEOUT') from None
            time.sleep(2)


def new_path(path):
    require(not os.path.lexists(path))


def plain(path, directory=False):
    mode = path.lstat().st_mode
    require(path.resolve() == path and (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)))
    return path


def read_material(directory, name, limit):
    path = plain(directory/name)
    parent = directory.stat()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == parent.st_uid and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) in (0o400, 0o600) and 0 < info.st_size <= limit)
        data = stream.read(limit+1)
    require(0 < len(data) <= limit)
    return data


def verify_baseline():
    require(os.geteuid() == 0 and sys.stdin.isatty() and sys.stderr.isatty())
    require(any(a.get('local') == IP for link in json.loads(command('ip', '-j', 'address', capture=True))
                for a in link.get('addr_info', [])))
    plain(ROOT, directory=True)
    for path in (ROOT/'backend', ROOT/'frontend'):
        plain(path, directory=True)
    for name in PATHS:
        plain(ROOT/name, directory=name != 'release.json')
    for unit, subdirectory in ((API, 'backend'), (WEB, 'frontend')):
        require(prop(unit, 'LoadState') == 'loaded' and prop(unit, 'NeedDaemonReload') == 'no')
        for hook in ('ExecCondition', 'ExecStartPre', 'ExecStartPost', 'ExecStop', 'ExecStopPost'):
            require(not prop(unit, hook))
        start = prop(unit, 'ExecStart')
        executable = re.match(r'^\{ path=([^ ;]+) ; argv\[\]=([^;]+) ;', start)
        require(executable is not None)
        program = Path(executable[1]).name
        argv = executable[2].split()
        if unit == API:
            require('app.main:app' in argv and (program == 'uvicorn'
                    or program.startswith('python') and argv[1:3] == ['-m', 'uvicorn']))
        else:
            require(program.startswith('python') and argv[1:3] == ['-m', 'http.server']
                    or program in ('node', 'vite') and 'preview' in argv)
        cwd = Path(os.readlink('/proc/' + str(int(prop(unit, 'MainPID'))) + '/cwd'))
        require(cwd in (ROOT, ROOT/subdirectory, ROOT/'frontend/dist') and
                (unit != API or cwd != ROOT/'frontend/dist'))
    api_owner = prop(API, 'User')
    require(api_owner and pwd.getpwnam(api_owner).pw_uid != 0 and api_owner != USER)
    for path in (OBSERVER_ROOT, UNIT, DROP, RUNTIME, Path('/etc/systemd/system/multi-user.target.wants')/OBSERVER):
        new_path(path)
    require(prop(OBSERVER, 'LoadState') == 'not-found')
    for lookup, name in ((pwd.getpwnam, USER), (grp.getgrnam, GROUP)):
        try:
            lookup(name)
        except KeyError:
            continue
        raise RuntimeError('ACCOUNT_ALREADY_EXISTS')
    health('2.6.13')


def archive_source(work):
    repo = work/'source.git'
    env = {'PATH': os.environ['PATH'], 'HOME': str(work), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
    command('git', 'init', '--bare', str(repo), env=env)
    command('git', '--git-dir', str(repo), 'fetch', '--depth=1', '--no-tags', REPO, NEW, OLD, env=env, timeout=180)
    require(command('git', '--git-dir', str(repo), 'rev-parse', NEW+'^{commit}', env=env, capture=True).decode().strip() == NEW)
    changed = command('git', '--git-dir', str(repo), 'diff', '--name-only', OLD, NEW, '--',
                      'migrations', 'backend/requirements.txt', env=env, capture=True)
    require(not changed and (ROOT/'backend/requirements.txt').read_bytes() == command(
        'git', '--git-dir', str(repo), 'show', NEW+':backend/requirements.txt', env=env, capture=True))
    selected = ('release.json', 'backend/app', 'backend/requirements.txt', 'frontend',
                'deploy/cebeci-observer/api-snapshot.conf', 'deploy/cebeci-observer/'+OBSERVER)
    packed = work/'source.tar'
    command('git', '--git-dir', str(repo), 'archive', '--output', str(packed), NEW, '--', *selected, env=env)
    source = work/'source'
    source.mkdir()
    with tarfile.open(packed) as archive:
        require(all(member.isfile() or member.isdir() for member in archive.getmembers()))
        archive.extractall(source, filter='data')
    require(json.loads((source/'release.json').read_bytes())['version'] == '2.6.16')
    return source


def backup_live():
    backup = Path(tempfile.mkdtemp(prefix='mikrotik-v2613-before-v2616-', dir='/srv'))
    path = backup/'code-and-dist.tar'
    command('tar', '-cpf', str(path), '-C', str(ROOT), *PATHS, timeout=180)
    command('tar', '-df', str(path), '-C', str(ROOT), timeout=180)
    digest = file_digest(path)
    put(backup/'sha256', (digest+'  code-and-dist.tar\n').encode(), 0o600)
    verify_backup(backup)
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
    parent = os.open(backup, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    print('Yedek doğrulandı:', backup, flush=True)
    return backup


def verify_backup(backup):
    path = backup/'code-and-dist.tar'
    require(file_digest(path) == (backup/'sha256').read_text().split()[0])
    command('tar', '-df', str(path), '-C', str(ROOT), timeout=180)


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def owned_tree(path, uid, gid):
    for base, directories, files in os.walk(path):
        for name in [*directories, *files]:
            os.chown(Path(base)/name, uid, gid, follow_symlinks=False)
    os.chown(path, uid, gid)


def build_frontend(source, stage):
    with tempfile.TemporaryDirectory(prefix='mtv26-build-') as name:
        build = Path(name)
        shutil.copytree(source/'frontend', build/'frontend')
        shutil.copy2(source/'release.json', build/'release.json')
        account = pwd.getpwnam(USER)
        owned_tree(build, account.pw_uid, account.pw_gid)
        prefix = ('runuser', '-u', USER, '--', 'env', '-i', 'PATH=/usr/local/bin:/usr/bin:/bin',
                  f'HOME={build}', 'V2_BUILD_COMMIT='+NEW)
        command(*prefix, 'npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', cwd=build/'frontend', timeout=600)
        command(*prefix, 'npm', 'run', 'build', cwd=build/'frontend', timeout=600)
        dist = build/'frontend/dist'
        require((dist/'release.json').read_bytes() == (source/'release.json').read_bytes()
                and NEW.encode() in (dist/'index.html').read_bytes())
        require(all(not item.is_symlink() for item in dist.rglob('*')))
        shutil.copytree(dist, stage/'frontend/dist')
    assets = stage/'frontend/dist/assets'
    for old in (ROOT/'frontend/dist/assets').iterdir():
        require(old.is_file() and not old.is_symlink())
        target = assets/old.name
        if target.exists():
            require(file_digest(old) == file_digest(target))
        else:
            shutil.copy2(old, target)
    for item in (stage/'frontend/dist').rglob('*'):
        item.chmod(0o755 if item.is_dir() else 0o644)
    (stage/'frontend/dist').chmod(0o755)


def observer_setup(source):
    OBSERVER_ROOT.chmod(0o755)
    shutil.copytree(source/'backend', OBSERVER_ROOT/'backend')
    python = OBSERVER_ROOT/'venv/bin/python'
    command('python3', '-m', 'venv', str(OBSERVER_ROOT/'venv'), timeout=180)
    account = pwd.getpwnam(USER)
    owned_tree(OBSERVER_ROOT/'venv', account.pw_uid, account.pw_gid)
    command('runuser', '-u', USER, '--', str(python), '-m', 'pip', '--isolated', 'install',
            '--disable-pip-version-check', '--no-cache-dir', '--only-binary=:all:', '-r', str(OBSERVER_ROOT/'backend/requirements.txt'),
            timeout=600)
    owned_tree(OBSERVER_ROOT/'venv', 0, 0)
    for item in OBSERVER_ROOT.rglob('*'):
        if not item.is_symlink():
            mode = item.stat().st_mode
            item.chmod(0o755 if item.is_dir() or mode & 0o100 else 0o644)
    return account


def put(path, data, mode, owner=0, group=0):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as stream:
        stream.write(data)
        os.fchown(stream.fileno(), owner, group)
        os.fchmod(stream.fileno(), mode)
        stream.flush()
        os.fsync(stream.fileno())


def approval(account, material):
    private = OBSERVER_ROOT
    for entry in MATERIAL_SUFFIX:
        private /= entry
        private.mkdir(mode=0o700)
        os.chown(private, account.pw_uid, account.pw_gid)
    for name, content in material.items():
        put(private/name, content, 0o600, account.pw_uid, account.pw_gid)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    data = json.dumps({'scope':'V2614_CEBECI_TOWERS_READ_ONLY', 'expires_at':expires.isoformat()})
    put(private/'approval.json', data.encode(), 0o600, account.pw_uid, account.pw_gid)


def exchange(left, right):
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    if rename(-100, os.fsencode(left), -100, os.fsencode(right), 2):
        raise OSError(ctypes.get_errno(), 'EXCHANGE_FAILED')


def accept(cookie):
    system('is-active', '--quiet', OBSERVER)
    data, headers = request('/api/v1/device-inventory', cookie=cookie)
    require(next((value for key, value in headers.items() if key.lower() == 'cache-control'), '') == 'no-store')
    payload = json.loads(data)
    require(payload['source'] == 'ROUTEROS_READ_ONLY' and payload['is_demo'] is False
            and payload['read_only'] is True)
    row, = payload['routers']
    require(row['id'] == 'device-cebeci-towers' and row['identity'] == 'CEBECI_TOWERS'
            and row['model'] == 'RB3011UiAS' and (row['routeros_version'] or '').removesuffix(' (stable)') == '6.49.19'
            and row['connection'] == 'ONLINE' and row['freshness'] == 'RECENT' and row['error'] is None
            and row['accounts_complete'] is True and len(row['accounts']) > 0
            and row['wan_status'] == 'UNKNOWN' and all(row[field] is None for field in ('wan_interface','rx_bytes','tx_bytes')))
    seconds = (datetime.fromisoformat(payload['authorization_expires_at']) - datetime.now(timezone.utc)).total_seconds()
    require(0 < seconds <= 86400)
    return len(row['accounts'])


def interrupted(_sig, _frame):
    raise RuntimeError('INTERRUPTED')


def run():
    stage_name = 'ön kontrol'
    staged = None
    backup = None
    switched = []
    undo = []
    stopped = False
    stage_dir = None
    os.umask(0o077)
    try:
        require(os.geteuid() == 0)
        fd = os.open('/run/mikrotik-v2616-cebeci-deploy.lock',
                     os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'wb') as lock:
            info = os.fstat(lock.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                verify_baseline()
                directory = Path(input('Mevcut V2 gözlemci özel malzeme dizini (mutlak yol): ').strip())
                require(directory.is_absolute() and directory.parts[-3:] == MATERIAL_SUFFIX)
                plain(directory, directory=True)
                require(stat.S_IMODE(directory.stat().st_mode) == 0o700)
                material = {'ca.pem':read_material(directory,'ca.pem',262144),
                            'password':read_material(directory,'password',1024)}
                require(all(char not in material['password'] for char in (b'\r', b'\n', b'\0')))
                material['password'].decode('utf-8')
                ssl.create_default_context(cadata=material['ca.pem'].decode())
                credentials = (input('Mevcut V2 merkezi yönetici adı: ').strip(), getpass.getpass('V2 yönetici parolası: '))
                login(credentials)

                stage_name = 'kaynak ve doğrulanmış yedek'
                stage_dir = Path(tempfile.mkdtemp(prefix='.v2616-stage-', dir=ROOT))
                staged = stage_dir/'publish'
                (staged/'backend').mkdir(parents=True)
                (staged/'frontend').mkdir()
                source = archive_source(stage_dir)
                backup = backup_live()

                stage_name = 'izole gözlemci ve frontend hazırlığı'
                command('groupadd', '--system', GROUP)
                undo.append(lambda: command('groupdel', GROUP))
                command('useradd', '--system', '--gid', GROUP, '--no-create-home', '--home-dir',
                        '/nonexistent', '--shell', '/usr/sbin/nologin', USER)
                undo.append(lambda: command('userdel', USER))
                OBSERVER_ROOT.mkdir(mode=0o755)
                undo.append(lambda: shutil.rmtree(OBSERVER_ROOT))
                account = observer_setup(source)
                build_frontend(source, staged)
                shutil.copytree(source/'backend/app', staged/'backend/app')
                for item in (staged/'backend/app').rglob('*'):
                    item.chmod(0o755 if item.is_dir() else 0o644)
                (staged/'backend/app').chmod(0o755)
                shutil.copy2(source/'release.json', staged/'release.json')
                (staged/'release.json').chmod(0o644)
                put(UNIT, (source/'deploy/cebeci-observer'/OBSERVER).read_bytes(), 0o644)
                undo.append(UNIT.unlink)
                command('systemd-analyze', 'verify', str(UNIT))
                require(DROP.parent.resolve() == DROP.parent)
                if not DROP.parent.exists():
                    DROP.parent.mkdir(mode=0o755)
                    DROP.parent.chmod(0o755)
                    undo.append(DROP.parent.rmdir)
                put(DROP, (source/'deploy/cebeci-observer/api-snapshot.conf').read_bytes(), 0o644)
                undo.append(DROP.unlink)
                system('daemon-reload')

                stage_name = 'V2.6.16 yayın geçişi'
                verify_backup(backup)
                stopped = True
                system('stop', WEB, API)
                for name in PATHS:
                    mask = signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP))
                    try:
                        exchange(ROOT/name, staged/name)
                        switched.append(name)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                system('start', API, WEB)
                wait_for(lambda: health('2.6.16', NEW), 60)
                stage_name = '24 saatlik pilot ve gerçek cihaz kabulü'
                approval(account, material)
                undo.append(lambda: system('disable', '--now', OBSERVER))
                system('enable', '--now', OBSERVER)
                request('/api/v1/device-inventory', status=401)
                cookie = login(credentials)
                count = wait_for(lambda: accept(cookie), 95)
                print(f'PASS — V2.6.16 {NEW} · CEBECI_TOWERS ONLINE · {count} hesap · WAN bilinmiyor')
                return 0

            except Exception:
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                    signal.signal(sig, signal.SIG_IGN)
                print('FAIL — aşama:', stage_name, file=sys.stderr)
                recovery_errors = []

                def recover(action):
                    try:
                        action()
                    except Exception:
                        recovery_errors.append(True)

                if stopped:
                    recover(lambda: system('stop', WEB, API))
                for name in reversed(switched):
                    recover(lambda name=name: exchange(ROOT/name, staged/name))
                for action in reversed(undo):
                    recover(action)
                if undo or stopped:
                    recover(lambda: system('daemon-reload'))
                if stopped:
                    recover(lambda: verify_backup(backup))
                    recover(lambda: system('start', API, WEB))
                    recover(lambda: wait_for(lambda: health('2.6.13'), 60))
                if recovery_errors:
                    print('ROLLBACK BLOCKED — yedek ve hazırlık dizini:', backup, stage_dir, file=sys.stderr)
                    stage_dir = None
                elif stopped:
                    print('ROLLBACK — V2.6.13 yedek ve HTTPS/API sağlığı doğrulandı.', file=sys.stderr)
                else:
                    print('BLOCKED — yayın geçişi başlamadı.', file=sys.stderr)
                return 1
            finally:
                if stage_dir is not None:
                    try:
                        shutil.rmtree(stage_dir)
                    except OSError:
                        print('Hazırlık dizini inceleme için kaldı:', stage_dir, file=sys.stderr)
    except Exception:
        print('BLOCKED — root, kurulum kilidi veya yerel hazırlık reddedildi.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    for caught in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(caught, interrupted)
    raise SystemExit(run())
