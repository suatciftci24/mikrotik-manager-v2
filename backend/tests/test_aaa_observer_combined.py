"""Combined offline AAA observer security acceptance."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import secrets
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4
from pydantic import SecretBytes

from app.integrations.aaa_observer_keyring import (
    FixtureObserverKey, FixtureObserverKeyring)
from app.integrations.aaa_observer_transport import ObserverTransport
from app.integrations.aaa_remote_observer import (
    ObservationChallenge, SyntheticRemoteObserver)
from app.repositories.aaa_reconciliation import RemoteObservation


class CombinedObserverAcceptance(TestCase):
    def setUp(self):
        for name in ("socket.socket", "socket.create_connection", "psycopg.connect"):
            self.enterContext(patch(name, side_effect=AssertionError("NETWORK_FORBIDDEN")))
        self.now = datetime.now(timezone.utc)
        self.challenge = ObservationChallenge(
            evaluation_id=uuid4(), execution_id=uuid4(),
            tenant_id=uuid4(), operation_id=uuid4(),
            subscriber_id="fixture-sub", router_id="fixture-router",
            plan_hash="a"*64, dispatch_fingerprint="b"*64,
            owner_revision=1, fence=1, requested_at=self.now,
            deadline=self.now+timedelta(seconds=5))
        observation = RemoteObservation(
            **self.challenge.model_dump(exclude={
                "evaluation_id", "requested_at", "deadline"}),
            sequence=1, observed_at=self.now,
            valid_until=self.now+timedelta(seconds=20),
            outcome="APPLIED")
        self.old = FixtureObserverKey(
            "old", SecretBytes(secrets.token_bytes(32)),
            "fixture-observer-radius3", 1)
        self.new = FixtureObserverKey(
            "new", SecretBytes(secrets.token_bytes(32)),
            "fixture-observer-radius3", 2)
        self.observation = observation

    def signed(self, item):
        return SyntheticRemoteObserver(
            [self.observation], key=item.key,
            source_identity=item.source_identity,
            source_revision=item.source_revision
        ).observe(self.challenge)

    def transport(self, reader, ring, key_id):
        class KeyVerifier:
            def verify(self, evidence, challenge, now):
                return ring.verify(key_id, evidence, challenge, now)
        return ObserverTransport(reader, KeyVerifier())

    def test_valid_new_key_after_old_revocation(self):
        ring = FixtureObserverKeyring([
            replace(self.old, revoked=True), self.new])
        reader = Mock(return_value=self.signed(self.new))
        result = self.transport(reader, ring, "new").observe(
            self.challenge, self.now)
        self.assertEqual(result.status, "VERIFIED")
        reader.assert_called_once()

    def test_revoked_and_substituted_keys_fail_closed(self):
        ring = FixtureObserverKeyring([
            replace(self.old, revoked=True), self.new])
        evidence = self.signed(self.old)
        for key_id in ("old", "new", "missing"):
            reader = Mock(return_value=evidence)
            result = self.transport(reader, ring, key_id).observe(
                self.challenge, self.now)
            self.assertEqual(result.status, "UNKNOWN")
            reader.assert_called_once()

    def test_timeout_auth_failure_and_missing_evidence(self):
        ring = FixtureObserverKeyring([self.new])
        for reader in (
            Mock(side_effect=TimeoutError("timeout")),
            Mock(side_effect=PermissionError("auth failed")),
            Mock(return_value=None),
        ):
            result = self.transport(reader, ring, "new").observe(
                self.challenge, self.now)
            self.assertEqual(result.status, "UNKNOWN")
            reader.assert_called_once()

    def test_reader_return_before_deadline_is_verified(self):
        ring = FixtureObserverKeyring([self.new])
        reader = Mock(return_value=self.signed(self.new))
        transport = self.transport(reader, ring, "new")
        with patch(
            "app.integrations.aaa_observer_transport.datetime"
        ) as clock:
            clock.now.return_value = self.now + timedelta(seconds=1)
            result = transport.observe(self.challenge, self.now)
        self.assertEqual(result.status, "VERIFIED")
        reader.assert_called_once()

    def test_reader_return_after_deadline_is_unknown(self):
        ring = FixtureObserverKeyring([self.new])
        reader = Mock(return_value=self.signed(self.new))
        transport = self.transport(reader, ring, "new")
        with patch(
            "app.integrations.aaa_observer_transport.datetime"
        ) as clock:
            clock.now.return_value = self.challenge.deadline
            result = transport.observe(self.challenge, self.now)
        self.assertEqual(result.status, "UNKNOWN")
        reader.assert_called_once()

    def test_remaining_budget_passed_to_reader(self):
        ring = FixtureObserverKeyring([self.new])
        reader = Mock(return_value=self.signed(self.new))
        result = self.transport(reader, ring, "new").observe(
            self.challenge, self.now + timedelta(seconds=2))
        self.assertEqual(result.status, "VERIFIED")
        reader.assert_called_once_with(self.challenge, 3.0)

    def test_late_reader_result_rejected(self):
        ring = FixtureObserverKeyring([self.new])
        reader = Mock(return_value=self.signed(self.new))
        transport = self.transport(reader, ring, "new")
        with patch(
            "app.integrations.aaa_observer_transport.datetime"
        ) as clock:
            clock.now.return_value = self.challenge.deadline
            result = transport.observe(self.challenge, self.now)
        self.assertEqual(result.status, "UNKNOWN")
        reader.assert_called_once_with(self.challenge, 5.0)

    def test_expired_challenge_rejected_without_success(self):
        ring = FixtureObserverKeyring([self.new])
        reader = Mock(return_value=self.signed(self.new))
        result = self.transport(reader, ring, "new").observe(
            self.challenge, self.challenge.deadline)
        self.assertEqual(result.status, "UNKNOWN")
        # Expired challenges must be rejected before invoking the reader.
        # Real network IO still requires an independently enforced timeout.
        reader.assert_not_called()
