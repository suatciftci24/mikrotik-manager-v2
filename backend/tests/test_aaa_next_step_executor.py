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


from app.simulation.aaa_executor import ExecutorReceipt, ReceiptAcceptance, ExecutorConflict

class NextStepExecutorTests(TestCase):

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

    def prepare(self, prefix=1, outcome='SUCCESS'):
        self.build_continue(prefix=prefix)
        self.staged = self.stage(self.issue(plan=self.plan(self.root.steps[prefix+1]), number=4100))
        self.executor = FixtureExecutor(self.unit, self.provider, outcome=outcome)
        self.runner = ExecutorContext(tenant_id=self.root.tenant_id,worker_id='next-executor',
            can_execute=True,can_accept=True,can_record_timeout=True)
        self.history = {k:deepcopy(self.unit.snapshot()[k]) for k in
            ('executor_accepted','executor_decision_records','executor_decision_authorizations',
             'executor_policy_records','executor_policy_authorizations')}

    def claim_next(self, attempt=4200, seconds=30):
        return self.executor.claim(self.request,self.scope,self.runner,self.staged.authorization_id,
            AttemptIntent(attempt_id=UUID(int=attempt),seconds=seconds),permission=True)

    def run_next(self, command, **kwargs):
        return self.executor.run(self.request,self.scope,self.runner,command,permission=True,**kwargs)

    def accept_next(self, receipt, **kwargs):
        return self.executor.accept(self.request,self.scope,self.runner,receipt,permission=True,**kwargs)

    def timeout_next(self, command, **kwargs):
        return self.executor.timeout(self.request,self.scope,self.runner,command,permission=True,**kwargs)

    def assert_history(self):
        state=self.unit.snapshot()
        for name, original in self.history.items():
            for key,value in original.items():
                self.assertEqual(state[name][key],value)

    def test_existing_executor_and_receipt_run_next_enable_once_and_preserve_history(self):
        self.prepare()
        command=self.claim_next()
        generation=self.provider.snapshot()['provider'].generation
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts=list(pool.map(lambda _: self.run_next(command),range(2)))
        self.assertEqual(receipts[0],receipts[1])
        receipt=receipts[0]
        self.assertIs(type(receipt),ExecutorReceipt)
        self.assertEqual(receipt.receipt_version,'AAA_EXECUTOR_RECEIPT_V1_FIXTURE')
        self.assertEqual(ExecutorReceipt.model_validate_json(receipt.model_dump_json()),receipt)
        self.assertEqual(receipt.allowed_step,'ENABLE_RADIUS')
        self.assertEqual(self.provider.snapshot()['provider'].generation,generation+1)
        self.assertEqual(self.provider.snapshot()['provider'].radius_state,'ENABLED')
        accepted=self.accept_next(receipt)
        self.assertEqual(accepted.state,'FIXTURE_STEP_SUCCEEDED')
        self.assertFalse(accepted.reconciliation_required)
        self.assert_history()
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request,self.scope,self.worker,Claim(attempt_id=UUID(int=99)),permission=True)

    def test_next_commit_owner_success_requires_enabled_provider_and_cas(self):
        self.prepare(prefix=2)
        before=self.provider.snapshot()['provider']
        receipt=self.run_next(self.claim_next())
        self.assertEqual(receipt.allowed_step,'COMMIT_OWNER_CAS')
        result=self.accept_next(receipt)
        owner=next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual(owner.authority,'RADIUS')
        self.assertIsNone(owner.active_request)
        self.assertEqual(result.owner_revision,12)
        self.assertEqual(before,self.provider.snapshot()['provider'])
        self.assert_history()

    def test_rejection_does_not_commit_owner_restore_effects_or_claim_success(self):
        for prefix in (1,2):
            with self.subTest(prefix=prefix):
                self.prepare(prefix=prefix,outcome='REJECTED')
                provider=self.provider.snapshot()['provider']
                result=self.accept_next(self.run_next(self.claim_next()))
                self.assertEqual(result.state,'FIXTURE_STEP_REJECTED')
                self.assertFalse(result.reconciliation_required)
                owner=next(iter(self.unit.snapshot()['owners'].values()))
                self.assertEqual(owner.authority,'LOCAL')
                self.assertEqual(owner.active_request,self.request.request_id)
                self.assertEqual(provider,self.provider.snapshot()['provider'])
                self.assertFalse(provider.local_enabled)
                self.assert_history()

    def test_duplicate_receipt_is_idempotent_but_conflicting_repeat_is_rejected(self):
        self.prepare()
        receipt=self.run_next(self.claim_next())
        accepted=self.accept_next(receipt)
        before=self.unit.snapshot(),self.provider.snapshot()
        self.assertEqual(self.accept_next(receipt),accepted)
        for change in ({'outcome':'REJECTED'},{'provider_evidence_fingerprint':'0'*64},
                       {'attempt_id':UUID(int=99)},{'event_id':UUID(int=99)}):
            with self.assertRaises(AtomicConflict):
                self.accept_next(receipt.model_copy(update=change))
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_wrong_attempt_step_event_hash_revision_token_and_worker_fail_closed(self):
        self.prepare()
        command=self.claim_next()
        before=self.unit.snapshot(),self.provider.snapshot()
        for change in ({'attempt_id':UUID(int=99)},{'event_id':UUID(int=99)},
                       {'plan_hash':'0'*64},{'allowed_step':'COMMIT_OWNER_CAS'},
                       {'owner_revision':1},{'fencing_token':1}):
            with self.assertRaises(AtomicConflict):
                self.run_next(command.model_copy(update=change))
        with self.assertRaises(AtomicConflict):
            self.executor.run(self.request,self.scope,self.runner.model_copy(update={'worker_id':'foreign'}),
                command,permission=True)
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_stale_cas_fencing_and_tampered_staging_reject_before_fake_effect(self):
        for kind in ('OWNER','TOKEN','EVENT','AUTH','HISTORY','PROVIDER'):
            with self.subTest(kind=kind):
                self.prepare()
                command=self.claim_next()
                key=next(iter(self.unit._state['journal']))
                owner_key=next(iter(self.unit._state['owners']))
                if kind=='OWNER':
                    owner=self.unit._state['owners'][owner_key]
                    self.unit._state['owners'][owner_key]=owner.model_copy(update={'revision':owner.revision+1})
                elif kind=='TOKEN':
                    lease=self.unit._state['leases'][key]
                    self.unit._state['leases'][key]=lease.model_copy(update={'token':lease.token+1})
                elif kind=='EVENT':
                    events=self.unit._state['outbox'][key]
                    self.unit._state['outbox'][key]=events[:-1]+(events[-1].model_copy(update={'step':'WRONG'}),)
                elif kind=='AUTH':
                    del self.unit._state['execution_authorizations'][self.staged.authorization_id]
                elif kind=='HISTORY':
                    del self.unit._state['executor_decision_records'][self.decision.authorization_id]
                else:
                    current=self.provider._state['provider']
                    self.provider._state['provider']=current.model_copy(update={'generation':current.generation+1})
                before=self.unit.snapshot(),self.provider.snapshot()
                with self.assertRaises(AtomicConflict):
                    self.run_next(command)
                self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_receipt_cas_conflict_preserves_unconsumed_attempt_and_provider_effect(self):
        self.prepare()
        receipt=self.run_next(self.claim_next())
        key=next(iter(self.unit._state['owners']))
        owner=self.unit._state['owners'][key]
        self.unit._state['owners'][key]=owner.model_copy(update={'revision':owner.revision+1})
        before=self.unit.snapshot(),self.provider.snapshot()
        with self.assertRaises(AtomicConflict):
            self.accept_next(receipt)
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
        self.assertNotIn(receipt.execution_id,self.unit.snapshot()['executor_accepted'])

    def test_five_partial_commit_boundaries_leave_no_partial_receipt_consumption(self):
        self.prepare()
        receipt=self.run_next(self.claim_next())
        before=self.unit.snapshot(),self.provider.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.subTest(fault=fault),self.assertRaises(AtomicConflict):
                self.accept_next(receipt,fail_at=fault)
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
        self.assertEqual(self.accept_next(receipt).state,'FIXTURE_STEP_SUCCEEDED')
        self.assert_history()

    def test_unknown_receipt_has_versioned_readonly_lineage_without_automatic_decision(self):
        for outcome in ('UNKNOWN','APPLY_THEN_UNKNOWN'):
            self.prepare(outcome=outcome)
            command=self.claim_next()
            accepted=self.accept_next(self.run_next(command))
            self.assertEqual(accepted.state,'FIXTURE_STEP_UNKNOWN')
            ref=accepted.reconciliation_reference
            self.assertEqual(ref.version,'NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE')
            self.assertEqual(ref.previous_execution_id,self.command.execution_id)
            self.assertEqual(ref.decision_id,self.decision.authorization_id)
            self.assertEqual(ref.event_id,command.event_id)
            self.assertEqual(ref.attempt_id,command.attempt_id)
            self.assertEqual(ref.plan_hash,command.plan_hash)
            self.assertEqual(ref.fencing_token,command.fencing_token)
            self.assertEqual(ref.owner_revision,accepted.owner_revision)
            self.assertFalse(ref.decision_authorized)
            self.assertEqual(ReceiptAcceptance.model_validate_json(accepted.model_dump_json()),accepted)
            before=self.unit.snapshot(),self.provider.snapshot()
            evidence=self.executor.unknown_evidence(self.request,self.scope,self.runner,command.execution_id,permission=True)
            self.assertEqual(evidence['accepted'],accepted)
            evaluation=self.service.evaluate(self.request,self.scope,self.context,command.execution_id,permission=True)
            self.assertEqual(evaluation.status,'READ_ONLY_RECONCILIATION_REQUIRED')
            with self.assertRaises(AtomicConflict):
                self.run_next(command)
            with self.assertRaises(AtomicConflict):
                self.unit.claim(self.request,self.scope,self.worker,Claim(attempt_id=UUID(int=99)),permission=True)
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
            self.assert_history()

    def test_crash_or_lost_response_stays_unknown_and_late_receipt_cannot_replace_it(self):
        for crash in ('AFTER_DISPATCH','AFTER_EFFECT'):
            self.prepare()
            command=self.claim_next(seconds=2)
            with self.assertRaises(FixtureCrash):
                self.run_next(command,crash=crash)
            self.clock.advance(2)
            accepted=self.timeout_next(command)
            self.assertEqual(accepted.receipt.outcome,'UNKNOWN')
            self.assertIsNotNone(accepted.reconciliation_reference)
            before=self.unit.snapshot(),self.provider.snapshot()
            self.assertEqual(self.timeout_next(command),accepted)
            known=self.provider.snapshot()['executor_receipts'].get(command.execution_id)
            if known:
                with self.assertRaises(AtomicConflict):
                    self.accept_next(known)
            with self.assertRaises(AtomicConflict):
                self.claim_next(attempt=4201)
            self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
            self.assert_history()

    def test_concurrent_claim_and_acceptance_share_one_attempt_and_consumption(self):
        self.prepare()
        with ThreadPoolExecutor(max_workers=2) as pool:
            commands=list(pool.map(lambda _:self.claim_next(),range(2)))
        self.assertEqual(commands[0],commands[1])
        with self.assertRaises(AtomicConflict):
            self.claim_next(attempt=4201)
        receipt=self.run_next(commands[0])
        with ThreadPoolExecutor(max_workers=2) as pool:
            accepted=list(pool.map(lambda _:self.accept_next(receipt),range(2)))
        self.assertEqual(accepted[0],accepted[1])
        audit=self.unit.snapshot()['executor_audit']
        self.assertEqual(sum(row[:3]==(receipt.execution_id,receipt.attempt_id,'FIXTURE_STEP_SUCCEEDED') for row in audit),1)

    def test_missing_stage_permission_foreign_provider_and_reused_attempt_are_rejected(self):
        self.prepare()
        before=self.unit.snapshot(),self.provider.snapshot()
        with self.assertRaises(PermissionError):
            self.executor.claim(self.request,self.scope,self.runner.model_copy(update={'can_execute':False}),
                self.staged.authorization_id,AttemptIntent(attempt_id=UUID(int=4200)),permission=True)
        with self.assertRaises(AtomicConflict):
            self.claim_next(attempt=2500)
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
        foreign=FakeFencedProvider(self.root)
        foreign._state=deepcopy(self.provider._state)
        other=FixtureExecutor(self.unit,foreign)
        command=self.claim_next()
        before=self.unit.snapshot(),self.provider.snapshot()
        with self.assertRaises(AtomicConflict):
            other.run(self.request,self.scope,self.runner,command,permission=True)
        self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))

    def test_provider_fence_drift_rejects_late_receipt_and_duplicate_without_changes(self):
        for delta in (-1,1):
            for already_accepted in (False,True):
                self.prepare()
                command=self.claim_next()
                receipt=self.run_next(command)
                if already_accepted:
                    self.accept_next(receipt)
                self.provider._state['highest']=(command.owner_fence,command.fencing_token+delta)
                before=self.unit.snapshot(),self.provider.snapshot()
                with self.assertRaises(AtomicConflict):
                    self.accept_next(receipt)
                self.assertEqual(before,(self.unit.snapshot(),self.provider.snapshot()))
