from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID
from pydantic import ValidationError

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import AtomicPlan, AtomicRequest, AtomicConflict
from app.simulation.aaa_worker import FakeLeaseClock, WorkerContext, Claim, LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, accept_provider_response
from app.simulation.aaa_decision import FixtureDecisionService, FixtureDecisionAuthority, DecisionIntent
from app.simulation.aaa_followup import FixtureFollowupService, FixtureFollowupAuthority, FollowupIntent
from app.simulation.aaa_execution import FixtureExecutionService, FixtureExecutionAuthority, ExecutionIntent
from app.simulation.aaa_executor import FixtureExecutor, ExecutorContext, AttemptIntent, FixtureCrash
from app.simulation.aaa_executor_decision import (ExecutorReconciliationService, ExecutorEvidenceContext,
    ExecutorDecisionIntent, EvidenceEvaluation, ExecutorDecisionConflict)

from app.simulation.aaa_executor_policy import (ExecutorPolicyService, ExecutorPolicyAuthority, ExecutorPolicyIntent, ExecutorContinuePlan, ExecutorCancelPlan, ExecutorPolicyConflict)

from app.simulation.aaa_next_step import NextStepExecutionService, NextStepPlan, NextStepExecutionAuthorization


class NextStepTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.root = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.root, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=2101), correlation_id=UUID(int=2102))
        self.clock = FakeLeaseClock(fixture.clock)
        self.worker = WorkerContext(tenant_id=self.root.tenant_id, worker_id='fixture-worker', can_deliver=True)
        self.context = ExecutorEvidenceContext(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id,
                                               can_evaluate=True, can_issue_decision=True, can_apply_decision=True)
        self.build_continue()
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))


    def build_unknown(self, outcome='SUCCESS', crash='AFTER_EFFECT', prefix=1):
        self.unit, self.provider = LeasedMemoryOutbox(self.root, self.clock), FakeFencedProvider(self.root)
        self.unit.reserve(self.request, self.scope, permission=True)
        for index in range(1, prefix + 1):
            lease = self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=index)), permission=True)
            self.unit.dispatch(self.request, self.scope, self.worker, lease, permission=True)
            command = self.provider.command(self.unit, self.request, self.scope, self.worker, lease, permission=True)
            receipt = self.provider.execute(self.unit, self.request, self.scope, self.worker, lease, command, permission=True)
            if index < prefix:
                accept_provider_response(self.unit, self.provider, self.request, self.scope, self.worker, lease, receipt, permission=True)
        self.unit.nack(self.request, self.scope, self.worker, lease, 'UNKNOWN', permission=True)
        recovery = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=prefix + 1), purpose='RECONCILE'), permission=True)
        service = FixtureDecisionService(self.unit, self.provider)
        authority = FixtureDecisionAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id, can_issue=True, can_commit=True)
        grant = service.issue(self.request, self.scope, self.worker, recovery, authority,
            DecisionIntent(authorization_id=UUID(int=2200), decision='ACCEPT_APPLIED_EVIDENCE'), permission=True)
        decision = service.commit(self.request, self.scope, self.worker, recovery, authority, grant, permission=True)
        followup = FixtureFollowupService(self.unit, self.provider)
        authority = FixtureFollowupAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id, can_continue=True)
        plan = followup.plan(self.request, self.scope, decision.authorization_id, 'CONTINUE', permission=True)
        grant = followup.issue(self.request, self.scope, authority, plan, FollowupIntent(authorization_id=UUID(int=2300)), permission=True)
        continued = followup.commit(self.request, self.scope, authority, grant, permission=True)
        execution = FixtureExecutionService(self.unit, self.provider)
        authority = FixtureExecutionAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id, can_issue=True, can_stage=True)
        plan = execution.plan(self.request, self.scope, continued.authorization_id, self.root.steps[prefix], permission=True)
        grant = execution.issue(self.request, self.scope, authority, plan, ExecutionIntent(authorization_id=UUID(int=2400)), permission=True)
        staged = execution.stage(self.request, self.scope, authority, grant, permission=True)
        self.executor = FixtureExecutor(self.unit, self.provider, outcome=outcome)
        worker = ExecutorContext(tenant_id=self.root.tenant_id, worker_id='executor', can_execute=True,
                                  can_accept=True, can_record_timeout=True)
        self.command = self.executor.claim(self.request, self.scope, worker, staged.authorization_id,
            AttemptIntent(attempt_id=UUID(int=2500)), permission=True)
        try:
            self.executor.run(self.request, self.scope, worker, self.command, permission=True, crash=crash)
        except FixtureCrash:
            pass
        self.clock.advance(30)  # Coordinator timeout requires the claimed attempt to expire.
        self.unknown = self.executor.timeout(self.request, self.scope, worker, self.command, permission=True)
        self.service = ExecutorReconciliationService(self.unit, self.provider)


    def build_decision(self, outcome='SUCCESS', prefix=1):
        self.build_unknown(outcome=outcome, prefix=prefix)
        evaluation = self.service.evaluate(self.request, self.scope, self.context, self.command.execution_id, permission=True)
        grant = self.service.issue(self.request, self.scope, self.context, evaluation,
            ExecutorDecisionIntent(authorization_id=UUID(int=3000), decision='CONFIRM_SUCCESS' if outcome == 'SUCCESS'
                                   else 'CONFIRM_REJECTION'), permission=True)
        self.decision = self.service.apply(self.request, self.scope, self.context, grant, permission=True)
        self.authority = ExecutorPolicyAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id,
                                                 can_continue=True, can_cancel=True)
        self.policy = ExecutorPolicyService(self.unit, self.provider)


    def build_continue(self, outcome='SUCCESS', prefix=1, kind='CONTINUE'):
        self.build_decision(outcome=outcome,prefix=prefix)
        policy_plan=self.policy.plan(self.request,self.scope,self.decision.authorization_id,kind,permission=True)
        policy_grant=self.policy.issue(self.request,self.scope,self.authority,policy_plan,
                                       ExecutorPolicyIntent(authorization_id=UUID(int=3100)),permission=True)
        self.continued=self.policy.apply(self.request,self.scope,self.authority,policy_grant,permission=True)
        self.next=NextStepExecutionService(self.unit,self.provider)
        self.execution_authority=FixtureExecutionAuthority(tenant_id=self.root.tenant_id,actor_id=self.scope.actor_id,
                                                           can_issue=True,can_stage=True)

    def plan(self,step='ENABLE_RADIUS'):
        return self.next.plan(self.request,self.scope,self.continued.authorization_id,step,permission=True)

    def issue(self,plan=None,number=1,seconds=30,authority=None):
        return self.next.issue(self.request,self.scope,authority or self.execution_authority,plan or self.plan(),
            ExecutionIntent(authorization_id=UUID(int=number),lifetime_seconds=seconds),permission=True)

    def stage(self,grant,**kwargs):
        return self.next.stage(self.request,self.scope,self.execution_authority,grant,permission=True,**kwargs)

    def test_canonical_next_step_contract_binds_parent_execution_decision_continue_and_scope(self):
        before=self.unit.snapshot(),self.provider.snapshot()
        plan=self.plan()
        self.assertEqual((plan.previous_execution_id,plan.decision_id,plan.continue_plan_hash,plan.owner_revision,plan.expected_state),
            (self.command.execution_id,self.decision.authorization_id,self.continued.plan_hash,10,'EXECUTOR_CONTINUE_HELD'))
        self.assertEqual((plan.allowed_step,plan.step_sequence),('ENABLE_RADIUS',3))
        self.assertEqual(self.plan().next_step_id,plan.next_step_id)
        self.assertEqual(NextStepPlan.model_validate_json(plan.model_dump_json()).plan_hash(),plan.plan_hash())
        self.assertFalse(plan.provider_dispatch)
        for change in ({'contract_version':'LIVE'},{'expected_state':'CONTINUE_HELD'},{'allowed_step':'FENCE_LOCAL'}):
            with self.assertRaises(ValidationError):
                NextStepPlan(**{**plan.model_dump(),**change})
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_existing_execution_authority_registry_and_atomic_engine_are_reused(self):
        before=self.unit.snapshot()
        with self.assertRaises(PermissionError):
            self.issue(authority=self.authority)  # CONTINUE policy authority is not execution authority.
        with self.assertRaises(PermissionError):
            self.issue(authority=self.execution_authority.model_copy(update={'can_issue':False}))
        self.assertEqual(before,self.unit.snapshot())
        grant=self.issue()
        self.assertIsInstance(grant,NextStepExecutionAuthorization)
        self.assertEqual(grant.version,'NEXT_STEP_EXECUTION_AUTHORIZATION_V1_FIXTURE')
        self.assertEqual(self.unit.snapshot()['execution_authorizations'][grant.authorization_id],grant)
        self.assertFalse(any(key.startswith('next_step_') for key in self.unit.snapshot()))
        before=self.unit.snapshot()
        with self.assertRaises(PermissionError):
            self.next.stage(self.request,self.scope,self.execution_authority.model_copy(update={'can_stage':False}),grant,permission=True)
        self.assertEqual(before,self.unit.snapshot())

    def test_staging_is_atomic_and_preserves_unknown_and_decision_history_without_dispatch(self):
        original=self.unit.snapshot()
        provider=self.provider.snapshot()
        grant=self.issue()
        record=self.stage(grant)
        state=self.unit.snapshot()
        self.assertEqual(next(iter(state['journal'].values())).state,'NEXT_STEP_EXECUTION_STAGED')
        self.assertEqual(next(iter(state['owners'].values())).revision,11)
        self.assertEqual(next(iter(state['owners'].values())).active_request,self.request.request_id)
        self.assertEqual(record.state,'NEXT_STEP_EXECUTION_STAGED')
        self.assertEqual(record.previous_execution_id,self.command.execution_id)
        self.assertEqual(record.next_step_id,grant.plan.next_step_id)
        self.assertEqual(state['executor_accepted'],original['executor_accepted'])
        self.assertEqual(state['executor_decision_records'],original['executor_decision_records'])
        self.assertEqual(state['executor_policy_records'],original['executor_policy_records'])
        self.assertEqual(next(iter(state['outbox'].values()))[-1].step,'NEXT_STEP_STAGE:ENABLE_RADIUS')
        self.assertFalse(any(e.status=='PENDING' for e in next(iter(state['outbox'].values()))))
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request,self.scope,self.worker,Claim(attempt_id=UUID(int=99)),permission=True)
        self.assertEqual(state,self.unit.snapshot())
        self.assertEqual(provider,self.provider.snapshot())

    def test_only_immediate_next_step_is_allowed_and_final_step_has_no_successor(self):
        with self.assertRaisesRegex(AtomicConflict,'WRONG_NEXT_STEP'):
            self.plan('COMMIT_OWNER_CAS')
        self.build_continue(prefix=2)
        plan=self.plan('COMMIT_OWNER_CAS')
        self.assertEqual(plan.step_sequence,4)
        provider=self.provider.snapshot()
        self.stage(self.issue(plan))
        self.assertEqual(provider,self.provider.snapshot())
        self.build_continue(prefix=3)
        with self.assertRaisesRegex(AtomicConflict,'NO_REMAINING_STEP'):
            self.plan('COMMIT_OWNER_CAS')

    def test_cancelled_policy_or_confirmed_rejection_never_skip_retry_into_next_step(self):
        for outcome,kind in (('SUCCESS','CANCEL'),('REJECTED','CONTINUE')):
            self.build_continue(outcome=outcome,kind=kind)
            before=self.unit.snapshot(),self.provider.snapshot()
            with self.assertRaisesRegex(AtomicConflict,'READ_ONLY_RECONCILIATION_REQUIRED'):
                self.plan()
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_wrong_scope_hash_step_id_previous_execution_and_evidence_fail_closed(self):
        plan=self.plan()
        for change in ({'tenant_id':'other'},{'subscriber_id':'demo-sub-other'},{'previous_execution_id':UUID(int=99)},
                       {'decision_id':UUID(int=99)},{'continue_plan_hash':'0'*64},{'next_step_id':UUID(int=99)},
                       {'evidence_fingerprint':'0'*64},{'owner_revision':1},{'allowed_step':'COMMIT_OWNER_CAS'}):
            before=self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(plan.model_copy(update=change))
            self.assertEqual(before,self.unit.snapshot())

    def test_expired_duplicate_and_wrong_version_authorization_are_rejected(self):
        grant=self.issue(seconds=2)
        before=self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.issue()
        with self.assertRaises(AtomicConflict):
            self.stage(grant.model_copy(update={'version':'EXECUTION_AUTHORIZATION_V1_FIXTURE'}))
        self.clock.advance(2)
        with self.assertRaisesRegex(AtomicConflict,'AUTHORIZATION_EXPIRED'):
            self.stage(grant)
        self.assertEqual(before,self.unit.snapshot())
        fresh=self.issue(number=2)
        self.stage(fresh)
        before=self.unit.snapshot()
        with self.assertRaisesRegex(AtomicConflict,'AUTHORIZATION_ALREADY_USED'):
            self.stage(fresh)
        self.assertEqual(before,self.unit.snapshot())

    def test_changed_provider_evidence_and_stale_cas_fencing_leave_grant_unconsumed(self):
        grant=self.issue()
        original=self.unit.snapshot()
        for table,field in (('owners','revision'),('owners','fence'),('journal','revision'),('leases','token')):
            key,value=next(iter(self.unit._state[table].items()))
            self.unit._state[table][key]=value.model_copy(update={field:getattr(value,field)+1})
            before=self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.stage(grant)
            self.assertEqual(before,self.unit.snapshot())
            self.unit._state=deepcopy(original)
        provider=self.provider.snapshot()
        self.provider._state['provider']=provider['provider'].model_copy(update={'generation':999})
        before=self.unit.snapshot(),self.provider.snapshot()
        with self.assertRaisesRegex(AtomicConflict,'READ_ONLY_RECONCILIATION_REQUIRED'):
            self.stage(grant)
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_concurrent_authorizations_for_same_next_step_have_one_cas_winner(self):
        grants=[self.issue(number=1),self.issue(number=2)]
        def compete(grant):
            try:
                self.stage(grant)
                return 'WIN'
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete,grants)),['WIN','CONFLICT'])
        state=self.unit.snapshot()
        self.assertEqual(sum(type(r).__name__=='NextStepExecutionRecord' for r in state['execution_records'].values()),1)
        self.assertEqual(next(iter(state['owners'].values())).revision,11)

    def test_every_partial_commit_fault_restores_grant_cas_journal_audit_outbox_and_lease(self):
        grant=self.issue()
        before=self.unit.snapshot(),self.provider.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.subTest(fault=fault),self.assertRaises(AtomicConflict):
                self.stage(grant,fail_at=fault)
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
        self.stage(grant)
