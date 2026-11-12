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


class ExecutorPolicyTests(TestCase):
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
        self.build_decision()
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

    def plan(self, kind='CONTINUE'):
        return self.policy.plan(self.request, self.scope, self.decision.authorization_id, kind, permission=True)

    def issue(self, plan=None, number=1, seconds=30, authority=None):
        return self.policy.issue(self.request, self.scope, authority or self.authority, plan or self.plan(),
                                 ExecutorPolicyIntent(authorization_id=UUID(int=number), seconds=seconds), permission=True)

    def apply(self, grant, **kwargs):
        return self.policy.apply(self.request, self.scope, self.authority, grant, permission=True, **kwargs)

    def test_canonical_separate_versions_bind_execution_decision_hash_evidence_and_current_owner(self):
        before = self.unit.snapshot(), self.provider.snapshot()
        go, stop = self.plan(), self.plan('CANCEL')
        self.assertIsInstance(go, ExecutorContinuePlan)
        self.assertIsInstance(stop, ExecutorCancelPlan)
        self.assertNotEqual(go.plan_hash(), stop.plan_hash())
        self.assertEqual(ExecutorContinuePlan.model_validate_json(go.model_dump_json()).plan_hash(), go.plan_hash())
        self.assertEqual((go.execution_id, go.decision_id, go.previous_plan_hash, go.owner_revision, go.expected_state),
            (self.command.execution_id, self.decision.authorization_id, self.command.plan_hash, 9, 'EXECUTOR_DECISION_RECORDED'))
        self.assertEqual(go.evidence_fingerprint, self.decision.evaluation.evidence_fingerprint)
        self.assertFalse(go.automatic_dispatch)
        with self.assertRaises(ValidationError):
            ExecutorContinuePlan(**{**go.model_dump(), 'contract_version': 'LIVE'})
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))

    def test_continue_and_cancel_have_separate_permissions_at_issue_and_apply(self):
        for kind, flag in (('CONTINUE','can_continue'),('CANCEL','can_cancel')):
            plan = self.plan(kind)
            denied = self.authority.model_copy(update={flag: False})
            before = self.unit.snapshot()
            with self.assertRaises(PermissionError):
                self.issue(plan, authority=denied)
            self.assertEqual(before, self.unit.snapshot())
            grant = self.issue(plan, number=1 if kind=='CONTINUE' else 2)
            before = self.unit.snapshot()
            with self.assertRaises(PermissionError):
                self.policy.apply(self.request,self.scope,denied,grant,permission=True)
            self.assertEqual(before, self.unit.snapshot())

    def test_continue_is_atomic_held_and_cannot_dispatch_or_change_original_unknown_receipt(self):
        unknown = self.unit.snapshot()['executor_accepted'][self.command.execution_id]
        provider = self.provider.snapshot()
        record = self.apply(self.issue())
        state = self.unit.snapshot()
        self.assertEqual(record.state,'EXECUTOR_CONTINUE_HELD')
        self.assertEqual(next(iter(state['owners'].values())).revision,10)
        self.assertEqual(next(iter(state['owners'].values())).active_request,self.request.request_id)
        self.assertEqual(state['executor_accepted'][self.command.execution_id],unknown)
        self.assertEqual(unknown.receipt.outcome,'UNKNOWN')
        self.assertFalse(any(e.status=='PENDING' for e in next(iter(state['outbox'].values()))))
        self.assertEqual(next(iter(state['outbox'].values()))[-1].status,'HELD')
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request,self.scope,self.worker,Claim(attempt_id=UUID(int=99)),permission=True)
        self.assertEqual(state,self.unit.snapshot())
        self.assertEqual(provider,self.provider.snapshot())

    def test_cancel_preserves_applied_provider_effect_and_unknown_receipt(self):
        self.build_decision(prefix=2)
        unknown=self.unit.snapshot()['executor_accepted'][self.command.execution_id]
        provider=self.provider.snapshot()
        self.assertEqual(provider['provider'].radius_state,'ENABLED')
        record=self.apply(self.issue(self.plan('CANCEL')))
        self.assertEqual(record.state,'EXECUTOR_CANCELLED_HELD')
        self.assertFalse(record.external_effects_reversed)
        self.assertEqual(provider,self.provider.snapshot())
        self.assertEqual(self.unit.snapshot()['executor_accepted'][self.command.execution_id],unknown)
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request,self.scope,self.worker,Claim(attempt_id=UUID(int=99)),permission=True)

    def test_wrong_scope_hash_decision_execution_evidence_and_grant_substitution_fail_closed(self):
        plan=self.plan()
        for change in ({'tenant_id':'other'},{'subscriber_id':'demo-sub-other'},{'execution_id':UUID(int=99)},
                       {'decision_id':UUID(int=99)},{'previous_plan_hash':'0'*64},{'evidence_fingerprint':'0'*64},
                       {'owner_revision':10}):
            before=self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(plan.model_copy(update=change))
            self.assertEqual(before,self.unit.snapshot())
        grant=self.issue()
        before=self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.apply(grant.model_copy(update={'plan':self.plan('CANCEL')}))
        with self.assertRaises(PermissionError):
            self.issue(number=2,authority=self.authority.model_copy(update={'environment':'PRODUCTION'}))
        self.assertEqual(before,self.unit.snapshot())

    def test_expiry_reissue_and_consumed_duplicate_are_rejected(self):
        grant=self.issue(seconds=2)
        before=self.unit.snapshot()
        with self.assertRaises(ExecutorPolicyConflict):
            self.issue()
        self.clock.advance(2)
        with self.assertRaisesRegex(ExecutorPolicyConflict,'AUTHORIZATION_EXPIRED'):
            self.apply(grant)
        self.assertEqual(before,self.unit.snapshot())
        fresh=self.issue(number=2)
        self.apply(fresh)
        before=self.unit.snapshot()
        with self.assertRaisesRegex(ExecutorPolicyConflict,'AUTHORIZATION_ALREADY_USED'):
            self.apply(fresh)
        self.assertEqual(before,self.unit.snapshot())

    def test_continue_cancel_race_has_one_cas_winner(self):
        grants=[self.issue(self.plan(),number=1),self.issue(self.plan('CANCEL'),number=2)]
        def compete(grant):
            try:
                return self.apply(grant).kind
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(compete,grants))
        self.assertEqual(results.count('CONFLICT'),1)
        state=self.unit.snapshot()
        self.assertEqual(len(state['executor_policy_records']),1)
        self.assertEqual(next(iter(state['owners'].values())).revision,10)
        self.assertEqual(sum(r[3]=='CONSUMED' for r in state['executor_policy_audit']),1)

    def test_stale_owner_journal_or_fence_leaves_authorization_unconsumed(self):
        grant=self.issue()
        original=self.unit.snapshot()
        for table,field in (('owners','revision'),('owners','fence'),('journal','revision'),('leases','token')):
            key,value=next(iter(self.unit._state[table].items()))
            self.unit._state[table][key]=value.model_copy(update={field:getattr(value,field)+1})
            before=self.unit.snapshot()
            with self.assertRaisesRegex(AtomicConflict,'READ_ONLY_RECONCILIATION_REQUIRED'):
                self.apply(grant)
            self.assertEqual(before,self.unit.snapshot())
            self.assertFalse(before['executor_policy_records'])
            self.unit._state=deepcopy(original)

    def test_changed_missing_or_contradictory_provider_evidence_is_readonly(self):
        grant=self.issue()
        original=self.provider.snapshot()
        for change in ('MISSING','UNKNOWN','DRIFT'):
            if change=='MISSING':
                del self.provider._state['executor_receipts'][self.command.execution_id]
            elif change=='UNKNOWN':
                receipt=self.provider._state['executor_receipts'][self.command.execution_id]
                self.provider._state['executor_receipts'][self.command.execution_id]=receipt.model_copy(update={'outcome':'UNKNOWN'})
            else:
                current=self.provider._state['provider']
                self.provider._state['provider']=current.model_copy(update={'generation':999})
            before=self.unit.snapshot(),self.provider.snapshot()
            with self.assertRaisesRegex(AtomicConflict,'READ_ONLY_RECONCILIATION_REQUIRED'):
                self.apply(grant)
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
            self.provider._state=deepcopy(original)

    def test_fault_injection_rolls_back_owner_journal_audit_outbox_lease_and_grant_consumption(self):
        grant=self.issue()
        before=self.unit.snapshot(),self.provider.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.subTest(fault=fault),self.assertRaises(AtomicConflict):
                self.apply(grant,fail_at=fault)
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
        self.apply(grant)

    def test_confirmed_rejection_can_only_enter_a_held_policy_not_automatic_retry(self):
        self.build_decision(outcome='REJECTED')
        self.assertEqual(self.decision.decision,'CONFIRM_REJECTION')
        provider=self.provider.snapshot()
        unknown=self.unit.snapshot()['executor_accepted'][self.command.execution_id]
        record=self.apply(self.issue())
        self.assertEqual(record.state,'EXECUTOR_CONTINUE_HELD')
        self.assertEqual(self.provider.snapshot(),provider)
        self.assertEqual(self.unit.snapshot()['executor_accepted'][self.command.execution_id],unknown)
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request,self.scope,self.worker,Claim(attempt_id=UUID(int=99)),permission=True)
