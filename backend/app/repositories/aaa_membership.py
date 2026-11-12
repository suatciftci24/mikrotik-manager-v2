"""Same-session, fail-closed resolver port. No engine, schema or login fallback."""
from typing import Literal
from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.repositories.aaa_owner_contract import OwnerScope, OwnershipGrant


class ServerPrincipal(ReadContract):
    actor_id: str = Field(min_length=1)
    deployment: str = Field(min_length=1)
    origin: Literal['LOCAL'] = 'LOCAL'


class MembershipProof(ReadContract):
    version: Literal['AAA_MEMBERSHIP_PROOF_V1'] = 'AAA_MEMBERSHIP_PROOF_V1'
    grant: OwnershipGrant
    actor_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    deployment: str
    capability: str


class SessionMembershipResolver:
    """Readers MUST lock actor then membership on the supplied UoW session.

    Principal is supplied by trusted server authentication, never client JSON.
    Readers/target guard have no defaults; missing identity metadata denies.
    """
    def __init__(self, *, deployment, target_guard, actor_reader, membership_reader):
        if not deployment or not all(callable(x) for x in (target_guard, actor_reader, membership_reader)):
            raise TypeError('EXPLICIT_TRUSTED_MEMBERSHIP_DEPENDENCIES_REQUIRED')
        self.deployment = deployment
        self.target_guard, self.actor_reader, self.membership_reader = target_guard, actor_reader, membership_reader

    def resolve(self, session, principal, scope, capability):
        if (type(principal) is not ServerPrincipal or type(scope) is not OwnerScope
                or principal.actor_id != scope.actor_id or principal.origin != 'LOCAL'
                or principal.deployment != self.deployment or self.target_guard(session) is not True):
            raise PermissionError('TRUSTED_PRINCIPAL_AND_TARGET_REQUIRED')
        actor = self.actor_reader(session, principal.actor_id)
        member = self.membership_reader(session, scope)
        if (not actor or not member or actor.get('actor_id') != scope.actor_id
                or actor.get('active') is not True or actor.get('origin') != 'LOCAL'
                or actor.get('role') not in ('ADMIN', 'OPERATOR')
                or actor.get('deployment') != self.deployment
                or member.get('deployment') != self.deployment
                or member.get('tenant_id') != scope.tenant_id or member.get('actor_id') != scope.actor_id
                or member.get('subscriber_id') != scope.subscriber_id or member.get('active') is not True
                or any(type(row.get(key)) is not int or row[key] < 1 for row, key in
                       ((actor, 'revision'), (member, 'revision'), (member, 'policy_revision')))
                or type(member.get('capabilities')) not in (list, tuple)
                or capability not in member['capabilities']):
            raise PermissionError('FRESH_ACTOR_MEMBERSHIP_POLICY_REQUIRED')
        owner_capability = 'DAILY_OWNER' if capability == 'DAILY_OWNER' else 'AAA_METADATA'
        if owner_capability not in member['capabilities']:
            raise PermissionError('OWNER_CAPABILITY_REQUIRED')
        grant = OwnershipGrant(**scope.model_dump(), actor_active=True, membership_revision=member['revision'],
                               capabilities=(owner_capability,))
        return MembershipProof(grant=grant, actor_revision=actor['revision'], policy_revision=member['policy_revision'],
                               deployment=self.deployment, capability=capability)
