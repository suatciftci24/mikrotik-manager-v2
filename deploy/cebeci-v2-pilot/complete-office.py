#!/usr/bin/env python3
"""Run on the office machine. Never print subprocess errors or secret values."""
import json
import errno
import os
import re
from pathlib import Path
import stat
import socket
import subprocess
import sys
import tempfile
import time
import shlex
from urllib.parse import urlsplit, unquote

ROOT = Path('/home/suatpc/Codex-Projects/mikrotik-manager-v2')
PACKAGE = ROOT / 'deploy/cebeci-v2-pilot'
SSH = ['ssh', '-i', '/home/suatpc/.ssh/mikrotik_manager_ed25519', '-o', 'IdentitiesOnly=yes',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
HOST = 'mikadmin@185.139.5.51'
STEP = 'preflight'


class SafeFailure(RuntimeError):
    """Only a locally chosen constant may reach the terminal."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def classify_psql(result):
    # Inspect in memory only. Never return raw stderr, SQL, paths or server values.
    error = result.stderr.lower()
    patterns = (
        (b'operation not permitted', 'V2_EXPORT_SOCKET_EPERM'),
        (b'permission denied to create socket', 'V2_EXPORT_SOCKET_DENIED'),
        (b'connection refused', 'V2_EXPORT_CONNECTION_REFUSED'),
        (b'timeout expired', 'V2_EXPORT_CONNECTION_TIMEOUT'),
        (b'canceling statement due to statement timeout', 'V2_EXPORT_QUERY_TIMEOUT'),
        (b'canceling statement due to lock timeout', 'V2_EXPORT_LOCK_TIMEOUT'),
        (b'password authentication failed', 'V2_EXPORT_DB_AUTH_FAILED'),
        (b'no password supplied', 'V2_EXPORT_PGPASS_NO_MATCH'),
        (b'no pg_hba.conf entry', 'V2_EXPORT_HBA_REJECTED'),
        (b'permission denied to examine', 'V2_EXPORT_CLUSTER_INSPECTION_DENIED'),
        (b'permission denied for', 'V2_EXPORT_DB_PRIVILEGE_DENIED'),
        (b'query returned no rows', 'V2_EXPORT_ADMIN_NOT_FOUND'),
    )
    for fragment, code in patterns:
        if fragment in error:
            return code
    if b'does not exist' in error:
        for fragment, code in ((b'relation ', 'V2_EXPORT_SOURCE_SCHEMA_MISSING'),
                               (b'column ', 'V2_EXPORT_SOURCE_SCHEMA_MISSING'),
                               (b'database ', 'V2_EXPORT_DATABASE_MISSING'),
                               (b'role ', 'V2_EXPORT_ROLE_MISSING')):
            if fragment in error:
                return code
    # SQL guards have fixed messages; whitelist rather than echoing extracted text.
    for suffix in ('CLUSTER_REJECTED', 'SETUP_NOT_CLOSED', 'ACCOUNT_NOT_FOUND', 'IDENTITY_REJECTED',
                   'SEAL_REJECTED', 'SCOPE_REJECTED', 'HASH_FORMAT_REJECTED'):
        if ('error:  v2_admin_source_' + suffix.lower()).encode() in error:
            return 'V2_EXPORT_SOURCE_' + suffix
    return 'V2_EXPORT_CONNECTION_FAILED' if result.returncode == 2 else 'V2_EXPORT_SQL_FAILED'


def require_tcp_socket():
    """No connection/retry: distinguish local sandbox denial from server failures."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM):
            pass
    except OSError as error:
        code = {errno.EPERM: 'V2_EXPORT_SOCKET_EPERM', errno.EACCES: 'V2_EXPORT_SOCKET_DENIED'}.get(
            error.errno, 'V2_EXPORT_SOCKET_UNAVAILABLE')
        raise SafeFailure(code) from None


def run(args, **kwargs):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    except FileNotFoundError:
        raise SafeFailure('V2_EXPORT_PSQL_MISSING' if Path(args[0]).name == 'psql' else 'V2_COMMAND_MISSING') from None
    if result.returncode:
        if Path(args[0]).name == 'psql':
            raise SafeFailure(classify_psql(result))
        raise SafeFailure('V2_COMMAND_FAILED')
    return result.stdout


def private(path, directory=False, code='V2_PRIVATE_PATH_REJECTED'):
    info = path.lstat()
    if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise SafeFailure(code)


def start_existing_v2():
    """Explicit office-only start; never initdb, create DB, delete PID, stop or restart."""
    global STEP
    STEP = 'office-existing-v2-start'
    if Path.cwd().resolve() != ROOT or os.getuid() == 0 or ROOT.resolve() != ROOT:
        raise SafeFailure('V2_START_OPERATOR_REJECTED')
    data = ROOT / '.local/postgres-v2-demo'
    sock = ROOT / '.local/postgres-v2-socket'
    for path in (ROOT / '.local', data, sock):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise SafeFailure('V2_START_PATH_UNSAFE')
    private(data, True, code='V2_START_DATA_UNSAFE')
    for name in ('PG_VERSION', 'global/pg_control', 'postgresql.conf', 'postgresql.auto.conf', 'pg_hba.conf', 'pg_ident.conf'):
        path = data / name
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o022 or path.resolve() != path):
            raise SafeFailure('V2_START_CLUSTER_FILE_UNSAFE')
    if (data / 'PG_VERSION').read_text().strip() != '16':
        raise SafeFailure('V2_START_VERSION_REJECTED')
    if any((data / name).exists() or (data / name).is_symlink() for name in ('standby.signal', 'recovery.signal')):
        raise SafeFailure('V2_START_RECOVERY_CONFIG_REJECTED')
    for name in ('postgresql.conf', 'postgresql.auto.conf'):
        for line in (data / name).read_text().splitlines():
            if re.match(r'^\s*include(?:_dir|_if_exists)?(?:\s|=)', line):
                raise SafeFailure('V2_START_EXTERNAL_CONFIG_REJECTED')
    # Fail before pg_ctl or any startup/log artifact when the sandbox denies sockets.
    require_tcp_socket()
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    env['LC_ALL'] = 'C'
    pg = Path('/usr/lib/postgresql/16/bin')
    expected = {'data_directory': str(data), 'hba_file': str(data / 'pg_hba.conf'),
                'ident_file': str(data / 'pg_ident.conf'), 'primary_conninfo': '',
                'restore_command': '', 'archive_command': '', 'archive_mode': 'off',
                'shared_preload_libraries': ''}
    for setting, value in expected.items():
        actual = run([str(pg / 'postgres'), '-D', str(data), '-C', setting], env=env).decode().strip()
        if actual != value:
            raise SafeFailure('V2_START_CONFIG_REJECTED')
    status = subprocess.run([str(pg / 'pg_ctl'), '-D', str(data), 'status'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if status.returncode == 0:
        # Export SQL verifies this running cluster's real identity; never restart it.
        if (data / 'postmaster.pid').read_text().splitlines()[-1].strip() == 'stopping':
            raise SafeFailure('V2_START_CLUSTER_STOPPING')
        return
    if status.returncode != 3:
        raise SafeFailure('V2_START_STATUS_FAILED')
    # Refuse an occupied target without connecting to or stopping its owner.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 55432))
    except OSError as error:
        code = 'V2_START_PORT_OCCUPIED' if error.errno == errno.EADDRINUSE else 'V2_START_SOCKET_FAILED'
        raise SafeFailure(code) from None
    logs = ROOT / '.local/admin-transfer'
    if not logs.exists():
        logs.mkdir(mode=0o700)
    private(logs, True, code='V2_EXPORT_DIRECTORY_UNSAFE')
    logfile = logs / 'postgres-start.log'
    if not logfile.exists():
        fd = os.open(logfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
    private(logfile, code='V2_START_LOG_UNSAFE')
    options = shlex.join(['-h', '127.0.0.1', '-p', '55432', '-k', str(sock),
        '-c', 'log_statement=none', '-c', 'log_min_error_statement=panic',
        '-c', 'log_error_verbosity=terse', '-c', 'log_parameter_max_length=0',
        '-c', 'log_parameter_max_length_on_error=0'])
    result = subprocess.run([str(pg / 'pg_ctl'), '-D', str(data), '-l', str(logfile),
        '-o', options, '-w', '-t', '30', 'start'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode:
        raise SafeFailure('V2_START_FAILED_PRIVATE_LOG')
    print('PASS: existing office V2 PostgreSQL started on loopback', flush=True)


def export():
    global STEP
    STEP = 'office-read-only-export'
    if Path.cwd().resolve() != ROOT or os.getuid() == 0:
        raise SafeFailure('V2_EXPORT_OPERATOR_REJECTED')
    # Only this V2 repo's configuration and this repo's running processes are eligible.
    configured = os.environ.get('V2_DATABASE_URL')
    if configured is None and (ROOT / '.env').is_file():
        private(ROOT / '.env', code='V2_EXPORT_CONFIG_FILE_UNSAFE')
        for line in (ROOT / '.env').read_text().splitlines():
            if line.startswith('V2_DATABASE_URL='):
                configured = line.split('=', 1)[1].strip().strip('"\'')
    if configured is None:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if (proc / 'cwd').resolve() not in (ROOT, ROOT / 'backend'):
                    continue
                values = (proc / 'environ').read_bytes().split(b'\0')
                urls = [v.split(b'=', 1)[1].decode() for v in values if v.startswith(b'V2_DATABASE_URL=')]
                if urls:
                    if configured is not None and configured != urls[0]:
                        raise SafeFailure('V2_EXPORT_CONFIG_AMBIGUOUS')
                    configured = urls[0]
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                continue
    # Extract the existing repository default without logging or embedding its password.
    if configured is None:
        import ast
        tree = ast.parse((ROOT / 'backend/app/core/config.py').read_text())
        configured = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                          and isinstance(n.value, str) and n.value.startswith('postgresql+psycopg://'))
    url = urlsplit(configured)
    if (url.scheme, url.hostname, url.port, url.path, url.username) != (
        'postgresql+psycopg', '127.0.0.1', 55432, '/mikrotik_manager_v2', 'v2_local') or url.query:
        raise SafeFailure('V2_EXPORT_TARGET_REJECTED')
    target = ROOT / '.local/admin-transfer'
    if not target.exists():
        target.mkdir(mode=0o700)
    private(target, True, code='V2_EXPORT_DIRECTORY_UNSAFE')
    bundle = target / 'admin-transfer.jsonl'
    if bundle.exists() or bundle.is_symlink():
        private(bundle, code='V2_EXPORT_BUNDLE_UNSAFE')
        if not bundle.stat().st_size:
            raise SafeFailure('V2_EXPORT_EXISTING_BUNDLE_EMPTY')
        try:
            data = json.loads(bundle.read_text())
        except (ValueError, UnicodeError):
            raise SafeFailure('V2_EXPORT_EXISTING_BUNDLE_INVALID') from None
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(data['exported_at'])).total_seconds()
        if not -300 <= age < 86400:
            raise SafeFailure('V2_EXPORT_EXISTING_BUNDLE_EXPIRED')
        return bundle
    require_tcp_socket()
    password = unquote(url.password or '')
    existing_passfile = os.environ.get('PGPASSFILE')
    if existing_passfile is None and (Path.home() / '.pgpass').exists():
        existing_passfile = str(Path.home() / '.pgpass')
    temporary_passfile = existing_passfile is None
    if temporary_passfile:
        if not password or any(c in password for c in '\r\n\0'):
            raise SafeFailure('V2_EXPORT_CONFIG_PASSWORD_INVALID')
        fd, pgfile = tempfile.mkstemp(prefix='pgpass-', dir=target)
    else:
        pgfile = str(Path(existing_passfile).absolute())
        private(Path(pgfile), code='V2_EXPORT_PGPASS_UNSAFE')
    created_bundle = False
    try:
        if temporary_passfile:
            with os.fdopen(fd, 'w') as stream:
                escaped = password.replace('\\', '\\\\').replace(':', '\\:')
                stream.write('127.0.0.1:55432:mikrotik_manager_v2:v2_local:' + escaped + '\n')
        with bundle.open('x'):
            pass
        created_bundle = True
        os.chmod(bundle, 0o600)
        private(bundle)
        env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
        env.update(PGPASSFILE=pgfile, PGCONNECT_TIMEOUT='5', LC_ALL='C',
                   PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=5000')
        run(['/usr/lib/postgresql/16/bin/psql', '-X', '-q', '-w', '-h', '127.0.0.1', '-p', '55432',
             '-U', 'v2_local', '-d', 'mikrotik_manager_v2', '-f', str(PACKAGE / 'export-admin.psql')], env=env)
        private(bundle)
        if not bundle.stat().st_size:
            raise SafeFailure('V2_EXPORT_EMPTY_RESULT')
    except BaseException:
        # Only remove our own failed export artifact, never an existing handoff.
        if created_bundle:
            try:
                bundle.unlink()
            except OSError:
                raise SafeFailure('V2_EXPORT_PARTIAL_FILE_CLEANUP_FAILED') from None
        raise
    finally:
        if temporary_passfile:
            try:
                Path(pgfile).unlink()
            except OSError:
                raise SafeFailure('V2_EXPORT_PGPASS_CLEANUP_FAILED') from None
    return bundle


def main():
    global STEP
    if sys.flags.optimize:
        raise SafeFailure('V2_OPTIMIZED_EXECUTION_FORBIDDEN')
    if sys.argv[1:] not in ([], ['--export-only'], ['--start-existing-v2', '--export-only']):
        raise SafeFailure('V2_ARGUMENTS_REJECTED')
    os.umask(0o077)
    os.chdir(ROOT)
    export_only = '--export-only' in sys.argv[1:]
    if not export_only:
        if run(['git', 'status', '--porcelain'], cwd=ROOT).strip():
            raise SafeFailure('V2_WORKTREE_DIRTY')
    if '--start-existing-v2' in sys.argv[1:]:
        start_existing_v2()
    bundle = export()
    print('PASS: office ADMIN read-only export (private file)', flush=True)
    if export_only:
        return
    assert not sys.argv[1:]
    STEP = 'ssh-private-staging'
    stage = run(SSH + ['-o', 'BatchMode=yes', HOST,
                      'umask 077; mktemp -d /home/mikadmin/v2-complete.XXXXXXXX']).decode().strip()
    import re
    assert re.fullmatch(r'/home/mikadmin/v2-complete\.[A-Za-z0-9]{8}', stage)
    STEP = 'source-archive'
    with tempfile.TemporaryDirectory(prefix='source-', dir=bundle.parent) as temp:
        archive = Path(temp) / 'app.tar'
        # Tracked source only; no .env, .local, venv or handoff in the application archive.
        run(['git', 'archive', '--format=tar', '--output=' + str(archive), 'HEAD'], cwd=ROOT)
        STEP = 'sftp-private-transfer'
        batch = '\n'.join(f'put {src} {stage}/{name}' for src, name in (
            (archive, 'app.tar'), (bundle, 'admin-transfer.jsonl'),
            (PACKAGE / 'complete-vds.py', 'complete-vds.py'))) + '\n'
        batch += ''.join(f'chmod 600 {stage}/{name}\n' for name in ('app.tar', 'admin-transfer.jsonl', 'complete-vds.py'))
        run(['sftp', '-b', '-', '-i', '/home/suatpc/.ssh/mikrotik_manager_ed25519',
             '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', HOST], input=batch.encode())
    STEP = 'vds-completion'
    # sudo may ask for the VDS operator's password on the real terminal, never in argv/logs.
    result = subprocess.run(SSH + ['-t', HOST, f'sudo python3 {stage}/complete-vds.py {stage}'])
    if result.returncode:
        raise RuntimeError('VDS completion failed')
    print('PASS: transfer and isolated V2 completion; actual ADMIN password login remains untested')


def failure_code(error):
    if isinstance(error, SafeFailure):
        return error.code
    if isinstance(error, KeyboardInterrupt):
        return 'V2_CANCELLED'
    if isinstance(error, PermissionError):
        return 'V2_FILESYSTEM_PERMISSION_DENIED'
    if isinstance(error, FileExistsError):
        return 'V2_FILE_ALREADY_EXISTS'
    if isinstance(error, FileNotFoundError):
        return 'V2_REQUIRED_FILE_MISSING'
    if STEP == 'office-existing-v2-start':
        return 'V2_START_PREFLIGHT_FAILED'
    return 'V2_EXPORT_CONFIG_INVALID' if STEP == 'office-read-only-export' else 'V2_COMPLETION_FAILED'


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print('BLOCKED: ' + failure_code(error), file=sys.stderr)
        sys.exit(1)
