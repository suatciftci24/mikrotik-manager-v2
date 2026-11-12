"""New panel boundary only. Synthetic DI backend, no PostgreSQL/HTTP/login IO."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

from backend.tests import test_aaa_next_step_preparation as builders
from backend.tests import test_aaa_next_step_executor as root
from app.integrations.aaa_contracts import PreviewScope, snapshot_fingerprint
from app.repositories.aaa_membership import SessionMembershipResolver
from app.repositories.aaa_owner_contract import OwnerScope
from app.services.aaa_panel_adapter import (PanelAaaAdapter, IsolatedPanelSelection,
    IsolatedPanelDependencies, PanelFixtureAccess, PanelOwnerBinding)
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_execution import ExecutionIntent
from app.simulation.aaa_executor import FixtureExecutor, AttemptIntent, FixtureCrash


class FixtureBackend:
    def __init__(self, f, deployment):
        self.f, self.provider, self.deployment = f, f.provider, deployment
        self.calls=[];self.outcome='SUCCESS';self.crash=None;self.session=object()
        self.member=dict(tenant_id=UUID(f.request.plan.tenant_id),actor_id=f.request.actor_id,
            subscriber_id=f.request.plan.snapshot.reference.account_id,active=True,revision=1,policy_revision=1,
            deployment=deployment,capabilities=['AAA_METADATA','AAA_PREPARE','AAA_EXECUTE'])
        self.resolver=SessionMembershipResolver(deployment=deployment,target_guard=lambda s:s is self.session,
            actor_reader=lambda s,a:dict(actor_id=a,active=True,origin='LOCAL',role='ADMIN',revision=1,deployment=deployment),
            membership_reader=lambda s,o:self.member)

    def _guard(self, request, scope, principal, capability):
        self.calls.append((capability,principal,scope))
        self.resolver.resolve(self.session,principal,OwnerScope(tenant_id=UUID(scope.tenant_id),
            actor_id=scope.actor_id,subscriber_id=request.plan.snapshot.reference.account_id),capability)

    def invoke(self, request, scope, principal, capability, callback):
        self._guard(request,scope,principal,capability)
        return callback(self.f.unit)

    def run(self, request, scope, principal, context, command):
        self._guard(request,scope,principal,'AAA_EXECUTE')
        return FixtureExecutor(self.f.unit,self.provider,outcome=self.outcome).run(
            request,scope,context,command,permission=True,crash=self.crash)


class PanelAaaAdapterTests(TestCase):
    def setUp(self):
        for target in ('socket.socket','socket.create_connection','sqlite3.connect','psycopg.connect'):
            self.enterContext(patch(target,side_effect=AssertionError('External IO forbidden')))
        self.tenant=UUID(int=19000);self.actor='aaa-panel-fixture-19001'
        make=root.synthetic_request
        def synthetic():
            base=make();data=base.snapshot.model_dump(mode='json')
            data['reference'].update(tenant_id=str(self.tenant),store='PERSISTENT_WORKSPACE',account_id='demo-managed-sub-panel-fixture')
            data['nas']['router_id']='demo-managed-router-panel-fixture'
            snapshot=type(base.snapshot).model_validate_json(json.dumps(data))
            scope=PreviewScope(actor_id=self.actor,store='PERSISTENT_WORKSPACE',tenant_id=str(self.tenant),workspace_admin=True)
            proof=base.proof.model_copy(update={'actor_id':self.actor,'store':'PERSISTENT_WORKSPACE',
                'account_id':snapshot.reference.account_id,'snapshot_sha256':snapshot_fingerprint(snapshot)})
            return type(base).model_validate_json(base.model_copy(update={'snapshot':snapshot,'scope':scope,'proof':proof}).model_dump_json())
        helper=builders.NextStepPreparationTests(methodName='runTest')
        try:
            with patch.object(root,'synthetic_request',side_effect=synthetic):
                self.f=helper.setup_fixture();self.prepared=helper.prepare(helper.issue())
        finally:helper.doCleanups()
        self.request=self.f.request;self.session='opaque-fixture-session';self.reads=0
        self.user=dict(id=self.actor,active=True,revision=1,role_code='ADMIN',account_origin='LOCAL',
            bootstrap_closed=True,login_enabled=True,is_demo=True,can_manage_users=True)
        self.binding=PanelOwnerBinding(actor_id=self.actor,tenant_id=self.tenant,subscriber_id=self.request.plan.snapshot.reference.account_id,
            router_id=self.request.plan.snapshot.nas.router_id,request_id=self.request.request_id)
        self.access=PanelFixtureAccess(can_issue_prepared=True,can_consume_prepared=True,can_execute=True,can_accept=True,can_record_timeout=True)
        self.selection=IsolatedPanelSelection(enabled=True,deployment='panel-fixture-stamp',tenant_id=self.tenant,
            actor_ids=(self.actor,),subscriber_ids=(self.binding.subscriber_id,),worker_id='aaa-panel-fixture-worker')
        self.backend=FixtureBackend(self.f,self.selection.deployment)
        def reader(handle):
            self.reads+=1
            return deepcopy(self.user) if handle==self.session else None
        def admin(user):
            if user['role_code']!='ADMIN' or user['can_manage_users'] is not True:raise PermissionError('Central admin denied')
            return user
        self.deps=IsolatedPanelDependencies(backend=self.backend,isolation_guard=lambda:True,identity_reader=reader,
            require_admin=admin,owner_reader=lambda request,actor:self.binding,access_reader=lambda handle,binding:self.access)
        self.adapter=PanelAaaAdapter(self.selection,self.deps)

    def snapshot(self):return self.f.unit.snapshot(),self.f.provider.snapshot()
    def issue(self,seconds=60):
        return self.adapter.issue_prepared(self.session,self.request,self.prepared.authorization_id,
            ExecutionIntent(authorization_id=UUID(int=19002),lifetime_seconds=seconds))
    def staged(self):
        self.grant=self.issue();return self.adapter.consume_prepared(self.session,self.request,self.grant)
    def claim(self,seconds=30):
        return self.adapter.claim(self.session,self.request,self.grant.authorization_id,AttemptIntent(attempt_id=UUID(int=19003),seconds=seconds))

    def test_default_disabled_and_environment_flag_cannot_enable_or_touch_dependencies(self):
        before=self.snapshot()
        with patch.dict(os.environ,{'V2_AAA_PANEL_ENABLED':'true'}):
            for adapter in (PanelAaaAdapter(),PanelAaaAdapter(self.selection.model_copy(update={'enabled':False}),self.deps)):
                with self.assertRaisesRegex(PermissionError,'DISABLED'):
                    adapter.issue_prepared(self.session,self.request,self.prepared.authorization_id,ExecutionIntent(authorization_id=UUID(int=1)))
        self.assertEqual(before,self.snapshot());self.assertEqual(self.reads,0);self.assertEqual(self.backend.calls,[])
        self.adapter=PanelAaaAdapter(self.selection,replace(self.deps,isolation_guard=lambda:False))
        with self.assertRaises(PermissionError):self.issue()
        self.assertEqual(self.reads,0)
        class UnavailableBackend:
            @property
            def provider(self):raise AssertionError('Backend touched before isolation')
        self.adapter=PanelAaaAdapter(self.selection,replace(self.deps,isolation_guard=lambda:False,backend=UnavailableBackend()))
        with self.assertRaises(PermissionError):self.issue()

    def test_unauthenticated_bootstrap_demo_viewer_inactive_and_truthy_flags_deny(self):
        before=self.snapshot();original=dict(self.user)
        for change in ({'account_origin':'DEMO'},{'account_origin':'BOOTSTRAP_DEMO'},{'role_code':'VIEWER'},
                       {'active':False},{'active':1},{'bootstrap_closed':False},{'login_enabled':False},{'can_manage_users':False}):
            self.user={**original,**change}
            with self.assertRaises(PermissionError):self.issue()
            self.assertEqual(before,self.snapshot())
        self.user=original
        with self.assertRaises(PermissionError):self.adapter.issue_prepared('invalid-session',self.request,self.prepared.authorization_id,ExecutionIntent(authorization_id=UUID(int=1)))
        self.assertEqual(self.backend.calls,[])
        for result in (False,None):
            self.adapter=PanelAaaAdapter(self.selection,replace(self.deps,require_admin=lambda user:result))
            with self.assertRaisesRegex(PermissionError,'CENTRAL_PANEL_ADMIN_REQUIRED'):self.issue()
        self.assertEqual(self.backend.calls,[])

    def test_wrong_owner_tenant_router_actor_or_unselected_fixture_denies_before_backend(self):
        before=self.snapshot();original=self.binding
        for change in ({'tenant_id':UUID(int=1)},{'subscriber_id':'demo-managed-sub-other'},
                       {'router_id':'demo-managed-router-other'},{'actor_id':'aaa-panel-fixture-other'},{'request_id':UUID(int=1)}):
            self.binding=original.model_copy(update=change)
            with self.assertRaises(PermissionError):self.issue()
            self.assertEqual(before,self.snapshot())
        self.binding=original
        self.adapter=PanelAaaAdapter(self.selection.model_copy(update={'subscriber_ids':()}),self.deps)
        with self.assertRaises(PermissionError):self.issue()
        self.assertEqual(self.backend.calls,[])

    def test_success_uses_membership_bridge_and_duplicate_receipt_is_idempotent_not_redispatched(self):
        self.staged();command=self.claim()
        receipt=self.adapter.run(self.session,self.request,command)
        accepted=self.adapter.accept(self.session,self.request,receipt)
        before=self.snapshot()
        self.assertEqual(self.adapter.accept(self.session,self.request,receipt),accepted)
        with self.assertRaises(AtomicConflict):self.adapter.run(self.session,self.request,command)
        with self.assertRaises(AtomicConflict):self.adapter.consume_prepared(self.session,self.request,self.grant)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(next(iter(before[0]['owners'].values())).authority,'RADIUS')
        for capability,principal,scope in self.backend.calls:
            self.assertIn(capability,('AAA_PREPARE','AAA_EXECUTE'));self.assertEqual(principal.actor_id,self.actor)
            self.assertEqual(principal.deployment,self.selection.deployment);self.assertEqual(scope,self.f.scope)
        self.assertEqual(self.reads,len(self.backend.calls))

    def test_expired_prepared_authorization_does_not_consume(self):
        grant=self.issue(seconds=2);self.f.clock.advance(2);before=self.snapshot()
        with self.assertRaises(AtomicConflict):self.adapter.consume_prepared(self.session,self.request,grant)
        self.assertEqual(before,self.snapshot())

    def test_panel_admin_is_not_aaa_permission_and_identity_is_fresh_at_consume(self):
        self.access=PanelFixtureAccess()
        with self.assertRaises(PermissionError):self.issue()
        self.assertEqual(self.backend.calls,[])
        self.access=PanelFixtureAccess(can_issue_prepared=True)
        grant=self.issue();before=self.snapshot()
        with self.assertRaises(PermissionError):self.adapter.consume_prepared(self.session,self.request,grant)
        self.access=self.access.model_copy(update={'can_consume_prepared':True})
        self.user['active']=False
        with self.assertRaises(PermissionError):self.adapter.consume_prepared(self.session,self.request,grant)
        self.assertEqual(before,self.snapshot());self.assertEqual(len(self.backend.calls),1)

    def test_membership_revocation_still_denies_when_panel_admin_and_fixture_access_allow(self):
        grant=self.issue();before=self.snapshot();self.backend.member['active']=False
        with self.assertRaises(PermissionError):self.adapter.consume_prepared(self.session,self.request,grant)
        self.assertEqual(before,self.snapshot())

    def test_unknown_receipt_remains_local_and_cannot_be_promoted_or_retried(self):
        self.staged();command=self.claim();self.backend.outcome='UNKNOWN'
        receipt=self.adapter.run(self.session,self.request,command)
        result=self.adapter.accept(self.session,self.request,receipt)
        self.assertTrue(result.reconciliation_required);self.assertEqual(result.state,'FIXTURE_STEP_UNKNOWN')
        before=self.snapshot()
        with self.assertRaises(AtomicConflict):self.adapter.run(self.session,self.request,command)
        with self.assertRaises(AtomicConflict):self.adapter.accept(self.session,self.request,receipt.model_copy(update={'outcome':'SUCCESS'}))
        self.assertEqual(before,self.snapshot());self.assertEqual(next(iter(before[0]['owners'].values())).authority,'LOCAL')

    def test_foreign_command_receipt_or_grant_is_rejected_without_effect(self):
        grant=self.issue();before=self.snapshot();calls=len(self.backend.calls)
        bad=grant.model_copy(update={'actor_id':'aaa-panel-fixture-other'})
        with self.assertRaises(PermissionError):self.adapter.consume_prepared(self.session,self.request,bad)
        self.assertEqual(len(self.backend.calls),calls);self.assertEqual(before,self.snapshot())
        self.grant=grant;self.adapter.consume_prepared(self.session,self.request,grant);command=self.claim()
        before=self.snapshot();calls=len(self.backend.calls)
        with self.assertRaises(PermissionError):self.adapter.run(self.session,self.request,command.model_copy(update={'worker_id':'foreign'}))
        self.assertEqual(len(self.backend.calls),calls);self.assertEqual(before,self.snapshot())
        receipt=self.adapter.run(self.session,self.request,command);before=self.snapshot();calls=len(self.backend.calls)
        with self.assertRaises(PermissionError):self.adapter.accept(self.session,self.request,receipt.model_copy(update={'subscriber_id':'demo-managed-sub-other'}))
        self.assertEqual(len(self.backend.calls),calls);self.assertEqual(before,self.snapshot())

    def test_timeout_is_separate_expiry_bound_permission_and_late_receipt_conflicts(self):
        self.staged();command=self.claim(seconds=1);self.backend.crash='AFTER_EFFECT'
        with self.assertRaises(FixtureCrash):self.adapter.run(self.session,self.request,command)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict):self.adapter.timeout(self.session,self.request,command)
        self.assertEqual(before,self.snapshot());self.f.clock.advance(1)
        self.access=self.access.model_copy(update={'can_record_timeout':False})
        with self.assertRaises(PermissionError):self.adapter.timeout(self.session,self.request,command)
        self.access=self.access.model_copy(update={'can_record_timeout':True})
        result=self.adapter.timeout(self.session,self.request,command)
        self.assertTrue(result.reconciliation_required)
        late=self.f.provider.snapshot()['executor_receipts'][command.execution_id];before=self.snapshot()
        with self.assertRaises(AtomicConflict):self.adapter.accept(self.session,self.request,late)
        self.assertEqual(before,self.snapshot())
