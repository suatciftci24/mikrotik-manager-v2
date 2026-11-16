"""Allowlisted acceptance stages; never log credentials, headers, paths or response bodies."""
import hashlib
import json
import re
import socket
import ssl
import urllib.error
import urllib.request


class AcceptanceFailure(RuntimeError):
    def __init__(self,stage,code,details=None,transient=False):
        self.details=dict(failed_stage=stage,reason=code,**(details or {}))
        self.transient=transient
        super().__init__(code)


def step(stage,callback):
    try:return callback()
    except AcceptanceFailure:raise
    except Exception as error:
        info=dict(error_class=type(error).__name__)
        if isinstance(error,urllib.error.HTTPError):info['http_status']=error.code
        if isinstance(error,RuntimeError) and re.fullmatch('[A-Z0-9_]{1,96}',str(error)):info['guard_code']=str(error)
        raise AcceptanceFailure(stage,'ACCEPTANCE_STEP_FAILED',info) from None


def request(opener,origin,path,stage,body=None):
    # Report only generated, allowlisted endpoints; never query values, credentials
    # or an HTTPError's possibly redirected/private URL.
    allowed={'/','/api/ready','/api/v1/auth/login','/api/v1/auth/me','/api/v1/auth/logout',
             '/api/v1/dashboard/summary','/api/v1/router-workspace/routers',
             '/api/v1/subscriber-workspace','/api/v1/packages'}
    endpoint=path.split('?',1)[0]
    safe_path=endpoint if endpoint in allowed else '/assets/<redacted>' if endpoint.startswith('/assets/') else '<redacted>'
    safe_origin=origin if origin in ('https://v26.mikmanager.com.tr','http://127.0.0.1:15173','http://127.0.0.1:18996') else '<redacted>'
    target=dict(request_url=safe_origin+safe_path)
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(origin+path,data=data,headers={'Content-Type':'application/json'})
    try:
        with opener.open(req,timeout=10) as response:
            raw=response.read();status=response.status
            mime=response.headers.get('Content-Type','').split(';',1)[0].strip().lower()
    except urllib.error.HTTPError as error:
        raw=error.read()
        raise AcceptanceFailure(stage,'ACCEPTANCE_HTTP_STATUS',
            dict(**target,http_status=error.code,bytes=len(raw),body_sha256=hashlib.sha256(raw).hexdigest()),
            transient=error.code in (502,503,504)) from None
    except (urllib.error.URLError,OSError) as error:
        cause=error.reason if isinstance(error,urllib.error.URLError) else error
        kind='DNS' if isinstance(cause,socket.gaierror) else 'TLS' if isinstance(cause,ssl.SSLError) else (
             'TIMEOUT' if isinstance(cause,TimeoutError) else 'CONNECTION')
        raise AcceptanceFailure(stage,'ACCEPTANCE_TRANSPORT',dict(**target,transport=kind),transient=kind in ('TIMEOUT','CONNECTION')) from None
    if status!=200:raise AcceptanceFailure(stage,'ACCEPTANCE_HTTP_STATUS',dict(**target,http_status=status),transient=status in (502,503,504))
    expected=None
    if path.startswith('/api/'):expected={'application/json'}
    elif path=='/':expected={'text/html'}
    elif path.startswith('/assets/'):
        if path.endswith('.js'):expected={'application/javascript','text/javascript'}
        elif path.endswith('.css'):expected={'text/css'}
    if expected is not None and mime not in expected:
        raise AcceptanceFailure(stage,'ACCEPTANCE_CONTENT_TYPE_REJECTED',dict(**target,http_status=status))
    return raw


def wait_ready(check,sleep,attempts=20):
    for attempt in range(1,attempts+1):
        try:return check()
        except AcceptanceFailure as error:
            error.details['attempts']=attempt
            if not error.transient or attempt==attempts:raise
            sleep(1)
