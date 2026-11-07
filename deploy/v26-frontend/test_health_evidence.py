"""Only new private failure evidence / rollback cases, synthetic temporary trees."""
import json
from unittest import TestCase
import test_update as fixtures
u = fixtures.u


class HealthEvidenceTests(TestCase):
    setUp = fixtures.UpdateTests.setUp

    def test_failure_captures_stack_and_rollback_without_secret_or_false_pass(self):
        u.apply(self.target, self.bundle, self.backup)
        def fail():
            raise AssertionError('SYNTHETIC_PASSWORD_COOKIE_CANARY')
        with self.assertRaisesRegex(ValueError, 'FAILED_ROLLBACK_VERIFIED'):
            u.accept_health_or_rollback(self.target, self.bundle, self.backup, fail)
        failure = json.loads((self.backup / 'health-failure.json').read_text())
        result = json.loads((self.backup / 'health-rollback.json').read_text())
        self.assertEqual(failure['status'], 'FAIL')
        self.assertEqual(failure['error_type'], 'AssertionError')
        self.assertTrue(failure['stack'])
        self.assertEqual(result['status'], 'ROLLBACK_VERIFIED')
        self.assertEqual(result['acceptance'], 'FAIL')
        for name in ('health-failure.json', 'health-rollback.json'):
            path = self.backup / name
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('SYNTHETIC_PASSWORD_COOKIE_CANARY', path.read_text())
        self.assertEqual(u.inputs(self.target), u.inputs(self.base))
        self.assertEqual(u.tree(self.target / 'dist'), u.tree(self.base / 'dist'))

    def test_existing_evidence_never_overwritten_and_cannot_skip_rollback(self):
        u.apply(self.target, self.bundle, self.backup)
        (self.backup / 'health-failure.json').write_text('previous evidence')
        with self.assertRaisesRegex(ValueError, 'ROLLBACK_VERIFIED_EVIDENCE_BLOCKED'):
            u.accept_health_or_rollback(self.target, self.bundle, self.backup, lambda: False)
        self.assertEqual((self.backup / 'health-failure.json').read_text(), 'previous evidence')
        self.assertEqual(u.inputs(self.target), u.inputs(self.base))
        self.assertEqual(u.tree(self.target / 'dist'), u.tree(self.base / 'dist'))

    def test_drift_is_recorded_as_blocked_and_operator_edit_kept(self):
        u.apply(self.target, self.bundle, self.backup)
        def fail():
            (self.target / 'src/keep.ts').write_text('operator change')
            return False
        with self.assertRaisesRegex(ValueError, 'FAILED_ROLLBACK_BLOCKED'):
            u.accept_health_or_rollback(self.target, self.bundle, self.backup, fail)
        result = json.loads((self.backup / 'health-rollback.json').read_text())
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['acceptance'], 'FAIL')
        self.assertEqual((self.target / 'src/keep.ts').read_text(), 'operator change')
