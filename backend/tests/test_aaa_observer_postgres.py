from datetime import timedelta
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from uuid import uuid4
from pydantic import SecretBytes
from sqlalchemy import text, select, event
from backend.tests import test_aaa_reconciliation_postgres as base
from app.repositories import aaa_metadata as db
from app.repositories.aaa_reconciliation import DurableFixtureReconciliation, RemoteObservation
from app.repositories.aaa_fixture_bridge import BridgeConflict
from app.integrations.aaa_remote_observer import SyntheticRemoteObserver, RemoteEvidenceVerifier
from app.integrations.aaa_runtime_guard import RuntimePrincipalGuard
from app.simulation.aaa_atomic import canonical_hash
from app.services.aaa_panel_adapter import (PanelAaaAdapter, IsolatedPanelDependencies,
    IsolatedPanelSelection, PanelOwnerBinding, PanelFixtureAccess)


class ObserverPostgresAcceptance(base.ReconciliationPostgresAcceptance):
    actor_prefix = 'aaa-panel-fixture-'
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with cls.engine.begin() as c:
            cls.verify(c)
            c.exec_driver_sql('ALTER TABLE v2_aaa.runtime_tenants ADD COLUMN actor_id text, ADD COLUMN deployment text')
            c.exec_driver_sql('CREATE FUNCTION v2_aaa.runtime_principal_lock() RETURNS TABLE '
                '(actor_id text,deployment text,tenant_id uuid) LANGUAGE sql SECURITY DEFINER '
                'SET search_path=pg_catalog AS $$ SELECT actor_id,deployment,tenant_id FROM v2_aaa.runtime_tenants '
                'WHERE login=session_user FOR SHARE $$')
            c.exec_driver_sql('REVOKE ALL ON FUNCTION v2_aaa.runtime_principal_lock() FROM PUBLIC')
            c.exec_driver_sql('GRANT EXECUTE ON FUNCTION v2_aaa.runtime_principal_lock() TO v26_aaa_fixture')

    def setUp(self):
        super().setUp()
        with self.admin() as c:
            c.execute(text('UPDATE v2_aaa.runtime_tenants SET actor_id=:a,deployment=:d WHERE login=:r'),
                      dict(a=self.actor,d=self.principal.deployment,r=self.login))
        self.staged()
        self.command = self.claim()
        result = self.bridge.run(self.f.request,self.f.scope,self.principal,self.f.runner,self.command,outcome='APPLY_THEN_UNKNOWN')
        self.accept(result)
        self.original = self.state()
        self.owner = next(iter(self.original['owners'].values()))
        with self.admin() as c: now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        self.observation = RemoteObservation(tenant_id=self.tenant,operation_id=self.f.request.request_id,
            execution_id=self.command.execution_id,subscriber_id=self.subscriber,
            router_id=self.f.request.plan.snapshot.nas.router_id,plan_hash=self.command.plan_hash,
            dispatch_fingerprint=canonical_hash(self.command.model_dump(mode='json')),
            owner_revision=self.owner.revision,fence=self.owner.fence,sequence=1,
            observed_at=now,valid_until=now+timedelta(seconds=25),outcome='APPLIED')
        self.options = dict(key=SecretBytes(secrets.token_bytes(32)),source_identity='fixture-observer-router7',source_revision=1)
        self.remote = SyntheticRemoteObserver([self.observation],**self.options)
        self.service = DurableFixtureReconciliation.with_observer(self.bridge,self.remote,
            RemoteEvidenceVerifier(**self.options),RuntimePrincipalGuard(login=self.login))
        f = self.f
        self.user = dict(id=self.actor,active=True,revision=1,role_code='ADMIN',account_origin='LOCAL',
            bootstrap_closed=True,login_enabled=True,is_demo=True,can_manage_users=True)
        self.access = PanelFixtureAccess(can_reconcile=True)
        self.binding = PanelOwnerBinding(actor_id=self.actor,tenant_id=self.tenant,subscriber_id=self.subscriber,
            router_id=f.request.plan.snapshot.nas.router_id,request_id=f.request.request_id)
        deps = IsolatedPanelDependencies(backend=self.bridge,isolation_guard=lambda:True,
            identity_reader=lambda h:dict(self.user) if h=='synthetic-session' else None,
            require_admin=lambda u:u,owner_reader=lambda *args:self.binding,access_reader=lambda *args:self.access)
        selection = IsolatedPanelSelection(enabled=True,deployment=self.principal.deployment,
            tenant_id=self.tenant,actor_ids=(self.actor,),subscriber_ids=(self.subscriber,),worker_id='observer-fixture')
        self.panel = PanelAaaAdapter(selection,deps)

    def evaluate(self, revision, identity=None, handle='synthetic-session'):
        return self.panel.reconcile(handle,self.f.request,self.service,execution_id=self.command.execution_id,
            evaluation_id=identity or uuid4(),expected_revision=revision,
            owner_revision=self.owner.revision,fence=self.owner.fence)

    def test_observer_evidence_atomicity_and_race(self):
        observed = []
        original = self.remote.observe
        def capture(challenge):
            envelope = original(challenge)
            observed.append(envelope)
            return envelope
        self.remote.observe = capture
        identity = uuid4()
        receipt = self.evaluate(0,identity)
        self.assertEqual(receipt.status,'CONFIRMED_APPLIED')
        self.assertEqual(receipt.observation.source_identity,self.options['source_identity'])
        self.assertEqual(self.evaluate(0,identity),receipt)
        self.assertEqual(len(observed),1)
        # Captured signed evidence from another evaluation must not be replayed.
        self.remote.observe = Mock(return_value=observed[0])
        self.assertEqual(self.evaluate(1).status,'UNKNOWN')
        self.remote.observe = Mock(side_effect=TimeoutError('synthetic'))
        self.assertEqual(self.evaluate(2).status,'UNKNOWN')
        # Even a correctly signed contradicting same-sequence observation is UNKNOWN.
        self.remote.observe = SyntheticRemoteObserver([self.observation.model_copy(update={'outcome':'NOT_APPLIED'})],**self.options).observe
        self.assertEqual(self.evaluate(3).status,'UNKNOWN')
        self.remote.observe = original
        def audit_fault(conn,cursor,statement,parameters,context,many):
            if statement.startswith('INSERT INTO v2_subscriber_workspace.events'): conn.exec_driver_sql('SELECT 1/0')
        event.listen(self.runtime_engine,'before_cursor_execute',audit_fault)
        try:
            with self.assertRaises(Exception) as failure: self.evaluate(4)
            self.assertEqual(failure.exception.orig.sqlstate,'22012')
        finally: event.remove(self.runtime_engine,'before_cursor_execute',audit_fault)
        def compete(_):
            try: return self.evaluate(4)
            except BridgeConflict: return None
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(compete,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(self.state(),self.original)
        with self.admin() as c:
            audits = c.execute(select(db.audit.c.changes).where(db.audit.c.operation=='AAA_RECONCILIATION_EVALUATED',
                db.audit.c.tenant_id==self.tenant)).scalars().all()
        self.assertEqual(len(audits),5)
        public = json.dumps(audits)
        self.assertNotIn(observed[0].signature,public)
        self.assertNotIn(self.options['key'].get_secret_value().hex(),public)

    def test_authenticated_principal_and_rls_denials(self):
        for handle in ('missing','foreign'):
            with self.assertRaises(PermissionError): self.evaluate(0,handle=handle)
        self.access = PanelFixtureAccess()
        with self.assertRaises(PermissionError): self.evaluate(0)
        self.access = PanelFixtureAccess(can_reconcile=True)
        self.user['role_code'] = 'VIEWER'
        with self.assertRaises((PermissionError,ValueError)): self.evaluate(0)
        self.user['role_code'] = 'ADMIN'
        original_binding = self.binding
        for changes in ({'router_id':'demo-managed-router-other'},{'subscriber_id':'demo-managed-sub-other'},
                        {'tenant_id':uuid4()},{'actor_id':'foreign'}):
            self.binding = original_binding.model_copy(update=changes)
            with self.assertRaises(PermissionError): self.evaluate(0)
        self.binding = original_binding
        for column,value in (('tenant_id',uuid4()),('actor_id','foreign'),('deployment','foreign')):
            with self.admin() as c:
                c.execute(text('UPDATE v2_aaa.runtime_tenants SET '+column+'=:v WHERE login=:r'),dict(v=value,r=self.login))
            with self.assertRaises(PermissionError): self.evaluate(0)
            with self.admin() as c:
                c.execute(text('UPDATE v2_aaa.runtime_tenants SET tenant_id=:t,actor_id=:a,deployment=:d WHERE login=:r'),
                    dict(t=self.tenant,a=self.actor,d=self.principal.deployment,r=self.login))
        # Fresh DB grants and owner/source are authoritative after panel inspection.
        with self.admin() as c:
            caps = c.execute(text('SELECT capabilities FROM v2_aaa.fixture_membership WHERE actor_id=:a'),dict(a=self.actor)).scalar_one()
            no_router = [x for x in caps if not x.startswith('AAA_ROUTER:')]
            c.execute(text('UPDATE v2_aaa.fixture_membership SET capabilities=CAST(:c AS jsonb) WHERE actor_id=:a'),
                      dict(c=json.dumps(no_router),a=self.actor))
        with self.assertRaises(PermissionError): self.evaluate(0)
        with self.admin() as c:
            c.execute(text('UPDATE v2_aaa.fixture_membership SET capabilities=CAST(:v AS jsonb) WHERE actor_id=:a'),dict(v=json.dumps(caps),a=self.actor))
            c.execute(text("UPDATE v2_subscriber_workspace.subscribers SET source='RADIUS' WHERE id=:u"),dict(u=self.subscriber))
        with self.assertRaises(BridgeConflict): self.evaluate(0)
        with self.admin() as c:
            c.execute(text("UPDATE v2_subscriber_workspace.subscribers SET source='LOCAL' WHERE id=:u"),dict(u=self.subscriber))
        self.assertEqual(self.evaluate(0).status,'CONFIRMED_APPLIED')
