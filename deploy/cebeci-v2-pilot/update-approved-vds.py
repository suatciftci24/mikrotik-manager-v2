#!/usr/bin/env python3
"""Approved 7bb617c V2 update. Fail closed; never connect to any router.

No migrations: this onboarding release requires none. Any migration/dependency
change against the installed tree blocks for separate review, before replacement.
"""
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import urllib.error
import uuid

B = Path('/srv/mikrotik-manager-v2-pilot')
UNIT = 'mikrotik-v2-cebeci-pilot.service'
PG = '/usr/lib/postgresql/16/bin/'
STEP = 'preflight'
COOKIE = ''
REASON = 'PRECONDITION_FAILED'
accepted = False


def need(value, reason='PRECONDITION_FAILED'):
    global REASON
    if not value:
        REASON = reason
        raise RuntimeError(STEP)


def run(args, **kw):
    global REASON
    REASON = kw.pop('reason', 'COMMAND_FAILED')
    p = subprocess.run(args, capture_output=True, **kw)
    need(p.returncode == 0, REASON)
    return p.stdout


def sql(query):
    return run([RUNUSER, '-u', 'mikrotik-v2-db', '--', PG+'psql', '-XqwAt',
                '-v', 'ON_ERROR_STOP=1', '-h', str(B/'postgres-socket'), '-p', '55432',
                '-U', 'v2_pilot_maint', '-d', 'mikrotik_manager_v2', '-c', query], env=PGENV, cwd=B, reason='MAINTENANCE_SOCKET_QUERY_FAILED')


def service_database_identity(service_env):
    # Use the running service's interpreter and URL, never a default or operator
    # shell configuration. Secrets travel on stdin only, not argv or diagnostics.
    probe = '''
import json, sys
from ipaddress import IPv4Interface
from urllib.parse import urlsplit, unquote
try:
    import psycopg
except BaseException:
    sys.exit(20)
code = 21
try:
    url = urlsplit(json.load(sys.stdin)['V2_DATABASE_URL'])
    if ((url.scheme, url.hostname, url.port, url.username, url.path) !=
        ('postgresql+psycopg', '127.0.0.1', 55432, 'v2_local', '/mikrotik_manager_v2')
        or url.query or url.fragment or not url.password):
        raise ValueError()
    code = 22
    with psycopg.connect(host='127.0.0.1', port=55432, user='v2_local',
            dbname='mikrotik_manager_v2', password=unquote(url.password),
            connect_timeout=5, options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
        code = 23
        row = conn.execute("SELECT current_database(), current_user, inet_server_addr()::text, inet_server_port(), current_setting('transaction_read_only')").fetchone()
        if not row or len(row) != 5:
            code = 29
            raise ValueError()
        # PostgreSQL's inet -> text cast can include the full host mask.
        # Accept only a single IPv4 host, never a subnet, DNS alias, IPv6 or
        # another member of 127/8. Keep the actual connection target fixed.
        code = 30
        if not isinstance(row[2], str):
            raise ValueError()
        address = IPv4Interface(row[2])
        if address.network.prefixlen != 32:
            raise ValueError()
        actual = (row[0], row[1], str(address.ip), row[3], row[4])
        for index, expected in enumerate(('mikrotik_manager_v2', 'v2_local', '127.0.0.1', 55432, 'on')):
            code = 24 + index
            if actual[index] != expected:
                raise ValueError()
except BaseException:
    sys.exit(code)
'''
    global REASON
    need(bool(service_env.get('V2_DATABASE_URL')), 'SERVICE_DATABASE_URL_MISSING')
    REASON = 'SERVICE_PROBE_EXECUTION_FAILED'
    result = subprocess.run([RUNUSER, '-u', 'mikrotik-v2-pilot', '--', str(B/'venv/bin/python'), '-I', '-c', probe],
        input=json.dumps({'V2_DATABASE_URL': service_env['V2_DATABASE_URL']}).encode(),
        env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, cwd=B, timeout=25, capture_output=True)
    need(result.returncode == 0, {20: 'SERVICE_PSYCOPG_IMPORT_FAILED',
        21: 'SERVICE_DATABASE_URL_INVALID', 22: 'SERVICE_DATABASE_CONNECT_FAILED',
        23: 'SERVICE_DATABASE_QUERY_FAILED', 24: 'SERVICE_DATABASE_NAME_MISMATCH', 25: 'SERVICE_DATABASE_ROLE_MISMATCH',
        26: 'SERVICE_DATABASE_ADDRESS_MISMATCH', 27: 'SERVICE_DATABASE_PORT_MISMATCH',
        28: 'SERVICE_DATABASE_READONLY_MISMATCH', 29: 'SERVICE_DATABASE_IDENTITY_SHAPE_INVALID',
        30: 'SERVICE_DATABASE_ADDRESS_INVALID'
        }.get(result.returncode, 'SERVICE_PROBE_EXECUTION_FAILED'))


def api(path, data=None):
    global COOKIE
    headers = {'Content-Type': 'application/json', 'Cookie': COOKIE,
               'X-V2-Demo-Action': 'router-onboarding'}
    req = urllib.request.Request('http://127.0.0.1:18080'+path,
            data=json.dumps(data).encode() if data is not None else None, headers=headers)
    # Explicitly prohibit proxies and redirects. Never follow a target from a response.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=10) as response:
        if path.endswith('/login'):
            COOKIE = response.headers.get('Set-Cookie', '').split(';')[0]
        return json.load(response)


def health():
    h = api('/api/health')
    need(h.get('database_connected') is True and h.get('device_adapters_connected') is False)
    run(['systemctl', 'is-active', '--quiet', UNIT])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()} if root.exists() else {}


def check_legacy_migration_evidence():
    """Read-only diagnosis, never reconstruct migration history from schema flags.

    This repository has no per-migration applied revision/checksum ledger.
    schema_state.version=1 identifies the synthetic store, not migration 001
    (nor the head). Even a healthy ADMIN seal cannot prove all migrations or
    constraints. Until independently verifiable history AND a complete target
    schema comparison are available, legacy adoption must remain blocked.
    """
    global REASON
    REASON = 'LEGACY_SCHEMA_EVIDENCE_QUERY_FAILED'
    # sql() uses the already identity-checked V2 maintenance socket and PGENV's
    # read-only transaction. Return booleans only; never read users or secrets.
    evidence = sql("""SELECT to_regclass('v2_demo.schema_state') IS NOT NULL,
        to_regclass('v2_demo.first_admin_setup') IS NOT NULL,
        to_regnamespace('v2_router_workspace') IS NOT NULL,
        to_regnamespace('v2_subscriber_workspace') IS NOT NULL""").decode().strip()
    need(evidence == 't|t|t|t', 'LEGACY_SCHEMA_EVIDENCE_INCOMPLETE')
    # Presence is necessary but insufficient. Do not stamp, seed, copy target
    # migrations into app, or treat backup/build success as database evidence.
    need(False, 'LEGACY_MIGRATION_HISTORY_UNVERIFIABLE')


def prepare_release(private, version):
    global REASON
    release = private/'release'
    REASON = 'RELEASE_DIRECTORY_CREATE_FAILED'
    release.mkdir(mode=0o755)
    REASON = 'RELEASE_ARCHIVE_READ_FAILED'
    with tarfile.open(private/'source.tar') as tar:
        need(tar.pax_headers.get('comment') == version, 'RELEASE_ARCHIVE_REVISION_MISMATCH')
        for member in tar.getmembers():
            need(not member.issym() and not member.islnk() and not member.isdev()
                 and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                 and (member.isfile() or member.isdir()), 'RELEASE_ARCHIVE_MEMBER_UNSAFE')
        REASON = 'RELEASE_ARCHIVE_EXTRACT_FAILED'
        tar.extractall(release, filter='data')
    for name in ('backend/requirements.txt', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/tsconfig.json', 'frontend/index.html'):
        need((release/name).is_file(), 'RELEASE_REQUIRED_FILE_MISSING')
    need((release/'migrations').is_dir(), 'RELEASE_MIGRATIONS_MISSING')
    REASON = 'RELEASE_REQUIREMENTS_READ_FAILED'
    for name in ('backend/requirements.txt',):
        need(digest(release/name) == digest(B/'app'/name), 'RELEASE_REQUIREMENTS_CHANGED')
    installed = B/'app/migrations'
    need(not installed.is_symlink(), 'INSTALLED_MIGRATIONS_UNSAFE')
    if not installed.exists():
        check_legacy_migration_evidence()
    need(installed.is_dir(), 'INSTALLED_MIGRATIONS_INVALID')
    REASON = 'RELEASE_MIGRATIONS_READ_FAILED'
    need(files(release/'migrations') == files(B/'app/migrations'), 'RELEASE_MIGRATIONS_CHANGED')
    # Existing V2 toolchain only; no system package changes, no venv changes.
    nodebin = B/'toolchain/node/bin'
    buildenv = {'PATH': str(nodebin)+':/usr/local/bin:/usr/bin:/bin', 'HOME': str(private),
                'npm_config_userconfig': '/dev/null', 'npm_config_globalconfig': str(private/'global.npmrc'),
                'npm_config_cache': str(private/'npm-cache'), 'npm_config_ignore_scripts': 'true'}
    REASON = 'FRONTEND_NPM_CONFIG_WRITE_FAILED'
    (private/'global.npmrc').write_text('')
    npm = shutil.which('npm', path=buildenv['PATH'])
    need(npm is not None, 'FRONTEND_NPM_NOT_FOUND')
    node = shutil.which('node', path=buildenv['PATH'])
    need(node is not None, 'FRONTEND_NODE_NOT_FOUND')
    run([node, '--version'], env=buildenv, reason='FRONTEND_NODE_RUNTIME_FAILED')
    run([npm, '--version'], env=buildenv, reason='FRONTEND_NPM_RUNTIME_FAILED')
    run([npm, 'ci', '--include=dev', '--include=optional', '--ignore-scripts', '--no-audit', '--no-fund', '--fetch-retries=0'], cwd=release/'frontend', env=buildenv, reason='FRONTEND_DEPENDENCY_INSTALL_FAILED')
    run([npm, 'run', 'build'], cwd=release/'frontend', env=buildenv, reason='FRONTEND_BUILD_FAILED')
    need((release/'frontend/dist/index.html').is_file(), 'FRONTEND_BUILD_INDEX_MISSING')
    REASON = 'FRONTEND_DEPENDENCY_CLEANUP_FAILED'
    shutil.rmtree(release/'frontend/node_modules')
    return release


os.umask(0o077)
PGENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'PGCONNECT_TIMEOUT': '5',
         'PGOPTIONS': '-c default_transaction_read_only=on -c statement_timeout=15000'}
changed = False
backup = None
previous = None
try:
    need(os.geteuid() == 0 and B.resolve() == B)
    stage = Path(sys.argv[1])
    need(stage.parent == Path('/home/mikadmin') and stage.name.startswith('v2-update.') and stage.resolve() == stage)
    # Copy operator-owned input into a root-only directory before validating/executing it.
    private = B / ('update-'+time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())+'-'+uuid.uuid4().hex[:8])
    private.mkdir(mode=0o700)
    for name in ('source.tar', 'source.sha256', 'version'):
        src = stage/name
        need(src.is_file() and not src.is_symlink())
        shutil.copyfile(src, private/name)
    version = (private/'version').read_text().strip()
    need(version == '7bb617c4838c1bd94b8cbe612981cabe5186b6b1', 'TARGET_REVISION_MISMATCH')
    need(digest(private/'source.tar') == (private/'source.sha256').read_text().split()[0])
    props = run(['systemctl', 'show', UNIT, '-p', 'WorkingDirectory', '-p', 'ExecStart', '-p', 'MainPID']).decode()
    need('WorkingDirectory='+str(B/'app')+'\n' in props and str(B/'venv/bin/python') in props)
    pid = int(next(x.split('=', 1)[1] for x in props.splitlines() if x.startswith('MainPID=')))
    need(pid > 0)
    env = dict(v.split('=', 1) for v in Path(f'/proc/{pid}/environ').read_text().split('\0') if '=' in v)
    need(env.get('V2_ROUTER_ONBOARDING_ENABLED') == 'false' and env.get('V2_CEBECI_API_SSL_ENABLED') == 'false')
    STEP = 'isolated-db-identity'
    # Resolve before applying the restricted PostgreSQL PATH: runuser normally
    # lives in /usr/sbin, which is intentionally absent from PGENV.
    RUNUSER = shutil.which('runuser', path='/usr/sbin:/usr/bin:/sbin:/bin')
    need(RUNUSER is not None, 'RUNUSER_NOT_FOUND')
    identity = sql("SELECT current_database(),current_user,current_setting('port'),current_setting('data_directory')").decode().strip()
    parts = identity.split('|')
    need(len(parts) == 4, 'MAINTENANCE_IDENTITY_SHAPE_INVALID')
    for actual, expected, field in zip(parts, ('mikrotik_manager_v2', 'v2_pilot_maint', '55432', str(B/'postgres')),
                                       ('DATABASE', 'ROLE', 'PORT', 'DATA_DIRECTORY')):
        need(actual == expected, 'MAINTENANCE_'+field+'_MISMATCH')
    service_database_identity(env)
    STEP = 'closed-service-health'
    health()
    if len(sys.argv) > 2:
        need(sys.argv[2:] in (['--check-only'], ['--release-check-only']), 'INVALID_MODE')
    if sys.argv[2:] == ['--check-only']:
        print('PASS isolated-db-identity closed-service-health; check-only; no deployment', flush=True)
        sys.exit(0)
    STEP = 'verified-backup'
    backup = private/'backup'
    backup.mkdir(mode=0o700)
    # App includes .local vault/certificates. Configuration and venv are preserved too.
    with tarfile.open(backup/'application.tar', 'w') as tar:
        for name in ('app', 'venv', 'config'):
            need((B/name).is_dir() and not (B/name).is_symlink())
            tar.add(B/name, arcname=name, recursive=True)
    with tarfile.open(backup/'application.tar') as tar:
        for member in tar:
            if member.isfile():
                stream = tar.extractfile(member)
                while stream.read(1024*1024):
                    pass
    dump = run([RUNUSER, '-u', 'mikrotik-v2-db', '--', PG+'pg_dump', '-Fc', '-w',
                '-h', str(B/'postgres-socket'), '-p', '55432', '-U', 'v2_pilot_maint',
                '-d', 'mikrotik_manager_v2'], env=PGENV, cwd=B)
    need(len(dump) > 1000)
    (backup/'database.dump').write_bytes(dump)
    run([PG+'pg_restore', '--list', str(backup/'database.dump')])
    # Read/decompress every data block without writing to any database.
    with open(os.devnull, 'wb') as null:
        p = subprocess.run([PG+'pg_restore', '--file=-', str(backup/'database.dump')], stdout=null, stderr=subprocess.PIPE)
        need(p.returncode == 0)
    sums = {name: digest(backup/name) for name in ('application.tar', 'database.dump')}
    (backup/'sha256.json').write_text(json.dumps(sums))
    need(all(digest(backup/name) == value for name, value in sums.items()))
    print('PASS backup='+str(backup), flush=True)
    STEP = 'release-scope-and-build'
    release = prepare_release(private, version)
    if sys.argv[2:] == ['--release-check-only']:
        print('PASS release-scope-and-build; no replacement/migration/restart; backup='+str(backup), flush=True)
        sys.exit(0)
    # Preserve certificates, vault and runtime files byte-for-byte and with ownership.
    if (B/'app/.local').exists():
        run(['cp', '-a', str(B/'app/.local'), str(release/'.local')])
    for current, dirs, names in os.walk(release):
        if Path(current).is_relative_to(release/'.local'):
            continue
        os.chmod(current, 0o755)
        for name in names:
            p = Path(current)/name
            os.chmod(p, 0o755 if p.stat().st_mode & 0o111 else 0o644)
    STEP = 'replace-and-health'
    previous = private/'previous-app'
    (B/'app').rename(previous)
    changed = True
    release.rename(B/'app')
    run(['systemctl', 'restart', UNIT])
    # One bounded startup wait, then one health acceptance; no router IO.
    time.sleep(3)
    health()
    STEP = 'admin-login'
    username = input('V2 ADMIN kullanıcı adı: ').strip()
    password = getpass.getpass('V2 ADMIN parolası (çıktıya yazılmaz): ')
    user = api('/api/v1/auth/login', {'username': username, 'password': password})
    del password
    need(user.get('role_code') == 'ADMIN' and user.get('account_origin') == 'LOCAL' and user.get('active') is True)
    me = api('/api/v1/auth/me')
    need(me.get('id') == user['id'])
    # Deployment is accepted before the optional inventory write. Never revert to
    # older code after a PENDING row has committed: old serializers may not support it.
    (B/'app/.pilot-version').write_text(version+'\n')
    accepted = True
    STEP = 'inventory'
    options = api('/api/v1/router-registry/options')
    need(options.get('connection_enabled') is False)
    inventory = 'BLOCKED:OPERATOR_NOT_AUTHORIZED'
    if options.get('operator_authorized') is True:
        rows = api('/api/v1/router-registry?query=10.250.0.19&page_size=100')
        need(rows['total'] <= 100)
        matching = [r for r in rows['items'] if r.get('management_address') == '10.250.0.19' and r.get('port') == 8729]
        if matching:
            inventory = 'EXISTING:'+matching[0].get('status', 'UNKNOWN')
        else:
            reference = input('Mevcut güvenli V2 vault credential_ref (yoksa Enter): ').strip()
            inventory = 'BLOCKED:CREDENTIAL_REF_NOT_VERIFIED'
            if reference:
                try:
                    reference = str(uuid.UUID(reference))
                    result = api('/api/v1/router-registry/inventory', dict(request_id=str(uuid.uuid4()),
                        name='CEBECI_TOWERS', management_address='10.250.0.19', port=8729,
                        credential_ref=reference, confirmed=True))
                    need(result['item']['status'] == 'PENDING_VERIFICATION')
                    saved = api('/api/v1/router-registry/'+result['item']['id'])
                    need(saved['item']['status'] == 'PENDING_VERIFICATION')
                    inventory = 'PENDING_VERIFICATION'
                except (ValueError, urllib.error.HTTPError):
                    inventory = 'BLOCKED:CREDENTIAL_REF_OR_AUTHORIZATION_REJECTED'
    api('/api/v1/auth/logout', {})
    COOKIE = ''
    print('APPLIED version='+version+' backup='+str(backup)+' V2_service=healthy ADMIN=PASS CEBECI_TOWERS='+inventory)
except BaseException as exc:
    if isinstance(exc, SystemExit) and exc.code == 0:
        raise
    failure_reason = REASON
    rollback = 'NOT_NEEDED'
    if changed and not accepted:
        try:
            if (B/'app').exists():
                (B/'app').rename(private/'failed-app')
            previous.rename(B/'app')
            run(['systemctl', 'restart', UNIT])
            time.sleep(3)
            health()
            rollback = 'PASS'
        except BaseException:
            rollback = 'BLOCKED'
    if accepted:
        print('APPLIED version='+version+' V2_service=healthy ADMIN=PASS CEBECI_TOWERS=BLOCKED backup='+str(backup), file=sys.stderr)
    print('BLOCKED step='+STEP+' reason='+failure_reason+' rollback='+rollback+' backup='+str(backup)+'; no secrets printed', file=sys.stderr)
    sys.exit(1)
