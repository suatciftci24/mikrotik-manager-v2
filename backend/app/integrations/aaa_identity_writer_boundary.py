"""Unwired, fail-closed AAA identity/writer preparation.

No session cookie, FastAPI route, database connection or live writer.
All authorization data must come from explicitly injected trusted readers.
"""
from dataclasses import dataclass
from typing import Callable

from app.simulation.aaa_atomic import AtomicRequest


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

        # Keep the original typed request for trusted readers and the bridge.
        # This projection only binds the existing identity/owner decision.
        if type(request) is AtomicRequest:
            request = AtomicRequest.model_validate_json(request.model_dump_json())
            binding = {
                'actor_id': request.actor_id,
                'tenant_id': request.plan.tenant_id,
                'subscriber_id': request.plan.snapshot.reference.account_id,
                'router_id': request.plan.snapshot.nas.router_id,
            }
            if request.plan.snapshot.reference.store != 'PERSISTENT_WORKSPACE':
                raise PermissionError('AAA_PERSISTENT_OWNER_REQUIRED')
        elif type(request) is dict:
            binding = request
        else:
            raise PermissionError("AAA_REQUEST_REQUIRED")
        if binding.get("actor_id") != actor_id:
            raise PermissionError("AAA_ACTOR_MISMATCH")

        permission = self.authorization_reader(session_handle, request)
        if permission is not True:
            raise PermissionError("AAA_EXPLICIT_PERMISSION_REQUIRED")

        owner = self.owner_reader(request)
        if type(owner) is not dict:
            raise PermissionError("AAA_OWNER_REQUIRED")

        for field in ("tenant_id", "subscriber_id", "router_id"):
            value = binding.get(field)
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
            "tenant_id": binding["tenant_id"],
            "subscriber_id": binding["subscriber_id"],
            "router_id": binding["router_id"],
        }

    def execute(self, *args, **kwargs):
        raise AaaBoundaryDisabled("AAA_REAL_IDENTITY_WRITER_NOT_ENABLED")
