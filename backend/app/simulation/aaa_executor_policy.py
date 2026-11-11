"""Versioned fixture policies for an executor decision. No execution or rollback implied."""
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, OutboxFixture, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider
from app.simulation.aaa_followup import CheckpointPlan, held_checkpoint_hash
from app.simulation.aaa_executor_decision import ExecutorReconciliationService


class ExecutorPolicyConflict(AtomicConflict):
    pass


class ExecutorPolicyPlan(CheckpointPlan):
    execution_id: UUID
    unknown_receipt_fingerprint: str
    expected_state: Literal['EXECUTOR_DECISION_RECORDED'] = 'EXECUTOR_DECISION_RECORDED'


class ExecutorContinuePlan(ExecutorPolicyPlan):
    contract_version: Literal['EXECUTOR_CONTINUE_POLICY_V1_FIXTURE'] = 'EXECUTOR_CONTINUE_POLICY_V1_FIXTURE'
    kind: Literal['CONTINUE'] = 'CONTINUE'
    execution_policy: Literal['SEPARATE_FRESH_EXECUTION_AUTH_REQUIRED'] = 'SEPARATE_FRESH_EXECUTION_AUTH_REQUIRED'


class ExecutorCancelPlan(ExecutorPolicyPlan):
    contract_version: Literal['EXECUTOR_CANCEL_POLICY_V1_FIXTURE'] = 'EXECUTOR_CANCEL_POLICY_V1_FIXTURE'
    kind: Literal['CANCEL'] = 'CANCEL'
    external_effects: Literal['NOT_REVERSED_BY_CANCEL'] = 'NOT_REVERSED_BY_CANCEL'


class ExecutorPolicyAuthority(ReadContract):
    environment: Literal['AAA_EXECUTOR_POLICY_FIXTURE_ONLY'] = 'AAA_EXECUTOR_POLICY_FIXTURE_ONLY'
    tenant_id: str
    actor_id: str
    can_continue: bool = False
    can_cancel: bool = False


class ExecutorPolicyIntent(ReadContract):
    authorization_id: UUID
    seconds: int = Field(default=60, ge=1, le=300)


class ExecutorPolicyAuthorization(ReadContract):
    version: Literal['EXECUTOR_POLICY_AUTH_V1_FIXTURE'] = 'EXECUTOR_POLICY_AUTH_V1_FIXTURE'
    authorization_id: UUID
    actor_id: str
    plan: ExecutorContinuePlan | ExecutorCancelPlan
    issued_at: datetime
    expires_at: datetime


class ExecutorPolicyRecord(ReadContract):
    authorization_id: UUID
    plan_hash: str
    decision_id: UUID
    execution_id: UUID
    kind: Literal['CONTINUE', 'CANCEL']
    state: Literal['EXECUTOR_CONTINUE_HELD', 'EXECUTOR_CANCELLED_HELD']
    owner_revision: int
    checkpoint_fingerprint: str
    automatic_dispatch: Literal[False] = False
    external_effects_reversed: Literal[False] = False
    external_writes: Literal[False] = False


class ExecutorPolicyService:
    def __init__(self, unit, provider):
        if type(unit) is not LeasedMemoryOutbox or type(provider) is not FakeFencedProvider:
            raise TypeError('Explicit memory fixtures required')
        self._unit, self._provider = unit, provider
        self._reviewer = ExecutorReconciliationService(unit, provider)
        with unit._lock:
            for key, empty in (('executor_policy_authorizations', {}), ('executor_policy_records', {}), ('executor_policy_audit', [])):
                unit._state.setdefault(key, empty)

    def _guard(self, request, scope, authority, plan, permission):
        self._unit._authorized(request, scope, permission)
        if (type(authority) is not ExecutorPolicyAuthority or type(plan) not in (ExecutorContinuePlan, ExecutorCancelPlan)
                or authority.environment != 'AAA_EXECUTOR_POLICY_FIXTURE_ONLY'
                or authority.tenant_id != request.plan.tenant_id or authority.actor_id != scope.actor_id
                or not (authority.can_continue if plan.kind == 'CONTINUE' else authority.can_cancel)):
            raise PermissionError('SEPARATE_EXECUTOR_CONTINUE_OR_CANCEL_PERMISSION_REQUIRED')

    def _checkpoint(self, request, scope, decision_id, permission):
        unit = self._unit
        unit._authorized(request, scope, permission)
        key, owner_key, op = unit._match(unit._state, request)
        record = unit._state.get('executor_decision_records', {}).get(decision_id)
        grant = unit._state.get('executor_decision_authorizations', {}).get(decision_id)
        owner, lease, events = unit._state['owners'][owner_key], unit._state['leases'][key], unit._state['outbox'][key]
        if record is None or grant is None:
            raise ExecutorPolicyConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        evaluation = record.evaluation
        if (op.state != 'EXECUTOR_DECISION_RECORDED' or record.decision != grant.decision
                or evaluation.model_dump(exclude={'observed_at'}) != grant.evaluation.model_dump(exclude={'observed_at'})
                or evaluation.tenant_id != request.plan.tenant_id or evaluation.request_id != request.request_id
                or evaluation.subscriber_id != owner_key[2] or record.owner_revision != owner.revision
                or owner.revision != evaluation.owner_revision + 1 or owner.revision != op.owner_revision
                or op.revision != record.operation_revision or op.revision != evaluation.operation_revision + 1
                or owner.fence != evaluation.owner_fence + 1 or owner.fence != op.fence
                or owner.authority != request.plan.source or owner.active_request != request.request_id
                or lease.status != 'DONE' or lease.token != evaluation.fencing_token + 1 or lease.operation_revision != op.revision
                or held_checkpoint_hash(owner, op, lease, events) != record.checkpoint_fingerprint):
            raise ExecutorPolicyConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        trace_id = uuid5(decision_id, evaluation.evidence_fingerprint)
        if (not events or events[-1].event_id != trace_id or events[-1].status != 'HELD'
                or events[-1].step != 'EXECUTOR_RECONCILIATION_DECISION'):
            raise ExecutorPolicyConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        audit = [r for r in unit._state['audit'] if r[:2] == key]
        if (not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, 'EXECUTOR_DECISION_RECORDED')
                or sum(r[0] == decision_id and r[2] == 'CONSUMED' for r in unit._state['executor_decision_audit']) != 1):
            raise ExecutorPolicyConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        # Reconstruct the pre-decision checkpoint in a private copy; never rewind the real UoW.
        prior = deepcopy(unit._state)
        prior['owners'][owner_key] = owner.model_copy(update={'revision': evaluation.owner_revision, 'fence': evaluation.owner_fence})
        prior['journal'][key] = op.model_copy(update={'state': 'FIXTURE_STEP_UNKNOWN', 'revision': evaluation.operation_revision,
            'owner_revision': evaluation.owner_revision, 'fence': evaluation.owner_fence})
        prior['leases'][key] = lease.model_copy(update={'token': evaluation.fencing_token, 'operation_revision': evaluation.operation_revision})
        prior['outbox'][key] = tuple(e.model_copy(update={'status': 'UNKNOWN', 'result': 'UNKNOWN'})
            if e.event_id == evaluation.event_id else e for e in events[:-1])
        last = next(i for i in range(len(prior['audit']) - 1, -1, -1) if prior['audit'][i][:2] == key)
        del prior['audit'][last]
        fresh = self._reviewer._evaluate(request, evaluation.execution_id, checkpoint=prior)
        if (fresh.status == 'READ_ONLY_RECONCILIATION_REQUIRED'
                or fresh.model_dump(exclude={'observed_at'}) != evaluation.model_dump(exclude={'observed_at'})):
            raise ExecutorPolicyConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        accepted = unit._state['executor_accepted'][evaluation.execution_id]
        digest = canonical_hash({'record': record.model_dump(mode='json'), 'grant': grant.model_dump(mode='json'),
            'held': record.checkpoint_fingerprint, 'unknown': accepted.model_dump(mode='json'),
            'fresh_evidence': fresh.model_dump(mode='json', exclude={'observed_at'})})
        return dict(tenant_id=request.plan.tenant_id, store=owner_key[1], subscriber_id=owner_key[2], request_id=request.request_id,
            previous_plan_hash=evaluation.plan_hash, decision_id=decision_id, execution_id=evaluation.execution_id,
            evidence_fingerprint=evaluation.evidence_fingerprint, provider_evidence_fingerprint=evaluation.provider_evidence_fingerprint,
            owner_revision=owner.revision, operation_revision=op.revision, owner_fence=owner.fence,
            worker_token=lease.token, checkpoint_fingerprint=digest,
            unknown_receipt_fingerprint=canonical_hash(accepted.receipt.model_dump(mode='json')))

    def plan(self, request, scope, decision_id, kind, *, permission=False):
        if kind not in ('CONTINUE', 'CANCEL'):
            raise ValueError('Unknown executor policy')
        with self._unit._lock, self._provider._lock:
            data = self._checkpoint(request, scope, decision_id, permission)
            return ExecutorContinuePlan(**data) if kind == 'CONTINUE' else ExecutorCancelPlan(**data)

    def issue(self, request, scope, authority, plan, intent: ExecutorPolicyIntent, *, permission=False):
        self._guard(request, scope, authority, plan, permission)
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction():
            if intent.authorization_id in unit._state['executor_policy_authorizations']:
                raise ExecutorPolicyConflict('AUTHORIZATION_ID_REUSED')
            if self.plan(request, scope, plan.decision_id, plan.kind, permission=permission) != plan:
                raise ExecutorPolicyConflict('STALE_OR_MISMATCHED_EXECUTOR_POLICY')
            now = unit._clock.now()
            grant = ExecutorPolicyAuthorization(authorization_id=intent.authorization_id, actor_id=authority.actor_id,
                plan=plan, issued_at=now, expires_at=now + timedelta(seconds=intent.seconds))
            unit._state['executor_policy_authorizations'][intent.authorization_id] = grant
            unit._state['executor_policy_audit'].append((intent.authorization_id, plan.plan_hash(), authority.actor_id, 'ISSUED', now))
            return grant

    def apply(self, request, scope, authority, grant: ExecutorPolicyAuthorization, *, permission=False, fail_at=None):
        self._guard(request, scope, authority, grant.plan, permission)
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction(None if fail_at == 'AUTHORIZATION' else fail_at):
            if unit._state['executor_policy_authorizations'].get(grant.authorization_id) != grant:
                raise ExecutorPolicyConflict('UNKNOWN_OR_TAMPERED_AUTHORIZATION')
            if grant.authorization_id in unit._state['executor_policy_records']:
                raise ExecutorPolicyConflict('AUTHORIZATION_ALREADY_USED')
            now = unit._clock.now()
            if grant.actor_id != authority.actor_id or now < grant.issued_at or now >= grant.expires_at:
                raise ExecutorPolicyConflict('AUTHORIZATION_EXPIRED_OR_FOREIGN')
            plan = grant.plan
            if self.plan(request, scope, plan.decision_id, plan.kind, permission=permission) != plan:
                raise ExecutorPolicyConflict('STALE_CAS_FENCING_OR_EVIDENCE')
            key, owner_key, op = unit._match(unit._state, request)
            owner = unit._state['owners'][owner_key].model_copy(update={'revision': plan.owner_revision + 1, 'fence': plan.owner_fence + 1})
            state = 'EXECUTOR_CONTINUE_HELD' if plan.kind == 'CONTINUE' else 'EXECUTOR_CANCELLED_HELD'
            op = op.model_copy(update={'state': state, 'revision': op.revision + 1, 'owner_revision': owner.revision, 'fence': owner.fence})
            unit._state['owners'][owner_key], unit._state['journal'][key] = owner, op
            unit._state['outbox'][key] += (OutboxFixture(event_id=uuid5(grant.authorization_id, plan.plan_hash()),
                tenant_id=plan.tenant_id, request_id=request.request_id, correlation_id=request.correlation_id,
                plan_hash=plan.plan_hash(), at=now, sequence=len(unit._state['outbox'][key]) + 1,
                step='EXECUTOR_' + plan.kind + '_REVIEW', status='HELD'),)
            lease = unit._state['leases'][key].model_copy(update={'status': 'DONE', 'token': plan.worker_token + 1,
                                                                'operation_revision': op.revision})
            unit._state['leases'][key] = lease
            record = ExecutorPolicyRecord(authorization_id=grant.authorization_id, plan_hash=plan.plan_hash(),
                decision_id=plan.decision_id, execution_id=plan.execution_id, kind=plan.kind, state=state,
                owner_revision=owner.revision, checkpoint_fingerprint=held_checkpoint_hash(owner, op, lease, unit._state['outbox'][key]))
            unit._state['executor_policy_records'][grant.authorization_id] = record
            unit._audit(unit._state, request, op, state)
            unit._record(lease, state)
            unit._state['executor_policy_audit'].append((grant.authorization_id, plan.plan_hash(), authority.actor_id, 'CONSUMED', now))
            if fail_at == 'AUTHORIZATION':
                raise ExecutorPolicyConflict('INJECTED_AUTHORIZATION_FAILURE')
            return record
