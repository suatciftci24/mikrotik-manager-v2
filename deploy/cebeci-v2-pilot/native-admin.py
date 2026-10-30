#!/usr/bin/env python3
"""Explicit VDS-only first ADMIN. No office export, migration or password reset."""
import getpass
import hmac
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid
import warnings

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('isolated_vds_completion', HERE / 'complete-vds.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
_login_password = None
TARGET_GUARD = """DO $$ BEGIN
 IF current_database()<>'mikrotik_manager_v2' OR current_user<>'v2_pilot_maint'
 OR current_setting('port')<>'55432'
 OR current_setting('data_directory')<>'/srv/mikrotik-manager-v2-pilot/postgres'
 THEN RAISE EXCEPTION 'V2_NATIVE_TARGET_REJECTED'; END IF;
END $$;"""

# Shared lock and row lock are acquired before this guard in the creation transaction.
EMPTY_GUARD = """DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM v2_demo.users WHERE role='ADMIN')
 THEN RAISE EXCEPTION 'V2_NATIVE_EXISTING_ADMIN_STOP'; END IF;
 IF EXISTS (SELECT 1 FROM v2_demo.users)
 THEN RAISE EXCEPTION 'V2_NATIVE_OTHER_USERS_STOP'; END IF;
 IF EXISTS (SELECT 1 FROM v2_demo.schema_state WHERE version=1 AND first_admin_initialized)
 THEN RAISE EXCEPTION 'V2_NATIVE_SETUP_CLOSED_STOP'; END IF;
 IF EXISTS (SELECT 1 FROM v2_demo.first_admin_setup)
 THEN RAISE EXCEPTION 'V2_NATIVE_SEAL_PRESENT_STOP'; END IF;
 IF EXISTS (SELECT 1 FROM v2_demo.user_audit)
 THEN RAISE EXCEPTION 'V2_NATIVE_AUDIT_PRESENT_STOP'; END IF;
 IF NOT EXISTS (SELECT 1 FROM v2_demo.schema_state WHERE version=1
 AND marker='mikrotik-manager-v2-synthetic-only' AND identity_initialized AND NOT first_admin_initialized)
 THEN RAISE EXCEPTION 'V2_NATIVE_SETUP_STATE_REJECTED'; END IF;
END $$;"""


def require_empty():
    deploy.STEP = 'native-admin-read-only-absence-check'
    if deploy.sql("BEGIN READ ONLY; " + TARGET_GUARD + " SELECT EXISTS(SELECT 1 FROM v2_demo.users WHERE role='ADMIN'); COMMIT;").stdout.strip() == b't':
        deploy.STEP = 'native-existing-admin-stop-no-changes'
        raise deploy.Blocked('V2_NATIVE_EXISTING_ADMIN_STOP')
    deploy.sql('BEGIN READ ONLY; ' + TARGET_GUARD + EMPTY_GUARD + ' COMMIT;')


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def creation_sql(record, operator_uid):
    """Secret SQL travels only on psql stdin; never argv, files or diagnostics."""
    assert type(operator_uid) is int and operator_uid > 0
    public = {k: v for k, v in record.items() if k != 'password_hash'}
    values = [literal(record[k]) for k in ('id', 'username', 'name', 'email')]
    return ("BEGIN; SELECT pg_advisory_xact_lock(hashtext('v2-user-management')); "
        "SELECT version FROM v2_demo.schema_state WHERE version=1 FOR UPDATE; " + TARGET_GUARD + EMPTY_GUARD +
        "INSERT INTO v2_demo.users(id,username,name,email,role,active,password_hash,permissions,revision,account_origin) VALUES ("
        + ','.join(values) + ",'ADMIN',true," + literal(record['password_hash']) + ','
        + literal(json.dumps(record['permissions'])) + "::jsonb,0,'LOCAL'); "
        "INSERT INTO v2_demo.first_admin_setup(singleton,admin_id,local_operator_uid) VALUES(1,"
        + literal(record['id']) + ',' + str(operator_uid) + "); "
        "INSERT INTO v2_demo.user_audit(id,actor_id,target_id,operation,previous_values,new_values,result,fingerprint,response) VALUES ("
        + literal(str(uuid.uuid4())) + ",'local-maintenance:v2_pilot_maint'," + literal(record['id'])
        + ",'FIRST_ADMIN_CREATE',NULL," + literal(json.dumps(public))
        + "::jsonb,'SUCCESS','VDS_LOCAL_TTY_BOOTSTRAP',"
        + literal(json.dumps({'id': record['id'], 'status': 'CREATED_SETUP_CLOSED'}))
        + "::jsonb); UPDATE v2_demo.schema_state SET first_admin_initialized=true WHERE version=1; COMMIT;")


def open_tty():
    # /dev/tty is non-seekable: built-in open(..., 'r+') would use BufferedRandom.
    raw = io.FileIO(os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY), mode='r+', closefd=True)
    return io.TextIOWrapper(raw, encoding='utf-8', line_buffering=True, write_through=True)


def provision(operator_uid):
    global _login_password
    require_empty()  # Recheck before prompting; never ask to reset an existing ADMIN.
    deploy.STEP = 'native-admin-tty-input'
    sys.path.insert(0, str(deploy.BASE / 'venv/lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'))
    sys.path.insert(0, str(deploy.BASE / 'app/backend'))
    from app.services.first_admin import FirstAdminIdentity, FirstAdminInput
    from app.services.identity import hash_password
    from app.core.authorization import PERMISSIONS
    from app.services.demo_data import ROUTERS
    with open_tty() as tty:
        if not tty.isatty():
            raise RuntimeError('TTY required')
        def ask(prompt):
            tty.write(prompt)
            value = tty.readline()
            if not value:
                raise RuntimeError('TTY closed')
            return value.rstrip('\n')
        public = FirstAdminIdentity(username='suatciftci', name=ask('Ad soyad: '), email=ask('E-posta: '))
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Yeni ADMIN parolası (14–128 karakter): ', stream=tty)
            repeat = getpass.getpass('Parola tekrar: ', stream=tty)
        if not hmac.compare_digest(password.encode('utf-8'), repeat.encode('utf-8')):
            raise RuntimeError('password mismatch')
        payload = FirstAdminInput(**public.model_dump(), password=password)
        if ask('Yalnız izole VDS V2 ADMIN oluşturmak için OLUSTUR yazın: ') != 'OLUSTUR':
            raise RuntimeError('cancelled')
    record = {**public.model_dump(), 'id': 'v2-user-' + str(uuid.uuid4()), 'role': 'ADMIN',
        'active': True, 'account_origin': 'LOCAL', 'revision': 0,
        'permissions': {r['id']: {p: True for p in PERMISSIONS} for r in ROUTERS},
        'password_hash': hash_password(payload.password.get_secret_value(), real_account=True)}
    _login_password = password
    del password, repeat, payload
    deploy.STEP = 'native-admin-atomic-create'
    deploy.sql(creation_sql(record, operator_uid))
    del record


def verify_login():
    global _login_password
    import http.cookiejar
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = 'http://127.0.0.1:18080/api/v1'
    def post(path, value):
        request = urllib.request.Request(base + path, data=json.dumps(value).encode(),
            headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=5) as response:
            return json.load(response)
    try:
        user = post('/auth/login', {'username': 'suatciftci', 'password': _login_password})
        assert user['username'] == 'suatciftci' and user['account_origin'] == 'LOCAL' and user['role_code'] == 'ADMIN'
        with opener.open(base + '/auth/me', timeout=5) as response:
            assert json.load(response)['id'] == user['id']
        with opener.open(base + '/router-registry/options', timeout=5) as response:
            options = json.load(response)
        assert options['connection_enabled'] is False and options['operator_authorized'] is False
        post('/auth/logout', {})
    finally:
        _login_password = None


if __name__ == '__main__':
    try:
        if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != '--preflight-only'):
            raise deploy.Blocked('V2_NATIVE_ARGUMENTS_REJECTED')
        deploy.main(Path(sys.argv[1]), native=sys.modules[__name__], preflight_only=len(sys.argv) == 3)
    except (Exception, KeyboardInterrupt) as error:
        print('BLOCKED: ' + deploy.failure_code(error), file=sys.stderr)
        sys.exit(1)
