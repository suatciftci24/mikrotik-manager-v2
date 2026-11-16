#!/usr/bin/env python3
"""Standalone VDS inspector for an installed 79b8484 tree. Never installs itself.

Reads existing backups only; creates no files, session, grants, schema or service.
All credential-bearing inputs/results remain in memory and are never printed.
"""
import getpass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tarfile
import warnings
import ssl
import shutil
import urllib.request
import pwd
import ctypes
import resource
import selectors
import time
from contextlib import contextmanager

ROOT = Path('/srv/mikrotik-v26-next')
ENV_FILE = Path('/etc/mikrotik-v26-api.env')
UNITS = ('mikrotik-v26-api.service', 'mikrotik-v26-web.service', 'postgresql@16-v26.service')
TABLES = ('v2_registered_routers', 'v2_router_verifications', 'v2_router_registry_audit')
REPORT = {}
TOOL_ENV = {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'}
SYSTEM_PYTHON = '/usr/bin/python3'
# Generated from the committed ORM; inspected types/keys/indexes are compared exactly.
CONTRACT = {'v2_registered_routers': {'columns': {'id': ['VARCHAR(48)', False], 'name': ['VARCHAR(120)', False], 'management_address': ['VARCHAR(64)', False], 'port': ['INTEGER', False], 'configuration': ['JSON', False], 'metadata_snapshot': ['JSON', False], 'credential_ref': ['VARCHAR(36)', False], 'revision': ['INTEGER', False], 'last_checked_at': ['VARCHAR(40)', False], 'last_success_at': ['VARCHAR(40)', False], 'last_error': ['VARCHAR(200)', True]}, 'indexes': {'ix_v2_registered_routers_name': ['name'], 'ix_v2_registered_routers_check': ['last_error', 'last_success_at']}, 'unique': ['management_address', 'port']}, 'v2_router_verifications': {'columns': {'id': ['VARCHAR(36)', False], 'actor_id': ['VARCHAR(80)', False], 'state': ['VARCHAR(16)', False], 'target_router_id': ['VARCHAR(48)', True], 'expected_revision': ['INTEGER', False], 'snapshot': ['JSON', False], 'credential_ref': ['VARCHAR(36)', False], 'created_at': ['VARCHAR(40)', False], 'expires_at': ['VARCHAR(40)', False], 'error_code': ['VARCHAR(200)', True], 'saved_router_id': ['VARCHAR(48)', True]}, 'indexes': {'ix_v2_router_verifications_actor_id': ['actor_id'], 'ix_v2_router_verifications_expiry': ['state', 'expires_at']}, 'unique': []}, 'v2_router_registry_audit': {'columns': {'id': ['VARCHAR(36)', False], 'actor_id': ['VARCHAR(80)', False], 'router_id': ['VARCHAR(48)', True], 'verification_id': ['VARCHAR(36)', False], 'action': ['VARCHAR(40)', False], 'occurred_at': ['VARCHAR(40)', False], 'details': ['JSON', False]}, 'indexes': {'ix_v2_router_registry_audit_router_id': ['router_id'], 'ix_v2_router_registry_audit_time': ['router_id', 'occurred_at']}, 'unique': []}}
MODEL_SHA256 = '0a31194f1d723f741be066da8d7a8360774b78b5a512390e9d4db1d990b10fc6'


class Blocked(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Blocked(code)


def check(name, call):
    try:
        result = call()
        REPORT[name] = 'PASS'
        return result
    except Blocked as error:
        REPORT[name] = 'BLOCKED:'+str(error)
    except Exception:
        REPORT[name] = 'BLOCKED:CHECK_UNAVAILABLE'
    return None


def run_tool(args,*,timeout,env,input=None,max_output=262144,**options):
    """Bounded pipes only; tool stderr (possibly sensitive) is never exported."""
    require(input is None or len(input)<=262144,'TOOL_INPUT_LIMIT')
    process=subprocess.Popen(args,stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,**options)
    output=bytearray();offset=0;deadline=time.monotonic()+timeout
    selection=selectors.DefaultSelector()
    try:
        os.set_blocking(process.stdout.fileno(),False)
        selection.register(process.stdout,selectors.EVENT_READ,'out')
        if input is not None:
            os.set_blocking(process.stdin.fileno(),False)
            if input:selection.register(process.stdin,selectors.EVENT_WRITE,'in')
            else:process.stdin.close()
        while selection.get_map():
            left=deadline-time.monotonic()
            require(left>0,'TOOL_TIMEOUT')
            for key,_ in selection.select(min(left,1)):
                if key.data=='in':
                    offset+=os.write(key.fd,input[offset:offset+4096])
                    if offset==len(input):selection.unregister(key.fileobj);key.fileobj.close()
                else:
                    data=os.read(key.fd,min(65536,max_output-len(output)+1))
                    if not data:selection.unregister(key.fileobj);continue
                    output.extend(data);require(len(output)<=max_output,'TOOL_OUTPUT_LIMIT')
        left=deadline-time.monotonic();require(left>0,'TOOL_TIMEOUT')
        code=process.wait(timeout=left)
        return subprocess.CompletedProcess(args,code,bytes(output),b'')
    except BaseException:
        if process.poll() is None:process.kill()
        process.wait()
        raise
    finally:
        selection.close()
        for stream in (process.stdin,process.stdout):
            if stream is not None and not stream.closed:stream.close()


def trusted_system_path(path):
    resolved=Path(path).resolve(strict=True)
    for item in (resolved,*resolved.parents):
        info=item.stat()
        require(info.st_uid==0 and not info.st_mode&0o022, 'TRUSTED_SYSTEM_TOOL_REQUIRED')
    return str(resolved)


def tls_context(ca=None):
    # create_default_context honours SSLKEYLOGFILE and may open a writable file.
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    if ca is None:context.load_verify_locations(cafile='/etc/ssl/certs/ca-certificates.crt')
    else:context.load_verify_locations(cadata=ca)
    return context


@contextmanager
def regular_file(path, limit=16*1024*1024, private=False, owners=None):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and path.name, 'ABSOLUTE_FILE_REQUIRED')
    directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    fd=None
    try:
        for part in path.parts[1:-1]:
            next_dir=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
            os.close(directory);directory=next_dir
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory)
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=limit,
                'REGULAR_BOUNDED_FILE_REQUIRED')
        if private:
            require(before.st_mode&stat.S_IRUSR and not before.st_mode&0o077
                    and (owners is None or before.st_uid in owners), 'PRIVATE_BACKUP_OR_ENV_PERMISSIONS_REQUIRED')
        with os.fdopen(fd,'rb') as stream:
            fd=None
            yield stream
            after=os.fstat(stream.fileno())
            require((before.st_size,before.st_mtime_ns,before.st_ino,before.st_mode,before.st_uid)==
                    (after.st_size,after.st_mtime_ns,after.st_ino,after.st_mode,after.st_uid),'FILE_CHANGED_OR_LIMIT')
    except OSError:
        raise Blocked('FILE_ACCESS_OR_SYMLINK_REJECTED') from None
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)


def read_file(path, limit=16*1024*1024, private=False, owners=None, metadata_only=False):
    with regular_file(path,limit,private,owners) as stream:
        value=b'' if metadata_only else stream.read(limit+1)
        require(len(value)<=limit,'FILE_CHANGED_OR_LIMIT')
        return value


def environment_file(raw):
    """Strict single-line EnvironmentFile subset, no shell/eval/interpolation."""
    values = {}
    for line in raw.decode('utf8').splitlines():
        line = line.strip()
        if not line or line.startswith(('#',';')):
            continue
        key, separator, value = line.partition('=')
        require(separator and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',key) and key not in values,
                'ENV_FORMAT_REQUIRES_REVIEW')
        words = shlex.split(value, comments=False, posix=True)
        require(len(words) <= 1, 'ENV_FORMAT_REQUIRES_REVIEW')
        values[key] = words[0] if words else ''
    return values


def unit(name):
    result = run_tool([trusted_system_path('/usr/bin/systemctl'),'show',name,'--no-pager',
        '--property=ActiveState,SubState,MainPID,WorkingDirectory,FragmentPath,DropInPaths,EnvironmentFiles,NeedDaemonReload'],
        timeout=10,env=TOOL_ENV)
    require(result.returncode == 0, 'UNIT_METADATA_UNAVAILABLE')
    data = dict(line.split('=',1) for line in result.stdout.decode().splitlines() if '=' in line)
    require(data.get('ActiveState') == 'active' and data.get('SubState') == 'running', 'UNIT_NOT_RUNNING')
    require(data.get('NeedDaemonReload') == 'no', 'UNIT_DISK_AND_LOADED_STATE_DIFFER')
    return data


def api_get(path, cookie=None):
    require(path in ('/api/ready','/api/health','/api/v1/auth/me'), 'API_PATH_REJECTED')
    require(not cookie or path=='/api/v1/auth/me', 'SESSION_DESTINATION_REJECTED')
    connection = http.client.HTTPConnection('127.0.0.1',18996,timeout=8)
    try:
        headers = {'Host':'v26.mikmanager.com.tr'}
        if cookie:
            require(re.fullmatch(r'[A-Za-z0-9_-]{40,100}',cookie), 'SESSION_FORMAT_REJECTED')
            headers['Cookie'] = 'v2_session='+cookie
        connection.request('GET',path,headers=headers)
        response = connection.getresponse()
        require(response.status == 200, 'API_OR_EXISTING_SESSION_REJECTED')
        body = response.read(262145)
        require(len(body) <= 262144, 'API_RESPONSE_LIMIT')
        return json.loads(body)
    finally:
        connection.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def https_get(path):
    require(path in ('/','/api/ready') or re.fullmatch(r'/assets/[A-Za-z0-9_.-]+',path), 'STATIC_PATH_REJECTED')
    url='https://v26.mikmanager.com.tr'+path
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),
                                      urllib.request.HTTPSHandler(context=tls_context()))
    with opener.open(url,timeout=10) as response:
        require(response.status==200 and response.geturl()==url, 'HTTPS_STATUS_OR_REDIRECT_REJECTED')
        data=response.read(16*1024*1024+1)
        require(len(data)<=16*1024*1024, 'HTTPS_RESPONSE_LIMIT')
        return data


def frontend_live(files):
    require(files is not None, 'CODE_SNAPSHOT_REQUIRED')
    remote=json.loads(https_get('/api/ready'));local=api_get('/api/ready')
    require(all(remote.get(k)==local.get(k) and local.get(k) is not None
                for k in ('repo_id','build_id','api_port','runtime_profile')), 'HTTPS_API_ROUTE_MISMATCH')
    index=https_get('/')
    require(index==files['frontend/dist/index.html'], 'HTTPS_FRONTEND_INDEX_MISMATCH')
    assets=re.findall(r'(?:src|href)=["\'](/assets/[A-Za-z0-9_.-]+)["\']',index.decode())
    require(bool(assets), 'FRONTEND_ASSETS_REQUIRED')
    for asset in set(assets):
        require(files.get('frontend/dist'+asset)==https_get(asset), 'HTTPS_FRONTEND_ASSET_MISMATCH')


def session_identity(cookie):
    user = api_get('/api/v1/auth/me',cookie)
    candidate = (user.get('pilot_identity') or {}).get('candidate') or {}
    require(user.get('account_origin') == 'LOCAL' and user.get('bootstrap_closed') is True
            and user.get('active') is True and user.get('role_code') == 'ADMIN'
            and user.get('can_manage_users') is True and (user.get('pilot_identity') or {}).get('state') == 'ELIGIBLE'
            and re.fullmatch(r'v2-user-[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',user.get('id',''))
            and type(user.get('revision')) is int and user['revision'] >= 0
            and candidate.get('id') == user['id'] and candidate.get('revision') == user['revision']
            and candidate.get('source') == 'V2_AUTHENTICATED_SESSION', 'REAL_LOCAL_ADMIN_SESSION_REQUIRED')
    return {'id':user['id'],'revision':user['revision']}


# Executed with the running API's interpreter and UID, not imported application code.
DB_INSPECT = r'''
import ctypes, json, os, sys
from pathlib import Path
from urllib.parse import urlsplit, unquote

def trusted(path):
    resolved=Path(path).resolve(strict=True)
    for item in (resolved,*resolved.parents):
        info=item.stat()
        if info.st_uid!=0 or info.st_mode&0o022:raise RuntimeError('UNTRUSTED_SYSTEM_LIBRARY')
    return str(resolved)

class LibPQ:
    def __init__(self,url):
        u=urlsplit(url)
        if ((u.scheme,u.hostname,u.port,u.path,unquote(u.username or '')) !=
            ('postgresql+psycopg','127.0.0.1',55433,'/mikrotik_v26_acceptance','v26_acceptance')
            or u.query or u.fragment):raise RuntimeError('DATABASE_SCOPE')
        password=unquote(u.password or '')
        if len(password)<20 or any(ord(c)<32 for c in password):raise RuntimeError('DATABASE_CREDENTIAL_FORMAT')
        path=next((p for p in ('/usr/lib/x86_64-linux-gnu/libpq.so.5','/usr/lib/aarch64-linux-gnu/libpq.so.5') if Path(p).exists()),None)
        if path is None:raise RuntimeError('SYSTEM_LIBPQ_REQUIRED')
        self.lib=ctypes.CDLL(trusted(path));self.conn=None
        declarations={
          'PQconnectdbParams':([ctypes.POINTER(ctypes.c_char_p),ctypes.POINTER(ctypes.c_char_p),ctypes.c_int],ctypes.c_void_p),
          'PQstatus':([ctypes.c_void_p],ctypes.c_int),
          'PQexecParams':([ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_void_p,ctypes.POINTER(ctypes.c_char_p),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int],ctypes.c_void_p),
          'PQresultStatus':([ctypes.c_void_p],ctypes.c_int),'PQntuples':([ctypes.c_void_p],ctypes.c_int),
          'PQnfields':([ctypes.c_void_p],ctypes.c_int),
          'PQgetisnull':([ctypes.c_void_p,ctypes.c_int,ctypes.c_int],ctypes.c_int),
          'PQgetvalue':([ctypes.c_void_p,ctypes.c_int,ctypes.c_int],ctypes.c_char_p),
          'PQclear':([ctypes.c_void_p],None),'PQfinish':([ctypes.c_void_p],None)}
        for name,(args,result) in declarations.items():
            function=getattr(self.lib,name);function.argtypes=args;function.restype=result
        config={'host':'127.0.0.1','hostaddr':'127.0.0.1','port':'55433','dbname':'mikrotik_v26_acceptance',
          'user':'v26_acceptance','password':password,'connect_timeout':'5',
          'sslmode':'disable','gssencmode':'disable','passfile':'/dev/null','client_encoding':'UTF8',
          'options':'-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=3000'}
        keys=(ctypes.c_char_p*(len(config)+1))(*(v.encode() for v in config),None)
        values=(ctypes.c_char_p*(len(config)+1))(*(v.encode() for v in config.values()),None)
        self.conn=self.lib.PQconnectdbParams(keys,values,0)
        if not self.conn or self.lib.PQstatus(self.conn)!=0:
            self.close();raise RuntimeError('DATABASE_CONNECTION_REJECTED')
    def query(self,sql,params=()):
        values=(ctypes.c_char_p*len(params))(*(str(v).encode() for v in params))
        result=self.lib.PQexecParams(self.conn,sql.encode(),len(params),None,values,None,None,0)
        if not result:raise RuntimeError('DATABASE_QUERY_REJECTED')
        try:
            if self.lib.PQresultStatus(result) not in (1,2):raise RuntimeError('DATABASE_QUERY_REJECTED')
            rows=self.lib.PQntuples(result);columns=self.lib.PQnfields(result)
            if rows>1024 or columns>16:raise RuntimeError('DATABASE_RESPONSE_LIMIT')
            output=[];size=0
            for row in range(rows):
                record=[]
                for col in range(columns):
                    value=None if self.lib.PQgetisnull(result,row,col) else self.lib.PQgetvalue(result,row,col).decode('utf8')
                    size+=len(value or '')
                    if size>262144:raise RuntimeError('DATABASE_RESPONSE_LIMIT')
                    record.append(value)
                output.append(record)
            return output
        finally:self.lib.PQclear(result)
    def close(self):
        if self.conn:self.lib.PQfinish(self.conn);self.conn=None

def inspect_database(p,query):
    result={}
    try:
        query('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if query('SHOW transaction_read_only')!=[['on']]:raise RuntimeError('READ_ONLY_REQUIRED')
        if query('SELECT pg_catalog.current_database(),current_user,pg_catalog.inet_server_port()')!=[['mikrotik_v26_acceptance','v26_acceptance','55433']]:raise RuntimeError('DATABASE_IDENTITY')
        for table in ('v26_acceptance.schema_state','v26_acceptance.users'):
            if query('SELECT relkind FROM pg_catalog.pg_class WHERE oid=pg_catalog.to_regclass($1)',(table,))!=[['r']]:raise RuntimeError('CORE_TABLE_REQUIRED')
        if query('SELECT marker FROM v26_acceptance.schema_state WHERE version=1')!=[['mikrotik-manager-v2-synthetic-only']]:raise RuntimeError('DATABASE_MARKER')
        result['database']='PASS';identity=p['identity']
        row=query('SELECT id,revision,role,active,account_origin FROM v26_acceptance.users WHERE id=$1',(identity['id'],))
        result['session_database_match']='PASS' if row==[[identity['id'],str(identity['revision']),'ADMIN','t','LOCAL']] else 'BLOCKED:SESSION_DATABASE_MISMATCH'
        namespaces=set()
        for name,expected in p['contract'].items():
            found=query("SELECT n.nspname FROM pg_catalog.pg_class t JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace WHERE t.relname=$1 AND n.nspname IN ('public','v26_acceptance') AND t.relkind='r'",(name,))
            resolved=query("SELECT n.nspname FROM pg_catalog.pg_class t JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace WHERE t.oid=pg_catalog.to_regclass($1) AND t.relkind='r'",(name,))
            if not found:result[name]='BLOCKED:TABLE_ABSENT';continue
            if len(found)!=1 or len(resolved)!=1 or resolved[0][0] not in ('public','v26_acceptance'):
                result[name]='BLOCKED:TABLE_SHADOWED_OR_NOT_RESOLVABLE';continue
            schema=resolved[0][0];namespaces.add(schema);qualified=schema+'.'+name
            rights=query("SELECT pg_catalog.has_database_privilege(pg_catalog.current_database(),'CONNECT'),pg_catalog.has_schema_privilege($1,'USAGE'),pg_catalog.has_table_privilege($2,'SELECT'),pg_catalog.has_table_privilege($2,'INSERT'),pg_catalog.has_table_privilege($2,'UPDATE')",(schema,qualified))
            if rights!=[['t']*5]:result[name]='BLOCKED:CONNECT_USAGE_SELECT_INSERT_UPDATE_REQUIRED';continue
            rows=query('SELECT attname,pg_catalog.format_type(atttypid,atttypmod),NOT attnotnull FROM pg_catalog.pg_attribute WHERE attrelid=pg_catalog.to_regclass($1) AND attnum>0 AND NOT attisdropped ORDER BY attnum',(qualified,))
            columns={r[0]:[r[1].upper().replace('CHARACTER VARYING','VARCHAR'),r[2]=='t'] for r in rows}
            rows=query('SELECT ci.relname,pg_catalog.json_agg(a.attname ORDER BY k.ord)::text,i.indisprimary,i.indisunique FROM pg_catalog.pg_index i JOIN pg_catalog.pg_class ci ON ci.oid=i.indexrelid CROSS JOIN LATERAL pg_catalog.unnest(i.indkey) WITH ORDINALITY k(attnum,ord) JOIN pg_catalog.pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum WHERE i.indrelid=pg_catalog.to_regclass($1) AND i.indisvalid AND i.indisready AND i.indpred IS NULL AND i.indexprs IS NULL GROUP BY ci.relname,i.indisprimary,i.indisunique',(qualified,))
            indexes={r[0]:json.loads(r[1]) for r in rows}
            good=(columns==expected['columns'] and any(r[2]=='t' and json.loads(r[1])==['id'] for r in rows) and all(indexes.get(k)==v for k,v in expected['indexes'].items()))
            if expected['unique']:good=good and any(r[3]=='t' and json.loads(r[1])==expected['unique'] for r in rows)
            result[name]='PASS' if good else 'BLOCKED:MODEL_SCHEMA_OR_INDEX_MISMATCH'
        if len(namespaces)>1:result['registry_namespace']='BLOCKED:SPLIT_SCHEMA'
    except Exception:result['database']='BLOCKED:READONLY_DATABASE_INSPECTION_FAILED'
    finally:
        try:query('ROLLBACK')
        except Exception:result['database']='BLOCKED:READONLY_DATABASE_INSPECTION_FAILED'
    return result

def main():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    libc=ctypes.CDLL(None)
    if libc.prctl(4,0,0,0,0)!=0:raise RuntimeError('PRIVATE_PROCESS_REQUIRED')
    db=None;result={'database':'BLOCKED:READONLY_DATABASE_INSPECTION_FAILED'}
    try:
        p=json.load(sys.stdin);db=LibPQ(p['url']);result=inspect_database(p,db.query)
    except Exception:pass
    finally:
        if db:db.close()
    print(json.dumps(result))

if __name__=='__main__':main()
'''


def database(values, identity, uid, gid):
    require(identity is not None, 'EXISTING_SESSION_REQUIRED_BEFORE_DB_CHECK')
    request = json.dumps({'url':values['V2_DATABASE_URL'],'identity':identity,'contract':CONTRACT})
    python=trusted_system_path(SYSTEM_PYTHON)
    result = run_tool([python,'-I','-S','-B','-c',DB_INSPECT],input=request.encode(),
        timeout=45,max_output=32768,cwd=ROOT,user=uid,group=gid,extra_groups=[],
        env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'})
    require(result.returncode == 0 and len(result.stdout) <= 32768, 'DB_HELPER_UNAVAILABLE')
    data = json.loads(result.stdout)
    require(isinstance(data,dict) and set(data) <= set(TABLES)|{'database','session_database_match','registry_namespace'}, 'DB_REPORT_REJECTED')
    for key,value in data.items():
        require(isinstance(value,str) and (value=='PASS' or re.fullmatch('BLOCKED:[A-Z_]+',value)), 'DB_REPORT_REJECTED')
        REPORT[key]=value
    require(data.get('database') == 'PASS' and data.get('session_database_match') == 'PASS'
            and all(data.get(t)=='PASS' for t in TABLES) and 'registry_namespace' not in data,
            'REGISTRY_OR_SESSION_DATABASE_DEPENDENCIES_BLOCKED')


def code_snapshot():
    require(ROOT.resolve() == ROOT and not ROOT.is_symlink(), 'RUNTIME_PHYSICAL_ROOT_REJECTED')
    model = read_file(ROOT/'backend/app/models/router_registry.py')
    require(hashlib.sha256(model).hexdigest() == MODEL_SHA256, 'INSTALLED_REGISTRY_MODEL_DRIFT')
    files = {name:read_file(ROOT/name) for name in ('backend/requirements.txt','frontend/package.json','frontend/package-lock.json')}
    for directory in (ROOT/'backend/app',ROOT/'frontend/dist'):
        require(directory.is_dir() and not directory.is_symlink(), 'CODE_OR_DIST_MISSING')
        for path in sorted(directory.rglob('*')):
            require(not path.is_symlink(), 'CODE_SYMLINK_REJECTED')
            if path.is_file() and (directory.name=='dist' or path.suffix=='.py'):
                files[str(path.relative_to(ROOT))]=read_file(path)
    require('frontend/dist/index.html' in files and bool(files), 'FRONTEND_BUILD_REQUIRED')
    return files


def active_code_identity(files):
    require(files is not None,'CODE_SNAPSHOT_REQUIRED')
    digest=hashlib.sha256()
    for name,value in sorted(files.items()):
        if name.startswith('backend/app/'):
            digest.update(name[len('backend/app/'):].encode());digest.update(b'\0');digest.update(value);digest.update(b'\0')
    ready=api_get('/api/ready')
    def safe_hash(value):
        return value if isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) else None
    disk_repo=hashlib.sha256(str(ROOT).encode()).hexdigest()
    REPORT['code_identity_evidence']={'disk_repo_id':disk_repo,'api_repo_id':safe_hash(ready.get('repo_id')),
        'disk_build_id':digest.hexdigest(),'api_build_id':safe_hash(ready.get('build_id')),
        'backup_scope':'DISK_BASELINE_ONLY_UNTIL_ACTIVE_IDENTITY_MATCHES'}
    require(ready.get('runtime_profile')=='v26-isolated-acceptance' and ready.get('api_port')==18996,
            'ACTIVE_API_SCOPE_MISMATCH')
    require(ready.get('repo_id')==disk_repo,'ACTIVE_REPO_IDENTITY_MISMATCH')
    require(ready.get('build_id')==digest.hexdigest(),'ACTIVE_BUILD_IDENTITY_MISMATCH')
    require(api_get('/api/health').get('database_connected') is True,'API_DATABASE_HEALTH_FAILED')
    REPORT['code_identity_evidence']['backup_scope']='DISK_AND_ACTIVE_IDENTITY_MATCH'


def selection(values,identity):
    require(identity is not None, 'VERIFIED_SESSION_CANDIDATE_REQUIRED')
    flag=values.get('V2_V26_CEBECI_READ_ENABLED','false')
    if flag=='false':
        require(not values.get('V2_V26_CEBECI_OPERATOR_ID','') and not values.get('V2_V26_CEBECI_OPERATOR_REVISION',''),
                'DISABLED_CAPABILITY_HAS_STALE_GRANT')
    else:
        require(flag=='true' and values.get('V2_V26_CEBECI_OPERATOR_ID')==identity['id']
                and values.get('V2_V26_CEBECI_OPERATOR_REVISION')==str(identity['revision']),
                'CAPABILITY_DOES_NOT_MATCH_AUTHENTICATED_ADMIN')


def private_material(uid,values):
    root=ROOT/'.local/cebeci-pilot'
    local=ROOT/'.local';info=local.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==uid and not info.st_mode&0o022
            and info.st_mode&0o300==0o300, 'PRIVATE_V2_PARENT_NOT_SERVICE_WRITABLE')
    for path in (local/'router-registry',local/'router-registry/secrets'):
        if path.exists() or path.is_symlink():
            info=path.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid==uid and not info.st_mode&0o077
                    and info.st_mode&0o700==0o700, 'PRIVATE_REGISTRY_VAULT_REJECTED')
    for path in (root,root/'trust',root/'secrets'):
        info=path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==uid and not info.st_mode&0o077
                and info.st_mode&0o500==0o500, 'PRIVATE_PILOT_DIRECTORY_REQUIRED')
    name=read_file(root/'secrets/username',128,private=True,owners={uid}).decode()
    password=read_file(root/'secrets/password',1024,private=True,owners={uid}).decode()
    require(name=='v2-cebeci-ro' and password and not any(v in password for v in ('\x00','\r','\n')),
            'PRIVATE_PILOT_CREDENTIAL_FORMAT_REJECTED')
    ca=read_file(root/'trust/ca.pem',262144,private=True,owners={uid}).decode()
    require('PRIVATE KEY' not in ca, 'PUBLIC_CA_REQUIRED')
    tls_context(ca)
    expected={'HOST':'10.250.0.19','SOURCE_IP':'10.250.0.1','PORT':'8729',
              'LEAF_SHA256':'896addde343bf45b429aa354605ee1930d91c30c024c71fe182b94243937acb6'}
    for key,value in expected.items():
        require(values.get('V2_CEBECI_API_SSL_'+key,value)==value, 'PILOT_TLS_SCOPE_OVERRIDE_REJECTED')


def source_route():
    ip=shutil.which('ip',path='/usr/sbin:/usr/bin:/sbin:/bin')
    require(ip is not None,'IP_ROUTE_TOOL_REQUIRED')
    def query(args):
        result=run_tool([trusted_system_path(ip),'-j','-4',*args],timeout=5,env=TOOL_ENV)
        require(result.returncode==0 and len(result.stdout)<=262144, 'SOURCE_ROUTE_UNAVAILABLE')
        return json.loads(result.stdout)
    addresses=query(['address','show'])
    require(any(a.get('local')=='10.250.0.1' for item in addresses for a in item.get('addr_info',[])),
            'PILOT_SOURCE_ADDRESS_NOT_LOCAL')
    route=query(['route','get','10.250.0.19','from','10.250.0.1'])
    require(len(route)==1 and route[0].get('dev') and route[0].get('from')=='10.250.0.1'
            and route[0].get('type') not in ('blackhole','unreachable','prohibit'), 'PILOT_SOURCE_ROUTE_REJECTED')


def ask_path(label):
    with open('/dev/tty','r+') as tty:
        tty.write(label+' (mevcut dosyanın tam yolu): ');tty.flush()
        value=tty.readline().strip()
    require(bool(value), 'EXISTING_BACKUP_PATH_REQUIRED')
    return Path(value)


class BoundedTarInfo(tarfile.TarInfo):
    def _proc_member(self,archive):
        require(self.type in (tarfile.REGTYPE,tarfile.AREGTYPE,tarfile.DIRTYPE,
                tarfile.XHDTYPE,tarfile.XGLTYPE,tarfile.GNUTYPE_LONGNAME,tarfile.GNUTYPE_LONGLINK),
                'BACKUP_ARCHIVE_TYPE_REJECTED')
        require(0<=self.size<=512*1024*1024,'BACKUP_ARCHIVE_LIMIT')
        if self.type in (tarfile.XHDTYPE,tarfile.XGLTYPE,tarfile.GNUTYPE_LONGNAME,tarfile.GNUTYPE_LONGLINK):
            require(self.size<=65536,'BACKUP_ARCHIVE_METADATA_LIMIT')
        return super()._proc_member(archive)


def archive_matches(path,files,owners):
    seen=set(); total=0; expanded=0; count=0
    with regular_file(path,limit=512*1024*1024,private=True,owners=owners) as source, tarfile.open(fileobj=source,mode='r|*',tarinfo=BoundedTarInfo) as archive:
        for member in archive:
            expanded+=member.size;count+=1
            require(expanded<=512*1024*1024 and count<=20000, 'BACKUP_ARCHIVE_LIMIT')
            name=member.name.removeprefix('./').removeprefix(ROOT.name+'/')
            require(not name.startswith('/') and '..' not in Path(name).parts, 'BACKUP_ARCHIVE_PATH_REJECTED')
            if name not in files:
                continue
            require(name not in seen and member.isfile() and member.size==len(files[name]), 'BACKUP_ARCHIVE_ENTRY_REJECTED')
            total+=member.size;require(total<=256*1024*1024, 'BACKUP_ARCHIVE_LIMIT')
            stream=archive.extractfile(member)
            require(stream is not None and stream.read(member.size+1)==files[name], 'BACKUP_CODE_OR_DIST_MISMATCH')
            seen.add(name)
    require(seen==set(files), 'BACKUP_CODE_OR_DIST_INCOMPLETE')


def dump_valid(path,owners):
    tool=trusted_system_path('/usr/lib/postgresql/16/bin/pg_restore')
    with regular_file(path,limit=1024*1024*1024,private=True,owners=owners) as source:
        result=run_tool([tool,'--list','/proc/self/fd/'+str(source.fileno())],
            pass_fds=(source.fileno(),),timeout=30,max_output=4*1024*1024,env=TOOL_ENV)
    require(result.returncode==0 and len(result.stdout)<=4*1024*1024, 'BACKUP_DUMP_LIST_FAILED')
    toc=result.stdout.decode('utf8',errors='strict')
    require(re.search(r'^;\s+dbname: mikrotik_v26_acceptance\s*$',toc,re.M), 'BACKUP_DATABASE_IDENTITY_REJECTED')
    require(re.search(r'\bTABLE DATA v26_acceptance users\b',toc), 'BACKUP_USER_DATA_REQUIRED')
    require(re.search(r'\bTABLE DATA v26_acceptance subscribers\b',toc), 'BACKUP_SUBSCRIBER_DATA_REQUIRED')


def main():
    require(os.geteuid()==0 and sys.stdin.isatty(), 'ROOT_AND_INTERACTIVE_VDS_TTY_REQUIRED')
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'ISOLATED_NO_SITE_NO_BYTECODE_REQUIRED')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    require(ctypes.CDLL(None).prctl(4,0,0,0,0)==0, 'PRIVATE_PROCESS_REQUIRED')
    units={name:check(name,lambda n=name:unit(n)) for name in UNITS}
    api=units[UNITS[0]]
    require(api is not None, 'API_UNIT_REQUIRED')
    require(api.get('WorkingDirectory')==str(ROOT), 'API_WORKING_DIRECTORY_REJECTED')
    pid=int(api['MainPID']);process=Path('/proc')/str(pid)
    require(pid>0 and (process/'cwd').resolve()==ROOT, 'RUNNING_API_ROOT_REJECTED')
    info=process.stat();owners={0,info.st_uid,int(os.environ.get('SUDO_UID','0'))}
    raw_env=check('env_file_private',lambda:read_file(ENV_FILE,private=True,owners={0}))
    require(raw_env is not None, 'ROOT_PRIVATE_ENV_REQUIRED')
    file_values=environment_file(raw_env)
    require(str(ENV_FILE) in shlex.split(api.get('EnvironmentFiles','')), 'API_ENV_FILE_NOT_ATTACHED')
    active=dict(part.decode().split('=',1) for part in (process/'environ').read_bytes().split(b'\0') if b'=' in part)
    require(all(active.get(k)==v for k,v in file_values.items() if k.startswith('V2_')), 'ENV_FILE_AND_RUNNING_PROCESS_DIFFER')
    values={k:v for k,v in active.items() if k.startswith('V2_')}
    require(values.get('V2_ENVIRONMENT')=='v26-acceptance'
            and values.get('V2_DEPLOYMENT_PROFILE')=='v26-isolated-acceptance'
            and values.get('V2_API_PORT')=='18996' and values.get('V2_API_HOST')=='127.0.0.1'
            and values.get('V2_ROUTER_ONBOARDING_ENABLED')=='false'
            and values.get('V2_CEBECI_API_SSL_ENABLED')=='false'
            and not values.get('V2_ROUTER_ONBOARDING_OPERATOR_IDS',''), 'ACCEPTANCE_GENERIC_GATES_REJECTED')
    REPORT['env_process_scope']='PASS'
    python=(process/'cmdline').read_bytes().split(b'\0')[0].decode()
    require(Path(python).is_absolute() and str(Path(python)).startswith(str(ROOT)+'/')
            and Path(python).name.startswith('python'), 'API_INTERPRETER_REQUIRES_REVIEW')
    files=check('disk_code_snapshot',code_snapshot)
    check('running_code_and_health',lambda:active_code_identity(files))
    check('https_api_frontend_assets',lambda:frontend_live(files))
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        cookie=getpass.getpass('Mevcut gerçek V2.6 oturumunun v2_session değeri (gizli): ')
    identity=check('authenticated_local_admin',lambda:session_identity(cookie));del cookie
    check('capability_selection',lambda:selection(values,identity))
    check('private_tls_material',lambda:private_material(info.st_uid,values))
    check('source_route',source_route)
    check('readonly_database_dependencies',lambda:database(values,identity,info.st_uid,info.st_gid))
    if identity is not None and REPORT.get('session_database_match')=='PASS':
        REPORT['verified_operator_candidate']=identity  # ID/revision only; this creates no grant.
    check('rollback_db_dump',lambda:dump_valid(ask_path('V2.6 pg_dump yedeği'),owners|{pwd.getpwnam('postgres').pw_uid}))
    check('rollback_code_and_dist',lambda:archive_matches(ask_path('V2.6 backend/app + frontend/dist tar yedeği'),files or {},owners) if files else require(False,'CODE_SNAPSHOT_REQUIRED'))
    protected={ENV_FILE}
    for name,data in units.items():
        if data is None or name==UNITS[2]:
            continue
        env_paths=[v for v in shlex.split(data.get('EnvironmentFiles','')) if v.startswith('/')]
        for entry in shlex.split(data.get('FragmentPath',''))+shlex.split(data.get('DropInPaths',''))+env_paths:
            protected.add(Path(entry))
    for index,path in enumerate(sorted(protected)):
        check('rollback_config_'+str(index),lambda p=path:require(
            read_file(ask_path('V2.6 '+p.name+' geri dönüş yedeği'),private=True,owners=owners)==read_file(p),
            'BACKUP_CONFIG_MISMATCH'))
    final='PASS' if all(not isinstance(v,str) or v=='PASS' for v in REPORT.values()) else 'BLOCKED'
    print(json.dumps({'status':final,'checks':REPORT,'writes_performed':False,
        'expected_tables':list(TABLES),'allowed_registry_schemas':['public','v26_acceptance'],
        'required_privileges':['DATABASE CONNECT','SCHEMA USAGE','TABLE SELECT,INSERT,UPDATE'],
        'planned_runtime_layout':'vds-next','dump_restore_tested':False,'device_connection_performed':False,
        'incidental_access_logging_possible':True},sort_keys=True))
    return 0 if final=='PASS' else 1


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Blocked as error:
        print(json.dumps({'status':'BLOCKED','reason':str(error),'checks':REPORT,'writes_performed':False}))
        raise SystemExit(1)
    except (Exception,KeyboardInterrupt):
        print(json.dumps({'status':'BLOCKED','reason':'PREFLIGHT_UNAVAILABLE_OR_CANCELLED','checks':REPORT,'writes_performed':False}))
        raise SystemExit(1)
