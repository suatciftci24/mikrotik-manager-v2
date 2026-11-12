"""Deadline regression checks using existing prepared memory fixture builders."""
from unittest import TestCase
from uuid import UUID

from pydantic import ValidationError
from backend.tests import test_aaa_prepared_executor as fixtures
from app.simulation.aaa_executor import AttemptIntent, ExecutorConflict, FixtureCrash


class ExecutorDeadlineTests(TestCase):
    def build(self):
        helper = fixtures.PreparedExecutorTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f = helper.setup_fixture()
        self.helper = helper
        return helper

    def snapshot(self):
        return self.f.unit.snapshot(), self.f.provider.snapshot()

    def test_tampered_attempt_lifetime_rejected_before_new_or_duplicate_claim(self):
        intent = AttemptIntent(attempt_id=UUID(int=13000))
        for duplicate in (False, True):
            for seconds in (0, -1, 301):
                with self.subTest(duplicate=duplicate, seconds=seconds):
                    helper = self.build()
                    f = self.f
                    if duplicate:
                        helper.executor.claim(f.request, f.scope, f.runner, helper.grant.authorization_id, intent, permission=True)
                    before = self.snapshot()
                    with self.assertRaises(ValidationError):
                        helper.executor.claim(f.request, f.scope, f.runner, helper.grant.authorization_id,
                                              intent.model_copy(update={'seconds': seconds}), permission=True)
                    self.assertEqual(before, self.snapshot())

    def test_valid_lifetime_boundaries_keep_prepared_authorization_cap(self):
        for seconds in (1, 300):
            with self.subTest(seconds=seconds):
                helper = self.build()
                f = self.f
                command = helper.executor.claim(f.request, f.scope, f.runner, helper.grant.authorization_id,
                    AttemptIntent(attempt_id=UUID(int=13000), seconds=seconds), permission=True)
                self.assertEqual((command.expires_at - f.clock.now()).total_seconds(), min(seconds, 60))

    def test_timeout_requires_expiry_and_preserves_late_receipt_conflict(self):
        for crash in ('AFTER_DISPATCH', 'AFTER_EFFECT', None):
            with self.subTest(crash=crash):
                helper = self.build()
                f = self.f
                command = helper.claim()
                if crash:
                    with self.assertRaises(FixtureCrash):
                        helper.run_fake(command, crash=crash)
                else:
                    helper.run_fake(command)
                f.clock.advance(29)
                before = self.snapshot()
                with self.assertRaisesRegex(ExecutorConflict, 'ATTEMPT_NOT_EXPIRED'):
                    helper.executor.timeout(f.request, f.scope, f.runner, command, permission=True)
                self.assertEqual(before, self.snapshot())
                f.clock.advance(1)
                accepted = helper.executor.timeout(f.request, f.scope, f.runner, command, permission=True)
                self.assertEqual(accepted.receipt.outcome, 'UNKNOWN')
                before = self.snapshot()
                self.assertEqual(helper.executor.timeout(f.request, f.scope, f.runner, command, permission=True), accepted)
                known = f.provider.snapshot()['executor_receipts'].get(command.execution_id)
                if known:
                    with self.assertRaises(ExecutorConflict):
                        helper.accept(known)
                self.assertEqual(before, self.snapshot())
