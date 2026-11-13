from datetime import timedelta
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4
from pydantic import SecretStr
from backend.tests import test_aaa_subscriber_isolated as lifecycle
from app.integrations.aaa_secret_provider import (SecretVerificationScope, SyntheticPasswordEntry,
    SyntheticSecretProvider, RadiusFixturePasswordVerifier)
from app.integrations.aaa_credentials import FixtureCredentialResolver
from app.simulation.aaa_integration_preparation import SyntheticAaaAccount


class SecretProviderAcceptance(TestCase):
    def setUp(self):
        helper = lifecycle.IsolatedSubscriberAcceptance()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.provider,self.adapter,self.binding,command = helper.fixture('RADIUS',7)
        self.now = helper.now
        self.command = command('CREATE',None,SyntheticAaaAccount(username='synthetic',plan='basic',status='ACTIVE'),0)
        self.scope = SecretVerificationScope(tenant_id=self.binding.tenant_id,actor_id='fixture',
            subscriber_id=self.command.subscriber_id,router_id=self.binding.router_id,source='RADIUS',
            purpose='SUBSCRIBER_PASSWORD',revision=1)
        import secrets
        self.value = secrets.token_urlsafe(32)
        self.entry = SyntheticPasswordEntry(reference=self.binding.reference,scope=self.scope,password=SecretStr(self.value))
        self.store = SyntheticSecretProvider([self.entry])
        self.authorize = Mock(return_value=True)
        self.clock = Mock(return_value=self.now)
        self.verifier = RadiusFixturePasswordVerifier(self.store,self.provider.credential_gate,self.authorize,self.clock)

    def verify(self,value=None):
        return self.verifier.verify(self.adapter,self.command,SecretStr(self.value if value is None else value))

    def test_pap_success_wrong_missing_and_no_secret_output(self):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            self.assertTrue(self.verify())
            self.assertFalse(self.verify('wrong'))
            self.assertFalse(self.verifier.verify(self.adapter,self.command,None))
            self.verifier.provider = SyntheticSecretProvider([])
            self.assertFalse(self.verify())
        public = output.getvalue()+repr(self.entry)+self.entry.model_dump_json()+repr(self.store)
        projection = self.adapter.prepare(self.command,self.now)
        public += projection.model_dump_json()+repr(projection)
        self.assertNotIn(self.value,public)
        self.assertNotIn(self.binding.reference,public)

    def test_scope_rotation_revocation_and_denied_before_provider(self):
        baseline = self.provider.snapshot()
        for changes in ({'tenant_id':uuid4()},{'router_id':'demo-managed-router-other'},
                        {'subscriber_id':'demo-managed-sub-other'},{'actor_id':'other'},
                        {'purpose':'ROUTER_LOGIN'},{'revision':2},{'source':'LOCAL'}):
            entry = self.entry.model_copy(update={'scope':self.scope.model_copy(update=changes)})
            self.verifier.provider = SyntheticSecretProvider([entry])
            self.assertFalse(self.verify())
        self.verifier.provider = SyntheticSecretProvider([self.entry.model_copy(update={'active':False})])
        self.assertFalse(self.verify())
        self.verifier.provider = SyntheticSecretProvider([self.entry,self.entry])
        self.assertFalse(self.verify())
        self.verifier.provider = Mock()
        self.authorize.return_value = False
        self.assertFalse(self.verify())
        self.verifier.provider.verify_password.assert_not_called()
        self.authorize.return_value = True
        self.provider.credential_gate.resolver = FixtureCredentialResolver([])
        self.assertFalse(self.verify())
        self.verifier.provider.verify_password.assert_not_called()
        self.assertEqual(self.provider.snapshot(),baseline)

    def test_provider_swap_errors_revocation_and_late_response_fail_closed(self):
        for fault in (TimeoutError(self.value), ConnectionError(self.value), RuntimeError(self.value)):
            self.verifier.provider = Mock(verify_password=Mock(side_effect=fault))
            self.assertFalse(self.verify())
            self.verifier.provider.verify_password.assert_called_once()
        self.verifier.provider = self.store
        self.authorize.side_effect = [True,False]
        self.assertFalse(self.verify())
        self.authorize.side_effect = None
        self.clock.side_effect = [self.now,self.provider.credential_gate.valid_until]
        self.assertFalse(self.verify())
        self.clock.side_effect = None
        # A provider may not smuggle a truthy result in place of explicit True.
        self.verifier.provider = Mock(verify_password=Mock(return_value=1))
        self.assertFalse(self.verify())

    def test_expired_paused_and_unsupported_methods_reject(self):
        for changes in ({'status':'PAUSED'},{'expires_on':'2026-11-12'}):
            self.command = self.command.model_copy(update={'after':self.command.after.model_copy(update=changes)})
            self.assertFalse(self.verify())
        self.command = self.command.model_copy(update={'after':self.command.after.model_copy(update={'status':'ACTIVE','expires_on':None})})
        self.adapter.target = self.adapter.target.model_copy(update={
            'password':self.adapter.target.password.model_copy(update={'method':'CHAP'})})
        self.assertFalse(self.verify())


class TransportFailureAcceptance(TestCase):
    def test_transport_failures_freeze_retry_and_reconcile_without_owner_commit(self):
        from backend.tests.test_aaa_provider import ProviderFencingTests
        from app.simulation.aaa_provider import ProviderConflict, reconcile_unknown
        from app.simulation.aaa_atomic import AtomicConflict
        for fault in ('CONNECTION','TIMEOUT_BEFORE','TIMEOUT_AFTER','PARTIAL'):
            with self.subTest(fault=fault):
                f = ProviderFencingTests()
                f.setUp()
                try:
                    lease,command = f.delivery()
                    owner = next(iter(f.unit.snapshot()['owners'].values()))
                    with self.assertRaisesRegex(ProviderConflict,'^PROVIDER_TRANSPORT_UNKNOWN_RECONCILIATION_REQUIRED$'):
                        f.provider.execute_transport_fixture(f.unit,f.request,f.scope,f.worker,lease,command,
                                                             failure=fault,permission=True)
                    before = f.unit.snapshot(),f.provider.snapshot()
                    with self.assertRaises(AtomicConflict):
                        f.provider.execute_transport_fixture(f.unit,f.request,f.scope,f.worker,lease,command,permission=True)
                    self.assertEqual(before,(f.unit.snapshot(),f.provider.snapshot()))
                    from app.simulation.aaa_worker import Claim
                    from uuid import UUID
                    recovery = f.unit.claim(f.request,f.scope,f.worker,
                        Claim(attempt_id=UUID(int=99),purpose='RECONCILE'),permission=True)
                    frozen = f.unit.snapshot(),f.provider.snapshot()
                    result = reconcile_unknown(f.unit,f.provider,f.request,f.scope,f.worker,recovery,permission=True)
                    self.assertEqual(result.status,'PROVIDER_APPLIED_CONFIRMED' if fault=='TIMEOUT_AFTER'
                                     else 'READ_ONLY_RECONCILIATION_REQUIRED')
                    self.assertFalse(result.automatic_resume)
                    self.assertEqual(frozen,(f.unit.snapshot(),f.provider.snapshot()))
                    self.assertEqual(next(iter(f.unit.snapshot()['owners'].values())),owner)
                finally: f.doCleanups()
