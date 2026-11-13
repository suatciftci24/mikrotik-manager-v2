"""Unwired, fail-closed AAA identity/writer preparation.

No session cookie, FastAPI route, database connection or live writer.
All authorization data must come from explicitly injected trusted readers.
"""
from dataclasses import dataclass
from typing import Callable


class AaaBoundaryDisabled(PermissionError):
    pass


@dataclass(frozen=True)
class AaaIdentityWriterBoundary:
    identity_reader: Callable
    authorization_reader: Callable
    owner_reader: Callable
    writer: Callable

    def inspect(self, session_handle, request):
        """Read-only authorization decision; never invokes writer."""
        user = self.identity_reader(session_handle)
        if type(user) is not dict:
            raise PermissionError("AAA_FRESH_IDENTITY_REQUIRED")
        if (
            user.get("active") is not True
            or user.get("bootstrap_closed") is not True
            or user.get("login_enabled") is not True
            or user.get("role_code") != "ADMIN"
            or user.get("account_origin") != "LOCAL"
            or user.get("can_manage_users") is not True
        ):
            raise PermissionError("AAA_SEALED_ADMIN_REQUIRED")

        actor_id = user.get("id")
        if type(actor_id) is not str or not actor_id:
            raise PermissionError("AAA_ACTOR_REQUIRED")

        if type(request) is not dict:
            raise PermissionError("AAA_REQUEST_REQUIRED")
        if request.get("actor_id") != actor_id:
            raise PermissionError("AAA_ACTOR_MISMATCH")

        permission = self.authorization_reader(session_handle, request)
        if permission is not True:
            raise PermissionError("AAA_EXPLICIT_PERMISSION_REQUIRED")

        owner = self.owner_reader(request)
        if type(owner) is not dict:
            raise PermissionError("AAA_OWNER_REQUIRED")

        for field in ("tenant_id", "subscriber_id", "router_id"):
            value = request.get(field)
            if type(value) is not str or not value:
                raise PermissionError("AAA_SCOPE_REQUIRED")
            if owner.get(field) != value:
                raise PermissionError("AAA_OWNER_SCOPE_CONFLICT")

        if owner.get("actor_id") != actor_id:
            raise PermissionError("AAA_OWNER_ACTOR_CONFLICT")
        if owner.get("source") != "LOCAL":
            raise PermissionError("AAA_LOCAL_OWNER_REQUIRED")

        return {
            "authorized": True,
            "actor_id": actor_id,
            "tenant_id": request["tenant_id"],
            "subscriber_id": request["subscriber_id"],
            "router_id": request["router_id"],
        }

    def execute(self, *args, **kwargs):
        raise AaaBoundaryDisabled("AAA_REAL_IDENTITY_WRITER_NOT_ENABLED")
