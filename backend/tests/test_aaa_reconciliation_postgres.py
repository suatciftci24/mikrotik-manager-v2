from contextlib import contextmanager
from datetime import timedelta
import json
import secrets
import time
from uuid import uuid4
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text, select, insert, event, create_engine
from sqlalchemy.orm import Session
from backend.tests import test_aaa_pg_bridge as base
from app.repositories import aaa_metadata as db
from app.repositories.aaa_fixture_bridge import BridgeConflict, PostgresFixtureBridge
from app.repositories.aaa_reconciliation import DurableFixtureReconciliation, RemoteObservation
from app.integrations.aaa_runtime_guard import require_fixture_runtime
from app.simulation.aaa_executor import FixtureExecutor
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_atomic import canonical_hash


class ReconciliationPostgresAcceptance(base.PostgresBridgeAcceptance):
    expected_cluster_id = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with cls.engine.begin() as c:
            cls.verify(c)
            c.exec_driver_sql('CREATE TABLE v2_aaa.runtime_tenants (login name PRIMARY KEY,tenant_id uuid NOT NULL)')
            c.exec_driver_sql('CREATE FUNCTION v2_aaa.runtime_tenant() RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER '
                'SET search_path=pg_catalog AS $$ SELECT tenant_id FROM v2_aaa.runtime_tenants WHERE login=session_user $$')
            c.exec_driver_sql('REVOKE ALL ON FUNCTION v2_aaa.runtime_tenant() FROM PUBLIC')
            c.exec_driver_sql('GRANT EXECUTE ON FUNCTION v2_aaa.runtime_tenant() TO v26_aaa_fixture')
            for table in db.metadata.tables.values():
                name = table.fullname
                c.exec_driver_sql('ALTER TABLE '+name+' ENABLE ROW LEVEL SECURITY')
                c.exec_driver_sql('ALTER TABLE '+name+' FORCE ROW LEVEL SECURITY')
                c.exec_driver_sql('CREATE POLICY tenant_scope ON '+name+' TO v26_aaa_fixture '
                    'USING (tenant_id=v2_aaa.runtime_tenant()) WITH CHECK (tenant_id=v2_aaa.runtime_tenant())')
            c.exec_driver_sql('ALTER TABLE v2_aaa.fixture_membership ENABLE ROW LEVEL SECURITY')
            c.exec_driver_sql('ALTER TABLE v2_aaa.fixture_membership FORCE ROW LEVEL SECURITY')
            c.exec_driver_sql('CREATE POLICY tenant_scope ON v2_aaa.fixture_membership TO v26_aaa_fixture '
                'USING (tenant_id=v2_aaa.runtime_tenant()) WITH CHECK (tenant_id=v2_aaa.runtime_tenant())')
            # Definer lock functions must not bypass the tenant bound to session_user.
            c.exec_driver_sql('CREATE OR REPLACE FUNCTION v2_aaa.bridge_member_lock(uuid,text,text) '
                'RETURNS SETOF v2_aaa.fixture_membership LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog '
                'AS $$ SELECT * FROM v2_aaa.fixture_membership WHERE tenant_id=$1 AND actor_id=$2 '
                'AND subscriber_id=$3 AND tenant_id=v2_aaa.runtime_tenant() FOR UPDATE $$')
            c.exec_driver_sql('CREATE OR REPLACE FUNCTION v2_aaa.bridge_actor_lock(text) '
                'RETURNS SETOF v2_aaa.fixture_actor_identity LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog '
                'AS $$ SELECT * FROM v2_aaa.fixture_actor_identity a WHERE actor_id=$1 AND EXISTS '
                '(SELECT 1 FROM v2_aaa.fixture_membership m WHERE m.actor_id=a.actor_id '
                'AND m.tenant_id=v2_aaa.runtime_tenant()) FOR UPDATE $$')
            c.exec_driver_sql('REVOKE EXECUTE ON FUNCTION v2_aaa.fixture_membership_lock(uuid,text,text) FROM v26_aaa_fixture')
            c.exec_driver_sql('REVOKE UPDATE ON v2_aaa.runtime_tenants FROM v26_aaa_fixture')

    @contextmanager
    def sessions(self):
        engine = getattr(self,'runtime_engine',self.engine)
        with Session(engine) as s:
            def begin(session,transaction,c):
                if engine is self.engine:
                    self.verify(c)
                    c.execute(text('INSERT INTO v2_aaa.runtime_tenants VALUES (session_user,:t) '
                        'ON CONFLICT (login) DO UPDATE SET tenant_id=excluded.tenant_id'),dict(t=self.tenant))
                c.exec_driver_sql('SET LOCAL ROLE v26_aaa_fixture')
                if engine is not self.engine:
                    require_fixture_runtime(c,login=self.login,tenant_id=self.tenant)
            event.listen(s,'after_begin',begin)
            yield s

    def setUp(self):
        super().setUp()
        from psycopg import sql
        self.login = 'aaa_runtime_'+self.tenant.hex
        password = secrets.token_urlsafe(32)
        with self.admin() as c:
            c.connection.driver_connection.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS '
                'NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}').format(sql.Identifier(self.login),sql.Literal(password)))
            c.exec_driver_sql('GRANT v26_aaa_fixture TO '+self.login)
            c.execute(text('INSERT INTO v2_aaa.runtime_tenants VALUES (:r,:t)'),dict(r=self.login,t=self.tenant))
            caps = base.CAPS+['AAA_SUBSCRIBER_READ','AAA_ROUTER:'+self.f.request.plan.snapshot.nas.router_id]
            c.execute(text('UPDATE v2_aaa.fixture_membership SET capabilities=CAST(:c AS jsonb) WHERE tenant_id=:t'),
                      dict(c=json.dumps(caps),t=self.tenant))
        self.runtime_engine = create_engine(self.engine.url.set(username=self.login,password=password),hide_parameters=True,
            connect_args={'connect_timeout':5,'options':'-c statement_timeout=10000 -c lock_timeout=3000'})
        self.addCleanup(self.runtime_engine.dispose)

    def test_timeout_reconciliation_and_runtime_rls(self):
        self.exercise('TIMEOUT')

    def test_partial_reconciliation_and_runtime_rls(self):
        self.exercise('PARTIAL')

    def exercise(self, kind):
        f = self.f
        self.staged()
        command = self.claim(seconds=1)
        if kind=='TIMEOUT':
            with self.assertRaises(BridgeConflict):
                self.bridge.run(f.request,f.scope,self.principal,f.runner,command,fail_response=True)
            time.sleep(1.05)
            self.call('AAA_EXECUTE',lambda u:FixtureExecutor(u,f.provider).timeout(f.request,f.scope,f.runner,command,permission=True))
        else:
            receipt = self.bridge.run(f.request,f.scope,self.principal,f.runner,command,outcome='APPLY_THEN_UNKNOWN')
            self.accept(receipt)
        before = self.state()
        owner = next(iter(before['owners'].values()))
        remote = Mock(return_value=None)
        verifier = Mock(return_value=True)
        service = DurableFixtureReconciliation(self.bridge,remote,verifier)
        def evaluate(revision,identity=None,**changes):
            return service.evaluate(f.request,f.scope,self.principal,execution_id=command.execution_id,
                evaluation_id=identity or uuid4(),expected_revision=revision,
                owner_revision=owner.revision,fence=changes.get('fence',owner.fence))
        identity = uuid4()
        first = evaluate(0,identity)
        self.assertEqual(first.status,'UNKNOWN')
        remote.reset_mock()
        self.assertEqual(evaluate(0,identity),first)
        remote.assert_not_called()
        # Discard repository/provider instances: reconciliation depends only on
        # durable UNKNOWN + independent observations, not provider object IDs.
        from app.simulation.aaa_provider import FakeFencedProvider
        cold_bridge = PostgresFixtureBridge(self.sessions,self.resolver,FakeFencedProvider(f.request.plan))
        service = DurableFixtureReconciliation(cold_bridge,remote,verifier)
        self.assertEqual(evaluate(0,identity),first)
        with self.assertRaises(BridgeConflict): evaluate(1,identity)
        with self.assertRaises(BridgeConflict): evaluate(1,fence=owner.fence+1)
        with self.admin() as c: now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        observation = RemoteObservation(tenant_id=self.tenant,operation_id=f.request.request_id,
            execution_id=command.execution_id,subscriber_id=self.subscriber,router_id=f.request.plan.snapshot.nas.router_id,
            plan_hash=command.plan_hash,dispatch_fingerprint=canonical_hash(command.model_dump(mode='json')),
            owner_revision=owner.revision,fence=owner.fence,sequence=1,
            observed_at=now,valid_until=now+timedelta(minutes=1),outcome='APPLIED')
        remote.return_value = observation.model_copy(update={'tenant_id':uuid4()})
        self.assertEqual(evaluate(1).status,'UNKNOWN')
        remote.return_value = observation
        verifier.return_value = False
        self.assertEqual(evaluate(2).status,'UNKNOWN')
        verifier.return_value = True
        def audit_fault(conn,cursor,statement,parameters,context,many):
            if statement.startswith('INSERT INTO v2_subscriber_workspace.events'): conn.exec_driver_sql('SELECT 1/0')
        event.listen(self.runtime_engine,'before_cursor_execute',audit_fault)
        try:
            with self.assertRaises(Exception) as failure: evaluate(3)
            self.assertEqual(failure.exception.orig.sqlstate,'22012')
        finally: event.remove(self.runtime_engine,'before_cursor_execute',audit_fault)
        def compete(_):
            try: return evaluate(3)
            except BridgeConflict: return None
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(compete,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        confirmed = next(r for r in results if r is not None)
        self.assertEqual(confirmed.status,'CONFIRMED_APPLIED')
        self.assertFalse(confirmed.automatic_resume)
        remote.return_value = observation.model_copy(update={'outcome':'NOT_APPLIED'})
        with self.assertRaises(BridgeConflict): evaluate(4)
        remote.side_effect = TimeoutError('synthetic')
        self.assertEqual(evaluate(4).status,'UNKNOWN')
        remote.side_effect = None
        remote.return_value = observation.model_copy(update={'outcome':'NOT_APPLIED'})
        with self.assertRaises(BridgeConflict): evaluate(5)
        remote.return_value = observation.model_copy(update={'sequence':2,'outcome':'NOT_APPLIED'})
        self.assertEqual(evaluate(5).status,'CONFIRMED_NOT_APPLIED')
        remote.return_value = observation
        with self.assertRaises(BridgeConflict): evaluate(6)
        # Missing/expired/unverifiable evidence never reuses an earlier success.
        remote.return_value = observation.model_copy(update={'sequence':3,'valid_until':now})
        self.assertEqual(evaluate(6).status,'UNKNOWN')
        # Evaluation never changes the engine or dispatches a provider request.
        self.assertEqual(before,self.state())
        with self.assertRaises(AtomicConflict): self.bridge.run(f.request,f.scope,self.principal,f.runner,command)
        self.rls_acceptance(service,command,owner)

    def rls_acceptance(self, service, command, owner):
        foreign = uuid4()
        with self.admin() as c:
            c.execute(insert(db.reconciliations).values(tenant_id=foreign,execution_id=uuid4(),operation_id=uuid4(),revision=1,receipt={}))
        with self.sessions() as s, s.begin():
            # Caller-controlled tenant GUC cannot override the login's tenant.
            s.execute(text("SELECT set_config('app.tenant_id',:t,true)"),dict(t=str(foreign)))
            self.assertEqual(set(s.execute(select(db.reconciliations.c.tenant_id)).scalars()),{self.tenant})
            self.assertEqual(s.execute(db.reconciliations.update().where(db.reconciliations.c.tenant_id==foreign).values(revision=9)).rowcount,0)
            self.assertEqual(s.execute(text('SELECT * FROM v2_aaa.bridge_member_lock(:t,:a,:u)'),
                dict(t=foreign,a=self.actor,u=self.subscriber)).all(),[])
            with self.assertRaises(PermissionError): require_fixture_runtime(s,login='foreign',tenant_id=self.tenant)
        with self.assertRaises(Exception) as failure:
            with self.sessions() as s, s.begin():
                s.execute(insert(db.reconciliations).values(tenant_id=foreign,execution_id=uuid4(),operation_id=uuid4(),revision=1,receipt={}))
        self.assertEqual(failure.exception.orig.sqlstate,'42501')
        with self.assertRaises(Exception) as failure:
            with self.sessions() as s, s.begin():
                s.execute(text('UPDATE v2_aaa.runtime_tenants SET tenant_id=:t WHERE login=session_user'),dict(t=foreign))
        self.assertEqual(failure.exception.orig.sqlstate,'42501')
        with self.assertRaises(Exception) as failure:
            with self.sessions() as s, s.begin(): s.execute(text('SET ROLE v26_acceptance'))
        self.assertEqual(failure.exception.orig.sqlstate,'42501')
        # Fresh role revocation still denies historical UUID reads/evaluation.
        with self.admin() as c: c.execute(text("UPDATE v2_aaa.fixture_actor_identity SET role='VIEWER' WHERE actor_id=:a"),dict(a=self.actor))
        with self.assertRaises(PermissionError):
            service.evaluate(self.f.request,self.f.scope,self.principal,execution_id=command.execution_id,
                evaluation_id=uuid4(),expected_revision=7,owner_revision=owner.revision,fence=owner.fence)
