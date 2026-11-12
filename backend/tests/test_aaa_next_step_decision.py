"""Targeted next-step decision tests, using existing memory fixture builders only."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from uuid import UUID

from backend.tests import test_aaa_next_step_evidence as fixtures
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_worker import Claim
from app.simulation.aaa_executor_decision import (ExecutorDecisionIntent, AuthorizedExecutorDecision,
                                                ExecutorDecisionRecord)


class NextStepDecisionTests(TestCase):
    def prepare(self, outcome='SUCCESS', prefix=1):
        helper = fixtures.NextStepEvidenceTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f, self.command, self.accepted = helper.prepare(outcome=outcome, prefix=prefix)
        self.evaluation = self.f.service.evaluate(self.f.request, self.f.scope, self.f.context,
                                                self.command.execution_id, permission=True)
        return self.f

    def issue(self, number=9900, seconds=60, decision=None, evaluation=None):
        f = self.f
        return f.service.issue(f.request, f.scope, f.context, evaluation or self.evaluation,
            ExecutorDecisionIntent(authorization_id=UUID(int=number), seconds=seconds,
                decision=decision or ('CONFIRM_SUCCESS' if self.evaluation.status == 'CONFIRMED_SUCCESS' else 'CONFIRM_REJECTION')),
            permission=True)

    def apply(self, grant, **kwargs):
        f = self.f
        return f.service.apply(f.request, f.scope, f.context, grant, permission=True, **kwargs)

    def snapshot(self):
        return self.f.unit.snapshot(), self.f.provider.snapshot()

    def test_same_authorization_contract_two_steps_two_decisions_and_no_dispatch(self):
        for prefix in (1, 2):
            for outcome in ('SUCCESS', 'REJECTED'):
                with self.subTest(prefix=prefix, outcome=outcome):
                    f = self.prepare(outcome, prefix)
                    history = f.unit.snapshot()
                    provider = f.provider.snapshot()
                    grant = self.issue()
                    self.assertIs(type(grant), AuthorizedExecutorDecision)
                    self.assertEqual(grant.version, 'AUTHORIZED_DECISION_V1_EXECUTOR_FIXTURE')
                    self.assertEqual(AuthorizedExecutorDecision.model_validate_json(grant.model_dump_json()), grant)
                    self.assertEqual(grant.evaluation.execution_id, self.command.execution_id)
                    record = self.apply(grant)
                    self.assertIs(type(record), ExecutorDecisionRecord)
                    self.assertEqual(record.state, 'NEXT_STEP_DECISION_RECORDED')
                    self.assertEqual(ExecutorDecisionRecord.model_validate_json(record.model_dump_json()), record)
                    state = f.unit.snapshot()
                    key = next(iter(state['journal']))
                    owner = next(iter(state['owners'].values()))
                    self.assertEqual(state['journal'][key].state, record.state)
                    self.assertEqual(owner.revision, self.evaluation.owner_revision + 1)
                    self.assertEqual(owner.fence, self.evaluation.owner_fence + 1)
                    self.assertEqual(owner.authority, 'LOCAL')
                    self.assertEqual(owner.active_request, f.request.request_id)
                    self.assertEqual(state['leases'][key].token, self.command.fencing_token+1)
                    self.assertEqual(state['audit'][-1][6], record.state)
                    self.assertFalse(record.automatic_dispatch)
                    self.assertFalse(record.external_writes)
                    self.assertEqual(state['executor_accepted'], history['executor_accepted'])
                    for table in ('executor_decision_records', 'executor_decision_authorizations',
                                  'executor_policy_records', 'executor_policy_authorizations'):
                        for old_id, value in history[table].items():
                            self.assertEqual(state[table][old_id], value)
                    self.assertEqual(state['executor_policy_audit'], history['executor_policy_audit'])
                    self.assertFalse(any(e.status == 'PENDING' for e in state['outbox'][key]))
                    self.assertEqual(state['outbox'][key][-1].status, 'HELD')
                    self.assertEqual(state['executor_accepted'][self.command.execution_id], self.accepted)
                    before = self.snapshot()
                    with self.assertRaises(AtomicConflict):
                        f.unit.claim(f.request, f.scope, f.worker, Claim(attempt_id=UUID(int=9999)), permission=True)
                    self.assertEqual(before, self.snapshot())
                    self.assertEqual(provider, f.provider.snapshot())
                    f.assert_history()

    def test_incomplete_conflicting_evidence_and_wrong_decision_cannot_issue(self):
        for outcome in ('UNKNOWN', 'APPLY_THEN_UNKNOWN'):
            self.prepare(outcome)
            before = self.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(decision='CONFIRM_SUCCESS')
            self.assertEqual(before, self.snapshot())
        self.prepare()
        for changes in ({'execution_id': self.f.command.execution_id}, {'tenant_id': 'foreign'},
                        {'subscriber_id': 'wrong'}, {'event_id': UUID(int=1)}, {'attempt_id': UUID(int=1)},
                        {'plan_hash': '0'*64}, {'evidence_fingerprint': '0'*64}, {'receipt_fingerprint': '0'*64},
                        {'owner_revision': 999}, {'fencing_token': 999}, {'version': 'wrong'},
                        {'reference_version': None}):
            before = self.snapshot()
            with self.assertRaises(AtomicConflict):
                self.issue(evaluation=self.evaluation.model_copy(update=changes))
            self.assertEqual(before, self.snapshot())
        with self.assertRaises(AtomicConflict):
            self.issue(decision='CONFIRM_REJECTION')

    def test_expiry_foreign_actor_permission_and_future_authority_fail_closed(self):
        f = self.prepare()
        grant = self.issue(seconds=2)
        original_clock = f.clock.now()
        for context in (f.context.model_copy(update={'can_apply_decision': False}),
                        f.context.model_copy(update={'can_evaluate': False}),
                        f.context.model_copy(update={'tenant_id': 'foreign'}),
                        f.context.model_copy(update={'actor_id': 'foreign'})):
            before = self.snapshot()
            with self.assertRaises(PermissionError):
                f.service.apply(f.request, f.scope, context, grant, permission=True)
            self.assertEqual(before, self.snapshot())
        f.clock.advance(2)
        before = self.snapshot()
        with self.assertRaises(AtomicConflict):
            self.apply(grant)
        self.assertEqual(before, self.snapshot())
        # A forged future grant cannot match the server registry.
        with self.assertRaises(AtomicConflict):
            self.apply(grant.model_copy(update={'issued_at': f.clock.now()}))
        self.assertGreaterEqual(f.clock.now(), original_clock)

    def test_changed_grant_binding_or_version_cannot_consume_original(self):
        self.prepare()
        grant = self.issue()
        variants = [grant.model_copy(update={'version': 'wrong'}),
                    grant.model_copy(update={'decision': 'CONFIRM_REJECTION'}),
                    grant.model_copy(update={'authorization_id': UUID(int=1)})]
        for field, value in [('execution_id', self.f.command.execution_id), ('owner_revision', 1),
                             ('fencing_token', 1), ('evidence_fingerprint', '0'*64)]:
            variants.append(grant.model_copy(update={'evaluation': grant.evaluation.model_copy(update={field: value})}))
        before = self.snapshot()
        for variant in variants:
            with self.assertRaises(AtomicConflict):
                self.apply(variant)
            self.assertEqual(before, self.snapshot())
        self.apply(grant)

    def test_cas_fence_evidence_history_conflict_leaves_authority_unconsumed(self):
        for kind in ('OWNER', 'OWNER_FENCE', 'JOURNAL', 'TOKEN', 'PROVIDER', 'PRIOR_HISTORY', 'STEP'):
            with self.subTest(kind=kind):
                f = self.prepare()
                grant = self.issue()
                if kind in ('OWNER', 'OWNER_FENCE', 'JOURNAL', 'TOKEN'):
                    table, field = {'OWNER': ('owners','revision'), 'OWNER_FENCE': ('owners','fence'),
                                    'JOURNAL': ('journal','revision'), 'TOKEN': ('leases','token')}[kind]
                    key, value = next(iter(f.unit._state[table].items()))
                    f.unit._state[table][key] = value.model_copy(update={field: getattr(value,field)+1})
                elif kind == 'PROVIDER':
                    f.provider._state['highest'] = (self.command.owner_fence, self.command.fencing_token+1)
                elif kind == 'PRIOR_HISTORY':
                    del f.unit._state['executor_decision_records'][f.decision.authorization_id]
                else:
                    record = f.unit._state['execution_records'][self.command.execution_id]
                    f.unit._state['execution_records'][self.command.execution_id] = record.model_copy(update={'allowed_step':'FENCE_LOCAL'})
                before = self.snapshot()
                with self.assertRaises(AtomicConflict):
                    self.apply(grant)
                self.assertEqual(before, self.snapshot())
                self.assertNotIn(grant.authorization_id, f.unit._state['executor_decision_records'])

    def test_five_atomic_failure_boundaries_restore_all_state_and_allow_retry(self):
        self.prepare()
        grant = self.issue()
        before = self.snapshot()
        for fault in ('OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX', 'AUTHORIZATION'):
            with self.subTest(fault=fault), self.assertRaises(AtomicConflict):
                self.apply(grant, fail_at=fault)
            self.assertEqual(before, self.snapshot())
        self.assertEqual(self.apply(grant).state, 'NEXT_STEP_DECISION_RECORDED')

    def test_duplicate_and_competing_grants_have_single_winner(self):
        f = self.prepare()
        grants = [self.issue(number=9900), self.issue(number=9901)]
        def compete(grant):
            try:
                self.apply(grant)
                return 'WIN'
            except AtomicConflict:
                return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete, grants)), ['WIN', 'CONFLICT'])
        state = self.snapshot()
        for grant in grants:
            with self.assertRaises(AtomicConflict):
                self.apply(grant)
            self.assertEqual(state, self.snapshot())
        self.assertEqual(sum(r[0] in {g.authorization_id for g in grants} and r[2]=='CONSUMED'
                             for r in f.unit._state['executor_decision_audit']), 1)

    def test_issue_permissions_and_reused_uuid_do_not_create_extra_authority(self):
        f = self.prepare()
        for context in (f.context.model_copy(update={'can_issue_decision': False}),
                        f.context.model_copy(update={'tenant_id': 'foreign'})):
            before = self.snapshot()
            with self.assertRaises(PermissionError):
                f.service.issue(f.request, f.scope, context, self.evaluation,
                    ExecutorDecisionIntent(authorization_id=UUID(int=9900),decision='CONFIRM_SUCCESS'), permission=True)
            self.assertEqual(before, self.snapshot())
        self.issue()
        before = self.snapshot()
        with self.assertRaises(AtomicConflict):
            self.issue()
        self.assertEqual(before, self.snapshot())
