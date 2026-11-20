#!/usr/bin/env python3
"""Compare the pinned standalone and systemd observer paths without deploying."""
import argparse
import configparser
from datetime import datetime, timedelta, timezone
import errno
import importlib
import io
import json
import logging
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace

PINS = {'standalone':'da7ef62b6e29703772bb0276f7b8b6cb11a894ac',
        'managed':'433e2ba99a7f4a24ba904b14db98b57f30709f9e'}
UNIT_FILE = 'deploy/cebeci-observer/mikrotik-v2-cebeci-observer.service'
MATERIAL_PATH = Path('.local/cebeci-pilot/v2614-observer')
STEPS = ('RUNTIME', 'AUTHORIZATION', 'SOURCE_BIND', 'TCP', 'SOURCE_PEER', 'TLS', 'LOGIN', 'IDENTITY', 'SNAPSHOT')
CAUSES = {'CONNECTION_UNREACHABLE', 'CONNECTION_TIMEOUT', 'DEADLINE_EXCEEDED', 'CA_CERTIFICATE_REJECTED',
          'TLS_POLICY_REJECTED', 'TLS_VERIFICATION_FAILED', 'CERTIFICATE_PIN_MISMATCH', 'CERTIFICATE_SAN_MISMATCH',
          'ENDPOINT_OR_SOURCE_MISMATCH', 'API_SSL_STOP', 'DEVICE_READ_REJECTED', 'INVALID_TEXT',
          'ROW_LIMIT', 'SENTENCE_LIMIT', 'RESPONSE_BYTE_LIMIT', 'UNEXPECTED_RESPONSE_FIELD',
          'MISSING_RESPONSE_FIELD', 'FIELD_VALUE_LIMIT', 'SENSITIVE_METADATA_REJECTED'}
SECURITY = ('NoNewPrivileges', 'CapabilityBoundingSet', 'ProtectSystem', 'ProtectHome', 'PrivateTmp',
            'PrivateDevices', 'ProtectKernelTunables', 'ProtectKernelModules', 'ProtectControlGroups',
            'RestrictAddressFamilies', 'IPAddressDeny', 'IPAddressAllow', 'LimitCORE', 'UMask',
            'RuntimeDirectoryMode', 'RuntimeDirectoryPreserve', 'TimeoutStopSec')


IMPORTS = (
    ('PYDANTIC_CORE', 'pydantic_core._pydantic_core', 'packages'),
    ('PYDANTIC', 'pydantic', 'packages'),
    ('FASTAPI', 'fastapi', 'packages'),
    ('OBSERVER', 'app.adapters.cebeci_observer', 'source'),
    ('TRANSPORT', 'app.adapters.router_api_ssl', 'source'),
    ('WIRE', 'app.adapters.cebeci_api_ssl', 'source'),
    ('COLLECTOR', 'app.adapters.device_inventory', 'source'),
    ('SNAPSHOT_SCHEMA', 'app.schemas.device_inventory', 'source'),
    ('SNAPSHOT_WRITER', 'app.services.device_poller', 'source'),
)
KNOWN_MODULES = {
    'app': 'APP', 'pydantic_core': 'PYDANTIC_CORE', 'pydantic': 'PYDANTIC', 'fastapi': 'FASTAPI',
    'starlette': 'STARLETTE', 'anyio': 'ANYIO', 'typing_extensions': 'TYPING_EXTENSIONS',
    'typing_inspection': 'TYPING_INSPECTION', 'annotated_types': 'ANNOTATED_TYPES',
    'annotated_doc': 'ANNOTATED_DOC', 'typing': 'TYPING_STDLIB', '_ssl': 'SSL_STDLIB',
}
IMPORT_FAILURES = {'MODULE_MISSING', 'NATIVE_MAP_DENIED', 'NATIVE_ABI_MISMATCH', 'NATIVE_LIBRARY_MISSING',
                   'NATIVE_INIT_FAILED', 'IMPORT_SYMBOL_MISSING', 'IMPORT_ERROR', 'ACCESS_DENIED', 'PATH_MISSING',
                   'IO_ERROR', 'MODULE_INIT_FAILED', 'ORIGIN_REJECTED'}


class Stop(RuntimeError):
    pass


def need(condition, code):
    if not condition:
        raise Stop(code)


def command(*args, timeout=20, cwd=None):
    with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True, cwd=cwd) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def emit(step, status):
    print(f'{step}={status}', flush=True)


def import_failure(error):
    if isinstance(error, ModuleNotFoundError):
        return 'MODULE_MISSING', KNOWN_MODULES.get((error.name or '').partition('.')[0])
    if isinstance(error, ImportError):
        # Native loader messages are classified locally and never printed.
        detail = str(error).lower()
        if 'failed to map segment' in detail or 'cannot map' in detail:
            return 'NATIVE_MAP_DENIED', None
        if any(marker in detail for marker in ('wrong elf class', 'invalid elf', 'undefined symbol', 'glibc_')):
            return 'NATIVE_ABI_MISMATCH', None
        if 'cannot open shared object file' in detail:
            return 'NATIVE_LIBRARY_MISSING', None
        if 'module export function' in detail:
            return 'NATIVE_INIT_FAILED', None
        if 'cannot import name' in detail:
            return 'IMPORT_SYMBOL_MISSING', None
        return 'IMPORT_ERROR', None
    if isinstance(error, PermissionError):
        return 'ACCESS_DENIED', None
    if isinstance(error, FileNotFoundError):
        return 'PATH_MISSING', None
    if isinstance(error, OSError):
        return 'IO_ERROR', None
    return 'MODULE_INIT_FAILED', None


def load_runtime(root, packages):
    source = root/'backend'
    need(sys.flags.isolated and sys.flags.no_site, 'PYTHON_ISOLATION_REQUIRED')
    need(Path.cwd() == root, 'WORKING_DIRECTORY_MISMATCH')
    for directory, code in ((source, 'SOURCE_DIRECTORY_ACCESS'), (packages, 'PACKAGE_DIRECTORY_ACCESS')):
        try:
            with os.scandir(directory) as entries:
                next(entries, None)
            need(os.access(directory, os.X_OK), code)
        except OSError:
            raise Stop(code) from None
    try:
        with (source/'app/adapters/cebeci_observer.py').open('rb') as stream:
            stream.read(1)
    except OSError:
        raise Stop('SOURCE_MODULE_ACCESS') from None
    need(not os.statvfs(packages).f_flag & os.ST_NOEXEC, 'PACKAGE_FILESYSTEM_NOEXEC')
    sys.path[:0] = [str(source), str(packages)]
    loaded = {}
    for label, module_name, location in IMPORTS:
        try:
            module = importlib.import_module(module_name)
            allowed = source if location == 'source' else packages
            origin = getattr(module, '__file__', None)
            need(origin and Path(origin).resolve().is_relative_to(allowed), 'ORIGIN_REJECTED')
            loaded[label] = module
        except Stop:
            print(f'IMPORT={label}:ORIGIN_REJECTED', flush=True)
            raise Stop('IMPORT_FAILED') from None
        except Exception as error:
            reason, missing = import_failure(error)
            suffix = ':' + missing if missing else ''
            print(f'IMPORT={label}:{reason}{suffix}', flush=True)
            raise Stop('IMPORT_FAILED') from None
    return loaded


def worker(root, packages, mode, runtime):
    logging.disable(logging.CRITICAL)
    try:
        loaded = load_runtime(root, packages)
    except Stop as error:
        emit('RUNTIME', str(error))
        return 1
    observer, transport = loaded['OBSERVER'], loaded['TRANSPORT']
    ApiSslStop, _Wire = loaded['WIRE'].ApiSslStop, loaded['WIRE']._Wire
    DeviceReadWire = loaded['COLLECTOR'].DeviceReadWire
    DeviceInventory = loaded['SNAPSHOT_SCHEMA'].DeviceInventory
    _publish = loaded['SNAPSHOT_WRITER']._publish

    emit('RUNTIME', 'PASS')
    current = 'AUTHORIZATION'
    identity_failure = None

    def advance(stage):
        nonlocal current
        current = stage

    class ProbeSocket(socket.socket):
        def bind(self, address):
            advance('SOURCE_BIND')
            try:
                super().bind(address)
            except OSError as error:
                if error.errno == errno.EADDRNOTAVAIL:
                    emit('SOURCE_BIND', 'ADDRESS_NOT_AVAILABLE')
                elif error.errno in (errno.EACCES, errno.EPERM):
                    emit('SOURCE_BIND', 'PERMISSION')
                raise
            emit('SOURCE_BIND', 'PASS')

        def connect(self, address):
            advance('TCP')
            try:
                super().connect(address)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EPERM):
                    emit('TCP', 'PERMISSION')
                raise
            emit('TCP', 'PASS')

    class ProbeTLS:
        def __init__(self, context):
            self.context = context

        def __getattr__(self, key):
            return getattr(self.context, key)

        def wrap_socket(self, raw, **kwargs):
            advance('TLS')
            return self.context.wrap_socket(raw, **kwargs)

    def new_socket(*args, **kwargs):
        advance('SOURCE_BIND')
        return ProbeSocket(*args, **kwargs)

    transport.socket = SimpleNamespace(socket=new_socket, AF_INET=socket.AF_INET, SOCK_STREAM=socket.SOCK_STREAM)
    original_context = transport.verified_tls_context
    transport.verified_tls_context = lambda *args: ProbeTLS(original_context(*args))
    original_login = _Wire.login
    original_read = DeviceReadWire.fixed_read
    original_transport = transport.RouterApiSslClient._verified_read

    def login(wire, **kwargs):
        # The real transport checks peer/source, TLS, IP SAN and leaf pin before invoking login.
        emit('SOURCE_PEER', 'PASS')
        emit('TLS', 'PASS')
        advance('LOGIN')
        result = original_login(wire, **kwargs)
        emit('LOGIN', 'PASS')
        advance('IDENTITY')
        return result

    def read_step(wire, menu):
        nonlocal identity_failure
        if menu in ('/ppp/secret', '/ppp/active') and current == 'IDENTITY':
            emit('IDENTITY', 'PASS')
            advance('SNAPSHOT')
        result = original_read(wire, menu)
        if menu in ('/system/identity', '/system/resource') and len(result) != 1:
            identity_failure = 'ROW_COUNT_MISMATCH'
        elif menu == '/system/identity' and result[0].get('name') != observer.IDENTITY:
            identity_failure = 'NAME_MISMATCH'
        elif menu == '/system/resource' and identity_failure is None:
            if result[0].get('board-name') != observer.MODEL:
                identity_failure = 'MODEL_MISMATCH'
            elif (result[0].get('version') or '').removesuffix(' (stable)') != observer.VERSION:
                identity_failure = 'VERSION_MISMATCH'
        return result

    def capture_error(client, *args):
        try:
            return original_transport(client, *args)
        except ApiSslStop as error:
            code = str(error).partition(':')[0]
            category = code if code in CAUSES else ('AUTHENTICATION_REJECTED' if code.startswith('AUTHENTICATION')
                                                     else 'REJECTED')
            if code == 'ENDPOINT_OR_SOURCE_MISMATCH':
                advance('SOURCE_PEER')
            if current == 'IDENTITY' and code == 'DEVICE_READ_REJECTED' and identity_failure:
                category = identity_failure
            emit(current, category)
            raise

    _Wire.login = login
    DeviceReadWire.fixed_read = read_step
    transport.RouterApiSslClient._verified_read = capture_error
    try:
        expiry = observer.managed_expiry() if mode == 'managed' else None
        sample = observer.make_sampler(managed=True) if mode == 'managed' else observer.make_sampler()
        emit('AUTHORIZATION', 'PASS')
        advance('TLS')
        result = sample(previous=None)
        advance('SNAPSHOT')
        output = runtime if mode == 'managed' else root/MATERIAL_PATH
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            directory = os.fstat(fd)
            need(stat.S_IMODE(directory.st_mode) == (0o750 if mode == 'managed' else 0o700)
                 and directory.st_uid == os.geteuid() and directory.st_gid == os.getegid(),
                 'DIRECTORY_METADATA')
            if mode == 'managed':
                expiry = min(expiry, observer.managed_expiry())
                _publish(fd, result, expiry)
            else:
                _publish(fd, result)
        finally:
            os.close(fd)
        path = output/'device-inventory.json'
        info = path.stat()
        expected_mode = 0o640 if mode == 'managed' else 0o600
        need(stat.S_IMODE(info.st_mode) == expected_mode and info.st_uid == os.geteuid()
             and info.st_gid == os.getegid() and info.st_nlink == 1, 'FILE_METADATA')
        snapshot = DeviceInventory.model_validate_json(path.read_bytes())
        need(len(snapshot.routers) == 1 and snapshot.routers[0] == result, 'PAYLOAD_MISMATCH')
        emit('SNAPSHOT', result.error or 'PASS')
        if result.connection == 'ONLINE' and result.error is None:
            emit('ACCOUNTS', f'{len(result.accounts or [])},COMPLETE={str(result.accounts_complete).upper()}')
            return 0
    except Stop as error:
        emit(current, str(error))
    except (OSError, ValueError, ApiSslStop):
        emit(current, 'LOCAL_OR_VALIDATION_FAILURE')
    return 1


def pinned_sources(repo, workspace):
    unit = None
    for mode, pin in PINS.items():
        args = ('backend/app', UNIT_FILE) if mode == 'managed' else ('backend/app',)
        archive = command('git', '-c', 'safe.directory='+str(repo), '-C', str(repo), 'archive', pin,
                          '--', *args)
        need(archive.returncode == 0, f'{mode.upper()}_PIN_UNAVAILABLE')
        root = workspace/mode
        root.mkdir(mode=0o755)
        root.chmod(0o755)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as payload:
            need(all(member.isfile() or member.isdir() for member in payload), 'SOURCE_ARCHIVE_UNSAFE')
            payload.extractall(root, filter='data')
        for path in (root/'backend').rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o644)
        (root/'backend').chmod(0o755)
        if mode == 'managed':
            unit = configparser.ConfigParser(interpolation=None)
            unit.read(root/UNIT_FILE)
    need(unit is not None and all(key in unit['Service'] for key in SECURITY), 'MANAGED_POLICY_UNAVAILABLE')
    return unit['Service']


def read_existing(path, uid, limit):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and info.st_nlink == 1
             and stat.S_IMODE(info.st_mode) in (0o400, 0o600) and 0 < info.st_size <= limit,
             'PRIVATE_MATERIAL_REJECTED')
        data = stream.read(limit+1)
    need(0 < len(data) <= limit, 'PRIVATE_MATERIAL_REJECTED')
    return data


def stage_material(root, account, material):
    directory = root
    for part in MATERIAL_PATH.parts:
        directory /= part
        directory.mkdir(mode=0o700)
        os.chown(directory, account.pw_uid, account.pw_gid)
    approval = dict(scope='V2614_CEBECI_TOWERS_READ_ONLY',
                    expires_at=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
    for name, data in (*material.items(), ('approval.json', json.dumps(approval).encode())):
        with (directory/name).open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), account.pw_uid, account.pw_gid)
            stream.write(data)


def report(mode, result):
    passed = set()
    safe = CAUSES | {'PASS', 'ADDRESS_NOT_AVAILABLE', 'PERMISSION', 'AUTHENTICATION_REJECTED', 'REJECTED',
                     'ROW_COUNT_MISMATCH', 'NAME_MISMATCH', 'MODEL_MISMATCH', 'VERSION_MISMATCH',
                     'DIRECTORY_METADATA', 'FILE_METADATA', 'PAYLOAD_MISMATCH', 'LOCAL_OR_VALIDATION_FAILURE',
                     'IMPORT_FAILED', 'RUNTIME_IO_FAILURE', 'PYTHON_ISOLATION_REQUIRED', 'WORKING_DIRECTORY_MISMATCH',
                     'SOURCE_DIRECTORY_ACCESS', 'PACKAGE_DIRECTORY_ACCESS', 'SOURCE_MODULE_ACCESS',
                     'PACKAGE_FILESYSTEM_NOEXEC',
                     'UNREACHABLE', 'TIMEOUT', 'TLS', 'AUTHORIZATION', 'INVALID_DATA'}
    import_labels = {label for label, _, _ in IMPORTS}
    for line in result.stdout.decode(errors='replace').splitlines():
        stage, _, value = line.partition('=')
        if stage == 'IMPORT':
            check, _, failure = value.partition(':')
            reason, _, module = failure.partition(':')
            if check in import_labels and reason in IMPORT_FAILURES and (not module or module in KNOWN_MODULES.values()):
                print(f'{mode.upper()} {line}')
        if stage in STEPS and value in safe or re.fullmatch(r'ACCOUNTS=[0-9]{1,3},COMPLETE=(?:TRUE|FALSE)', line):
            print(f'{mode.upper()} {line}')
            passed.add(stage)
    for stage in STEPS:
        if stage not in passed:
            print(f'{mode.upper()} {stage}=NOT_REACHED')
    if result.returncode:
        print(f'{mode.upper()} EXIT={result.returncode}')


def launch(args):
    need(os.geteuid() == 0, 'ROOT_REQUIRED')
    # Reject an active production observer, so this only runs after rollback.
    active = command('systemctl', 'is-active', 'mikrotik-v2-cebeci-observer.service')
    need(active.returncode in (3, 4) and active.stdout.strip() in (b'inactive', b'failed', b'unknown'),
         'LIVE_OBSERVER_STATE_UNSAFE')
    repo = Path(args.repo).resolve(strict=True)
    private = Path(args.material)
    need(private.is_absolute() and private.resolve(strict=True) == private and
         private.parts[-3:] == MATERIAL_PATH.parts, 'MATERIAL_DIRECTORY_REJECTED')
    info = private.stat()
    need(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid != 0,
         'MATERIAL_DIRECTORY_REJECTED')
    account = pwd.getpwuid(info.st_uid)
    need(account.pw_gid != 0, 'OBSERVER_GROUP_REJECTED')
    material = {name:read_existing(private/name, account.pw_uid, limit)
                for name, limit in (('ca.pem', 262144), ('password', 1024))}
    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    packages = Path(args.venv).resolve(strict=True)/'lib'/version/'site-packages'
    need(packages.is_dir(), 'VENV_PYTHON_ABI_OR_PACKAGES_MISSING')
    original_mount = 'NOEXEC' if os.statvfs('/run').f_flag & os.ST_NOEXEC else 'EXEC_ALLOWED'
    print(f'ORIGINAL_RUN_MOUNT={original_mount}')
    os.umask(0o077)
    status = []
    with tempfile.TemporaryDirectory(prefix='mtv2-cebeci-diag-', dir='/opt') as directory:
        workspace = Path(directory)
        workspace.chmod(0o755)
        props = pinned_sources(repo, workspace)
        # Copy dependencies only. Keep paths outside ProtectHome and avoid running pip.
        target = workspace/'packages'
        need(not any(path.is_symlink() for path in packages.rglob('*')), 'VENV_PACKAGE_LINK_REJECTED')
        shutil.copytree(packages, target, ignore=shutil.ignore_patterns('__pycache__', '*.pth'))
        for path in target.rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o644)
        target.chmod(0o755)
        launcher = workspace/'probe.py'
        shutil.copyfile(Path(__file__), launcher)
        launcher.chmod(0o644)
        unit = workspace.name + '.service'
        runtime = Path('/run')/(workspace.name+'-snapshot')
        for mode in PINS:
            stage_material(workspace/mode, account, material)
        del material
        need(not os.path.lexists(runtime), 'DIAGNOSTIC_RUNTIME_EXISTS')
        for mode in PINS:
            root = workspace/mode
            worker_args = ('/usr/bin/python3', '-I', '-S', '-B', str(launcher), '--worker', str(root),
                           str(target), mode, str(runtime))
            if mode == 'standalone':
                try:
                    result = command('runuser', '-u', account.pw_name, '--', 'env', '-i',
                                     'PATH=/usr/bin:/bin', *worker_args, timeout=25, cwd=root)
                except subprocess.TimeoutExpired:
                    result = subprocess.CompletedProcess(worker_args, 124, b'', b'')
            else:
                options = [f'--property={key}={props[key]}' for key in SECURITY]
                try:
                    result = command('systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                                     f'--unit={unit}', f'--uid={account.pw_uid}', f'--gid={account.pw_gid}',
                                     f'--working-directory={root}', f'--property=RuntimeDirectory={runtime.name}',
                                     '--property=RuntimeMaxSec=30s', *options, *worker_args, timeout=45)
                except subprocess.TimeoutExpired:
                    result = subprocess.CompletedProcess(worker_args, 124, b'', b'')
                finally:
                    command('systemctl', 'stop', unit)
                    need(not os.path.lexists(runtime), 'DIAGNOSTIC_RUNTIME_CLEANUP_UNVERIFIED')
            report(mode, result)
            status.append(result.returncode)
    return int(any(status))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='/srv/mikrotik-v26-next')
    parser.add_argument('--material')
    parser.add_argument('--venv')
    parser.add_argument('--worker', nargs=4, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        root, packages, mode, runtime = args.worker
        try:
            return worker(Path(root), Path(packages), mode, Path(runtime))
        except OSError:
            emit('RUNTIME', 'RUNTIME_IO_FAILURE')
            return 1
    try:
        need(args.material and args.venv, 'MATERIAL_AND_VENV_REQUIRED')
        return launch(args)
    except Stop as error:
        print(f'DIAGNOSTIC={error}', file=sys.stderr)
    except (OSError, KeyError, ValueError, subprocess.SubprocessError):
        print('DIAGNOSTIC=LOCAL_EXECUTION_FAILED', file=sys.stderr)
    return 1


if __name__ == '__main__':
    for sig in (signal.SIGINT, signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(Stop('INTERRUPTED')))
    raise SystemExit(main())
