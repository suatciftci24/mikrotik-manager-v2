"""Offline-only Remote Observer transport boundary. No network IO."""
from dataclasses import dataclass
from typing import Callable
from app.integrations.aaa_remote_observer import (
    ObservationChallenge, SignedRemoteEvidence,
)


@dataclass(frozen=True)
class ObserverTransportResult:
    status: str
    evidence: SignedRemoteEvidence | None = None


class ObserverTransport:
    """Single-attempt, fail-closed synthetic transport."""
    def __init__(self, reader: Callable, verifier):
        if not callable(reader) or not callable(getattr(verifier, "verify", None)):
            raise TypeError("TRUSTED_OBSERVER_DEPENDENCIES_REQUIRED")
        self._reader = reader
        self._verifier = verifier

    def observe(self, challenge, now):
        if type(challenge) is not ObservationChallenge:
            return ObserverTransportResult("UNKNOWN")
        try:
            if (
                now.utcoffset() is None
                or challenge.requested_at.utcoffset() is None
                or challenge.deadline.utcoffset() is None
                or not challenge.requested_at <= now < challenge.deadline
                or (challenge.deadline - challenge.requested_at).total_seconds() > 5
            ):
                return ObserverTransportResult("UNKNOWN")
            envelope = self._reader(challenge)
            # A blocking reader must enforce its own IO deadline.
            # Never accept evidence if the reader returned too late.
            from datetime import datetime, timezone
            finished_at = datetime.now(timezone.utc)
            if finished_at >= challenge.deadline:
                return ObserverTransportResult("UNKNOWN")
            if type(envelope) is not SignedRemoteEvidence:
                return ObserverTransportResult("UNKNOWN")
            observation = self._verifier.verify(envelope, challenge, now)
            if observation is None:
                return ObserverTransportResult("UNKNOWN")
            return ObserverTransportResult("VERIFIED", envelope)
        except Exception:
            return ObserverTransportResult("UNKNOWN")
