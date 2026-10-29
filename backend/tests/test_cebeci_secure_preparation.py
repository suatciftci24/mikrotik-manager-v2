"""Stage 28 offline TLS setup and disabled account contract; never contacts a device."""
from copy import deepcopy
from pathlib import Path
import re
import ssl
from unittest import TestCase
from unittest.mock import patch,Mock
from fastapi import HTTPException
from app.integrations import cebeci_access as access
from app.integrations.cebeci_account_preparation import PilotAccountContract,prepare
from app.integrations.cebeci_preparation import profile
from app.services.identity import public_user,bootstrap
from app.services.demo_data import ROUTERS,SUBSCRIBERS

class SecurePreparationTests(TestCase):
    def setUp(self):self.user=public_user(bootstrap())
    def plan(self):return access.AccessPlan(reviewed_management_pin='10.250.0.19',reviewed_source_cidr='192.0.2.10/32',public_certificate_sha256='a'*64)
    def public_ca(self):
        # Public OS trust fixture only, passed explicitly. Not a CEBECI certificate or private key.
        bundle=ssl.get_default_verify_paths().cafile
        if not bundle:self.skipTest('Public CA fixture unavailable')
        return re.search(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----',Path(bundle).read_text(),re.S)[0]
    def test_separate_account_is_operator_created_disabled_and_collision_preserves_existing(self):
        contract=PilotAccountContract();self.assertEqual(contract.policies,('read','api'))
        self.assertEqual(contract.initial_account_state,'DISABLED');self.assertEqual(contract.existing_object_action,'STOP_PRESERVE_EXISTING')
        self.assertEqual(contract.provisioning_method,'OPERATOR_SECURE_MANAGEMENT_SESSION')
        for change in ({'initial_account_state':'ENABLED'},{'existing_object_action':'OVERWRITE'},{'provisioning_method':'API'},{'policies':('read','api','write')}):
            with self.assertRaises(ValueError):prepare(self.user,contract=contract.model_copy(update=change))
    def test_credentials_are_not_configuration_fields_or_preparation_inputs(self):
        for field in ('username','password','psk','private_key','secret_reference'):
            with self.assertRaises(ValueError) as failure:prepare(self.user,contract=PilotAccountContract().model_copy(update={field:'SECRET_CANARY'}))
            self.assertNotIn('SECRET_CANARY',str(failure.exception))
    def test_unassigned_default_is_blocked_before_trust_loading(self):
        with patch('ssl.SSLContext',side_effect=AssertionError('No trust loading before reviewed scope')):
            with self.assertRaisesRegex(ValueError,'REVIEWED_TARGET_SOURCE_AND_PUBLIC_PIN_REQUIRED'):access.prepare_offline_tls_context(self.user)
        for key in ('reviewed_management_pin','reviewed_source_cidr','public_certificate_sha256'):
            with self.assertRaises(ValueError):access.prepare_offline_tls_context(self.user,self.plan().model_copy(update={key:None}))
    def test_context_requires_explicit_ca_tls12_chain_and_san_without_keylog_or_sockets(self):
        ca=self.public_ca()
        with patch('socket.socket',side_effect=AssertionError('No sockets')),patch.dict('os.environ',{'SSLKEYLOGFILE':'/tmp/cebeci-do-not-write.keylog'}):
            context=access.prepare_offline_tls_context(self.user,self.plan(),public_ca_pem=ca)
        self.assertEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED);self.assertTrue(context.check_hostname)
        self.assertFalse(context.hostname_checks_common_name);self.assertTrue(context.verify_flags&ssl.VERIFY_X509_STRICT)
        self.assertIsNone(context.keylog_filename);self.assertEqual(len(context.get_ca_certs()),1)
        self.assertTrue(all(c['auth']!='auth-null' for c in context.get_ciphers()))
        self.assertTrue(all(c['aead'] for c in context.get_ciphers()))
    def test_missing_private_malformed_mixed_or_excessive_trust_is_redacted_and_rejected(self):
        for pem in (None,'','/tmp/credential.pem','-----BEGIN PRIVATE KEY-----\nSECRET_CANARY\n-----END PRIVATE KEY-----','-----BEGIN CERTIFICATE-----\nSECRETCANARY\n-----END CERTIFICATE-----','x'*262145):
            with self.assertRaises(ValueError) as failure:access.prepare_offline_tls_context(self.user,self.plan(),public_ca_pem=pem)
            self.assertNotIn('SECRET',str(failure.exception))
        ca=self.public_ca()
        for pem in (ca+'\nPRIVATE_KEY_CANARY',ca+'\n'+ca,(ca+'\n')*17):
            with self.assertRaises(ValueError):access.prepare_offline_tls_context(self.user,self.plan(),public_ca_pem=pem)
    def test_non_ca_trust_input_is_not_accepted_as_ca(self):
        fake=Mock();fake.get_ca_certs.return_value=[]
        fake.verify_flags=0;fake.options=0
        with patch('ssl.SSLContext',return_value=fake):
            with self.assertRaisesRegex(ValueError,'PILOT_PUBLIC_CA_REJECTED'):access.prepare_offline_tls_context(self.user,self.plan(),public_ca_pem=self.public_ca())
    def test_bypassed_network_or_plain_api_plan_cannot_prepare_a_context(self):
        for update in ({'network_enabled':True},{'verify_tls':False},{'verify_hostname':False},{'transport':'API','port':8728},{'candidate_id':'OTHER_ROUTER'},{'password':'SECRET_CANARY'}):
            with self.assertRaisesRegex(ValueError,'PILOT_CONTRACT_REJECTED') as failure:access.prepare_offline_tls_context(self.user,self.plan().model_copy(update=update))
            self.assertNotIn('SECRET',str(failure.exception))
    def test_preparation_approval_is_not_execution_and_dispatch_never_touches_adapter(self):
        class NeverTouch:
            def __getattribute__(self,key):raise AssertionError('Adapter accessed')
        with self.assertRaises(HTTPException) as failure:access.dispatch_pilot_read(self.user,self.plan(),access.OfflineEvidence(),access.ReadIntent(menu='/system/identity',properties=('name',)),NeverTouch())
        self.assertEqual(failure.exception.status_code,403)
        result=prepare(self.user);self.assertFalse(result['account_creation_allowed']);self.assertFalse(result['connection_allowed']);self.assertEqual(result['decision'],'NO_GO')
    def test_admin_only_existing_profile_preserves_data_no_new_endpoint(self):
        from app.api.v1.system import router
        before=deepcopy((ROUTERS,SUBSCRIBERS))
        with patch('socket.socket',side_effect=AssertionError('No sockets')):self.assertEqual(profile(self.user),profile(self.user))
        self.assertEqual((ROUTERS,SUBSCRIBERS),before)
        self.assertEqual([(r.path,r.methods) for r in router.routes if 'cebeci' in r.path],[('/system/cebeci-pilot',{'GET'})])
        for change in ({'role_code':'VIEWER'},{'can_manage_users':False}):
            with self.assertRaises(HTTPException):access.prepare_offline_tls_context({**self.user,**change},self.plan())
