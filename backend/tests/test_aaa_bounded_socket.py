"""Fixture-only bounded socket acceptance."""
import unittest
from unittest.mock import Mock, patch

from app.integrations.aaa_bounded_reader import ReaderBudget
from app.integrations.aaa_bounded_socket import BoundedSocketIO


class BoundedSocketTests(unittest.TestCase):
    def test_connect_read_and_close(self):
        connection = Mock()
        connector = Mock(return_value=connection)
        receiver = Mock(return_value="fixture-evidence")
        io = BoundedSocketIO(connector, receiver)

        with patch(
            "app.integrations.aaa_bounded_socket.time.monotonic",
            side_effect=[100.0, 100.2, 100.4],
        ):
            result = io("fixture-challenge", ReaderBudget(1.0, 3.0))

        self.assertEqual(result, "fixture-evidence")
        connector.assert_called_once_with(
            "fixture-challenge", timeout=1.0
        )
        connection.settimeout.assert_called_once_with(3.0)
        connection.close.assert_called_once()
        receiver.assert_called_once()

    def test_connect_timeout_closes_no_connection(self):
        connector = Mock(side_effect=TimeoutError("connect timeout"))
        receiver = Mock()
        with self.assertRaises(TimeoutError):
            BoundedSocketIO(connector, receiver)(
                "fixture", ReaderBudget(1.0, 3.0)
            )
        receiver.assert_not_called()

    def test_read_timeout_closes_connection(self):
        connection = Mock()
        receiver = Mock(side_effect=TimeoutError("read timeout"))
        with self.assertRaises(TimeoutError):
            BoundedSocketIO(Mock(return_value=connection), receiver)(
                "fixture", ReaderBudget(1.0, 3.0)
            )
        connection.close.assert_called_once()

    def test_invalid_budget_never_connects(self):
        connector = Mock()
        io = BoundedSocketIO(connector, Mock())
        for budget in (
            ReaderBudget(0, 1),
            ReaderBudget(1, -1),
            ReaderBudget(float("nan"), 1),
            ReaderBudget(1, float("inf")),
        ):
            with self.assertRaises(TimeoutError):
                io("fixture", budget)
        connector.assert_not_called()

    def test_late_response_rejected_and_closed(self):
        connection = Mock()
        with patch(
            "app.integrations.aaa_bounded_socket.time.monotonic",
            side_effect=[100.0, 100.1, 105.0],
        ):
            with self.assertRaises(TimeoutError):
                BoundedSocketIO(
                    Mock(return_value=connection),
                    Mock(return_value="late-evidence"),
                )("fixture", ReaderBudget(1.0, 3.0))
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
