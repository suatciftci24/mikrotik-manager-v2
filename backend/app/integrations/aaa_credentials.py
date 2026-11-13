"""Fixture reference resolution only: no secret values, store IO or live authority."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field
from app.integrations.aaa_contracts import ReadContract


class CredentialBinding(ReadContract):
    reference: str = Field(repr=False, exclude=True,
        pattern=r'^secretref:v2/aaa-fixture/[A-Za-z0-9_-]{1,64}$')
    tenant_id: UUID
    router_id: str = Field(pattern=r'^demo-managed-router-.+$')
    source: Literal['LOCAL', 'RADIUS']
    purpose: Literal['SUBSCRIBER_PASSWORD', 'ROUTER_LOGIN', 'RADIUS_SHARED_SECRET']
    revision: int = Field(ge=1)
    active: bool = True


class CredentialResolution(ReadContract):
    fixture_only: Literal[True] = True
    external_writes: Literal[False] = False
    live_ready: Literal[False] = False
    tenant_id: UUID
    router_id: str
    source: Literal['LOCAL', 'RADIUS']
    purpose: Literal['SUBSCRIBER_PASSWORD', 'ROUTER_LOGIN', 'RADIUS_SHARED_SECRET']
    revision: int
    # Deliberately no secret value or reference in the public result.


class FixtureCredentialResolver:
    def __init__(self, bindings):
        if any(type(b) is not CredentialBinding for b in bindings):
            raise PermissionError('FIXTURE_CREDENTIAL_BINDINGS_REQUIRED')
        self._bindings = tuple(CredentialBinding.model_validate(
            {k:getattr(b,k) for k in CredentialBinding.model_fields}) for b in bindings)

    def resolve(self, reference, *, tenant_id, router_id, source, purpose, revision,
                permitted=False, now, valid_until):
        # Authorization is supplied by a trusted caller; this object cannot grant it.
        if (permitted is not True or now.utcoffset() is None or valid_until.utcoffset() is None
                or not now < valid_until):
            raise PermissionError('CREDENTIAL_RESOLUTION_DENIED')
        matches = [b for b in self._bindings if b.reference == reference]
        if len(matches) != 1:
            raise PermissionError('CREDENTIAL_RESOLUTION_DENIED')
        b = matches[0]
        if (not b.active or (b.tenant_id,b.router_id,b.source,b.purpose,b.revision)
                != (tenant_id,router_id,source,purpose,revision)):
            raise PermissionError('CREDENTIAL_RESOLUTION_DENIED')
        return CredentialResolution(**{k:getattr(b,k) for k in
            ('tenant_id','router_id','source','purpose','revision')})
