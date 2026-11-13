"""Offline security acceptance for fixture observer key selection."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import secrets
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretBytes
from app.integrations.aaa_observer_keyring import (
    FixtureObserverKey, FixtureObserverKeyring)
from app.integrations.aaa_remote_observer import (
    ObservationChallenge, SyntheticRemoteObserver)
from app.repositories.aaa_reconciliation import RemoteObservation


class ObserverKeyringSecurityTests(TestCase):
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
        self.observation = RemoteObservation(
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

    def signed(self, item):
        return SyntheticRemoteObserver(
            [self.observation], key=item.key,
            source_identity=item.source_identity,
            source_revision=item.source_revision
        ).observe(self.challenge)

    def test_key_id_substitution_rejected(self):
        ring = FixtureObserverKeyring([self.old, self.new])
        evidence = self.signed(self.old)
        self.assertIsNotNone(
            ring.verify("old", evidence, self.challenge, self.now))
        self.assertIsNone(
            ring.verify("new", evidence, self.challenge, self.now))

    def test_revoked_key_and_unknown_key_rejected(self):
        revoked = replace(self.old, revoked=True)
        ring = FixtureObserverKeyring([revoked, self.new])
        evidence = self.signed(self.old)
        self.assertIsNone(
            ring.verify("old", evidence, self.challenge, self.now))
        self.assertIsNone(
            ring.verify("missing", evidence, self.challenge, self.now))

    def test_wrong_signing_key_rejected(self):
        impostor = replace(
            self.old, key=SecretBytes(secrets.token_bytes(32)))
        ring = FixtureObserverKeyring([self.old])
        self.assertIsNone(
            ring.verify("old", self.signed(impostor),
                        self.challenge, self.now))

    def test_new_key_still_accepted(self):
        ring = FixtureObserverKeyring([
            replace(self.old, revoked=True), self.new])
        self.assertIsNotNone(
            ring.verify("new", self.signed(self.new),
                        self.challenge, self.now))
