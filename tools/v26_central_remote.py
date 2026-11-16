"""V26-only static/release bootstrap. Called through a length-framed SSH channel."""
import base64
import contextlib
import fcntl
import hashlib
import io
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
    require(actual_files==expected_files,'CENTRAL_SOURCE_EXTRA_FILE_REJECTED')


def public_accept(profile):
    opener=L['client']()
    L['ready'](opener)
    L['admin_check'](opener,panel=True)
    release=Path(profile['release'])
    verify_source(release,profile['commit'])
    index=(release/'dist/index.html').read_bytes()
    require(L['request'](opener,'/')==index,'CENTRAL_STATIC_INDEX_MISMATCH')
    document=W['EntryHTML']();document.feed(index.decode())
    require(document.root and document.scripts and
            all(not src.startswith(('/src/','/@vite','/@react-refresh')) for src in document.scripts),
            'DEVELOPMENT_SERVER_IS_NOT_A_RELEASE')
    assets=re.findall(r'(?:src|href)="(/assets/[^"?#]+)"',index.decode())
    require(any(path.endswith('.js') for path in assets),'STATIC_ENTRYPOINT_REQUIRED')
    for path in assets:
        require('..' not in path and L['request'](opener,path)==(release/'dist'/path.lstrip('/')).read_bytes(),
                'CENTRAL_STATIC_ASSET_MISMATCH')
    with opener.open(ORIGIN+'/',timeout=10) as response:
        require(response.headers.get('X-V26-Instance')==profile['instance'] and
                response.headers.get('X-V26-Release')==profile['commit'] and
                response.headers.get('X-V26-Database')==profile['database'],'CENTRAL_PUBLIC_BINDING_MISMATCH')
    ready=json.loads(L['request'](opener,'/api/ready'))
    require(ready.get('repo_id')==hashlib.sha256(str(release).encode()).hexdigest(),'CENTRAL_RUNTIME_RELEASE_MISMATCH')
    expected=hashlib.sha256()
    for file in sorted((release/'backend/app').rglob('*.py')):
        expected.update(str(file.relative_to(release)).encode()+b'\0'+file.read_bytes()+b'\0')
    require(ready.get('build_id')==expected.hexdigest() and
            profile.get('build_id',ready['build_id'])==ready['build_id'],'CENTRAL_RUNTIME_CODE_CHANGED')
    return ready


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
        for _ in range(20):
            try:ready=public_accept(profile);break
            except Exception:
                time.sleep(1)
        else:raise RuntimeError('CENTRAL_PUBLIC_ACCEPTANCE_FAILED')
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
        private_json(attempt/'failure.json',dict(reason=str(original) if isinstance(original,RuntimeError) else type(original).__name__,
                                               target=TARGET,db_restore_performed=False))
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


def protocol():
    def interrupted(*args):raise RuntimeError('CENTRAL_OPERATION_INTERRUPTED')
    for number in (signal.SIGHUP,signal.SIGINT,signal.SIGTERM):signal.signal(number,interrupted)
    try:
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
