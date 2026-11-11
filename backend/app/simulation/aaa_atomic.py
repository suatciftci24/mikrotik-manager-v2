"""Versioned atomicity rehearsal. Caller-owned memory only; no real repository/executor."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import RLock
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, field_validator, model_validator
from app.integrations.aaa_contracts import AaaSnapshot, PreviewScope, ReadContract, require_preview_scope

STEPS = ('STAGE_DISABLED_TARGET', 'FENCE_LOCAL', 'ENABLE_RADIUS', 'COMMIT_OWNER_CAS')


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                             allow_nan=False).encode('ascii')).hexdigest()


class AtomicPlan(ReadContract):
    contract_version: Literal['AAA_ATOMIC_PLAN_V1'] = 'AAA_ATOMIC_PLAN_V1'
    tenant_id: str = Field(min_length=1)
    snapshot: AaaSnapshot
    source: Literal['LOCAL'] = 'LOCAL'
    target: Literal['RADIUS'] = 'RADIUS'
    expected_account_revision: int = Field(ge=0)
    expected_source_revision: int = Field(ge=1)
    expected_target_revision: int = Field(ge=0)
    namespace_revision: int = Field(ge=1)
    authorization_policy_revision: int = Field(ge=1)
    preparation_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    steps: tuple[str, ...] = STEPS

    @model_validator(mode='after')
    def binding(self):
        if (self.snapshot.reference.tenant_id != self.tenant_id
                or self.snapshot.reference.revision != self.expected_account_revision
                or self.snapshot.authority != self.source or self.steps != STEPS):
            raise ValueError('Plan owner, revision or ordered steps mismatch')
        return self

    def plan_hash(self):
        return canonical_hash(self.model_dump(mode='json'))


class AtomicRequest(ReadContract):
    journal_version: Literal['AAA_JOURNAL_V2_FIXTURE'] = 'AAA_JOURNAL_V2_FIXTURE'
    request_id: UUID
    correlation_id: UUID
    actor_id: str = Field(min_length=1)
    at: datetime
    plan: AtomicPlan

    @field_validator('at')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Aware logical fixture clock required')
        return value.astimezone(timezone.utc)

    def fingerprint(self):
        return canonical_hash({'version': self.journal_version, 'plan_hash': self.plan.plan_hash(),
                               'actor': self.actor_id, 'correlation': str(self.correlation_id), 'at': self.at.isoformat()})


class OwnerFixture(ReadContract):
    authority: Literal['LOCAL', 'RADIUS']
    revision: int = Field(ge=0)
    active_request: UUID | None = None
    fence: int = Field(default=0, ge=0)


class OperationFixture(ReadContract):
    origin: Literal['AAA_ATOMIC_MEMORY_ONLY'] = 'AAA_ATOMIC_MEMORY_ONLY'
    live_ready: Literal[False] = False
    external_writes: Literal[False] = False
    plan_hash: str
    fingerprint: str
    revision: int = 1
    state: Literal['RESERVED', 'PLANNED', 'MODELED', 'RECONCILIATION', 'COMPENSATED', 'DECISION_RECORDED', 'CONTINUE_HELD', 'CANCELLED_HELD', 'FIXTURE_EXECUTION_STAGED', 'FIXTURE_STEP_SUCCEEDED', 'FIXTURE_STEP_REJECTED', 'FIXTURE_STEP_UNKNOWN', 'EXECUTOR_DECISION_RECORDED', 'EXECUTOR_CONTINUE_HELD', 'EXECUTOR_CANCELLED_HELD', 'NEXT_STEP_EXECUTION_STAGED'] = 'RESERVED'
    owner_revision: int
    fence: int


class OutboxFixture(ReadContract):
    event_id: UUID
    tenant_id: str
    request_id: UUID
    correlation_id: UUID
    plan_hash: str
    at: datetime
    sequence: int
    step: str
    status: Literal['PENDING', 'ACKED', 'UNKNOWN', 'CANCELLED', 'HELD'] = 'PENDING'
    result: Literal['APPLIED', 'NOT_APPLIED', 'UNKNOWN'] | None = None


class CompensationEvidence(ReadContract):
    origin: Literal['FIXTURE_ONLY'] = 'FIXTURE_ONLY'
    plan_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    expected_owner_revision: int = Field(ge=0)
    expected_operation_revision: int = Field(ge=1)
    fence: int = Field(ge=1)
    external_result_known: bool = False
    target_disabled: bool = False
    local_restored: bool = False


class AtomicConflict(ValueError):
    pass


class MemoryAtomicUnit:
    """Fake UoW: one lock + copy/publish models one transaction, never PostgreSQL."""
    def __init__(self, plan: AtomicPlan):
        self._lock = RLock()
        ref = plan.snapshot.reference
        self._state = {'owners': {(plan.tenant_id, ref.store, ref.account_id):
                                   OwnerFixture(authority=plan.source, revision=ref.revision)},
                       'journal': {}, 'outbox': {}, 'audit': []}

    def snapshot(self):
        with self._lock:
            return deepcopy(self._state)

    def _authorized(self, request, scope, permission):
        require_preview_scope(request.plan.snapshot, scope)
        if (not permission or scope.tenant_id != request.plan.tenant_id or scope.actor_id != request.actor_id):
            raise PermissionError('ATOMIC_FIXTURE_SCOPE_DENIED')

    def _keys(self, request):
        ref = request.plan.snapshot.reference
        return (request.plan.tenant_id, request.request_id), (request.plan.tenant_id, ref.store, ref.account_id)

    def _match(self, state, request):
        key, owner_key = self._keys(request)
        op = state['journal'].get(key)
        if op is None or op.fingerprint != request.fingerprint():
            raise AtomicConflict('IDEMPOTENCY_CONFLICT')
        return key, owner_key, op

    def _audit(self, state, request, op, phase):
        # Safe metadata only; no snapshot, secret or provider payload.
        state['audit'].append((request.plan.tenant_id, request.request_id, request.correlation_id,
                               request.actor_id, op.plan_hash, op.revision, phase, request.at))

    def _publish(self, candidate, fail_at):
        if fail_at not in (None, 'OWNER', 'JOURNAL', 'AUDIT', 'OUTBOX'):
            raise ValueError('Unknown fixture fault')
        if fail_at:
            raise AtomicConflict('INJECTED_' + fail_at + '_FAILURE')
        self._state = candidate

    def reserve(self, request: AtomicRequest, scope: PreviewScope, *, permission=False, fail_at=None):
        self._authorized(request, scope, permission)
        with self._lock:
            key, owner_key = self._keys(request)
            if key in self._state['journal']:
                return self._match(self._state, request)[2]  # Historical replay, no new event.
            candidate = deepcopy(self._state)
            owner = candidate['owners'].get(owner_key)
            if (owner is None or owner.active_request is not None or owner.authority != request.plan.source
                    or owner.revision != request.plan.expected_account_revision):
                raise AtomicConflict('OWNER_CAS_CONFLICT')
            owner = owner.model_copy(update={'revision': owner.revision + 1, 'fence': owner.fence + 1,
                                             'active_request': request.request_id})
            op = OperationFixture(plan_hash=request.plan.plan_hash(), fingerprint=request.fingerprint(),
                                  owner_revision=owner.revision, fence=owner.fence)
            candidate['owners'][owner_key] = owner
            candidate['journal'][key] = op
            candidate['outbox'][key] = tuple(OutboxFixture(event_id=uuid5(request.request_id,
                request.plan.tenant_id + ':' + op.plan_hash + ':' + str(seq)),
                tenant_id=request.plan.tenant_id, request_id=request.request_id,
                correlation_id=request.correlation_id, plan_hash=op.plan_hash, at=request.at, sequence=seq, step=step)
                for seq, step in enumerate(request.plan.steps, 1))
            self._audit(candidate, request, op, 'RESERVED')
            self._publish(candidate, fail_at)
            return op

    def next_event(self, request, scope, *, permission=False):
        self._authorized(request, scope, permission)
        with self._lock:
            key, owner_key, op = self._match(self._state, request)
            owner = self._state['owners'][owner_key]
            if op.state in ('RESERVED', 'PLANNED') and (owner.active_request != request.request_id
                    or owner.revision != op.owner_revision or owner.fence != op.fence
                    or owner.authority != request.plan.source):
                raise AtomicConflict('OWNER_CAS_RECONCILIATION_REQUIRED')
            if op.state in ('CONTINUE_HELD', 'CANCELLED_HELD', 'FIXTURE_EXECUTION_STAGED', 'FIXTURE_STEP_SUCCEEDED', 'FIXTURE_STEP_REJECTED', 'EXECUTOR_DECISION_RECORDED', 'EXECUTOR_CONTINUE_HELD', 'EXECUTOR_CANCELLED_HELD', 'NEXT_STEP_EXECUTION_STAGED'):
                raise AtomicConflict('CHECKPOINT_NO_AUTOMATIC_DISPATCH')
            if op.state == 'DECISION_RECORDED':
                raise AtomicConflict('DECISION_RECORDED_NO_AUTOMATIC_DISPATCH')
            if op.state in ('RECONCILIATION', 'FIXTURE_STEP_UNKNOWN'):
                raise AtomicConflict('READ_ONLY_RECONCILIATION_REQUIRED')
            return next((e for e in self._state['outbox'][key] if e.status == 'PENDING'), None)

    def settle(self, request, scope, event_id: UUID, outcome: Literal['APPLIED', 'NOT_APPLIED', 'UNKNOWN'],
               expected_revision: int, *, permission=False, fail_at=None):
        self._authorized(request, scope, permission)
        if outcome not in ('APPLIED', 'NOT_APPLIED', 'UNKNOWN'):
            raise ValueError('Unknown fixture outcome')
        with self._lock:
            candidate = deepcopy(self._state)
            key, owner_key, op = self._match(candidate, request)
            events = list(candidate['outbox'][key])
            index = next((i for i, e in enumerate(events) if e.event_id == event_id), None)
            if index is None:
                raise AtomicConflict('UNKNOWN_EVENT')
            event = events[index]
            if event.status == 'ACKED' and event.result == outcome:
                return op  # Duplicate ack after success, still authorization checked.
            if op.state == 'RECONCILIATION' or event.status != 'PENDING':
                raise AtomicConflict('READ_ONLY_RECONCILIATION_REQUIRED')
            allowed_prior = ('ACKED', 'CANCELLED') if event.step == 'COMPENSATED' else ('ACKED',)
            if op.revision != expected_revision or any(e.status not in allowed_prior for e in events[:index]):
                raise AtomicConflict('OPERATION_REVISION_OR_ORDER_CONFLICT')
            owner = candidate['owners'][owner_key]
            if event.step == 'COMPENSATED' and outcome != 'APPLIED':
                return op  # Notification redelivery never reopens a completed compensation.
            if event.step != 'COMPENSATED' and (owner.active_request != request.request_id
                    or owner.revision != op.owner_revision or owner.fence != op.fence
                    or owner.authority != request.plan.source):
                # No side effects; caller must reconcile this owner drift.
                raise AtomicConflict('OWNER_CAS_RECONCILIATION_REQUIRED')
            events[index] = event.model_copy(update={'status': 'ACKED' if outcome == 'APPLIED' else 'UNKNOWN',
                                                     'result': outcome})
            state = 'PLANNED' if outcome == 'APPLIED' else 'RECONCILIATION'
            if event.step == 'COMMIT_OWNER_CAS' and outcome == 'APPLIED':
                candidate['owners'][owner_key] = owner.model_copy(update={'authority': request.plan.target,
                    'revision': owner.revision + 1, 'active_request': None})
                state = 'MODELED'
            elif event.step == 'COMPENSATED' and outcome == 'APPLIED':
                state = 'COMPENSATED'
            op = op.model_copy(update={'revision': op.revision + 1, 'state': state})
            candidate['journal'][key], candidate['outbox'][key] = op, tuple(events)
            self._audit(candidate, request, op, state)
            self._publish(candidate, fail_at)
            return op

    def compensate(self, request, scope, evidence: CompensationEvidence, *, permission=False,
                   compensation_permission=False, fail_at=None):
        self._authorized(request, scope, permission)
        if not compensation_permission:
            raise PermissionError('SEPARATE_COMPENSATION_PERMISSION_REQUIRED')
        with self._lock:
            candidate = deepcopy(self._state)
            key, owner_key, op = self._match(candidate, request)
            owner = candidate['owners'][owner_key]
            if (op.state != 'RECONCILIATION' or evidence.plan_hash != op.plan_hash
                    or evidence.expected_operation_revision != op.revision
                    or evidence.expected_owner_revision != owner.revision
                    or owner.revision != op.owner_revision or owner.fence != evidence.fence
                    or owner.fence != op.fence or owner.active_request != request.request_id
                    or not all((evidence.external_result_known, evidence.target_disabled, evidence.local_restored))):
                raise AtomicConflict('COMPENSATION_RECONCILIATION_REQUIRED')
            candidate['owners'][owner_key] = owner.model_copy(update={'authority': request.plan.source,
                'revision': owner.revision + 1, 'active_request': None})
            op = op.model_copy(update={'state': 'COMPENSATED', 'revision': op.revision + 1})
            old = candidate['outbox'][key]
            seq = len(old) + 1
            notification = OutboxFixture(event_id=uuid5(request.request_id, op.plan_hash + ':compensated'),
                tenant_id=request.plan.tenant_id, request_id=request.request_id,
                correlation_id=request.correlation_id, plan_hash=op.plan_hash, at=request.at, sequence=seq, step='COMPENSATED')
            candidate['outbox'][key] = tuple(e if e.status == 'ACKED' else e.model_copy(update={'status': 'CANCELLED'})
                                             for e in old) + (notification,)
            candidate['journal'][key] = op
            self._audit(candidate, request, op, 'COMPENSATED')
            self._publish(candidate, fail_at)
            return op


def plan_from_preparation(request, scope, adapter, *, policy_revision: int, permission=False):
    """Bind an approved fixture PREPARE decision; the digest is not an authorization token."""
    from app.simulation.aaa_integration_preparation import prepare_handoff
    decision = prepare_handoff(request, scope, adapter, fixture_transition_permission=permission)
    if decision.action != 'STAGE_DISABLED_TARGET':
        raise AtomicConflict('PREPARATION_NOT_RESERVABLE')
    snapshot = request.preview.snapshot
    return AtomicPlan(tenant_id=request.gates.tenant_id, snapshot=snapshot,
        expected_account_revision=snapshot.reference.revision,
        expected_source_revision=request.expected_source_revision,
        expected_target_revision=request.expected_target_revision,
        namespace_revision=request.gates.namespace_revision,
        authorization_policy_revision=policy_revision, preparation_sha256=decision.fingerprint)
