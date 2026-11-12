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
from app.simulation.aaa_executor import FixtureExecutor, ExecutorContext, AttemptIntent, ExecutorReceipt, ExecutorConflict, FixtureCrash


class FixtureExecutorTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.root = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.root, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=1401), correlation_id=UUID(int=1402))
        self.clock = FakeLeaseClock(fixture.clock)
        self.worker = WorkerContext(tenant_id=self.root.tenant_id, worker_id='fixture-worker', can_deliver=True)
        self.context = ExecutorContext(tenant_id=self.root.tenant_id, worker_id='fixture-executor',
                                      can_execute=True, can_accept=True)
        self.coordinator = self.context.model_copy(update={'worker_id': 'timeout-controller', 'can_record_timeout': True})
        self.build_staged()
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def build_staged(self, prefix=1, outcome='SUCCESS'):
        self.unit, self.provider = LeasedMemoryOutbox(self.root, self.clock), FakeFencedProvider(self.root)
        self.unit.reserve(self.request, self.scope, permission=True)
        for index in range(1, prefix + 1):
            lease = self.unit.claim(self.request, self.scope, self.worker,
                Claim(attempt_id=UUID(int=index)), permission=True)
            self.unit.dispatch(self.request, self.scope, self.worker, lease, permission=True)
            command = self.provider.command(self.unit, self.request, self.scope, self.worker, lease, permission=True)
            receipt = self.provider.execute(self.unit, self.request, self.scope, self.worker, lease, command, permission=True)
            if index < prefix:
                accept_provider_response(self.unit, self.provider, self.request, self.scope, self.worker, lease, receipt, permission=True)
        self.unit.nack(self.request, self.scope, self.worker, lease, 'UNKNOWN', permission=True)
        recovery = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=prefix + 1), purpose='RECONCILE'), permission=True)
        service = FixtureDecisionService(self.unit, self.provider)
        authority = FixtureDecisionAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id,
                                              can_issue=True, can_commit=True)
        grant = service.issue(self.request, self.scope, self.worker, recovery, authority,
            DecisionIntent(authorization_id=UUID(int=1500), decision='ACCEPT_APPLIED_EVIDENCE'), permission=True)
        decision = service.commit(self.request, self.scope, self.worker, recovery, authority, grant, permission=True)
        followup = FixtureFollowupService(self.unit, self.provider)
        authority = FixtureFollowupAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id, can_continue=True)
        plan = followup.plan(self.request, self.scope, decision.authorization_id, 'CONTINUE', permission=True)
        grant = followup.issue(self.request, self.scope, authority, plan,
                               FollowupIntent(authorization_id=UUID(int=1600)), permission=True)
        record = followup.commit(self.request, self.scope, authority, grant, permission=True)
        execution = FixtureExecutionService(self.unit, self.provider)
        authority = FixtureExecutionAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id,
                                              can_issue=True, can_stage=True)
        plan = execution.plan(self.request, self.scope, record.authorization_id, self.root.steps[prefix], permission=True)
        grant = execution.issue(self.request, self.scope, authority, plan,
                                ExecutionIntent(authorization_id=UUID(int=1700)), permission=True)
        self.staged = execution.stage(self.request, self.scope, authority, grant, permission=True)
        self.executor = FixtureExecutor(self.unit, self.provider, outcome=outcome)

    def claim(self, attempt=1800, seconds=30):
        return self.executor.claim(self.request, self.scope, self.context, self.staged.authorization_id,
                                   AttemptIntent(attempt_id=UUID(int=attempt), seconds=seconds), permission=True)

    def execute(self, command, **kwargs):
        return self.executor.run(self.request, self.scope, self.context, command, permission=True, **kwargs)

    def accept(self, receipt, **kwargs):
        return self.executor.accept(self.request, self.scope, self.context, receipt, permission=True, **kwargs)

    def timeout(self, command, **kwargs):
        return self.executor.timeout(self.request, self.scope, self.coordinator, command, permission=True, **kwargs)

    def test_versioned_receipt_binds_execution_event_attempt_hash_fence_evidence_and_result(self):
        command = self.claim()
        receipt = self.execute(command)
        self.assertEqual((receipt.execution_id, receipt.event_id, receipt.attempt_id, receipt.plan_hash, receipt.fencing_token),
                         (command.execution_id, command.event_id, command.attempt_id, command.plan_hash, command.fencing_token))
        self.assertEqual(len(receipt.provider_evidence_fingerprint), 64)
        self.assertEqual(receipt.outcome, 'SUCCESS')
        self.assertEqual(ExecutorReceipt.model_validate_json(receipt.model_dump_json()), receipt)
        with self.assertRaises(ValidationError):
            ExecutorReceipt(**{**receipt.model_dump(), 'receipt_version': 'REAL_PROVIDER'})

    def test_wrong_attempt_event_step_hash_revision_and_foreign_worker_cannot_execute(self):
        command = self.claim()
        before = self.unit.snapshot(), self.provider.snapshot()
        for change in ({'attempt_id': UUID(int=99)}, {'event_id': UUID(int=99)}, {'plan_hash': '0' * 64},
                       {'allowed_step': 'ENABLE_RADIUS'}, {'fencing_token': 1}, {'owner_revision': 6}):
            with self.assertRaises(ExecutorConflict):
                self.execute(command.model_copy(update=change))
        with self.assertRaises(ExecutorConflict):
            self.executor.run(self.request, self.scope, self.context.model_copy(update={'worker_id': 'other'}),
                              command, permission=True)
        with self.assertRaises(PermissionError):
            self.executor.run(self.request, self.scope, self.context.model_copy(update={'can_execute': False}),
                              command, permission=True)
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))

    def test_concurrent_repeated_run_has_one_fake_effect_and_same_receipt(self):
        command = self.claim()
        generation = self.provider.snapshot()['provider'].generation
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda _: self.execute(command), range(2)))
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(self.provider.snapshot()['provider'].generation, generation + 1)
        self.assertFalse(self.provider.snapshot()['provider'].local_enabled)
        with self.assertRaises(ExecutorConflict):
            self.claim(attempt=1801)

    def test_receipt_acceptance_is_atomic_and_duplicate_is_idempotent(self):
        receipt = self.execute(self.claim())
        provider = self.provider.snapshot()
        accepted = self.accept(receipt)
        before = self.unit.snapshot()
        self.assertEqual(self.accept(receipt), accepted)
        self.assertEqual(before, self.unit.snapshot())
        self.assertEqual(provider, self.provider.snapshot())
        self.assertEqual(accepted.state, 'FIXTURE_STEP_SUCCEEDED')
        self.assertEqual(next(iter(before['owners'].values())).revision, 8)
        with self.assertRaises(ExecutorConflict):
            self.accept(receipt.model_copy(update={'outcome': 'REJECTED'}))
        self.assertEqual(before, self.unit.snapshot())

    def test_definite_rejection_is_not_unknown_and_does_not_restore_prior_effects(self):
        self.build_staged(prefix=2, outcome='REJECTED')
        before = self.provider.snapshot()['provider']
        accepted = self.accept(self.execute(self.claim()))
        self.assertEqual(accepted.state, 'FIXTURE_STEP_REJECTED')
        self.assertFalse(accepted.reconciliation_required)
        self.assertEqual(self.provider.snapshot()['provider'], before)
        self.assertFalse(before.local_enabled)
        self.assertEqual(before.radius_state, 'DISABLED')

    def test_apply_then_unknown_remains_unknown_without_retry_compensation_or_next_step(self):
        self.build_staged(outcome='APPLY_THEN_UNKNOWN')
        command = self.claim()
        receipt = self.execute(command)
        self.assertFalse(self.provider.snapshot()['provider'].local_enabled)
        self.assertEqual(receipt.outcome, 'UNKNOWN')
        accepted = self.accept(receipt)
        self.assertTrue(accepted.reconciliation_required)
        self.assertEqual(accepted.state, 'FIXTURE_STEP_UNKNOWN')
        before = self.unit.snapshot(), self.provider.snapshot()
        with self.assertRaises(AtomicConflict):
            self.execute(command)
        with self.assertRaisesRegex(AtomicConflict, 'READ_ONLY_RECONCILIATION_REQUIRED'):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=99)), permission=True)
        evidence = self.executor.unknown_evidence(self.request, self.scope, self.coordinator,
                                                 command.execution_id, permission=True)
        self.assertEqual(evidence['accepted'], accepted)
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))

    def test_crash_before_or_after_effect_requires_timeout_and_late_success_is_rejected(self):
        for crash in ('AFTER_DISPATCH', 'AFTER_EFFECT'):
            self.build_staged()
            command = self.claim(seconds=2)
            with self.assertRaises(FixtureCrash):
                self.execute(command, crash=crash)
            with self.assertRaisesRegex(ExecutorConflict, 'READ_ONLY_RECONCILIATION_REQUIRED'):
                self.execute(command)
            self.clock.advance(2)
            with self.assertRaises(PermissionError):
                self.executor.timeout(self.request, self.scope, self.context, command, permission=True)
            unknown = self.timeout(command)
            self.assertEqual(unknown.receipt.outcome, 'UNKNOWN')
            before = self.unit.snapshot(), self.provider.snapshot()
            self.assertEqual(self.timeout(command), unknown)
            known = self.provider.snapshot()['executor_receipts'].get(command.execution_id)
            if known:
                with self.assertRaises(ExecutorConflict):
                    self.accept(known)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))

    def test_cas_or_fencing_drift_rejects_receipt_without_partial_unit_changes(self):
        receipt = self.execute(self.claim())
        original = self.unit.snapshot()
        for table, field in (('owners', 'revision'), ('owners', 'fence'), ('journal', 'revision'), ('leases', 'token')):
            key, value = next(iter(self.unit._state[table].items()))
            self.unit._state[table][key] = value.model_copy(update={field: getattr(value, field) + 1})
            before = self.unit.snapshot(), self.provider.snapshot()
            with self.assertRaises(AtomicConflict):
                self.accept(receipt)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
            self.unit._state = deepcopy(original)

    def test_receipt_commit_faults_do_not_rollback_or_repeat_provider_effect(self):
        command = self.claim()
        receipt = self.execute(command)
        before = self.unit.snapshot(), self.provider.snapshot()
        for stage in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX'):
            with self.assertRaises(AtomicConflict):
                self.accept(receipt, fail_at=stage)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.accept(receipt)
        self.assertEqual(before[1], self.provider.snapshot())

    def test_expired_attempt_and_forged_or_stale_receipt_are_rejected(self):
        command = self.claim(seconds=2)
        receipt = self.execute(command)
        before = self.unit.snapshot()
        for change in ({'provider_evidence_fingerprint': '0' * 64}, {'outcome': 'REJECTED'}, {'event_id': UUID(int=99)}):
            with self.assertRaises(ExecutorConflict):
                self.accept(receipt.model_copy(update=change))
        self.clock.advance(2)
        with self.assertRaises(ExecutorConflict):
            self.accept(receipt)
        self.assertEqual(before, self.unit.snapshot())
        self.assertEqual(self.timeout(command).state, 'FIXTURE_STEP_UNKNOWN')

    def test_final_owner_cas_only_changes_authority_on_success_and_does_not_launch_more_work(self):
        self.build_staged(prefix=3)
        provider = self.provider.snapshot()['provider']
        accepted = self.accept(self.execute(self.claim()))
        owner = next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual((owner.authority, owner.active_request), ('RADIUS', None))
        self.assertEqual(accepted.state, 'FIXTURE_STEP_SUCCEEDED')
        self.assertEqual(self.provider.snapshot()['provider'], provider)
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=99)), permission=True)

    def test_staged_consumption_audit_and_accepted_checkpoint_are_required_for_safe_replay(self):
        original = self.unit.snapshot()
        self.unit._state['execution_audit'] = [r for r in self.unit._state['execution_audit'] if r[3] != 'CONSUMED']
        before = self.unit.snapshot(), self.provider.snapshot()
        with self.assertRaises(ExecutorConflict):
            self.claim()
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.unit._state = original
        receipt = self.execute(self.claim())
        accepted = self.accept(receipt)
        self.assertEqual(self.accept(receipt), accepted)
        key, events = next(iter(self.unit._state['outbox'].items()))
        self.unit._state['outbox'][key] = (*events[:-1], events[-1].model_copy(update={'status': 'PENDING'}))
        before = self.unit.snapshot()
        with self.assertRaises(ExecutorConflict):
            self.accept(receipt)
        self.assertEqual(before, self.unit.snapshot())
        from app.simulation.aaa_executor import ExecutorCommand
        with self.assertRaises(ValidationError):
            ExecutorCommand(**{**self.unit._state['executor_claims'][receipt.execution_id].model_dump(),
                               'expires_at': receipt.expires_at.replace(tzinfo=None)})

    def test_unknown_without_observed_effect_still_requires_reconciliation_and_atomic_receipt(self):
        self.build_staged(outcome='UNKNOWN')
        before_effect = self.provider.snapshot()['provider']
        receipt = self.execute(self.claim())
        self.assertEqual(receipt.outcome, 'UNKNOWN')
        self.assertEqual(self.provider.snapshot()['provider'], before_effect)
        before = self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.accept(receipt, fail_at='AUDIT')
        self.assertEqual(self.unit.snapshot(), before)
        self.assertTrue(self.accept(receipt).reconciliation_required)

    def test_authorized_radius_enable_preserves_disabled_local_and_does_not_commit_owner_early(self):
        self.build_staged(prefix=2)
        command = self.claim()
        self.assertEqual(command.allowed_step, 'ENABLE_RADIUS')
        receipt = self.execute(command)
        state = self.provider.snapshot()['provider']
        self.assertFalse(state.local_enabled)
        self.assertEqual(state.radius_state, 'ENABLED')
        self.assertEqual(state.fenced_request, self.request.request_id)
        self.assertEqual(self.accept(receipt).state, 'FIXTURE_STEP_SUCCEEDED')
        owner = next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual((owner.authority, owner.active_request), ('LOCAL', self.request.request_id))

    def test_concurrent_valid_and_conflicting_receipts_publish_one_acceptance(self):
        receipt = self.execute(self.claim())
        forged = receipt.model_copy(update={'outcome': 'REJECTED'})
        def accept_candidate(value):
            try:
                return self.accept(value).state
            except ExecutorConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(accept_candidate, (receipt, forged))),
                                  ['FIXTURE_STEP_SUCCEEDED', 'CONFLICT'])
        state = self.unit.snapshot()
        self.assertEqual(len(state['executor_accepted']), 1)
        self.assertEqual(next(iter(state['owners'].values())).revision, 8)
        self.assertEqual(sum(r[2] == 'FIXTURE_STEP_SUCCEEDED' for r in state['executor_audit']), 1)
