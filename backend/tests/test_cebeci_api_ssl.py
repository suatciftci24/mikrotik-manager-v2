"""Only mocked transport: socket creation is always patched; no listener/device or real TLS IO."""
import hashlib
import os
import ssl
from contextlib import ExitStack
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock,patch
from fastapi import HTTPException
from app.adapters import cebeci_api_ssl as api
from app.integrations.cebeci_access import ReadIntent
from app.integrations.cebeci_preparation import profile
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS

DER=b'SYNTHETIC_PUBLIC_CERT_NOT_A_REAL_CERT'
PIN=hashlib.sha256(DER).hexdigest()
ENV={'V2_CEBECI_API_SSL_USERNAME':'v2-fixture','V2_CEBECI_API_SSL_PASSWORD':'SYNTHETIC_SECRET_CANARY'}
def sentence(*words):
    # Independent short-word fixtures from the published RouterOS framing format.
    result=b''
    for word in words:
        data=word.encode();size=len(data)
        result+=(bytes([size]) if size<128 else bytes([0x80+(size>>8),size&255]))+data
    return result+b'\0'
def response(menu='fixture-interface',identity='CEBECI_TOWERS',model='RB3011UiAS',version='6.49.19',last=None):
    return sentence('!done')+sentence('!re','=name='+identity)+sentence('!done')+sentence('!re','=board-name='+model,'=version='+version)+sentence('!done')+(last if last is not None else sentence('!re','=name='+menu)+sentence('!done'))
class FakeTls:
    def __init__(self,data):self.data=data;self.sent=b'';self.closed=False;self.timeouts=[];self.peer=('10.250.0.19',8729);self.local=('10.250.0.1',55555);self.der=DER;self.san=(('IP Address','10.250.0.19'),)
    def recv(self,n):out=self.data[:min(n,3)];self.data=self.data[len(out):];return out
    def sendall(self,data):self.sent+=data
    def settimeout(self,t):self.timeouts.append(t)
    def close(self):self.closed=True
    def getpeername(self):return self.peer
    def getsockname(self):return self.local
    def getpeercert(self,binary_form=False):return self.der if binary_form else {'subjectAltName':self.san}
    def version(self):return 'TLSv1.2'

class ApiSslTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap());self.intent=ReadIntent(menu='/interface',properties=('name',))
    def cfg(self,**kw):return api.ApiSslConfiguration(**{**dict(enabled=True,public_ca_pem='SYNTHETIC_PUBLIC_CA_FIXTURE',public_leaf_sha256=PIN),**kw})
    def mocked(self,data=None):
        stack=ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch.dict(os.environ,ENV,clear=True))
        # Production authorization is closed; this localized mock simulates a future authorized call.
        stack.enter_context(patch.object(api,'authorize',return_value=None))
        raw=Mock();tls=FakeTls(response() if data is None else data)
        context=Mock(verify_mode=ssl.CERT_REQUIRED,check_hostname=True,minimum_version=ssl.TLSVersion.TLSv1_2,hostname_checks_common_name=False)
        context.wrap_socket.return_value=tls
        factory=stack.enter_context(patch.object(api.socket,'socket',return_value=raw))
        builder=stack.enter_context(patch.object(api,'prepare_offline_tls_context',return_value=context))
        return raw,tls,context,factory,builder
    def test_default_configuration_disabled_and_only_v2_environment_keys(self):
        with patch.dict(os.environ,{'MIKROTIK_PASSWORD':'SYNTHETIC_SECRET_CANARY','API_HOST':'OTHER'},clear=True):
            cfg=api.configuration_from_environment()
        self.assertFalse(cfg.enabled);self.assertEqual(cfg.host,'10.250.0.19');self.assertEqual(cfg.source_ip,'10.250.0.1');self.assertEqual(cfg.port,8729)
        self.assertNotIn('SYNTHETIC_PUBLIC_CA_FIXTURE',repr(self.cfg()))
    def test_bad_scope_plain_port_bypass_flags_timeout_and_incomplete_trust_rejected(self):
        for update in ({'host':'OTHER_ROUTER'},{'source_ip':'0.0.0.0'},{'port':8728},{'verify':False},{'enabled':1},{'io_timeout':float('nan')},{'total_timeout':999},{'public_ca_pem':''},{'public_leaf_sha256':''}):
            with self.assertRaises(ValueError):self.cfg(**update)
        for env in ({'V2_CEBECI_API_SSL_ENABLED':'yes'},{'V2_CEBECI_API_SSL_HOST':'SECRET_CANARY'},{'V2_CEBECI_API_SSL_ENABLED':'true'},{'V2_CEBECI_API_SSL_PORT':'SECRET_CANARY'}):
            with patch.dict(os.environ,env,clear=True),self.assertRaises(api.ApiSslStop) as error:api.configuration_from_environment()
            self.assertEqual(str(error.exception),'CONFIGURATION_REJECTED')
    def test_current_authorization_blocks_even_requested_config_before_socket_or_secret(self):
        with patch.object(api.socket,'socket',side_effect=AssertionError('No sockets')),patch.object(api,'prepare_offline_tls_context',side_effect=AssertionError('No trust loading')):
            client=api.CebeciApiSslAdapter(self.user,self.cfg())
            with self.assertRaises(HTTPException) as failure:client.read_metadata(self.intent)
        self.assertEqual(failure.exception.status_code,403)
    def test_disabled_adapter_and_write_or_unlisted_descriptor_never_reach_tls(self):
        raw,tls,ctx,factory,builder=self.mocked()
        with self.assertRaisesRegex(api.ApiSslStop,'ADAPTER_DISABLED'):api.CebeciApiSslAdapter(self.user,api.ApiSslConfiguration()).read_metadata(self.intent)
        for change in ({'operation':'set'},{'menu':'/system/script'},{'menu':'/system/scheduler'},{'menu':'/ip/firewall'},{'menu':'/ppp/secret'},{'properties':('password',)},{'properties':('name',),'query':'remove'}):
            with self.assertRaisesRegex(api.ApiSslStop,'COMMAND_REJECTED'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent.model_copy(update=change))
        factory.assert_not_called();builder.assert_not_called()
    def test_mocked_success_binds_source_uses_verified_tls_pin_and_only_print_frames(self):
        raw,tls,ctx,factory,builder=self.mocked();client=api.CebeciApiSslAdapter(self.user,self.cfg())
        self.assertEqual(client.read_metadata(self.intent),({'name':'fixture-interface'},))
        raw.bind.assert_called_once_with(('10.250.0.1',0));raw.connect.assert_called_once_with(('10.250.0.19',8729))
        ctx.wrap_socket.assert_called_once_with(raw,server_hostname='10.250.0.19')
        self.assertEqual(tls.sent,sentence('/login','=name=v2-fixture','=password=SYNTHETIC_SECRET_CANARY')+sentence('/system/identity/print','=.proplist=name')+sentence('/system/resource/print','=.proplist=board-name,version')+sentence('/interface/print','=.proplist=name'))
        self.assertTrue(tls.closed);raw.close.assert_called_once();self.assertTrue(all(0<t<=2 for t in tls.timeouts))
        raw,tls,ctx,factory,builder=self.mocked(response(version='6.49.19 (stable)'))
        self.assertEqual(api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent),({'name':'fixture-interface'},))
    def test_chain_or_hostname_verification_error_redacted_and_no_credentials_sent(self):
        raw,tls,ctx,factory,builder=self.mocked();ctx.wrap_socket.side_effect=ssl.SSLCertVerificationError('SECRET_CANARY')
        with self.assertRaisesRegex(api.ApiSslStop,'^TLS_VERIFICATION_FAILED$') as error:api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        self.assertNotIn('SECRET',str(error.exception));self.assertEqual(tls.sent,b'');raw.close.assert_called_once()
    def test_weak_context_rejected_before_tcp(self):
        raw,tls,ctx,factory,builder=self.mocked()
        for attr,value in [('verify_mode',ssl.CERT_NONE),('check_hostname',False),('minimum_version',ssl.TLSVersion.TLSv1_1),('hostname_checks_common_name',True)]:
            before=getattr(ctx,attr);setattr(ctx,attr,value)
            with self.assertRaisesRegex(api.ApiSslStop,'TLS_POLICY_REJECTED'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
            setattr(ctx,attr,before)
        factory.assert_not_called()
    def test_pin_san_source_and_peer_mismatch_stop_before_auth_and_latch(self):
        for attr,value,code in [('der',b'WRONG_PUBLIC_CERT','CERTIFICATE_PIN_MISMATCH'),('san',(('DNS','other'),),'CERTIFICATE_SAN_MISMATCH'),('peer',('10.250.0.20',8729),'ENDPOINT_OR_SOURCE_MISMATCH'),('local',('10.250.0.2',123),'ENDPOINT_OR_SOURCE_MISMATCH')]:
            raw,tls,ctx,factory,builder=self.mocked();setattr(tls,attr,value);client=api.CebeciApiSslAdapter(self.user,self.cfg())
            with self.assertRaisesRegex(api.ApiSslStop,code):client.read_metadata(self.intent)
            self.assertEqual(tls.sent,b'');self.assertTrue(tls.closed)
            with self.assertRaisesRegex(api.ApiSslStop,'ADAPTER_STOPPED'):client.read_metadata(self.intent)
            factory.assert_called_once()
    def test_wrong_identity_stops_immediately_before_resource_and_user_read(self):
        raw,tls,ctx,factory,builder=self.mocked(response(identity='WRONG'))
        with self.assertRaisesRegex(api.ApiSslStop,'ROUTER_IDENTITY_MODEL_VERSION_MISMATCH'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        self.assertNotIn(b'/system/resource/print',tls.sent);self.assertNotIn(b'/interface/print',tls.sent)
    def test_wrong_model_or_version_stop_before_user_read(self):
        for kw in ({'model':'OTHER'},{'version':'7.16.2'},{'version':'6.49.190'},{'version':'6.49.19 (unreviewed)'}):
            raw,tls,ctx,factory,builder=self.mocked(response(**kw))
            with self.assertRaisesRegex(api.ApiSslStop,'ROUTER_IDENTITY_MODEL_VERSION_MISMATCH'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
            self.assertNotIn(b'/interface/print',tls.sent)
    def test_secret_extra_duplicate_missing_or_trap_reply_never_exported_or_logged(self):
        replies=[sentence('!re','=name=fixture','=password=SECRET_CANARY'),sentence('!re','=name=x','=name=y'),sentence('!re'),sentence('!re','=name=password=SECRET_CANARY'),sentence('!re','=name=PSK=SECRET_CANARY'),sentence('!re','=name=-----BEGIN PRIVATE KEY-----'),sentence('!re','=name=line\nSECRET_CANARY'),sentence('!trap','=message=SECRET_CANARY')]
        for reply in replies:
            raw,tls,ctx,factory,builder=self.mocked(response(last=reply+sentence('!done')))
            with self.assertNoLogs(level='DEBUG'),self.assertRaises(api.ApiSslStop) as error:api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
            self.assertNotIn('SECRET',str(error.exception));self.assertTrue(tls.closed)
    def test_auth_error_or_missing_v2_secret_does_not_fallback(self):
        raw,tls,ctx,factory,builder=self.mocked(sentence('!trap','=message=SECRET_CANARY'))
        with self.assertRaisesRegex(api.ApiSslStop,'AUTHENTICATION_REJECTED'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        with patch.dict(os.environ,{'V1_PASSWORD':'SECRET_CANARY'},clear=True),self.assertRaisesRegex(api.ApiSslStop,'DEDICATED_CREDENTIAL_REQUIRED'):
            api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
    def test_timeout_deadline_unknown_failure_cleanup_and_redaction(self):
        raw,tls,ctx,factory,builder=self.mocked();tls.recv=Mock(side_effect=TimeoutError('SECRET_CANARY'))
        with self.assertRaisesRegex(api.ApiSslStop,'^CONNECTION_TIMEOUT$'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        raw,tls,ctx,factory,builder=self.mocked()
        with patch.object(api.time,'monotonic',side_effect=[0,20]),self.assertRaisesRegex(api.ApiSslStop,'DEADLINE_EXCEEDED'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        ctx.wrap_socket.assert_not_called();raw.close.assert_called_once()
        raw,tls,ctx,factory,builder=self.mocked();raw.connect.side_effect=OSError('SECRET_CANARY')
        with self.assertRaisesRegex(api.ApiSslStop,'^API_SSL_STOP$'):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
    def test_frame_word_row_and_total_byte_limits_fail_closed(self):
        for data,code in [(b'\xf8','RESERVED_PROTOCOL_LENGTH'),(b'\xf0\0\x10\0\0','WORD_LIMIT'),(b'','UNEXPECTED_EOF'),(b'\x02\xff\xff','INVALID_TEXT')]:
            raw,tls,ctx,factory,builder=self.mocked(data)
            with self.assertRaisesRegex(api.ApiSslStop,code):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        for last,code in [(sentence('!re','=name=x')*129+sentence('!done'),'ROW_LIMIT'),(sentence('!re','=name='+'x'*4090)*70+sentence('!done'),'RESPONSE_BYTE_LIMIT')]:
            raw,tls,ctx,factory,builder=self.mocked(response(last=last))
            with self.assertRaisesRegex(api.ApiSslStop,code):api.CebeciApiSslAdapter(self.user,self.cfg()).read_metadata(self.intent)
        self.assertEqual(api._encoded_word('abc'),b'\x03abc');self.assertEqual(api._encoded_word('a'*128),b'\x80\x80'+b'a'*128)
    def test_admin_status_is_pure_and_demo_baselines_remain_untouched(self):
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch.object(api.socket,'socket',side_effect=AssertionError('No socket')),patch.object(api,'configuration_from_environment',side_effect=AssertionError('No env on UI')):
            result=profile(self.user);self.assertEqual(result,profile(self.user))
        self.assertEqual((ROUTERS,SUBSCRIBERS),before);status=result['access_preparation']['api_ssl_adapter']
        self.assertFalse(status['execution_enabled']);self.assertEqual(status['readiness'],'NOT READY');self.assertFalse(status['provider_registered'])
        with self.assertRaises(HTTPException):api.adapter_status({**self.user,'role_code':'VIEWER'})
