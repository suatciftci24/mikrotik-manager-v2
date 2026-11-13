"""Fixture-only socket timeout adapter; no real network connection."""
import math
import time

from app.integrations.aaa_bounded_reader import ReaderBudget


class BoundedSocketIO:
    def __init__(self, connector, receiver):
        if not callable(connector) or not callable(receiver):
            raise TypeError("INVALID_IO_DEPENDENCIES")
        self._connector = connector
        self._receiver = receiver

    def __call__(self, challenge, budget: ReaderBudget):
        if (
            type(budget) is not ReaderBudget
            or not all(
                isinstance(v, (int, float))
                and math.isfinite(v)
                and v > 0
                for v in (budget.connect_seconds, budget.read_seconds)
            )
        ):
            raise TimeoutError("INVALID_IO_BUDGET")

        deadline = time.monotonic() + (
            budget.connect_seconds + budget.read_seconds
        )
        connection = None
        try:
            connection = self._connector(
                challenge, timeout=budget.connect_seconds
            )
            if connection is None:
                raise ConnectionError("NO_CONNECTION")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("IO_BUDGET_EXHAUSTED")

            connection.settimeout(
                min(budget.read_seconds, remaining)
            )
            result = self._receiver(connection, challenge)

            if time.monotonic() >= deadline:
                raise TimeoutError("IO_BUDGET_EXHAUSTED")
            return result
        finally:
            if connection is not None:
                connection.close()
