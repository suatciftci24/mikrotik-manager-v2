"""Unwired read-only AAA fixture gate.

No API registration, live writer, RADIUS or router access.
Authorization must be checked before each isolated fixture read.
"""
from dataclasses import dataclass
from typing import Callable

from app.integrations.aaa_identity_writer_boundary import (
    AaaIdentityWriterBoundary,
)


@dataclass(frozen=True)
class AaaFixtureReadGate:
    boundary: AaaIdentityWriterBoundary
    bridge_reader: Callable

    def read(self, session_handle, request, scope, principal):
        decision = self.boundary.inspect(session_handle, request)

        if type(decision) is not dict or decision.get("authorized") is not True:
            raise PermissionError("AAA_AUTHORIZATION_REQUIRED")

        if type(principal) is not dict:
            raise PermissionError("AAA_PRINCIPAL_REQUIRED")

        if principal.get("actor_id") != decision["actor_id"]:
            raise PermissionError("AAA_PRINCIPAL_ACTOR_MISMATCH")

        for field in ("tenant_id", "subscriber_id", "router_id"):
            if principal.get(field) != decision[field]:
                raise PermissionError("AAA_PRINCIPAL_SCOPE_MISMATCH")

        return self.bridge_reader(request, scope, principal, "AAA_READ")
