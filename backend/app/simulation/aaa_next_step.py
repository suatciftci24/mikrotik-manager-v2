"""Next-step fixture authorization using the existing execution registry/transaction engine."""
from copy import deepcopy
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field
from app.simulation.aaa_atomic import canonical_hash
from app.simulation.aaa_execution import (ExecutionStepPlan, ExecutionAuthorization, ExecutionRecord,
                                         FixtureExecutionService, ExecutionConflict)
from app.simulation.aaa_executor_policy import ExecutorPolicyService, ExecutorContinuePlan
from app.simulation.aaa_followup import held_checkpoint_hash


class NextStepPlan(ExecutionStepPlan):
    contract_version: Literal['NEXT_STEP_EXECUTION_PLAN_V1_FIXTURE'] = 'NEXT_STEP_EXECUTION_PLAN_V1_FIXTURE'
    previous_execution_id: UUID
    policy_id: UUID
    next_step_id: UUID
    expected_state: Literal['EXECUTOR_CONTINUE_HELD'] = 'EXECUTOR_CONTINUE_HELD'
    allowed_step: Literal['ENABLE_RADIUS', 'COMMIT_OWNER_CAS']
    step_sequence: int = Field(ge=3, le=4)


class NextStepExecutionAuthorization(ExecutionAuthorization):
    version: Literal['NEXT_STEP_EXECUTION_AUTHORIZATION_V1_FIXTURE'] = 'NEXT_STEP_EXECUTION_AUTHORIZATION_V1_FIXTURE'
    plan: NextStepPlan


class NextStepExecutionRecord(ExecutionRecord):
    state: Literal['NEXT_STEP_EXECUTION_STAGED'] = 'NEXT_STEP_EXECUTION_STAGED'
    previous_execution_id: UUID
    next_step_id: UUID


class NextStepExecutionService(FixtureExecutionService):
    """Reuse authorization TTL, single use, role checks, journal and staging CAS unchanged."""
    authorization_type = NextStepExecutionAuthorization
    record_type = NextStepExecutionRecord
    stage_state = 'NEXT_STEP_EXECUTION_STAGED'
    stage_prefix = 'NEXT_STEP_STAGE:'
    checkpoint_state = 'EXECUTOR_CONTINUE_HELD'
    policy_prefix = 'EXECUTOR'
    plan_type = NextStepPlan

    def _plan_extras(self, known):
        return {}

    def __init__(self, unit, provider, *, initialize=True):
        super().__init__(unit, provider, initialize=initialize)
        self._policy = ExecutorPolicyService(unit, provider, initialize=initialize)

    def _record_kwargs(self, plan):
        return {'previous_execution_id': plan.previous_execution_id, 'next_step_id': plan.next_step_id}

    def _plan(self, request, scope, followup_id, allowed_step, permission, *, checkpoint=None, provider_checkpoint=None):
        unit = self._unit
        state = unit._state if checkpoint is None else checkpoint
        unit._authorized(request, scope, permission)
        key, owner_key, op = unit._match(state, request)
        record = state.get('executor_policy_records', {}).get(followup_id)
        grant = state.get('executor_policy_authorizations', {}).get(followup_id)
        owner, lease, events = state['owners'][owner_key], state['leases'][key], state['outbox'][key]
        if (record is None or grant is None or type(grant.plan) is not ExecutorContinuePlan
                or record.kind != 'CONTINUE' or record.state != self.checkpoint_state or op.state != record.state
                or record.plan_hash != grant.plan.plan_hash() or record.execution_id != grant.plan.execution_id
                or record.decision_id != grant.plan.decision_id or record.owner_revision != owner.revision
                or owner.revision != grant.plan.owner_revision + 1 or owner.revision != op.owner_revision
                or owner.fence != op.fence or owner.fence != grant.plan.owner_fence + 1
                or owner.authority != request.plan.source or owner.active_request != request.request_id
                or op.revision != grant.plan.operation_revision + 1 or lease.status != 'DONE'
                or lease.operation_revision != op.revision or lease.token != grant.plan.worker_token + 1
                or held_checkpoint_hash(owner, op, lease, events) != record.checkpoint_fingerprint):
            raise ExecutionConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        if (not events or events[-1].event_id != uuid5(followup_id, record.plan_hash)
                or events[-1].step != self.policy_prefix + '_CONTINUE_REVIEW' or events[-1].status != 'HELD'):
            raise ExecutionConflict('POLICY_OUTBOX_CONFLICT')
        audit = [r for r in state['audit'] if r[:2] == key]
        if (not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, self.checkpoint_state)
                or sum(r[0] == followup_id and r[3] == 'CONSUMED' for r in state['executor_policy_audit']) != 1):
            raise ExecutionConflict('POLICY_AUDIT_CONFLICT')
        # Reuse the policy's complete decision/provider validator on an authenticated private predecessor image.
        prior = deepcopy(state)
        prior['owners'][owner_key] = owner.model_copy(update={'revision': grant.plan.owner_revision, 'fence': grant.plan.owner_fence})
        prior['journal'][key] = op.model_copy(update={'state': grant.plan.expected_state,
            'revision': grant.plan.operation_revision, 'owner_revision': grant.plan.owner_revision, 'fence': grant.plan.owner_fence})
        prior['leases'][key] = lease.model_copy(update={'token': grant.plan.worker_token, 'operation_revision': grant.plan.operation_revision})
        prior['outbox'][key] = events[:-1]
        last = next(i for i in range(len(prior['audit']) - 1, -1, -1) if prior['audit'][i][:2] == key)
        del prior['audit'][last]
        data = self._policy._checkpoint(request, scope, record.decision_id, permission, checkpoint=prior, provider_checkpoint=provider_checkpoint)
        if ExecutorContinuePlan(**data) != grant.plan:
            raise ExecutionConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        decision = state['executor_decision_records'][record.decision_id]
        previous = state['execution_authorizations'][record.execution_id].plan
        provider_state = self._provider._state if provider_checkpoint is None else provider_checkpoint
        known = provider_state['executor_receipts'].get(record.execution_id)
        if decision.decision != 'CONFIRM_SUCCESS' or known is None or known.outcome != 'SUCCESS':
            raise ExecutionConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        sequence = previous.step_sequence + 1
        if sequence > len(request.plan.steps) or request.plan.steps[sequence - 1] != allowed_step:
            raise ExecutionConflict('WRONG_NEXT_STEP_OR_NO_REMAINING_STEP')
        head = [e for e in events if e.event_id == known.event_id]
        if len(head) != 1 or (head[0].status, head[0].result) != ('ACKED', 'APPLIED') or any(e.status == 'PENDING' for e in events):
            raise ExecutionConflict('PREVIOUS_UNKNOWN_NOT_AUTHORIZED_RESOLVED')
        current = provider_state['provider']
        if (allowed_step == 'ENABLE_RADIUS' and not (not current.local_enabled and current.radius_state == 'DISABLED'
                    and current.fenced_request == request.request_id and current.owner_fence == known.owner_fence)
                or allowed_step == 'COMMIT_OWNER_CAS' and not (not current.local_enabled and current.radius_state == 'ENABLED'
                    and current.fenced_request == request.request_id and current.owner_fence > 0)):
            raise ExecutionConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        next_id = uuid5(followup_id, 'NEXT_STEP_V1:' + request.plan.tenant_id + ':' + str(record.execution_id)
                        + ':' + str(sequence) + ':' + decision.evaluation.evidence_fingerprint)
        digest = canonical_hash({'held': record.checkpoint_fingerprint, 'policy': record.model_dump(mode='json'),
                                 'verified_predecessor': ExecutorContinuePlan(**data).model_dump(mode='json'), 'next_step_id': str(next_id)})
        ref = request.plan.snapshot.reference
        return self.plan_type(tenant_id=request.plan.tenant_id, store=ref.store, subscriber_id=ref.account_id,
            request_id=request.request_id, continue_plan_hash=record.plan_hash, followup_id=followup_id,
            policy_id=followup_id, previous_execution_id=record.execution_id, next_step_id=next_id,
            decision_id=record.decision_id, evidence_fingerprint=decision.evaluation.evidence_fingerprint,
            provider_evidence_fingerprint=decision.evaluation.provider_evidence_fingerprint,
            owner_revision=owner.revision, operation_revision=op.revision, owner_fence=owner.fence, worker_token=lease.token,
            allowed_step=allowed_step, step_sequence=sequence, previous_event_id=known.event_id, checkpoint_fingerprint=digest, **self._plan_extras(known))
