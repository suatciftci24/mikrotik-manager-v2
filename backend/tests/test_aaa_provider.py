from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import AtomicPlan, AtomicRequest
from app.simulation.aaa_worker import FakeLeaseClock, WorkerContext, Claim, LeasedMemoryOutbox, LeaseConflict
from app.simulation.aaa_provider import (FakeFencedProvider, ProviderConflict, accept_provider_response,
                                       assess_unknown, reconcile_unknown)


class ProviderFencingTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.plan = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.plan, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=601), correlation_id=UUID(int=602))
        self.clock = FakeLeaseClock(fixture.clock)
        self.unit = LeasedMemoryOutbox(self.plan, self.clock)
        self.worker = WorkerContext(tenant_id=self.plan.tenant_id, worker_id='worker-a', can_deliver=True)
        self.provider = FakeFencedProvider(self.plan)
        self.unit.reserve(self.request, self.scope, permission=True)
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def delivery(self, attempt=1):
        lease = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=attempt), seconds=10), permission=True)
        self.unit.dispatch(self.request, self.scope, self.worker, lease, permission=True)
        command = self.provider.command(self.unit, self.request, self.scope, self.worker, lease, permission=True)
        return lease, command

    def execute(self, lease, command):
        return self.provider.execute(self.unit, self.request, self.scope, self.worker, lease, command, permission=True)

    def accept(self, lease, receipt):
        return accept_provider_response(self.unit, self.provider, self.request, self.scope,
                                        self.worker, lease, receipt, permission=True)

    def recovery(self, lease, attempt=2):
        self.unit.nack(self.request, self.scope, self.worker, lease, 'UNKNOWN', permission=True)
        return self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=attempt), purpose='RECONCILE'), permission=True)

    def proof(self, recovery):
        return self.provider.observe(self.unit, self.request, self.scope, self.worker, recovery, permission=True)

    def assess(self, recovery):
        return reconcile_unknown(self.unit, self.provider, self.request, self.scope,
                                  self.worker, recovery, permission=True)

    def test_provider_exact_replay_and_duplicate_response_have_one_effect_and_one_ack(self):
        lease, command = self.delivery()
        receipt = self.execute(lease, command)
        before = self.provider.snapshot()
        self.assertEqual(self.execute(lease, command), receipt)
        self.assertEqual(self.provider.snapshot(), before)
        op = self.accept(lease, receipt)
        journal = self.unit.snapshot()
        self.assertEqual(self.accept(lease, receipt), op)
        self.assertEqual(self.unit.snapshot(), journal)
        self.assertEqual(self.execute(lease, command), receipt)
        self.assertEqual(self.provider.snapshot()['provider'].generation, 1)

    def test_wrong_hash_event_attempt_token_or_account_content_is_rejected_without_effect(self):
        lease, command = self.delivery()
        before = self.provider.snapshot()
        for change in ({'plan_hash': 'b' * 64}, {'event_id': UUID(int=999)},
                       {'attempt_id': UUID(int=999)}, {'worker_token': 99},
                       {'account_id': 'demo-sub-other'}, {'request_fingerprint': 'b' * 64},
                       {'owner_fence': 2}, {'step': 'ENABLE_RADIUS'}):
            with self.subTest(change=change), self.assertRaises(ProviderConflict):
                self.execute(lease, command.model_copy(update=change))
            self.assertEqual(self.provider.snapshot(), before)
        self.execute(lease, command)
        with self.assertRaises(ProviderConflict):
            self.execute(lease, command.model_copy(update={'sequence': 2}))

    def test_provider_monotonic_fence_and_attempt_ledger_are_independent_guards(self):
        lease, command = self.delivery()
        self.execute(lease, command)
        self.provider._state['highest'] = (command.owner_fence, command.worker_token + 1)
        before = self.provider.snapshot()
        with self.assertRaisesRegex(ProviderConflict, 'STALE_PROVIDER_FENCE'):
            self.execute(lease, command)
        self.assertEqual(self.provider.snapshot(), before)
        self.provider._state['highest'] = (command.owner_fence, command.worker_token)
        key = (command.tenant_id, command.request_id, command.attempt_id)
        self.provider._state['attempts'][key] = 'different-content-already-recorded'
        with self.assertRaisesRegex(ProviderConflict, 'ATTEMPT_CONTENT_CONFLICT'):
            self.execute(lease, command)

    def test_unauthorized_owner_and_stale_worker_cannot_apply_or_supply_late_ack(self):
        lease, command = self.delivery()
        other = self.worker.model_copy(update={'worker_id': 'worker-b'})
        with self.assertRaises(LeaseConflict):
            self.provider.execute(self.unit, self.request, self.scope, other, lease, command, permission=True)
        with self.assertRaises(PermissionError):
            self.provider.execute(self.unit, self.request, self.scope,
                self.worker.model_copy(update={'tenant_id': 'other'}), lease, command, permission=True)
        receipt = self.execute(lease, command)
        self.clock.advance(11)
        recovery = self.unit.claim(self.request, self.scope, other, Claim(attempt_id=UUID(int=2)), permission=True)
        before = self.provider.snapshot(), self.unit.snapshot()
        with self.assertRaises(LeaseConflict):
            self.execute(lease, command)
        with self.assertRaises(LeaseConflict):
            self.accept(lease, receipt)
        self.assertEqual((self.provider.snapshot(), self.unit.snapshot()), before)
        self.assertEqual(recovery.purpose, 'RECONCILE')

    def test_concurrent_identical_provider_delivery_is_idempotent_under_one_fence(self):
        lease, command = self.delivery()
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda _: self.execute(lease, command), range(2)))
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(self.provider.snapshot()['provider'].generation, 1)
        self.assertEqual(len(self.provider.snapshot()['receipts']), 1)

    def test_forged_or_contradictory_provider_ack_nack_cannot_update_journal(self):
        lease, command = self.delivery()
        receipt = self.execute(lease, command)
        before = self.unit.snapshot()
        with self.assertRaisesRegex(ProviderConflict, 'UNTRUSTED_OR_CONTRADICTORY'):
            self.accept(lease, receipt.model_copy(update={'outcome': 'NOT_APPLIED'}))
        self.assertEqual(self.unit.snapshot(), before)
        self.provider = FakeFencedProvider(self.plan, outcomes={'STAGE_DISABLED_TARGET': 'NOT_APPLIED'})
        receipt = self.execute(lease, command)
        op = self.accept(lease, receipt)
        self.assertEqual(op.state, 'RECONCILIATION')
        self.assertEqual(self.provider.snapshot()['provider'].radius_state, 'ABSENT')

    def test_unknown_with_missing_or_indeterminate_provider_receipt_never_implies_failure_or_success(self):
        lease, _ = self.delivery()
        recovery = self.recovery(lease)
        self.assertEqual(self.assess(recovery).status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        # A separate isolated fixture with explicitly indeterminate provider outcome.
        self.setUp_unknown_fixture()
        lease, command = self.delivery()
        receipt = self.execute(lease, command)
        self.assertEqual(receipt.outcome, 'UNKNOWN')
        self.accept(lease, receipt)
        recovery = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=2), purpose='RECONCILE'), permission=True)
        self.assertEqual(self.assess(recovery).status, 'READ_ONLY_RECONCILIATION_REQUIRED')

    def setUp_unknown_fixture(self):
        self.unit = LeasedMemoryOutbox(self.plan, self.clock)
        self.unit.reserve(self.request, self.scope, permission=True)
        self.provider = FakeFencedProvider(self.plan, outcomes={'STAGE_DISABLED_TARGET': 'UNKNOWN'})

    def test_full_applied_and_not_applied_evidence_only_classify_step_without_resuming(self):
        for outcome, expected in (('APPLIED', 'PROVIDER_APPLIED_CONFIRMED'),
                                 ('NOT_APPLIED', 'PROVIDER_NOT_APPLIED_CONFIRMED')):
            self.unit = LeasedMemoryOutbox(self.plan, self.clock)
            self.unit.reserve(self.request, self.scope, permission=True)
            self.provider = FakeFencedProvider(self.plan, outcomes={'STAGE_DISABLED_TARGET': outcome})
            lease, command = self.delivery()
            self.execute(lease, command)  # Response lost: worker records UNKNOWN instead.
            recovery = self.recovery(lease)
            before = self.unit.snapshot(), self.provider.snapshot()
            result = self.assess(recovery)
            self.assertEqual(result.status, expected)
            self.assertFalse(result.automatic_resume)
            self.assertEqual((self.unit.snapshot(), self.provider.snapshot()), before)
            self.assertEqual(next(iter(before[0]['journal'].values())).state, 'RECONCILIATION')
            self.assertEqual(next(iter(before[0]['owners'].values())).revision, 4)

    def test_partial_prefix_evidence_compares_all_prior_steps_and_owner_fence(self):
        lease, command = self.delivery()
        self.accept(lease, self.execute(lease, command))
        lease, command = self.delivery(2)
        self.execute(lease, command)
        recovery = self.recovery(lease, 3)
        proof = self.proof(recovery)
        self.assertEqual(len(proof.receipts), 2)
        self.assertEqual(self.assess(recovery).status, 'PROVIDER_APPLIED_CONFIRMED')
        self.assertFalse(proof.current.local_enabled)
        self.assertEqual(proof.current.radius_state, 'DISABLED')

    def test_missing_conflicting_or_stale_evidence_keeps_readonly_reconciliation(self):
        lease, command = self.delivery()
        self.execute(lease, command)
        recovery = self.recovery(lease)
        proof, state = self.proof(recovery), self.unit.snapshot()
        bad_proofs = [proof.model_copy(update={'complete': False}), proof.model_copy(update={'receipts': ()}),
            proof.model_copy(update={'plan_hash': '0' * 64}),
            proof.model_copy(update={'current': proof.current.model_copy(update={'local_enabled': False})})]
        receipt = proof.receipts[0]
        bad_proofs += [proof.model_copy(update={'receipts': (receipt.model_copy(update={'command':
            receipt.command.model_copy(update={'attempt_id': UUID(int=999)})}),)}),
            proof.model_copy(update={'receipts': (receipt.model_copy(update={'outcome': 'NOT_APPLIED'}),)})]
        for bad in bad_proofs:
            self.assertEqual(assess_unknown(self.request, recovery, state, bad).status,
                             'READ_ONLY_RECONCILIATION_REQUIRED')
        owner_key, owner = next(iter(state['owners'].items()))
        altered = deepcopy(state)
        altered['owners'][owner_key] = owner.model_copy(update={'revision': owner.revision + 1})
        self.assertEqual(assess_unknown(self.request, recovery, altered, proof).status,
                         'READ_ONLY_RECONCILIATION_REQUIRED')
        altered = deepcopy(state)
        altered['worker_audit'] = [r for r in altered['worker_audit'] if r[8] != 'DISPATCH']
        self.assertEqual(assess_unknown(self.request, recovery, altered, proof).status,
                         'READ_ONLY_RECONCILIATION_REQUIRED')
        altered = deepcopy(state)
        altered['audit'].pop()
        self.assertEqual(assess_unknown(self.request, recovery, altered, proof).status,
                         'READ_ONLY_RECONCILIATION_REQUIRED')
        self.assertEqual(self.unit.snapshot(), state)

    def test_radius_activation_needs_provider_source_fence_and_proven_step_is_not_owner_commit(self):
        for attempt in (1, 2):
            lease, command = self.delivery(attempt)
            self.accept(lease, self.execute(lease, command))
        lease, command = self.delivery(3)
        valid = self.provider.snapshot()['provider']
        self.provider._state['provider'] = valid.model_copy(update={'owner_fence': 0})
        before = self.provider.snapshot()
        with self.assertRaisesRegex(ProviderConflict, 'UNSAFE_PROVIDER_STATE'):
            self.execute(lease, command)
        self.assertEqual(self.provider.snapshot(), before)
        self.provider._state['provider'] = valid
        receipt = self.execute(lease, command)
        self.assertFalse(receipt.after.local_enabled)
        self.assertEqual(receipt.after.radius_state, 'ENABLED')
        recovery = self.recovery(lease, 4)
        self.assertEqual(self.assess(recovery).status, 'PROVIDER_APPLIED_CONFIRMED')
        owner = next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual((owner.authority, owner.revision), ('LOCAL', 4))
        # Conflicting explicit NACK cannot be overwritten by a later APPLIED observation.
        state, proof = self.unit.snapshot(), self.proof(recovery)
        key = (self.request.plan.tenant_id, self.request.request_id)
        events = list(state['outbox'][key])
        events[2] = events[2].model_copy(update={'result': 'NOT_APPLIED'})
        state['outbox'][key] = tuple(events)
        self.assertEqual(assess_unknown(self.request, recovery, state, proof).status,
                         'READ_ONLY_RECONCILIATION_REQUIRED')
