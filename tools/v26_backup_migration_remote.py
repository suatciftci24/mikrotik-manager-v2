"""Remote isolated acceptance worker. Invoked only by the office launcher."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

PG = Path('/usr/lib/postgresql/16/bin')
BACKUP = Path('/home/mikadmin/v26-predeploy-20261116T061246Z/database.dump')
DB = 'mikrotik_v26_acceptance'
ROLE = 'v26_acceptance'
APP = Path('/srv/mikrotik-v26-next')

CATALOG = """SELECT json_build_object(
 'columns', (SELECT json_agg(x ORDER BY x.table_name,x.ordinal_position) FROM
  (SELECT table_name,column_name,ordinal_position,data_type,udt_name,
          character_maximum_length,is_nullable,column_default
   FROM information_schema.columns WHERE table_schema='v2_subscriber_workspace'
   AND table_name IN ('packages','package_events')) x),
 'constraints',(SELECT json_agg(x ORDER BY x.table_name,x.definition) FROM
  (SELECT c.relname AS table_name,pg_get_constraintdef(k.oid) AS definition
   FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
   JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='v2_subscriber_workspace'
   AND c.relname IN ('packages','package_events')) x),
 'indexes',(SELECT json_agg(x ORDER BY x.tablename,x.indexname) FROM
  (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='v2_subscriber_workspace'
   AND tablename IN ('packages','package_events')) x));"""


def run(args, *, sql=None, timeout=60):
    result = subprocess.run([str(a) for a in args], input=sql, text=True,
                            capture_output=True, timeout=timeout,
                            env={k:v for k,v in os.environ.items() if not k.startswith('PG')})
    if result.returncode:
        # Never expose SQL errors with row data, dump contents or credentials.
        raise RuntimeError('COMMAND_FAILED:' + Path(str(args[0])).name)
    return result.stdout.strip()


def live_catalog():
    # Peer access must already be authorized; no permission or role changes.
    sql = """BEGIN READ ONLY;
    SELECT current_database() || ':' || current_setting('port') || ':' || current_setting('data_directory');
    """ + CATALOG + '\nROLLBACK;'
    output = run(['sudo','-n','-u','postgres',str(PG/'psql'),'-X','-qAt',
                  '-v','ON_ERROR_STOP=1','-h','/var/run/postgresql','-p','55433','-d',DB], sql=sql)
    lines = output.splitlines()
    if len(lines) != 2 or lines[0] != DB + ':55433:/var/lib/postgresql/16/v26':
        raise RuntimeError('LIVE_TARGET_REJECTED')
    return json.loads(lines[1])


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def snapshot(query):
    tables = json.loads(query("""SELECT coalesce(json_agg(x ORDER BY x.s,x.t),'[]') FROM
     (SELECT schemaname AS s,tablename AS t FROM pg_tables
      WHERE schemaname NOT IN ('pg_catalog','information_schema')
      AND schemaname NOT LIKE 'pg_toast%') x;"""))
    hashes = {}
    for table in tables:
        name = quote_identifier(table['s'])+'.'+quote_identifier(table['t'])
        # Raw data stays in process memory, never logs or stdout.
        data = query('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\') FROM '+name+' t;')
        hashes[name] = hashlib.sha256(data.encode()).hexdigest()
    return hashes


def assert_preserved(before, after):
    if any(after.get(name) != digest for name,digest in before.items()):
        raise RuntimeError('RESTORED_DATA_CHANGED')
    allowed = {'"v2_subscriber_workspace"."packages"', '"v2_subscriber_workspace"."package_events"'}
    if set(after)-set(before)-allowed:
        raise RuntimeError('UNEXPECTED_SCHEMA_CHANGE')


def main():
    root = None
    data = None
    report = {'status':'BLOCKED','live_modified':False,'backup':str(BACKUP)}
    try:
        info = BACKUP.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError('BACKUP_OWNER_OR_TYPE_REJECTED')
        head = run(['git','-C',APP,'rev-parse','HEAD'])
        if head != 'b4e78a44685f83e58bb37684712236a33c5ccbaf':
            raise RuntimeError('VDS_BASELINE_CHANGED')
        if run(['git','-C',APP,'status','--porcelain=v1']):
            raise RuntimeError('VDS_WORKTREE_DIRTY')
        live = live_catalog()
        root = Path(tempfile.mkdtemp(prefix='v26-backup-011-',dir='/home/mikadmin'))
        report['evidence_root'] = str(root)
        data = root/'pgdata'
        socket = root/'socket'
        socket.mkdir(mode=0o700)
        # Copy exact backup bytes into private absent-only path; source is untouched.
        frozen = root/'database.dump'
        digest = hashlib.sha256()
        with BACKUP.open('rb') as source, frozen.open('xb') as target:
            while chunk := source.read(1024*1024):
                digest.update(chunk)
                target.write(chunk)
        frozen.chmod(0o600)
        if BACKUP.stat().st_size != frozen.stat().st_size or BACKUP.stat().st_mtime_ns != info.st_mtime_ns:
            raise RuntimeError('BACKUP_CHANGED_DURING_COPY')
        report['backup_sha256'] = digest.hexdigest()
        run([PG/'pg_restore','--list',frozen])
        run([PG/'initdb','-D',data,'-U',ROLE,'--auth-local=trust','--auth-host=reject','--no-locale'])
        run([PG/'pg_ctl','-D',data,'-l',root/'postgres.log','-o',
             "-c listen_addresses='' -p 55433 -k "+str(socket),'-w','-t','30','start'],timeout=40)
        base = [PG/'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-h',socket,'-p','55433','-U',ROLE,'-d',DB]
        run([PG/'createdb','-h',socket,'-p','55433','-U',ROLE,DB])
        def query(sql):
            return run(base,sql=sql)
        if query('SHOW data_directory;') != str(data):
            raise RuntimeError('ISOLATED_DATA_DIRECTORY_REJECTED')
        run([PG/'pg_restore','--exit-on-error','--single-transaction','--no-owner','--no-acl',
             '-h',socket,'-p','55433','-U',ROLE,'-d',DB,frozen],timeout=180)
        restored = json.loads(query(CATALOG))
        if restored != live:
            raise RuntimeError('LIVE_AND_BACKUP_PACKAGE_SCHEMA_DIFFER')
        before = snapshot(query)
        admins = query("SELECT count(*) FROM v26_acceptance.users WHERE role='ADMIN' AND active IS TRUE;")
        if int(admins) < 1:
            raise RuntimeError('ACTIVE_ADMIN_REQUIRED')
        # MIGRATION_SQL injected from the pinned office checkout by the launcher.
        query(MIGRATION_SQL)
        first = snapshot(query)
        assert_preserved(before,first)
        schema_first = query(CATALOG)
        query(MIGRATION_SQL)
        second = snapshot(query)
        if first != second or query(CATALOG) != schema_first:
            raise RuntimeError('MIGRATION_NOT_IDEMPOTENT')
        # Detect live schema drift during the isolated acceptance window.
        if live_catalog() != live or run(['git','-C',APP,'rev-parse','HEAD']) != head:
            raise RuntimeError('LIVE_BASELINE_DRIFT')
        report.update(status='PASS',source_commit=globals().get('SOURCE_COMMIT','NOT_PINNED'),
                      vds_commit=head,active_admins=int(admins),
                      existing_tables_preserved=len(before),migration_runs=2,
                      migration_sha256=hashlib.sha256(MIGRATION_SQL.encode()).hexdigest(),
                      package_schema_match=True,deployment_enabled=False)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        report['reason'] = str(error) if isinstance(error,RuntimeError) else type(error).__name__
    finally:
        if data is not None and (data/'postmaster.pid').exists():
            try:
                pid_lines = (data/'postmaster.pid').read_text().splitlines()
                if len(pid_lines)<2 or Path(pid_lines[1]) != data:
                    raise RuntimeError('OWNED_CLUSTER_IDENTITY_REJECTED')
                run([PG/'pg_ctl','-D',data,'-m','fast','-w','-t','30','stop'],timeout=40)
            except (OSError,RuntimeError,subprocess.SubprocessError):
                report.update(status='BLOCKED',reason='ISOLATED_CLUSTER_STOP_UNCONFIRMED')
        if root:
            path = root/'result.json'
            path.write_text(json.dumps(report,indent=2)+'\n')
            path.chmod(0o600)
        print(json.dumps(report,sort_keys=True))
    return 0 if report['status']=='PASS' else 1
