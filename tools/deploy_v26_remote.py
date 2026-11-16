"""Authorized V26-only deployment worker; no deletion or automatic DB restore."""
import base64
import ctypes
import fcntl
import hashlib
import http.cookiejar
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.request

# HELPER_SOURCE, MIGRATION_SQL, TARGET, DIST_B64, DIST_SHA, ADMIN are injected via SSH stdin.
BASELINE = 'b4e78a44685f83e58bb37684712236a33c5ccbaf'
APP = Path('/srv/mikrotik-v26-next')
BACKUP = Path('/home/mikadmin/v26-predeploy-20261116T061246Z/database.dump')
STASH = 'v26-vds-predeploy-20261116T062025Z'
ORIGIN = 'https://v26.mikmanager.com.tr'


def require(condition, code):
    if not condition:raise RuntimeError(code)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):value.update(chunk)
    return value.hexdigest()


def tree_hash(path):
    value = hashlib.sha256()
    require(path.is_dir() and not path.is_symlink(),'DIST_PATH_REJECTED')
    for item in sorted(path.rglob('*')):
        require(not item.is_symlink(),'DIST_SYMLINK_REJECTED')
        if item.is_file():
            value.update(str(item.relative_to(path)).encode()+b'\0'+digest(item).encode()+b'\0')
    return value.hexdigest()


def exchange(left,right):
    libc = ctypes.CDLL(None,use_errno=True)
    result = libc.renameat2(-100,os.fsencode(left),-100,os.fsencode(right),2)
    if result:raise RuntimeError('ATOMIC_DIST_EXCHANGE_FAILED')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def client():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),
             urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(opener,path,body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(ORIGIN+path,data=data,
                                 headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=15) as response:
        require(response.status==200,'HTTPS_STATUS_REJECTED')
        return response.read()


def ready(opener):
    value = json.loads(request(opener,'/api/ready'))
    require(value.get('service')=='mikrotik-manager-v2' and
            value.get('runtime_profile')=='v26-isolated-acceptance' and
            value.get('api_version')=='v1' and value.get('api_port')==18996,
            'HTTPS_API_IDENTITY_REJECTED')


def admin_check(opener, *, panel=False):
    user = json.loads(request(opener,'/api/v1/auth/login',ADMIN))
    try:
        require(user.get('role_code')=='ADMIN','ADMIN_LOGIN_REJECTED')
        me = json.loads(request(opener,'/api/v1/auth/me'))
        require(me.get('id')==user.get('id') and me.get('role_code')=='ADMIN','ADMIN_SESSION_REJECTED')
        if panel:
            for path in ['/api/v1/dashboard/summary','/api/v1/router-workspace/routers',
                         '/api/v1/subscriber-workspace','/api/v1/packages']:
                data = json.loads(request(opener,path))
                require(isinstance(data,dict),'PANEL_JSON_REJECTED')
                if path.endswith('/summary'):
                    require(isinstance(data.get('summary'),dict) and
                            all(type(data['summary'].get(key)) is int and data['summary'][key]>=0
                                for key in ('router_count','subscribers_total')),'DASHBOARD_CONTRACT_REJECTED')
                else:
                    require(isinstance(data.get('items'),list) and type(data.get('total')) is int
                            and data['total']>=0,'WORKSPACE_CONTRACT_REJECTED')
    finally:
        request(opener,'/api/v1/auth/logout',{})


def stash_pin(run):
    lines = run(['git','-C',APP,'stash','list','--format=%H %gs'],stage='STASH_VERIFY').splitlines()
    matches = [line.split(' ',1)[0] for line in lines if STASH in line.partition(' ')[2]]
    require(len(matches)==1 and re.fullmatch('[0-9a-f]{40}',matches[0]),'STASH_LABEL_REJECTED')
    return tuple(lines),matches[0]


def evidence():
    info = BACKUP.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid(),'BACKUP_OWNER_OR_TYPE_REJECTED')
    expected = digest(BACKUP)
    for path in sorted(Path('/home/mikadmin').glob('v26-backup-011-*/result.json'),reverse=True):
        if path.is_symlink() or path.parent.is_symlink():continue
        if path.stat().st_uid!=os.getuid() or path.parent.stat().st_mode & 0o077:continue
        value = json.loads(path.read_text())
        if value.get('status')=='PASS' and value.get('source_commit')==TARGET:
            require(value.get('vds_commit')==BASELINE and value.get('migration_runs')==2 and
                    value.get('package_schema_match') is True and
                    value.get('existing_tables_preserved')==17 and value.get('active_admins',0)>0 and
                    value.get('backup')==str(BACKUP) and value.get('backup_sha256')==expected and
                    value.get('migration_sha256')==hashlib.sha256(MIGRATION_SQL.encode()).hexdigest(),
                    'ACCEPTANCE_EVIDENCE_MISMATCH')
            return str(path),expected
    raise RuntimeError('PINNED_ISOLATED_ACCEPTANCE_REQUIRED')


def services(run):
    names = run(['systemctl','list-units','--type=service','--state=running','--no-legend','--plain'],
                stage='SERVICE_INVENTORY').splitlines()
    selected = []
    for line in names:
        name = line.split()[0]
        if 'v26' not in name or not re.fullmatch(r'[A-Za-z0-9_.@-]+\.service',name):continue
        def prop(key):
            return run(['systemctl','show',name,'--value','--property='+key],stage='SERVICE_IDENTITY')
        cwd = prop('WorkingDirectory')
        if cwd not in [str(APP),str(APP/'backend'),str(APP/'frontend')]:continue
        executable = prop('ExecStart')
        require(str(APP) in executable and '--reload' not in executable,'SERVICE_EXEC_REJECTED')
        pid = prop('MainPID')
        require(pid.isdigit() and int(pid)>1,'SERVICE_PID_REJECTED')
        # Read only this already-pinned V26 process environment; never print it.
        environment = subprocess.run(['sudo','-n','cat','/proc/'+pid+'/environ'],
                                     capture_output=True,timeout=10)
        require(environment.returncode==0,'SERVICE_ENV_UNREADABLE')
        values = dict(item.split(b'=',1) for item in environment.stdout.split(b'\0') if b'=' in item)
        if b'V2_DATABASE_URL' in values:
            from urllib.parse import urlsplit,unquote
            url = urlsplit(values[b'V2_DATABASE_URL'].decode())
            require(url.scheme in ('postgresql','postgresql+psycopg','postgresql+psycopg2')
                    and url.hostname=='127.0.0.1' and url.port==55433 and
                    url.path=='/mikrotik_v26_acceptance' and unquote(url.username or '')=='v26_acceptance'
                    and not url.query and not url.fragment,'SERVICE_DATABASE_REJECTED')
            require(values.get(b'V2_DEPLOYMENT_PROFILE')==b'v26-isolated-acceptance','SERVICE_PROFILE_REJECTED')
            selected.append((name,True))
        else:
            require(cwd==str(APP/'frontend'),'SERVICE_SCOPE_REJECTED')
            selected.append((name,False))
    require(sum(api for _,api in selected)==1,'SINGLE_V26_API_SERVICE_REQUIRED')
    return selected


def main():
    namespace = {'__name__':'v26_acceptance_helper'}
    exec(HELPER_SOURCE,namespace)
    run = namespace['run']
    def git(*args,stage='GIT'):
        return run(['git','-C',APP,*args],stage=stage)
    def query(sql, *, stage):
        return run(['sudo','-n','-u','postgres','/usr/lib/postgresql/16/bin/psql',
                    '-X','-qAt','-v','ON_ERROR_STOP=1','-v','VERBOSITY=sqlstate',
                    '-h','/var/run/postgresql','-p','55433','-d','mikrotik_v26_acceptance'],
                   stage=stage,sql='BEGIN READ ONLY;\n'+sql+'\nROLLBACK;')
    report = dict(status='BLOCKED',target_commit=TARGET,live_commit='NOT_VERIFIED',
                  db_restore_performed=False,migration='NOT_RUN',https='NOT_VERIFIED')
    root = None
    code_changed = False
    swapped = False
    units = []
    lock = None
    stage = 'PREFLIGHT'
    def interrupted(*_):raise RuntimeError('DEPLOYMENT_INTERRUPTED')
    for number in (signal.SIGHUP,signal.SIGTERM,signal.SIGINT):signal.signal(number,interrupted)
    try:
        require(APP.is_dir() and APP.resolve()==APP,'APP_PATH_REJECTED')
        for child in (APP/'.git',APP/'backend',APP/'frontend'):
            require(child.is_dir() and child.resolve()==child,'APP_COMPONENT_REJECTED')
        descriptor = os.open(APP/'.git/v26-deploy.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        lock = os.fdopen(descriptor,'a')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(git('rev-parse','HEAD')==BASELINE,'VDS_BASELINE_CHANGED')
        report['live_commit'] = BASELINE
        require(not git('status','--porcelain=v1'),'VDS_WORKTREE_DIRTY')
        stashes,stash_id = stash_pin(run)
        proof,backup_hash = evidence()
        live_catalog = namespace['live_catalog']()
        units = services(run)
        opener = client()
        ready(opener)
        admin_check(opener)
        old_dist = APP/'frontend/dist'
        old_hash = tree_hash(old_dist)
        require(request(opener,'/')==(old_dist/'index.html').read_bytes(),'HTTPS_WEBROOT_REJECTED')
        before = namespace['snapshot'](query,stage='LIVE_SNAPSHOT_BEFORE')
        require(int(query("SELECT count(*) FROM v26_acceptance.users WHERE role='ADMIN' AND active IS TRUE;",
                          stage='LIVE_ADMIN_COUNT'))>0,'ACTIVE_ADMIN_REQUIRED')
        root = Path(tempfile.mkdtemp(prefix='v26-live-',dir=APP/'.git'))
        report.update(evidence_root=str(root),backup_sha256=backup_hash,acceptance_evidence=proof,stash_oid=stash_id)
        bundle = base64.b64decode(DIST_B64,validate=True)
        require(hashlib.sha256(bundle).hexdigest()==DIST_SHA,'DIST_HASH_REJECTED')
        with tarfile.open(fileobj=io.BytesIO(bundle)) as archive:
            for member in archive.getmembers():
                require((member.name=='dist' or member.name.startswith('dist/')) and
                        not member.issym() and not member.islnk() and '..' not in Path(member.name).parts
                        and (member.isfile() or member.isdir()),'DIST_ARCHIVE_REJECTED')
            archive.extractall(root,filter='data')
        candidate = root/'dist'
        require((candidate/'index.html').is_file(),'DIST_INDEX_REQUIRED')
        # Retain hashed assets needed by browsers opened before cutover.
        for item in (old_dist/'assets').rglob('*'):
            if not item.is_file():continue
            dest = candidate/'assets'/item.relative_to(old_dist/'assets')
            if dest.exists():require(digest(dest)==digest(item),'ASSET_COLLISION')
            else:
                import shutil
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(item,dest)
        new_hash = tree_hash(candidate)
        require(old_dist.stat().st_dev==candidate.stat().st_dev,'DIST_FILESYSTEM_MISMATCH')
        # Verify exchange syscall before touching the live webroot.
        a,b = root/'exchange-a',root/'exchange-b'
        a.mkdir();b.mkdir();exchange(a,b)
        git('fetch','origin',TARGET,stage='TARGET_FETCH')
        require(git('rev-parse',TARGET+'^{commit}')==TARGET,'TARGET_COMMIT_REJECTED')
        git('merge-base','--is-ancestor',BASELINE,TARGET,stage='TARGET_ANCESTRY')
        require(git('rev-parse','HEAD')==BASELINE and not git('status','--porcelain=v1'),'PREDEPLOY_DRIFT')
        require(stash_pin(run)==(stashes,stash_id) and services(run)==units,'PREDEPLOY_SCOPE_DRIFT')
        require(digest(BACKUP)==backup_hash and namespace['live_catalog']()==live_catalog,'BACKUP_OR_CATALOG_DRIFT')
        git('bundle','create',str(root/'baseline.bundle'),'HEAD',stage='CODE_BACKUP')
        stage = 'MIGRATION'
        # If present, exact 011 validation runs read-only; no live DDL is needed.
        if live_catalog['columns'] is not None:
            validation = MIGRATION_SQL.replace('BEGIN;','BEGIN READ ONLY;',1)
            run(['sudo','-n','-u','postgres','/usr/lib/postgresql/16/bin/psql','-X','-qAt',
                 '-v','ON_ERROR_STOP=1','-v','VERBOSITY=sqlstate','-h','/var/run/postgresql',
                 '-p','55433','-d','mikrotik_v26_acceptance'],stage='LIVE_011_VALIDATE',
                sql='SET ROLE v26_acceptance;\n'+validation)
            report['migration']='COMPATIBLE_NOOP'
        else:
            require(live_catalog['constraints'] is None and live_catalog['indexes'] is None,'PARTIAL_CATALOG_REJECTED')
            report['migration']='ATTEMPTED_RECHECK_REQUIRED'
            run(['sudo','-n','-u','postgres','/usr/lib/postgresql/16/bin/psql','-X','-qAt',
                 '-v','ON_ERROR_STOP=1','-v','VERBOSITY=sqlstate','-h','/var/run/postgresql',
                 '-p','55433','-d','mikrotik_v26_acceptance'],stage='LIVE_011_APPLY',
                sql='SET ROLE v26_acceptance;\n'+MIGRATION_SQL)
            report['migration']='APPLIED_011'
        stage = 'CODE_UPDATE'
        code_changed = True
        git('merge','--ff-only',TARGET,stage='CODE_FAST_FORWARD')
        exchange(old_dist,candidate)
        swapped = True
        stage = 'V26_RESTART'
        for unit,_ in units:run(['sudo','-n','systemctl','restart',unit],stage='V26_RESTART')
        stage = 'ACCEPTANCE'
        last = None
        for _ in range(15):
            try:ready(opener);last=None;break
            except Exception as error:last=error;time.sleep(1)
        require(last is None,'HTTPS_API_ACCEPTANCE_FAILED')
        admin_check(opener,panel=True)
        require(request(opener,'/')==(old_dist/'index.html').read_bytes(),'HTTPS_INDEX_MISMATCH')
        html = (old_dist/'index.html').read_text()
        assets = re.findall(r'(?:src|href)="(/assets/[^"?#]+)"',html)
        require(any(asset.endswith('.js') for asset in assets),'PANEL_ENTRYPOINT_REQUIRED')
        for asset in assets:
            require('..' not in asset,'ASSET_PATH_REJECTED')
            require(request(opener,asset)==(old_dist/asset.lstrip('/')).read_bytes(),'HTTPS_ASSET_MISMATCH')
        after = namespace['snapshot'](query,stage='LIVE_SNAPSHOT_AFTER')
        namespace['assert_preserved'](before,after)
        require(stash_pin(run)==(stashes,stash_id),'STASH_CHANGED')
        require(git('rev-parse','HEAD')==TARGET,'LIVE_COMMIT_MISMATCH')
        require(services(run)==units,'POSTDEPLOY_SERVICE_SCOPE_DRIFT')
        for unit,_ in units:require(run(['systemctl','is-active',unit],stage='SERVICE_HEALTH')=='active','SERVICE_NOT_ACTIVE')
        report.update(status='PASS',live_commit=TARGET,https='PASS',admin_login='PASS',
                      panel_acceptance='HTTP_READ_ONLY_PASS',preserved_tables=len(before),
                      dist_backup=str(candidate),services=[unit for unit,_ in units])
    except (Exception,KeyboardInterrupt) as error:
        report.update(failed_stage=stage,reason=str(error) if isinstance(error,RuntimeError) else type(error).__name__)
        if isinstance(error,namespace['CommandFailure']):report.update(error.details)
        if code_changed:
            try:
                require(git('rev-parse','HEAD')==TARGET and not git('status','--porcelain=v1','--untracked-files=no'),
                        'ROLLBACK_CODE_DRIFT')
                if swapped:
                    require(tree_hash(old_dist)==new_hash and tree_hash(candidate)==old_hash,'ROLLBACK_DIST_DRIFT')
                git('switch','--detach',BASELINE,stage='CODE_ROLLBACK')
                if swapped:exchange(old_dist,candidate)
                for unit,_ in units:run(['sudo','-n','systemctl','restart',unit],stage='ROLLBACK_V26_RESTART')
                rollback_client = client()
                ready(rollback_client)
                admin_check(rollback_client)
                require(tree_hash(old_dist)==old_hash and
                        request(rollback_client,'/')==(old_dist/'index.html').read_bytes(),'ROLLBACK_WEBROOT_MISMATCH')
                require(stash_pin(run)==(stashes,stash_id),'ROLLBACK_STASH_CHANGED')
                report.update(live_commit=BASELINE,rollback='CODE_VERIFIED',https='PASS_AFTER_ROLLBACK')
            except Exception:
                report['rollback']='BLOCKED_REQUIRES_REVIEW'
        report['db_restore_performed']=False
        if str(error)=='RESTORED_DATA_CHANGED':report['db_review_required']=True
    finally:
        if code_changed:
            try:
                observed = git('rev-parse','HEAD',stage='FINAL_LIVE_HEAD')
                report['live_commit'] = observed if re.fullmatch('[0-9a-f]{40}',observed) else 'NOT_VERIFIED'
            except Exception:report['live_commit']='NOT_VERIFIED'
        if root:
            result = root/'deployment-result.json'
            result.write_text(json.dumps(report,indent=2)+'\n');result.chmod(0o600)
        if lock:lock.close()
        ADMIN.clear()
        print(json.dumps(report,sort_keys=True))
    return 0 if report['status']=='PASS' else 1
