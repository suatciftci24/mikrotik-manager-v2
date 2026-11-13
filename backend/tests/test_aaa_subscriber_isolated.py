"""Network-free lifecycle acceptance. No claim of PostgreSQL or PAP/CHAP acceptance."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app.adapters.aaa_freeradius import FreeRadiusFixtureAdapter
from app.adapters.aaa_routeros import RouterOsFixtureAdapter
from app.integrations.aaa_credentials import (CredentialBinding, FixtureCredentialResolver,
                                             FixtureSubscriberCredentialGate)
from app.modules.adapter_contracts import AaaAdapterTarget, AaaProfileMapping, PasswordVerification
from app.simulation.aaa_integration_preparation import SyntheticAaaAccount, SyntheticAaaCommand
from app.simulation.aaa_provider import FakeFencedProvider


class IsolatedSubscriberAcceptance(TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'psycopg.connect', 'sqlite3.connect'):
            self.enterContext(patch(name, side_effect=AssertionError('EXTERNAL_IO_FORBIDDEN')))
        self.now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)

    def fixture(self, source, major):
        tenant, subscriber, router = uuid4(), 'demo-managed-sub-isolated', 'demo-managed-router-isolated'
        binding = CredentialBinding(reference='secretref:v2/aaa-fixture/isolated', tenant_id=tenant,
            router_id=router, source=source, purpose='SUBSCRIBER_PASSWORD', revision=1)
        # Generator input must not lose its bindings during validation.
        resolver = FixtureCredentialResolver(b for b in (binding,))
        gate = FixtureSubscriberCredentialGate(resolver, revision=1, valid_until=self.now+timedelta(minutes=1))
        target = AaaAdapterTarget(tenant_id=tenant, actor_id='fixture', subscriber_id=subscriber,
            router_id=router, source=source, routeros_major=major, mapping_revision=1,
            nas_identifier='isolated', profiles=tuple(AaaProfileMapping(plan=p, profile=p) for p in ('basic','fast')),
            password=PasswordVerification(method='PAP', storage='CLEARTEXT_REFERENCE',
                                          credential_reference=binding.reference))
        adapter = RouterOsFixtureAdapter(target) if source=='LOCAL' else FreeRadiusFixtureAdapter(target)
        plan = SimpleNamespace(steps=(), tenant_id=str(tenant), snapshot=SimpleNamespace(
            reference=SimpleNamespace(store='PERSISTENT_WORKSPACE', account_id=subscriber)))
        provider = FakeFencedProvider(plan, subscriber_adapter=adapter, credential_gate=gate)
        def command(operation, before, after, revision, **extra):
            return SyntheticAaaCommand(request_id=uuid4(), tenant_id=tenant, actor_id='fixture',
                subscriber_id=subscriber, router_id=router, expected_source=source,
                expected_revision=revision, expected_fence=revision, operation=operation,
                before=before, after=after, confirmed=True, **extra)
        return provider, adapter, binding, command

    def test_lifecycle_all_provider_versions_and_expired_authorization(self):
        for source, major in (('LOCAL',6), ('LOCAL',7), ('RADIUS',7)):
            with self.subTest(source=source, major=major):
                provider, adapter, binding, command = self.fixture(source, major)
                account = SyntheticAaaAccount(username='isolated', plan='basic', status='ACTIVE', expires_on='2026-11-14')
                current = None
                changes = [('CREATE', account, {}),
                    ('EXTEND', account.model_copy(update={'expires_on':'2026-11-16'}), {'days':2})]
                changes += [('PLAN', changes[-1][1].model_copy(update={'plan':'fast'}), {})]
                changes += [('STATUS', changes[-1][1].model_copy(update={'status':'PAUSED'}), {})]
                changes += [('STATUS', changes[-1][1].model_copy(update={'status':'ACTIVE'}), {})]
                for revision, (operation, after, extra) in enumerate(changes):
                    cmd = command(operation, current, after, revision, **extra)
                    result, projection = provider.project_subscriber(cmd, current, self.now, include_mapping=True)
                    self.assertEqual(result, after)
                    self.assertEqual(projection.fingerprint, cmd.fingerprint())
                    self.assertNotIn(binding.reference, projection.model_dump_json()+repr(projection))
                    if source=='RADIUS':
                        self.assertEqual(projection.authorization.control.get('Auth-Type'),
                                         'Reject' if after.status=='PAUSED' else None)
                    elif operation=='STATUS':
                        self.assertEqual(projection.values['disabled'], 'yes' if after.status=='PAUSED' else 'no')
                    current = result
                    if operation=='CREATE' and source=='LOCAL':
                        adapter.target = adapter.target.model_copy(update={'routeros_record_id':'*A'})
                expired = account.model_copy(update={'expires_on':'2026-11-12'})
                # Pure authorization at expiry, independent of expired gate lifetime.
                projection = adapter.prepare(command('STATUS', expired.model_copy(update={'status':'PAUSED'}), expired, 6), self.now)
                if source=='RADIUS':
                    self.assertEqual(projection.authorization.control['Auth-Type'], 'Reject')
                else:
                    self.assertEqual(projection.values['disabled'], 'yes')

    def test_scope_expiry_and_provider_failure_leave_no_effect(self):
        provider, adapter, binding, command = self.fixture('LOCAL',7)
        account = SyntheticAaaAccount(username='isolated', plan='basic', status='ACTIVE')
        cmd = command('CREATE', None, account, 0)
        baseline = provider.snapshot()
        for binding_change in ({'tenant_id':uuid4()}, {'router_id':'demo-managed-router-other'},
                               {'source':'RADIUS'}, {'purpose':'ROUTER_LOGIN'}, {'revision':2}, {'active':False}):
            provider.credential_gate.resolver = FixtureCredentialResolver([binding.model_copy(update=binding_change)])
            with self.assertRaises(PermissionError): provider.project_subscriber(cmd, None, self.now)
            self.assertEqual(provider.snapshot(), baseline)
        provider.credential_gate.resolver = FixtureCredentialResolver([binding])
        with self.assertRaises(PermissionError):
            provider.project_subscriber(cmd, None, self.now+timedelta(minutes=1))
        with patch.object(RouterOsFixtureAdapter, 'prepare', side_effect=RuntimeError('SYNTHETIC_PROVIDER_FAILURE')):
            with self.assertRaises(RuntimeError): provider.project_subscriber(cmd, None, self.now)
        self.assertEqual(provider.snapshot(), baseline)
        # Recovery is an explicit fresh projection; pure failure has no remote effect.
        self.assertEqual(provider.project_subscriber(cmd, None, self.now), account)

    def test_local_expire_reaches_router_mapping_with_credential_gate(self):
        from app.simulation.aaa_local_expire import LocalExpireFixtureWorker
        from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge
        provider, adapter, binding, command = self.fixture('LOCAL',6)
        adapter.target = adapter.target.model_copy(update={'routeros_record_id':'*A'})
        account = SyntheticAaaAccount(username='isolated', plan='basic', status='ACTIVE',
                                     local_expire_comment='EXPIRE=2026-11-13 15:00')
        target = adapter.target
        request = SimpleNamespace(actor_id=target.actor_id, plan=SimpleNamespace(tenant_id=str(target.tenant_id),
            snapshot=SimpleNamespace(authority='LOCAL', access_type='PPPOE',
                reference=SimpleNamespace(account_id=target.subscriber_id), nas=SimpleNamespace(router_id=target.router_id))))
        # Deliberate bridge seam: exercises worker->command->provider->adapter, not PG.
        bridge = object.__new__(PostgresFixtureBridge)
        def handoff(request, scope, principal, cmd):
            return provider.project_subscriber(cmd, account, self.now, include_mapping=True)
        with patch.object(PostgresFixtureBridge, 'subscriber_change', side_effect=handoff):
            after, mapping = LocalExpireFixtureWorker(bridge, enabled=True).run_one(request,None,None,
                account=account, revision=1, fence=1, now=self.now, deadline=self.now+timedelta(seconds=30))
        self.assertEqual(after.status, 'PAUSED')
        self.assertEqual(mapping.values, {'.id':'*A', 'disabled':'yes'})
