"""Fail-closed identity-to-bridge contract tests. No PostgreSQL access."""
from unittest import TestCase
from unittest.mock import Mock

from app.integrations.aaa_identity_writer_boundary import (
    AaaBoundaryDisabled,
    AaaIdentityWriterBoundary,
)
from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge


class BoundaryBridgeContractTests(TestCase):
    def setUp(self):
        self.bridge = Mock(spec=PostgresFixtureBridge)
        self.user = {
            "id": "fixture-admin",
            "active": True,
            "bootstrap_closed": True,
            "login_enabled": True,
            "role_code": "ADMIN",
            "account_origin": "LOCAL",
            "can_manage_users": True,
        }
        self.request = {
            "actor_id": "fixture-admin",
            "tenant_id": "fixture-tenant",
            "subscriber_id": "fixture-subscriber",
            "router_id": "fixture-router",
        }
        self.owner = {**self.request, "source": "LOCAL"}
        self.permission = True
        self.boundary = AaaIdentityWriterBoundary(
            identity_reader=lambda _: dict(self.user),
            authorization_reader=lambda *_: self.permission,
            owner_reader=lambda _: dict(self.owner),
            writer=self.bridge.invoke,
        )

    def assert_bridge_untouched(self):
        self.bridge.assert_not_called()
        for method in (
            "invoke", "run", "read", "seed_fixture", "daily_touch"
        ):
            getattr(self.bridge, method).assert_not_called()

    def test_valid_inspection_does_not_touch_bridge(self):
        result = self.boundary.inspect("session", self.request)
        self.assertTrue(result["authorized"])
        self.assert_bridge_untouched()

    def test_invalid_identity_denies_before_bridge(self):
        self.user["active"] = False
        with self.assertRaises(PermissionError):
            self.boundary.inspect("session", self.request)
        self.assert_bridge_untouched()

    def test_revoked_permission_denies_before_bridge(self):
        self.permission = False
        with self.assertRaises(PermissionError):
            self.boundary.inspect("session", self.request)
        self.assert_bridge_untouched()

    def test_foreign_owner_denies_before_bridge(self):
        self.owner["tenant_id"] = "foreign"
        with self.assertRaises(PermissionError):
            self.boundary.inspect("session", self.request)
        self.assert_bridge_untouched()

    def test_execute_always_disabled_even_after_valid_inspection(self):
        self.boundary.inspect("session", self.request)
        with self.assertRaisesRegex(
            AaaBoundaryDisabled, "AAA_REAL_IDENTITY_WRITER_NOT_ENABLED"
        ):
            self.boundary.execute("session", self.request)
        self.assert_bridge_untouched()
