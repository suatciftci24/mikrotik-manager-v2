"""Offline acceptance for fixture-only observer key lifecycle."""
from datetime import datetime, timedelta, timezone
import secrets
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretBytes
from app.integrations.aaa_observer_keyring import FixtureObserverKey, FixtureObserverKeyring
from app.integrations.aaa_remote_observer import ObservationChallenge, SyntheticRemoteObserver
from app.repositories.aaa_reconciliation import RemoteObservation


class FixtureObserverKeyringTests(TestCase):
    def setUp(self):
        for name in ("socket.socket", "socket.create_connection", "psycopg.connect"):
            self.enterContext(patch(name, side_effect=AssertionError("NETWORK_FORBIDDEN")))
        self.now = datetime.now(timezone.utc)
        self.challenge = ObservationChallenge(
            evaluation_id=uuid4(), execution_id=uuid4(), tenant_id=uuid4(),
            operation_id=uuid4(), subscriber_id="fixture-sub", router_id="fixture-router",
            plan_hash="a"*64, dispatch_fingerprint="b"*64,
            owner_revision=1, fence=1, requested_at=self.now,
            deadline=self.now+timedelta(seconds=5))
        self.observation = RemoteObservation(
            **self.challenge.model_dump(exclude={"evaluation_id", "requested_at", "deadline"}),
            sequence=1, observed_at=self.now,
            valid_until=self.now+timedelta(seconds=20), outcome="APPLIED")
        self.old = FixtureObserverKey(
            "old", SecretBytes(secrets.token_bytes(32)), "fixture-observer-radius3", 1)
        self.new = FixtureObserverKey(
            "new", SecretBytes(secrets.token_bytes(32)), "fixture-observer-radius3", 2)

    def signed(self, item):
        return SyntheticRemoteObserver(
            [self.observation], key=item.key,
            source_identity=item.source_identity,
            source_revision=item.source_revision).observe(self.challenge)

    def test_rotation_and_revocation(self):
        ring = FixtureObserverKeyring([self.old, self.new])
        self.assertIsNotNone(ring.verify("old", self.signed(self.old), self.challenge, self.now))
        self.assertIsNotNone(ring.verify("new", self.signed(self.new), self.challenge, self.now))
        self.assertIsNone(ring.verify("new", self.signed(self.old), self.challenge, self.now))
        revoked = FixtureObserverKey(
            self.old.key_id, self.old.key, self.old.source_identity,
            self.old.source_revision, revoked=True)
        ring = FixtureObserverKeyring([revoked, self.new])
        self.assertIsNone(ring.verify("old", self.signed(self.old), self.challenge, self.now))
        self.assertIsNotNone(ring.verify("new", self.signed(self.new), self.challenge, self.now))

    def test_unknown_duplicate_and_invalid_keys(self):
        ring = FixtureObserverKeyring([self.old])
        self.assertIsNone(ring.verify("unknown", self.signed(self.old), self.challenge, self.now))
        with self.assertRaises(ValueError):
            FixtureObserverKeyring([self.old, self.old])
        with self.assertRaises(ValueError):
            FixtureObserverKeyring([FixtureObserverKey(
                "short", SecretBytes(b"short"), "fixture-observer-radius3", 1)])
