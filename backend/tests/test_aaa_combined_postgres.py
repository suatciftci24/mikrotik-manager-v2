"""Combined fixture acceptance; launched ONLY by the fresh-cluster runner."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import insert, select, text, event

from backend.tests.test_aaa_pg_bridge import PostgresBridgeAcceptance, STAMP
from app.repositories import aaa_metadata as db
from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge, BridgeConflict
from app.integrations.aaa_credentials import CredentialBinding, FixtureCredentialResolver, FixtureSubscriberCredentialGate
from app.adapters.aaa_freeradius import FreeRadiusFixtureAdapter
from app.adapters.aaa_routeros import RouterOsFixtureAdapter
from app.modules.adapter_contracts import AaaAdapterTarget, AaaProfileMapping, PasswordVerification
from app.simulation.aaa_integration_preparation import SyntheticAaaAccount, SyntheticAaaCommand
from app.simulation.aaa_local_expire import LocalExpireFixtureWorker
from app.simulation.aaa_provider import FakeFencedProvider


class CombinedPostgresAcceptance(PostgresBridgeAcceptance):
    # Direct unittest invocation cannot adopt the parent's existing cluster ID.
    # Only the fresh provisioning callback supplies its newly observed identity.
    expected_cluster_id = None

    def fixture(self, source, major):
        subscriber, router = 'demo-managed-sub-'+str(uuid4()), 'demo-managed-router-'+str(uuid4())
        raw = self.f.request.plan.snapshot.model_dump(mode='json')
        raw['reference']['account_id'], raw['nas']['router_id'] = subscriber, router
        raw['authority'] = source
        snapshot = type(self.f.request.plan.snapshot).model_validate_json(json.dumps(raw))
        request = self.f.request.model_copy(update={'plan':self.f.request.plan.model_copy(update={'snapshot':snapshot})})
        with self.admin() as c:
            now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
            c.execute(insert(db.owner).values(id=subscriber, tenant_id=self.tenant, source=source,
                                             revision=0, aaa_fence=0, aaa_active_operation=None))
            caps = ['DAILY_OWNER','AAA_ROUTER:'+router]+['AAA_SUBSCRIBER_'+k for k in ('CREATE','EXTEND','PLAN','STATUS','READ')]
            c.execute(text('INSERT INTO v2_aaa.fixture_membership VALUES (:t,:a,:u,true,1,1,CAST(:c AS jsonb),:d)'),
                      dict(t=self.tenant,a=self.actor,u=subscriber,c=json.dumps(caps),d=STAMP))
        binding = CredentialBinding(reference='secretref:v2/aaa-fixture/combined', tenant_id=self.tenant,
            router_id=router, source=source, purpose='SUBSCRIBER_PASSWORD', revision=1)
        gate = FixtureSubscriberCredentialGate(FixtureCredentialResolver([binding]), revision=1,valid_until=now+timedelta(minutes=5))
        target = AaaAdapterTarget(tenant_id=self.tenant,actor_id=self.actor,subscriber_id=subscriber,
            router_id=router,source=source,routeros_major=major,mapping_revision=1,nas_identifier='combined',
            profiles=tuple(AaaProfileMapping(plan=p,profile=p) for p in ('basic','fast')),
            password=PasswordVerification(method='PAP',storage='CLEARTEXT_REFERENCE',credential_reference=binding.reference))
        adapter = RouterOsFixtureAdapter(target) if source=='LOCAL' else FreeRadiusFixtureAdapter(target)
        provider = FakeFencedProvider(request.plan,subscriber_adapter=adapter,credential_gate=gate)
        bridge = PostgresFixtureBridge(self.sessions,self.resolver,provider)
        def command(kind,before,after,revision,**extra):
            return SyntheticAaaCommand(request_id=uuid4(),tenant_id=self.tenant,actor_id=self.actor,
                subscriber_id=subscriber,router_id=router,expected_source=source,expected_revision=revision,
                expected_fence=revision,operation=kind,before=before,after=after,confirmed=True,**extra)
        return request,bridge,adapter,binding,command,now

    def state(self, request):
        with self.admin() as c:
            owner = c.execute(select(db.owner).where(db.owner.c.id==request.plan.snapshot.reference.account_id)).mappings().one()
            audits = c.execute(select(db.audit).where(db.audit.c.subscriber_id==owner['id']).order_by(db.audit.c.revision)).mappings().all()
            return dict(owner),[dict(e) for e in audits]

    def test_combined_lifecycle_and_expire(self):
        from zoneinfo import ZoneInfo
        for source,major in (('LOCAL',6),('LOCAL',7),('RADIUS',7)):
            with self.subTest(source=source,major=major):
                request,bridge,adapter,binding,command,now = self.fixture(source,major)
                today = now.astimezone(ZoneInfo('Europe/Istanbul')).date()
                comment = 'EXPIRE='+ (now-timedelta(minutes=2)).astimezone(ZoneInfo('Europe/Istanbul')).strftime('%Y-%m-%d %H:%M')
                account = SyntheticAaaAccount(username='combined',plan='basic',status='ACTIVE',
                    expires_on=(today-timedelta(days=1)).isoformat(),local_expire_comment=comment if source=='LOCAL' else None)
                def write(cmd): return bridge.subscriber_change(request,self.f.scope,self.principal,cmd)
                create = command('CREATE',None,account,0)
                receipt = write(create)
                self.assertEqual(write(create),receipt)
                self.assertEqual(bridge.subscriber_result(request,self.f.scope,self.principal,create.request_id),receipt)
                first = self.state(request)[1][0]['changes']['_aaa_subscriber']['adapter_projection']
                if source=='LOCAL':
                    self.assertEqual(first['values']['disabled'],'yes')
                    adapter.target = adapter.target.model_copy(update={'routeros_record_id':'*A'})
                else: self.assertEqual(first['authorization']['control']['Auth-Type'],'Reject')
                extended = account.model_copy(update={'expires_on':(today+timedelta(days=30)).isoformat()})
                planned = extended.model_copy(update={'plan':'fast'})
                paused = planned.model_copy(update={'status':'PAUSED'})
                for revision,(kind,before,after,extra) in enumerate((('EXTEND',account,extended,{'days':30}),
                    ('PLAN',extended,planned,{}),('STATUS',planned,paused,{}),('STATUS',paused,planned,{})),1):
                    self.assertEqual(write(command(kind,before,after,revision,**extra)).after,after)
                count = 5
                if source=='LOCAL':
                    args = dict(account=planned,revision=5,fence=5,now=now,deadline=now+timedelta(minutes=1))
                    with self.assertRaises(PermissionError): LocalExpireFixtureWorker(bridge).run_one(request,self.f.scope,self.principal,**args)
                    worker = LocalExpireFixtureWorker(bridge,enabled=True)
                    expired = worker.run_one(request,self.f.scope,self.principal,**args)
                    self.assertEqual(expired.after.status,'PAUSED')
                    self.assertEqual(worker.run_one(request,self.f.scope,self.principal,**args),expired)
                    count += 1
                owner,audits = self.state(request)
                self.assertEqual((owner['revision'],owner['aaa_fence'],len(audits)),(count,count,count))
                for e in audits:
                    canonical = bridge._subscriber_receipt(e)
                    self.assertEqual(bridge.subscriber_result(request,self.f.scope,self.principal,canonical.request_id),canonical)
                    self.assertNotIn(binding.reference,json.dumps(e['changes']))
                if source=='LOCAL':
                    self.assertEqual(audits[-1]['changes']['_aaa_subscriber']['adapter_projection']['values']['disabled'],'yes')

    def test_combined_denials_atomicity_and_races(self):
        request,bridge,adapter,binding,command,now = self.fixture('LOCAL',7)
        account = SyntheticAaaAccount(username='combined',plan='basic',status='ACTIVE')
        def write(cmd): return bridge.subscriber_change(request,self.f.scope,self.principal,cmd)
        create = command('CREATE',None,account,0)
        baseline = self.state(request)
        for change in ({'tenant_id':uuid4()},{'router_id':'demo-managed-router-other'}, {'source':'RADIUS'},
                       {'purpose':'ROUTER_LOGIN'},{'revision':2},{'active':False}):
            bridge.provider.credential_gate.resolver = FixtureCredentialResolver([binding.model_copy(update=change)])
            with self.assertRaises(PermissionError): write(create)
            self.assertEqual(self.state(request),baseline)
        bridge.provider.credential_gate.resolver = FixtureCredentialResolver([binding])
        bridge.provider.credential_gate.valid_until = now-timedelta(seconds=1)
        with self.assertRaises(PermissionError): write(create)
        bridge.provider.credential_gate.valid_until = now+timedelta(minutes=5)
        for role in ('VIEWER','OPERATOR'):
            with self.admin() as c: c.execute(text('UPDATE v2_aaa.fixture_actor_identity SET role=:r WHERE actor_id=:a'),dict(r=role,a=self.actor))
            with self.assertRaises(PermissionError): write(create)
            self.assertEqual(self.state(request),baseline)
        with self.admin() as c: c.execute(text("UPDATE v2_aaa.fixture_actor_identity SET role='ADMIN' WHERE actor_id=:a"),dict(a=self.actor))
        for change in ({'tenant_id':uuid4()},{'router_id':'demo-managed-router-other'},{'actor_id':'foreign'}):
            with self.assertRaises(PermissionError): write(create.model_copy(update=change))
        with patch.object(RouterOsFixtureAdapter,'prepare',side_effect=RuntimeError('SYNTHETIC_PROVIDER_FAILURE')):
            with self.assertRaises(RuntimeError): write(create)
        self.assertEqual(self.state(request),baseline)
        def audit_fault(conn,cursor,statement,parameters,context,many):
            if statement.startswith('INSERT INTO v2_subscriber_workspace.events'): conn.exec_driver_sql('SELECT 1/0')
        event.listen(self.engine,'before_cursor_execute',audit_fault)
        try:
            with self.assertRaises(Exception) as failure: write(create)
            self.assertEqual(getattr(getattr(failure.exception,'orig',None),'sqlstate',None),'22012')
        finally: event.remove(self.engine,'before_cursor_execute',audit_fault)
        self.assertEqual(self.state(request),baseline)
        with ThreadPoolExecutor(max_workers=2) as pool: receipts = list(pool.map(write,[create,create]))
        self.assertEqual(receipts[0],receipts[1])
        with self.assertRaises(BridgeConflict): write(create.model_copy(update={'after':account.model_copy(update={'plan':'fast'})}))
        adapter.target = adapter.target.model_copy(update={'routeros_record_id':'*A'})
        planned = account.model_copy(update={'plan':'fast'})
        for revision,fence in ((0,1),(1,0)):
            stale = command('PLAN',account,planned,revision).model_copy(update={'expected_fence':fence})
            with self.assertRaises(BridgeConflict): write(stale)
        candidates = [command('PLAN',account,planned,1),command('STATUS',account,account.model_copy(update={'status':'PAUSED'}),1)]
        def race(cmd):
            try: return write(cmd)
            except BridgeConflict: return None
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(race,candidates))
        self.assertEqual(sum(r is not None for r in outcomes),1)
        owner,audits = self.state(request)
        self.assertEqual((owner['revision'],owner['aaa_fence'],len(audits)),(2,2,2))
        for e in audits: self.assertEqual(bridge.subscriber_result(request,self.f.scope,self.principal,bridge._subscriber_receipt(e).request_id),bridge._subscriber_receipt(e))
