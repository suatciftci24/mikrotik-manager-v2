"""Fixture-only handoff decisions. No executor, endpoint, credentials, network or DB."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, field_validator, model_validator, model_serializer
from app.integrations.aaa_contracts import ReadContract, PreviewScope, require_preview_scope, snapshot_fingerprint
from app.simulation.aaa_transition import SimulationRequest, simulate_transition

Phase = Literal['PREPARE', 'TARGET_STAGED', 'SOURCE_FENCED', 'TARGET_ENABLED', 'COMPENSATING', 'UNCERTAIN']
Action = Literal['STAGE_DISABLED_TARGET', 'FENCE_LOCAL', 'ENABLE_RADIUS', 'COMMIT_OWNER_CAS',
                 'DISABLE_RADIUS', 'RESTORE_LOCAL', 'COMPLETE_COMPENSATION', 'READ_ONLY_RECONCILIATION', 'NONE']


class FixtureGates(ReadContract):
    origin: Literal['FIXTURE_EVIDENCE_ONLY'] = 'FIXTURE_EVIDENCE_ONLY'
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    actor_id: str
    tenant_id: str
    valid_until: datetime
    namespace_revision: int = Field(ge=1)
    nas_revision: int = Field(ge=1)
    profile_revision: int = Field(ge=1)
    namespace_exclusive: bool = False
    credential_ownership_approved: bool = False
    disabled_target_supported: bool = False
    source_fencing_supported: bool = False
    atomic_owner_audit_supported: bool = False

    @field_validator('valid_until')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Aware fixture evidence expiry required')
        return value.astimezone(timezone.utc)


class PreparationRequest(ReadContract):
    preview: SimulationRequest
    gates: FixtureGates
    correlation_id: UUID
    phase: Phase
    expected_operation_revision: int = Field(ge=1)
    expected_source_revision: int = Field(ge=1)
    expected_target_revision: int = Field(ge=0)

    def fingerprint(self):
        return sha256(self.model_dump_json().encode()).hexdigest()


class FixtureObservation(ReadContract):
    origin: Literal['FAKE_ADAPTER_ONLY'] = 'FAKE_ADAPTER_ONLY'
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    namespace_revision: int = Field(ge=1)
    account_revision: int = Field(ge=0)
    source_revision: int = Field(ge=1)
    target_revision: int = Field(ge=0)
    local_state: Literal['ENABLED', 'DISABLED', 'UNKNOWN']
    radius_state: Literal['ABSENT', 'DISABLED', 'ENABLED', 'UNKNOWN']
    source_fenced: bool = False
    fence_request_id: UUID | None = None


@dataclass(frozen=True)
class FakeAaaReadAdapter:
    """Explicit immutable fixture input, never a provider or subscriber repository."""
    observation: FixtureObservation

    def read(self) -> FixtureObservation:
        return self.observation


class PreparedStep(ReadContract):
    origin: Literal['FIXTURE_PREPARATION_ONLY'] = 'FIXTURE_PREPARATION_ONLY'
    request_id: UUID
    correlation_id: UUID
    operation_revision: int
    fingerprint: str
    event_id: UUID
    action: Action
    reason: str
    live_ready: Literal[False] = False
    external_writes: Literal[False] = False


def prepare_handoff(request: PreparationRequest, trusted_scope: PreviewScope,
                    adapter: FakeAaaReadAdapter, *, fixture_transition_permission: bool = False) -> PreparedStep:
    """Recommend one step only. Permission is fixture context, never a production grant."""
    # Refuse arbitrary adapter injection: this module cannot become a live dispatcher.
    if type(adapter) is not FakeAaaReadAdapter:
        raise TypeError('Only the explicit fake read adapter is accepted')
    preview, gates = request.preview, request.gates
    snapshot = preview.snapshot
    digest = request.fingerprint()

    def result(action: Action, reason: str):
        return PreparedStep(request_id=preview.proof.request_id, correlation_id=request.correlation_id,
                            operation_revision=request.expected_operation_revision, fingerprint=digest,
                            event_id=uuid5(preview.proof.request_id, str(request.expected_operation_revision) + digest),
                            action=action, reason=reason)

    try:
        require_preview_scope(snapshot, trusted_scope)
        if trusted_scope != preview.scope or not fixture_transition_permission:
            raise PermissionError('Fixture transition scope denied')
    except PermissionError:
        return result('NONE', 'SCOPE_OR_TRANSITION_PERMISSION_DENIED')
    if (gates.actor_id != trusted_scope.actor_id or gates.tenant_id != trusted_scope.tenant_id
            or gates.snapshot_sha256 != snapshot_fingerprint(snapshot)
            or gates.valid_until <= preview.clock
            or gates.nas_revision != snapshot.nas.mapping_revision
            or gates.profile_revision != snapshot.profile.mapping_revision
            or not all((gates.namespace_exclusive, gates.credential_ownership_approved,
                        gates.disabled_target_supported, gates.source_fencing_supported,
                        gates.atomic_owner_audit_supported))):
        return result('NONE', 'MISSING_STALE_OR_MISMATCHED_FIXTURE_EVIDENCE')
    # Existing identity, namespace, NAS/profile, expiry and proof checks stay authoritative.
    if preview.fail_at != 'NONE' or simulate_transition(preview)[0].outcome != 'PASS':
        return result('NONE', 'PREVIEW_PRECONDITIONS_FAILED')
    observed = adapter.read()
    digest = sha256((digest + observed.model_dump_json()).encode()).hexdigest()
    if (observed.namespace_revision != gates.namespace_revision
            or observed.snapshot_sha256 != gates.snapshot_sha256
            or observed.account_revision != snapshot.reference.revision
            or observed.source_revision != request.expected_source_revision
            or observed.target_revision != request.expected_target_revision):
        return result('READ_ONLY_RECONCILIATION', 'REVISION_OR_OBSERVATION_CONFLICT')
    fenced = observed.source_fenced and observed.fence_request_id == preview.proof.request_id
    local, radius = observed.local_state, observed.radius_state
    if request.phase == 'UNCERTAIN' or local == 'UNKNOWN' or radius == 'UNKNOWN':
        return result('READ_ONLY_RECONCILIATION', 'UNKNOWN_EXTERNAL_RESULT')
    if local == 'ENABLED' and radius == 'ENABLED':
        return result('READ_ONLY_RECONCILIATION', 'DUAL_AUTHORITY_DETECTED')
    if request.phase == 'PREPARE' and (local, radius) == ('ENABLED', 'ABSENT'):
        return result('STAGE_DISABLED_TARGET', 'TARGET_MUST_REMAIN_DISABLED')
    if request.phase == 'TARGET_STAGED' and (local, radius) == ('ENABLED', 'DISABLED'):
        return result('FENCE_LOCAL', 'VERIFY_LOCAL_DISABLED_BEFORE_TARGET_ACTIVATION')
    if fenced and (local, radius) == ('DISABLED', 'DISABLED'):
        if request.phase == 'SOURCE_FENCED':
            return result('ENABLE_RADIUS', 'SOURCE_DISABLED_AND_FENCED_IN_FIXTURE')
        if request.phase == 'COMPENSATING':
            return result('RESTORE_LOCAL', 'TARGET_DISABLED_AND_REVISION_CHECKED_IN_FIXTURE')
    if (local, radius) == ('DISABLED', 'ENABLED') and fenced:
        if request.phase == 'TARGET_ENABLED':
            return result('COMMIT_OWNER_CAS', 'OWNER_REVISION_AND_AUDIT_MUST_COMMIT_ATOMICALLY')
        if request.phase == 'COMPENSATING':
            return result('DISABLE_RADIUS', 'VERIFY_TARGET_DISABLED_BEFORE_LOCAL_RESTORE')
    if request.phase == 'COMPENSATING' and (local, radius) == ('ENABLED', 'DISABLED'):
        return result('COMPLETE_COMPENSATION', 'MONOTONIC_OWNER_REVISION_REQUIRED')
    return result('READ_ONLY_RECONCILIATION', 'UNSAFE_PHASE_OR_MISSING_FENCE')


def compare_prepared_steps(previous: PreparedStep, incoming: PreparedStep):
    """Content comparison only; no persistent receipt or execution guarantee."""
    if previous.request_id != incoming.request_id:
        return 'UNRELATED'
    if previous.operation_revision != incoming.operation_revision:
        return 'DIFFERENT_STEP'
    return 'MATCH' if previous == incoming else 'CONFLICT'


class SyntheticAaaAccount(ReadContract):
    """Public AAA attributes only; credential material is never part of a command."""
    username: str = Field(min_length=1, max_length=96, pattern=r'^[A-Za-z0-9][A-Za-z0-9._@-]*$')
    plan: str = Field(min_length=1, max_length=120)
    status: Literal['ACTIVE', 'PAUSED']
    expires_on: str | None = None
    local_expire_comment: str | None = None

    @model_serializer(mode='wrap')
    def serialize_account(self, handler):
        data = handler(self)
        if self.local_expire_comment is None:
            data.pop('local_expire_comment', None)
        return data

    @field_validator('local_expire_comment')
    @classmethod
    def local_comment(cls, value):
        if value is not None:
            from app.simulation.aaa_local_expire import expire_instant
            expire_instant(value)
        return value

    @field_validator('expires_on')
    @classmethod
    def calendar_date(cls, value):
        from datetime import date
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError('CANONICAL_EXPIRY_REQUIRED')
        return value

    @field_validator('plan')
    @classmethod
    def printable_plan(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('CANONICAL_PLAN_REQUIRED')
        return value


class SyntheticAaaCommand(ReadContract):
    version: Literal['AAA_SYNTHETIC_SUBSCRIBER_V1'] = 'AAA_SYNTHETIC_SUBSCRIBER_V1'
    fixture_only: Literal[True] = True
    external_writes: Literal[False] = False
    request_id: UUID
    tenant_id: UUID
    actor_id: str = Field(min_length=1)
    subscriber_id: str = Field(pattern=r'^demo-managed-sub-.+$')
    router_id: str = Field(pattern=r'^demo-managed-router-.+$')
    expected_source: Literal['LOCAL', 'RADIUS']
    expected_revision: int = Field(ge=0)
    expected_fence: int = Field(ge=0)
    operation: Literal['CREATE', 'EXTEND', 'PLAN', 'STATUS']
    before: SyntheticAaaAccount | None
    after: SyntheticAaaAccount
    days: int | None = Field(default=None, ge=1, le=366)
    confirmed: Literal[True]
    expire_deadline: datetime | None = None

    @model_serializer(mode='wrap')
    def serialize_command(self, handler):
        data = handler(self)
        if self.expire_deadline is None:
            data.pop('expire_deadline', None)
        return data

    @field_validator('confirmed', 'fixture_only', 'external_writes', mode='before')
    @classmethod
    def explicit_boolean(cls, value, info):
        expected = info.field_name != 'external_writes'
        if type(value) is not bool or value is not expected:
            raise ValueError('EXPLICIT_SYNTHETIC_CONFIRMATION_REQUIRED')
        return value

    @model_validator(mode='after')
    def explicit_change(self):
        if self.expire_deadline is not None:
            from app.simulation.aaa_local_expire import require_expire_command
            require_expire_command(self)
        if self.operation=='CREATE':
            if self.before is not None or self.days is not None:
                raise ValueError('EMPTY_SYNTHETIC_ACCOUNT_REQUIRED')
        else:
            if self.before is None:
                raise ValueError('EXISTING_SYNTHETIC_ACCOUNT_REQUIRED')
            field = {'EXTEND':'expires_on','PLAN':'plan','STATUS':'status'}[self.operation]
            changed = {k for k in SyntheticAaaAccount.model_fields if getattr(self.before,k)!=getattr(self.after,k)}
            if changed != {field} or (self.operation!='EXTEND' and self.days is not None):
                raise ValueError('SINGLE_EXPLICIT_SUBSCRIBER_CHANGE_REQUIRED')
        return self

    def fingerprint(self):
        from app.simulation.aaa_atomic import canonical_hash
        return canonical_hash(self.model_dump(mode='json'))


class SyntheticAaaReceipt(ReadContract):
    version: Literal['AAA_SYNTHETIC_RECEIPT_V1'] = 'AAA_SYNTHETIC_RECEIPT_V1'
    fixture_only: Literal[True] = True
    external_writes: Literal[False] = False
    request_id: UUID
    tenant_id: UUID
    actor_id: str
    subscriber_id: str
    router_id: str
    source: Literal['LOCAL', 'RADIUS']
    operation: Literal['CREATE', 'EXTEND', 'PLAN', 'STATUS']
    fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    outcome: Literal['APPLIED'] = 'APPLIED'
    before: SyntheticAaaAccount | None
    after: SyntheticAaaAccount
    revision: int = Field(ge=1)
    fence: int = Field(ge=1)
    occurred_at: datetime

    @field_validator('occurred_at')
    @classmethod
    def utc_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError('AWARE_RECEIPT_TIME_REQUIRED')
        return value.astimezone(timezone.utc)
