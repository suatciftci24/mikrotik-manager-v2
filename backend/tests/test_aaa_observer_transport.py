"""Offline Remote Observer transport safety acceptance."""
from datetime import datetime, timedelta, timezone
import secrets
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from pydantic import SecretBytes
from app.integrations.aaa_observer_transport import ObserverTransport
from app.integrations.aaa_remote_observer import (
    ObservationChallenge, SyntheticRemoteObserver, RemoteEvidenceVerifier,
)
from app.repositories.aaa_reconciliation import RemoteObservation


class ObserverTransportTests(TestCase):
    def setUp(self):
        for name in ("socket.socket", "socket.create_connection", "psycopg.connect"):
            self.enterContext(patch(name, side_effect=AssertionError("NETWORK_FORBIDDEN")))
        self.now = datetime.now(timezone.utc)
        self.challenge = ObservationChallenge(
            evaluation_id=uuid4(), execution_id=uuid4(), tenant_id=uuid4(),
            operation_id=uuid4(), subscriber_id="fixture-sub",
            router_id="fixture-router", plan_hash="a"*64,
            dispatch_fingerprint="b"*64, owner_revision=1, fence=1,
            requested_at=self.now, deadline=self.now+timedelta(seconds=5))
        observation = RemoteObservation(
            **self.challenge.model_dump(exclude={
                "evaluation_id", "requested_at", "deadline"}),
            sequence=1, observed_at=self.now,
            valid_until=self.now+timedelta(seconds=20), outcome="APPLIED")
        key = SecretBytes(secrets.token_bytes(32))
        options = dict(key=key, source_identity="fixture-observer-radius3", source_revision=1)
        synthetic_observe = SyntheticRemoteObserver(
            [observation], **options
        ).observe
        self.reader = Mock(
            side_effect=lambda challenge, remaining_seconds:
                synthetic_observe(challenge)
        )
        self.verifier = RemoteEvidenceVerifier(**options)

    def test_valid_signed_evidence(self):
        result = ObserverTransport(self.reader, self.verifier).observe(
            self.challenge, self.now)
        self.assertEqual(result.status, "VERIFIED")
        self.assertEqual(self.reader.call_count, 1)

    def test_timeout_and_authentication_failure(self):
        for error in (TimeoutError("timeout"), PermissionError("authentication failed")):
            reader = Mock(side_effect=error)
            result = ObserverTransport(reader, self.verifier).observe(
                self.challenge, self.now)
            self.assertEqual(result.status, "UNKNOWN")
            reader.assert_called_once()

    def test_missing_or_invalid_evidence(self):
        for value in (None, {}, "invalid"):
            reader = Mock(return_value=value)
            result = ObserverTransport(reader, self.verifier).observe(
                self.challenge, self.now)
            self.assertEqual(result.status, "UNKNOWN")
            reader.assert_called_once()

    def test_invalid_signature_and_expired_challenge(self):
        evidence = self.reader(self.challenge, 5.0)
        invalid = evidence.model_copy(update={"signature": "0"*64})
        reader = Mock(return_value=invalid)
        result = ObserverTransport(reader, self.verifier).observe(
            self.challenge, self.now)
        self.assertEqual(result.status, "UNKNOWN")
        result = ObserverTransport(self.reader, self.verifier).observe(
            self.challenge, self.challenge.deadline)
        self.assertEqual(result.status, "UNKNOWN")
