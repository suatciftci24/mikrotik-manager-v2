from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import AtomicPlan, AtomicRequest, CompensationEvidence, AtomicConflict
from app.simulation.aaa_worker import FakeLeaseClock, WorkerContext, Claim, LeasedMemoryOutbox, LeaseConflict


class WorkerLeaseTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        plan = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=plan, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=401), correlation_id=UUID(int=402))
        self.clock = FakeLeaseClock(fixture.clock)
        self.unit = LeasedMemoryOutbox(plan, self.clock)
        self.worker = WorkerContext(tenant_id=plan.tenant_id, worker_id='worker-a', can_deliver=True)
        self.other = self.worker.model_copy(update={'worker_id': 'worker-b'})
        self.unit.reserve(self.request, self.scope, permission=True)
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def claim(self, attempt=1, worker=None, purpose='DELIVER', seconds=10):
        return self.unit.claim(self.request, self.scope, worker or self.worker,
            Claim(attempt_id=UUID(int=attempt), purpose=purpose, seconds=seconds), permission=True)

    def call(self, name, lease, *args, worker=None, **kwargs):
        return getattr(self.unit, name)(self.request, self.scope, worker or self.worker,
                                        lease, *args, permission=True, **kwargs)

    def evidence(self):
        op = next(iter(self.unit.snapshot()['journal'].values()))
        return CompensationEvidence(plan_hash=op.plan_hash, expected_owner_revision=op.owner_revision,
            expected_operation_revision=op.revision, fence=op.fence,
            external_result_known=True, target_disabled=True, local_restored=True)

    def test_concurrent_claims_have_one_winner_and_same_attempt_claim_is_idempotent(self):
        def compete(value):
            try:
                return self.claim(attempt=value, worker=self.worker if value == 1 else self.other)
            except LeaseConflict:
                return 'BUSY'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, (1, 2)))
        self.assertEqual(results.count('BUSY'), 1)
        lease = next(r for r in results if r != 'BUSY')
        worker = self.worker if lease.worker_id == self.worker.worker_id else self.other
        before = self.unit.snapshot()
        self.assertEqual(self.claim(lease.attempt_id.int, worker=worker), lease)
        self.assertEqual(self.unit.snapshot(), before)
        self.assertEqual(lease.token, 1)

    def test_expired_lease_rejects_every_mutator_including_compensation_and_renewal(self):
        lease = self.claim()
        self.clock.advance(10)  # expiry is exclusive, equality is already expired
        before = self.unit.snapshot()
        for name, args in (('ack', ()), ('nack', ()), ('retry', ()), ('renew', ()),
                           ('dispatch', ()), ('compensate', (self.evidence(),))):
            with self.subTest(name=name), self.assertRaisesRegex(LeaseConflict, 'STALE_EXPIRED'):
                self.call(name, lease, *args)
            self.assertEqual(self.unit.snapshot(), before)

    def test_takeover_before_dispatch_reissues_same_event_with_new_attempt_and_monotonic_token(self):
        old = self.claim()
        self.clock.advance(11)
        current = self.claim(2, worker=self.other)
        self.assertEqual(current.event_id, old.event_id)
        self.assertGreater(current.token, old.token)
        before = self.unit.snapshot()
        for name, args in (('ack', ()), ('nack', ()), ('retry', ()), ('renew', ()),
                           ('dispatch', ()), ('compensate', (self.evidence(),))):
            with self.assertRaises(LeaseConflict):
                self.call(name, old, *args)
        self.assertEqual(self.unit.snapshot(), before)
        self.call('dispatch', current, worker=self.other)
        self.call('ack', current, worker=self.other)

    def test_attempt_cannot_be_reused_after_expiry_and_foreign_or_tampered_token_is_rejected(self):
        lease = self.claim()
        before = self.unit.snapshot()
        for bad, worker in ((lease, self.other), (lease.model_copy(update={'token': 99}), self.worker),
                            (lease.model_copy(update={'event_id': UUID(int=999)}), self.worker)):
            with self.assertRaises(LeaseConflict):
                self.call('dispatch', bad, worker=worker)
        self.assertEqual(before, self.unit.snapshot())
        self.clock.advance(10)
        with self.assertRaisesRegex(LeaseConflict, 'ATTEMPT_ID_REUSED'):
            self.claim()

    def test_renewal_preserves_fence_and_attempt_and_cannot_resurrect_expired_lease(self):
        lease = self.claim()
        self.clock.advance(8)
        renewed = self.call('renew', lease, seconds=20)
        self.assertEqual((renewed.token, renewed.attempt_id), (lease.token, lease.attempt_id))
        self.clock.advance(5)  # Original handle uses current repository expiry after renewal.
        self.call('dispatch', lease)
        self.clock.advance(15)
        with self.assertRaises(LeaseConflict):
            self.call('renew', renewed)
        with self.assertRaises(ValueError):
            self.clock.advance(-1)

    def test_retry_is_only_safe_before_dispatch_and_released_lease_cannot_mutate(self):
        lease = self.claim()
        self.call('retry', lease)
        with self.assertRaises(LeaseConflict):
            self.call('ack', lease)
        newer = self.claim(2)
        self.assertEqual(newer.event_id, lease.event_id)
        self.assertGreater(newer.token, lease.token)
        self.call('dispatch', newer)
        with self.assertRaisesRegex(LeaseConflict, 'UNPROVEN_RETRY'):
            self.call('retry', newer)

    def test_crash_after_dispatch_becomes_readonly_reconciliation_not_automatic_redelivery(self):
        old = self.claim()
        self.call('dispatch', old)
        self.clock.advance(11)
        recovery = self.claim(2, worker=self.other)
        self.assertEqual(recovery.purpose, 'RECONCILE')
        self.assertEqual(next(iter(self.unit.snapshot()['journal'].values())).state, 'RECONCILIATION')
        self.assertEqual(self.claim(2, worker=self.other), recovery)
        before = self.unit.snapshot()
        with self.assertRaises(LeaseConflict):
            self.call('ack', old)
        with self.assertRaises(LeaseConflict):
            self.call('dispatch', recovery, worker=self.other)
        with self.assertRaises(LeaseConflict):
            self.call('ack', recovery, worker=self.other)
        self.assertEqual(self.unit.snapshot(), before)
        self.assertEqual(next(iter(before['owners'].values())).authority, 'LOCAL')

    def test_lost_ack_response_replays_only_with_current_unexpired_lease_and_preserves_order(self):
        lease = self.claim()
        self.call('dispatch', lease)
        op = self.call('ack', lease)
        before = self.unit.snapshot()
        self.assertEqual(self.call('ack', lease), op)
        self.assertEqual(self.unit.snapshot(), before)
        next_lease = self.claim(2, worker=self.other)
        self.assertGreater(next_lease.token, lease.token)
        event = self.call('dispatch', next_lease, worker=self.other)
        self.assertEqual(event.sequence, 2)
        with self.assertRaises(LeaseConflict):
            self.call('ack', lease)
        self.clock.advance(11)
        with self.assertRaises(LeaseConflict):
            self.call('ack', next_lease, worker=self.other)

    def test_unknown_nack_stops_following_events_and_compensation_requires_current_recovery_lease(self):
        lease = self.claim()
        self.call('dispatch', lease)
        self.call('nack', lease)
        recovery = self.claim(2, purpose='RECONCILE')
        evidence = self.evidence()
        with self.assertRaises(PermissionError):
            self.call('compensate', recovery, evidence)
        self.clock.advance(11)
        privileged = self.worker.model_copy(update={'can_compensate': True})
        current = self.claim(3, worker=privileged, purpose='RECONCILE')
        before = self.unit.snapshot()
        with self.assertRaises(LeaseConflict):
            self.call('compensate', recovery, evidence, worker=privileged)
        self.assertEqual(self.unit.snapshot(), before)
        op = self.call('compensate', current, evidence, worker=privileged)
        self.assertEqual(op.state, 'COMPENSATED')
        owner = next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual((owner.authority, owner.revision), ('LOCAL', 5))
        notification_lease = self.claim(4)
        self.assertEqual(self.call('dispatch', notification_lease).step, 'COMPENSATED')
        self.clock.advance(11)
        redelivery = self.claim(5, worker=self.other)
        self.assertEqual(redelivery.purpose, 'DELIVER')
        self.assertEqual(redelivery.event_id, notification_lease.event_id)

    def test_ack_and_lease_audit_publish_atomically_with_final_owner_commit(self):
        for attempt in range(1, 5):
            lease = self.claim(attempt)
            event = self.call('dispatch', lease)
            if event.step == 'COMMIT_OWNER_CAS':
                before = self.unit.snapshot()
                with self.assertRaises(AtomicConflict):
                    self.call('ack', lease, fail_at='OUTBOX')
                self.assertEqual(self.unit.snapshot(), before)
            self.call('ack', lease)
        state = self.unit.snapshot()
        self.assertEqual(next(iter(state['owners'].values())).authority, 'RADIUS')
        self.assertEqual([e.sequence for e in next(iter(state['outbox'].values()))], [1, 2, 3, 4])
        self.assertTrue(all(e.status == 'ACKED' for e in next(iter(state['outbox'].values()))))
        self.assertEqual([r[6] for r in state['worker_audit'] if r[8] == 'ACK'], [1, 2, 3, 4])

    def test_scope_operation_revision_and_unfenced_mutator_bypasses_fail_closed(self):
        lease = self.claim()
        with self.assertRaises(PermissionError):
            self.call('dispatch', lease, worker=self.worker.model_copy(update={'tenant_id': 'other'}))
        with self.assertRaises(LeaseConflict):
            self.unit.settle(self.request, self.scope, lease.event_id, 'APPLIED', 1, permission=True)
        with self.assertRaises(LeaseConflict):
            self.unit.next_event(self.request, self.scope, permission=True)
        # Caller-owned fixture fault, representing journal drift between claim and ACK.
        key, op = next(iter(self.unit._state['journal'].items()))
        self.unit._state['journal'][key] = op.model_copy(update={'revision': op.revision + 1})
        before = self.unit.snapshot()
        with self.assertRaises(LeaseConflict):
            self.call('dispatch', lease)
        self.assertEqual(self.unit.snapshot(), before)

    def test_concurrent_old_and_current_delivery_and_ack_have_only_one_effect(self):
        old = self.claim()
        self.clock.advance(11)
        current = self.claim(2, worker=self.other)
        def invoke(pair, method):
            lease, worker = pair
            try:
                self.call(method, lease, worker=worker)
                return 'WIN'
            except LeaseConflict:
                return 'STALE'
        pairs = [(old, self.worker), (current, self.other)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda p: invoke(p, 'dispatch'), pairs)), ['WIN', 'STALE'])
            self.assertCountEqual(list(pool.map(lambda p: invoke(p, 'ack'), pairs)), ['WIN', 'STALE'])
        audit = self.unit.snapshot()['worker_audit']
        self.assertEqual(sum(r[8] == 'DISPATCH' for r in audit), 1)
        self.assertEqual(sum(r[8] == 'ACK' for r in audit), 1)

    def test_expiry_recovery_lease_and_unknown_journal_result_rollback_together(self):
        old = self.claim()
        self.call('dispatch', old)
        self.clock.advance(11)
        before = self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request, self.scope, self.other,
                Claim(attempt_id=UUID(int=2)), permission=True, fail_at='AUDIT')
        self.assertEqual(self.unit.snapshot(), before)
        recovery = self.claim(2, worker=self.other)
        self.assertEqual((recovery.token, recovery.purpose), (2, 'RECONCILE'))
        state = self.unit.snapshot()
        self.assertEqual([r[6] for r in state['audit']], ['RESERVED', 'RECONCILIATION'])
