#!/usr/bin/env python3
"""One idempotent central-V26 application command; independent home/office verification."""
import argparse
import base64
import getpass
import hashlib
import importlib.util
import json
import socket
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://v26.mikmanager.com.tr'


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def source(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT,text=True)


def observe(profile,credentials,location,legacy):
    namespace={'__name__':'client_observation','ADMIN':credentials}
    exec(legacy,namespace)
    opener=namespace['client']()
    namespace['ready'](opener)
    namespace['admin_check'](opener)  # Dedicated login/session check; credentials never stored.
    user=json.loads(namespace['request'](opener,'/api/v1/auth/login',credentials))
    try:
        if user.get('role_code')!='ADMIN':raise RuntimeError('ADMIN_REQUIRED')
        with opener.open(ORIGIN+'/',timeout=15) as response:
            if any(response.headers.get('X-V26-'+key)!=profile[field] for key,field in
                   [('Instance','instance'),('Release','commit'),('Database','database')]):
                raise RuntimeError('CENTRAL_BROWSER_BINDING_MISMATCH')
        ready=json.loads(namespace['request'](opener,'/api/ready'))
        if ready['build_id']!=profile['build_id']:raise RuntimeError('CLIENT_RELEASE_BUILD_MISMATCH')
        view={}
        for key,path in [('routers','/api/v1/router-workspace/routers'),
                         ('subscribers','/api/v1/subscriber-workspace'),('packages','/api/v1/packages')]:
            rows=[]
            for page in range(1,1001):
                data=json.loads(namespace['request'](opener,path+'?page_size=100&page='+str(page)))
                if not isinstance(data.get('items'),list) or type(data.get('total')) is not int:raise RuntimeError('CENTRAL_COLLECTION_CONTRACT')
                rows.extend(data['items'])
                if len(rows)>=data['total']:break
            else:raise RuntimeError('CENTRAL_COLLECTION_LIMIT')
            if len(rows)!=data['total']:raise RuntimeError('CENTRAL_COLLECTION_CHANGED')
            view[key]=rows
        view['dashboard']=json.loads(namespace['request'](opener,'/api/v1/dashboard/summary'))
        return dict(origin=ORIGIN,instance=profile['instance'],release=profile['commit'],database=profile['database'],
                    location=location,machine=hashlib.sha256(socket.gethostname().encode()).hexdigest(),
                    view_hash=hashlib.sha256(json.dumps(view,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                    build_id=ready['build_id'],captured_at=time.time())
    finally:namespace['request'](opener,'/api/v1/auth/logout',{})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--verify-location',choices=('home','office'))
    mode.add_argument('--diagnose-attempt')
    args=parser.parse_args()
    if args.diagnose_attempt and not re.fullmatch(r'attempt-[a-z0-9_]{1,48}',args.diagnose_attempt):
        raise RuntimeError('EVIDENCE_LABEL_REJECTED')
    commit=git('rev-parse','HEAD')
    if git('status','--porcelain=v1'):raise RuntimeError('OFFICE_CHECKOUT_DIRTY')
    spec=importlib.util.spec_from_file_location('office_legacy',ROOT/'tools/deploy-v26-office.py')
    legacy_office=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy_office)
    values=dict(TARGET=commit,ACTION='diagnose' if args.diagnose_attempt else 'apply' if args.apply else 'verify',
                ATTEMPT_LABEL=args.diagnose_attempt,
                DIAGNOSTICS=source(commit,'tools/v26_acceptance_diagnostics.py'),
                CANDIDATE_PROBE=source(commit,'tools/v26_candidate_probe.py'),
                POLICY=source(commit,'tools/v26_central_policy.py'),
                LEGACY=source(commit,'tools/deploy_v26_remote.py'),
                WEBROOT=source(commit,'tools/v26_webroot_preflight.py'),
                HELPER=source(commit,'tools/v26_backup_migration_remote.py'),
                MIGRATION_SQL=source(commit,'migrations/versions/011_package_catalog.sql'))
    if args.apply:
        if git('rev-parse',commit+':frontend')==git('rev-parse',legacy_office.TARGET+':frontend'):
            artifact=legacy_office.build_artifact()
        else:
            spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/prepare-v26-dry-run.py')
            builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
            artifact=builder.prepare(commit)
        archive=subprocess.check_output(['git','archive',commit,'backend/app','migrations'],cwd=ROOT)
        values.update(SOURCE_B64=base64.b64encode(archive).decode(),
                      DIST_B64=base64.b64encode((Path(artifact['artifact_directory'])/'frontend-dist.tar').read_bytes()).decode(),
                      DIST_SHA=artifact['frontend_dist_sha256'])
    credentials=dict(username=input('Mevcut merkezi ADMIN kullanıcı adı: '),password=getpass.getpass('ADMIN parolası: '))
    values['ADMIN']=credentials
    text='\n'.join(key+' = '+repr(value) for key,value in values.items())+'\n'
    text+=source(commit,'tools/v26_central_remote.py')+'\nprotocol()\n'
    compile(text,'central_v26_payload','exec')
    command=['ssh','-i',str(Path.home()/'.ssh/mikrotik_manager_ed25519'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
             '-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','mikadmin@185.139.5.51',
             "python3 -u -c \"import sys; n=int(sys.stdin.buffer.readline()); exec(compile(sys.stdin.buffer.read(n),'central_v26','exec'))\""]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=False)
    try:
        data=text.encode();process.stdin.write(str(len(data)).encode()+b'\n'+data);process.stdin.flush()
        line=process.stdout.readline()
        if not line:
            process.wait();print(json.dumps(dict(status='BLOCKED',reason='SSH_CHANNEL_UNAVAILABLE')));return 1
        event=json.loads(line)
        if event.get('event')!='CENTRAL_READY':print(json.dumps(event));return 1
        try:receipt=observe(event['profile'],credentials,args.verify_location or 'office',values['LEGACY'])
        except Exception as error:
            print(json.dumps(dict(status='BLOCKED',setup='VERIFIED',live_commit=event['profile']['commit'],
                  reason=str(error) if isinstance(error,RuntimeError) else type(error).__name__)))
            return 1
        process.stdin.write(json.dumps(receipt).encode()+b'\n');process.stdin.flush()
        report=json.loads(process.stdout.readline())
        print(json.dumps(report,sort_keys=True))
        process.stdin.close();process.wait()
        return 0 if report['status']=='PASS' else 1
    finally:
        credentials.clear()
        if process.stdin and not process.stdin.closed:process.stdin.close()
        if process.poll() is None:process.wait(timeout=30)


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='BLOCKED',reason=str(error) if isinstance(error,RuntimeError) else type(error).__name__)))
        raise SystemExit(1)
