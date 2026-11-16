"""Pure central-development invariants; no IO or deployment on import."""
import hashlib
import json
import re
import time
import math

ORIGIN='https://v26.mikmanager.com.tr'
APP='/srv/mikrotik-v26-next'
DB='mikrotik_v26_acceptance'
BASELINE='b4e78a44685f83e58bb37684712236a33c5ccbaf'


def require(value,code):
    if not value:raise RuntimeError(code)


def database_fingerprint(value):
    require(value.get('database')==DB and value.get('port')=='55433' and
            value.get('data_directory')=='/var/lib/postgresql/16/v26' and
            str(value.get('system_identifier','')).isdigit() and str(value.get('oid','')).isdigit(),
            'CENTRAL_DATABASE_REJECTED')
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def complete_receipts(receipts,profile,now=None):
    now=time.time() if now is None else now
    expected=dict(origin=ORIGIN,instance=profile['instance'],release=profile['commit'],database=profile['database'])
    chosen={}
    for value in receipts:
        location=value.get('location')
        if location not in ('home','office'):continue
        if any(value.get(key)!=item for key,item in expected.items()):continue
        captured=value.get('captured_at')
        if type(captured) not in (int,float) or not math.isfinite(captured) or not 0<=now-captured<=600:continue
        if not all(re.fullmatch('[0-9a-f]{64}',value.get(key,'')) for key in ('machine','view_hash','build_id')):continue
        if location not in chosen or value['captured_at']>chosen[location]['captured_at']:chosen[location]=value
    if set(chosen)!={'home','office'}:return 'HOME_AND_OFFICE_OBSERVATIONS_REQUIRED'
    if chosen['home']['machine']==chosen['office']['machine']:return 'INDEPENDENT_MACHINES_REQUIRED'
    if any(chosen['home'][key]!=chosen['office'][key] for key in ('view_hash','build_id')):
        return 'HOME_OFFICE_VERSION_OR_DATA_DIFFER'
    return None


SECURITY_HEADERS={'X-Content-Type-Options':'nosniff','X-Frame-Options':'SAMEORIGIN',
                  'Referrer-Policy':'strict-origin-when-cross-origin','Cache-Control':'no-store'}


def public_header_checks(headers,profile):
    checks={key:headers.get('X-V26-'+key)==profile[field] for key,field in
            [('Instance','instance'),('Release','commit'),('Database','database')]}
    checks.update({key:headers.get(key)==value for key,value in SECURITY_HEADERS.items()})
    checks['Content-Type']=headers.get('Content-Type','').split(';',1)[0].strip().lower()=='text/html'
    return checks


def static_config(root,runtime,profile):
    require(re.fullmatch('[0-9a-f]{40}',profile['commit']) is not None,'RELEASE_COMMIT_REJECTED')
    require(re.fullmatch('[0-9a-f]{64}',profile['database']) is not None,'DATABASE_FINGERPRINT_REJECTED')
    require(re.fullmatch('[0-9a-f-]{36}',profile['instance']) is not None,'CENTRAL_INSTANCE_REJECTED')
    require(root.startswith(APP+'/.local/central/') and runtime.startswith(APP+'/.local/central/')
            and not any(c in root+runtime for c in '\n\r;{}"$ '),'STATIC_PATH_REJECTED')
    return f'''daemon off;
worker_processes 1;
pid {runtime}/nginx.pid;
error_log {runtime}/error.log;
working_directory {APP}/frontend;
events {{ worker_connections 128; }}
http {{
 include /etc/nginx/mime.types;
 default_type application/octet-stream;
 access_log off;
 client_body_temp_path {runtime}/body;
 proxy_temp_path {runtime}/proxy;
 fastcgi_temp_path {runtime}/fastcgi;
 uwsgi_temp_path {runtime}/uwsgi;
 scgi_temp_path {runtime}/scgi;
 server {{
  listen 127.0.0.1:15173;
  server_name v26.mikmanager.com.tr;
  root {root};
  add_header X-V26-Instance "{profile['instance']}" always;
  add_header X-V26-Release "{profile['commit']}" always;
  add_header X-V26-Database "{profile['database']}" always;
  add_header Cache-Control "no-store" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "SAMEORIGIN" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  location ~ (^|/)\\. {{ return 404; }}
  location /src/ {{ return 404; }}
  location /@vite {{ return 404; }}
  location /@react-refresh {{ return 404; }}
  location /api/ {{ return 404; }}
  location / {{ try_files $uri $uri/ /index.html; }}
 }}
}}
'''
