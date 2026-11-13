"""Unwired read-only AAA fixture gate.

No API registration, live writer, RADIUS or router access.
Authorization must be checked before each isolated fixture read.
"""
from dataclasses import dataclass
from typing import Callable

from app.simulation.aaa_atomic import AtomicRequest
from app.integrations.aaa_contracts import PreviewScope
from app.repositories.aaa_membership import ServerPrincipal

from app.integrations.aaa_identity_writer_boundary import (
    AaaIdentityWriterBoundary,
)


@dataclass(frozen=True)
class AaaFixtureReadGate:
    boundary: AaaIdentityWriterBoundary
    bridge_reader: Callable

    def read(self, session_handle, request, scope, principal, *, expected_source='LOCAL'):

        decision = self.boundary.inspect(session_handle, request, expected_source=expected_source)

        if type(decision) is not dict or decision.get("authorized") is not True:
            raise PermissionError("AAA_AUTHORIZATION_REQUIRED")

        if type(request) is AtomicRequest:
            if type(principal) is not ServerPrincipal or type(scope) is not PreviewScope:
                raise PermissionError('AAA_TYPED_SCOPE_AND_PRINCIPAL_REQUIRED')
            if (principal.actor_id != decision['actor_id']
                    or scope.actor_id != decision['actor_id']
                    or scope.tenant_id != decision['tenant_id']
                    or scope.store != 'PERSISTENT_WORKSPACE'
                    or scope.workspace_admin is not True):
                raise PermissionError('AAA_PRINCIPAL_SCOPE_MISMATCH')
        else:
            if type(principal) is not dict:
                raise PermissionError("AAA_PRINCIPAL_REQUIRED")
            if principal.get("actor_id") != decision["actor_id"]:
                raise PermissionError("AAA_PRINCIPAL_ACTOR_MISMATCH")
            for field in ("tenant_id", "subscriber_id", "router_id"):
                if principal.get(field) != decision[field]:
                    raise PermissionError("AAA_PRINCIPAL_SCOPE_MISMATCH")

        # Mandatory same-transaction authoritative resolution inside bridge.read
        # closes the gap after the boundary's preliminary identity inspection.
        return self.bridge_reader(request, scope, principal, "AAA_READ")
