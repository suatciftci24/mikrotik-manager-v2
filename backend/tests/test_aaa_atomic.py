from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID
from pydantic import ValidationError

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import (AtomicPlan, AtomicRequest, MemoryAtomicUnit,
    AtomicConflict, CompensationEvidence, canonical_hash)


class AtomicContractTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.plan = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.plan, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=110), correlation_id=UUID(int=111))
        self.unit = MemoryAtomicUnit(self.plan)
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def reserve(self, request=None, **kwargs):
        return self.unit.reserve(request or self.request, self.scope, permission=True, **kwargs)

    def next(self):
        return self.unit.next_event(self.request, self.scope, permission=True)

    def settle(self, event, revision, outcome='APPLIED', **kwargs):
        return self.unit.settle(self.request, self.scope, event.event_id, outcome, revision,
                                permission=True, **kwargs)

    def test_canonical_hash_json_roundtrip_and_all_plan_bindings(self):
        self.assertEqual(canonical_hash({'b': 2, 'a': 1}), canonical_hash({'a': 1, 'b': 2}))
        self.assertEqual(AtomicPlan.model_validate_json(self.plan.model_dump_json()).plan_hash(), self.plan.plan_hash())
        for change in ({'expected_source_revision': 8}, {'expected_target_revision': 1},
                       {'namespace_revision': 3}, {'authorization_policy_revision': 2},
                       {'preparation_sha256': 'b' * 64}):
            altered = AtomicPlan(**{**self.plan.model_dump(), **change})
            self.assertNotEqual(altered.plan_hash(), self.plan.plan_hash())
        for change in ({'steps': tuple(reversed(self.plan.steps))}, {'tenant_id': 'other'},
                       {'expected_account_revision': 4}, {'source': 'RADIUS'},
                       {'contract_version': 'AAA_ATOMIC_PLAN_V2'}, {'password': 'forbidden'}):
            with self.assertRaises(ValidationError):
                AtomicPlan(**{**self.plan.model_dump(), **change})

    def test_reservation_atomically_binds_owner_journal_audit_and_outbox(self):
        op = self.reserve()
        state = self.unit.snapshot()
        owner = next(iter(state['owners'].values()))
        self.assertEqual((owner.revision, owner.fence, owner.active_request), (4, 1, self.request.request_id))
        self.assertEqual(op.plan_hash, self.plan.plan_hash())
        events = next(iter(state['outbox'].values()))
        self.assertEqual(tuple(e.step for e in events), self.plan.steps)
        self.assertTrue(all(e.plan_hash == op.plan_hash and e.correlation_id == self.request.correlation_id for e in events))
        self.assertEqual(state['audit'][0][4], op.plan_hash)

    def test_every_injected_commit_failure_publishes_nothing(self):
        original = self.unit.snapshot()
        for fail_at in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX'):
            with self.assertRaises(AtomicConflict):
                self.reserve(fail_at=fail_at)
            self.assertEqual(self.unit.snapshot(), original)
        self.reserve()
        event = self.next()
        for fail_at in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX'):
            original = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.settle(event, 1, fail_at=fail_at)
            self.assertEqual(self.unit.snapshot(), original)

    def test_same_request_replays_and_changed_actor_correlation_or_plan_conflicts(self):
        self.reserve()
        before = self.unit.snapshot()
        self.assertEqual(self.reserve().plan_hash, self.plan.plan_hash())
        self.assertEqual(self.unit.snapshot(), before)
        for change in ({'correlation_id': UUID(int=112)},
                       {'plan': self.plan.model_copy(update={'preparation_sha256': 'c' * 64})}):
            with self.assertRaisesRegex(AtomicConflict, 'IDEMPOTENCY_CONFLICT'):
                self.reserve(self.request.model_copy(update=change))
        with self.assertRaises(PermissionError):
            self.reserve(self.request.model_copy(update={'actor_id': 'other'}))
        with self.assertRaises(PermissionError):
            self.unit.next_event(self.request, self.scope.model_copy(update={'tenant_id': 'other'}), permission=True)
        self.assertEqual(self.unit.snapshot(), before)

    def test_concurrent_request_ids_for_one_owner_have_one_cas_winner(self):
        requests = [self.request.model_copy(update={'request_id': UUID(int=n)}) for n in (120, 121)]
        def compete(request):
            try:
                self.reserve(request)
                return 'WIN'
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete, requests)), ['WIN', 'CONFLICT'])
        self.assertEqual(len(self.unit.snapshot()['journal']), 1)
        self.assertEqual(len(self.unit.snapshot()['audit']), 1)

    def test_at_least_once_delivery_is_ordered_and_duplicate_ack_adds_no_effect(self):
        self.reserve()
        event = self.next()
        self.assertEqual(self.next(), event)  # Lost delivery ACK: same stable id.
        later = next(iter(self.unit.snapshot()['outbox'].values()))[1]
        with self.assertRaises(AtomicConflict):
            self.settle(later, 1)
        op = self.settle(event, 1)
        before = self.unit.snapshot()
        self.assertEqual(self.settle(event, 1), op)
        self.assertEqual(self.unit.snapshot(), before)
        self.assertEqual(self.next().sequence, 2)
        with self.assertRaises(AtomicConflict):
            self.settle(self.next(), 1)  # stale operation CAS

    def test_final_owner_switch_and_audit_outbox_ack_are_one_publish(self):
        op = self.reserve()
        for _ in range(3):
            op = self.settle(self.next(), op.revision)
        before = self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.settle(self.next(), op.revision, fail_at='AUDIT')
        self.assertEqual(self.unit.snapshot(), before)
        self.assertEqual(next(iter(before['owners'].values())).authority, 'LOCAL')
        op = self.settle(self.next(), op.revision)
        owner = next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual((owner.authority, owner.revision, owner.active_request), ('RADIUS', 5, None))
        self.assertEqual(op.state, 'MODELED')
        self.assertIsNone(self.next())

    def test_unknown_or_partial_failure_blocks_delivery_and_historical_retry(self):
        for outcome in ('UNKNOWN', 'NOT_APPLIED'):
            self.unit = MemoryAtomicUnit(self.plan)
            op = self.reserve()
            op = self.settle(self.next(), op.revision)
            event = self.next()
            op = self.settle(event, op.revision, outcome)
            self.assertEqual(op.state, 'RECONCILIATION')
            before = self.unit.snapshot()
            self.assertEqual(self.reserve().state, 'RECONCILIATION')
            with self.assertRaises(AtomicConflict):
                self.next()
            with self.assertRaises(AtomicConflict):
                self.settle(event, op.revision, 'APPLIED')
            self.assertEqual(self.unit.snapshot(), before)
            self.assertEqual(next(iter(before['owners'].values())).authority, 'LOCAL')

    def test_compensation_requires_fresh_evidence_cancels_old_intents_and_increments_revision(self):
        op = self.reserve()
        op = self.settle(self.next(), op.revision, 'UNKNOWN')
        evidence = CompensationEvidence(plan_hash=op.plan_hash, expected_owner_revision=4,
            expected_operation_revision=op.revision, fence=op.fence,
            external_result_known=True, target_disabled=True, local_restored=True)
        with self.assertRaises(PermissionError):
            self.unit.compensate(self.request, self.scope, evidence, permission=True)
        for change in ({'external_result_known': False}, {'target_disabled': False},
                       {'expected_owner_revision': 3}, {'fence': 2}):
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.unit.compensate(self.request, self.scope, evidence.model_copy(update=change), permission=True, compensation_permission=True)
            self.assertEqual(before, self.unit.snapshot())
        op = self.unit.compensate(self.request, self.scope, evidence, permission=True, compensation_permission=True)
        owner = next(iter(self.unit.snapshot()['owners'].values()))
        self.assertEqual((owner.authority, owner.revision, owner.active_request), ('LOCAL', 5, None))
        notification = self.next()
        self.assertEqual(notification.step, 'COMPENSATED')
        self.assertEqual(self.settle(notification, op.revision, 'UNKNOWN'), op)
        self.assertEqual(self.next(), notification)
        self.settle(notification, op.revision)
        self.assertIsNone(self.next())
        self.assertEqual(self.reserve().state, 'COMPENSATED')

    def test_preparation_bridge_binds_validated_evidence_and_rejects_unapproved_plan(self):
        from datetime import timedelta
        from app.simulation.aaa_integration_preparation import (
            FixtureGates, PreparationRequest, FixtureObservation, FakeAaaReadAdapter, prepare_handoff)
        from app.integrations.aaa_contracts import snapshot_fingerprint
        from app.simulation.aaa_atomic import plan_from_preparation
        preview = synthetic_request()
        digest = snapshot_fingerprint(preview.snapshot)
        gates = FixtureGates(snapshot_sha256=digest, actor_id=self.scope.actor_id,
            tenant_id=self.scope.tenant_id, valid_until=preview.clock + timedelta(minutes=5),
            namespace_revision=2, nas_revision=1, profile_revision=1, namespace_exclusive=True,
            credential_ownership_approved=True, disabled_target_supported=True,
            source_fencing_supported=True, atomic_owner_audit_supported=True)
        request = PreparationRequest(preview=preview, gates=gates, correlation_id=UUID(int=900),
            phase='PREPARE', expected_operation_revision=1, expected_source_revision=7, expected_target_revision=0)
        adapter = FakeAaaReadAdapter(FixtureObservation(snapshot_sha256=digest, namespace_revision=2,
            account_revision=3, source_revision=7, target_revision=0, local_state='ENABLED', radius_state='ABSENT'))
        plan = plan_from_preparation(request, self.scope, adapter, policy_revision=2, permission=True)
        decision = prepare_handoff(request, self.scope, adapter, fixture_transition_permission=True)
        self.assertEqual(plan.preparation_sha256, decision.fingerprint)
        self.assertEqual(plan.snapshot, preview.snapshot)
        self.assertEqual(plan.authorization_policy_revision, 2)
        with self.assertRaises(AtomicConflict):
            plan_from_preparation(request, self.scope, adapter, policy_revision=2)
        with self.assertRaises(AtomicConflict):
            plan_from_preparation(request.model_copy(update={'phase': 'UNCERTAIN'}), self.scope,
                                  adapter, policy_revision=2, permission=True)

    def test_owner_drift_after_reservation_blocks_delivery_and_completion(self):
        op = self.reserve()
        event = self.next()
        # Fault injection into caller-owned fake memory, representing a competing writer.
        key, owner = next(iter(self.unit._state['owners'].items()))
        self.unit._state['owners'][key] = owner.model_copy(update={'revision': owner.revision + 1})
        before = self.unit.snapshot()
        with self.assertRaisesRegex(AtomicConflict, 'OWNER_CAS_RECONCILIATION_REQUIRED'):
            self.next()
        with self.assertRaisesRegex(AtomicConflict, 'OWNER_CAS_RECONCILIATION_REQUIRED'):
            self.settle(event, op.revision)
        self.assertEqual(before, self.unit.snapshot())
