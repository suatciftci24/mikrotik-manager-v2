from datetime import datetime, timedelta, timezone
from unittest import TestCase
from uuid import uuid4
from app.integrations.aaa_credentials import CredentialBinding, FixtureCredentialResolver
from app.simulation.aaa_local_expire import expire_instant, require_expire_command
from app.simulation.aaa_integration_preparation import SyntheticAaaAccount, SyntheticAaaCommand


class CredentialExpireAcceptance(TestCase):
    def test_reference_scope_and_redaction(self):
        now = datetime.now(timezone.utc)
        b = CredentialBinding(reference='secretref:v2/aaa-fixture/isolated',tenant_id=uuid4(),
            router_id='demo-managed-router-fixture',source='LOCAL',purpose='ROUTER_LOGIN',revision=1)
        resolver = FixtureCredentialResolver([b])
        args = dict(tenant_id=b.tenant_id,router_id=b.router_id,source=b.source,purpose=b.purpose,
                    revision=1,permitted=True,now=now,valid_until=now+timedelta(seconds=30))
        result = resolver.resolve(b.reference,**args)
        self.assertNotIn(b.reference,repr(b)+b.model_dump_json()+result.model_dump_json())
        for changes in ({'tenant_id':uuid4()},{'router_id':'demo-managed-router-other'},
                        {'source':'RADIUS'},{'purpose':'RADIUS_SHARED_SECRET'}, {'revision':2},
                        {'permitted':False},{'valid_until':now}):
            with self.assertRaisesRegex(PermissionError,'^CREDENTIAL_RESOLUTION_DENIED$'):
                resolver.resolve(b.reference,**{**args,**changes})
        with self.assertRaises(PermissionError):
            FixtureCredentialResolver([b,b]).resolve(b.reference,**args)

    def test_expire_boundary_and_provider(self):
        from app.simulation.aaa_provider import FakeFencedProvider, ProviderConflict
        from types import SimpleNamespace
        due = expire_instant('EXPIRE=2026-11-13 18:30')
        self.assertEqual(due.isoformat(),'2026-11-13T15:30:00+00:00')
        for bad in ('EXPIRE=2026-02-30 18:30','EXPIRE=2026-11-13 18:30 extra','2026-11-13','EXPIRE=2026-11-13 25:00'):
            with self.assertRaises(ValueError): expire_instant(bad)
        tenant = uuid4()
        account = SyntheticAaaAccount(username='fixture',plan='fixture',status='ACTIVE',
            local_expire_comment='EXPIRE=2026-11-13 18:30')
        command = SyntheticAaaCommand(request_id=uuid4(),tenant_id=tenant,actor_id='fixture',
            subscriber_id='demo-managed-sub-fixture',router_id='demo-managed-router-fixture',
            expected_source='LOCAL',expected_revision=1,expected_fence=1,operation='STATUS',before=account,
            after=account.model_copy(update={'status':'PAUSED'}),confirmed=True,expire_deadline=due+timedelta(seconds=30))
        plan = SimpleNamespace(steps=(),tenant_id=str(tenant),snapshot=SimpleNamespace(
            reference=SimpleNamespace(store='PERSISTENT_WORKSPACE',account_id=command.subscriber_id)))
        provider = FakeFencedProvider(plan)
        self.assertEqual(provider.project_subscriber(command,account,due).status,'PAUSED')
        for instant in (due-timedelta(microseconds=1),command.expire_deadline):
            with self.assertRaises(ProviderConflict): provider.project_subscriber(command,account,instant)
        with self.assertRaises(ProviderConflict):
            provider.project_subscriber(command,account.model_copy(update={'local_expire_comment':'EXPIRE=2027-01-01 00:00'}),due)
        with self.assertRaises(PermissionError):
            require_expire_command(command.model_copy(update={'expected_source':'RADIUS'}))

    def test_worker_default_closed_and_bridge_handoff(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.simulation.aaa_local_expire import LocalExpireFixtureWorker
        from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge
        # No session/DB is opened: exercise the worker boundary and exact command.
        bridge = object.__new__(PostgresFixtureBridge)
        tenant = uuid4()
        request = SimpleNamespace(actor_id='fixture',plan=SimpleNamespace(tenant_id=str(tenant),
            snapshot=SimpleNamespace(authority='LOCAL',access_type='PPPOE',
                reference=SimpleNamespace(account_id='demo-managed-sub-fixture'),
                nas=SimpleNamespace(router_id='demo-managed-router-fixture'))))
        account = SyntheticAaaAccount(username='fixture',plan='fixture',status='ACTIVE',
            local_expire_comment='EXPIRE=2026-11-13 18:30')
        due = expire_instant(account.local_expire_comment)
        args = dict(account=account,revision=1,fence=1,now=due,deadline=due+timedelta(seconds=30))
        with self.assertRaises(PermissionError):
            LocalExpireFixtureWorker(bridge).run_one(request,None,None,**args)
        worker = LocalExpireFixtureWorker(bridge,enabled=True)
        with patch.object(PostgresFixtureBridge,'subscriber_change',return_value='receipt') as change:
            self.assertEqual(worker.run_one(request,None,None,**args),'receipt')
            first = change.call_args.args[-1]
            worker.run_one(request,None,None,**args)
            self.assertEqual(first,change.call_args.args[-1])
            self.assertEqual(first.before,account)
            self.assertEqual(first.after.status,'PAUSED')
            self.assertIsNone(worker.run_one(request,None,None,**{**args,'now':due-timedelta(seconds=1)}))
            request.plan.snapshot.authority='RADIUS'
            with self.assertRaises(PermissionError): worker.run_one(request,None,None,**args)

    def test_legacy_fingerprint_and_receipt_compatibility(self):
        from app.simulation.aaa_atomic import canonical_hash
        account = SyntheticAaaAccount(username='fixture',plan='fixture',status='ACTIVE')
        command = SyntheticAaaCommand(request_id=uuid4(),tenant_id=uuid4(),actor_id='fixture',
            subscriber_id='demo-managed-sub-fixture',router_id='demo-managed-router-fixture',
            expected_source='LOCAL',expected_revision=0,expected_fence=0,operation='CREATE',before=None,
            after=account,confirmed=True)
        raw = command.model_dump(mode='json')
        self.assertNotIn('expire_deadline',raw)
        self.assertNotIn('local_expire_comment',raw['after'])
        self.assertEqual(command.fingerprint(),canonical_hash(raw))
        self.assertEqual(command,SyntheticAaaCommand.model_validate_json(command.model_dump_json()))
