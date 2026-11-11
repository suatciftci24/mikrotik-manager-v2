import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID
from unittest.mock import patch

from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_journal import IsolatedJournal, JournalRequest, JournalEvent, JournalConflict


class JournalTests(unittest.TestCase):
    def setUp(self):
        fixture = synthetic_request()
        self.scope, self.clock = fixture.scope, fixture.clock
        self.request = JournalRequest(tenant_id=self.scope.tenant_id, actor_id=self.scope.actor_id,
                                      request_id=UUID(int=101), correlation_id=UUID(int=102), snapshot=fixture.snapshot)
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.journal = IsolatedJournal(self.conn)
        self.journal.initialize()

    def advance(self, state, revision):
        return self.journal.advance(self.request, self.scope,
                                   JournalEvent(state=state, expected_revision=revision, at=self.clock))

    def test_replay_and_changed_payload(self):
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
            self.assertEqual(self.journal.reserve(self.request, self.scope, self.clock), ('RESERVED', 1, False))
            self.assertEqual(self.journal.reserve(self.request, self.scope, self.clock), ('RESERVED', 1, True))
            altered = JournalRequest(**{**self.request.model_dump(), 'correlation_id': UUID(int=103)})
            with self.assertRaisesRegex(JournalConflict, 'IDEMPOTENCY_CONFLICT'):
                self.journal.reserve(altered, self.scope, self.clock)
        self.assertEqual(len(self.journal.history(self.request, self.scope)), 1)

    def test_scope_and_tenant(self):
        wrong = self.scope.model_copy(update={'tenant_id': 'other'})
        with self.assertRaises(PermissionError):
            self.journal.reserve(self.request, wrong, self.clock)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM operations').fetchone()[0], 0)

    def test_account_revision_reservation(self):
        self.journal.reserve(self.request, self.scope, self.clock)
        other = JournalRequest(**{**self.request.model_dump(), 'request_id': UUID(int=104)})
        with self.assertRaisesRegex(JournalConflict, 'ACCOUNT_REVISION_ALREADY_RESERVED'):
            self.journal.reserve(other, self.scope, self.clock)

    def test_compensation_and_stale_revision(self):
        self.journal.reserve(self.request, self.scope, self.clock)
        self.advance('PLANNED', 1)
        with self.assertRaisesRegex(JournalConflict, 'OPERATION_REVISION_CONFLICT'):
            self.advance('MODELED', 1)
        self.advance('MODELED', 2)
        self.advance('COMPENSATING', 3)
        self.advance('COMPENSATED', 4)
        with self.assertRaisesRegex(JournalConflict, 'INVALID_STATE_TRANSITION'):
            self.advance('PLANNED', 5)
        history = self.journal.history(self.request, self.scope)
        self.assertEqual([r[0] for r in history], [1, 2, 3, 4, 5])
        self.assertTrue(all(r[3:] == (str(self.request.correlation_id), self.request.actor_id) for r in history))

    def test_timeout_requires_reconciliation(self):
        self.journal.reserve(self.request, self.scope, self.clock)
        self.advance('PLANNED', 1)
        self.advance('UNCERTAIN', 2)
        with self.assertRaises(JournalConflict):
            self.advance('MODELED', 3)
        self.advance('RECONCILIATION', 3)
        self.assertEqual(self.journal.reserve(self.request, self.scope, self.clock), ('RECONCILIATION', 4, True))

    def test_failed_retry_does_not_restart(self):
        self.journal.reserve(self.request, self.scope, self.clock)
        self.advance('FAILED', 1)
        self.assertEqual(self.journal.reserve(self.request, self.scope, self.clock), ('FAILED', 2, True))
        with self.assertRaises(JournalConflict):
            self.advance('PLANNED', 2)

    def test_atomic_event_failure(self):
        self.journal.reserve(self.request, self.scope, self.clock)
        self.conn.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.advance('PLANNED', 1)
        self.assertEqual(self.journal.reserve(self.request, self.scope, self.clock), ('RESERVED', 1, True))
        self.assertEqual(len(self.journal.history(self.request, self.scope)), 1)

    def test_reopen_and_concurrent_cas(self):
        with tempfile.TemporaryDirectory(prefix='aaa-journal-test-') as root:
            path = Path(root) / 'synthetic.sqlite'
            conn = sqlite3.connect(path)
            ledger = IsolatedJournal(conn)
            ledger.initialize()
            ledger.reserve(self.request, self.scope, self.clock)
            conn.close()
            def compete(_):
                connection = sqlite3.connect(path)
                try:
                    return IsolatedJournal(connection).advance(self.request, self.scope,
                        JournalEvent(state='PLANNED', expected_revision=1, at=self.clock))
                except JournalConflict:
                    return 'CONFLICT'
                finally:
                    connection.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(compete, range(2)))
            self.assertEqual(results.count(('PLANNED', 2)), 1)
            self.assertEqual(results.count('CONFLICT'), 1)
            conn = sqlite3.connect(path)
            try:
                ledger = IsolatedJournal(conn)
                self.assertEqual(ledger.reserve(self.request, self.scope, self.clock), ('PLANNED', 2, True))
                self.assertEqual(len(ledger.history(self.request, self.scope)), 2)
            finally:
                conn.close()
