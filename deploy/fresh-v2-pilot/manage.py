#!/usr/bin/env python3
"""Offline check by default. Explicit fresh-only migrate/verify/backup; no SSH or reset."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'backend'))
ROOT = Path('/srv/mikrotik-manager-v2-fresh-pilot')
DATABASE = 'mikrotik_manager_v2_fresh_pilot'
OWNER = 'v2_fresh_owner'
APP = 'v2_fresh_app'
SCHEMAS = ('public', 'v2_demo', 'v2_router_workspace', 'v2_subscriber_workspace', 'v2_migrations')
ASSETS = ('profile.json','ledger.sql','schema.sql','schema.expected.json','postgresql.conf',
          'pg_hba.conf','pg_ident.conf','mikrotik-v2-fresh-pilot.service',
          'mikrotik-v2-fresh-pilot-db.service','manage.py','stage-approved.py',
          'accept-approved.py','runtime_check.py')
FILES = ('001_initial_v2.sql', '002_demo_storage.sql', '003_demo_alarm_actions.sql',
         '004_demo_identity.sql', '005_demo_settings.sql', '006_router_registry.sql',
         '007_router_workspace.sql', '008_subscriber_workspace.sql', '009_first_local_admin.sql')


class Blocked(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Blocked(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def checked_file(path):
    need(path.is_file() and not path.is_symlink(), 'SOURCE_FILE_REJECTED')
    return path.read_bytes()


def check_sources():
    manifest_bytes = checked_file(HERE / 'manifest.json')
    manifest = json.loads(manifest_bytes)
    need(tuple(item['revision'] for item in manifest['migrations']) == FILES, 'MIGRATION_ORDER_REJECTED')
    need(manifest['format'] == 1 and set(manifest['assets']) == set(ASSETS), 'MANIFEST_FORMAT_REJECTED')
    sql = []
    for position, item in enumerate(manifest['migrations'], 1):
        data = checked_file(REPO / 'migrations/versions' / item['revision'])
        need(item['position'] == position and digest(data) == item['sha256'], 'MIGRATION_CHECKSUM_MISMATCH')
        sql.append(data.decode())
    for name, checksum in manifest['assets'].items():
        need('/' not in name and digest(checked_file(HERE / name)) == checksum, 'PROFILE_CHECKSUM_MISMATCH')
    profile = json.loads(checked_file(HERE / 'profile.json'))
    need(profile == dict(profile='fresh-v2-pilot', root=str(ROOT), database=DATABASE,
        owner_role=OWNER, app_role=APP, db_os_user='mikrotik-v2-fresh-db', app_os_user='mikrotik-v2-fresh',
        db_port=55442, api_port=18090, db_service='mikrotik-v2-fresh-pilot-db.service',
        app_service='mikrotik-v2-fresh-pilot.service', postgres_major=16), 'PROFILE_IDENTITY_REJECTED')
    return manifest_bytes, manifest, sql


def execute(c, sql, params=None):
    from sqlalchemy import text
    return c.execute(text(sql), params or {})


def execute_script(c, content):
    # Pinned SQL currently contains no dollar quotes or semicolons in literals.
    # Strip line comments before splitting; changing that grammar requires runner review.
    import re
    for statement in re.sub(r'--[^\n]*', '', content).split(';'):
        if statement.strip():
            execute(c, statement)


def verify_identity(c, database=DATABASE):
    need(tuple(execute(c, 'SELECT current_database(),current_user,inet_server_port(),inet_server_addr()').one())
         == (database, OWNER, None, None), 'DATABASE_IDENTITY_REJECTED')
    need(execute(c, 'SHOW data_directory').scalar_one() == str(ROOT / 'postgres'), 'DATA_DIRECTORY_REJECTED')
    need(execute(c, 'SHOW port').scalar_one() == '55442', 'DATABASE_PORT_REJECTED')
    need(execute(c, 'SHOW server_version_num').scalar_one().startswith('16'), 'POSTGRES_MAJOR_REJECTED')
    need(execute(c, 'SHOW listen_addresses').scalar_one() == '127.0.0.1', 'DATABASE_BIND_REJECTED')


def require_empty(c):
    # No ledger/adoption/resume path. Reject objects beyond standard empty PG16 template.
    need(list(execute(c, "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema' ORDER BY 1").scalars()) == ['public'], 'NONEMPTY_TARGET')
    for catalog, namespace in [('pg_class','relnamespace'), ('pg_proc','pronamespace'), ('pg_type','typnamespace'), ('pg_operator','oprnamespace'), ('pg_collation','collnamespace'), ('pg_conversion','connamespace')]:
        need(execute(c, f"SELECT count(*) FROM {catalog} o JOIN pg_namespace n ON n.oid=o.{namespace} WHERE n.nspname='public'").scalar_one() == 0, 'NONEMPTY_TARGET')
    need(list(execute(c, 'SELECT extname FROM pg_extension ORDER BY 1').scalars()) == ['plpgsql'], 'NONEMPTY_TARGET')
    for catalog in ('pg_event_trigger','pg_default_acl','pg_foreign_server','pg_foreign_data_wrapper','pg_publication','pg_subscription'):
        need(execute(c, f'SELECT count(*) FROM {catalog}').scalar_one() == 0, 'NONEMPTY_TARGET')
    need(execute(c, 'SELECT count(*) FROM pg_largeobject_metadata').scalar_one() == 0, 'NONEMPTY_TARGET')
    need(not execute(c, 'SELECT 1 FROM pg_roles WHERE rolname=:name', {'name':APP}).scalar_one_or_none(), 'APP_ROLE_ALREADY_EXISTS')


def schema_hash(c):
    value = execute(c, checked_file(HERE / 'schema.sql').decode()).scalar_one()
    return digest(canonical(json.loads(value)))


def verify_schema(c):
    expected = json.loads(checked_file(HERE / 'schema.expected.json'))
    need(schema_hash(c) == digest(canonical(expected)), 'SCHEMA_MISMATCH')


def verify(c, manifest_bytes, manifest):
    verify_identity(c)
    verify_schema(c)
    rows = list(execute(c, 'SELECT position,revision,sha256 FROM v2_migrations.applied ORDER BY position'))
    need([tuple(row) for row in rows] == [(m['position'],m['revision'],m['sha256']) for m in manifest['migrations']], 'LEDGER_MISMATCH')
    expected = digest(canonical(json.loads(checked_file(HERE / 'schema.expected.json'))))
    need(tuple(execute(c, 'SELECT profile,manifest_sha256,schema_sha256 FROM v2_migrations.installation WHERE singleton=1').one()) == ('fresh-v2-pilot',digest(manifest_bytes),expected), 'INSTALLATION_MISMATCH')
    need(execute(c, "SELECT count(*) FROM v2_demo.users WHERE account_origin='LOCAL' AND role='ADMIN' AND active").scalar_one() == 1, 'ADMIN_STATE_REJECTED')
    need(execute(c, "SELECT count(*) FROM v2_demo.first_admin_setup s JOIN v2_demo.users u ON u.id=s.admin_id WHERE s.singleton=1 AND u.account_origin='LOCAL'").scalar_one() == 1, 'ADMIN_SEAL_REJECTED')
    need(execute(c, "SELECT first_admin_initialized AND identity_initialized FROM v2_demo.schema_state WHERE version=1").scalar_one() is True, 'ADMIN_SEAL_REJECTED')
    need(execute(c, "SELECT count(*) FROM v2_demo.user_audit WHERE operation='FIRST_ADMIN_CREATE' AND result='SUCCESS'").scalar_one() == 1, 'ADMIN_AUDIT_REJECTED')
    need(execute(c, "SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND rolcanlogin FROM pg_roles WHERE rolname=:role", {'role':APP}).scalar_one() is True, 'APP_ROLE_UNSAFE')
    need(execute(c, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname IN ('public','v2_demo','v2_router_workspace','v2_subscriber_workspace','v2_migrations') AND r.rolname<>:owner", {'owner':OWNER}).scalar_one() == 0, 'OBJECT_OWNER_REJECTED')
    need(execute(c, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE n.nspname IN ('public','v2_demo','v2_router_workspace','v2_subscriber_workspace','v2_migrations') AND a.grantee=0").scalar_one() == 0, 'PUBLIC_TABLE_PRIVILEGES_UNSAFE')
    need(not execute(c, "SELECT has_schema_privilege(:role,'v2_migrations','USAGE') OR has_schema_privilege(:role,'public','CREATE') OR has_database_privilege(:role,current_database(),'CREATE')", {'role':APP}).scalar_one(), 'APP_PRIVILEGES_UNSAFE')


def migrate(c, manifest_bytes, manifest, sql, payload, uid, app_password):
    # The caller supplies ONE transaction, including 009, identity, audit and ledger.
    verify_identity(c)
    execute(c, "SELECT pg_advisory_xact_lock(5544218090)")
    execute(c, 'SET LOCAL search_path = public, pg_catalog')
    execute(c, "SET LOCAL timezone = 'UTC'")
    require_empty(c)
    execute_script(c, checked_file(HERE / 'ledger.sql').decode())
    from app.services.first_admin import create_local_admin
    for item, content in zip(manifest['migrations'], sql):
        execute_script(c, content)
        if item['position'] == 9:
            create_local_admin(c, payload, uid)
        execute(c, 'INSERT INTO v2_migrations.applied(position,revision,sha256) VALUES (:position,:revision,:sha256)', item)
    verify_schema(c)
    # Only locally generated hex, never input-interpolated SQL or printed credentials.
    need(len(app_password) == 64 and all(ch in '0123456789abcdef' for ch in app_password), 'GENERATED_SECRET_REJECTED')
    execute(c, f"CREATE ROLE {APP} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '{app_password}'")
    execute(c, f'REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC')
    execute(c, f'GRANT CONNECT ON DATABASE {DATABASE} TO {APP}')
    for schema in SCHEMAS:
        execute(c, f'REVOKE ALL ON SCHEMA {schema} FROM PUBLIC')
        execute(c, f'REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM PUBLIC')
        if schema != 'v2_migrations':
            execute(c, f'GRANT USAGE ON SCHEMA {schema} TO {APP}')
            execute(c, f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO {APP}')
    execute(c, 'INSERT INTO v2_migrations.installation VALUES (1,:profile,:manifest,:schema,clock_timestamp())',
        dict(profile='fresh-v2-pilot', manifest=digest(manifest_bytes), schema=schema_hash(c)))
    verify(c, manifest_bytes, manifest)


def secure_runtime():
    need(not any(key.startswith('PG') for key in os.environ) and 'V2_DATABASE_URL' not in os.environ, 'INHERITED_DATABASE_ENVIRONMENT_REJECTED')
    import pwd
    need(os.getuid() == pwd.getpwnam('mikrotik-v2-fresh-db').pw_uid and os.getuid() > 0, 'FRESH_DB_OS_OWNER_REQUIRED')
    for path in (ROOT, ROOT/'postgres', ROOT/'socket', ROOT/'config', ROOT/'backups'):
        need(path.is_dir() and not path.is_symlink(), 'RUNTIME_PATH_REJECTED')
        need(path.resolve() == path and not path.stat().st_mode & 0o022, 'RUNTIME_PATH_REJECTED')
    for path in (ROOT/'postgres', ROOT/'socket', ROOT/'config', ROOT/'backups'):
        need(path.stat().st_uid == os.getuid(), 'RUNTIME_OWNER_REJECTED')
    need(REPO == ROOT/'app', 'INSTALLED_SOURCE_REQUIRED')


def connect(database=DATABASE):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    return create_engine(URL.create('postgresql+psycopg', username=OWNER, database=database,
        query={'host':str(ROOT/'socket'), 'port':'55442'}), hide_parameters=True,
        connect_args={'connect_timeout':3, 'options':'-c statement_timeout=30000 -c lock_timeout=3000'})


def file_digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def backup(c, manifest_bytes, manifest, empty=False):
    from datetime import datetime, timezone
    import secrets
    if empty:
        verify_identity(c)
        require_empty(c)
    else:
        verify(c, manifest_bytes, manifest)
    directory = ROOT/'backups'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4))
    directory.mkdir(mode=0o700)
    dump = directory/'database.dump'
    # No inherited PGHOST/PGSERVICE/PGOPTIONS/PGPASSWORD and no DSN in argv/output.
    env = {'PATH':'/usr/bin:/bin', 'LC_ALL':'C'}
    args = ['/usr/lib/postgresql/16/bin/pg_dump','-h',str(ROOT/'socket'),'-p','55442','-U',OWNER,'-d',DATABASE,'-Fc','-f',str(dump)]
    need(subprocess.run(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0, 'BACKUP_FAILED')
    need(subprocess.run(['/usr/lib/postgresql/16/bin/pg_restore','--list',str(dump)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0, 'BACKUP_ARCHIVE_INVALID')
    dump.chmod(0o600)
    (directory/'receipt.json').write_text(json.dumps(dict(profile='fresh-v2-pilot',database=DATABASE,
        manifest_sha256=digest(manifest_bytes), dump_sha256=file_digest(dump),
        phase='EMPTY_PREIMAGE' if empty else 'INSTALLED', restore_drill='NOT_PERFORMED'),indent=2)+'\n')
    (directory/'receipt.json').chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check','create-database-approved','migrate-approved','verify','backup'), default='check', nargs='?')
    args = parser.parse_args()
    engine = None
    try:
        manifest_bytes, manifest, sql = check_sources()
        if args.action == 'check':
            print('PASS: OFFLINE_PROFILE_MANIFEST_VERIFIED; NO_CONNECTION_NO_INSTALL')
            return 0
        secure_runtime()
        os.umask(0o077)
        if args.action == 'migrate-approved':
            from app.first_admin import require_tty, collect_input
            require_tty()
        if args.action == 'create-database-approved':
            engine = connect('postgres')
            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
                verify_identity(c, 'postgres')
                databases = list(execute(c, "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY 1").scalars())
                need(databases == ['postgres'], 'DATABASE_ALREADY_EXISTS_OR_CLUSTER_NOT_FRESH')
                require_empty(c)
                execute(c, f"CREATE DATABASE {DATABASE} OWNER {OWNER} TEMPLATE template0 ENCODING 'UTF8'")
            print('PASS: FRESH_DATABASE_CREATED_EMPTY; NO_MIGRATION_OR_SERVICE_START')
            return 0
        engine = connect()
        if args.action == 'migrate-approved':
            # Fail before collecting identity on nonempty/wrong targets.
            with engine.begin() as c:
                verify_identity(c)
                require_empty(c)
                backup(c, manifest_bytes, manifest, empty=True)
            payload = collect_input()
            need(input('Yalnız YENI BOS pilot için KUR yazın: ') == 'KUR', 'CANCELLED')
            import secrets
            password = secrets.token_hex(32)
            # Reserve the new config with exclusive create BEFORE the transaction.
            envpath = ROOT/'config/database.env'
            with envpath.open('x') as output:
                output.write(f'V2_DATABASE_URL=postgresql+psycopg://{APP}:{password}@127.0.0.1:55442/{DATABASE}\n')
            envpath.chmod(0o640)
            with engine.begin() as c:
                migrate(c, manifest_bytes, manifest, sql, payload, os.getuid(), password)
            # Never start/enable services here. Backup must pass before a later API start.
            with engine.begin() as c:
                backup(c, manifest_bytes, manifest)
        else:
            with engine.begin() as c:
                execute(c, 'SET TRANSACTION READ ONLY')
                if args.action == 'verify':
                    verify(c, manifest_bytes, manifest)
                else:
                    backup(c, manifest_bytes, manifest)
        print('PASS: FRESH_PILOT_'+args.action.upper().replace('-','_'))
        return 0
    except Blocked as failure:
        print('BLOCKED: '+str(failure)+'; NO_RESET_NO_RESUME', file=sys.stderr)
        return 2
    except Exception:
        # All SQL/input/subprocess exception text is confidential; no traceback/DSN.
        print('BLOCKED: FRESH_PILOT_PRECONDITION_OR_OPERATION_FAILED; NO_RESET_NO_RESUME', file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
