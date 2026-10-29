"""Stage 31 reported public pin and closed configuration. No real certificate or device IO."""
import os
import ssl
from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from app.adapters import cebeci_api_ssl as api
from app.integrations.cebeci_access import AccessPlan,ReadIntent,prepare_offline_tls_context
from tests import test_cebeci_api_ssl as fixtures

EXPECTED='896addde343bf45b429aa354605ee1930d91c30c024c71fe182b94243937acb6'
class PilotPinTests(TestCase):
    def setUp(self):
        self.fixture=fixtures.ApiSslTests();self.fixture.setUp();self.user=self.fixture.user
        self.addCleanup(self.fixture.doCleanups)
    def test_reported_public_pin_is_default_for_the_single_disabled_runtime_profile(self):
        with patch.dict(os.environ,{},clear=True):cfg=api.configuration_from_environment()
        self.assertEqual(cfg.public_leaf_sha256,EXPECTED);self.assertEqual(api.REVIEWED_LEAF_SHA256,EXPECTED)
        self.assertEqual((cfg.candidate_id,cfg.host,cfg.source_ip,cfg.port),('CEBECI_TOWERS','10.250.0.19','10.250.0.1',8729))
        self.assertFalse(cfg.enabled);self.assertEqual((cfg.connect_timeout,cfg.io_timeout,cfg.total_timeout),(2,2,10))
    def test_unreviewed_rotated_empty_or_malformed_environment_pin_is_rejected(self):
        for pin in ('','0'*64,EXPECTED.upper(),EXPECTED+' ','SECRET_CANARY'):
            with patch.dict(os.environ,{'V2_CEBECI_API_SSL_LEAF_SHA256':pin},clear=True),self.assertRaisesRegex(api.ApiSslStop,'^CONFIGURATION_REJECTED$') as error:
                api.configuration_from_environment()
            self.assertNotIn(pin,str(error.exception)) if pin else None
    def test_pin_does_not_replace_ca_or_grant_execution(self):
        with patch.dict(os.environ,{'V2_CEBECI_API_SSL_ENABLED':'true'},clear=True),self.assertRaises(api.ApiSslStop):api.configuration_from_environment()
        with patch.dict(os.environ,{'V2_CEBECI_API_SSL_ENABLED':'true','V2_CEBECI_API_SSL_CA_PEM':'SYNTHETIC_PUBLIC_CA_NOT_REAL','V2_CEBECI_API_SSL_LEAF_SHA256':EXPECTED},clear=True):
            cfg=api.configuration_from_environment()
        with patch.object(api.socket,'socket',side_effect=AssertionError('No socket')):
            client=api.CebeciApiSslAdapter(self.user,cfg)
            with self.assertRaises(HTTPException) as failure:client.read_metadata(self.fixture.intent)
            self.assertFalse(api.adapter_status(self.user)['execution_enabled'])
        self.assertEqual(failure.exception.status_code,403)
        plan=AccessPlan(reviewed_management_pin=cfg.host,reviewed_source_cidr=cfg.source_ip+'/32',public_certificate_sha256=EXPECTED)
        with self.assertRaises(ValueError):prepare_offline_tls_context(self.user,plan)
        with self.assertRaises(ValueError):prepare_offline_tls_context(self.user,plan,public_ca_pem='NOT_A_CA')
    def test_mocked_chain_san_or_pin_failure_happens_before_auth(self):
        for scenario in ('chain','san','pin'):
            raw,tls,context,factory,builder=self.fixture.mocked()
            if scenario=='chain':context.wrap_socket.side_effect=ssl.SSLCertVerificationError('SYNTHETIC_SECRET_CANARY')
            elif scenario=='san':tls.san=(('IP Address','10.250.0.20'),)
            else:tls.der=b'DIFFERENT_SYNTHETIC_LEAF'
            with self.assertRaises(api.ApiSslStop) as error:api.CebeciApiSslAdapter(self.user,self.fixture.cfg()).read_metadata(self.fixture.intent)
            self.assertEqual(tls.sent,b'');self.assertNotIn('SECRET',str(error.exception));raw.close.assert_called_once()
    def test_write_scope_and_timeout_still_stop_without_fallback(self):
        raw,tls,context,factory,builder=self.fixture.mocked()
        for update in ({'operation':'set'},{'menu':'/system/scheduler'},{'menu':'/ip/firewall'},{'properties':('password',)}):
            with self.assertRaisesRegex(api.ApiSslStop,'COMMAND_REJECTED'):api.CebeciApiSslAdapter(self.user,self.fixture.cfg()).read_metadata(self.fixture.intent.model_copy(update=update))
        factory.assert_not_called()
        tls.recv=lambda _n:(_ for _ in ()).throw(TimeoutError('SYNTHETIC_SECRET_CANARY'))
        client=api.CebeciApiSslAdapter(self.user,self.fixture.cfg())
        with self.assertRaisesRegex(api.ApiSslStop,'CONNECTION_TIMEOUT'):client.read_metadata(self.fixture.intent)
        with self.assertRaisesRegex(api.ApiSslStop,'ADAPTER_STOPPED'):client.read_metadata(self.fixture.intent)
        factory.assert_called_once();self.assertTrue(tls.closed)
    def test_other_router_source_or_plain_port_cannot_be_selected(self):
        for key,value in [('V2_CEBECI_API_SSL_HOST','10.250.0.20'),('V2_CEBECI_API_SSL_SOURCE_IP','0.0.0.0'),('V2_CEBECI_API_SSL_PORT','8728')]:
            with patch.dict(os.environ,{key:value},clear=True),self.assertRaises(api.ApiSslStop):api.configuration_from_environment()
