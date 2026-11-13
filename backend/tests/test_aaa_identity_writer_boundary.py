from unittest import TestCase

from app.integrations.aaa_identity_writer_boundary import (
    AaaBoundaryDisabled,
    AaaIdentityWriterBoundary,
)


class AaaIdentityWriterBoundaryTests(TestCase):
    def setUp(self):
        self.calls = []
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
        self.owner = {
            **self.request,
            "source": "LOCAL",
        }
        self.permission = True

        def identity(_):
            self.calls.append("identity")
            return dict(self.user)

        def authorization(_, __):
            self.calls.append("authorization")
            return self.permission

        def owner(_):
            self.calls.append("owner")
            return dict(self.owner)

        def writer(*args, **kwargs):
            raise AssertionError("WRITER_MUST_REMAIN_DISABLED")

        self.boundary = AaaIdentityWriterBoundary(
            identity, authorization, owner, writer
        )

    def test_explicit_read_only_inspection(self):
        result = self.boundary.inspect("fixture-session", self.request)
        self.assertTrue(result["authorized"])
        self.assertEqual(
            self.calls, ["identity", "authorization", "owner"]
        )

    def test_identity_and_admin_denied(self):
        for field, value in (
            ("active", False),
            ("bootstrap_closed", False),
            ("login_enabled", False),
            ("role_code", "OPERATOR"),
            ("account_origin", "RADIUS"),
            ("can_manage_users", False),
        ):
            with self.subTest(field=field):
                self.calls.clear()
                self.user[field] = value
                with self.assertRaises(PermissionError):
                    self.boundary.inspect("fixture-session", self.request)
                self.assertEqual(self.calls, ["identity"])
                self.user = {
                    **self.user,
                    field: (
                        True if field in (
                            "active", "bootstrap_closed",
                            "login_enabled", "can_manage_users"
                        )
                        else "ADMIN" if field == "role_code"
                        else "LOCAL"
                    ),
                }

    def test_actor_and_permission_denied(self):
        self.request["actor_id"] = "other"
        with self.assertRaises(PermissionError):
            self.boundary.inspect("fixture-session", self.request)
        self.request["actor_id"] = "fixture-admin"
        self.permission = False
        with self.assertRaises(PermissionError):
            self.boundary.inspect("fixture-session", self.request)

    def test_owner_scope_denied(self):
        for field in ("tenant_id", "subscriber_id", "router_id"):
            with self.subTest(field=field):
                self.owner[field] = "foreign"
                with self.assertRaises(PermissionError):
                    self.boundary.inspect("fixture-session", self.request)
                self.owner[field] = self.request[field]

    def test_writer_always_disabled(self):
        with self.assertRaises(AaaBoundaryDisabled):
            self.boundary.execute(self.request)
        self.assertEqual(self.calls, [])
