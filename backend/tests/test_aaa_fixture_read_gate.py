from unittest import TestCase
from unittest.mock import Mock

from app.integrations.aaa_fixture_read_gate import AaaFixtureReadGate
from app.integrations.aaa_identity_writer_boundary import (
    AaaIdentityWriterBoundary,
)


class AaaFixtureReadGateTests(TestCase):
    def setUp(self):
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
        self.principal = dict(self.request)
        self.permission = True
        self.reader = Mock(return_value={"fixture": True})

        boundary = AaaIdentityWriterBoundary(
            identity_reader=lambda _: dict(self.user),
            authorization_reader=lambda *_: self.permission,
            owner_reader=lambda _: dict(self.owner),
            writer=Mock(side_effect=AssertionError("WRITER_FORBIDDEN")),
        )
        self.gate = AaaFixtureReadGate(boundary, self.reader)

    def read(self):
        return self.gate.read(
            "fixture-session", self.request, "fixture-scope", self.principal
        )

    def test_authorized_read(self):
        self.assertEqual(self.read(), {"fixture": True})
        self.reader.assert_called_once_with(
            self.request, "fixture-scope", self.principal, "AAA_READ"
        )

    def test_revoked_identity_denies_before_bridge(self):
        self.user["active"] = False
        with self.assertRaises(PermissionError):
            self.read()
        self.reader.assert_not_called()

    def test_revoked_permission_denies_before_bridge(self):
        self.permission = False
        with self.assertRaises(PermissionError):
            self.read()
        self.reader.assert_not_called()

    def test_owner_change_denies_before_bridge(self):
        self.owner["subscriber_id"] = "foreign"
        with self.assertRaises(PermissionError):
            self.read()
        self.reader.assert_not_called()

    def test_principal_mismatch_denies_before_bridge(self):
        self.principal["tenant_id"] = "foreign"
        with self.assertRaises(PermissionError):
            self.read()
        self.reader.assert_not_called()
