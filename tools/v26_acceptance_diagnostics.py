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


TEST_SUITE='backend.tests.test_v26_central_development'


def test_evidence(command,cwd,env,evidence,target,timeout=60):
    """Persist an allowlisted structural projection; raw test output never reaches disk."""
    import ast
    import os
    from pathlib import Path
    import subprocess
    cwd=Path(cwd);evidence=Path(evidence)
    expected=['-B','-m','unittest','-v',TEST_SUITE]
    if command[1:]!=expected or command[0]!=str(cwd.parent.parent/'dev-venv/bin/python') or not re.fullmatch('[0-9a-f]{40}',target):
        raise RuntimeError('TEST_EVIDENCE_COMMAND_REJECTED')
    info=evidence.lstat()
    if evidence.resolve()!=evidence or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('TEST_EVIDENCE_DIRECTORY_REJECTED')
    source=cwd/'backend/tests/test_v26_central_development.py'
    tree=ast.parse(source.read_text())
    ids={TEST_SUITE+'.'+cls.name+'.'+method.name for cls in tree.body if isinstance(cls,ast.ClassDef)
         for method in cls.body if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) and method.name.startswith('test_')}
    ids.add('unittest.loader._FailedTest.'+TEST_SUITE)
    ids.add('unittest.loader._FailedTest.'+TEST_SUITE.split('.')[-1])
    failures=set()
    def filtered(raw):
        raw=raw or b''
        if isinstance(raw,bytes):raw=raw.decode('utf-8','replace')
        safe=[]
        for line in raw.splitlines():
            match=re.match(r'^(FAIL|ERROR): [\w.]+ \(([^)]+)\)',line)
            if match and match[2] in ids:
                failures.add(match[2]);safe.append(match[1]+': '+match[2]);continue
            match=re.match(r'^\w+ \(([^)]+)\).*\.\.\. (ok|FAIL|ERROR|skipped)',line)
            if match and match[1] in ids:
                safe.append(match[1]+' ... '+match[2]);continue
            if re.fullmatch(r'Ran \d+ tests? in \d+(?:\.\d+)?s',line) or line=='OK' or re.fullmatch(r'FAILED \((?:failures=\d+|errors=\d+|skipped=\d+)(?:, (?:failures=\d+|errors=\d+|skipped=\d+))*\)',line):
                safe.append(line);continue
            match=re.match(r'^\s*File "([^"]+)", line (\d+)',line)
            if match:
                path=Path(match[1])
                try:relative=str(path.relative_to(cwd))
                except ValueError:relative='<external>'
                if relative!='<external>' and not re.fullmatch(r'(backend|tools)/[A-Za-z0-9_./-]+\.py',relative):relative='<external>'
                safe.append('frame '+relative+':'+match[2]);continue
            match=re.match(r'^(AssertionError|ImportError|ModuleNotFoundError|AttributeError|TypeError|ValueError|RuntimeError|PermissionError|FileNotFoundError|SyntaxError|OSError|TimeoutError):',line)
            if match:safe.append('exception '+match[1])
        return '\n'.join(safe)+'\n'
    code=None;error_class=None;out=b'';err=b''
    try:
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,timeout=timeout)
        code=result.returncode;out=result.stdout;err=result.stderr
    except subprocess.TimeoutExpired as error:
        error_class='TimeoutExpired';out=error.stdout;err=error.stderr
    except OSError:error_class='OSError'
    stdout=filtered(out);stderr=filtered(err)
    report=dict(command=command,cwd=str(cwd),target_commit=target,exit_code=code,
                status='TESTS_PASS' if code==0 else 'BLOCKED',failed_tests=sorted(failures),
                error_class=error_class,output_policy='allowlisted-structure-no-messages-or-source-lines')
    for name,value in [('targeted-tests.stdout.log',stdout),('targeted-tests.stderr.log',stderr),
                       ('targeted-tests.json',json.dumps(report,indent=2)+'\n')]:
        descriptor=os.open(evidence/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as stream:stream.write(value)
    return report
