"""Candidate ASGI probe: no listener, no DB writes, no raw response/error output."""
import asyncio
import hashlib
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import sys


def install_readonly_policy():
    import sqlalchemy
    original=sqlalchemy.create_engine
    def create(*args,**kwargs):
        from sqlalchemy.engine import make_url
        url=make_url(args[0])
        if (url.drivername!='postgresql+psycopg' or url.host!='127.0.0.1' or url.port!=55433
            or url.database!='mikrotik_v26_acceptance' or url.username!='v26_acceptance' or url.query):
            raise RuntimeError('PROBE_DATABASE_REJECTED')
        connect=dict(kwargs.get('connect_args',{}))
        connect['options']=connect.get('options','')+' -c default_transaction_read_only=on'
        kwargs['connect_args']=connect
        engine=original(*args,**kwargs)
        @sqlalchemy.event.listens_for(engine,'connect')
        def readonly(connection,record):
            with connection.cursor() as cursor:
                cursor.execute('SHOW default_transaction_read_only')
                if cursor.fetchone()[0]!='on':raise RuntimeError('PROBE_READONLY_REQUIRED')
        @sqlalchemy.event.listens_for(engine,'before_cursor_execute')
        def guard(connection,cursor,statement,parameters,context,many):
            if not re.match(r'^\s*(SELECT|SHOW)\b',statement,re.I):
                raise RuntimeError('PROBE_WRITE_STATEMENT_BLOCKED')
        return engine
    sqlalchemy.create_engine=create


def main():
    stage='INPUT'
    report={'status':'BLOCKED','mode':'CANDIDATE_ASGI_READONLY','steps':[]}
    try:
        payload=json.load(sys.stdin)
        release=Path(payload['release'])
        if not str(release).startswith('/srv/mikrotik-v26-next/.local/central/releases/') or release.resolve()!=release:
            raise RuntimeError('PROBE_RELEASE_REJECTED')
        for key in list(os.environ):
            if key.startswith(('V2_','PG')):os.environ.pop(key)
        os.environ.update(payload['environment'])
        sys.path.insert(0,str(release/'backend'))
        stage='READONLY_DATABASE_POLICY'
        install_readonly_policy()
        stage='IMPORT_CANDIDATE'
        from app.main import app
        cookie=''
        async def call(path,body=None):
            nonlocal cookie
            data=b'' if body is None else json.dumps(body).encode()
            received=False;messages=[]
            async def receive():
                nonlocal received
                if not received:received=True;return dict(type='http.request',body=data,more_body=False)
                return dict(type='http.disconnect')
            async def send(message):messages.append(message)
            headers=[(b'host',b'v26.mikmanager.com.tr'),(b'content-type',b'application/json')]
            if cookie:headers.append((b'cookie',cookie.encode()))
            scope=dict(type='http',asgi={'version':'3.0'},http_version='1.1',scheme='https',
                       method='GET' if body is None else 'POST',path=path,raw_path=path.encode(),query_string=b'',
                       root_path='',headers=headers,server=('v26.mikmanager.com.tr',443),client=('127.0.0.1',1))
            await app(scope,receive,send)
            start=next(m for m in messages if m['type']=='http.response.start')
            raw=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
            item=dict(stage=stage,status_code=start['status'],bytes=len(raw),body_sha256=hashlib.sha256(raw).hexdigest())
            report['steps'].append(item)
            for key,value in start.get('headers',[]):
                if key.lower()==b'set-cookie':
                    parsed=SimpleCookie();parsed.load(value.decode())
                    if 'v2_session' in parsed:cookie='v2_session='+parsed['v2_session'].value
            if start['status']!=200:raise RuntimeError('PROBE_HTTP_STATUS_REJECTED')
            return json.loads(raw)
        async def checks():
            nonlocal stage
            for label,path,body in [('API_READY','/api/ready',None),('ADMIN_LOGIN','/api/v1/auth/login',payload['admin']),
                                   ('ADMIN_ME','/api/v1/auth/me',None),('DASHBOARD','/api/v1/dashboard/summary',None),
                                   ('ROUTERS','/api/v1/router-workspace/routers',None),
                                   ('SUBSCRIBERS','/api/v1/subscriber-workspace',None),('PACKAGES','/api/v1/packages',None),
                                   ('ADMIN_LOGOUT','/api/v1/auth/logout',{})]:
                stage=label;value=await call(path,body)
                if label in ('ADMIN_LOGIN','ADMIN_ME') and value.get('role_code')!='ADMIN':
                    raise RuntimeError('PROBE_ADMIN_ROLE_REJECTED')
        asyncio.run(checks())
        report['status']='PASS'
    except Exception as error:
        report.update(failed_stage=stage,error_class=type(error).__name__)
        if isinstance(error,RuntimeError) and re.fullmatch('[A-Z0-9_]{1,96}',str(error)):report['reason']=str(error)
        code=getattr(getattr(error,'orig',error),'sqlstate',None)
        if isinstance(code,str) and re.fullmatch('[0-9A-Z]{5}',code):report['sqlstate']=code
    print(json.dumps(report))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
