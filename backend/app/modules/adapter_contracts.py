"""Protocol boundaries only. Phase 1 has no implementation that opens a connection."""
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from pydantic import Field, model_validator
from app.integrations.aaa_contracts import ReadContract, SubscriptionTerms
from app.simulation.aaa_integration_preparation import SyntheticAaaCommand

if TYPE_CHECKING:
    from app.simulation.aaa_integration_preparation import SyntheticAaaCommand, SyntheticAaaReceipt


@dataclass(frozen=True)
class LocalSubscriberCredential:
    router_id: str
    username: str
    secret_reference: str  # Reference to an external V2 secret store; never the password.


@dataclass(frozen=True)
class RadiusIdentity:
    username: str
    realm: str
    nas_identifier: str


class RouterOSAdapter(Protocol):
    """Future RouterOS API contract. Implementations must be injected explicitly."""
    async def health(self, router_id: str) -> dict: ...
    async def list_pppoe_sessions(self, router_id: str) -> list[dict]: ...
    async def apply_subscriber(self, command: 'SyntheticAaaCommand') -> 'SyntheticAaaReceipt':
        """CREATE/EXTEND/PLAN/STATUS: actor, tenant, router, source, CAS, UUID and audit.

        V1 is fixture-only. A live implementation MUST reject this version;
        production dispatch requires a separately accepted contract/version.
        UNKNOWN must never be retried as a new write.
        """
        ...
    async def create_local_subscriber(self, account: LocalSubscriberCredential) -> dict: ...


class FreeRadiusAdapter(Protocol):
    """Future FreeRADIUS SQL/API contract. Production credentials are forbidden in Phase 1."""
    async def health(self) -> dict: ...
    async def apply_subscriber(self, command: 'SyntheticAaaCommand') -> 'SyntheticAaaReceipt':
        """Same idempotency/CAS/receipt contract; V1 fixture input is not live authority.

        No direct SQL fallback or success on response loss. Accepting production
        commands needs an independently approved provider contract/version.
        """
        ...
    async def create_identity(self, identity: RadiusIdentity) -> dict: ...
    async def disable_identity(self, identity: RadiusIdentity) -> dict: ...


# Pure, fixture-only mapping contracts. None of these objects owns a transport.



class PasswordVerification(ReadContract):
    method: Literal['PAP', 'CHAP', 'MSCHAPV2']
    storage: Literal['CLEARTEXT_REFERENCE', 'NT_HASH_REFERENCE', 'CRYPT_REFERENCE']
    credential_reference: str = Field(repr=False, exclude=True,
        pattern=r'^secretref:v2/aaa-fixture/[A-Za-z0-9_-]{1,64}$')

    @model_validator(mode='after')
    def compatible(self):
        if (self.method == 'CHAP' and self.storage != 'CLEARTEXT_REFERENCE'
                or self.method == 'MSCHAPV2' and self.storage not in ('CLEARTEXT_REFERENCE','NT_HASH_REFERENCE')):
            raise ValueError('PASSWORD_VERIFICATION_MODEL_INCOMPATIBLE')
        return self


class AaaProfileMapping(ReadContract):
    plan: str = Field(min_length=1, max_length=120)
    profile: str = Field(pattern=r'^[A-Za-z0-9_. -]{1,120}$')
    rate_limit: str | None = Field(default=None, pattern=r'^\d+[kM]?/\d+[kM]?$')


class AaaAdapterTarget(ReadContract):
    tenant_id: UUID
    actor_id: str
    subscriber_id: str = Field(pattern=r'^demo-managed-sub-.+$')
    router_id: str = Field(pattern=r'^demo-managed-router-.+$')
    source: Literal['LOCAL', 'RADIUS']
    routeros_major: Literal[6, 7]
    freeradius_major: Literal[3] = 3
    mapping_revision: int = Field(ge=1)
    nas_identifier: str = Field(min_length=1, max_length=160)
    profiles: tuple[AaaProfileMapping, ...] = Field(min_length=1)
    routeros_record_id: str | None = Field(default=None, pattern=r'^\*[0-9A-Fa-f]+$')
    password: PasswordVerification | None = Field(default=None, repr=False, exclude=True)

    @model_validator(mode='after')
    def unique_profiles(self):
        if len({p.plan for p in self.profiles}) != len(self.profiles):
            raise ValueError('AMBIGUOUS_PROFILE_MAPPING')
        return self


class AaaAdapterProjection(ReadContract):
    fixture_only: Literal[True] = True
    external_writes: Literal[False] = False
    live_ready: Literal[False] = False
    request_id: UUID
    tenant_id: UUID
    actor_id: str
    subscriber_id: str
    router_id: str
    source: Literal['LOCAL', 'RADIUS']
    operation: Literal['CREATE', 'EXTEND', 'PLAN', 'STATUS']
    fingerprint: str
    expected_revision: int
    expected_fence: int
    mapping_revision: int
    expires_at_utc: datetime | None


def bound_adapter_command(command, target, source):
    if type(command) is not SyntheticAaaCommand or type(target) is not AaaAdapterTarget:
        raise PermissionError('EXPLICIT_TYPED_ADAPTER_BINDING_REQUIRED')
    command = SyntheticAaaCommand.model_validate_json(command.model_dump_json())
    # Revalidate without serializing excluded credential references.
    raw = {name:getattr(target,name) for name in type(target).model_fields}
    raw['profiles'] = tuple(p.model_dump() for p in target.profiles)
    if target.password is not None:
        raw['password'] = {name:getattr(target.password,name) for name in PasswordVerification.model_fields}
    target = AaaAdapterTarget.model_validate(raw)
    if (target.source != source or command.expected_source != source
            or any(getattr(command,k) != getattr(target,k) for k in ('tenant_id','actor_id','subscriber_id','router_id'))):
        raise PermissionError('ADAPTER_TENANT_ACTOR_OWNER_SOURCE_CONFLICT')
    profiles = [p for p in target.profiles if p.plan == command.after.plan]
    if len(profiles) != 1:
        raise PermissionError('EXPLICIT_PACKAGE_PROFILE_MAPPING_REQUIRED')
    return command, target, profiles[0]


def adapter_expiration(account):
    if account.expires_on is None:
        return None
    end = date.fromisoformat(account.expires_on)
    instant = datetime.combine(end + timedelta(days=1), datetime.min.time(), ZoneInfo('Europe/Istanbul')).astimezone(timezone.utc)
    return SubscriptionTerms(expires_on=end, expiration_policy='END_OF_DAY_INCLUSIVE', expires_at_utc=instant).expires_at_utc


def adapter_envelope(command, target):
    return dict(request_id=command.request_id,tenant_id=command.tenant_id,actor_id=command.actor_id,
        subscriber_id=command.subscriber_id,router_id=command.router_id,source=command.expected_source,
        operation=command.operation,fingerprint=command.fingerprint(),expected_revision=command.expected_revision,
        expected_fence=command.expected_fence,mapping_revision=target.mapping_revision,
        expires_at_utc=adapter_expiration(command.after))
