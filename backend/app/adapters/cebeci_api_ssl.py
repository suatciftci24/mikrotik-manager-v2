"""Bounded read-only RouterOS API-SSL transport. Not registered as a live provider.

Current DEVICE_READ authorization remains closed even when configuration is requested.
Only mocked tests exercise the wire path in this phase. No polling, writes or retries.
"""
import hashlib
import hmac
import os
import socket
import ssl
import time
from threading import Lock
from typing import Literal
from pydantic import Field,StrictBool,model_validator
from app.integrations.cebeci_access import AccessPlan,ClosedContract,ReadIntent,prepare_offline_tls_context
from app.integrations.cebeci_preparation import authorize,project_fixture_row


class ApiSslStop(RuntimeError):
    """Only fixed codes, never device messages, credentials, packets or underlying exceptions."""


class ApiSslConfiguration(ClosedContract):
    enabled:StrictBool=False
    candidate_id:Literal['CEBECI_TOWERS']='CEBECI_TOWERS'
    host:Literal['10.250.0.19']='10.250.0.19'
    source_ip:Literal['10.250.0.1']='10.250.0.1'
    port:Literal[8729]=8729
    public_ca_pem:str=Field(default='',repr=False,exclude=True,max_length=262144)
    public_leaf_sha256:str=Field(default='',repr=False,pattern=r'^(?:[a-f0-9]{64})?$')
    connect_timeout:float=Field(default=2,ge=.1,le=5,allow_inf_nan=False)
    io_timeout:float=Field(default=2,ge=.1,le=5,allow_inf_nan=False)
    total_timeout:float=Field(default=10,ge=1,le=30,allow_inf_nan=False)
    @model_validator(mode='after')
    def closed_without_trust(self):
        if self.enabled and (not self.public_ca_pem or not self.public_leaf_sha256):raise ValueError('PUBLIC_TRUST_REQUIRED')
        if max(self.connect_timeout,self.io_timeout)>self.total_timeout:raise ValueError('INVALID_TIME_BUDGET')
        return self


def configuration_from_environment():
    """V2-only keys. Never opens .env, V1 config, files, databases or a secret store."""
    try:
        requested=os.environ.get('V2_CEBECI_API_SSL_ENABLED','false')
        if requested not in ('true','false'):raise ValueError('INVALID_ENABLE_FLAG')
        return ApiSslConfiguration(enabled=requested=='true',
            host=os.environ.get('V2_CEBECI_API_SSL_HOST','10.250.0.19'),
            source_ip=os.environ.get('V2_CEBECI_API_SSL_SOURCE_IP','10.250.0.1'),
            port=int(os.environ.get('V2_CEBECI_API_SSL_PORT','8729')),
            public_ca_pem=os.environ.get('V2_CEBECI_API_SSL_CA_PEM',''),
            public_leaf_sha256=os.environ.get('V2_CEBECI_API_SSL_LEAF_SHA256',''),
            connect_timeout=float(os.environ.get('V2_CEBECI_API_SSL_CONNECT_TIMEOUT','2')),
            io_timeout=float(os.environ.get('V2_CEBECI_API_SSL_IO_TIMEOUT','2')),
            total_timeout=float(os.environ.get('V2_CEBECI_API_SSL_TOTAL_TIMEOUT','10')))
    except (ValueError,TypeError):raise ApiSslStop('CONFIGURATION_REJECTED') from None


def adapter_status(user):
    authorize(user)
    # Pure status: don't load configuration or resolve secrets to render ADMIN plans.
    return dict(implemented=True,connection='NOT CONNECTED',readiness='NOT READY',execution_enabled=False,
        provider_registered=False,decision='NO_GO',reason='DEVICE_EXECUTION_NOT_AUTHORIZED')


def _encoded_word(word):
    data=word.encode('utf8')
    if len(data)>4096:raise ApiSslStop('WORD_LIMIT')
    size=len(data)
    prefix=bytes([size]) if size<0x80 else (size|0x8000).to_bytes(2,'big')
    return prefix+data


class _Wire:
    """RouterOS framing, exact print queries only. Shared total budget across auth and reads."""
    def __init__(self,stream,deadline,io_timeout):
        self.stream=stream;self.deadline=deadline;self.io_timeout=io_timeout;self.bytes=0;self.sentences=0
    def timeout(self):
        left=self.deadline-time.monotonic()
        if left<=0:raise ApiSslStop('DEADLINE_EXCEEDED')
        self.stream.settimeout(min(self.io_timeout,left))
    def _receive(self,size):
        data=bytearray()
        while len(data)<size:
            self.timeout();chunk=self.stream.recv(size-len(data))
            if not chunk:raise ApiSslStop('UNEXPECTED_EOF')
            self.bytes+=len(chunk)
            if self.bytes>262144:raise ApiSslStop('RESPONSE_BYTE_LIMIT')
            data.extend(chunk)
        return bytes(data)
    def _length(self):
        first=self._receive(1)[0]
        if first<0x80:size=first
        elif first<0xC0:size=((first&0x3F)<<8)|int.from_bytes(self._receive(1),'big')
        elif first<0xE0:size=((first&0x1F)<<16)|int.from_bytes(self._receive(2),'big')
        elif first<0xF0:size=((first&0x0F)<<24)|int.from_bytes(self._receive(3),'big')
        elif first==0xF0:size=int.from_bytes(self._receive(4),'big')
        else:raise ApiSslStop('RESERVED_PROTOCOL_LENGTH')
        if size>4096:raise ApiSslStop('WORD_LIMIT')
        return size
    def sentence(self):
        self.sentences+=1
        if self.sentences>256:raise ApiSslStop('SENTENCE_LIMIT')
        words=[]
        while True:
            length=self._length()
            if length==0:return words
            if len(words)>=32:raise ApiSslStop('FIELD_LIMIT')
            try:words.append(self._receive(length).decode('utf8',errors='strict'))
            except UnicodeError:raise ApiSslStop('INVALID_TEXT') from None
    def send(self,words):
        self.timeout();self.stream.sendall(b''.join(_encoded_word(word) for word in words)+b'\x00')
    def login(self):
        # Resolve only AFTER verified TLS, SAN, pin and source checks; don't retain credentials.
        self.timeout()
        name=os.environ.get('V2_CEBECI_API_SSL_USERNAME','')
        password=os.environ.get('V2_CEBECI_API_SSL_PASSWORD','')
        import re
        if not re.fullmatch(r'v2-[A-Za-z0-9_-]{1,56}',name) or not 1<=len(password.encode('utf8'))<=1024:
            raise ApiSslStop('DEDICATED_CREDENTIAL_REQUIRED')
        self.send(('/login','=name='+name,'=password='+password))
        if self.sentence()!=['!done']:raise ApiSslStop('AUTHENTICATION_REJECTED')
    def read(self,intent):
        self.send((intent.menu+'/print','=.proplist='+','.join(intent.properties)))
        rows=[]
        while True:
            words=self.sentence()
            if words==['!done']:return tuple(rows)
            if not words or words[0]!='!re':raise ApiSslStop('DEVICE_REPLY_REJECTED')
            row={}
            for word in words[1:]:
                parts=word.split('=',2)
                if len(parts)!=3 or parts[0]!='' or parts[1] not in intent.properties or parts[1] in row:
                    raise ApiSslStop('UNEXPECTED_RESPONSE_FIELD')
                row[parts[1]]=parts[2]
            markers=('password=','passwd=','psk=','secret=','token=','auth-key=','enc-key=','api-key=','secretref:','-----begin')
            if any(any(marker in value.lower() for marker in markers) or any(ord(char)<32 for char in value) for value in row.values()):
                raise ApiSslStop('UNSAFE_OR_MISSING_RESPONSE_FIELD')
            safe=project_fixture_row(intent.menu,row)  # Same metadata sanitizer; no raw response escapes.
            if set(row)!=set(intent.properties) or set(safe)!=set(row):raise ApiSslStop('UNSAFE_OR_MISSING_RESPONSE_FIELD')
            rows.append(safe)
            if len(rows)>128:raise ApiSslStop('ROW_LIMIT')


class CebeciApiSslAdapter:
    """Narrow PilotReadAdapter implementation; no generic execute or mutation methods."""
    def __init__(self,user,configuration:ApiSslConfiguration|None=None):
        authorize(user)
        try:self._configuration=ApiSslConfiguration.model_validate(dict((configuration or configuration_from_environment()).__dict__))
        except (ValueError,AttributeError):raise ApiSslStop('CONFIGURATION_REJECTED') from None
        self._user=user;self._stopped=False;self._lock=Lock()
    def read_metadata(self,intent:ReadIntent)->tuple[dict,...]:
        # Existing server-side gate is intentionally still closed for all production callers.
        authorize(self._user,self._configuration.candidate_id,purpose='DEVICE_READ')
        if not self._lock.acquire(blocking=False):raise ApiSslStop('ADAPTER_BUSY')
        raw=None;secure=None
        try:
            if self._stopped:raise ApiSslStop('ADAPTER_STOPPED')
            cfg=ApiSslConfiguration.model_validate(dict(self._configuration.__dict__))
            if not cfg.enabled:raise ApiSslStop('ADAPTER_DISABLED')
            try:intent=ReadIntent.model_validate(dict(intent.__dict__))
            except (ValueError,AttributeError):raise ApiSslStop('COMMAND_REJECTED') from None
            plan=AccessPlan(reviewed_management_pin=cfg.host,reviewed_source_cidr=cfg.source_ip+'/32',public_certificate_sha256=cfg.public_leaf_sha256)
            context=prepare_offline_tls_context(self._user,plan,public_ca_pem=cfg.public_ca_pem)
            if context.verify_mode!=ssl.CERT_REQUIRED or context.check_hostname is not True or context.minimum_version<ssl.TLSVersion.TLSv1_2 or context.hostname_checks_common_name is not False:
                raise ApiSslStop('TLS_POLICY_REJECTED')
            deadline=time.monotonic()+cfg.total_timeout
            raw=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            raw.settimeout(min(cfg.connect_timeout,cfg.total_timeout));raw.bind((cfg.source_ip,0));raw.connect((cfg.host,cfg.port))
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ApiSslStop('DEADLINE_EXCEEDED')
            raw.settimeout(min(cfg.connect_timeout,remaining))
            secure=context.wrap_socket(raw,server_hostname=cfg.host)
            if secure.getpeername()[:2]!=(cfg.host,cfg.port) or secure.getsockname()[0]!=cfg.source_ip:raise ApiSslStop('ENDPOINT_OR_SOURCE_MISMATCH')
            if secure.version() not in ('TLSv1.2','TLSv1.3'):raise ApiSslStop('TLS_POLICY_REJECTED')
            certificate=secure.getpeercert(binary_form=True)
            if not certificate or not hmac.compare_digest(hashlib.sha256(certificate).hexdigest(),cfg.public_leaf_sha256):raise ApiSslStop('CERTIFICATE_PIN_MISMATCH')
            if ('IP Address',cfg.host) not in secure.getpeercert().get('subjectAltName',()):raise ApiSslStop('CERTIFICATE_SAN_MISMATCH')
            wire=_Wire(secure,deadline,cfg.io_timeout);wire.login()
            identity=wire.read(ReadIntent(menu='/system/identity',properties=('name',)))
            if identity!=({'name':plan.expected_identity},):raise ApiSslStop('ROUTER_IDENTITY_MODEL_VERSION_MISMATCH')
            resource=wire.read(ReadIntent(menu='/system/resource',properties=('board-name','version')))
            if len(resource)!=1 or resource[0]['board-name']!=plan.expected_model or resource[0]['version'] not in (plan.expected_version,plan.expected_version+' (stable)'):
                raise ApiSslStop('ROUTER_IDENTITY_MODEL_VERSION_MISMATCH')
            result=wire.read(intent);wire.timeout()  # Don't report success after the total deadline.
            return result
        except ApiSslStop:
            self._stopped=True;raise
        except ssl.SSLError:
            self._stopped=True;raise ApiSslStop('TLS_VERIFICATION_FAILED') from None
        except TimeoutError:
            self._stopped=True;raise ApiSslStop('CONNECTION_TIMEOUT') from None
        except Exception:
            self._stopped=True;raise ApiSslStop('API_SSL_STOP') from None
        finally:
            for stream in (secure,raw):
                if stream is not None:
                    try:stream.close()
                    except Exception:pass
            self._lock.release()
