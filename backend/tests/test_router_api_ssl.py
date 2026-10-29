"""Transport is always mocked; exercise source/TLS/protocol before any live IO."""
import hashlib
import ssl
from unittest import TestCase
from unittest.mock import Mock,patch
from app.adapters import router_api_ssl as transport
from app.adapters.cebeci_api_ssl import ApiSslStop
from backend.tests.test_cebeci_api_ssl import FakeTls,response,sentence,DER

class RouterTransportTests(TestCase):
    def setUp(self):
        self.target=transport.Target('10.77.0.2',8729,'SYNTHETIC_PUBLIC_CA',hashlib.sha256(DER).hexdigest())
        self.policy=transport.ConnectionPolicy(True,'10.77.0.1',('10.77.0.0/24',))
        self.credentials=('operator-ro','SYNTHETIC_PASSWORD_CANARY')
        self.client=transport.RouterApiSslClient()
        self.raw=Mock();self.tls=FakeTls(response(identity='LAB',model='LAB-MODEL',version='7.20.1'))
        self.tls.peer=('10.77.0.2',8729);self.tls.local=('10.77.0.1',54321);self.tls.san=(('IP Address','10.77.0.2'),)
        self.context=Mock(verify_mode=ssl.CERT_REQUIRED,check_hostname=True,minimum_version=ssl.TLSVersion.TLSv1_2,hostname_checks_common_name=False)
        self.context.wrap_socket.return_value=self.tls
        for patcher in (patch.object(transport.socket,'socket',return_value=self.raw),patch.object(transport,'verified_tls_context',return_value=self.context)):
            patcher.start();self.addCleanup(patcher.stop)
    def test_649_and_7_use_single_connection_two_reads_and_same_strict_tls(self):
        for version in ('6.49.19','6.49.19 (stable)','7.20.1','7.20rc1','7.19 (long-term)'):
            self.tls.data=response(identity='LAB',model='LAB-MODEL',version=version);self.tls.sent=b'';self.raw.reset_mock()
            result=self.client.probe(self.target,self.credentials,self.policy)
            self.assertEqual(result,dict(identity='LAB',model='LAB-MODEL',routeros_version=version))
            self.raw.connect.assert_called_once_with(('10.77.0.2',8729));self.raw.bind.assert_called_once_with(('10.77.0.1',0))
            self.assertEqual(self.tls.sent,sentence('/login','=name=operator-ro','=password=SYNTHETIC_PASSWORD_CANARY')+sentence('/system/identity/print','=.proplist=name')+sentence('/system/resource/print','=.proplist=board-name,version'))
            self.raw.close.assert_called_once();self.assertTrue(self.tls.closed)
    def test_closed_policy_ssrf_wrong_port_and_missing_pin_stop_before_socket(self):
        from dataclasses import replace
        cases=[(self.target,transport.ConnectionPolicy()),(replace(self.target,address='127.0.0.1'),self.policy),(replace(self.target,address='169.254.169.254'),self.policy),(replace(self.target,address='10.78.0.2'),self.policy),(replace(self.target,port=8728),self.policy),(replace(self.target,leaf_sha256=''),self.policy),(self.target,transport.ConnectionPolicy(True,'10.77.0.1',('0.0.0.0/0',)))]
        for target,policy in cases:
            with self.assertRaises(ApiSslStop):self.client.probe(target,self.credentials,policy)
        transport.socket.socket.assert_not_called()
    def test_tls_chain_weak_policy_and_pin_san_source_peer_fail_before_login(self):
        self.context.wrap_socket.side_effect=ssl.SSLCertVerificationError('SECRET_CANARY')
        with self.assertRaisesRegex(ApiSslStop,'^TLS_VERIFICATION_FAILED$'):self.client.probe(self.target,self.credentials,self.policy)
        self.assertEqual(self.tls.sent,b'');self.raw.close.assert_called_once()
        self.context.wrap_socket.side_effect=None
        for attribute,value,code in (('der',b'WRONG','CERTIFICATE_PIN_MISMATCH'),('san',(('DNS','wrong'),),'CERTIFICATE_SAN_MISMATCH'),('local',('10.77.0.9',10),'ENDPOINT_OR_SOURCE_MISMATCH'),('peer',('10.77.0.9',8729),'ENDPOINT_OR_SOURCE_MISMATCH')):
            old=getattr(self.tls,attribute);setattr(self.tls,attribute,value)
            with self.assertRaisesRegex(ApiSslStop,'^'+code+'$'):self.client.probe(self.target,self.credentials,self.policy)
            self.assertEqual(self.tls.sent,b'');setattr(self.tls,attribute,old)
        self.context.verify_mode=ssl.CERT_NONE;transport.socket.socket.reset_mock()
        with self.assertRaisesRegex(ApiSslStop,'TLS_POLICY_REJECTED'):self.client.probe(self.target,self.credentials,self.policy)
        transport.socket.socket.assert_not_called()
    def test_timeout_closes_once_and_never_falls_back_to_plain_api(self):
        self.raw.connect.side_effect=TimeoutError('SECRET_CANARY')
        with self.assertRaisesRegex(ApiSslStop,'^CONNECTION_TIMEOUT$'):self.client.probe(self.target,self.credentials,self.policy)
        self.raw.connect.assert_called_once();self.raw.close.assert_called_once()
    def test_identity_version_mismatch_auth_rejection_and_unsupported_version(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ApiSslStop,'ROUTER_IDENTITY_MISMATCH'):self.client.probe(replace(self.target,expected_identity='OTHER'),self.credentials,self.policy)
        self.assertNotIn(b'/system/resource/print',self.tls.sent)
        self.tls.data=response(identity='LAB',model='LAB-MODEL',version='7.20.1')
        with self.assertRaisesRegex(ApiSslStop,'ROUTEROS_VERSION_MISMATCH'):self.client.probe(replace(self.target,expected_version='6.49.19'),self.credentials,self.policy)
        self.tls.data=response(identity='LAB',model='LAB-MODEL',version='6.42.1')
        with self.assertRaisesRegex(ApiSslStop,'ROUTEROS_VERSION_UNSUPPORTED'):self.client.probe(self.target,self.credentials,self.policy)
        self.tls.data=sentence('!trap','=message=invalid user name or password (6)');self.tls.sent=b''
        with self.assertRaisesRegex(ApiSslStop,'CREDENTIAL_OR_ACCOUNT_POLICY'):self.client.probe(self.target,self.credentials,self.policy)
        self.assertNotIn(b'/system/identity/print',self.tls.sent)
    def test_reflected_password_cannot_enter_metadata_api_or_audit(self):
        self.tls.data=response(identity='SYNTHETIC_PASSWORD_CANARY',model='LAB-MODEL',version='7.20.1')
        with self.assertRaisesRegex(ApiSslStop,'^SENSITIVE_METADATA_REJECTED$'):self.client.probe(self.target,self.credentials,self.policy)
        self.assertTrue(self.tls.closed)
    def test_saved_model_mismatch_stops_before_metadata_is_saved(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ApiSslStop,'^ROUTER_MODEL_MISMATCH$'):
            self.client.probe(replace(self.target,expected_model='OTHER-MODEL'),self.credentials,self.policy)
        self.assertTrue(self.tls.closed)
