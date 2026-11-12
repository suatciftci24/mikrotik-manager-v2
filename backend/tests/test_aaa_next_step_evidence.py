"""Only next-step UNKNOWN evidence acceptance; existing suites are not re-run."""
from copy import deepcopy
from unittest import TestCase
from uuid import UUID

from backend.tests import test_aaa_next_step_executor as fixtures
from app.simulation.aaa_executor import FixtureCrash
from app.simulation.aaa_executor_decision import ExecutorDecisionIntent, ExecutorDecisionConflict, ExecutorReconciliationService


class NextStepEvidenceTests(TestCase):
    def prepare(self, *, outcome='SUCCESS', prefix=1, crash='AFTER_EFFECT'):
        f = fixtures.NextStepExecutorTests(methodName='runTest')
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.prepare(prefix=prefix, outcome=outcome)
        command = f.claim_next(seconds=2)
        try:
            f.run_next(command, crash=crash)
        except FixtureCrash:
            pass
        f.clock.advance(2)
        accepted = f.timeout_next(command)
        return f, command, accepted

    def evaluate(self, f, command):
        before = f.unit.snapshot(), f.provider.snapshot()
        result = f.service.evaluate(f.request, f.scope, f.context, command.execution_id, permission=True)
        self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))
        self.assertFalse(result.decision_authority)
        self.assertFalse(result.automatic_dispatch)
        f.assert_history()
        return result

    def test_independent_success_and_rejection_for_both_next_steps_read_only(self):
        for prefix in (1, 2):
            for outcome in ('SUCCESS', 'REJECTED'):
                with self.subTest(prefix=prefix, outcome=outcome):
                    f, command, accepted = self.prepare(prefix=prefix, outcome=outcome)
                    result = self.evaluate(f, command)
                    self.assertEqual(result.status, 'CONFIRMED_SUCCESS' if outcome == 'SUCCESS' else 'CONFIRMED_REJECTION')
                    ref = accepted.reconciliation_reference
                    for field in ('tenant_id', 'subscriber_id', 'execution_id', 'event_id', 'attempt_id',
                                  'plan_hash', 'fencing_token', 'owner_revision', 'receipt_fingerprint'):
                        self.assertEqual(getattr(result, field), getattr(ref, field))
                    self.assertEqual(result.version, ref.evaluation_contract)
                    self.assertEqual(result.reference_version, ref.version)
                    self.assertNotEqual(result.execution_id, f.command.execution_id)
                    self.assertEqual(f.unit.snapshot()['executor_accepted'][command.execution_id], accepted)

    def test_evaluation_does_not_issue_and_explicit_issue_permission_is_required(self):
        f, command, _ = self.prepare()
        result = self.evaluate(f, command)
        before = f.unit.snapshot(), f.provider.snapshot()
        self.assertNotIn(UUID(int=9900), f.unit._state['executor_decision_authorizations'])
        with self.assertRaises(PermissionError):
            f.service.issue(f.request, f.scope, f.context.model_copy(update={'can_issue_decision': False}), result,
                ExecutorDecisionIntent(authorization_id=UUID(int=9900), decision='CONFIRM_SUCCESS'), permission=True)
        self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))

    def test_reference_fields_and_versions_fail_closed(self):
        f, command, accepted = self.prepare()
        ref = accepted.reconciliation_reference
        changes = {name: UUID(int=9999) for name in ('execution_id', 'previous_execution_id', 'decision_id', 'next_step_id', 'event_id', 'attempt_id', 'request_id')}
        changes.update({name: 'wrong' for name in ('tenant_id', 'subscriber_id', 'plan_hash', 'continue_plan_hash', 'prior_evidence_fingerprint', 'provider_evidence_fingerprint', 'receipt_fingerprint', 'version', 'execution_plan_contract', 'evaluation_contract')})
        changes.update({name: 999 for name in ('owner_revision', 'fencing_token', 'owner_fence')})
        for field, value in changes.items():
            with self.subTest(field=field):
                f.unit._state['executor_accepted'][command.execution_id] = accepted.model_copy(update={
                    'reconciliation_reference': ref.model_copy(update={field: value})})
                self.assertEqual(self.evaluate(f, command).status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        f.unit._state['executor_accepted'][command.execution_id] = accepted.model_copy(update={'reconciliation_reference': None})
        self.assertEqual(self.evaluate(f, command).status, 'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_missing_unknown_or_wrong_step_provider_receipt_fail_closed(self):
        for kind in ('MISSING', 'UNKNOWN', 'WRONG_STEP', 'HASH', 'VERSION'):
            with self.subTest(kind=kind):
                f, command, _ = self.prepare(outcome='UNKNOWN' if kind == 'UNKNOWN' else 'SUCCESS')
                receipts = f.provider._state['executor_receipts']
                if kind == 'MISSING':
                    del receipts[command.execution_id]
                elif kind != 'UNKNOWN':
                    change = {'WRONG_STEP': {'execution_id': f.command.execution_id},
                              'HASH': {'provider_evidence_fingerprint': '0'*64},
                              'VERSION': {'receipt_version': 'wrong'}}[kind]
                    receipts[command.execution_id] = receipts[command.execution_id].model_copy(update=change)
                self.assertEqual(self.evaluate(f, command).status, 'READ_ONLY_RECONCILIATION_REQUIRED')

    def test_cas_fencing_provider_and_prior_history_drift_fail_closed(self):
        for kind in ('OWNER', 'FENCE', 'PROVIDER', 'DECISION', 'POLICY', 'AUDIT', 'OUTBOX'):
            with self.subTest(kind=kind):
                f, command, _ = self.prepare()
                state = f.unit._state
                if kind == 'OWNER':
                    key = next(iter(state['owners']))
                    state['owners'][key] = state['owners'][key].model_copy(update={'revision': 999})
                elif kind == 'FENCE':
                    f.provider._state['highest'] = (command.owner_fence, command.fencing_token + 1)
                elif kind == 'PROVIDER':
                    current = f.provider._state['provider']
                    f.provider._state['provider'] = current.model_copy(update={'generation': current.generation+1})
                elif kind == 'DECISION':
                    del state['executor_decision_records'][f.decision.authorization_id]
                elif kind == 'POLICY':
                    del state['executor_policy_authorizations'][f.continued.authorization_id]
                elif kind == 'AUDIT':
                    state['executor_audit'] = [r for r in state['executor_audit'] if r[0] != command.execution_id]
                else:
                    key = next(iter(state['outbox']))
                    state['outbox'][key] = state['outbox'][key][:-1]
                before = f.unit.snapshot(), f.provider.snapshot()
                result = f.service.evaluate(f.request, f.scope, f.context, command.execution_id, permission=True)
                self.assertEqual(result.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
                self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))

    def test_scope_permission_and_foreign_reader_deny_without_mutation(self):
        f, command, _ = self.prepare()
        for context in (f.context.model_copy(update={'can_evaluate': False}),
                        f.context.model_copy(update={'tenant_id': 'foreign'})):
            before = f.unit.snapshot(), f.provider.snapshot()
            with self.assertRaises(PermissionError):
                f.service.evaluate(f.request, f.scope, context, command.execution_id, permission=True)
            self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))
        from app.simulation.aaa_provider import FakeFencedProvider
        foreign = FakeFencedProvider(f.root)
        foreign._state = deepcopy(f.provider._state)
        reader = ExecutorReconciliationService(f.unit, foreign, initialize=False)
        before = f.unit.snapshot(), foreign.snapshot()
        result = reader.evaluate(f.request, f.scope, f.context, command.execution_id, permission=True)
        self.assertEqual(result.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        self.assertEqual(before, (f.unit.snapshot(), foreign.snapshot()))

    def test_lost_dispatch_and_old_execution_cannot_confirm_new_step(self):
        f, command, _ = self.prepare(crash='AFTER_DISPATCH')
        self.assertEqual(self.evaluate(f, command).status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        before = f.unit.snapshot(), f.provider.snapshot()
        old = f.service.evaluate(f.request, f.scope, f.context, f.command.execution_id, permission=True)
        self.assertEqual(old.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))

    def test_staging_and_prior_receipt_tampering_rejected(self):
        for kind in ('STAGED', 'STAGE_AUDIT', 'PRIOR_UNKNOWN', 'PREVIOUS_RECEIPT', 'GRANT_VERSION'):
            with self.subTest(kind=kind):
                f, command, _ = self.prepare()
                state = f.unit._state
                if kind == 'STAGED':
                    record = state['execution_records'][command.execution_id]
                    state['execution_records'][command.execution_id] = record.model_copy(update={'owner_revision': 999})
                elif kind == 'STAGE_AUDIT':
                    state['audit'] = state['audit'][:-2] + state['audit'][-1:]
                elif kind == 'PRIOR_UNKNOWN':
                    old = state['executor_accepted'][f.command.execution_id]
                    state['executor_accepted'][f.command.execution_id] = old.model_copy(update={'receipt': old.receipt.model_copy(update={'outcome': 'SUCCESS'})})
                elif kind == 'PREVIOUS_RECEIPT':
                    del f.provider._state['executor_receipts'][f.command.execution_id]
                else:
                    grant = state['execution_authorizations'][command.execution_id]
                    state['execution_authorizations'][command.execution_id] = grant.model_copy(update={'version': 'wrong'})
                before = f.unit.snapshot(), f.provider.snapshot()
                result = f.service.evaluate(f.request, f.scope, f.context, command.execution_id, permission=True)
                self.assertEqual(result.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
                self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))

    def test_repeat_evaluation_stable_and_missing_registry_not_initialized(self):
        f, command, _ = self.prepare()
        first = self.evaluate(f, command)
        second = self.evaluate(f, command)
        self.assertEqual(first, second)
        del f.unit._state['executor_policy_records']
        before = f.unit.snapshot(), f.provider.snapshot()
        result = f.service.evaluate(f.request, f.scope, f.context, command.execution_id, permission=True)
        self.assertEqual(result.status, 'READ_ONLY_RECONCILIATION_REQUIRED')
        self.assertEqual(before, (f.unit.snapshot(), f.provider.snapshot()))
