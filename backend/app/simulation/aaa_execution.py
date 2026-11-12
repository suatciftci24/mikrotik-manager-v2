"""Authorize one controlled fixture stage. No provider execution, worker claim or IO."""
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, OutboxFixture, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, ProviderEvidence
from app.simulation.aaa_followup import ContinuePlan, held_checkpoint_hash

Step = Literal['FENCE_LOCAL', 'ENABLE_RADIUS', 'COMMIT_OWNER_CAS']


class ExecutionConflict(AtomicConflict):
    pass


class ExecutionStepPlan(ReadContract):
    contract_version: Literal['AAA_EXECUTION_STEP_V1_FIXTURE'] = 'AAA_EXECUTION_STEP_V1_FIXTURE'
    tenant_id: str
    store: str
    subscriber_id: str
    request_id: UUID
    continue_plan_hash: str
    followup_id: UUID
    decision_id: UUID
    evidence_fingerprint: str
    provider_evidence_fingerprint: str
    owner_revision: int
    operation_revision: int
    owner_fence: int
    worker_token: int
    allowed_step: Step
    step_sequence: int = Field(ge=2, le=4)
    previous_event_id: UUID
    previous_result: Literal['APPLIED'] = 'APPLIED'
    expected_state: Literal['CONTINUE_HELD'] = 'CONTINUE_HELD'
    checkpoint_fingerprint: str
    provider_dispatch: Literal[False] = False

    def plan_hash(self):
        return canonical_hash(self.model_dump(mode='json'))


class FixtureExecutionAuthority(ReadContract):
    environment: Literal['AAA_EXECUTION_FIXTURE_ONLY'] = 'AAA_EXECUTION_FIXTURE_ONLY'
    tenant_id: str
    actor_id: str
    can_issue: bool = False
    can_stage: bool = False


class ExecutionIntent(ReadContract):
    authorization_id: UUID
    lifetime_seconds: int = Field(default=60, ge=1, le=300)


class ExecutionAuthorization(ReadContract):
    version: Literal['EXECUTION_AUTHORIZATION_V1_FIXTURE'] = 'EXECUTION_AUTHORIZATION_V1_FIXTURE'
    authorization_id: UUID
    actor_id: str
    plan: ExecutionStepPlan
    issued_at: datetime
    expires_at: datetime


class ExecutionRecord(ReadContract):
    authorization_id: UUID
    execution_plan_hash: str
    continue_plan_hash: str
    decision_id: UUID
    allowed_step: Step
    state: Literal['FIXTURE_EXECUTION_STAGED'] = 'FIXTURE_EXECUTION_STAGED'
    owner_revision: int
    owner_fence: int
    worker_token: int
    checkpoint_fingerprint: str
    provider_dispatch: Literal[False] = False
    external_writes: Literal[False] = False
    live_ready: Literal[False] = False


class FixtureExecutionService:
    authorization_type = ExecutionAuthorization
    record_type = ExecutionRecord
    stage_state = 'FIXTURE_EXECUTION_STAGED'
    stage_prefix = 'FIXTURE_STAGE:'

    def _record_kwargs(self, plan):
        return {}

    def __init__(self, unit, provider, *, initialize=True):
        if type(unit) is not LeasedMemoryOutbox or type(provider) is not FakeFencedProvider:
            raise TypeError('Explicit memory fixtures required')
        self._unit, self._provider = unit, provider
        if not initialize:
            return
        with unit._lock:
            for key, empty in (('execution_authorizations', {}), ('execution_records', {}), ('execution_audit', [])):
                unit._state.setdefault(key, empty)

    def _privilege(self, request, scope, authority, flag):
        if (type(authority) is not FixtureExecutionAuthority or authority.environment != 'AAA_EXECUTION_FIXTURE_ONLY'
                or authority.tenant_id != request.plan.tenant_id or authority.actor_id != scope.actor_id
                or not getattr(authority, flag)):
            raise PermissionError('SEPARATE_FIXTURE_EXECUTION_PERMISSION_REQUIRED')

    def _plan(self, request, scope, followup_id, allowed_step, permission):
        unit, provider = self._unit, self._provider
        unit._authorized(request, scope, permission)
        key, owner_key, op = unit._match(unit._state, request)
        record = unit._state.get('followup_records', {}).get(followup_id)
        grant = unit._state.get('followup_authorizations', {}).get(followup_id)
        owner, lease, events = unit._state['owners'][owner_key], unit._state['leases'][key], unit._state['outbox'][key]
        if (record is None or grant is None or type(grant.plan) is not ContinuePlan
                or record.kind != 'CONTINUE' or record.state != 'CONTINUE_HELD' or op.state != record.state
                or record.plan_hash != grant.plan.plan_hash() or record.previous_plan_hash != op.plan_hash
                or record.decision_id != grant.plan.decision_id or owner.revision != record.owner_revision
                or record.owner_revision != grant.plan.owner_revision + 1 or op.owner_revision != owner.revision
                or op.revision != grant.plan.operation_revision + 1 or owner.fence != op.fence
                or owner.fence != grant.plan.owner_fence + 1 or owner.active_request != request.request_id
                or owner.authority != request.plan.source or lease.status != 'DONE'
                or lease.operation_revision != op.revision or lease.token != grant.plan.worker_token + 1
                or provider._account != owner_key
                or held_checkpoint_hash(owner, op, lease, events) != record.checkpoint_fingerprint):
            raise ExecutionConflict('CONTINUE_CHECKPOINT_CAS_OR_FENCE_CONFLICT')
        decision = unit._state.get('decision_records', {}).get(record.decision_id)
        if (decision is None or decision.evidence_fingerprint != grant.plan.evidence_fingerprint
                or decision.provider_evidence_fingerprint != grant.plan.provider_evidence_fingerprint
                or decision.plan_hash != request.plan.plan_hash()):
            raise ExecutionConflict('DECISION_EVIDENCE_BINDING_CONFLICT')
        receipts = tuple(sorted((r for (tenant, req, _), r in provider._state['receipts'].items()
            if (tenant, req) == key), key=lambda r: r.command.sequence))
        proof = ProviderEvidence(tenant_id=request.plan.tenant_id, account_id=owner_key[2], plan_hash=op.plan_hash,
            complete=bool(receipts) and all(r.outcome != 'UNKNOWN' for r in receipts),
            receipts=receipts, current=provider._state['provider'])
        proof_hash = canonical_hash(proof.model_dump(mode='json'))
        if (not proof.complete or proof_hash != grant.plan.provider_evidence_fingerprint
                or any(r.outcome != 'APPLIED' for r in receipts)):
            raise ExecutionConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        sequence = len(receipts) + 1
        if sequence > len(request.plan.steps) or request.plan.steps[sequence - 1] != allowed_step:
            raise ExecutionConflict('WRONG_STEP_OR_PREVIOUS_RESULT')
        if (tuple(r.command.sequence for r in receipts) != tuple(range(1, sequence))
                or len(events) != len(request.plan.steps) + 1
                or events[-1].status != 'HELD' or events[-1].step != 'CONTINUE_EXECUTION_REVIEW'
                or events[-1].plan_hash != record.plan_hash
                or events[sequence - 2].event_id != receipts[-1].command.event_id
                or (events[sequence - 2].status, events[sequence - 2].result) != ('ACKED', 'APPLIED')
                or any(e.status != 'CANCELLED' for e in events[sequence - 1:-1])):
            raise ExecutionConflict('JOURNAL_OUTBOX_ORDER_CONFLICT')
        current = proof.current
        if (allowed_step == 'FENCE_LOCAL' and not (current.local_enabled and current.radius_state == 'DISABLED')
                or allowed_step == 'ENABLE_RADIUS' and not (not current.local_enabled and current.radius_state == 'DISABLED'
                    and current.fenced_request == request.request_id and current.owner_fence == receipts[-1].command.owner_fence)
                or allowed_step == 'COMMIT_OWNER_CAS' and not (not current.local_enabled and current.radius_state == 'ENABLED'
                    and current.fenced_request == request.request_id and current.owner_fence == receipts[-1].command.owner_fence)):
            raise ExecutionConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        audit = [r for r in unit._state['audit'] if r[:2] == key]
        if (not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, 'CONTINUE_HELD')
                or sum(r[0] == followup_id and r[3] == 'CONSUMED' for r in unit._state['followup_audit']) != 1):
            raise ExecutionConflict('CONTINUE_AUDIT_CONFLICT')
        ref = request.plan.snapshot.reference
        return ExecutionStepPlan(tenant_id=request.plan.tenant_id, store=ref.store, subscriber_id=ref.account_id,
            request_id=request.request_id, continue_plan_hash=record.plan_hash, followup_id=followup_id,
            decision_id=record.decision_id, evidence_fingerprint=decision.evidence_fingerprint,
            provider_evidence_fingerprint=proof_hash, owner_revision=owner.revision, operation_revision=op.revision,
            owner_fence=owner.fence, worker_token=lease.token, allowed_step=allowed_step, step_sequence=sequence,
            previous_event_id=receipts[-1].command.event_id, checkpoint_fingerprint=record.checkpoint_fingerprint)

    def plan(self, request, scope, followup_id, allowed_step, *, permission=False):
        with self._unit._lock, self._provider._lock:
            return self._plan(request, scope, followup_id, allowed_step, permission)

    def issue(self, request, scope, authority, plan, intent: ExecutionIntent, *, permission=False):
        self._privilege(request, scope, authority, 'can_issue')
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction():
            if intent.authorization_id in unit._state['execution_authorizations']:
                raise ExecutionConflict('AUTHORIZATION_ID_REUSED')
            if self._plan(request, scope, plan.followup_id, plan.allowed_step, permission) != plan:
                raise ExecutionConflict('STALE_OR_MISMATCHED_EXECUTION_PLAN')
            now = unit._clock.now()
            grant = self.authorization_type(authorization_id=intent.authorization_id, actor_id=authority.actor_id,
                plan=plan, issued_at=now, expires_at=now + timedelta(seconds=intent.lifetime_seconds))
            unit._state['execution_authorizations'][intent.authorization_id] = grant
            unit._state['execution_audit'].append((intent.authorization_id, plan.plan_hash(), authority.actor_id, 'ISSUED', now))
            return grant

    def stage(self, request, scope, authority, grant: ExecutionAuthorization, *, permission=False, fail_at=None):
        self._privilege(request, scope, authority, 'can_stage')
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction(None if fail_at == 'AUTHORIZATION' else fail_at):
            if unit._state['execution_authorizations'].get(grant.authorization_id) != grant:
                raise ExecutionConflict('UNKNOWN_OR_TAMPERED_AUTHORIZATION')
            if grant.authorization_id in unit._state['execution_records']:
                raise ExecutionConflict('AUTHORIZATION_ALREADY_USED')
            now = unit._clock.now()
            if grant.actor_id != authority.actor_id or now < grant.issued_at or now >= grant.expires_at:
                raise ExecutionConflict('AUTHORIZATION_EXPIRED_OR_FOREIGN')
            plan = grant.plan
            if self._plan(request, scope, plan.followup_id, plan.allowed_step, permission) != plan:
                raise ExecutionConflict('STALE_CAS_FENCE_OR_EVIDENCE')
            key, owner_key, op = unit._match(unit._state, request)
            owner = unit._state['owners'][owner_key].model_copy(update={
                'revision': plan.owner_revision + 1, 'fence': plan.owner_fence + 1})
            op = op.model_copy(update={'state': self.stage_state, 'revision': op.revision + 1,
                                      'owner_revision': owner.revision, 'fence': owner.fence})
            unit._state['owners'][owner_key], unit._state['journal'][key] = owner, op
            lease = unit._state['leases'][key].model_copy(update={'token': plan.worker_token + 1,
                'operation_revision': op.revision, 'status': 'DONE'})
            unit._state['leases'][key] = lease
            unit._state['outbox'][key] += (OutboxFixture(event_id=uuid5(grant.authorization_id, plan.plan_hash()),
                tenant_id=plan.tenant_id, request_id=request.request_id, correlation_id=request.correlation_id,
                plan_hash=plan.plan_hash(), at=now, sequence=len(unit._state['outbox'][key]) + 1,
                step=self.stage_prefix + plan.allowed_step, status='HELD'),)
            record = self.record_type(authorization_id=grant.authorization_id, execution_plan_hash=plan.plan_hash(),
                continue_plan_hash=plan.continue_plan_hash, decision_id=plan.decision_id, allowed_step=plan.allowed_step,
                owner_revision=owner.revision, owner_fence=owner.fence, worker_token=lease.token,
                checkpoint_fingerprint=held_checkpoint_hash(owner, op, lease, unit._state['outbox'][key]), **self._record_kwargs(plan))
            unit._state['execution_records'][grant.authorization_id] = record
            unit._audit(unit._state, request, op, self.stage_state)
            unit._record(lease, self.stage_state)
            unit._state['execution_audit'].append((grant.authorization_id, plan.plan_hash(), authority.actor_id, 'CONSUMED', now))
            if fail_at == 'AUTHORIZATION':
                raise ExecutionConflict('INJECTED_AUTHORIZATION_FAILURE')
            return record
