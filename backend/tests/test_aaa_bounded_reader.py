"""Offline-only bounded reader contract tests."""
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.integrations.aaa_bounded_reader import BoundedObserverReader


class BoundedReaderTests(unittest.TestCase):
    def setUp(self):
        from app.integrations.aaa_remote_observer import ObservationChallenge
        now = datetime.now(timezone.utc)
        self.challenge = ObservationChallenge(
            evaluation_id=uuid4(), execution_id=uuid4(),
            tenant_id=uuid4(), operation_id=uuid4(),
            subscriber_id="fixture-sub", router_id="fixture-router",
            plan_hash="a"*64, dispatch_fingerprint="b"*64,
            owner_revision=1, fence=1,
            requested_at=now, deadline=now+timedelta(seconds=5),
        )

    def test_budgets_are_forwarded(self):
        io = Mock(return_value="fixture-evidence")
        result = BoundedObserverReader(io)(
            self.challenge, 4.0)
        self.assertEqual(result, "fixture-evidence")
        budget = io.call_args.args[1]
        self.assertEqual(budget.connect_seconds, 1.0)
        self.assertEqual(budget.read_seconds, 3.0)

    def test_invalid_budget_never_calls_io(self):
        io = Mock()
        reader = BoundedObserverReader(io)
        for budget in (0, -1, 6, float("nan"), float("inf")):
            with self.assertRaises(TimeoutError):
                reader(self.challenge, budget)
        io.assert_not_called()

    def test_late_io_result_is_rejected(self):
        io = Mock(return_value="fixture-evidence")
        reader = BoundedObserverReader(io)
        with patch(
            "app.integrations.aaa_bounded_reader.time.monotonic",
            side_effect=[100.0, 106.0],
        ):
            with self.assertRaises(TimeoutError):
                reader(self.challenge, 5.0)
        io.assert_called_once()

    def test_io_failure_is_not_converted_to_success(self):
        io = Mock(side_effect=TimeoutError("connect timeout"))
        with self.assertRaises(TimeoutError):
            BoundedObserverReader(io)(self.challenge, 5.0)
        io.assert_called_once()


if __name__ == "__main__":
    unittest.main()
