"""Opt-in real PG bridge acceptance on the already verified Home WSL cluster.

No start/stop/provision of clusters. Only the existing AAA test schemas change.
Synthetic predecessor builders use the real domain services, not patched success.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import time
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from backend.tests.run_v26_http_acceptance_wsl import _isolated_runtime
from backend.tests.run_aaa_postgres_wsl import home_guard
from backend.tests.v26_disposable_cluster import DisposableClusterGuard
from backend.tests import test_aaa_next_step_preparation as builders
from app.integrations.aaa_contracts import PreviewScope, snapshot_fingerprint
from app.repositories.aaa_membership import SessionMembershipResolver, ServerPrincipal
from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge, BridgeConflict
from app.repositories.aaa_owner_contract import OwnerContractConflict
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_prepared_authorization import PreparedExecutionService
from app.simulation.aaa_execution import ExecutionIntent
from app.simulation.aaa_executor import FixtureExecutor, AttemptIntent, FixtureCrash
from app.simulation.aaa_executor_decision import ExecutorReconciliationService, ExecutorDecisionIntent

ROOT = Path('/tmp/mikrotik-v26-acceptance')
STAMP = 'AAA_HOME_WSL_BRIDGE_V1'
CAPS = ['AAA_METADATA', 'AAA_SEED', 'AAA_PREPARE', 'AAA_EXECUTE', 'AAA_DECISION', 'AAA_READ', 'DAILY_OWNER']


@skipUnless(os.environ.get('V2_AAA_EXISTING_PG_TESTS') == '1', 'Explicit existing isolated AAA PG opt-in required')
class PostgresBridgeAcceptance(TestCase):
    actor_prefix = 'aaa-pg-actor-'
    existing_schema_only = False
    fixture_root = ROOT
    expected_cluster_id = '7707358750625226262'
    environment_guard = staticmethod(home_guard)
    @classmethod
    def verify(cls, connection):
        DisposableClusterGuard(cls.fixture_root)(cls.fixture_root / 'postgres-test')
        manifest = json.loads((cls.fixture_root / 'fixture-manifest.json').read_text())
        for p, key in ((cls.fixture_root, 'root_identity'), (cls.fixture_root / 'postgres-test', 'data_identity')):
            s = p.lstat()
            if (s.st_dev, s.st_ino, s.st_uid) != tuple(manifest[key]):
                raise RuntimeError('RECORDED_OWNERSHIP_REQUIRED')
        identity = connection.execute(text("SELECT current_database(),host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),current_setting('listen_addresses'),"
            "(SELECT system_identifier::text FROM pg_control_system())")).one()
        if tuple(identity) != ('mikrotik_v26_acceptance','127.0.0.1',55433,str(cls.fixture_root / 'postgres-test'),
                               '127.0.0.1',cls.expected_cluster_id):
            raise RuntimeError('EXACT_EXISTING_AAA_IDENTITY_REQUIRED')

    @classmethod
    def setUpClass(cls):
        cls.environment_guard()
        cls.env = _isolated_runtime()
        cls.env.__enter__()
        cls.addClassCleanup(lambda: cls.env.__exit__(None, None, None))
        url = URL.create('postgresql+psycopg', username='v26_acceptance', password=(cls.fixture_root / 'test-password').read_text(),
                         host='127.0.0.1', port=55433, database='mikrotik_v26_acceptance')
        cls.engine = create_engine(url, hide_parameters=True,
            connect_args={'connect_timeout':5,'options':'-c statement_timeout=10000 -c lock_timeout=3000'})
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.begin() as c:
            cls.verify(c)  # BEFORE any DDL/DML.
            if cls.existing_schema_only:
                c.exec_driver_sql('SELECT actor_id FROM v2_aaa.fixture_actor_identity LIMIT 0')
                c.exec_driver_sql('SELECT capabilities,policy_revision FROM v2_aaa.fixture_membership LIMIT 0')
                return
            c.exec_driver_sql('CREATE TABLE IF NOT EXISTS v2_aaa.fixture_actor_identity '
                '(actor_id text PRIMARY KEY,active boolean NOT NULL,origin text NOT NULL,role text NOT NULL,'
                'revision bigint NOT NULL CHECK(revision>0),deployment text NOT NULL)')
            for column, kind in (('policy_revision','bigint'),('capabilities','jsonb'),('deployment','text')):
                c.exec_driver_sql('ALTER TABLE v2_aaa.fixture_membership ADD COLUMN IF NOT EXISTS ' + column + ' ' + kind)
            c.exec_driver_sql('CREATE OR REPLACE FUNCTION v2_aaa.bridge_actor_lock(text) '
                'RETURNS SETOF v2_aaa.fixture_actor_identity LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog '
                'AS $$ SELECT * FROM v2_aaa.fixture_actor_identity WHERE actor_id=$1 FOR UPDATE $$')
            c.exec_driver_sql('CREATE OR REPLACE FUNCTION v2_aaa.bridge_member_lock(uuid,text,text) '
                'RETURNS SETOF v2_aaa.fixture_membership LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog '
                'AS $$ SELECT * FROM v2_aaa.fixture_membership WHERE tenant_id=$1 AND actor_id=$2 AND subscriber_id=$3 FOR UPDATE $$')
            for function in ('bridge_actor_lock(text)', 'bridge_member_lock(uuid,text,text)'):
                c.exec_driver_sql('REVOKE ALL ON FUNCTION v2_aaa.' + function + ' FROM PUBLIC')
                c.exec_driver_sql('GRANT EXECUTE ON FUNCTION v2_aaa.' + function + ' TO v26_aaa_fixture')

    @contextmanager
    def sessions(self):
        with Session(self.engine) as session:
            def restricted(session, transaction, connection):
                self.verify(connection)
                connection.exec_driver_sql('SET LOCAL ROLE v26_aaa_fixture')
            event.listen(session, 'after_begin', restricted)
            yield session

    @contextmanager
    def admin(self):
        with self.engine.begin() as connection:
            self.verify(connection)
            yield connection

    def setUp(self):
        self.tenant = uuid4()
        self.actor = self.actor_prefix + str(self.tenant)
        self.subscriber = 'demo-managed-sub-' + str(self.tenant)
        with self.admin() as c:
            now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        from backend.tests import test_aaa_next_step_executor as root
        make = root.synthetic_request
        def synthetic():
            base = make()
            data = base.snapshot.model_dump(mode='json')
            data['reference'].update(tenant_id=str(self.tenant), store='PERSISTENT_WORKSPACE', account_id=self.subscriber)
            data['nas']['router_id'] = 'demo-managed-router-' + str(self.tenant)
            snapshot = type(base.snapshot).model_validate_json(json.dumps(data))
            scope = PreviewScope(actor_id=self.actor, store='PERSISTENT_WORKSPACE',tenant_id=str(self.tenant),workspace_admin=True)
            proof = base.proof.model_copy(update={'actor_id':self.actor,'store':'PERSISTENT_WORKSPACE',
                'account_id':self.subscriber,'snapshot_sha256':snapshot_fingerprint(snapshot)})
            return type(base).model_validate_json(base.model_copy(update={'snapshot':snapshot,'scope':scope,'proof':proof,
                'clock':now-timedelta(seconds=62)}).model_dump_json())
        helper = builders.NextStepPreparationTests(methodName='runTest')
        try:
            with patch.object(root, 'synthetic_request', side_effect=synthetic):
                self.f = helper.setup_fixture()
                self.prepared = helper.prepare(helper.issue())
        finally:
            helper.doCleanups()
        self.principal = ServerPrincipal(actor_id=self.actor, deployment=STAMP)
        with self.admin() as c:
            c.execute(text('INSERT INTO v2_aaa.fixture_actor_identity VALUES (:actor,true,\'LOCAL\',\'ADMIN\',1,:stamp)'),
                      {'actor':self.actor,'stamp':STAMP})
            c.execute(text('INSERT INTO v2_aaa.fixture_membership '
                '(tenant_id,actor_id,subscriber_id,active,revision,policy_revision,capabilities,deployment) '
                'VALUES (:tenant,:actor,:subscriber,true,1,1,CAST(:caps AS jsonb),:stamp)'),
                {'tenant':self.tenant,'actor':self.actor,'subscriber':self.subscriber,'caps':json.dumps(CAPS),'stamp':STAMP})
        def target(session):
            return session.execute(text('SELECT current_user,current_database(),inet_server_port()')).one() == (
                'v26_aaa_fixture','mikrotik_v26_acceptance',55433)
        self.resolver = SessionMembershipResolver(deployment=STAMP, target_guard=target,
            actor_reader=lambda s,a:s.execute(text('SELECT * FROM v2_aaa.bridge_actor_lock(:a)'),{'a':a}).mappings().one_or_none(),
            membership_reader=lambda s,o:s.execute(text('SELECT * FROM v2_aaa.bridge_member_lock(:t,:a,:u)'),
                {'t':o.tenant_id,'a':o.actor_id,'u':o.subscriber_id}).mappings().one_or_none())
        self.bridge = PostgresFixtureBridge(self.sessions,self.resolver,self.f.provider)
        self.bridge.seed_fixture(self.f.request,self.f.scope,self.principal,self.f.unit)

    def test_adapter_mappings_scoped_secret_free_and_durable(self):
        from sqlalchemy import insert, select, func
        from pydantic import ValidationError
        from app.repositories import aaa_metadata as db
        from app.simulation.aaa_provider import FakeFencedProvider
        from app.simulation.aaa_integration_preparation import SyntheticAaaAccount, SyntheticAaaCommand
        from app.modules.adapter_contracts import AaaAdapterTarget, AaaProfileMapping, PasswordVerification
        from app.adapters.aaa_freeradius import FreeRadiusFixtureAdapter
        from app.adapters.aaa_routeros import RouterOsFixtureAdapter
        from app.integrations.aaa_identity_writer_boundary import AaaBoundaryDisabled
        reference = 'secretref:v2/aaa-fixture/opaque-test-reference'
        password = PasswordVerification(method='CHAP',storage='CLEARTEXT_REFERENCE',credential_reference=reference)
        with self.assertRaises(ValidationError):
            PasswordVerification(method='CHAP',storage='CRYPT_REFERENCE',credential_reference=reference)
        with self.admin() as c: now = c.execute(select(func.clock_timestamp())).scalar_one()
        from zoneinfo import ZoneInfo
        today = now.astimezone(ZoneInfo('Europe/Istanbul')).date()
        for source, major in (('LOCAL',6),('LOCAL',7),('RADIUS',7)):
            subscriber, router = 'demo-managed-sub-'+str(uuid4()), 'demo-managed-router-'+str(uuid4())
            snapshot_data = self.f.request.plan.snapshot.model_dump(mode='json')
            snapshot_data['reference']['account_id'] = subscriber
            snapshot_data['nas']['router_id'] = router
            snapshot = type(self.f.request.plan.snapshot).model_validate_json(json.dumps(snapshot_data))
            plan = self.f.request.plan.model_copy(update={'snapshot':snapshot})
            request = self.f.request.model_copy(update={'plan':plan,'request_id':uuid4()})
            target = AaaAdapterTarget(tenant_id=self.tenant,actor_id=self.actor,subscriber_id=subscriber,
                router_id=router,source=source,routeros_major=major,mapping_revision=1,nas_identifier='fixture-nas',
                profiles=(AaaProfileMapping(plan='Fixture 100',profile='pppoe-100',rate_limit='10M/100M'),
                          AaaProfileMapping(plan='Fixture 500',profile='pppoe-500',rate_limit='50M/500M')),password=password)
            adapter = RouterOsFixtureAdapter(target) if source=='LOCAL' else FreeRadiusFixtureAdapter(target)
            provider = FakeFencedProvider(plan,subscriber_adapter=adapter)
            bridge = PostgresFixtureBridge(self.sessions,self.resolver,provider)
            caps = ['DAILY_OWNER','AAA_ROUTER:'+router] + ['AAA_SUBSCRIBER_'+k for k in ('CREATE','EXTEND','PLAN','STATUS','READ')]
            with self.admin() as c:
                c.execute(insert(db.owner).values(id=subscriber,tenant_id=self.tenant,source=source,revision=0,aaa_fence=0,aaa_active_operation=None))
                c.execute(text('INSERT INTO v2_aaa.fixture_membership '
                    '(tenant_id,actor_id,subscriber_id,active,revision,policy_revision,capabilities,deployment) '
                    'VALUES (:t,:a,:u,true,1,1,CAST(:c AS jsonb),:d)'),
                    {'t':self.tenant,'a':self.actor,'u':subscriber,'c':json.dumps(caps),'d':STAMP})
            account = SyntheticAaaAccount(username='aaa.adapter.fixture',plan='Fixture 100',status='ACTIVE',
                expires_on=(today+timedelta(days=5)).isoformat())
            def command(operation,before,after,revision,**kwargs):
                return SyntheticAaaCommand(request_id=uuid4(),tenant_id=self.tenant,actor_id=self.actor,
                    subscriber_id=subscriber,router_id=router,expected_source=source,expected_revision=revision,
                    expected_fence=revision,operation=operation,before=before,after=after,confirmed=True,**kwargs)
            create = command('CREATE',None,account,0)
            projection = adapter.prepare(create,now)
            public = projection.model_dump_json()
            for value in (reference,'credential_reference','Cleartext-Password :=','password='):
                self.assertNotIn(value,public)
            self.assertNotIn(reference,repr(target));self.assertNotIn(reference,repr(projection))
            self.assertEqual(projection.expires_at_utc.hour,21)
            self.assertEqual(projection.expires_at_utc.utcoffset(),timedelta(0))
            if source=='LOCAL':
                self.assertEqual(projection.api_path,'/ppp/secret/add')
                self.assertEqual(projection.values,{'name':account.username,'service':'pppoe','profile':'pppoe-100','disabled':'no'})
                self.assertNotIn('password',projection.values)
                self.assertEqual(projection.expiration_enforcement,'EXTERNAL_WORKER_REQUIRED')
            else:
                self.assertEqual(projection.authentication.password_attribute,'Cleartext-Password')
                self.assertEqual(projection.authentication.action,'SET_FROM_REFERENCE')
                self.assertEqual(projection.authorization.control['Expiration'],int(projection.expires_at_utc.timestamp()))
                self.assertEqual(projection.authorization.reply['Mikrotik-Group'],'pppoe-100')
                self.assertEqual(projection.authorization.reply['Mikrotik-Rate-Limit'],'10M/100M')
                self.assertNotIn('Auth-Type',projection.authorization.control)
            with self.assertRaises(PermissionError): adapter.prepare(create.model_copy(update={'tenant_id':uuid4()}),now)
            malformed = type(adapter)(target.model_copy(update={'routeros_major':8}))
            with self.assertRaises(ValidationError): malformed.prepare(create,now)
            malformed_profile = target.profiles[0].model_copy(update={'profile':'bad\nprofile'})
            malformed = type(adapter)(target.model_copy(update={'profiles':(malformed_profile,)}))
            with self.assertRaises(ValidationError): malformed.prepare(create,now)
            foreign = FreeRadiusFixtureAdapter(target) if source=='LOCAL' else RouterOsFixtureAdapter(target)
            with self.assertRaises(PermissionError): foreign.prepare(create,now)
            with self.assertRaises(AaaBoundaryDisabled): adapter.apply_subscriber(create).send(None)
            self.assertEqual(bridge.subscriber_change(request,self.f.scope,self.principal,create).after,account)
            if source=='LOCAL': adapter.target = target.model_copy(update={'routeros_record_id':'*AB'})
            changed = account.model_copy(update={'plan':'Fixture 500'})
            package = command('PLAN',account,changed,1)
            mapped = adapter.prepare(package,now)
            if source=='LOCAL': self.assertEqual(mapped.values,{'.id':'*AB','profile':'pppoe-500'})
            else: self.assertEqual(mapped.authentication.action,'PRESERVE')
            self.assertEqual(bridge.subscriber_change(request,self.f.scope,self.principal,package).after,changed)
            extended = changed.model_copy(update={'expires_on':(today+timedelta(days=35)).isoformat()})
            renewal = command('EXTEND',changed,extended,2,days=30)
            mapped = adapter.prepare(renewal,now)
            if source=='LOCAL':
                self.assertEqual(mapped.action,'METADATA_ONLY');self.assertIsNone(mapped.api_path);self.assertEqual(mapped.values,{})
            else: self.assertGreater(mapped.authorization.reply['Session-Timeout'],projection.authorization.reply['Session-Timeout'])
            self.assertEqual(bridge.subscriber_change(request,self.f.scope,self.principal,renewal).after,extended)
            paused = extended.model_copy(update={'status':'PAUSED'})
            status = command('STATUS',extended,paused,3)
            mapped = adapter.prepare(status,now)
            if source=='LOCAL': self.assertEqual(mapped.values['disabled'],'yes')
            else: self.assertEqual(mapped.authorization.control['Auth-Type'],'Reject')
            self.assertEqual(bridge.subscriber_change(request,self.f.scope,self.principal,status).after,paused)
            self.assertEqual(bridge.subscriber_change(request,self.f.scope,self.principal,create).revision,1)
            with self.admin() as c:
                audits = c.execute(select(db.audit).where(db.audit.c.subscriber_id==subscriber)).mappings().all()
            self.assertEqual(len(audits),4)
            self.assertTrue(all(e['changes']['_aaa_subscriber']['adapter_projection']['mapping_revision']==1 for e in audits))
            self.assertTrue(all(bridge._subscriber_receipt(e).actor_id==self.actor for e in audits))
            self.assertNotIn(reference,json.dumps([dict(e) for e in audits],default=str))
            self.assertEqual(provider.snapshot()['attempts'],{})

    def test_synthetic_subscriber_writes_atomic_authorized_and_idempotent(self):
        from dataclasses import replace
        from sqlalchemy import insert, select
        from app.repositories import aaa_metadata as db
        from app.simulation.aaa_provider import FakeFencedProvider
        from app.simulation.aaa_integration_preparation import SyntheticAaaAccount, SyntheticAaaCommand
        from app.services.aaa_panel_adapter import (PanelAaaAdapter, IsolatedPanelSelection,
            IsolatedPanelDependencies, PanelFixtureAccess, PanelOwnerBinding)
        from app.integrations.aaa_identity_writer_boundary import AaaIdentityWriterBoundary, AaaBoundaryDisabled
        actor = 'aaa-panel-fixture-' + str(uuid4())
        user = dict(id=actor, active=True, revision=1, role_code='ADMIN', account_origin='LOCAL',
            bootstrap_closed=True, login_enabled=True, is_demo=True, can_manage_users=True)
        with self.admin() as c:
            c.execute(text("INSERT INTO v2_aaa.fixture_actor_identity VALUES (:a,true,'LOCAL','ADMIN',1,:d)"),
                      {'a':actor, 'd':STAMP})
        for source in ('LOCAL', 'RADIUS'):
            subscriber = 'demo-managed-sub-' + str(uuid4())
            router = 'demo-managed-router-' + str(uuid4())
            snapshot_data = self.f.request.plan.snapshot.model_dump(mode='json')
            snapshot_data['reference']['account_id'] = subscriber
            snapshot_data['nas']['router_id'] = router
            snapshot = type(self.f.request.plan.snapshot).model_validate_json(json.dumps(snapshot_data))
            plan = self.f.request.plan.model_copy(update={'snapshot':snapshot})
            request = self.f.request.model_copy(update={'actor_id':actor, 'plan':plan, 'request_id':uuid4()})
            scope = self.f.scope.model_copy(update={'actor_id':actor})
            provider = FakeFencedProvider(plan)
            bridge = PostgresFixtureBridge(self.sessions, self.resolver, provider)
            caps = ['DAILY_OWNER', 'AAA_ROUTER:' + router] + ['AAA_SUBSCRIBER_' + k for k in ('CREATE','EXTEND','PLAN','STATUS','READ')]
            with self.admin() as c:
                c.execute(insert(db.owner).values(id=subscriber,tenant_id=self.tenant,source=source,
                    revision=0,aaa_fence=0,aaa_active_operation=None))
                c.execute(text('INSERT INTO v2_aaa.fixture_membership '
                    '(tenant_id,actor_id,subscriber_id,active,revision,policy_revision,capabilities,deployment) '
                    'VALUES (:t,:a,:u,true,1,1,CAST(:c AS jsonb),:d)'),
                    {'t':self.tenant,'a':actor,'u':subscriber,'c':json.dumps(caps),'d':STAMP})
            binding = PanelOwnerBinding(actor_id=actor,tenant_id=self.tenant,subscriber_id=subscriber,
                router_id=router,request_id=request.request_id,source=source)
            access = PanelFixtureAccess(can_manage_subscriber=True,can_read_subscriber=True)
            deps = IsolatedPanelDependencies(backend=bridge,isolation_guard=lambda:True,
                identity_reader=lambda h:dict(user) if h=='fixture-session' else None,
                require_admin=lambda u:u,owner_reader=lambda *args:binding,access_reader=lambda *args:access)
            selection = IsolatedPanelSelection(enabled=True,deployment=STAMP,tenant_id=self.tenant,
                actor_ids=(actor,),subscriber_ids=(subscriber,),worker_id='fixture-worker')
            adapter = PanelAaaAdapter(selection,deps)
            now = self.engine.connect()
            try: today = now.execute(text("SELECT (clock_timestamp() AT TIME ZONE 'Europe/Istanbul')::date")).scalar_one()
            finally: now.close()
            account = SyntheticAaaAccount(username='aaa.fixture',plan='Fixture 100',status='ACTIVE',expires_on=today.isoformat())
            def command(kind, before, after, revision, **kwargs):
                return SyntheticAaaCommand(request_id=uuid4(),tenant_id=self.tenant,actor_id=actor,
                    subscriber_id=subscriber,router_id=router,expected_source=source,
                    expected_revision=revision,expected_fence=revision,operation=kind,
                    before=before,after=after,confirmed=True,**kwargs)
            def write(cmd): return adapter.subscriber_change('fixture-session',request,cmd)
            def owner_state():
                with self.admin() as c:
                    return tuple(c.execute(select(db.owner.c.revision, db.owner.c.aaa_fence).where(db.owner.c.id==subscriber)).one())
            create = command('CREATE',None,account,0)
            with self.assertRaises(PermissionError): PanelAaaAdapter().subscriber_change('fixture-session',request,create)
            denied = PanelAaaAdapter(selection,replace(deps,access_reader=lambda *args:PanelFixtureAccess()))
            with self.assertRaises(PermissionError): denied.subscriber_change('fixture-session',request,create)
            user['active'] = False
            with self.assertRaises(PermissionError): write(create)
            user['active'] = True
            self.assertIsNone(adapter.subscriber_result('fixture-session',request,create.request_id))
            receipt = write(create)
            self.assertEqual(receipt,adapter.subscriber_result('fixture-session',request,create.request_id))
            self.assertEqual(receipt,write(create))
            self.assertEqual(owner_state(),(1,1))
            with self.assertRaises(BridgeConflict): write(create.model_copy(update={'after':account.model_copy(update={'plan':'Foreign'})}))
            extended = account.model_copy(update={'expires_on':(today+timedelta(days=30)).isoformat()})
            extension = command('EXTEND',account,extended,1,days=30)
            self.assertEqual(write(extension).after,extended)
            planned = extended.model_copy(update={'plan':'Fixture 500'})
            self.assertEqual(write(command('PLAN',extended,planned,2)).before,extended)
            paused = planned.model_copy(update={'status':'PAUSED'})
            self.assertEqual(write(command('STATUS',planned,paused,3)).after,paused)
            self.assertEqual(owner_state(),(4,4))
            pending = command('PLAN',paused,paused.model_copy(update={'plan':'Fixture 900'}),4)
            # Committed revocation AFTER panel inspection must deny in the same
            # transaction resolver. No row outside this new fixture is touched.
            def revoke(value):
                with self.admin() as c:
                    c.execute(text('UPDATE v2_aaa.fixture_membership SET active=:v WHERE tenant_id=:t AND actor_id=:a AND subscriber_id=:u'),
                        {'v':value,'t':self.tenant,'a':actor,'u':subscriber})
            def race_access(*args):
                revoke(False)
                return access
            racing = PanelAaaAdapter(selection,replace(deps,access_reader=race_access))
            with self.assertRaises(PermissionError): racing.subscriber_change('fixture-session',request,pending)
            revoke(True)
            for table, field, value, restore in (
                ('fixture_actor_identity','active',False,True),
                ('fixture_actor_identity','role','OPERATOR','ADMIN'),
            ):
                with self.admin() as c:
                    c.execute(text('UPDATE v2_aaa.'+table+' SET '+field+'=:v WHERE actor_id=:a'),{'v':value,'a':actor})
                with self.assertRaises(PermissionError): write(pending)
                with self.admin() as c:
                    c.execute(text('UPDATE v2_aaa.'+table+' SET '+field+'=:v WHERE actor_id=:a'),{'v':restore,'a':actor})
            def owner_race_access(*args):
                with self.admin() as c:
                    c.execute(text('UPDATE v2_subscriber_workspace.subscribers SET source=:v WHERE id=:u'),
                              {'v':'RADIUS' if source=='LOCAL' else 'LOCAL','u':subscriber})
                return access
            owner_racing = PanelAaaAdapter(selection,replace(deps,access_reader=owner_race_access))
            with self.assertRaises(PermissionError): owner_racing.subscriber_change('fixture-session',request,pending)
            with self.admin() as c:
                c.execute(text('UPDATE v2_subscriber_workspace.subscribers SET source=:v WHERE id=:u'),{'v':source,'u':subscriber})
            with self.assertRaises(PermissionError): write(pending.model_copy(update={'tenant_id':uuid4()}))
            with self.assertRaises(PermissionError): write(pending.model_copy(update={'router_id':'demo-managed-router-foreign'}))
            # Audit INSERT fails after owner CAS; real PostgreSQL error must roll back both.
            def audit_fault(conn,cursor,statement,parameters,context,many):
                if statement.startswith('INSERT INTO v2_subscriber_workspace.events'):
                    conn.exec_driver_sql('SELECT 1/0')
            event.listen(self.engine,'before_cursor_execute',audit_fault)
            try:
                with self.assertRaises(Exception) as failure: write(pending)
                self.assertEqual(getattr(getattr(failure.exception,'orig',None),'sqlstate',None),'22012')
            finally: event.remove(self.engine,'before_cursor_execute',audit_fault)
            self.assertEqual(owner_state(),(4,4))
            def run(cmd):
                try: return write(cmd)
                except BridgeConflict: return None
            competing = command('STATUS',paused,paused.model_copy(update={'status':'ACTIVE'}),4)
            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(workers.map(run,[pending,competing]))
            self.assertEqual(sum(result is not None for result in results),1)
            self.assertEqual(owner_state(),(5,5))
            # Canonical stored receipt is exactly the returned historical result.
            with self.admin() as c:
                events = c.execute(select(db.audit).where(db.audit.c.subscriber_id==subscriber)).mappings().all()
            self.assertEqual(len(events),5)
            self.assertTrue(all(bridge._subscriber_receipt(e).actor_id==actor for e in events))
            corrupt = deepcopy(dict(events[0]))
            corrupt['changes']['_aaa_subscriber']['receipt']['after']['plan'] = 'Tampered'
            with self.assertRaises(BridgeConflict): bridge._subscriber_receipt(corrupt)
            self.assertEqual(receipt,write(create))
            self.assertEqual(provider.snapshot()['attempts'],{})
        with self.assertRaises(AaaBoundaryDisabled): AaaIdentityWriterBoundary(None,None,None,None).execute()

    def test_identity_gate_postgres_read_fail_closed(self):
        from app.integrations.aaa_identity_writer_boundary import AaaIdentityWriterBoundary, AaaBoundaryDisabled
        from app.integrations.aaa_fixture_read_gate import AaaFixtureReadGate
        f = self.f
        def identity(handle):
            if handle != 'synthetic-session':
                return None
            with self.admin() as c:
                row = c.execute(text('SELECT * FROM v2_aaa.fixture_actor_identity WHERE actor_id=:a'),
                                {'a': self.actor}).mappings().one()
            return dict(id=row['actor_id'], active=row['active'], bootstrap_closed=True,
                        login_enabled=True, role_code=row['role'], account_origin=row['origin'], can_manage_users=True)
        def permission(handle, request):
            with self.admin() as c:
                row = c.execute(text('SELECT active,capabilities FROM v2_aaa.fixture_membership '
                    'WHERE tenant_id=:t AND actor_id=:a AND subscriber_id=:u'),
                    {'t': self.tenant, 'a': self.actor, 'u': self.subscriber}).mappings().one()
            return row['active'] is True and 'AAA_READ' in row['capabilities']
        def owner(request):
            with self.admin() as c:
                row = c.execute(text('SELECT source FROM v2_subscriber_workspace.subscribers '
                    'WHERE tenant_id=:t AND id=:u'), {'t': self.tenant, 'u': self.subscriber}).one()
            return dict(actor_id=self.actor, tenant_id=str(self.tenant), subscriber_id=self.subscriber,
                        router_id=f.request.plan.snapshot.nas.router_id, source=row.source)
        def forbidden(*args, **kwargs):
            raise AssertionError('REAL_WRITER_FORBIDDEN')
        boundary = AaaIdentityWriterBoundary(identity, permission, owner, forbidden)
        gate = AaaFixtureReadGate(boundary, self.bridge.read)
        def read(scope=None):
            return gate.read('synthetic-session', f.request, f.scope if scope is None else scope, self.principal)
        provider_before = f.provider.snapshot()
        before = read()[0].snapshot()
        with self.assertRaises(PermissionError):
            read(f.scope.model_copy(update={'tenant_id': str(uuid4())}))
        # Revocations both before inspection and after inspection (TOCTOU).
        for table, change, restore in (
            ('fixture_actor_identity', 'active=false', 'active=true'),
            ('fixture_membership', "capabilities='[]'::jsonb", 'capabilities=CAST(:caps AS jsonb)'),
        ):
            def update(value):
                with self.admin() as c:
                    c.execute(text('UPDATE v2_aaa.' + table + ' SET ' + value + ' WHERE actor_id=:a'),
                              {'a': self.actor, 'caps': json.dumps(CAPS)})
            update(change)
            with self.assertRaises(PermissionError): read()
            update(restore)
            def race(*args):
                update(change)
                return self.bridge.read(*args)
            with self.assertRaises(PermissionError):
                AaaFixtureReadGate(boundary, race).read('synthetic-session', f.request, f.scope, self.principal)
            update(restore)
        # Owner revision change after inspection must be rejected by the locked
        # authoritative owner/journal binding, not trusted boundary metadata.
        def owner_race(*args):
            with self.admin() as c:
                c.execute(text('UPDATE v2_subscriber_workspace.subscribers SET revision=revision+1 '
                    'WHERE tenant_id=:t AND id=:u'), {'t': self.tenant, 'u': self.subscriber})
            return self.bridge.read(*args)
        with self.assertRaisesRegex(BridgeConflict, 'OWNER_JOURNAL_DRIFT'):
            AaaFixtureReadGate(boundary, owner_race).read('synthetic-session', f.request, f.scope, self.principal)
        with self.admin() as c:
            c.execute(text('UPDATE v2_subscriber_workspace.subscribers SET revision=revision-1 '
                'WHERE tenant_id=:t AND id=:u'), {'t': self.tenant, 'u': self.subscriber})
        with self.assertRaises(AaaBoundaryDisabled): boundary.execute()
        self.assertEqual(before, read()[0].snapshot())
        self.assertEqual(provider_before, f.provider.snapshot())

    def call(self, capability, callback, **kwargs):
        return self.bridge.invoke(self.f.request,self.f.scope,self.principal,capability,callback,**kwargs)

    def state(self):
        return self.bridge.read(self.f.request,self.f.scope,self.principal)[0].snapshot()

    def issue(self, number=18000, seconds=60):
        f=self.f
        def issue(unit):
            service=PreparedExecutionService(unit,f.provider)
            plan=service.plan(f.request,f.scope,self.prepared.authorization_id,'COMMIT_OWNER_CAS',permission=True)
            return service.issue(f.request,f.scope,f.execution_authority,plan,
                ExecutionIntent(authorization_id=UUID(int=number),lifetime_seconds=seconds),permission=True)
        return self.call('AAA_PREPARE',issue)

    def consume(self, grant):
        f=self.f
        return self.call('AAA_PREPARE',lambda u:PreparedExecutionService(u,f.provider).consume(
            f.request,f.scope,f.execution_authority,grant,permission=True))

    def claim(self, seconds=30):
        f=self.f
        return self.call('AAA_EXECUTE',lambda u:FixtureExecutor(u,f.provider).claim(f.request,f.scope,f.runner,
            self.grant.authorization_id,AttemptIntent(attempt_id=UUID(int=18001),seconds=seconds),permission=True))

    def accept(self, receipt):
        f=self.f
        return self.call('AAA_EXECUTE',lambda u:FixtureExecutor(u,f.provider).accept(f.request,f.scope,f.runner,receipt,permission=True))

    def staged(self, seconds=60):
        self.grant=self.issue(seconds=seconds)
        self.consume(self.grant)

    def test_prepared_success_cold_reload_receipt_replay_and_daily_owner_gate(self):
        self.staged()
        f=self.f
        owner=next(iter(self.state()['owners'].values()))
        with self.assertRaises(OwnerContractConflict):self.bridge.daily_touch(f.request,f.scope,self.principal,owner)
        command=self.claim()
        receipt=self.bridge.run(f.request,f.scope,self.principal,f.runner,command)
        self.bridge=PostgresFixtureBridge(self.sessions,self.resolver,f.provider)
        accepted=self.accept(receipt)
        before=self.state()
        self.assertEqual(self.accept(receipt),accepted)
        self.assertEqual(before,self.state())
        final=next(iter(before['owners'].values()))
        self.assertEqual(final.authority,'RADIUS');self.assertIsNone(final.active_request)
        self.assertEqual(self.bridge.daily_touch(f.request,f.scope,self.principal,final).fence,final.fence+1)

    def test_real_server_ttl_expiry_cannot_consume_or_change_owner(self):
        grant=self.issue(seconds=1)
        before=self.state()
        time.sleep(1.05)
        with self.assertRaises(AtomicConflict):self.consume(grant)
        self.assertEqual(before,self.state())

    def test_concurrent_prepared_consumption_has_one_winner_and_one_unused_grant(self):
        grants=[self.issue(18000),self.issue(18002)]
        def compete(grant):
            try:self.consume(grant);return 'WIN'
            except AtomicConflict:return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete,grants)),['WIN','CONFLICT'])
        state=self.state()
        self.assertEqual(sum(g.authorization_id in state['execution_records'] for g in grants),1)

    def test_lost_response_durable_inflight_unknown_and_authorized_decision(self):
        self.staged();command=self.claim(seconds=1);f=self.f
        with self.assertRaises(BridgeConflict):
            self.bridge.run(f.request,f.scope,self.principal,f.runner,command,fail_response=True)
        state=self.state()
        self.assertEqual(state['executor_status'][command.execution_id],'IN_FLIGHT')
        with self.assertRaises(AtomicConflict):self.bridge.run(f.request,f.scope,self.principal,f.runner,command)
        time.sleep(1.05)
        accepted=self.call('AAA_EXECUTE',lambda u:FixtureExecutor(u,f.provider).timeout(f.request,f.scope,f.runner,command,permission=True))
        self.assertEqual(accepted.receipt.outcome,'UNKNOWN')
        evaluation=self.call('AAA_DECISION',lambda u:ExecutorReconciliationService(u,f.provider).evaluate(
            f.request,f.scope,f.context,command.execution_id,permission=True))
        self.assertEqual(evaluation.status,'CONFIRMED_SUCCESS')
        grant=self.call('AAA_DECISION',lambda u:ExecutorReconciliationService(u,f.provider).issue(
            f.request,f.scope,f.context,evaluation,ExecutorDecisionIntent(authorization_id=UUID(int=18003),decision='CONFIRM_SUCCESS'),permission=True))
        self.call('AAA_DECISION',lambda u:ExecutorReconciliationService(u,f.provider).apply(f.request,f.scope,f.context,grant,permission=True))
        state=self.state();self.assertEqual(state['executor_accepted'][command.execution_id],accepted)
        self.assertEqual(next(iter(state['journal'].values())).state,'NEXT_STEP_DECISION_RECORDED')
        self.assertEqual(next(iter(state['owners'].values())).authority,'LOCAL')

    def test_revoked_actor_membership_or_policy_cannot_consume(self):
        grant=self.issue();before=self.state()
        for table,updates,restore in [('fixture_actor_identity',"active=false,revision=2","active=true,revision=3"),
            ('fixture_membership',"active=false,revision=2","active=true,revision=3"),
            ('fixture_membership',"capabilities='[]'::jsonb,policy_revision=2",'capabilities=CAST(:caps AS jsonb),policy_revision=3')]:
            with self.admin() as c:c.execute(text('UPDATE v2_aaa.'+table+' SET '+updates+' WHERE actor_id=:actor'),{'actor':self.actor})
            with self.assertRaises(PermissionError):self.consume(grant)
            with self.admin() as c:c.execute(text('UPDATE v2_aaa.'+table+' SET '+restore+' WHERE actor_id=:actor'),{'actor':self.actor,'caps':json.dumps(CAPS)})
            self.assertEqual(before,self.state())

    def test_tampered_authorization_and_foreign_principal_are_readonly(self):
        grant=self.issue();before=self.state()
        with self.assertRaises(AtomicConflict):self.consume(grant.model_copy(update={'version':'wrong'}))
        with self.assertRaises(PermissionError):self.bridge.read(self.f.request,self.f.scope,self.principal.model_copy(update={'actor_id':'foreign'}))
        def regress(unit):
            key,owner_key,op=unit._match(unit._state,self.f.request)
            owner=unit._state['owners'][owner_key]
            unit._state['owners'][owner_key]=owner.model_copy(update={'revision':owner.revision-1})
            unit._state['journal'][key]=op.model_copy(update={'owner_revision':owner.revision-1})
        with self.assertRaisesRegex(BridgeConflict,'MONOTONIC_OWNER'):self.call('AAA_PREPARE',regress)
        self.assertEqual(before,self.state())

    def test_changed_actor_or_policy_epoch_invalidates_issued_grant(self):
        grant=self.issue();before=self.state()
        for table,column in (('fixture_actor_identity','revision'),('fixture_membership','policy_revision')):
            with self.admin() as c:c.execute(text('UPDATE v2_aaa.'+table+' SET '+column+'='+column+'+1 WHERE actor_id=:actor'),{'actor':self.actor})
            with self.assertRaisesRegex(PermissionError,'MEMBERSHIP_EPOCH_CHANGED'):self.consume(grant)
            self.assertEqual(before,self.state())

    def test_sql_audit_fault_rolls_back_receipt_but_keeps_fake_provider_evidence(self):
        self.staged();command=self.claim();f=self.f
        receipt=self.bridge.run(f.request,f.scope,self.principal,f.runner,command)
        before=self.state();provider=f.provider.snapshot()
        constraint='aaa_fixture_fault_'+self.tenant.hex
        with self.admin() as c:c.exec_driver_sql('ALTER TABLE v2_subscriber_workspace.events ADD CONSTRAINT '+constraint+
            " CHECK (tenant_id <> '"+str(self.tenant)+"'::uuid) NOT VALID")
        try:
            with self.assertRaises(Exception) as failure:self.accept(receipt)
            self.assertEqual(getattr(failure.exception.orig,'sqlstate',None),'23514')
            self.assertEqual(before,self.state());self.assertEqual(provider,f.provider.snapshot())
        finally:
            with self.admin() as c:c.exec_driver_sql('ALTER TABLE v2_subscriber_workspace.events DROP CONSTRAINT '+constraint)
        self.assertEqual(self.bridge.run(f.request,f.scope,self.principal,f.runner,command),receipt)
        self.accept(receipt)

    def test_attempt_expiring_after_load_cannot_dispatch_or_change_pg_checkpoint(self):
        self.staged();command=self.claim(seconds=1);f=self.f
        before=self.state();provider=f.provider.snapshot();read=self.bridge.read
        def delayed(*args,**kwargs):
            result=read(*args,**kwargs)
            time.sleep(1.05)
            return result
        with patch.object(self.bridge,'read',side_effect=delayed):
            with self.assertRaises(AtomicConflict):
                self.bridge.run(f.request,f.scope,self.principal,f.runner,command)
        self.assertEqual(before,self.state());self.assertEqual(provider,f.provider.snapshot())

    def test_rejected_receipt_preserves_local_owner_and_reservation(self):
        self.staged();command=self.claim();f=self.f
        receipt=self.bridge.run(f.request,f.scope,self.principal,f.runner,command,outcome='REJECTED')
        result=self.accept(receipt)
        self.assertEqual(result.state,'FIXTURE_STEP_REJECTED')
        owner=next(iter(self.state()['owners'].values()))
        self.assertEqual(owner.authority,'LOCAL');self.assertEqual(owner.active_request,f.request.request_id)

    def test_unknown_receipt_is_not_success_or_an_automatic_retry_permission(self):
        self.staged();command=self.claim();f=self.f
        receipt=self.bridge.run(f.request,f.scope,self.principal,f.runner,command,outcome='UNKNOWN')
        result=self.accept(receipt)
        self.assertEqual(result.state,'FIXTURE_STEP_UNKNOWN')
        state=self.state()
        self.assertEqual(next(iter(state['owners'].values())).authority,'LOCAL')
        evaluation=self.call('AAA_DECISION',lambda u:ExecutorReconciliationService(u,f.provider).evaluate(
            f.request,f.scope,f.context,command.execution_id,permission=True))
        self.assertEqual(evaluation.status,'READ_ONLY_RECONCILIATION_REQUIRED')
        with self.assertRaises(AtomicConflict):self.bridge.run(f.request,f.scope,self.principal,f.runner,command)
        self.assertEqual(state,self.state())
