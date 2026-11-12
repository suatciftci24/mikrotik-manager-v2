from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID
from pydantic import ValidationError

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import AtomicPlan, AtomicRequest, AtomicConflict
from app.simulation.aaa_worker import FakeLeaseClock, WorkerContext, Claim, LeasedMemoryOutbox, LeaseConflict
from app.simulation.aaa_provider import FakeFencedProvider, reconcile_unknown
from app.simulation.aaa_decision import (FixtureDecisionAuthority, DecisionIntent, FixtureDecisionService,
                                        DecisionConflict, ReconciliationAuthorization)


class ReconciliationDecisionTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.plan = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.plan, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=801), correlation_id=UUID(int=802))
        self.clock = FakeLeaseClock(fixture.clock)
        self.worker = WorkerContext(tenant_id=self.plan.tenant_id, worker_id='fixture-worker',
                                    can_deliver=True, can_compensate=True)
        self.authority = FixtureDecisionAuthority(tenant_id=self.plan.tenant_id,
            actor_id=self.scope.actor_id, can_issue=True, can_commit=True)
        self.build_unknown('APPLIED')
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def build_unknown(self, outcome):
        self.unit = LeasedMemoryOutbox(self.plan, self.clock)
        self.provider = FakeFencedProvider(self.plan, outcomes={'STAGE_DISABLED_TARGET': outcome})
        self.unit.reserve(self.request, self.scope, permission=True)
        old = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=1)), permission=True)
        self.unit.dispatch(self.request, self.scope, self.worker, old, permission=True)
        command = self.provider.command(self.unit, self.request, self.scope, self.worker, old, permission=True)
        self.provider.execute(self.unit, self.request, self.scope, self.worker, old, command, permission=True)
        self.unit.nack(self.request, self.scope, self.worker, old, 'UNKNOWN', permission=True)
        self.lease = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=2), purpose='RECONCILE'), permission=True)
        self.service = FixtureDecisionService(self.unit, self.provider)

    def issue(self, *, number=1, decision='ACCEPT_APPLIED_EVIDENCE', ttl=10, authority=None):
        return self.service.issue(self.request, self.scope, self.worker, self.lease, authority or self.authority,
            DecisionIntent(authorization_id=UUID(int=number), decision=decision, lifetime_seconds=ttl), permission=True)

    def commit(self, grant, **kwargs):
        return self.service.commit(self.request, self.scope, self.worker, self.lease, self.authority,
                                    grant, permission=True, **kwargs)

    def test_evidence_confirmation_is_readonly_and_never_grants_decision_permission(self):
        before = self.unit.snapshot()
        result = reconcile_unknown(self.unit, self.provider, self.request, self.scope,
                                    self.worker, self.lease, permission=True)
        self.assertEqual(result.status, 'PROVIDER_APPLIED_CONFIRMED')
        self.assertEqual(self.unit.snapshot(), before)
        with self.assertRaises(PermissionError):
            self.issue(authority=self.authority.model_copy(update={'can_issue': False}))
        self.assertEqual(self.unit.snapshot(), before)
        grant = self.issue()
        before = self.unit.snapshot()
        with self.assertRaises(PermissionError):
            self.service.commit(self.request, self.scope, self.worker, self.lease,
                self.authority.model_copy(update={'can_commit': False}), grant, permission=True)
        self.assertEqual(self.unit.snapshot(), before)

    def test_authorization_binds_scope_hash_revision_event_evidence_and_fixture_version(self):
        grant = self.issue()
        self.assertEqual((grant.tenant_id, grant.subscriber_id, grant.plan_hash),
            (self.plan.tenant_id, self.plan.snapshot.reference.account_id, self.plan.plan_hash()))
        self.assertEqual((grant.event_id, grant.owner_revision, grant.operation_revision),
                         (self.lease.event_id, 4, 2))
        self.assertEqual(grant.worker_token, self.lease.token)
        self.assertEqual(len(grant.evidence_fingerprint), 64)
        for change in ({'tenant_id': 'other'}, {'subscriber_id': 'demo-sub-other'},
                       {'plan_hash': '0' * 64}, {'event_id': UUID(int=999)}, {'owner_revision': 999},
                       {'evidence_fingerprint': '0' * 64}, {'decision': 'ACCEPT_NOT_APPLIED_EVIDENCE'},
                       {'version': 'REAL_SYSTEM_GRANT'}):
            before = self.unit.snapshot()
            with self.assertRaises(DecisionConflict):
                self.commit(grant.model_copy(update=change))
            self.assertEqual(self.unit.snapshot(), before)
        with self.assertRaises(ValidationError):
            ReconciliationAuthorization(**{**grant.model_dump(), 'version': 'PRODUCTION'})
        with self.assertRaises(PermissionError):
            self.issue(number=2, authority=self.authority.model_copy(update={'environment': 'PRODUCTION'}))

    def test_registered_grant_cannot_be_forged_or_reissued_and_expiry_is_exclusive(self):
        grant = self.issue(ttl=2)
        before = self.unit.snapshot()
        with self.assertRaises(DecisionConflict):
            self.issue()
        with self.assertRaises(DecisionConflict):
            self.commit(grant.model_copy(update={'authorization_id': UUID(int=999)}))
        self.assertEqual(self.unit.snapshot(), before)
        self.clock.advance(2)
        with self.assertRaisesRegex(DecisionConflict, 'AUTHORIZATION_EXPIRED'):
            self.commit(grant)
        self.assertEqual(self.unit.snapshot(), before)

    def test_commit_is_one_use_atomic_and_keeps_owner_reserved_without_provider_dispatch(self):
        grant = self.issue()
        provider_before = self.provider.snapshot()
        record = self.commit(grant)
        state = self.unit.snapshot()
        owner = next(iter(state['owners'].values()))
        op = next(iter(state['journal'].values()))
        self.assertEqual((owner.authority, owner.revision, owner.active_request), ('LOCAL', 5, self.request.request_id))
        self.assertEqual((owner.fence, op.fence, op.owner_revision), (2, 2, 5))
        self.assertEqual(op.state, 'DECISION_RECORDED')
        self.assertFalse(record.automatic_dispatch)
        self.assertEqual(state['decision_records'][grant.authorization_id], record)
        self.assertTrue(all(e.status in ('ACKED', 'CANCELLED') for e in next(iter(state['outbox'].values()))))
        self.assertEqual(state['audit'][-1][6], 'DECISION_RECORDED')
        self.assertEqual(state['decision_audit'][-1][2], 'CONSUMED')
        with self.assertRaisesRegex(DecisionConflict, 'AUTHORIZATION_ALREADY_USED'):
            self.commit(grant)
        with self.assertRaises(LeaseConflict):
            self.unit.dispatch(self.request, self.scope, self.worker, self.lease, permission=True)
        with self.assertRaises(LeaseConflict):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=3)), permission=True)
        self.assertEqual(self.unit.snapshot(), state)
        self.assertEqual(self.provider.snapshot(), provider_before)

    def test_not_applied_decision_cancels_unapplied_intents_but_is_not_a_completed_transition(self):
        self.build_unknown('NOT_APPLIED')
        grant = self.issue(decision='ACCEPT_NOT_APPLIED_EVIDENCE')
        self.commit(grant)
        state = self.unit.snapshot()
        events = next(iter(state['outbox'].values()))
        self.assertTrue(all(e.status == 'CANCELLED' for e in events))
        self.assertEqual(events[0].result, 'NOT_APPLIED')
        self.assertEqual(next(iter(state['journal'].values())).state, 'DECISION_RECORDED')
        self.assertEqual(next(iter(state['owners'].values())).authority, 'LOCAL')

    def test_owner_cas_or_journal_conflict_does_not_consume_authorization(self):
        grant = self.issue()
        original = self.unit.snapshot()
        for table, field in (('owners', 'revision'), ('journal', 'revision')):
            self.unit._state = self.unit.snapshot()
            key, value = next(iter(self.unit._state[table].items()))
            self.unit._state[table][key] = value.model_copy(update={field: value.revision + 1})
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.commit(grant)
            self.assertEqual(self.unit.snapshot(), before)
            self.assertNotIn(grant.authorization_id, before['decision_records'])
            self.unit._state = original

    def test_every_partial_publish_fault_rolls_back_owner_journal_audit_outbox_and_grant_consumption(self):
        grant = self.issue()
        before = self.unit.snapshot(), self.provider.snapshot()
        for stage in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX', 'AUTHORIZATION'):
            with self.subTest(stage=stage), self.assertRaises(AtomicConflict):
                self.commit(grant, fail_at=stage)
            self.assertEqual((self.unit.snapshot(), self.provider.snapshot()), before)
        self.commit(grant)  # Rollback left the same grant usable.

    def test_concurrent_duplicate_decision_has_one_commit_and_no_partial_loser(self):
        grant = self.issue()
        def compete(_):
            try:
                self.commit(grant)
                return 'WIN'
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete, range(2))), ['WIN', 'CONFLICT'])
        state = self.unit.snapshot()
        self.assertEqual(len(state['decision_records']), 1)
        self.assertEqual(sum(r[2] == 'CONSUMED' for r in state['decision_audit']), 1)
        self.assertEqual(next(iter(state['owners'].values())).revision, 5)

    def test_other_grant_for_same_event_and_stale_recovery_fence_are_rejected(self):
        first, second = self.issue(), self.issue(number=2)
        self.commit(first)
        before = self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.commit(second)
        self.assertEqual(self.unit.snapshot(), before)
        # Separate fresh fixture: valid grant expiry does not override a changed lease owner/token.
        self.build_unknown('APPLIED')
        grant = self.issue(ttl=30)
        self.clock.advance(30)
        current = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=3), purpose='RECONCILE'), permission=True)
        before = self.unit.snapshot()
        with self.assertRaises(AtomicConflict):
            self.service.commit(self.request, self.scope, self.worker, current,
                                self.authority, grant, permission=True)
        self.assertEqual(self.unit.snapshot(), before)

    def test_changed_but_consistent_provider_evidence_requires_new_authorization(self):
        grant = self.issue()
        # Fixture history correction: still internally consistent, but a different evidence digest.
        key, receipt = next(iter(self.provider._state['receipts'].items()))
        command = receipt.command.model_copy(update={'worker_id': 'corrected-historical-worker'})
        self.provider._state['receipts'][key] = receipt.model_copy(update={'command': command})
        for index, row in enumerate(self.unit._state['worker_audit']):
            if row[8] == 'DISPATCH':
                self.unit._state['worker_audit'][index] = (*row[:4], command.worker_id, *row[5:])
        result = reconcile_unknown(self.unit, self.provider, self.request, self.scope,
                                    self.worker, self.lease, permission=True)
        self.assertEqual(result.status, 'PROVIDER_APPLIED_CONFIRMED')
        before = self.unit.snapshot(), self.provider.snapshot()
        with self.assertRaisesRegex(DecisionConflict, 'CAS_FENCE_OR_EVIDENCE_CHANGED'):
            self.commit(grant)
        self.assertEqual((self.unit.snapshot(), self.provider.snapshot()), before)

    def test_wrong_decision_or_missing_evidence_cannot_issue_authorization(self):
        before = self.unit.snapshot()
        with self.assertRaisesRegex(DecisionConflict, 'DECISION_EVIDENCE_CONFLICT'):
            self.issue(decision='ACCEPT_NOT_APPLIED_EVIDENCE')
        self.assertEqual(self.unit.snapshot(), before)
        self.build_unknown('UNKNOWN')
        before = self.unit.snapshot()
        with self.assertRaisesRegex(DecisionConflict, 'EVIDENCE_NOT_CONFIRMED'):
            self.issue()
        self.assertEqual(self.unit.snapshot(), before)

    def test_changed_fence_with_unexpired_grant_requires_new_authorization(self):
        grant = self.issue()
        key = (self.plan.tenant_id, self.request.request_id)
        # Explicit in-memory supervisor/fencing fault while the original grant time is still valid.
        replacement = self.lease.model_copy(update={'token': self.lease.token + 1,
            'worker_id': 'replacement-worker', 'attempt_id': UUID(int=3)})
        self.unit._state['leases'][key] = replacement
        worker = self.worker.model_copy(update={'worker_id': replacement.worker_id})
        before = self.unit.snapshot()
        with self.assertRaises(LeaseConflict):
            self.commit(grant)
        with self.assertRaisesRegex(DecisionConflict, 'CAS_FENCE_OR_EVIDENCE_CHANGED'):
            self.service.commit(self.request, self.scope, worker, replacement,
                                self.authority, grant, permission=True)
        self.assertEqual(self.unit.snapshot(), before)
        self.assertNotIn(grant.authorization_id, before['decision_records'])

    def test_terminal_decision_cannot_dispatch_even_if_a_future_intent_is_accidentally_pending(self):
        self.commit(self.issue())
        key = (self.plan.tenant_id, self.request.request_id)
        events = list(self.unit._state['outbox'][key])
        events[1] = events[1].model_copy(update={'status': 'PENDING'})
        self.unit._state['outbox'][key] = tuple(events)
        before = self.unit.snapshot()
        with self.assertRaisesRegex(AtomicConflict, 'DECISION_RECORDED_NO_AUTOMATIC_DISPATCH'):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=3)), permission=True)
        self.assertEqual(self.unit.snapshot(), before)
