"""Offline-only bounded observer reader adapter. No network IO."""
from dataclasses import dataclass
from typing import Callable
import time

from app.integrations.aaa_remote_observer import ObservationChallenge


@dataclass(frozen=True)
class ReaderBudget:
    connect_seconds: float
    read_seconds: float


class BoundedObserverReader:
    """Injects explicit IO budgets; underlying IO must enforce them."""

    def __init__(self, io: Callable, *, connect_cap=1.0):
        if not callable(io) or not 0 < connect_cap <= 5:
            raise ValueError("INVALID_BOUNDED_READER")
        self._io = io
        self._connect_cap = connect_cap

    def __call__(self, challenge: ObservationChallenge, remaining_seconds: float):
        if (
            type(challenge) is not ObservationChallenge
            or not isinstance(remaining_seconds, (int, float))
            or not 0 < remaining_seconds <= 5
        ):
            raise TimeoutError("INVALID_IO_BUDGET")

        started = time.monotonic()
        connect = min(self._connect_cap, remaining_seconds / 2)
        read = remaining_seconds - connect
        if read <= 0:
            raise TimeoutError("IO_BUDGET_EXHAUSTED")

        result = self._io(
            challenge,
            ReaderBudget(connect_seconds=connect, read_seconds=read),
        )
        if time.monotonic() - started >= remaining_seconds:
            raise TimeoutError("IO_BUDGET_EXHAUSTED")
        return result
