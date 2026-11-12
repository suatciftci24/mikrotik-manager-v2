from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID
from pydantic import ValidationError

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import AtomicPlan, AtomicRequest, AtomicConflict
from app.simulation.aaa_worker import FakeLeaseClock, WorkerContext, Claim, LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, accept_provider_response
from app.simulation.aaa_decision import FixtureDecisionService, FixtureDecisionAuthority, DecisionIntent
from app.simulation.aaa_followup import (FixtureFollowupService, FixtureFollowupAuthority,
    FollowupIntent, ContinuePlan, CancelPlan, FollowupConflict)


class FollowupPlanTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.root = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.root, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=901), correlation_id=UUID(int=902))
        self.clock = FakeLeaseClock(fixture.clock)
        self.worker = WorkerContext(tenant_id=self.root.tenant_id, worker_id='fixture-worker', can_deliver=True)
        self.authority = FixtureFollowupAuthority(tenant_id=self.root.tenant_id,
                                                 actor_id=self.scope.actor_id, can_continue=True, can_cancel=True)
        self.build_checkpoint()
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def build_checkpoint(self, unknown_at=1):
        self.unit = LeasedMemoryOutbox(self.root, self.clock)
        self.provider = FakeFencedProvider(self.root)
        self.unit.reserve(self.request, self.scope, permission=True)
        for attempt in range(1, unknown_at + 1):
            lease = self.unit.claim(self.request, self.scope, self.worker,
                Claim(attempt_id=UUID(int=attempt)), permission=True)
            self.unit.dispatch(self.request, self.scope, self.worker, lease, permission=True)
            command = self.provider.command(self.unit, self.request, self.scope, self.worker, lease, permission=True)
            receipt = self.provider.execute(self.unit, self.request, self.scope, self.worker, lease, command, permission=True)
            if attempt < unknown_at:
                accept_provider_response(self.unit, self.provider, self.request, self.scope,
                                          self.worker, lease, receipt, permission=True)
        self.unit.nack(self.request, self.scope, self.worker, lease, 'UNKNOWN', permission=True)
        self.recovery = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=unknown_at + 1), purpose='RECONCILE'), permission=True)
        decisions = FixtureDecisionService(self.unit, self.provider)
        authority = FixtureDecisionAuthority(tenant_id=self.root.tenant_id,
            actor_id=self.scope.actor_id, can_issue=True, can_commit=True)
        grant = decisions.issue(self.request, self.scope, self.worker, self.recovery, authority,
            DecisionIntent(authorization_id=UUID(int=950), decision='ACCEPT_APPLIED_EVIDENCE'), permission=True)
        self.decision = decisions.commit(self.request, self.scope, self.worker, self.recovery,
                                         authority, grant, permission=True)
        self.service = FixtureFollowupService(self.unit, self.provider)

    def plan(self, kind='CONTINUE'):
        return self.service.plan(self.request, self.scope, self.decision.authorization_id, kind, permission=True)

    def issue(self, plan=None, number=1, ttl=30, authority=None):
        return self.service.issue(self.request, self.scope, authority or self.authority, plan or self.plan(),
            FollowupIntent(authorization_id=UUID(int=number), lifetime_seconds=ttl), permission=True)

    def commit(self, grant, **kwargs):
        return self.service.commit(self.request, self.scope, self.authority, grant, permission=True, **kwargs)

    def test_distinct_versioned_canonical_plans_bind_checkpoint_and_do_not_grant_execution(self):
        before = self.unit.snapshot()
        go, stop = self.plan(), self.plan('CANCEL')
        self.assertIsInstance(go, ContinuePlan)
        self.assertIsInstance(stop, CancelPlan)
        self.assertNotEqual(go.plan_hash(), stop.plan_hash())
        self.assertEqual(ContinuePlan.model_validate_json(go.model_dump_json()).plan_hash(), go.plan_hash())
        self.assertEqual(CancelPlan.model_validate_json(stop.model_dump_json()).plan_hash(), stop.plan_hash())
        self.assertEqual((go.previous_plan_hash, go.decision_id, go.owner_revision, go.expected_state),
                         (self.root.plan_hash(), self.decision.authorization_id, 5, 'DECISION_RECORDED'))
        self.assertFalse(go.automatic_dispatch)
        self.assertEqual(stop.external_effects, 'NOT_REVERSED_BY_CANCEL')
        for change in ({'contract_version': 'PRODUCTION'}, {'kind': 'CANCEL'}, {'automatic_dispatch': True}):
            with self.assertRaises(ValidationError):
                ContinuePlan(**{**go.model_dump(), **change})
        self.assertEqual(before, self.unit.snapshot())

    def test_continue_and_cancel_permissions_are_separate_at_issue_and_commit(self):
        for kind, flag in (('CONTINUE', 'can_continue'), ('CANCEL', 'can_cancel')):
            plan = self.plan(kind)
            denied = self.authority.model_copy(update={flag: False})
            before = self.unit.snapshot()
            with self.assertRaises(PermissionError):
                self.issue(plan, authority=denied)
            self.assertEqual(before, self.unit.snapshot())
            grant = self.issue(plan, number=1 if kind == 'CONTINUE' else 2)
            before = self.unit.snapshot()
            with self.assertRaises(PermissionError):
                self.service.commit(self.request, self.scope, denied, grant, permission=True)
            self.assertEqual(before, self.unit.snapshot())

    def test_wrong_scope_plan_evidence_or_authorization_cannot_be_substituted(self):
        plan = self.plan()
        for change in ({'tenant_id': 'other'}, {'subscriber_id': 'demo-sub-other'},
                       {'previous_plan_hash': '0' * 64}, {'decision_id': UUID(int=999)},
                       {'owner_revision': 6}, {'evidence_fingerprint': '0' * 64},
                       {'checkpoint_fingerprint': '0' * 64}):
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(plan.model_copy(update=change))
            self.assertEqual(before, self.unit.snapshot())
        grant = self.issue(plan)
        before = self.unit.snapshot()
        with self.assertRaises(FollowupConflict):
            self.commit(grant.model_copy(update={'plan': self.plan('CANCEL')}))
        self.assertEqual(before, self.unit.snapshot())

    def test_expired_or_duplicate_authorization_fails_closed(self):
        grant = self.issue(ttl=2)
        before = self.unit.snapshot()
        with self.assertRaises(FollowupConflict):
            self.issue()
        self.clock.advance(2)
        with self.assertRaisesRegex(FollowupConflict, 'AUTHORIZATION_EXPIRED'):
            self.commit(grant)
        self.assertEqual(before, self.unit.snapshot())

    def test_continue_advances_to_held_review_with_no_pending_provider_intent(self):
        grant = self.issue()
        provider = self.provider.snapshot()
        record = self.commit(grant)
        state = self.unit.snapshot()
        owner, op = next(iter(state['owners'].values())), next(iter(state['journal'].values()))
        self.assertEqual((op.state, owner.revision, owner.fence), ('CONTINUE_HELD', 6, 3))
        self.assertEqual(owner.active_request, self.request.request_id)
        self.assertEqual(owner.authority, 'LOCAL')
        events = next(iter(state['outbox'].values()))
        self.assertEqual((events[-1].status, events[-1].step, events[-1].plan_hash),
                         ('HELD', 'CONTINUE_EXECUTION_REVIEW', grant.plan.plan_hash()))
        self.assertFalse(any(e.status == 'PENDING' for e in events))
        self.assertFalse(record.automatic_dispatch)
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=10)), permission=True)
        self.assertEqual(provider, self.provider.snapshot())
        self.assertEqual(state, self.unit.snapshot())

    def test_cancel_closes_plan_without_assuming_applied_effects_were_reversed(self):
        self.build_checkpoint(unknown_at=3)  # Provider LOCAL is off and RADIUS is already enabled.
        provider = self.provider.snapshot()
        self.assertEqual(provider['provider'].radius_state, 'ENABLED')
        grant = self.issue(self.plan('CANCEL'))
        record = self.commit(grant)
        state = self.unit.snapshot()
        self.assertEqual(record.state, 'CANCELLED_HELD')
        self.assertFalse(record.external_effects_reversed)
        self.assertEqual(self.provider.snapshot(), provider)
        self.assertEqual(next(iter(state['owners'].values())).active_request, self.request.request_id)
        self.assertEqual(next(iter(state['outbox'].values()))[-1].status, 'HELD')
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=10)), permission=True)

    def test_duplicate_commit_consumes_once_and_cannot_reapply(self):
        grant = self.issue()
        self.commit(grant)
        before = self.unit.snapshot()
        with self.assertRaisesRegex(FollowupConflict, 'AUTHORIZATION_ALREADY_USED'):
            self.commit(grant)
        self.assertEqual(before, self.unit.snapshot())
        self.assertEqual(sum(r[3] == 'CONSUMED' for r in before['followup_audit']), 1)

    def test_continue_cancel_race_has_one_atomic_winner(self):
        grants = [self.issue(self.plan(), number=1), self.issue(self.plan('CANCEL'), number=2)]
        def compete(grant):
            try:
                return self.commit(grant).kind
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, grants))
        self.assertEqual(results.count('CONFLICT'), 1)
        state = self.unit.snapshot()
        self.assertEqual(len(state['followup_records']), 1)
        self.assertEqual(next(iter(state['owners'].values())).revision, 6)
        self.assertEqual(len(next(iter(state['outbox'].values()))), 5)

    def test_partial_commit_faults_leave_authorization_owner_journal_audit_and_outbox_unchanged(self):
        grant = self.issue()
        before = self.unit.snapshot(), self.provider.snapshot()
        for stage in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX', 'AUTHORIZATION'):
            with self.subTest(stage=stage), self.assertRaises(AtomicConflict):
                self.commit(grant, fail_at=stage)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.commit(grant)

    def test_stale_revision_or_fence_after_issue_cannot_consume_grant(self):
        grant = self.issue()
        original = self.unit.snapshot()
        for table, field in (('owners', 'revision'), ('owners', 'fence'), ('journal', 'revision'), ('leases', 'token')):
            key, value = next(iter(self.unit._state[table].items()))
            self.unit._state[table][key] = value.model_copy(update={field: getattr(value, field) + 1})
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.commit(grant)
            self.assertEqual(before, self.unit.snapshot())
            self.assertFalse(before['followup_records'])
            self.unit._state = deepcopy(original)

    def test_changed_provider_evidence_after_issue_is_rejected_without_partial_changes(self):
        grant = self.issue()
        provider = self.provider._state['provider']
        self.provider._state['provider'] = provider.model_copy(update={'generation': provider.generation + 1})
        before = self.unit.snapshot(), self.provider.snapshot()
        with self.assertRaisesRegex(FollowupConflict, 'PROVIDER_EVIDENCE_CHANGED'):
            self.commit(grant)
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
