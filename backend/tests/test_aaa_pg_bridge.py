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
    expected_cluster_id = '7707358750625226262'
    environment_guard = staticmethod(home_guard)
    @classmethod
    def verify(cls, connection):
        DisposableClusterGuard(ROOT)(ROOT / 'postgres-test')
        manifest = json.loads((ROOT / 'fixture-manifest.json').read_text())
        for p, key in ((ROOT, 'root_identity'), (ROOT / 'postgres-test', 'data_identity')):
            s = p.lstat()
            if (s.st_dev, s.st_ino, s.st_uid) != tuple(manifest[key]):
                raise RuntimeError('RECORDED_OWNERSHIP_REQUIRED')
        identity = connection.execute(text("SELECT current_database(),host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),current_setting('listen_addresses'),"
            "(SELECT system_identifier::text FROM pg_control_system())")).one()
        if tuple(identity) != ('mikrotik_v26_acceptance','127.0.0.1',55433,str(ROOT / 'postgres-test'),
                               '127.0.0.1',cls.expected_cluster_id):
            raise RuntimeError('EXACT_EXISTING_AAA_IDENTITY_REQUIRED')

    @classmethod
    def setUpClass(cls):
        cls.environment_guard()
        cls.env = _isolated_runtime()
        cls.env.__enter__()
        cls.addClassCleanup(lambda: cls.env.__exit__(None, None, None))
        url = URL.create('postgresql+psycopg', username='v26_acceptance', password=(ROOT / 'test-password').read_text(),
                         host='127.0.0.1', port=55433, database='mikrotik_v26_acceptance')
        cls.engine = create_engine(url, hide_parameters=True,
            connect_args={'connect_timeout':5,'options':'-c statement_timeout=10000 -c lock_timeout=3000'})
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.begin() as c:
            cls.verify(c)  # BEFORE any DDL/DML.
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
        self.actor = 'aaa-pg-actor-' + str(self.tenant)
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
