"""Shared DI-only owner identity and CAS contract; no DB or authorization lookup."""
from typing import Literal
from uuid import UUID
from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import OwnerFixture


class OwnerScope(ReadContract):
    tenant_id: UUID
    actor_id: str = Field(min_length=1)
    subscriber_id: str = Field(min_length=1)


class OwnershipGrant(OwnerScope):
    version: Literal['AAA_OWNER_SCOPE_V1'] = 'AAA_OWNER_SCOPE_V1'
    actor_active: bool = False
    membership_revision: int = Field(ge=1)
    capabilities: tuple[Literal['AAA_METADATA', 'DAILY_OWNER'], ...] = ()


class OwnerContractConflict(ValueError):
    pass


def require_ownership(scope, grant, capability='AAA_METADATA'):
    if (type(scope) is not OwnerScope or type(grant) is not OwnershipGrant
            or grant.version != 'AAA_OWNER_SCOPE_V1' or not grant.actor_active
            or grant.membership_revision < 1 or capability not in grant.capabilities
            or (grant.tenant_id,grant.actor_id,grant.subscriber_id)
                != (scope.tenant_id,scope.actor_id,scope.subscriber_id)):
        raise PermissionError('TRUSTED_TENANT_ACTOR_OWNER_GRANT_REQUIRED')


def locked_owner(row, scope, *, operation_id, writer='AAA_METADATA', expected=None):
    if writer not in ('AAA_METADATA','DAILY_OWNER'):
        raise OwnerContractConflict('UNKNOWN_OWNER_WRITER')
    required={'tenant_id','id','revision','source','aaa_fence','aaa_active_operation'}
    if (row is None or not required.issubset(row) or row['tenant_id'] != scope.tenant_id
            or row['id'] != scope.subscriber_id or type(row['revision']) is not int or row['revision'] < 0
            or type(row['aaa_fence']) is not int or row['aaa_fence'] < 0
            or row['source'] not in ('LOCAL','RADIUS')):
        raise OwnerContractConflict('OWNER_METADATA_OR_IDENTITY_REQUIRED')
    active=row['aaa_active_operation']
    if (writer=='AAA_METADATA' and (type(operation_id) is not UUID or active != operation_id)
            or writer=='DAILY_OWNER' and (active is not None or operation_id is not None)):
        raise OwnerContractConflict('ACTIVE_OPERATION_LOCK_CONFLICT')
    current=OwnerFixture(authority=row['source'],revision=row['revision'],fence=row['aaa_fence'],active_request=active)
    if expected is not None and current != expected:
        raise OwnerContractConflict('OWNER_REVISION_OR_FENCE_CONFLICT')
    return current


def owner_cas_predicates(table, scope, expected, *, operation_id, writer='AAA_METADATA'):
    # Defense in depth: lock validation never replaces a tenant/revision/fence predicate.
    locked_owner(dict(tenant_id=scope.tenant_id,id=scope.subscriber_id,revision=expected.revision,
        source=expected.authority,aaa_fence=expected.fence,aaa_active_operation=expected.active_request),
        scope,operation_id=operation_id,writer=writer,expected=expected)
    active=(table.c.aaa_active_operation.is_(None) if writer=='DAILY_OWNER'
            else table.c.aaa_active_operation==operation_id)
    return (table.c.tenant_id==scope.tenant_id,table.c.id==scope.subscriber_id,
        table.c.revision==expected.revision,table.c.aaa_fence==expected.fence,
        table.c.source==expected.authority,active)


def require_metadata_transition(before, after, *, operation_id, writer='AAA_METADATA'):
    if (type(before) is not OwnerFixture or type(after) is not OwnerFixture
            or after.revision != before.revision+1 or after.fence != before.fence+1
            or after.authority != before.authority or after.active_request != before.active_request
            or writer not in ('AAA_METADATA','DAILY_OWNER')
            or writer=='AAA_METADATA' and (type(operation_id) is not UUID or before.active_request != operation_id)
            or writer=='DAILY_OWNER' and (operation_id is not None or before.active_request is not None)):
        raise OwnerContractConflict('MONOTONIC_METADATA_TRANSITION_REQUIRED')
