"""Versioned read projections and pure checks. No ORM, IO, adapters or write commands."""
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ConfigDict, Field, field_validator, model_validator
from app.integrations.contracts import Contract

Store = Literal['LEGACY_DEMO', 'PERSISTENT_WORKSPACE']
Authority = Literal['LOCAL', 'RADIUS', 'UNKNOWN']
AccessType = Literal['PPPOE', 'HOTSPOT', 'UNKNOWN']


class ReadContract(Contract):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, hide_input_in_errors=True)


class AccountReference(ReadContract):
    store: Store
    account_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=0)
    subscription_id: UUID | None = None
    tenant_id: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode='after')
    def existing_owner(self):
        prefix = 'demo-sub-' if self.store == 'LEGACY_DEMO' else 'demo-managed-sub-'
        if not self.account_id.startswith(prefix) or (self.store == 'PERSISTENT_WORKSPACE' and self.revision < 1):
            raise ValueError('Account reference does not match its existing store contract')
        return self


class AaaIdentity(ReadContract):
    username_raw: str | None = Field(default=None, min_length=1, max_length=96)
    realm: str | None = Field(default=None, min_length=1, max_length=160)
    normalization: Literal['UNDECIDED', 'EXACT'] = 'UNDECIDED'
    username_canonical: str | None = Field(default=None, min_length=1, max_length=96)

    @model_validator(mode='after')
    def no_implicit_normalization(self):
        if self.normalization == 'UNDECIDED' and self.username_canonical is not None:
            raise ValueError('Canonical username requires an explicit normalization policy')
        if self.normalization == 'EXACT' and (self.username_raw is None or self.username_canonical != self.username_raw):
            raise ValueError('EXACT policy cannot trim, case-fold or rewrite the username')
        return self


class NasReference(ReadContract):
    router_id: str | None = Field(default=None, min_length=1, max_length=160)
    nas_id: UUID | None = None
    nas_identifier: str | None = Field(default=None, min_length=1, max_length=160)
    mapping_revision: int | None = Field(default=None, ge=1)
    live_verification: Literal['UNVERIFIED'] = 'UNVERIFIED'


class ProfileReference(ReadContract):
    plan_id: UUID | None = None
    plan_name: str | None = Field(default=None, min_length=1, max_length=120)
    aaa_profile_id: UUID | None = None
    mapping_revision: int | None = Field(default=None, ge=1)
    attribute_policy_version: str | None = Field(default=None, min_length=1, max_length=80)
    live_verification: Literal['UNVERIFIED'] = 'UNVERIFIED'


class SubscriptionTerms(ReadContract):
    expires_on: date | None = None
    business_timezone: Literal['Europe/Istanbul'] = 'Europe/Istanbul'
    expiration_policy: Literal['UNDECIDED', 'END_OF_DAY_INCLUSIVE'] = 'UNDECIDED'
    expires_at_utc: datetime | None = None
    account_status: Literal['ACTIVE', 'PAUSED', 'PENDING', 'UNKNOWN'] = 'UNKNOWN'
    session_status: Literal['UNKNOWN'] = 'UNKNOWN'

    @field_validator('expires_at_utc')
    @classmethod
    def aware_utc(cls, value):
        if value is not None:
            if value.utcoffset() is None:
                raise ValueError('Expiry timestamp must be timezone-aware')
            return value.astimezone(timezone.utc)
        return None

    @model_validator(mode='after')
    def explicit_expiration(self):
        if self.expires_at_utc is None:
            return self
        if self.expires_on is None or self.expiration_policy != 'END_OF_DAY_INCLUSIVE':
            raise ValueError('UTC expiry requires a recorded date and explicit expiration policy')
        try:
            expected = datetime.combine(self.expires_on + timedelta(days=1), time.min,
                                        ZoneInfo(self.business_timezone)).astimezone(timezone.utc)
        except OverflowError:
            raise ValueError('Expiry is outside the supported calendar') from None
        if self.expires_at_utc != expected:
            raise ValueError('UTC expiry differs from the explicit business-day boundary')
        return self


class AaaSnapshot(ReadContract):
    version: Literal[1] = 1
    mode: Literal['SYNTHETIC_READ_ONLY'] = 'SYNTHETIC_READ_ONLY'
    reference: AccountReference
    authority: Authority
    access_type: AccessType
    identity: AaaIdentity
    nas: NasReference
    profile: ProfileReference
    terms: SubscriptionTerms
    uniqueness_policy: Literal['UNDECIDED', 'TENANT_REALM_EXACT', 'TENANT_NAS_EXACT'] = 'UNDECIDED'
    external_writes: Literal[False] = False

    @model_validator(mode='after')
    def same_reference_store(self):
        prefix = 'demo-router-' if self.reference.store == 'LEGACY_DEMO' else 'demo-managed-router-'
        if self.nas.router_id is not None and not self.nas.router_id.startswith(prefix):
            raise ValueError('Router reference differs from the existing account store')
        return self


class PreviewScope(ReadContract):
    """Trusted server-side read context, never an accepted client authorization body."""
    actor_id: str = Field(min_length=1, max_length=160)
    store: Store
    tenant_id: str | None = Field(default=None, min_length=1, max_length=80)
    readable_router_ids: tuple[str, ...] = ()
    workspace_admin: bool = False


def require_preview_scope(snapshot: AaaSnapshot, scope: PreviewScope):
    if snapshot.reference.store != scope.store or snapshot.reference.tenant_id != scope.tenant_id:
        raise PermissionError('AAA preview store access denied')
    if scope.store == 'PERSISTENT_WORKSPACE':
        if not scope.workspace_admin:
            raise PermissionError('AAA preview requires the existing central workspace administrator')
    elif snapshot.nas.router_id not in scope.readable_router_ids:
        raise PermissionError('AAA preview router access denied')


def collision_key(snapshot: AaaSnapshot):
    """None means unknown, never a proof that the namespace is collision-free."""
    ref, identity = snapshot.reference, snapshot.identity
    if not ref.tenant_id or identity.normalization != 'EXACT' or not identity.username_canonical:
        return None
    if snapshot.uniqueness_policy == 'TENANT_REALM_EXACT' and identity.realm:
        return ('TENANT_REALM_EXACT', ref.tenant_id, identity.realm, identity.username_canonical)
    if snapshot.uniqueness_policy == 'TENANT_NAS_EXACT' and snapshot.nas.nas_id:
        return ('TENANT_NAS_EXACT', ref.tenant_id, str(snapshot.nas.nas_id), identity.username_canonical)
    return None


def snapshot_fingerprint(snapshot: AaaSnapshot):
    return sha256(snapshot.model_dump_json().encode('utf-8')).hexdigest()


class PreviewProof(ReadContract):
    """Unpersisted correlation evidence; not a signed token or execution authorization."""
    request_id: UUID
    actor_id: str = Field(min_length=1, max_length=160)
    store: Store
    account_id: str = Field(min_length=1, max_length=160)
    expected_revision: int = Field(ge=0)
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    result: Literal['PREVIEW_ONLY'] = 'PREVIEW_ONLY'


def validate_preview_proof(snapshot: AaaSnapshot, scope: PreviewScope, proof: PreviewProof):
    require_preview_scope(snapshot, scope)
    if (proof.actor_id != scope.actor_id or proof.store != snapshot.reference.store
            or proof.account_id != snapshot.reference.account_id
            or proof.expected_revision != snapshot.reference.revision
            or proof.snapshot_sha256 != snapshot_fingerprint(snapshot)):
        raise ValueError('AAA preview proof is stale or does not match actor, store and account')


def compare_preview_proofs(previous: PreviewProof, incoming: PreviewProof):
    if previous.request_id != incoming.request_id:
        return 'UNRELATED'
    return 'MATCH' if previous == incoming else 'CONFLICT'


def inspect_aaa_snapshot(snapshot: AaaSnapshot, scope: PreviewScope, peers: tuple[AaaSnapshot, ...] = ()):
    """No connection or credentials accepted. All live verification remains unknown."""
    require_preview_scope(snapshot, scope)
    findings = []
    if snapshot.authority != 'LOCAL':
        findings.append('NOT_A_LOCAL_TRANSITION_CANDIDATE')
    if snapshot.access_type == 'UNKNOWN':
        findings.append('ACCESS_TYPE_UNKNOWN')
    if snapshot.reference.subscription_id is None:
        findings.append('SUBSCRIPTION_ID_UNKNOWN')
    key = collision_key(snapshot)
    if key is None:
        findings.append('NAMESPACE_POLICY_UNRESOLVED')
    for peer in peers:
        require_preview_scope(peer, scope)  # Hidden peers must not leak through risk counts.
        if peer.reference.account_id == snapshot.reference.account_id:
            findings.append('ACCOUNT_REFERENCE_REPEATED')
        elif key is not None and collision_key(peer) == key:
            findings.append('VISIBLE_NAMESPACE_CONFLICT_RISK')
    if snapshot.terms.expires_on is None or snapshot.terms.expires_at_utc is None:
        findings.append('EXPIRATION_MAPPING_UNRESOLVED')
    return {'version': 1, 'mode': 'SYNTHETIC_READ_ONLY', 'findings': tuple(dict.fromkeys(findings)),
            'snapshot_sha256': snapshot_fingerprint(snapshot), 'live_identity': 'UNVERIFIED',
            'nas_mapping': 'UNVERIFIED', 'profile_mapping': 'UNVERIFIED',
            'subscription_mapping': 'UNVERIFIED',
            'credential_reference': 'UNVERIFIED', 'aaa_write_authorization': 'UNVERIFIED',
            'external_writes': False}
