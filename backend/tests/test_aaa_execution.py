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
from app.simulation.aaa_execution import (FixtureExecutionService, FixtureExecutionAuthority, ExecutionIntent,
                                        ExecutionStepPlan, ExecutionConflict)


class ExecutionAuthorizationTests(TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope = fixture.scope
        self.root = AtomicPlan(tenant_id=self.scope.tenant_id, snapshot=fixture.snapshot,
            expected_account_revision=3, expected_source_revision=7, expected_target_revision=0,
            namespace_revision=2, authorization_policy_revision=1, preparation_sha256='a' * 64)
        self.request = AtomicRequest(plan=self.root, actor_id=self.scope.actor_id, at=fixture.clock,
                                     request_id=UUID(int=1001), correlation_id=UUID(int=1002))
        self.clock = FakeLeaseClock(fixture.clock)
        self.worker = WorkerContext(tenant_id=self.root.tenant_id, worker_id='fixture-worker', can_deliver=True)
        self.authority = FixtureExecutionAuthority(tenant_id=self.root.tenant_id,
            actor_id=self.scope.actor_id, can_issue=True, can_stage=True)
        self.build_continue()
        for target in ('socket.socket', 'socket.create_connection', 'sqlite3.connect', 'psycopg.connect'):
            self.enterContext(patch(target, side_effect=AssertionError('External IO forbidden')))

    def build_continue(self, prefix=1, outcome='APPLIED', kind='CONTINUE'):
        self.unit = LeasedMemoryOutbox(self.root, self.clock)
        script = {self.root.steps[prefix - 1]: outcome}
        self.provider = FakeFencedProvider(self.root, outcomes=script)
        self.unit.reserve(self.request, self.scope, permission=True)
        for index in range(1, prefix + 1):
            lease = self.unit.claim(self.request, self.scope, self.worker,
                Claim(attempt_id=UUID(int=index)), permission=True)
            self.unit.dispatch(self.request, self.scope, self.worker, lease, permission=True)
            command = self.provider.command(self.unit, self.request, self.scope, self.worker, lease, permission=True)
            receipt = self.provider.execute(self.unit, self.request, self.scope, self.worker, lease, command, permission=True)
            if index < prefix:
                accept_provider_response(self.unit, self.provider, self.request, self.scope,
                                          self.worker, lease, receipt, permission=True)
        self.unit.nack(self.request, self.scope, self.worker, lease, 'UNKNOWN', permission=True)
        recovery = self.unit.claim(self.request, self.scope, self.worker,
            Claim(attempt_id=UUID(int=prefix + 1), purpose='RECONCILE'), permission=True)
        decisions = FixtureDecisionService(self.unit, self.provider)
        reviewer = FixtureDecisionAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id,
                                           can_issue=True, can_commit=True)
        decision_grant = decisions.issue(self.request, self.scope, self.worker, recovery, reviewer,
            DecisionIntent(authorization_id=UUID(int=1100), decision='ACCEPT_APPLIED_EVIDENCE' if outcome == 'APPLIED'
                           else 'ACCEPT_NOT_APPLIED_EVIDENCE'), permission=True)
        decision = decisions.commit(self.request, self.scope, self.worker, recovery, reviewer,
                                     decision_grant, permission=True)
        followup = FixtureFollowupService(self.unit, self.provider)
        approver = FixtureFollowupAuthority(tenant_id=self.root.tenant_id, actor_id=self.scope.actor_id,
                                            can_continue=True, can_cancel=True)
        plan = followup.plan(self.request, self.scope, decision.authorization_id, kind, permission=True)
        grant = followup.issue(self.request, self.scope, approver, plan,
                               FollowupIntent(authorization_id=UUID(int=1200)), permission=True)
        self.followup = followup.commit(self.request, self.scope, approver, grant, permission=True)
        self.service = FixtureExecutionService(self.unit, self.provider)

    def plan(self, step='FENCE_LOCAL'):
        return self.service.plan(self.request, self.scope, self.followup.authorization_id, step, permission=True)

    def issue(self, plan=None, number=1, ttl=30, authority=None):
        return self.service.issue(self.request, self.scope, authority or self.authority, plan or self.plan(),
            ExecutionIntent(authorization_id=UUID(int=number), lifetime_seconds=ttl), permission=True)

    def stage(self, grant, **kwargs):
        return self.service.stage(self.request, self.scope, self.authority, grant, permission=True, **kwargs)

    def test_execution_contract_binds_exact_continue_decision_evidence_and_one_step(self):
        plan = self.plan()
        self.assertEqual((plan.continue_plan_hash, plan.decision_id, plan.owner_revision, plan.expected_state),
                         (self.followup.plan_hash, self.followup.decision_id, 6, 'CONTINUE_HELD'))
        self.assertEqual((plan.allowed_step, plan.step_sequence, plan.previous_result), ('FENCE_LOCAL', 2, 'APPLIED'))
        self.assertEqual(ExecutionStepPlan.model_validate_json(plan.model_dump_json()).plan_hash(), plan.plan_hash())
        self.assertFalse(plan.provider_dispatch)
        for change in ({'provider_dispatch': True}, {'expected_state': 'PLANNED'}, {'contract_version': 'LIVE'}):
            with self.assertRaises(ValidationError):
                ExecutionStepPlan(**{**plan.model_dump(), **change})

    def test_continue_grant_or_worker_permission_is_not_execution_authority(self):
        before = self.unit.snapshot()
        with self.assertRaises(PermissionError):
            self.issue(authority=self.authority.model_copy(update={'can_issue': False}))
        self.assertEqual(self.unit.snapshot(), before)
        grant = self.issue()
        before = self.unit.snapshot()
        with self.assertRaises(PermissionError):
            self.service.stage(self.request, self.scope,
                self.authority.model_copy(update={'can_stage': False}), grant, permission=True)
        with self.assertRaises(PermissionError):
            self.service.stage(self.request, self.scope,
                self.authority.model_copy(update={'environment': 'PRODUCTION'}), grant, permission=True)
        self.assertEqual(self.unit.snapshot(), before)

    def test_wrong_step_scope_hash_or_evidence_is_rejected_before_authorization(self):
        plan = self.plan()
        for change in ({'tenant_id': 'other'}, {'subscriber_id': 'demo-sub-other'},
                       {'continue_plan_hash': '0' * 64}, {'decision_id': UUID(int=99)},
                       {'allowed_step': 'ENABLE_RADIUS'}, {'step_sequence': 3},
                       {'evidence_fingerprint': '0' * 64}):
            before = self.unit.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(plan.model_copy(update=change))
            self.assertEqual(self.unit.snapshot(), before)
        with self.assertRaisesRegex(ExecutionConflict, 'WRONG_STEP'):
            self.plan('COMMIT_OWNER_CAS')

    def test_expiry_duplicate_id_and_reused_grant_fail_closed(self):
        grant = self.issue(ttl=2)
        before = self.unit.snapshot()
        with self.assertRaises(ExecutionConflict):
            self.issue()
        with self.assertRaises(ExecutionConflict):
            self.stage(grant.model_copy(update={'authorization_id': UUID(int=99)}))
        self.clock.advance(2)
        with self.assertRaisesRegex(ExecutionConflict, 'AUTHORIZATION_EXPIRED'):
            self.stage(grant)
        self.assertEqual(self.unit.snapshot(), before)
        fresh = self.issue(number=2)
        self.stage(fresh)
        before = self.unit.snapshot()
        with self.assertRaisesRegex(ExecutionConflict, 'AUTHORIZATION_ALREADY_USED'):
            self.stage(fresh)
        self.assertEqual(self.unit.snapshot(), before)

    def test_atomic_staging_consumes_grant_and_remains_non_dispatchable(self):
        grant = self.issue()
        provider_before = self.provider.snapshot()
        record = self.stage(grant)
        state = self.unit.snapshot()
        owner, op = next(iter(state['owners'].values())), next(iter(state['journal'].values()))
        self.assertEqual((op.state, owner.revision, owner.fence), ('FIXTURE_EXECUTION_STAGED', 7, 4))
        self.assertEqual(owner.active_request, self.request.request_id)
        self.assertEqual(owner.authority, 'LOCAL')
        self.assertEqual(record.worker_token, 5)
        self.assertFalse(record.provider_dispatch)
        events = next(iter(state['outbox'].values()))
        self.assertEqual((events[-1].status, events[-1].step), ('HELD', 'FIXTURE_STAGE:FENCE_LOCAL'))
        self.assertFalse(any(e.status == 'PENDING' for e in events))
        self.assertEqual(state['execution_audit'][-1][3], 'CONSUMED')
        self.assertEqual(state['audit'][-1][6], 'FIXTURE_EXECUTION_STAGED')
        with self.assertRaises(AtomicConflict):
            self.unit.claim(self.request, self.scope, self.worker, Claim(attempt_id=UUID(int=10)), permission=True)
        self.assertEqual(self.unit.snapshot(), state)
        self.assertEqual(self.provider.snapshot(), provider_before)

    def test_definitive_prefix_selects_only_immediately_next_step_for_all_forward_stages(self):
        for prefix, step in ((1, 'FENCE_LOCAL'), (2, 'ENABLE_RADIUS'), (3, 'COMMIT_OWNER_CAS')):
            self.build_continue(prefix=prefix)
            plan = self.plan(step)
            self.assertEqual(plan.step_sequence, prefix + 1)
            provider_before = self.provider.snapshot()
            self.stage(self.issue(plan))
            self.assertEqual(self.provider.snapshot(), provider_before)

    def test_cancelled_checkpoint_and_not_applied_previous_step_do_not_authorize_forward_execution(self):
        self.build_continue(kind='CANCEL')
        before = self.unit.snapshot()
        with self.assertRaises(ExecutionConflict):
            self.plan()
        self.assertEqual(before, self.unit.snapshot())
        self.build_continue(outcome='NOT_APPLIED')
        before = self.unit.snapshot()
        with self.assertRaisesRegex(ExecutionConflict, 'READ_ONLY_RECONCILIATION_REQUIRED'):
            self.plan()
        self.assertEqual(before, self.unit.snapshot())

    def test_cas_fence_and_outbox_drift_after_issue_leave_grant_unconsumed(self):
        grant = self.issue()
        original = self.unit.snapshot()
        for table, field in (('owners', 'revision'), ('owners', 'fence'), ('journal', 'revision'), ('leases', 'token')):
            key, value = next(iter(self.unit._state[table].items()))
            self.unit._state[table][key] = value.model_copy(update={field: getattr(value, field) + 1})
            before = self.unit.snapshot()
            with self.assertRaises(ExecutionConflict):
                self.stage(grant)
            self.assertEqual(before, self.unit.snapshot())
            self.unit._state = deepcopy(original)
        key, events = next(iter(self.unit._state['outbox'].items()))
        self.unit._state['outbox'][key] = (*events[:-1], events[-1].model_copy(update={'status': 'PENDING'}))
        before = self.unit.snapshot()
        with self.assertRaises(ExecutionConflict):
            self.stage(grant)
        self.assertEqual(before, self.unit.snapshot())

    def test_unknown_or_changed_provider_result_requires_readonly_reconciliation(self):
        grant = self.issue()
        key, receipt = next(iter(self.provider._state['receipts'].items()))
        self.provider._state['receipts'][key] = receipt.model_copy(update={'outcome': 'UNKNOWN'})
        before = self.unit.snapshot(), self.provider.snapshot()
        with self.assertRaisesRegex(ExecutionConflict, 'READ_ONLY_RECONCILIATION_REQUIRED'):
            self.stage(grant)
        self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.assertFalse(self.unit.snapshot()['execution_records'])

    def test_partial_commit_faults_rollback_every_record_and_authorization_consumption(self):
        grant = self.issue()
        before = self.unit.snapshot(), self.provider.snapshot()
        for stage in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX', 'AUTHORIZATION'):
            with self.subTest(stage=stage), self.assertRaises(AtomicConflict):
                self.stage(grant, fail_at=stage)
            self.assertEqual(before, (self.unit.snapshot(), self.provider.snapshot()))
        self.stage(grant)

    def test_concurrent_execution_grants_for_same_checkpoint_have_one_cas_winner(self):
        grants = [self.issue(number=1), self.issue(number=2)]
        def compete(grant):
            try:
                self.stage(grant)
                return 'WIN'
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete, grants)), ['WIN', 'CONFLICT'])
        state = self.unit.snapshot()
        self.assertEqual(len(state['execution_records']), 1)
        self.assertEqual(next(iter(state['owners'].values())).revision, 7)
        self.assertEqual(sum(r[3] == 'CONSUMED' for r in state['execution_audit']), 1)
