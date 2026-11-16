"""V26-only static/release bootstrap. Called through a length-framed SSH channel."""
import base64
import contextlib
import fcntl
import hashlib
import io
import importlib.util
import marshal
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

# POLICY, LEGACY, HELPER, WEBROOT, TARGET, SOURCE_B64, DIST_B64, DIST_SHA, ADMIN, ACTION injected.
exec(POLICY,globals())
APP_PATH=Path(APP)
ROOT=APP_PATH/'.local/central'


def load(source,values=None):
    namespace={'__name__':'central_helper',**(values or {})}
    exec(source,namespace)
    return namespace


H=load(HELPER)
L=load(LEGACY,dict(HELPER_SOURCE=HELPER,WEBROOT_SOURCE=WEBROOT,ADMIN=ADMIN))
W=load(WEBROOT)
D=load(DIAGNOSTICS)
run=H['run']


def git(*args):return run(['git','-C',APP,*args],stage='CENTRAL_GIT')


def query(sql,*,stage='CENTRAL_DB_READ'):
    return run(['sudo','-n','-u','postgres','/usr/lib/postgresql/16/bin/psql','-X','-qAt',
                '-v','ON_ERROR_STOP=1','-v','VERBOSITY=sqlstate','-h','/var/run/postgresql',
                '-p','55433','-d',DB],stage=stage,sql='BEGIN READ ONLY;\n'+sql+'\nROLLBACK;')


def db_identity():
    value=json.loads(query("""SELECT json_build_object('database',current_database(),
     'port',current_setting('port'),'data_directory',current_setting('data_directory'),
     'system_identifier',(SELECT system_identifier::text FROM pg_control_system()),
     'oid',(SELECT oid::text FROM pg_database WHERE datname=current_database()));"""))
    return database_fingerprint(value)


def private_json(path,value):
    require(not path.exists(),'PRIVATE_RECEIPT_ALREADY_EXISTS')
    path.write_text(json.dumps(value,indent=2)+'\n');path.chmod(0o600)


def unit_properties(unit):
    require(re.fullmatch(r'[A-Za-z0-9_.@-]+\.service',unit) and 'v26' in unit,'UNIT_SCOPE_REJECTED')
    return {key:run(['systemctl','show',unit,'--value','--property='+key],stage='CENTRAL_UNIT_READ')
            for key in ('WorkingDirectory','ExecStart','User','Group','MainPID','Type','KillMode',
                        'ExecStartPre','ExecStartPost','ExecStop','ExecStopPost')}


def installed_units(profile):
    require(profile['origin']==ORIGIN and profile['checkout']==APP and profile['database']==db_identity(),
            'INSTALLED_CENTRAL_BINDING_CHANGED')
    release=ROOT/'releases'/profile['commit']
    require(re.fullmatch('[0-9a-f]{40}',profile['commit']) is not None and profile['release']==str(release),
            'INSTALLED_RELEASE_REJECTED')
    require(len(profile['units'])==2 and sum(bool(api) for unit,api in profile['units'])==1,'CENTRAL_UNIT_SET_REJECTED')
    expected_api=[str(APP_PATH/'.venv/bin/python'),'-P','-B','-m','uvicorn','app.main:app','--app-dir',str(release/'backend'),
                  '--host','127.0.0.1','--port','18996']
    require(profile['api_argv']==expected_api and profile['web_argv'][:2]==['/usr/sbin/nginx','-c']
            and len(profile['web_argv'])==5 and profile['web_argv'][3]=='-p'
            and all(str(path).startswith(str(ROOT)+'/attempt-') and Path(path).resolve()==Path(path)
                    for path in (profile['web_argv'][2],profile['web_argv'][4])),'CENTRAL_EXEC_BINDING_REJECTED')
    for unit,api in profile['units']:
        value=unit_properties(unit)
        require(value['User']==value['Group']=='mikadmin' and
                value['WorkingDirectory']==str(APP_PATH if api else APP_PATH/'frontend'),'CENTRAL_UNIT_SCOPE_CHANGED')
        require(value['Type']=='simple' and value['KillMode']=='control-group' and
                not any(value[key] for key in ('ExecStartPre','ExecStartPost','ExecStop','ExecStopPost')),
                'CENTRAL_UNIT_HOOKS_REJECTED')
        expected=profile['api_argv'] if api else profile['web_argv']
        require(L['service_exec_argv'](value['ExecStart'])==expected,'CENTRAL_UNIT_EXEC_CHANGED')
        require(value['MainPID'].isdigit() and int(value['MainPID'])>1,'CENTRAL_UNIT_NOT_RUNNING')
        env=run(['sudo','-n','cat','/proc/'+value['MainPID']+'/environ'],stage='CENTRAL_ENV_READ')
        if api:
            values=dict(item.split('=',1) for item in env.split('\0') if '=' in item)
            from urllib.parse import urlsplit,unquote
            url=urlsplit(values.get('V2_DATABASE_URL',''))
            require(url.scheme=='postgresql+psycopg' and url.hostname=='127.0.0.1' and url.port==55433
                    and url.path=='/'+DB and unquote(url.username or '')=='v26_acceptance' and not url.query,
                    'CENTRAL_RUNTIME_DATABASE_CHANGED')
            require(values.get('V2_DEPLOYMENT_PROFILE')=='v26-isolated-acceptance' and
                    values.get('V2_SESSION_SECURE')=='true' and values.get('V2_ROUTER_ONBOARDING_ENABLED')=='false'
                    and values.get('V2_CEBECI_API_SSL_ENABLED')=='false','CENTRAL_RUNTIME_PROFILE_CHANGED')
    return profile['units']


def verified_source_cache(release,name,expected_files):
    """Accept only byte-for-byte compiler output of an already verified Git blob.

    Never import/unmarshal an extra file. A suffix or a cache directory alone
    grants no exception to the source inventory.
    """
    file=release/name
    if file.parent.name!='__pycache__':return False
    tag=re.escape(sys.implementation.cache_tag)
    match=re.fullmatch(r'(.+)\.'+tag+r'(?:\.opt-([12]))?\.pyc',file.name)
    if not match:return False
    source=file.parent.parent/(match[1]+'.py')
    if str(source.relative_to(release)) not in expected_files:return False
    raw=file.read_bytes();data=source.read_bytes()
    if len(raw)<16 or raw[:4]!=importlib.util.MAGIC_NUMBER:return False
    flags=int.from_bytes(raw[4:8],'little')
    if flags==0:
        stat=source.stat()
        if raw[8:16]!=(int(stat.st_mtime)&0xffffffff).to_bytes(4,'little')+(len(data)&0xffffffff).to_bytes(4,'little'):return False
    elif flags in (1,3):
        if raw[8:16]!=importlib.util.source_hash(data):return False
    else:return False
    try:
        expected=compile(data,str(source),'exec',dont_inherit=True,optimize=int(match[2] or 0))
    except (SyntaxError,ValueError):return False
    return raw[16:]==marshal.dumps(expected)


def verify_source(release,commit):
    expected_files=set()
    for line in git('ls-tree','-r',commit,'--','backend/app','migrations').splitlines():
        metadata,separator,name=line.partition('\t')
        parts=metadata.split()
        require(separator and len(parts)==3 and parts[1]=='blob' and parts[0] in ('100644','100755'),
                'CENTRAL_SOURCE_TREE_REJECTED')
        expected_files.add(name)
        file=release/name
        require(file.is_file() and file.resolve()==file,'CENTRAL_SOURCE_FILE_REJECTED')
        data=file.read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        require(actual==parts[2],'CENTRAL_SOURCE_BLOB_CHANGED')
    actual_files=set()
    for base in (release/'backend/app',release/'migrations'):
        for file in base.rglob('*'):
            require(not file.is_symlink(),'CENTRAL_SOURCE_SYMLINK_REJECTED')
            if file.is_file():actual_files.add(str(file.relative_to(release)))
    extras=actual_files-expected_files
    verified_caches={name for name in extras if verified_source_cache(release,name,expected_files)}
    unexpected=extras-verified_caches
    if unexpected:
        # Unknown file names can themselves contain secrets. Only fingerprint them.
        details=dict(expected_files=len(expected_files),actual_files=len(actual_files),
                     verified_cache_files=len(verified_caches),unexpected_files=len(unexpected),
                     unexpected_inventory_sha256=hashlib.sha256('\n'.join(sorted(unexpected)).encode()).hexdigest())
        raise D['AcceptanceFailure']('SOURCE_INVENTORY','CENTRAL_SOURCE_EXTRA_FILE_REJECTED',details)
    require(expected_files<=actual_files,'CENTRAL_SOURCE_FILE_REJECTED')
    return dict(expected_files=len(expected_files),actual_files=len(actual_files),verified_cache_files=len(verified_caches))


def checked_request(opener,path,body=None):
    labels={'/api/ready':'API_READY','/api/v1/auth/login':'ADMIN_LOGIN','/api/v1/auth/me':'ADMIN_ME',
            '/api/v1/auth/logout':'ADMIN_LOGOUT','/api/v1/dashboard/summary':'DASHBOARD',
            '/api/v1/router-workspace/routers':'ROUTERS','/api/v1/subscriber-workspace':'SUBSCRIBERS',
            '/api/v1/packages':'PACKAGES','/':'STATIC_INDEX'}
    return D['request'](opener,ORIGIN,path,labels.get(path,'STATIC_ASSET'),body)


def warm_api():
    original=L['request'];L['request']=checked_request
    try:return D['step']('API_READY_CONTRACT',lambda:L['ready'](L['client']()))
    finally:L['request']=original


def public_accept(profile):
    opener=L['client']();original=L['request']
    checked=checked_request
    L['request']=checked
    try:
        D['step']('API_READY_CONTRACT',lambda:L['ready'](opener))
        D['step']('ADMIN_PANEL_CONTRACTS',lambda:L['admin_check'](opener,panel=True))
        release=Path(profile['release'])
        D['step']('SOURCE_BLOBS',lambda:verify_source(release,profile['commit']))
        index=D['step']('STATIC_INDEX_FILE',lambda:(release/'dist/index.html').read_bytes())
        D['step']('STATIC_INDEX_MATCH',lambda:require(checked(opener,'/')==index,'CENTRAL_STATIC_INDEX_MISMATCH'))
        document=W['EntryHTML']();document.feed(index.decode())
        D['step']('STATIC_HTML_MODE',lambda:require(document.root and document.scripts and
            all(not src.startswith(('/src/','/@vite','/@react-refresh')) for src in document.scripts),
            'DEVELOPMENT_SERVER_IS_NOT_A_RELEASE'))
        assets=re.findall(r'(?:src|href)="(/assets/[^"?#]+)"',index.decode())
        D['step']('STATIC_ENTRYPOINT',lambda:require(any(path.endswith('.js') for path in assets),'STATIC_ENTRYPOINT_REQUIRED'))
        for ordinal,path in enumerate(assets,1):
            D['step']('STATIC_ASSET_'+str(ordinal),lambda:require('..' not in path and
                checked(opener,path)==(release/'dist'/path.lstrip('/')).read_bytes(),'CENTRAL_STATIC_ASSET_MISMATCH'))
        def headers():
            with opener.open(ORIGIN+'/',timeout=10) as response:
                values={key:response.headers.get('X-V26-'+key)==profile[field] for key,field in
                        [('Instance','instance'),('Release','commit'),('Database','database')]}
                if not all(values.values()):raise D['AcceptanceFailure']('PUBLIC_HEADERS',
                    'CENTRAL_PUBLIC_BINDING_MISMATCH',dict(matches=values,http_status=response.status))
        D['step']('PUBLIC_HEADERS',headers)
        ready=D['step']('API_READY_JSON',lambda:json.loads(checked(opener,'/api/ready')))
        D['step']('API_RELEASE_ROOT',lambda:require(ready.get('repo_id')==hashlib.sha256(str(release).encode()).hexdigest(),
                'CENTRAL_RUNTIME_RELEASE_MISMATCH'))
        expected=hashlib.sha256()
        for file in sorted((release/'backend/app').rglob('*.py')):
            expected.update(str(file.relative_to(release)).encode()+b'\0'+file.read_bytes()+b'\0')
        D['step']('API_BUILD_ID',lambda:require(ready.get('build_id')==expected.hexdigest() and
                profile.get('build_id',ready['build_id'])==ready['build_id'],'CENTRAL_RUNTIME_CODE_CHANGED'))
        return ready
    finally:L['request']=original


def extract(data,destination,kind):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            allowed=(member.name=='dist' or member.name.startswith('dist/')) if kind=='dist' else (
                member.name.startswith(('backend/app/','migrations/')) or member.name in ('backend','backend/app','migrations'))
            require(allowed and '..' not in Path(member.name).parts and (member.isfile() or member.isdir()),
                    'RELEASE_ARCHIVE_REJECTED')
        archive.extractall(destination,filter='data')


def dropin_path(unit):
    unit_properties(unit)
    return Path('/etc/systemd/system')/(unit+'.d')/'80-v26-central.conf'


def install_dropin(unit,path):
    run(['sudo','-n','install','-D','-o','root','-g','root','-m','0644',path,dropin_path(unit)],stage='CENTRAL_UNIT_INSTALL')


def setup():
    require(APP_PATH.resolve()==APP_PATH and (APP_PATH/'.venv').resolve()==APP_PATH/'.venv',
            'CENTRAL_PATH_REJECTED')
    if ACTION=='apply':require(not git('status','--porcelain=v1'),'CENTRAL_CHECKOUT_DIRTY')
    stash=L['stash_pin'](run)
    W['nginx_routes'](run(['sudo','-n','nginx','-T'],stage='CENTRAL_NGINX_READ'))
    fingerprint=db_identity()
    require(not (APP_PATH/'.local').is_symlink() and not ROOT.is_symlink(),'CENTRAL_PRIVATE_PATH_REJECTED')
    require(ACTION=='apply' or (ROOT/'current.json').is_file(),'CENTRAL_INSTALL_REQUIRED')
    ROOT.mkdir(parents=True,mode=0o700,exist_ok=True)
    require(ROOT.stat().st_uid==os.getuid() and ROOT.stat().st_mode & 0o077==0,'CENTRAL_PRIVATE_OWNER_REJECTED')
    state=APP_PATH/'.local'
    require(state.resolve()==state and state.stat().st_uid==os.getuid() and state.stat().st_mode & 0o022==0,
            'CENTRAL_MUTABLE_STATE_PREFLIGHT_REJECTED')
    lock=(ROOT/'setup.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    identity_path=ROOT/'identity.json'
    if identity_path.exists():
        identity=json.loads(identity_path.read_text())
        require(identity['database']==fingerprint and identity['checkout']==APP and identity['origin']==ORIGIN,
                'CENTRAL_INSTANCE_DATABASE_CHANGED')
    else:
        identity=dict(instance=str(uuid.uuid4()),database=fingerprint,checkout=APP,origin=ORIGIN)
        private_json(identity_path,identity)
    pointer=ROOT/'current.json'
    old=json.loads(pointer.read_text()) if pointer.exists() else None
    head=git('rev-parse','HEAD')
    if old:require(digest_file(Path(old['web_argv'][2]))==old['static_config_sha256'],'CENTRAL_STATIC_CONFIG_CHANGED')
    if old:
        units=installed_units(old)
        if ACTION=='verify' or old['commit']==TARGET:
            if ACTION=='apply':require(head==TARGET and git('branch','--show-current')=='main-guncel','CENTRAL_SOURCE_DRIFT')
            ready=public_accept(old)
            require(L['stash_pin'](run)==stash,'CENTRAL_STASH_CHANGED')
            lock.close()
            return old,ready
    else:
        require(head==BASELINE,'INITIAL_VDS_BASELINE_CHANGED')
        units=L['services'](run)
        L['ready'](L['client']());L['admin_check'](L['client']())
    require(ACTION=='apply','CENTRAL_INSTALL_REQUIRED')
    for unit,api in units:
        props=unit_properties(unit)
        require(props['Type']=='simple' and props['KillMode']=='control-group' and
                not any(props[key] for key in ('ExecStartPre','ExecStartPost','ExecStop','ExecStopPost')),
                'CENTRAL_UNIT_HOOKS_REJECTED')
    git('fetch','origin',TARGET)
    git('merge-base','--is-ancestor',head,TARGET)
    for relative in ('backend/requirements.txt','frontend/package.json','frontend/package-lock.json'):
        require(not git('diff','--name-only',head,TARGET,'--',relative),'DEPENDENCY_CHANGE_REQUIRES_ISOLATED_PREPARATION')
    attempt=Path(tempfile.mkdtemp(prefix='attempt-',dir=ROOT))
    globals()['CURRENT_ATTEMPT']=str(attempt)
    release=ROOT/'releases'/TARGET
    require(not release.exists(),'INCOMPLETE_RELEASE_REQUIRES_REVIEW')
    release.mkdir(parents=True,mode=0o700)
    extract(base64.b64decode(SOURCE_B64,validate=True),release,'source')
    verify_source(release,TARGET)
    dist=base64.b64decode(DIST_B64,validate=True)
    require(hashlib.sha256(dist).hexdigest()==DIST_SHA,'CENTRAL_DIST_HASH_REJECTED')
    extract(dist,release,'dist')
    if old:
        previous=Path(old['release'])/'dist/assets'
        for item in previous.rglob('*'):
            require(not item.is_symlink(),'PREVIOUS_ASSET_SYMLINK_REJECTED')
            if not item.is_file():continue
            dest=release/'dist/assets'/item.relative_to(previous)
            if dest.exists():require(digest_file(dest)==digest_file(item),'STATIC_ASSET_COLLISION')
            else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,dest)
    dev=ROOT/'dev-venv'
    if not dev.exists():
        shutil.copytree(APP_PATH/'.venv',dev,symlinks=True)
        private_json(ROOT/'dev-environment.json',dict(path=str(dev),source=str(APP_PATH/'.venv')))
    require((ROOT/'dev-environment.json').is_file() and
            run([dev/'bin/python','-c','import sys;print(sys.prefix)'],stage='CENTRAL_DEV_PREFIX')==str(dev),
            'CENTRAL_DEV_ENVIRONMENT_REJECTED')
    runtime=attempt/'static-runtime';runtime.mkdir(mode=0o700)
    profile=dict(**identity,commit=TARGET,release=str(release),units=units)
    config=attempt/'static-nginx.conf';config.write_text(static_config(str(release/'dist'),str(runtime),profile))
    profile['static_config_sha256']=digest_file(config)
    runtime_env=attempt/'runtime.env'
    runtime_env.write_text('V2_SESSION_SECURE=true\nV2_CENTRAL_STATE_ROOT='+str(APP_PATH/'.local')+'\nPYTHONPATH='+str(release/'backend')+'\n');runtime_env.chmod(0o600)
    profile['api_argv']=[str(APP_PATH/'.venv/bin/python'),'-P','-B','-m','uvicorn','app.main:app','--app-dir',str(release/'backend'),
                         '--host','127.0.0.1','--port','18996']
    profile['web_argv']=['/usr/sbin/nginx','-c',str(config),'-p',str(runtime)]
    run(['/usr/sbin/nginx','-t','-c',config,'-p',runtime],stage='CENTRAL_STATIC_CONFIG_TEST')
    backups={}
    for unit,api in units:
        path=dropin_path(unit)
        exists=subprocess.run(['sudo','-n','test','-e',str(path)],capture_output=True).returncode
        require(exists in (0,1),'UNIT_BACKUP_ACCESS_FAILED')
        if exists==0:
            require(old is not None,'UNOWNED_CENTRAL_DROPIN_EXISTS')
            result=subprocess.run(['sudo','-n','cat',str(path)],capture_output=True,timeout=15)
            require(result.returncode==0,'CENTRAL_UNIT_BACKUP_FAILED')
            content=result.stdout
        else:content=b''
        saved=attempt/(unit+'.previous');saved.write_bytes(content);saved.chmod(0o600);backups[unit]=saved
        argv=profile['api_argv'] if api else profile['web_argv']
        # All argv tokens are generated paths/flags; no shell or credential values.
        require(all(re.fullmatch(r'[A-Za-z0-9_./:-]+',arg) for arg in argv),'UNIT_ARGUMENT_REJECTED')
        text='[Service]\nExecStart=\nExecStart='+' '.join(argv)+'\n'
        if api:text+='EnvironmentFile='+str(runtime_env)+'\n'
        candidate=attempt/(unit+'.next');candidate.write_text(text);candidate.chmod(0o600)
    # Verify exact sudo capabilities without stopping or changing any service.
    for unit,api in units:
        for action in ('stop','start'):
            run(['sudo','-n','-l','--','/usr/bin/systemctl',action,unit],stage='CENTRAL_PRIVILEGE_CHECK')
        for saved in (backups[unit],attempt/(unit+'.next')):
            run(['sudo','-n','-l','--','/usr/bin/install','-D','-o','root','-g','root','-m','0644',saved,dropin_path(unit)],
                stage='CENTRAL_PRIVILEGE_CHECK')
    run(['sudo','-n','-l','--','/usr/bin/systemctl','daemon-reload'],stage='CENTRAL_PRIVILEGE_CHECK')
    changed=False;source_changed=False;stopped=False
    try:
        stopped=True
        for unit,api in units:run(['sudo','-n','systemctl','stop',unit],stage='CENTRAL_V26_STOP')
        before=H['snapshot'](query,stage='CENTRAL_DATA_BEFORE')
        backup=attempt/'database.dump'
        with backup.open('xb') as stream:
            result=subprocess.run(['sudo','-n','-u','postgres','/usr/lib/postgresql/16/bin/pg_dump','-Fc',
                                   '-h','/var/run/postgresql','-p','55433','-d',DB],stdout=stream,stderr=subprocess.PIPE,timeout=180)
        require(result.returncode==0,'CENTRAL_BACKUP_FAILED');backup.chmod(0o600)
        proof=load(HELPER,dict())
        proof.update(BACKUP=backup,BASELINE=head,MIGRATION_SQL=MIGRATION_SQL,SOURCE_COMMIT=TARGET)
        captured=io.StringIO()
        with contextlib.redirect_stdout(captured):code=proof['main']()
        receipt=json.loads(captured.getvalue())
        private_json(attempt/'restore-proof.json',receipt)
        require(code==0,'CENTRAL_FRESH_RESTORE_MIGRATION_ACCEPTANCE_FAILED')
        require(receipt.get('migration_runs')==2 and receipt.get('backup_sha256')==digest_file(backup),
                'CENTRAL_RESTORE_PROOF_MISMATCH')
        # Existing live package catalog must validate in READ ONLY mode. No live DDL.
        run(['sudo','-n','-u','postgres','/usr/lib/postgresql/16/bin/psql','-X','-qAt','-v','ON_ERROR_STOP=1',
             '-h','/var/run/postgresql','-p','55433','-d',DB],stage='CENTRAL_SCHEMA_READONLY',
             sql='SET ROLE v26_acceptance;\n'+MIGRATION_SQL.replace('BEGIN;','BEGIN READ ONLY;',1))
        source_changed=True
        git('switch','main-guncel');git('merge','--ff-only',TARGET)
        env={key:value for key,value in os.environ.items() if not key.startswith(('V2_','PG'))}
        env.update(PYTHONPATH=str(APP_PATH/'backend'),PYTHONDONTWRITEBYTECODE='1',
                   V2_DATABASE_URL='postgresql+psycopg://isolated_only@127.0.0.1:1/isolated_only')
        result=subprocess.run([str(dev/'bin/python'),'-B','-m','unittest','backend.tests.test_v26_central_development'],
                              cwd=APP,capture_output=True,env=env,timeout=60)
        require(result.returncode==0,'CENTRAL_TARGETED_TEST_FAILED')
        changed=True
        for unit,api in units:install_dropin(unit,attempt/(unit+'.next'))
        run(['sudo','-n','systemctl','daemon-reload'],stage='CENTRAL_UNIT_RELOAD')
        for unit,api in units:
            free=run(['sudo','-n','ss','-H','-ltn','sport = :'+('18996' if api else '15173')],stage='CENTRAL_PORT_FREE')
            require(not free,'CENTRAL_PORT_COLLISION')
            run(['sudo','-n','systemctl','start',unit],stage='CENTRAL_V26_START')
        D['wait_ready'](warm_api,time.sleep)
        ready=public_accept(profile)
        installed_units(profile)
        H['assert_preserved'](before,H['snapshot'](query,stage='CENTRAL_DATA_AFTER'))
        require(db_identity()==fingerprint and L['stash_pin'](run)==stash,'CENTRAL_DB_OR_STASH_CHANGED')
        profile.update(backup=str(backup),backup_sha256=digest_file(backup),build_id=ready['build_id'])
        version=attempt/'profile.json';private_json(version,profile)
        # Immutable profile receipt retained; atomically move a new pointer into place.
        pending=attempt/'current-next.json';private_json(pending,profile);os.replace(pending,pointer)
        return profile,ready
    except Exception as original:
        for number in (signal.SIGHUP,signal.SIGINT,signal.SIGTERM):signal.signal(number,signal.SIG_IGN)
        failure=dict(reason=str(original) if isinstance(original,RuntimeError) else type(original).__name__,
                     target=TARGET,db_restore_performed=False)
        if getattr(original,'details',None):failure.update(original.details)
        private_json(attempt/'failure.json',failure)
        if changed:
            for unit,api in units:run(['sudo','-n','systemctl','stop',unit],stage='CENTRAL_ROLLBACK_STOP')
            for unit,api in units:install_dropin(unit,backups[unit])
            run(['sudo','-n','systemctl','daemon-reload'],stage='CENTRAL_ROLLBACK_RELOAD')
        if source_changed and old is None:
            current=git('rev-parse','HEAD')
            require(current in (head,TARGET) and not git('status','--porcelain=v1','--untracked-files=no'),
                    'CENTRAL_ROLLBACK_SOURCE_DRIFT')
            if current!=head:git('switch','--detach',head)
        if stopped:
            for unit,api in units:run(['sudo','-n','systemctl','start',unit],stage='CENTRAL_ROLLBACK_START')
            for _ in range(20):
                try:
                    if old:public_accept(old)
                    else:L['ready'](L['client']());L['admin_check'](L['client']())
                    break
                except Exception:time.sleep(1)
            else:raise RuntimeError('CENTRAL_ROLLBACK_HEALTH_BLOCKED')
        require(db_identity()==fingerprint and L['stash_pin'](run)==stash,'CENTRAL_ROLLBACK_BINDING_CHANGED')
        private_json(attempt/'rollback.json',dict(status='BASELINE_VERIFIED',source_head=git('rev-parse','HEAD'),
                                                db_restore_performed=False))
        raise
    finally:lock.close()


def digest_file(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):value.update(chunk)
    return value.hexdigest()


def diagnose_attempt():
    label=ATTEMPT_LABEL
    require(re.fullmatch(r'attempt-[a-z0-9_]{1,48}',label),'EVIDENCE_LABEL_REJECTED')
    attempt=ROOT/label
    require(attempt.is_dir() and attempt.resolve()==attempt and attempt.stat().st_uid==os.getuid(),
            'EVIDENCE_DIRECTORY_REJECTED')
    failure=json.loads((attempt/'failure.json').read_text())
    target=failure.get('target','')
    require(re.fullmatch('[0-9a-f]{40}',target),'EVIDENCE_TARGET_REJECTED')
    rollback=json.loads((attempt/'rollback.json').read_text())
    require(rollback.get('status')=='BASELINE_VERIFIED' and rollback.get('db_restore_performed') is False,
            'BASELINE_ROLLBACK_NOT_VERIFIED')
    release=ROOT/'releases'/target
    verify_source(release,target)
    result=dict(status='BLOCKED',mode='DIAGNOSTIC_ONLY',live_modified=False,live_commit=git('rev-parse','HEAD'),
                candidate_commit=target,historical_reason='CENTRAL_PUBLIC_ACCEPTANCE_FAILED',
                historical_cause='NOT_RECORDED',production_acceptance='NOT_VERIFIED')
    proof=json.loads((attempt/'restore-proof.json').read_text())
    result['restore_proof']={key:proof.get(key) for key in ('status','migration_runs','existing_tables_preserved')}
    state=APP_PATH/'.local';info=state.lstat()
    result['mutable_state']=dict(canonical=state.resolve()==state,directory=state.is_dir(),
                                owner_matches=info.st_uid==os.getuid(),no_group_or_world_write=not info.st_mode & 0o022)
    errorlog=attempt/'static-runtime/error.log'
    result['static_nginx_error_log_bytes']=errorlog.stat().st_size if errorlog.is_file() else None
    result['database_identity_verified']=bool(db_identity())
    result['current_delivery']={}
    for label,origin,path in [('HTTPS_INDEX',ORIGIN,'/'),('HTTPS_API',ORIGIN,'/api/ready'),
                              ('LOOPBACK_STATIC','http://127.0.0.1:15173','/'),
                              ('LOOPBACK_API','http://127.0.0.1:18996','/api/ready')]:
        try:
            raw=D['request'](L['client'](),origin,path,label)
            result['current_delivery'][label]=dict(http_status=200,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        except D['AcceptanceFailure'] as error:result['current_delivery'][label]=error.details
    result['current_delivery_context']='BASELINE_AFTER_ROLLBACK_NOT_FAILED_CANDIDATE'
    units=L['services'](run)
    api=next(unit for unit,role in units if role)
    props=unit_properties(api)
    env=run(['sudo','-n','cat','/proc/'+props['MainPID']+'/environ'],stage='DIAG_RUNTIME_ENV')
    values=dict(item.split('=',1) for item in env.split('\0') if '=' in item)
    values={key:value for key,value in values.items() if key.startswith('V2_')}
    for line in (attempt/'runtime.env').read_text().splitlines():
        key,sep,value=line.partition('=')
        require(sep and key in ('V2_SESSION_SECURE','V2_CENTRAL_STATE_ROOT','PYTHONPATH'),'DIAG_ENV_FILE_REJECTED')
        values[key]=value
    values['PYTHONPATH']=str(release/'backend')
    payload=dict(release=str(release),environment=values,admin=ADMIN)
    process=subprocess.run([str(APP_PATH/'.venv/bin/python'),'-P','-B','-c',CANDIDATE_PROBE],
                           input=json.dumps(payload),text=True,capture_output=True,cwd=APP,timeout=90)
    # Only our JSON report is forwarded. No stderr, traceback, env or raw body.
    try:probe=json.loads(process.stdout)
    except ValueError:probe=dict(status='BLOCKED',reason='PROBE_REPORT_UNAVAILABLE',exit_code=process.returncode)
    require(set(probe)<= {'status','mode','steps','failed_stage','error_class','reason','sqlstate','exit_code'},'PROBE_REPORT_SHAPE_REJECTED')
    result['candidate_api_readonly']=probe
    start=int((attempt/'restore-proof.json').stat().st_mtime)-30
    end=int((attempt/'failure.json').stat().st_mtime)+1
    try:
        journal=run(['sudo','-n','journalctl','-u',api,'--since=@'+str(start),'--until=@'+str(end),
                     '-n','200','-o','json','--no-pager'],stage='DIAG_API_JOURNAL')
        classes={'ModuleNotFoundError','ImportError','PermissionError','FileNotFoundError','RuntimeError',
                 'ValueError','TypeError','OperationalError','ProgrammingError','IntegrityError'}
        markers={'CENTRAL_STATE_ROOT_REJECTED','V26_ACCEPTANCE_ROOT_REJECTED','V26_ACCEPTANCE_DATABASE_REJECTED',
                 'V26_ACCEPTANCE_PROFILE_REJECTED','DATABASE_UNAVAILABLE'}
        seen=set();codes=set();count=0
        for line in journal.splitlines():
            try:message=json.loads(line).get('MESSAGE','')
            except ValueError:continue
            if not isinstance(message,str):continue
            count+=1
            seen.update(value for value in classes if re.search(r'\b'+value+r'\b',message))
            codes.update(value for value in markers if value in message)
        result['api_journal_summary']=dict(messages=count,exception_types=sorted(seen),guard_markers=sorted(codes))
    except Exception:result['api_journal_summary']=dict(status='UNAVAILABLE')
    result['next_step']='REVIEW_CANDIDATE_AND_HISTORICAL_STAGE_BEFORE_APPLY'
    return result


def protocol():
    def interrupted(*args):raise RuntimeError('CENTRAL_OPERATION_INTERRUPTED')
    for number in (signal.SIGHUP,signal.SIGINT,signal.SIGTERM):signal.signal(number,interrupted)
    try:
        if ACTION=='diagnose':
            print(json.dumps(diagnose_attempt(),sort_keys=True),flush=True)
            return
        profile,ready=setup()
        print(json.dumps(dict(event='CENTRAL_READY',profile=profile,ready=ready)),flush=True)
        value=json.loads(sys.stdin.readline())
        allowed={'origin','instance','release','database','location','machine','view_hash','build_id','captured_at'}
        require(set(value)==allowed and value['location'] in ('home','office'),'CLIENT_RECEIPT_REJECTED')
        require(value['origin']==ORIGIN and value['instance']==profile['instance'] and value['release']==profile['commit']
                and value['database']==profile['database'] and value['build_id']==ready['build_id'],'CLIENT_BINDING_REJECTED')
        require(type(value['captured_at']) in (int,float) and 0<=time.time()-value['captured_at']<=600 and
                all(re.fullmatch('[0-9a-f]{64}',value[key]) for key in ('machine','view_hash','build_id')),'CLIENT_RECEIPT_FORMAT_REJECTED')
        folder=ROOT/'verification';folder.mkdir(mode=0o700,exist_ok=True)
        private_json(folder/(value['location']+'-'+uuid.uuid4().hex+'.json'),value)
        receipts=[json.loads(path.read_text()) for path in folder.glob('*.json')]
        reason=complete_receipts(receipts,profile)
        print(json.dumps(dict(status='PASS' if reason is None else 'BLOCKED',setup='VERIFIED',
              reason=reason,live_commit=profile['commit'],origin=ORIGIN,database=profile['database'],
              instance=profile['instance'],migration='LIVE_READONLY_COMPATIBLE',
              backup=profile.get('backup'),db_restore_performed=False)),flush=True)
    except Exception as error:
        report=dict(status='BLOCKED',reason=str(error) if isinstance(error,RuntimeError) else type(error).__name__,
                    db_restore_performed=False,evidence_root=globals().get('CURRENT_ATTEMPT'))
        if getattr(error,'details',None):report.update(error.details)
        print(json.dumps(report),flush=True)
    finally:ADMIN.clear()
