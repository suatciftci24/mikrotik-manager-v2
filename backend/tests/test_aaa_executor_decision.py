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


class ExecutorUnknownDecisionTests(TestCase):
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
        self.build_unknown()
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

    def evaluate(self, context=None):
        return self.service.evaluate(self.request, self.scope, context or self.context,
                                     self.command.execution_id, permission=True)

    def issue(self, evaluation=None, number=1, decision='CONFIRM_SUCCESS', seconds=30, context=None):
        return self.service.issue(self.request, self.scope, context or self.context, evaluation or self.evaluate(),
            ExecutorDecisionIntent(authorization_id=UUID(int=number), decision=decision, seconds=seconds), permission=True)

    def apply(self, grant, **kwargs):
        return self.service.apply(self.request, self.scope, self.context, grant, permission=True, **kwargs)

    def test_evaluation_is_versioned_bound_and_readonly_without_decision_or_execution_authority(self):
        before = self.unit.snapshot(), self.provider.snapshot()
        evaluation = self.evaluate()
        self.assertEqual(evaluation.status, 'CONFIRMED_SUCCESS')
        for field in ('execution_id', 'event_id', 'attempt_id', 'plan_hash', 'fencing_token'):
            self.assertEqual(getattr(evaluation, field), getattr(self.command, field))
        self.assertEqual(evaluation.owner_revision, 8)
        self.assertFalse(evaluation.decision_authority)
        self.assertFalse(evaluation.automatic_dispatch)
        self.assertEqual(EvidenceEvaluation.model_validate_json(evaluation.model_dump_json()), evaluation)
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        with self.assertRaises(ValidationError):
            EvidenceEvaluation(**{**evaluation.model_dump(), 'decision_authority': True})
        readonly = self.context.model_copy(update={'can_issue_decision': False, 'can_apply_decision': False})
        self.assertEqual(self.evaluate(readonly).status, 'CONFIRMED_SUCCESS')
        with self.assertRaises(PermissionError):
            self.issue(evaluation, context=readonly)

    def test_missing_unknown_or_unverifiable_independent_provider_source_keeps_readonly_state(self):
        for outcome, crash in (('SUCCESS', 'AFTER_DISPATCH'), ('UNKNOWN', 'AFTER_EFFECT'), ('APPLY_THEN_UNKNOWN', 'AFTER_EFFECT')):
            self.build_unknown(outcome, crash)
            before = self.unit.snapshot(), self.provider.snapshot()
            evaluation = self.evaluate()
            self.assertEqual(evaluation.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
            with self.assertRaises(ExecutorDecisionConflict):
                self.issue(evaluation)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.provider._state['executor_receipts'][self.command.execution_id] = {'untrusted': 'caller proof'}
        self.assertEqual(self.evaluate().status, 'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_rejection_requires_definitive_provider_receipt_and_cannot_be_assumed_from_absence(self):
        self.build_unknown('REJECTED')
        evaluation = self.evaluate()
        self.assertEqual(evaluation.status, 'CONFIRMED_REJECTION')
        before = self.unit.snapshot()
        with self.assertRaises(ExecutorDecisionConflict):
            self.issue(evaluation, decision='CONFIRM_SUCCESS')
        self.assertEqual(before, self.unit.snapshot())
        record = self.apply(self.issue(evaluation, decision='CONFIRM_REJECTION'))
        self.assertEqual(record.decision, 'CONFIRM_REJECTION')
        event = next(e for e in next(iter(self.unit.snapshot()['outbox'].values())) if e.event_id == self.command.event_id)
        self.assertEqual((event.status, event.result), ('CANCELLED', 'NOT_APPLIED'))

    def test_conflicting_attempt_hash_or_provider_state_is_not_trusted(self):
        original = self.provider.snapshot()
        known = original['executor_receipts'][self.command.execution_id]
        for change in ({'attempt_id': UUID(int=99)}, {'event_id': UUID(int=99)}, {'plan_hash': '0' * 64},
                       {'fencing_token': 1}, {'provider_evidence_fingerprint': '0' * 64}):
            self.provider._state['executor_receipts'][self.command.execution_id] = known.model_copy(update=change)
            self.assertEqual(self.evaluate().status, 'READ_ONLY_RECONCILIATION_REQUIRED')
            self.provider._state = deepcopy(original)
        self.provider._state['provider'] = original['provider'].model_copy(update={'generation': 999})
        self.assertEqual(self.evaluate().status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        self.provider._state = deepcopy(original)
        self.provider._state['highest'] = (self.command.owner_fence, self.command.fencing_token + 1)
        self.assertEqual(self.evaluate().status, 'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_issue_and_apply_permissions_are_distinct_and_fixture_only(self):
        with self.assertRaises(PermissionError):
            self.evaluate(self.context.model_copy(update={'can_evaluate': False}))
        grant = self.issue()
        before = self.unit.snapshot()
        with self.assertRaises(PermissionError):
            self.service.apply(self.request, self.scope, self.context.model_copy(update={'can_apply_decision': False}), grant, permission=True)
        with self.assertRaises(PermissionError):
            self.service.apply(self.request, self.scope, self.context.model_copy(update={'environment': 'PRODUCTION'}), grant, permission=True)
        self.assertEqual(before, self.unit.snapshot())

    def test_wrong_scope_or_client_modified_evaluation_and_authorization_are_rejected(self):
        evaluation = self.evaluate()
        for change in ({'tenant_id': 'other'}, {'subscriber_id': 'demo-sub-other'}, {'execution_id': UUID(int=99)},
                       {'evidence_fingerprint': '0' * 64}, {'plan_hash': '0' * 64}, {'owner_revision': 1}):
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(evaluation.model_copy(update=change))
            self.assertEqual(before, self.unit.snapshot())
        grant = self.issue(evaluation)
        before = self.unit.snapshot()
        with self.assertRaises(ExecutorDecisionConflict):
            self.apply(grant.model_copy(update={'decision': 'CONFIRM_REJECTION'}))
        with self.assertRaises(PermissionError):
            self.evaluate(self.context.model_copy(update={'tenant_id': 'other'}))
        self.assertEqual(before, self.unit.snapshot())

    def test_expired_authorization_is_not_reusable_or_renewed_implicitly(self):
        grant = self.issue(seconds=2)
        before = self.unit.snapshot()
        with self.assertRaises(ExecutorDecisionConflict):
            self.issue()
        self.clock.advance(2)
        with self.assertRaisesRegex(ExecutorDecisionConflict, 'AUTHORIZATION_EXPIRED'):
            self.apply(grant)
        self.assertEqual(before, self.unit.snapshot())

    def test_authorized_decision_is_atomic_holds_owner_and_never_dispatches(self):
        grant = self.issue()
        provider = self.provider.snapshot()
        record = self.apply(grant)
        state = self.unit.snapshot()
        self.assertEqual(record.state, 'EXECUTOR_DECISION_RECORDED')
        self.assertEqual(next(iter(state['owners'].values())).revision, 9)
        self.assertEqual(next(iter(state['owners'].values())).active_request, self.request.request_id)
        self.assertEqual(state['executor_accepted'][self.command.execution_id].receipt.outcome, 'UNKNOWN')
        self.assertFalse(any(e.status == 'PENDING' for e in next(iter(state['outbox'].values()))))
        self.assertEqual(next(iter(state['outbox'].values()))[-1].status, 'HELD')
        self.assertEqual(state['audit'][-1][6], 'EXECUTOR_DECISION_RECORDED')
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=99)), permission=True)
        self.assertEqual(state, self.unit.snapshot())
        self.assertEqual(provider, self.provider.snapshot())

    def test_concurrent_duplicate_decisions_have_one_cas_winner_and_one_consumed_grant(self):
        grant = self.issue()
        def compete(_):
            try:
                self.apply(grant)
                return 'WIN'
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete, range(2))), ['WIN', 'CONFLICT'])
        before = self.unit.snapshot()
        with self.assertRaisesRegex(ExecutorDecisionConflict, 'AUTHORIZATION_ALREADY_USED'):
            self.apply(grant)
        self.assertEqual(before, self.unit.snapshot())
        self.assertEqual(sum(r[2] == 'CONSUMED' for r in before['executor_decision_audit']), 1)

    def test_stale_cas_fencing_changed_evidence_and_partial_commit_do_not_consume_grant(self):
        grant = self.issue()
        original = self.unit.snapshot()
        for table, field in (('owners', 'revision'), ('owners', 'fence'), ('journal', 'revision'), ('leases', 'token')):
            key, value = next(iter(self.unit._state[table].items()))
            self.unit._state[table][key] = value.model_copy(update={field: getattr(value, field) + 1})
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.apply(grant)
            self.assertEqual(before, self.unit.snapshot())
            self.unit._state = deepcopy(original)
        provider = self.provider.snapshot()
        self.provider._state['provider'] = provider['provider'].model_copy(update={'generation': 999})
        before = self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.apply(grant)
        self.assertEqual(before, self.unit.snapshot())
        self.provider._state = provider
        for fault in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX', 'AUTHORIZATION'):
            before = self.unit.snapshot(), self.provider.snapshot()
            with self.assertRaises(AtomicConflict):
                self.apply(grant, fail_at=fault)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.apply(grant)

    def test_unverifiable_prefix_and_all_executor_steps_use_the_same_definitive_evidence_rules(self):
        self.build_unknown()
        key = next(iter(self.provider._state['receipts']))
        self.provider._state['receipts'][key] = {'untrusted': 'prefix'}
        before = self.unit.snapshot(), self.provider.snapshot()
        self.assertEqual(self.evaluate().status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        for prefix in (2, 3):
            self.build_unknown(prefix=prefix)
            before = self.unit.snapshot(), self.provider.snapshot()
            self.assertEqual(self.evaluate().status, 'CONFIRMED_SUCCESS')
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))

    def test_copied_provider_receipt_from_unbound_instance_is_not_independent_trusted_evidence(self):
        self.assertEqual(self.evaluate().status, 'CONFIRMED_SUCCESS')
        replacement = FakeFencedProvider(self.root)
        replacement._state = self.provider.snapshot()  # Even byte-for-byte copied facts are not this execution's reader.
        foreign = ExecutorReconciliationService(self.unit, replacement)
        before = self.unit.snapshot(), replacement.snapshot()
        evaluation = foreign.evaluate(self.request, self.scope, self.context, self.command.execution_id, permission=True)
        self.assertEqual(evaluation.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        with self.assertRaises(ExecutorDecisionConflict):
            foreign.issue(self.request, self.scope, self.context, evaluation,
                          ExecutorDecisionIntent(authorization_id=UUID(int=99), decision='CONFIRM_SUCCESS'), permission=True)
        self.assertEqual(before, (self.unit.snapshot(), replacement.snapshot()))
