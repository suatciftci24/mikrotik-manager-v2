#!/usr/bin/env python3
"""Root-only completion of the already migrated isolated V2 cluster. No migrations."""
import base64
import grp
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from urllib.parse import quote, urlsplit, unquote

BASE = Path('/srv/mikrotik-manager-v2-pilot')
PG = '/usr/lib/postgresql/16/bin/psql'
DBUSER = 'mikrotik-v2-db'
APIUSER = 'mikrotik-v2-pilot'
UNIT = 'mikrotik-v2-cebeci-pilot.service'
STEP = 'preflight'


def run(args, data=None, check=True, **kwargs):
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if check and result.returncode:
        raise RuntimeError('command failed')
    return result


def sql(query=None, file=None, check=True):
    args = ['runuser', '-u', DBUSER, '--', PG, '-X', '-q', '-w', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
            '-h', str(BASE / 'postgres-socket'), '-p', '55432', '-U', 'v2_pilot_maint', '-d', 'mikrotik_manager_v2']
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    env.update(PGCONNECT_TIMEOUT='5', PGOPTIONS='-c standard_conforming_strings=on -c log_statement=none -c log_min_error_statement=panic -c log_error_verbosity=terse -c log_parameter_max_length=0 -c log_parameter_max_length_on_error=0')
    if file:
        args += ['-f', str(file)]
    return run(args, data=query.encode() if query else None, check=check, env=env, cwd=BASE)


def safe(path, uid, mode, directory=False):
    s = path.lstat()
    assert s.st_uid == uid and stat.S_IMODE(s.st_mode) == mode
    assert stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1


def directory(path, uid, gid, mode):
    if not path.exists():
        path.mkdir(mode=mode)
        os.chown(path, uid, gid)
    safe(path, uid, mode, True)


def write_new(path, data, uid, gid):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        os.fchown(stream.fileno(), uid, gid)


def main(stage, native=None):
    global STEP
    if sys.flags.optimize:
        raise RuntimeError('optimized execution forbidden')
    assert os.geteuid() == 0 and BASE.resolve() == BASE
    os.umask(0o077)
    operator = pwd.getpwnam('mikadmin')
    assert stage.parent == Path('/home/mikadmin') and stage.name.startswith('v2-complete.')
    safe(stage, operator.pw_uid, 0o700, True)
    for name in (('app.tar', 'native-admin.py', 'complete-vds.py') if native else ('app.tar', 'admin-transfer.jsonl', 'complete-vds.py')):
        safe(stage / name, operator.pw_uid, 0o600)
    db = pwd.getpwnam(DBUSER)  # Existing migrated cluster owner; never create/init/restart DB.
    safe(BASE, 0, 0o755, True)
    safe(BASE / 'postgres', db.pw_uid, 0o700, True)
    safe(BASE / 'postgres-socket', db.pw_uid, 0o700, True)
    STEP = 'existing-cluster-identity'
    guard = """DO $$ BEGIN
 IF current_database()<>'mikrotik_manager_v2' OR current_user<>'v2_pilot_maint'
 OR current_setting('port')<>'55432' OR current_setting('server_version_num')<>'160015'
 OR current_setting('data_directory')<>'/srv/mikrotik-manager-v2-pilot/postgres'
 OR current_setting('listen_addresses')<>'127.0.0.1'
 OR current_setting('password_encryption')<>'scram-sha-256'
 OR current_setting('log_statement')<>'none' OR current_setting('log_error_verbosity')<>'terse'
 OR current_setting('log_parameter_max_length')<>'0'
 OR current_setting('log_parameter_max_length_on_error')<>'0'
 THEN RAISE EXCEPTION 'V2_CLUSTER_REJECTED'; END IF;
 IF EXISTS (SELECT 1 FROM pg_hba_file_rules WHERE error IS NOT NULL OR auth_method='trust')
 OR NOT EXISTS (SELECT 1 FROM pg_hba_file_rules WHERE type='host' AND database=ARRAY['mikrotik_manager_v2']
 AND user_name=ARRAY['v2_local'] AND address='127.0.0.1' AND netmask='255.255.255.255' AND auth_method='scram-sha-256')
 THEN RAISE EXCEPTION 'V2_HBA_REJECTED'; END IF;
END $$;"""
    sql(guard)
    if native:
        native.require_empty()  # READ ONLY: before dependency/config/identity changes.
    STEP = 'isolated-source'
    archive = stage / 'app.tar'
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    app = BASE / 'app'
    marker = BASE / '.completion-source'
    if native and app.exists():
        safe(app, 0, 0o755, True)
        if marker.exists():
            safe(marker, 0, 0o600)
        if not marker.exists() or marker.read_text() != digest:
            # Preserve the isolated previous app intact, never overwrite it or restart a service.
            active = run(['systemctl', 'is-active', '--quiet', UNIT], check=False).returncode
            assert active in (3, 4)  # Inactive/not installed only; any active/unknown state stops.
            backup = BASE / ('native-preinstall-' + secrets.token_hex(8))
            backup.mkdir(mode=0o700)
            app.rename(backup / 'app')
            for name in ('.completion-source', '.completion-built'):
                old = BASE / name
                if old.exists():
                    safe(old, 0, 0o600)
                    old.rename(backup / name)
    if app.exists():
        safe(app, 0, 0o755, True)
        if marker.exists():
            safe(marker, 0, 0o600)
            assert marker.read_text() == digest
        else:
            # Adopt only an exact, root-owned prepositioned copy. Never overwrite unknown code.
            with tarfile.open(archive) as tar:
                for member in tar.getmembers():
                    p = Path(member.name)
                    assert not p.is_absolute() and '..' not in p.parts
                    assert member.isdir() or member.isfile()
                    destination = app / p
                    assert not destination.is_symlink() and destination.stat().st_uid == 0
                    if member.isfile():
                        assert destination.is_file() and destination.stat().st_nlink == 1
                        assert destination.read_bytes() == tar.extractfile(member).read()
            write_new(marker, digest.encode(), 0, 0)
    else:
        # Reject all links/devices/traversal before extraction; no V1/private files in archive.
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                p = Path(member.name)
                assert not p.is_absolute() and '..' not in p.parts
                assert member.isdir() or member.isfile()
                assert not any(part in ('.local', '.env', '.venv', 'node_modules') for part in p.parts)
            app.mkdir(mode=0o755)
            tar.extractall(app, filter='data')
        for current, dirs, files in os.walk(app):
            os.chmod(current, 0o755)
            for name in files:
                path = Path(current) / name
                os.chown(path, 0, 0)
                os.chmod(path, 0o755 if path.stat().st_mode & 0o111 else 0o644)
        write_new(marker, digest.encode(), 0, 0)
    package = app / 'deploy/cebeci-v2-pilot'
    STEP = 'isolated-dependencies-and-build'
    venv = BASE / 'venv'
    if not venv.exists():
        run(['python3', '-m', 'venv', str(venv)])
        os.chmod(venv, 0o755)
    safe(venv, 0, 0o755, True)
    built = BASE / '.completion-built'
    if not built.exists():
        run([str(venv / 'bin/pip'), 'install', '-r', str(app / 'backend/requirements.txt')])
        run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=app / 'frontend')
        run(['npm', 'run', 'build'], cwd=app / 'frontend')
        # umask 077 during install/build; API needs read/execute access to public code only.
        for tree in (venv, app / 'frontend/node_modules', app / 'frontend/dist'):
            for current, dirs, files in os.walk(tree):
                os.chmod(current, 0o755)
                for name in files:
                    path = Path(current) / name
                    if not path.is_symlink():
                        os.chmod(path, 0o755 if path.stat().st_mode & 0o111 else 0o644)
        write_new(built, digest.encode(), 0, 0)
    safe(built, 0, 0o600)
    assert built.read_text() == digest
    if native:
        verify = lambda: sql(file=package / 'verify-native-admin.psql')
    else:
        STEP = 'admin-import-or-verified-resume'
        directory(BASE / 'maintenance', db.pw_uid, db.pw_gid, 0o700)
        handoff = BASE / 'maintenance/admin-transfer.jsonl'
        if handoff.exists():
            safe(handoff, db.pw_uid, 0o600)
            assert hmac.compare_digest(handoff.read_bytes(), (stage / 'admin-transfer.jsonl').read_bytes())
        else:
            write_new(handoff, (stage / 'admin-transfer.jsonl').read_bytes(), db.pw_uid, db.pw_gid)
        if sql(file=package / 'verify-admin.psql', check=False).returncode:
            # import-admin rejects any nonempty/closed state; no reset or repair of identities.
            sql(file=package / 'import-admin.psql')
        sql(file=package / 'verify-admin.psql')
        # Exact account (including hash/revision/grants) AND original office seal must match.
        bundle = json.loads(handoff.read_text())
        def literal(value):
            return "'" + json.dumps(value, ensure_ascii=True).replace("'", "''") + "'::jsonb"
        assert sql("SELECT EXISTS (SELECT 1 FROM v2_demo.users u WHERE to_jsonb(u)=" + literal(bundle['account'])
            + ") AND EXISTS (SELECT 1 FROM v2_demo.first_admin_setup s WHERE to_jsonb(s)=" + literal(bundle['source_setup'])
            + ");").stdout.strip() == b't'
        print('PASS: exact existing ADMIN + original seal + closed setup + import audit', flush=True)
        verify = lambda: sql(file=package / 'verify-admin.psql')
    STEP = 'api-account-and-private-paths'
    try:
        api = pwd.getpwnam(APIUSER)
        assert api.pw_shell in ('/usr/sbin/nologin', '/sbin/nologin')
    except KeyError:
        run(['useradd', '--system', '--user-group', '--no-create-home', '--home-dir', str(BASE), '--shell', '/usr/sbin/nologin', APIUSER])
        api = pwd.getpwnam(APIUSER)
    assert api.pw_uid not in (0, db.pw_uid) and api.pw_gid != db.pw_gid
    assert grp.getgrnam(APIUSER).gr_gid == api.pw_gid
    for name in ('config', 'logs'):
        directory(BASE / name, 0, 0, 0o711)
    for name in ('config/api', 'logs/api', 'app/.local'):
        directory(BASE / name, api.pw_uid, api.pw_gid, 0o700)
    for name in ('output.log', 'error.log'):
        path = BASE / 'logs/api' / name
        if not path.exists():
            write_new(path, b'', api.pw_uid, api.pw_gid)
        safe(path, api.pw_uid, 0o600)
    STEP = 'least-privilege-grants'
    sql(file=package / 'identity-access.psql')
    STEP = 'scram-config'
    config = BASE / 'config/api/database.env'
    if config.exists():
        safe(config, api.pw_uid, 0o600)
        lines = config.read_text().splitlines()
        assert len(lines) == 1 and lines[0].startswith('V2_DATABASE_URL=')
        url = urlsplit(lines[0].split('=', 1)[1])
        assert (url.scheme, url.hostname, url.port, url.username, url.path) == (
            'postgresql+psycopg', '127.0.0.1', 55432, 'v2_local', '/mikrotik_manager_v2')
        password = unquote(url.password or '')
        assert len(password) >= 20 and not url.query
    else:
        password = secrets.token_urlsafe(36)
        # Set only the isolated database role's SCRAM verifier, never the ADMIN hash/password.
        salt = secrets.token_bytes(16)
        salted = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 4096)
        client = hmac.digest(salted, b'Client Key', 'sha256')
        enc = lambda b: base64.b64encode(b).decode()
        verifier = 'SCRAM-SHA-256$4096:' + enc(salt) + '$' + enc(hashlib.sha256(client).digest()) + ':' + enc(hmac.digest(salted, b'Server Key', 'sha256'))
        sql("SET log_statement='none'; ALTER ROLE v2_local LOGIN PASSWORD '" + verifier + "';")
        write_new(config, ('V2_DATABASE_URL=postgresql+psycopg://v2_local:' + quote(password, safe='')
                          + '@127.0.0.1:55432/mikrotik_manager_v2\n').encode(), api.pw_uid, api.pw_gid)
    assert sql("SELECT rolpassword LIKE 'SCRAM-SHA-256$%' FROM pg_authid WHERE rolname='v2_local';").stdout.strip() == b't'
    onboarding = BASE / 'config/api/onboarding.env'
    expected = (package / 'onboarding.env.example').read_bytes()
    if native:
        expected = expected.replace(b'V2_ROUTER_ONBOARDING_OPERATOR_IDS=v2-user-b72c04eb-8000-4f2c-a41a-bc4909cddb92', b'V2_ROUTER_ONBOARDING_OPERATOR_IDS=')
    if not onboarding.exists():
        write_new(onboarding, expected, api.pw_uid, api.pw_gid)
    safe(onboarding, api.pw_uid, 0o600)
    if native and onboarding.read_bytes() == (package / 'onboarding.env.example').read_bytes():
        # Only the exact closed old template is changed; remove its cancelled office operator ID.
        replacement = onboarding.with_name('native-onboarding.env')
        write_new(replacement, expected, api.pw_uid, api.pw_gid)
        replacement.replace(onboarding)
    assert onboarding.read_bytes() == expected
    if native:
        native.provision(operator.pw_uid)
        verify()
    STEP = 'app-role-db-and-identity-check'
    # Run under actual service UID/config, no password/hash output; no credentials for ADMIN requested.
    probe = """import os
from pathlib import Path
for f in ('database.env','onboarding.env'):
 for line in (Path('/srv/mikrotik-manager-v2-pilot/config/api')/f).read_text().splitlines():
  if line and not line.startswith('#'):
   k,v=line.split('=',1);os.environ[k]=v
os.environ['V2_API_PORT']='18080'
from app.core.pilot_runtime import validate_runtime
validate_runtime(Path('/srv/mikrotik-manager-v2-pilot/app'))
from app.services.identity import find_user,public_user
u=find_user('suatciftci',by_username=True)
assert u and u['id'].startswith('v2-user-') and u['account_origin']=='LOCAL' and u['active'] and u['role']=='ADMIN'
assert find_user('demo-user') is None
from app.core.pilot_operator import pilot_identity
p=pilot_identity(public_user(u))
assert p['state']=='ELIGIBLE' and p['candidate']['id']==u['id']
from app.api.v1.router_registry import options
o=options(public_user(u))
assert o['connection_enabled'] is False and o['operator_candidate']['id']==u['id']
"""
    env = dict(os.environ, PYTHONPATH=str(app / 'backend'), PYTHONDONTWRITEBYTECODE='1')
    run(['runuser', '-u', APIUSER, '--', str(venv / 'bin/python'), '-c', probe], env=env, cwd=app)
    STEP = 'verified-api-start'
    verify()  # Mandatory final guard immediately before start.
    unit = Path('/etc/systemd/system') / UNIT
    content = (package / UNIT).read_bytes()
    if unit.exists():
        safe(unit, 0, 0o644)
        assert unit.read_bytes() == content
    else:
        write_new(unit, content, 0, 0)
        os.chmod(unit, 0o644)
        run(['systemctl', 'daemon-reload'])
    active = run(['systemctl', 'is-active', '--quiet', UNIT], check=False).returncode == 0
    if not active:
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 18080))  # Refuse occupied port, never stop another process.
        run(['systemctl', 'start', UNIT])
    STEP = 'loopback-panel-acceptance'
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(10):
        try:
            with opener.open('http://127.0.0.1:18080/api/ready', timeout=3) as response:
                ready = json.load(response)
            assert ready['service'] == 'mikrotik-manager-v2' and ready['api_port'] == 18080
            break
        except Exception:
            if attempt == 9:
                raise
            time.sleep(1)
    with opener.open('http://127.0.0.1:18080/api/health', timeout=5) as response:
        health = json.load(response)
    assert health['database_connected'] is True and health['device_adapters_connected'] is False
    from urllib.error import HTTPError
    request = urllib.request.Request('http://127.0.0.1:18080/api/v1/auth/login',
        data=b'{"username":"demo","password":"demo-only"}', headers={'Content-Type': 'application/json'})
    try:
        opener.open(request, timeout=5)
        raise RuntimeError('demo login unexpectedly accepted')
    except HTTPError as error:
        assert error.code == 401
    with opener.open('http://127.0.0.1:18080/', timeout=5) as response:
        assert response.status == 200 and b'<html' in response.read().lower()
    listeners = run(['ss', '-H', '-ltn', 'sport = :18080']).stdout.decode().splitlines()
    assert len(listeners) == 1 and listeners[0].split()[3] == '127.0.0.1:18080'
    if native:
        STEP = 'native-admin-http-login'
        native.verify_login()
    # Delete only the exact transfer artifacts after all checks; retain DB/audit/source/config.
    if not native:
        safe(handoff, db.pw_uid, 0o600)
        handoff.unlink()
    for name in (('native-admin.py', 'app.tar', 'complete-vds.py') if native else ('admin-transfer.jsonl', 'app.tar', 'complete-vds.py')):
        safe(stage / name, operator.pw_uid, 0o600)
        (stage / name).unlink()
    stage.rmdir()
    print('PASS: SCRAM app connection, verified ADMIN, UI/API 127.0.0.1:18080, both router gates false')
    if not native:
        print('UNTESTED: actual ADMIN password login (password was neither requested nor reset)')


if __name__ == '__main__':
    try:
        main(Path(sys.argv[1]))
    except (Exception, KeyboardInterrupt):
        # Do not emit SQL errors, DSNs, subprocess output, bundle content or traceback.
        print(f'BLOCKED: {STEP}; private state preserved; no automatic retry', file=sys.stderr)
        sys.exit(1)
