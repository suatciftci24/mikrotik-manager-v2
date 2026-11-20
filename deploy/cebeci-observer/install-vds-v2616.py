#!/usr/bin/env python3
"""Install the approved CEBECI V2.6.16 pilot on its fixed VDS."""
import argparse
from contextlib import contextmanager
import ctypes
import errno
from datetime import datetime, timedelta, timezone
import fcntl
import getpass
import grp
import hashlib
import http.client
from http.cookies import SimpleCookie
import io
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
WEB_NPM_USER = 'mikadmin'
WEB_NPM_FRAGMENT = '/etc/systemd/system/' + WEB
WEB_PREVIEW_HOST = '127.0.0.1'
WEB_PREVIEW_PORT = 15173
WEB_NPM_ARGV = ('/usr/bin/npm', 'exec', '--', 'vite', 'preview', '--host', WEB_PREVIEW_HOST,
                '--port', str(WEB_PREVIEW_PORT), '--strictPort')
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


class CheckRejected(RuntimeError):
    """Contains only a fixed operator-facing code."""


def require(condition, code):
    if not condition:
        raise CheckRejected(code)


def error_suffix(error):
    if isinstance(error, ssl.SSLError):
        return '_TLS'
    if isinstance(error, subprocess.TimeoutExpired):
        return '_TIMEOUT'
    if isinstance(error, OSError):
        return {errno.EACCES:'_PERMISSION', errno.EPERM:'_PERMISSION', errno.ENOENT:'_NOT_FOUND',
                errno.ENOSPC:'_NO_SPACE', errno.EROFS:'_READ_ONLY', errno.EXDEV:'_CROSS_DEVICE',
                errno.EEXIST:'_ALREADY_EXISTS'}.get(error.errno, '_IO')
    return ''


@contextmanager
def gate(code):
    try:
        yield
    except CheckRejected:
        raise
    except Exception as error:
        raise CheckRejected(code + error_suffix(error)) from None


def step(code, action, *args, **kwargs):
    with gate(code):
        return action(*args, **kwargs)


def tool_failure(code, returncode, output):
    output = output.lower()
    known = (
        (b'no space left', 'NO_SPACE'),
        (b'permission denied', 'PERMISSION'),
        (b'eacces', 'PERMISSION'),
        (b'read-only file system', 'READ_ONLY'),
        (b'ensurepip is not available', 'ENSUREPIP_UNAVAILABLE'),
        (b'no module named ensurepip', 'ENSUREPIP_UNAVAILABLE'),
        (b'no matching distribution found', 'NO_COMPATIBLE_DISTRIBUTION'),
        (b'resolutionimpossible', 'DEPENDENCY_CONFLICT'),
        (b'has requirement', 'DEPENDENCY_CONFLICT'),
        (b'which is not installed', 'DEPENDENCY_MISSING'),
        (b'command not found', 'COMMAND_MISSING'),
        (b'not executable', 'NOT_EXECUTABLE'),
        (b'failed to load', 'LOAD_FAILED'),
        (b'unknown key', 'UNIT_KEY_UNKNOWN'),
        (b'certificate_verify_failed', 'TLS'),
        (b'certificate verify failed', 'TLS'),
        (b'unable_to_verify_leaf_signature', 'TLS'),
        (b'eai_again', 'DNS'),
        (b'temporary failure in name resolution', 'DNS'),
        (b'enetunreach', 'NETWORK'),
        (b'econnrefused', 'NETWORK'),
        (b'could not resolve host', 'DNS'),
        (b'only install packages when your package.json', 'LOCKFILE_MISMATCH'),
        (b'ebadengine', 'NODE_ENGINE'),
        (b'cannot find module', 'MODULE_MISSING'),
        (b'modulenotfounderror', 'MODULE_MISSING'),
        (b'v2614_cebeci_observer_not_authorized', 'APPROVAL'),
        (b'v2614_cebeci_observer_scope_rejected', 'SCOPE'),
    )
    for pattern, label in known:
        if pattern in output:
            return code + '_' + label
    if code == 'FRONTEND_BUILD' and re.search(rb'error ts[0-9]+:', output):
        return code + '_TYPESCRIPT'
    return code + (f'_SIGNAL_{-returncode}' if returncode < 0 else f'_EXIT_{returncode}')


def command(*args, cwd=None, env=None, capture=False, timeout=60, code=None):
    if code is None:
        return subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=timeout,
                              check=True).stdout
    with gate(code + '_EXEC'), tempfile.TemporaryFile() as diagnostics:
        result = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE if capture else diagnostics,
                                stderr=diagnostics, stdin=subprocess.DEVNULL, timeout=timeout)
        if result.returncode:
            length = diagnostics.seek(0, os.SEEK_END)
            diagnostics.seek(max(0, length - 65536))
            raise CheckRejected(tool_failure(code, result.returncode, diagnostics.read(65536)))
        return result.stdout


def system(*args, capture=False, code=None):
    return command('systemctl', *args, capture=capture, timeout=120, code=code)


def prop(unit, name):
    return system('show', '--property=' + name, '--value', unit, capture=True).decode().strip()


class PanelConnection(http.client.HTTPSConnection):
    def __init__(self):
        super().__init__(HOST, port=443, context=ssl.create_default_context(), timeout=6)
        self._create_connection = lambda _address, *args: socket.create_connection((IP, 443), *args)


def request(path, *, cookie=None, credentials=None, status=200, code="HTTP", loopback=False):
    if loopback:
        require(cookie is None and credentials is None, 'WEB_LOOPBACK_PUBLIC_GET_ONLY')
        conn = http.client.HTTPConnection(WEB_PREVIEW_HOST, WEB_PREVIEW_PORT, timeout=6)
    else:
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
        require(response.status == status, code+"_STATUS")
        data = response.read(16 * 1024 * 1024 + 1)
        require(len(data) <= 16 * 1024 * 1024, code+"_BODY_LIMIT")
        return data, dict(response.getheaders())
    finally:
        conn.close()


def health_json(path, code):
    with gate(code + '_REQUEST'):
        raw, _ = request(path, code=code)
    with gate(code + '_JSON'):
        payload = json.loads(raw)
        require(isinstance(payload, dict), code + '_JSON')
        return payload


def login(credentials):
    with gate('ADMIN_LOGIN_REQUEST'):
        data, headers = request('/api/v1/auth/login', credentials=credentials, code='ADMIN_LOGIN')
    with gate('ADMIN_LOGIN_RESPONSE'):
        user = json.loads(data)
        require(user.get('role_code') == 'ADMIN' and user.get('can_manage_users') is True, 'ADMIN_ROLE_REQUIRED')
        cookies = SimpleCookie(headers.get('set-cookie') or headers.get('Set-Cookie') or '')
        require('v2_session' in cookies, 'ADMIN_SESSION_COOKIE_MISSING')
        token = cookies['v2_session'].value
        require(re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token), 'ADMIN_SESSION_COOKIE_INVALID')
        return 'v2_session=' + token


def checkout_git(*args):
    env = {'PATH': os.environ['PATH'], 'HOME': '/nonexistent',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    return command('git', '-c', 'safe.directory='+str(ROOT), '-C', str(ROOT), *args, env=env, capture=True)


def checkout_head():
    if not os.path.lexists(ROOT/'.git'):
        return None
    with gate('GIT_HEAD_UNREADABLE'):
        head = checkout_git('rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
        require(re.fullmatch(r'[a-f0-9]{40}', head), 'GIT_HEAD_INVALID')
        return head


def head_matches_api(head, running_build):
    if head is None:
        return 'GIT_HEAD_TREE_ABSENT'
    with gate('GIT_HEAD_TREE_UNREADABLE'):
        archive = checkout_git('archive', head, '--', 'backend/app', 'release.json')
        digest = hashlib.sha256()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tracked:
            for member in sorted(tracked.getmembers(), key=lambda item: item.name):
                if member.name.startswith('backend/app/') and member.name.endswith('.py') and member.isfile():
                    digest.update(member.name.encode() + b'\0' + tracked.extractfile(member).read() + b'\0')
            release = tracked.extractfile('release.json').read()
        matches = (digest.hexdigest() == running_build and release == (ROOT/'release.json').read_bytes())
    return 'GIT_HEAD_TREE_MATCHES_API' if matches else 'GIT_HEAD_TREE_DIFFERS_FROM_API'


def build_id(root=ROOT):
    digest = hashlib.sha256()
    for path in sorted((root/'backend/app').rglob('*.py')):
        digest.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def health(version, commit=None, expected_build=None, *, npm_preview=False):
    for unit, code in ((API, 'API_NOT_ACTIVE'), (WEB, 'WEB_NOT_ACTIVE')):
        with gate(code):
            system('is-active', '--quiet', unit)
    ready = health_json('/api/ready', 'API_READY')
    require(ready.get('service') == 'mikrotik-manager-v2', 'API_SERVICE_MISMATCH')
    require(ready.get('api_version') == 'v1', 'API_CONTRACT_MISMATCH')
    require(ready.get('runtime_profile') == 'v26-isolated-acceptance', 'API_PROFILE_MISMATCH')
    require(ready.get('app_version') == version, 'API_VERSION_MISMATCH')
    with gate('API_DISK_BUILD_UNREADABLE'):
        disk_build = build_id()
    require(ready.get('build_id') == disk_build, 'API_RUNNING_DISK_BUILD_MISMATCH')
    require(expected_build is None or disk_build == expected_build, 'API_PINNED_BUILD_MISMATCH')
    require(ready.get('repo_id') == hashlib.sha256(str(ROOT).encode()).hexdigest(), 'API_REPOSITORY_MISMATCH')
    with gate('DISK_RELEASE_UNREADABLE'):
        disk_release = json.loads((ROOT/'release.json').read_bytes())
        require(isinstance(disk_release, dict), 'DISK_RELEASE_INVALID')
    require(disk_release.get('version') == version, 'DISK_RELEASE_VERSION_MISMATCH')
    require(health_json('/api/health', 'API_HEALTH').get('database_connected') is True, 'API_DATABASE_UNHEALTHY')
    if npm_preview:
        verify_npm_web_unit()
    dist = ROOT/'frontend/dist'
    with gate('WEB_INDEX_REQUEST'):
        index = request('/', code='WEB_INDEX')[0]
    with gate('WEB_DISK_INDEX_UNREADABLE'):
        disk_index = (dist/'index.html').read_bytes()
    require(index == disk_index, 'WEB_INDEX_DISK_MISMATCH')
    if npm_preview:
        verify_preview_response('/', disk_index, 'WEB_LOOPBACK_INDEX')
    if commit:
        require(re.search(rb'<meta[^>]+name="mikrotik-app-version"[^>]+content="2\.6\.16"', index),
                'WEB_RELEASE_META_MISMATCH')
        require(re.search(rb'<meta[^>]+name="mikrotik-build-commit"[^>]+content="' + commit.encode() + rb'"', index),
                'WEB_COMMIT_META_MISMATCH')
    assets = set(re.findall(rb'["\'](/assets/[A-Za-z0-9_.-]+\.(?:js|css))["\']', index))
    require(assets and any(asset.endswith(b'.js') for asset in assets), 'WEB_INDEX_ASSETS_MISSING')
    for asset in sorted(assets):
        path = asset.decode()
        with gate('WEB_ASSET_REQUEST'):
            served = request(path, code='WEB_ASSET')[0]
        with gate('WEB_DISK_ASSET_UNREADABLE'):
            disk = (dist/path.removeprefix('/')).read_bytes()
        require(served == disk, 'WEB_ASSET_DISK_MISMATCH')
        if npm_preview:
            verify_preview_response(path, disk, 'WEB_LOOPBACK_ASSET')
    return disk_build


def verify_preview_response(path, expected, code):
    with gate(code + '_REQUEST'):
        served, _ = request(path, code=code, loopback=True)
    require(served == expected, code + '_DISK_MISMATCH')


def wait_for(check, seconds):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return check()
        except (RuntimeError, OSError, KeyError, ValueError, http.client.HTTPException, subprocess.SubprocessError) as error:
            if time.monotonic() >= deadline:
                code = str(error) if isinstance(error, CheckRejected) else 'ACCEPTANCE_CHECK_FAILED'
                raise CheckRejected('TIMEOUT_' + code) from None
            time.sleep(2)


def plain(path, directory=False, code='PATH_UNSAFE'):
    mode = path.lstat().st_mode
    require(path.resolve() == path and (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)), code)
    return path


def read_material(directory, name, limit, code):
    path = plain(directory/name, code=code + '_PATH_UNSAFE')
    parent = directory.stat()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), code + '_TYPE')
        require(info.st_uid == parent.st_uid, code + '_OWNER')
        require(info.st_nlink == 1, code + '_LINK_COUNT')
        require(stat.S_IMODE(info.st_mode) in (0o400, 0o600), code + '_PERMISSIONS')
        require(0 < info.st_size <= limit, code + '_SIZE')
        data = stream.read(limit+1)
    require(0 < len(data) <= limit, code + '_READ_SIZE')
    return data


def preflight_prop(unit, name, code):
    with gate(code):
        return prop(unit, name)


def verify_unit(unit, kind, subdirectory, *, running=True):
    code = kind + '_UNIT_LOAD'
    require(preflight_prop(unit, 'LoadState', code) == 'loaded', code + '_STATE')
    code = kind + '_UNIT_DAEMON_RELOAD'
    require(preflight_prop(unit, 'NeedDaemonReload', code) == 'no', code + '_PENDING')
    for hook, label in (('ExecCondition', 'EXEC_CONDITION'), ('ExecStartPre', 'EXEC_START_PRE'),
                        ('ExecStartPost', 'EXEC_START_POST'), ('ExecStop', 'EXEC_STOP'),
                        ('ExecStopPost', 'EXEC_STOP_POST')):
        code = kind + '_UNIT_' + label
        require(not preflight_prop(unit, hook, code), code + '_PRESENT')
    start = preflight_prop(unit, 'ExecStart', kind + '_UNIT_EXEC_START')
    executable = re.fullmatch(r'\{ path=([^ ;]+) ; argv\[\]=([^;]+) ;[^{}]*\}', start)
    require(executable is not None, kind + '_UNIT_EXEC_START_FORMAT')
    program = Path(executable[1]).name
    argv = tuple(executable[2].split())
    npm_preview = unit == WEB and executable[1] == WEB_NPM_ARGV[0] and argv == WEB_NPM_ARGV
    if npm_preview:
        verify_preview_settings()
    elif unit == API:
        require('app.main:app' in argv and (program == 'uvicorn'
                or program.startswith('python') and argv[1:3] == ('-m', 'uvicorn')), 'API_UNIT_EXEC_START_UNSUPPORTED')
    else:
        require(program.startswith('python') and argv[1:3] == ('-m', 'http.server')
                or program in ('node', 'vite') and 'preview' in argv, 'WEB_UNIT_EXEC_START_UNSUPPORTED')
    if running:
        with gate(kind + '_UNIT_MAIN_PID'):
            pid = int(prop(unit, 'MainPID'))
            require(pid > 0, kind + '_UNIT_NO_MAIN_PID')
        with gate(kind + '_UNIT_PROCESS_CWD'):
            cwd = Path(os.readlink(f'/proc/{pid}/cwd'))
        allowed = (ROOT/'frontend',) if npm_preview else (ROOT, ROOT/subdirectory, ROOT/'frontend/dist')
        require(cwd in allowed and (unit != API or cwd != ROOT/'frontend/dist'),
                kind + '_UNIT_PROCESS_CWD_MISMATCH')
    return npm_preview


def verify_preview_settings():
    for field, expected, code in (
        ('WorkingDirectory', str(ROOT/'frontend'), 'WEB_NPM_WORKING_DIRECTORY'),
        ('User', WEB_NPM_USER, 'WEB_NPM_USER'),
        ('FragmentPath', WEB_NPM_FRAGMENT, 'WEB_NPM_FRAGMENT'),
        ('KillMode', 'control-group', 'WEB_NPM_KILL_MODE'),
    ):
        require(preflight_prop(WEB, field, code + '_QUERY') == expected, code + '_MISMATCH')
    with gate('WEB_NPM_USER_LOOKUP'):
        require(pwd.getpwnam(WEB_NPM_USER).pw_uid != 0, 'WEB_NPM_USER_ROOT')
    modules = ROOT/'frontend/node_modules'
    entry = modules/'vite/bin/vite.js'
    with gate('WEB_NPM_LOCAL_VITE_UNREADABLE'):
        require((modules/'.bin/vite').resolve(strict=True) == entry and entry.resolve() == entry
                and entry.is_file() and entry.stat().st_mode & 0o111, 'WEB_NPM_LOCAL_VITE_MISMATCH')


def verify_npm_web_unit(*, running=True):
    require(verify_unit(WEB, 'WEB', 'frontend', running=running), 'WEB_NPM_LAYOUT_CHANGED')


def start_panel(npm_preview):
    if npm_preview:
        verify_npm_web_unit(running=False)
    system('start', API, WEB, code='PANEL_START')


def verify_baseline():
    require(os.geteuid() == 0, 'ROOT_REQUIRED')
    with gate('VDS_ADDRESS_QUERY'):
        addresses = json.loads(command('ip', '-j', 'address', capture=True))
        require(isinstance(addresses, list), 'VDS_ADDRESS_RESPONSE')
        address_present = any(a.get('local') == IP for link in addresses for a in link.get('addr_info', []))
    require(address_present, 'VDS_IPV4_NOT_ASSIGNED')
    for path, directory, code in (
        (ROOT, True, 'VDS_ROOT_PATH'), (ROOT/'backend', True, 'BACKEND_PATH'),
        (ROOT/'frontend', True, 'FRONTEND_PATH'), (ROOT/'backend/app', True, 'BACKEND_APP_PATH'),
        (ROOT/'frontend/dist', True, 'FRONTEND_DIST_PATH'), (ROOT/'release.json', False, 'RELEASE_FILE_PATH'),
    ):
        with gate(code + '_UNREADABLE'):
            plain(path, directory=directory, code=code + '_UNSAFE')
    with gate('PUBLISH_FILESYSTEM_QUERY'):
        require(all((ROOT/name).stat().st_dev == ROOT.stat().st_dev for name in PATHS),
                'PUBLISH_FILESYSTEM_MISMATCH')
    with gate('API_DROPIN_PARENT_QUERY'):
        require(DROP.parent.resolve() == DROP.parent, 'API_DROPIN_PARENT_UNSAFE')
    verify_unit(API, 'API', 'backend')
    npm_preview = verify_unit(WEB, 'WEB', 'frontend')
    api_owner = preflight_prop(API, 'User', 'API_UNIT_USER_QUERY')
    require(api_owner and api_owner != USER, 'API_UNIT_USER_REQUIRED')
    with gate('API_UNIT_USER_LOOKUP'):
        require(pwd.getpwnam(api_owner).pw_uid != 0, 'API_UNIT_USER_ROOT')
    for path, code in (
        (OBSERVER_ROOT, 'OBSERVER_ROOT_EXISTS'), (UNIT, 'OBSERVER_UNIT_FILE_EXISTS'),
        (DROP, 'API_SNAPSHOT_DROPIN_EXISTS'), (RUNTIME, 'OBSERVER_RUNTIME_EXISTS'),
        (Path('/etc/systemd/system/multi-user.target.wants')/OBSERVER, 'OBSERVER_ENABLE_LINK_EXISTS'),
    ):
        require(not os.path.lexists(path), code)
    require(preflight_prop(OBSERVER, 'LoadState', 'OBSERVER_UNIT_LOAD_QUERY') == 'not-found', 'OBSERVER_UNIT_ALREADY_DEFINED')
    for lookup, name, code in ((pwd.getpwnam, USER, 'OBSERVER_USER'), (grp.getgrnam, GROUP, 'OBSERVER_GROUP')):
        with gate(code + '_LOOKUP'):
            try:
                lookup(name)
            except KeyError:
                continue
            raise CheckRejected(code + '_EXISTS')
    head = checkout_head()
    return head, health('2.6.13', npm_preview=npm_preview), npm_preview


def archive_source(work):
    repo = work/'source.git'
    env = {'PATH': os.environ['PATH'], 'HOME': str(work), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0'}
    command('git', 'init', '--bare', str(repo), env=env, code='SOURCE_GIT_INIT')
    command('git', '--git-dir', str(repo), 'fetch', '--depth=1', '--no-tags', REPO, NEW, OLD,
            env=env, timeout=180, code='SOURCE_GIT_FETCH')
    pinned = command('git', '--git-dir', str(repo), 'rev-parse', NEW+'^{commit}',
                     env=env, capture=True, code='SOURCE_GIT_PIN')
    require(pinned.strip() == NEW.encode(), 'SOURCE_COMMIT_MISMATCH')
    changed = command('git', '--git-dir', str(repo), 'diff', '--name-only', OLD, NEW, '--',
                      'migrations', 'backend/requirements.txt', env=env, capture=True, code='SOURCE_CONTRACT_DIFF')
    require(not changed, 'SOURCE_SCHEMA_OR_DEPENDENCIES_CHANGED')
    pinned_requirements = command('git', '--git-dir', str(repo), 'show', NEW+':backend/requirements.txt',
                                  env=env, capture=True, code='SOURCE_REQUIREMENTS')
    live_requirements = step('LIVE_REQUIREMENTS_READ', (ROOT/'backend/requirements.txt').read_bytes)
    require(live_requirements == pinned_requirements, 'LIVE_REQUIREMENTS_MISMATCH')
    selected = ('release.json', 'backend/app', 'backend/requirements.txt', 'frontend',
                'deploy/cebeci-observer/api-snapshot.conf', 'deploy/cebeci-observer/'+OBSERVER)
    packed = work/'source.tar'
    command('git', '--git-dir', str(repo), 'archive', '--output', str(packed), NEW, '--', *selected,
            env=env, code='SOURCE_ARCHIVE')
    source = work/'source'
    with gate('SOURCE_EXTRACT'):
        source.mkdir()
        with tarfile.open(packed) as archive:
            require(all(member.isfile() or member.isdir() for member in archive.getmembers()), 'SOURCE_ARCHIVE_MEMBER')
            archive.extractall(source, filter='data')
    with gate('SOURCE_RELEASE_READ'):
        require(json.loads((source/'release.json').read_bytes())['version'] == '2.6.16', 'SOURCE_VERSION_MISMATCH')
    return source


def backup_live():
    backup = Path(step('BACKUP_DIRECTORY', tempfile.mkdtemp, prefix='mikrotik-v2613-before-v2616-', dir='/srv'))
    path = backup/'code-and-dist.tar'
    command('tar', '-cpf', str(path), '-C', str(ROOT), *PATHS, timeout=180, code='BACKUP_TAR_CREATE')
    with gate('BACKUP_DIGEST_WRITE'):
        digest = file_digest(path)
        put(backup/'sha256', (digest+'  code-and-dist.tar\n').encode(), 0o600)
    verify_backup(backup)
    with gate('BACKUP_SYNC'):
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
        parent = os.open(backup, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    print('Yedek doğrulandı:', backup, flush=True)
    return backup


def verify_backup_digest(backup):
    path = backup/'code-and-dist.tar'
    with gate('BACKUP_DIGEST_READ'):
        require(file_digest(path) == (backup/'sha256').read_text().split()[0], 'BACKUP_DIGEST_MISMATCH')
    return path


def verify_backup(backup):
    path = verify_backup_digest(backup)
    command('tar', '-df', str(path), '-C', str(ROOT), timeout=180, code='BACKUP_TAR_COMPARE')


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def owned_tree(path, uid, gid):
    for base, directories, files in os.walk(path):
        for name in [*directories, *files]:
            os.chown(Path(base)/name, uid, gid, follow_symlinks=False)
    os.chown(path, uid, gid)


@contextmanager
def worker_home(prefix, account):
    with tempfile.TemporaryDirectory(prefix=prefix, dir='/tmp') as temporary:
        home = Path(temporary)
        os.chown(home, account.pw_uid, account.pw_gid)
        yield home


def as_observer(home, *args, cwd, code, timeout=60, **variables):
    settings = {'PATH':'/usr/local/bin:/usr/bin:/bin', 'HOME':str(home), 'TMPDIR':str(home), **variables}
    prefix = ('runuser', '-u', USER, '--', 'env', '-i', *(f'{key}={value}' for key, value in settings.items()))
    command(*prefix, *args, cwd=cwd, code=code, timeout=timeout)


def public_code_modes(root):
    """Make installed code traversable without granting write access."""
    root.chmod(0o755)
    for item in root.rglob('*'):
        if not item.is_symlink():
            mode = item.stat().st_mode
            item.chmod(0o755 if item.is_dir() or mode & 0o100 else 0o644)


def build_frontend(source, stage, account):
    with gate('FRONTEND_WORKSPACE'), worker_home('mtv26-build-', account) as build:
        with gate('FRONTEND_SOURCE_COPY'):
            shutil.copytree(source/'frontend', build/'frontend')
            shutil.copy2(source/'release.json', build/'release.json')
        step('FRONTEND_SOURCE_OWNER', owned_tree, build, account.pw_uid, account.pw_gid)
        frontend = build/'frontend'
        as_observer(build, WEB_NPM_ARGV[0], 'ci', '--ignore-scripts', '--no-audit', '--no-fund',
                    cwd=frontend, code='FRONTEND_NPM_CI', timeout=600, V2_BUILD_COMMIT=NEW)
        as_observer(build, WEB_NPM_ARGV[0], 'run', 'build', cwd=frontend, code='FRONTEND_BUILD',
                    timeout=600, V2_BUILD_COMMIT=NEW)
        dist = frontend/'dist'
        with gate('FRONTEND_DIST_VERIFY'):
            require((dist/'release.json').read_bytes() == (source/'release.json').read_bytes(),
                    'FRONTEND_DIST_VERSION_MISMATCH')
            require(NEW.encode() in (dist/'index.html').read_bytes(), 'FRONTEND_DIST_COMMIT_MISMATCH')
            require(dist.resolve() == dist and all(not item.is_symlink() for item in dist.rglob('*')),
                    'FRONTEND_DIST_LINK_REJECTED')
        step('FRONTEND_DIST_STAGE', shutil.copytree, dist, stage/'frontend/dist')
    with gate('FRONTEND_OLD_ASSETS'):
        assets = stage/'frontend/dist/assets'
        for old in (ROOT/'frontend/dist/assets').iterdir():
            require(old.is_file() and not old.is_symlink(), 'FRONTEND_OLD_ASSET_UNSAFE')
            target = assets/old.name
            if target.exists():
                require(file_digest(old) == file_digest(target), 'FRONTEND_ASSET_COLLISION')
            else:
                shutil.copy2(old, target)
    step('FRONTEND_DIST_MODE', public_code_modes, stage/'frontend/dist')


def observer_setup(source, account):
    with gate('OBSERVER_CODE_STAGE'):
        OBSERVER_ROOT.chmod(0o755)
        backend = OBSERVER_ROOT/'backend'
        shutil.copytree(source/'backend', backend)
        # tarfile creates archived directories with the installer's private umask.
        # Normalize this root-owned code tree before the observer opens requirements.
        public_code_modes(backend)
    venv = OBSERVER_ROOT/'venv'
    with gate('OBSERVER_VENV_DIRECTORY'):
        venv.mkdir(mode=0o700)
        os.chown(venv, account.pw_uid, account.pw_gid)
    with gate('OBSERVER_BUILD_WORKSPACE'), worker_home('mtv26-python-', account) as home:
        as_observer(home, '/usr/bin/python3', '-m', 'venv', str(venv),
                    cwd=OBSERVER_ROOT, code='OBSERVER_VENV_CREATE', timeout=180)
        python = str(venv/'bin/python')
        requirements = backend/'requirements.txt'
        as_observer(home, '/usr/bin/test', '-r', str(requirements),
                    cwd=OBSERVER_ROOT, code='OBSERVER_REQUIREMENTS_ACCESS')
        as_observer(home, python, '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
                    '--no-cache-dir', '--only-binary=:all:', '-r', str(requirements),
                    cwd=OBSERVER_ROOT, code='OBSERVER_PIP_INSTALL', timeout=600)
        as_observer(home, python, '-m', 'pip', '--isolated', 'check',
                    cwd=OBSERVER_ROOT, code='OBSERVER_PIP_CHECK')
        with gate('OBSERVER_VENV_FREEZE'):
            owned_tree(venv, 0, 0)
            public_code_modes(venv)
        as_observer(home, python, '-B', '-m', 'app.cebeci_observer', '--help',
                    cwd=OBSERVER_ROOT, code='OBSERVER_RUNTIME_IMPORT', PYTHONPATH=str(backend))


def verify_api_reader_group(group):
    with gate('API_READER_GROUP_PROBE'):
        pid = int(prop(API, 'MainPID'))
        require(pid > 0, 'API_READER_PROCESS_MISSING')
        lines = Path(f'/proc/{pid}/status').read_text().splitlines()
        groups = next((line.split()[1:] for line in lines if line.startswith('Groups:')), [])
        require(str(group) in groups, 'API_READER_GROUP_MISSING')


def verify_observer_material():
    as_observer('/nonexistent', str(OBSERVER_ROOT/'venv/bin/python'), '-B', '-c',
                'from app.adapters.cebeci_observer import make_sampler; make_sampler(managed=True)',
                cwd=OBSERVER_ROOT, code='OBSERVER_MATERIAL_PREFLIGHT',
                PYTHONPATH=str(OBSERVER_ROOT/'backend'))


def put(path, data, mode, owner=0, group=0):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchown(stream.fileno(), owner, group)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


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
    system('is-active', '--quiet', OBSERVER, code='OBSERVER_NOT_ACTIVE')
    with gate('OBSERVATION_API_REQUEST'):
        data, headers = request('/api/v1/device-inventory', cookie=cookie, code='OBSERVATION_API')
    require(next((value for key, value in headers.items() if key.lower() == 'cache-control'), '') == 'no-store',
            'OBSERVATION_CACHE_POLICY')
    with gate('OBSERVATION_PAYLOAD_INVALID'):
        payload = json.loads(data)
        require(payload['source'] == 'ROUTEROS_READ_ONLY' and payload['is_demo'] is False
                and payload['read_only'] is True, 'OBSERVATION_SOURCE_MISMATCH')
        require(len(payload['routers']) == 1, 'OBSERVATION_ROUTER_COUNT')
        row, = payload['routers']
        require(row['id'] == 'device-cebeci-towers' and row['identity'] == 'CEBECI_TOWERS'
                and row['model'] == 'RB3011UiAS' and (row['routeros_version'] or '').removesuffix(' (stable)') == '6.49.19',
                'OBSERVATION_DEVICE_IDENTITY')
        require(row['connection'] == 'ONLINE' and row['freshness'] == 'RECENT' and row['error'] is None,
                'OBSERVATION_HEALTH')
        require(row['accounts_complete'] is True and len(row['accounts']) > 0, 'OBSERVATION_ACCOUNT_COVERAGE')
        require(row['wan_status'] == 'UNKNOWN'
                and all(row[field] is None for field in ('wan_interface','rx_bytes','tx_bytes')), 'OBSERVATION_WAN_SCOPE')
        expiry = datetime.fromisoformat(payload['authorization_expires_at'])
        require(0 < (expiry - datetime.now(timezone.utc)).total_seconds() <= 86400, 'OBSERVATION_APPROVAL_EXPIRY')
        return len(row['accounts'])


def installation_credentials():
    require(sys.stdin.isatty(), 'INSTALL_STDIN_TTY_REQUIRED')
    require(sys.stderr.isatty(), 'INSTALL_STDERR_TTY_REQUIRED')
    with gate('MATERIAL_PATH_INPUT'):
        directory = Path(input('Mevcut V2 gözlemci özel malzeme dizini (mutlak yol): ').strip())
    require(directory.is_absolute(), 'MATERIAL_PATH_NOT_ABSOLUTE')
    require(directory.parts[-3:] == MATERIAL_SUFFIX, 'MATERIAL_PATH_SCOPE')
    with gate('MATERIAL_DIRECTORY_UNREADABLE'):
        plain(directory, directory=True, code='MATERIAL_DIRECTORY_UNSAFE')
        require(stat.S_IMODE(directory.stat().st_mode) == 0o700, 'MATERIAL_DIRECTORY_PERMISSIONS')
    with gate('MATERIAL_CA_READ'):
        ca = read_material(directory, 'ca.pem', 262144, 'MATERIAL_CA')
    with gate('MATERIAL_PASSWORD_READ'):
        password = read_material(directory, 'password', 1024, 'MATERIAL_PASSWORD')
    require(all(char not in password for char in (b'\r', b'\n', b'\0')), 'MATERIAL_PASSWORD_FORMAT')
    with gate('MATERIAL_PASSWORD_ENCODING'):
        password.decode('utf-8')
    with gate('MATERIAL_CA_INVALID'):
        ssl.create_default_context(cadata=ca.decode())
    with gate('ADMIN_CREDENTIAL_INPUT'):
        username = input('Mevcut V2 merkezi yönetici adı: ').strip()
        admin_password = getpass.getpass('V2 yönetici parolası: ')
    require(username and admin_password, 'ADMIN_CREDENTIALS_MISSING')
    credentials = (username, admin_password)
    login(credentials)
    return {'ca.pem':ca, 'password':password}, credentials


def preflight_only():
    """Report without opening the install lock, prompting, or logging in."""
    try:
        head, baseline_build, _ = verify_baseline()
        tree_relation = head_matches_api(head, baseline_build)
    except CheckRejected as error:
        print('BLOCKED —', error, file=sys.stderr)
        return 1
    except Exception:
        print('BLOCKED — PREFLIGHT_UNEXPECTED', file=sys.stderr)
        return 1
    relation = ('GIT_HEAD_ABSENT' if head is None else 'GIT_HEAD_BASELINE' if head == OLD else
                'GIT_HEAD_TARGET' if head == NEW else 'GIT_HEAD_OTHER')
    print('PASS — PREFLIGHT_READ_ONLY ·', relation, '·', tree_relation)
    print('DEFERRED — PRIVATE_MATERIAL, ADMIN_LOGIN, SOURCE_FETCH, DEVICE_ACCEPTANCE')
    return 0


def identity(path):
    info = path.lstat()
    return info.st_dev, info.st_ino


def restore_swaps(staged, switched):
    for name, before, after in switched:
        require(identity(ROOT/name) == after and identity(staged/name) == before, 'ROLLBACK_TARGET_DRIFT')
    for name, _, _ in reversed(switched):
        exchange(ROOT/name, staged/name)


def stop_observer():
    system('stop', OBSERVER, code='ROLLBACK_OBSERVER_STOP_UNIT')
    system('disable', OBSERVER, code='ROLLBACK_OBSERVER_DISABLE_UNIT')


def rollback(backup, staged, switched, undo, stopped, observer_attempted, baseline_build, initial_head,
             *, npm_preview=False):
    def recover(code, action):
        try:
            action()
            return True
        except Exception as error:
            print('FAIL —', error if isinstance(error, CheckRejected) else code, file=sys.stderr)
            return False

    observer_stopped = not observer_attempted or recover('ROLLBACK_OBSERVER_STOP', stop_observer)
    app_stopped = not stopped or recover('ROLLBACK_PANEL_STOP', lambda: system('stop', WEB, API))
    ready = observer_stopped and app_stopped
    if stopped and ready:
        ready = (recover('ROLLBACK_BACKUP_DIGEST', lambda: verify_backup_digest(backup))
                 and recover('ROLLBACK_FILE_EXCHANGE', lambda: restore_swaps(staged, switched)))
    if observer_stopped:
        for code, action in reversed(undo):
            if not recover(code, action):
                ready = False
    if undo or stopped:
        if not recover('ROLLBACK_DAEMON_RELOAD', lambda: system('daemon-reload')):
            ready = False
    if stopped and ready:
        ready = (recover('ROLLBACK_BACKUP_COMPARE', lambda: verify_backup(backup))
                 and recover('ROLLBACK_PANEL_START', lambda: start_panel(npm_preview))
                 and recover('ROLLBACK_BASELINE_HEALTH',
                             lambda: wait_for(lambda: health('2.6.13', expected_build=baseline_build, npm_preview=npm_preview), 60)))
    if stopped and ready:
        try:
            require(checkout_head() == initial_head, 'ROLLBACK_GIT_HEAD_CHANGED_EXTERNALLY')
        except CheckRejected as error:
            print('NOTICE —', error, file=sys.stderr)
    return ready


def interrupted(_sig, _frame):
    raise CheckRejected('INTERRUPTED')


def run():
    stage_name = 'ön kontrol'
    staged = None
    backup = None
    switched = []
    undo = []
    stopped = False
    observer_attempted = npm_preview = False
    initial_head = baseline_build = None
    stage_dir = None
    os.umask(0o077)
    try:
        require(os.geteuid() == 0, 'ROOT_REQUIRED')
        with gate('INSTALL_LOCK_OPEN'):
            fd = os.open('/run/mikrotik-v2616-cebeci-deploy.lock',
                         os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'wb') as lock:
            info = os.fstat(lock.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1, 'INSTALL_LOCK_UNSAFE')
            with gate('INSTALL_LOCK_BUSY'):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                initial_head, baseline_build, npm_preview = verify_baseline()
                stage_name = 'özel malzeme ve yönetici ön kontrolü'
                material, credentials = installation_credentials()

                stage_name = 'kaynak ve doğrulanmış yedek'
                with gate('PUBLISH_STAGE_DIRECTORY'):
                    stage_dir = Path(tempfile.mkdtemp(prefix='.v2616-stage-', dir=ROOT))
                    staged = stage_dir/'publish'
                    (staged/'backend').mkdir(parents=True)
                    (staged/'frontend').mkdir()
                source = archive_source(stage_dir)
                backup = backup_live()
                rollback_record = dict(baseline_version='2.6.13', baseline_api_build_id=baseline_build,
                                       checkout_head=initial_head, stage_directory=str(stage_dir), paths=PATHS)
                step('BACKUP_ROLLBACK_RECEIPT', put, backup/'rollback-proof.json',
                     json.dumps(rollback_record).encode(), 0o600)

                stage_name = 'izole gözlemci ve frontend hazırlığı'
                command('groupadd', '--system', GROUP, code='OBSERVER_GROUP_CREATE')
                undo.append(('ROLLBACK_GROUP_REMOVE', lambda: command('groupdel', GROUP, code='ROLLBACK_GROUP_REMOVE')))
                command('useradd', '--system', '--gid', GROUP, '--no-create-home', '--home-dir',
                        '/nonexistent', '--shell', '/usr/sbin/nologin', USER, code='OBSERVER_USER_CREATE')
                undo.append(('ROLLBACK_USER_REMOVE', lambda: command('userdel', USER, code='ROLLBACK_USER_REMOVE')))
                step('OBSERVER_ROOT_CREATE', OBSERVER_ROOT.mkdir, mode=0o755)
                undo.append(('ROLLBACK_OBSERVER_ROOT_REMOVE', lambda: shutil.rmtree(OBSERVER_ROOT)))
                account = step('OBSERVER_USER_LOOKUP', pwd.getpwnam, USER)
                require(account.pw_uid != 0 and account.pw_gid != 0, 'OBSERVER_ACCOUNT_PRIVILEGED')
                group = step('OBSERVER_GROUP_LOOKUP', grp.getgrnam, GROUP)
                require(account.pw_gid == group.gr_gid, 'OBSERVER_ACCOUNT_GROUP_MISMATCH')
                observer_setup(source, account)
                print('OK — OBSERVER_RUNTIME_READY', flush=True)
                target_build = step('SOURCE_API_BUILD_HASH', build_id, source)
                build_frontend(source, staged, account)
                print('OK — FRONTEND_DIST_READY', flush=True)
                with gate('API_CODE_STAGE'):
                    shutil.copytree(source/'backend/app', staged/'backend/app')
                    public_code_modes(staged/'backend/app')
                with gate('RELEASE_FILE_STAGE'):
                    shutil.copy2(source/'release.json', staged/'release.json')
                    (staged/'release.json').chmod(0o644)
                with gate('OBSERVER_UNIT_INSTALL'):
                    put(UNIT, (source/'deploy/cebeci-observer'/OBSERVER).read_bytes(), 0o644)
                undo.append(('ROLLBACK_OBSERVER_UNIT_REMOVE', UNIT.unlink))
                command('systemd-analyze', 'verify', str(UNIT), code='OBSERVER_SYSTEMD_VERIFY')
                with gate('API_DROPIN_DIRECTORY'):
                    require(DROP.parent.resolve() == DROP.parent, 'API_DROPIN_PARENT_UNSAFE')
                    if not DROP.parent.exists():
                        DROP.parent.mkdir(mode=0o700)
                        undo.append(('ROLLBACK_API_DROPIN_DIRECTORY_REMOVE', DROP.parent.rmdir))
                        DROP.parent.chmod(0o755)
                with gate('API_DROPIN_INSTALL'):
                    put(DROP, (source/'deploy/cebeci-observer/api-snapshot.conf').read_bytes(), 0o644)
                undo.append(('ROLLBACK_API_DROPIN_REMOVE', DROP.unlink))
                api_fragment = preflight_prop(API, 'FragmentPath', 'API_UNIT_FRAGMENT_QUERY')
                require(api_fragment.startswith('/') and api_fragment.endswith('/' + API), 'API_UNIT_FRAGMENT_UNSAFE')
                command('systemd-analyze', 'verify', api_fragment, code='API_SYSTEMD_VERIFY')
                system('daemon-reload', code='PUBLISH_DAEMON_RELOAD')
                step('OBSERVER_APPROVAL_INSTALL', approval, account, material)
                verify_observer_material()
                print('OK — UNIT_AND_MATERIAL_READY', flush=True)

                stage_name = 'V2.6.16 yayın geçişi'
                verify_backup(backup)
                require(checkout_head() == initial_head, 'GIT_HEAD_CHANGED_BEFORE_SWITCH')
                require(step('STAGED_API_BUILD_HASH', build_id, staged) == target_build, 'STAGED_PINNED_BUILD_MISMATCH')
                if npm_preview:
                    verify_npm_web_unit()
                stopped = True
                system('stop', WEB, API, code='PANEL_STOP')
                for name, code in zip(PATHS, ('PUBLISH_API_EXCHANGE', 'PUBLISH_FRONTEND_EXCHANGE', 'PUBLISH_RELEASE_EXCHANGE')):
                    with gate(code):
                        mask = signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGINT, signal.SIGTERM, signal.SIGHUP))
                        try:
                            before, after = identity(ROOT/name), identity(staged/name)
                            exchange(ROOT/name, staged/name)
                            switched.append((name, before, after))
                        finally:
                            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                start_panel(npm_preview)
                wait_for(lambda: health('2.6.16', NEW, target_build, npm_preview=npm_preview), 60)
                stage_name = '24 saatlik pilot ve gerçek cihaz kabulü'
                verify_api_reader_group(group.gr_gid)
                observer_attempted = True
                system('enable', '--now', OBSERVER, code='OBSERVER_ENABLE_START')
                with gate('OBSERVATION_ANONYMOUS_REQUEST'):
                    request('/api/v1/device-inventory', status=401, code='OBSERVATION_ANONYMOUS')
                cookie = login(credentials)
                count = wait_for(lambda: accept(cookie), 95)
                final_head = checkout_head()
                require(final_head == initial_head, 'GIT_HEAD_CHANGED_DURING_SWITCH')
                receipt = dict(source_commit=NEW, app_version='2.6.16', api_build_id=target_build,
                               frontend_index_sha256=step('RELEASE_FRONTEND_INDEX_HASH', file_digest,
                                                          ROOT/'frontend/dist/index.html'),
                               checkout_head_before=initial_head, checkout_head_after=final_head,
                               rollback_app_version='2.6.13', rollback_api_build_id=baseline_build)
                step('RELEASE_RECEIPT_WRITE', put, backup/'release-proof.json', json.dumps(receipt).encode(), 0o600)
                print(f'PASS — V2.6.16 {NEW} · CEBECI_TOWERS ONLINE · {count} hesap · WAN bilinmiyor')
                return 0

            except Exception as error:
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                    signal.signal(sig, signal.SIG_IGN)
                code = str(error) if isinstance(error, CheckRejected) else 'UNEXPECTED_INSTALLER_ERROR'
                print('FAIL —', stage_name, '·', code, file=sys.stderr)
                if not rollback(backup, staged, switched, undo, stopped, observer_attempted,
                                baseline_build, initial_head, npm_preview=npm_preview):
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
    except Exception as error:
        code = str(error) if isinstance(error, CheckRejected) else 'INSTALL_SETUP_FAILED'
        print('BLOCKED —', code, file=sys.stderr)
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only', action='store_true', help='run read-only host and HTTPS checks')
    args = parser.parse_args()
    for caught in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(caught, interrupted)
    raise SystemExit(preflight_only() if args.preflight_only else run())
