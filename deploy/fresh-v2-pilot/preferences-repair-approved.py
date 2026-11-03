#!/usr/bin/env python3
"""Prepared remote executor. No action without separate explicit live approval.

Use the reviewed streamed bundle, not an application deployment. No migrations,
service commands, timer triggers, router access or HTTP preference writes.
"""
import argparse
import hashlib
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from uuid import UUID, uuid4
from datetime import datetime, timezone

ROOT = Path('/srv/mikrotik-manager-v2-fresh-pilot')
BASE = 'http://127.0.0.1:18090'
SCHEMAS = ('public', 'v2_demo', 'v2_router_workspace', 'v2_subscriber_workspace', 'v2_migrations')
EXPECTED_VALUES_SCHEMA_SHA256 = None  # Set only by the reviewed local bundle.


def main(argv=None):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import SQLAlchemyError
    from app.services.preferences_repair import RepairBlocked, require, lock, admin, inspect_default, repair, rollback
    from app.services.system_settings import Values
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'rollback'])
    parser.add_argument('--approved-live-default-repair', action='store_true')
    parser.add_argument('--request-id', required=True, type=UUID)
    parser.add_argument('--repair-id', type=UUID)
    args = parser.parse_args(argv)
    require(args.approved_live_default_repair, 'SEPARATE_LIVE_APPROVAL_REQUIRED')
    require(hashlib.sha256(json.dumps(Values.model_json_schema(), sort_keys=True).encode()).hexdigest()
            == EXPECTED_VALUES_SCHEMA_SHA256, 'INSTALLED_VALUES_MODEL_MISMATCH')
    require(os.geteuid() == 0, 'ROOT_OPERATOR_REQUIRED')
    for p in [ROOT, ROOT/'app', ROOT/'config', ROOT/'backups']:
        require(p.is_dir() and not p.is_symlink() and p.resolve() == p and not p.stat().st_mode & 0o022, 'PATH_REJECTED')
    for p in [ROOT/'admin-handoff.json', ROOT/'config/database.env']:
        info = p.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == 0 and not info.st_mode & 0o007, 'SECRET_FILE_REJECTED')
    jar = http.cookiejar.CookieJar()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPCookieProcessor(jar))
    engine = None
    evidence = None
    result = {'status': 'LIVE_PENDING', 'action': args.action, 'request_id': str(args.request_id)}

    def req(path, data=None):
        require(path in ['/api/health', '/api/v1/auth/login', '/api/v1/auth/logout', '/api/v1/auth/me', '/api/v1/preferences', '/api/v1/v1-inventory'], 'HTTP_SCOPE_REJECTED')
        request = urllib.request.Request(BASE+path, data=json.dumps(data).encode() if data is not None else None,
                                         headers={'Content-Type': 'application/json'})
        try:
            response = http.open(request, timeout=12)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read(1048576))

    def units():
        values = {}
        for unit in ['mikrotik-v2-fresh-pilot.service', 'mikrotik-v2-fresh-pilot-db.service', 'mikrotik-v2-health-transfer.timer']:
            r = subprocess.run(['systemctl', 'show', unit, '--property=MainPID,ActiveState,SubState,UnitFileState,ActiveEnterTimestampMonotonic'], capture_output=True, text=True, timeout=8)
            require(r.returncode == 0, 'UNIT_READ_FAILED')
            values[unit] = dict(line.split('=', 1) for line in r.stdout.strip().splitlines())
        require(all(v['ActiveState'] == 'active' for v in values.values()), 'SERVICE_NOT_ACTIVE')
        require(values['mikrotik-v2-health-transfer.timer']['UnitFileState'] == 'enabled', 'TIMER_NOT_ENABLED')
        return values

    def inventory():
        s, data = req('/api/v1/v1-inventory')
        require(s == 200 and data['source'] == 'V1_INVENTORY_EXPORT' and data['is_demo'] is False and len(data['items']) == 9, 'NINE_INVENTORY_REQUIRED')
        rows = sorted(({k: r[k] for k in ['id', 'name', 'identity', 'model', 'routeros_version']} for r in data['items']), key=lambda r:r['id'])
        return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()

    def identity(c):
        row = c.execute(text('SELECT current_database(),current_user,inet_server_port(),host(inet_server_addr())')).one()
        require(tuple(row) == ('mikrotik_manager_v2_fresh_pilot', 'v2_fresh_app', 55442, '127.0.0.1'), 'DATABASE_IDENTITY_REJECTED')
        require(c.execute(text("SELECT marker FROM v2_demo.schema_state WHERE version=1")).scalar_one() == 'mikrotik-manager-v2-synthetic-only', 'DATABASE_MARKER_REJECTED')

    def protected(c, excluded):
        # Digests are computed in PostgreSQL; rows, including password hashes,
        # never enter the receipt, logs or this process.
        hashes = {}
        tables = c.execute(text("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','v2_demo','v2_router_workspace','v2_subscriber_workspace') ORDER BY 1,2"))
        quote = c.dialect.identifier_preparer.quote_identifier
        for schema, table in tables:
            suffix = ''
            params = {}
            if (schema, table) == ('v2_demo', 'settings_records'):
                suffix = " WHERE id<>'default'"
            if (schema, table) == ('v2_demo', 'settings_audit'):
                suffix = ' WHERE id NOT IN (:repair,:rollback)'
                params = {'repair': str(excluded[0]), 'rollback': str(excluded[1])}
            sql = 'SELECT md5(COALESCE(string_agg(h,\'\' ORDER BY h),\'\')) FROM (SELECT md5(to_jsonb(t)::text) h FROM '+quote(schema)+'.'+quote(table)+' t'+suffix+') q'
            hashes[schema+'.'+table] = c.execute(text(sql), params).scalar_one()
        return hashes

    def save(name, data):
        with (evidence/name).open('x') as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(data, f, sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        fd = os.open(evidence, os.O_RDONLY | os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def owner_metadata():
        # The app role deliberately cannot read v2_migrations. Use the existing
        # owner peer transport for these SELECTs; do not grant app privileges.
        sql = """SELECT jsonb_build_object(
            'identity',jsonb_build_array(current_database(),current_user,current_setting('port'),current_setting('data_directory')),
            'installation',(SELECT jsonb_build_array(profile,manifest_sha256) FROM v2_migrations.installation WHERE singleton=1),
            'ledger',(SELECT jsonb_agg(jsonb_build_array(position,revision,sha256) ORDER BY position) FROM v2_migrations.applied),
            'role_safe',(SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND rolcanlogin FROM pg_roles WHERE rolname='v2_fresh_app'))::text;"""
        command = ['runuser','-u','mikrotik-v2-fresh-db','--','/usr/lib/postgresql/16/bin/psql',
                   '-X','-A','-t','--set=ON_ERROR_STOP=1','-h',str(ROOT/'socket'),'-p','55442',
                   '-U','v2_fresh_owner','-d','mikrotik_manager_v2_fresh_pilot','-c',sql]
        r = subprocess.run(command,capture_output=True,text=True,timeout=15,
                           env={'PATH':'/usr/bin:/bin','LC_ALL':'C','PGOPTIONS':'-c default_transaction_read_only=on -c statement_timeout=5000'})
        require(r.returncode == 0, 'OWNER_METADATA_READ_FAILED')
        value = json.loads(r.stdout)
        require(value['identity'] == ['mikrotik_manager_v2_fresh_pilot','v2_fresh_owner','55442',str(ROOT/'postgres')]
                and value['role_safe'] is True, 'OWNER_OR_ROLE_IDENTITY_REJECTED')
        return value

    def backup(c):
        snapshot = c.execute(text('SELECT pg_export_snapshot()')).scalar_one()
        output = evidence/'database-before.dump'
        # Existing owner peer transport only. No DB password in file/env/argv.
        command = ['runuser', '-u', 'mikrotik-v2-fresh-db', '--', '/usr/lib/postgresql/16/bin/pg_dump',
                   '-h', str(ROOT/'socket'), '-p', '55442', '-U', 'v2_fresh_owner', '-d', 'mikrotik_manager_v2_fresh_pilot',
                   '--format=custom', '--snapshot='+snapshot]
        with output.open('xb') as f:
            os.fchmod(f.fileno(), 0o600)
            r = subprocess.run(command, stdout=f, stderr=subprocess.DEVNULL, env={'PATH':'/usr/bin:/bin','LC_ALL':'C'}, timeout=90)
            f.flush(); os.fsync(f.fileno())
        require(r.returncode == 0 and output.stat().st_size > 0, 'BACKUP_FAILED')
        r = subprocess.run(['/usr/lib/postgresql/16/bin/pg_restore', '--list', str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        require(r.returncode == 0, 'BACKUP_ARCHIVE_INVALID')
        # Custom archive is a full independent pre-image. --list is not reported
        # as a restore drill; only the conditional row rollback is automatic tooling.
        return hashlib.sha256(output.read_bytes()).hexdigest()

    try:
        # Use the installed manifest/schema identity, never the new local manifest.
        spec = importlib.util.spec_from_file_location('installed_fresh_manage', ROOT/'app/deploy/fresh-v2-pilot/manage.py')
        installed = importlib.util.module_from_spec(spec); spec.loader.exec_module(installed)
        manifest_bytes, manifest, _ = installed.check_sources()
        before_owner = owner_metadata()
        require(before_owner['installation'] == ['fresh-v2-pilot',hashlib.sha256(manifest_bytes).hexdigest()], 'INSTALLED_LEDGER_REJECTED')
        require(before_owner['ledger'] == [[m['position'],m['revision'],m['sha256']] for m in manifest['migrations']], 'MIGRATION_LEDGER_REJECTED')
        values = {}
        for line in (ROOT/'config/database.env').read_text().splitlines():
            if line.startswith('V2_DATABASE_URL='):
                values['url'] = line.split('=', 1)[1]
        url = make_url(values['url'])
        require((url.drivername, url.host, url.port, url.database, url.username) ==
                ('postgresql+psycopg', '127.0.0.1', 55442, 'mikrotik_manager_v2_fresh_pilot', 'v2_fresh_app') and not url.query, 'DATABASE_URL_REJECTED')
        engine = create_engine(url, hide_parameters=True, connect_args={'connect_timeout':5, 'options':'-c statement_timeout=15000 -c lock_timeout=3000'})
        before_units = units()
        # Files whose contents must remain unchanged. Snapshot/status are naturally updated by timer.
        files = [ROOT/'admin-handoff.json', ROOT/'config/database.env']+list((ROOT/'app/backend/app').rglob('*.py'))
        before_files = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        credentials = json.loads((ROOT/'admin-handoff.json').read_text())
        s, user = req('/api/v1/auth/login', {k: credentials[k] for k in ['username','password']}); del credentials
        require(s == 200 and user['role_code'] == 'ADMIN' and user['can_manage_users'] is True and user['account_origin'] == 'LOCAL', 'LOCAL_ADMIN_REQUIRED')
        actor = user['id']
        s, health = req('/api/health')
        require(s == 200 and health['database_connected'] is True and health['device_adapters_connected'] is False, 'API_NOT_READY')
        before_inventory = inventory()
        exclude = (args.repair_id or args.request_id, args.request_id)
        with engine.begin() as c:
            identity(c)
            installed.verify_schema(c)
            lock(c); admin(c, actor)
            old = inspect_default(c)
            if args.action == 'apply' and old is not None:
                result.update(status='NOOP_EXISTING_VALID', changed=False)
            else:
                require(args.action == 'apply' or args.repair_id is not None, 'REPAIR_ID_REQUIRED')
                evidence = ROOT/'backups'/('preferences-default-'+str(args.request_id))
                evidence.mkdir(mode=0o700, exist_ok=False)
                before_data = protected(c, exclude)
                preimage = {'default_present':old is not None,'default':dict(payload=old['payload'],revision=old['revision'],updated_at=old['updated_at'].isoformat()) if old else None,
                            'protected':before_data,'units':before_units,'source_hashes':before_files,
                            'inventory_metadata_sha256':before_inventory,'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(), 'owner_metadata':before_owner}
                save('before.json', preimage)
                digest = backup(c)
                save('backup.json', {'sha256':digest,'archive_list_verified':True,'restore_drill':'NOT_PERFORMED','snapshot_exported':True})
                if args.action == 'apply':
                    changed = repair(c, actor, args.request_id, digest)
                else:
                    changed = rollback(c, actor, args.repair_id, args.request_id)
                require(protected(c, exclude) == before_data, 'PROTECTED_DATA_CHANGED')
                require(owner_metadata() == before_owner, 'OWNER_METADATA_CHANGED')
                installed.verify_schema(c)
                require(units() == before_units, 'SERVICE_STATE_CHANGED')
                require({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files} == before_files, 'PROTECTED_FILES_CHANGED')
                result.update(changed)
                save('transaction-ready.json', result)
        # This point is after commit. Failure is reported as committed but not accepted;
        # never delete a record automatically or restore the whole database.
        result['transaction_committed'] = True
        s, preferences = req('/api/v1/preferences')
        if args.action == 'apply':
            require(s == 200 and preferences['storage_ready'] is True, 'POST_COMMIT_PREFERENCES_NOT_READY')
            Values.model_validate(preferences['values'])
        else:
            require(s == 503, 'ROLLBACK_HTTP_NOT_RESTORED')
        require(inventory() == before_inventory and units() == before_units, 'POST_COMMIT_PROTECTION_FAILED')
        require(owner_metadata() == before_owner, 'POST_COMMIT_OWNER_METADATA_CHANGED')
        with engine.connect() as c:
            if evidence:
                require(protected(c, exclude) == before_data, 'POST_COMMIT_PROTECTED_DATA_CHANGED')
            row = inspect_default(c)
            require((row is not None) == (args.action == 'apply'), 'POST_COMMIT_DEFAULT_STATE_INVALID')
        result.update(status='LIVE_ACCEPTED' if args.action == 'apply' else 'ROLLBACK_VERIFIED', http_status=s,
                      protected_data_unchanged=True, service_timer_unchanged=True)
    except RepairBlocked as error:
        result.update(status='BLOCKED', error_code=str(error))
    except SQLAlchemyError:
        result.update(status='BLOCKED', error_code='DATABASE_UNAVAILABLE')
    except Exception:
        result.update(status='BLOCKED', error_code='MAINTENANCE_PRECONDITION_OR_OPERATION_FAILED')
    finally:
        if list(jar):
            try:
                s, _ = req('/api/v1/auth/logout', {}); me, _ = req('/api/v1/auth/me')
                result['session_closed'] = s == 200 and me == 401
                if not result['session_closed']:
                    result.update(status='BLOCKED', error_code='SESSION_CLEANUP_FAILED')
            except Exception:
                result.update(status='BLOCKED', error_code='SESSION_CLEANUP_FAILED')
        jar.clear()
        if engine:
            engine.dispose()
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        if evidence:
            try:save('receipt.json', result)
            except Exception:result.update(status='BLOCKED', error_code='RECEIPT_WRITE_FAILED')
        print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('LIVE_ACCEPTED','ROLLBACK_VERIFIED') else 2


if __name__ == '__main__':
    # An installed source file is not a deployment instruction or implicit approval.
    sys.path.insert(0, str(ROOT/'app/backend'))
    sys.exit(main())
