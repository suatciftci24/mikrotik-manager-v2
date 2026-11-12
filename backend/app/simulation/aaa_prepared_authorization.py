"""Separate prepared-step authorization metadata; creation/consumption never dispatches."""
from copy import copy, deepcopy
from typing import Literal
from uuid import UUID, uuid5
from app.simulation.aaa_atomic import canonical_hash
from app.simulation.aaa_followup import held_checkpoint_hash
from app.simulation.aaa_execution import FixtureExecutionService, ExecutionAuthorization, ExecutionIntent, ExecutionConflict
from app.simulation.aaa_next_step_preparation import (NextStepPreparationPlan, NextStepPreparationAuthorization,
    NextStepPreparationRecord, NextStepPreparationService)


class PreparedExecutionPlan(NextStepPreparationPlan):
    contract_version: Literal['PREPARED_EXECUTION_PLAN_V1_FIXTURE'] = 'PREPARED_EXECUTION_PLAN_V1_FIXTURE'
    expected_state: Literal['NEXT_STEP_PREPARED_HELD'] = 'NEXT_STEP_PREPARED_HELD'
    preparation_id: UUID
    preparation_fingerprint: str


class PreparedExecutionAuthorization(ExecutionAuthorization):
    version: Literal['PREPARED_EXECUTION_AUTH_V1_FIXTURE'] = 'PREPARED_EXECUTION_AUTH_V1_FIXTURE'
    plan: PreparedExecutionPlan


class PreparedExecutionRecord(NextStepPreparationRecord):
    state: Literal['EXECUTION_AUTHORIZED_HELD'] = 'EXECUTION_AUTHORIZED_HELD'
    preparation_id: UUID
    # Explicit fixture claim is separate; creating this checkpoint never dispatches.


class PreparedExecutionService(FixtureExecutionService):
    authorization_type = PreparedExecutionAuthorization
    record_type = PreparedExecutionRecord
    stage_state = 'EXECUTION_AUTHORIZED_HELD'
    stage_prefix = 'PREPARED_EXECUTION_AUTH:'

    def _record_kwargs(self, plan):
        return dict(previous_execution_id=plan.previous_execution_id, next_step_id=plan.next_step_id,
                    preparation_id=plan.preparation_id)

    def _plan(self, request, scope, followup_id, allowed_step, permission, *, provider_checkpoint=None):
        unit = self._unit
        unit._authorized(request, scope, permission)
        key, owner_key, op = unit._match(unit._state, request)
        grant = unit._state['execution_authorizations'].get(followup_id)
        record = unit._state['execution_records'].get(followup_id)
        owner, lease, events = unit._state['owners'][owner_key], unit._state['leases'][key], unit._state['outbox'][key]
        if (type(grant) is not NextStepPreparationAuthorization or type(record) is not NextStepPreparationRecord
                or type(grant.plan) is not NextStepPreparationPlan
                or grant.version != 'NEXT_STEP_PREPARATION_AUTH_V1_FIXTURE'
                or record.authorization_id != followup_id or grant.authorization_id != followup_id
                or record.state != 'NEXT_STEP_PREPARED_HELD' or op.state != record.state):
            raise ExecutionConflict('PREPARED_CHECKPOINT_REQUIRED')
        plan = grant.plan
        if (record.execution_plan_hash != plan.plan_hash() or record.allowed_step != allowed_step
                or plan.allowed_step != allowed_step or record.next_step_id != plan.next_step_id
                or record.previous_execution_id != plan.previous_execution_id
                or record.continue_plan_hash != plan.continue_plan_hash or record.decision_id != plan.decision_id
                or owner.revision != record.owner_revision or owner.revision != plan.owner_revision + 1
                or owner.fence != record.owner_fence or owner.fence != plan.owner_fence + 1
                or op.owner_revision != owner.revision or op.fence != owner.fence
                or op.revision != plan.operation_revision + 1 or owner.active_request != request.request_id
                or owner.authority != request.plan.source or lease.status != 'DONE'
                or lease.token != record.worker_token or lease.token != plan.worker_token + 1
                or lease.operation_revision != op.revision
                or held_checkpoint_hash(owner, op, lease, events) != record.checkpoint_fingerprint
                or not events or events[-1].event_id != uuid5(followup_id, plan.plan_hash())
                or events[-1].step != 'NEXT_STEP_PREPARE:' + allowed_step or events[-1].status != 'HELD'):
            raise ExecutionConflict('PREPARED_CAS_FENCE_PLAN_OR_EVENT_CONFLICT')
        audit = [row for row in unit._state['audit'] if row[:2] == key]
        if (not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, record.state)
                or sum(r[0] == followup_id and r[3] == 'CONSUMED' for r in unit._state['execution_audit']) != 1):
            raise ExecutionConflict('PREPARATION_AUDIT_CONFLICT')
        # Existing preparation validator receives a private predecessor image, never a rewound live UoW.
        shadow = copy(unit)
        shadow._state = deepcopy(unit._state)
        state = shadow._state
        state['owners'][owner_key] = owner.model_copy(update={'revision': plan.owner_revision, 'fence': plan.owner_fence})
        state['journal'][key] = op.model_copy(update={'state': plan.expected_state, 'revision': plan.operation_revision,
            'owner_revision': plan.owner_revision, 'fence': plan.owner_fence})
        state['leases'][key] = lease.model_copy(update={'token': plan.worker_token, 'operation_revision': plan.operation_revision})
        state['outbox'][key] = events[:-1]
        last = next(i for i in range(len(state['audit'])-1, -1, -1) if state['audit'][i][:2] == key)
        del state['audit'][last]
        del state['execution_records'][followup_id]
        fresh = NextStepPreparationService(shadow, self._provider, initialize=False)._plan(
            request, scope, plan.followup_id, allowed_step, permission, provider_checkpoint=provider_checkpoint)
        if fresh != plan:
            raise ExecutionConflict('PREPARATION_EVIDENCE_OR_ORDER_CHANGED')
        return PreparedExecutionPlan(**{**plan.model_dump(), 'contract_version':'PREPARED_EXECUTION_PLAN_V1_FIXTURE',
            'expected_state':'NEXT_STEP_PREPARED_HELD', 'followup_id':followup_id,
            'preparation_id':followup_id, 'preparation_fingerprint':canonical_hash(record.model_dump(mode='json')),
            'owner_revision':owner.revision, 'operation_revision':op.revision, 'owner_fence':owner.fence,
            'worker_token':lease.token, 'checkpoint_fingerprint':record.checkpoint_fingerprint})

    def issue(self, request, scope, authority, plan, intent, *, permission=False):
        if type(plan) is not PreparedExecutionPlan:
            raise ExecutionConflict('PREPARED_EXECUTION_PLAN_REQUIRED')
        intent = ExecutionIntent.model_validate_json(intent.model_dump_json())
        return super().issue(request, scope, authority, plan, intent, permission=permission)

    def stage(self, request, scope, authority, grant, *, permission=False, fail_at=None):
        if (type(grant) is not PreparedExecutionAuthorization or type(grant.plan) is not PreparedExecutionPlan
                or grant.version != 'PREPARED_EXECUTION_AUTH_V1_FIXTURE'):
            raise ExecutionConflict('PREPARED_EXECUTION_AUTHORIZATION_REQUIRED')
        return super().stage(request, scope, authority, grant, permission=permission, fail_at=fail_at)

    def consume(self, request, scope, authority, grant, *, permission=False, fail_at=None):
        return self.stage(request, scope, authority, grant, permission=permission, fail_at=fail_at)
