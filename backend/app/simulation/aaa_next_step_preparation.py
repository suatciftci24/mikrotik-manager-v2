"""Preparation data only: reuse the existing TTL registry and atomic staging engine."""
from typing import Literal
from uuid import UUID
from pydantic import Field
from app.simulation.aaa_atomic import canonical_hash
from app.simulation.aaa_execution import ExecutionAuthorization, ExecutionRecord, ExecutionIntent, ExecutionConflict
from app.simulation.aaa_next_step import NextStepPlan, NextStepExecutionService
from app.simulation.aaa_executor_policy import ExecutorPolicyAuthorization, ExecutorPolicyRecord


class NextStepPreparationPlan(NextStepPlan):
    contract_version: Literal['NEXT_STEP_PREPARATION_PLAN_V1_FIXTURE'] = 'NEXT_STEP_PREPARATION_PLAN_V1_FIXTURE'
    expected_state: Literal['NEXT_STEP_CONTINUE_HELD'] = 'NEXT_STEP_CONTINUE_HELD'
    previous_attempt_id: UUID
    unknown_receipt_fingerprint: str
    reference_version: Literal['NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE'] = 'NEXT_STEP_UNKNOWN_REFERENCE_V1_FIXTURE'
    allowed_step: Literal['COMMIT_OWNER_CAS'] = 'COMMIT_OWNER_CAS'
    step_sequence: int = Field(default=4, ge=4, le=4)
    execution_authorized: Literal[False] = False


class NextStepPreparationAuthorization(ExecutionAuthorization):
    version: Literal['NEXT_STEP_PREPARATION_AUTH_V1_FIXTURE'] = 'NEXT_STEP_PREPARATION_AUTH_V1_FIXTURE'
    plan: NextStepPreparationPlan


class NextStepPreparationRecord(ExecutionRecord):
    state: Literal['NEXT_STEP_PREPARED_HELD'] = 'NEXT_STEP_PREPARED_HELD'
    previous_execution_id: UUID
    next_step_id: UUID
    execution_authorized: Literal[False] = False


class NextStepPreparationService(NextStepExecutionService):
    authorization_type = NextStepPreparationAuthorization
    record_type = NextStepPreparationRecord
    plan_type = NextStepPreparationPlan
    checkpoint_state = 'NEXT_STEP_CONTINUE_HELD'
    policy_prefix = 'NEXT_STEP'
    stage_state = 'NEXT_STEP_PREPARED_HELD'
    stage_prefix = 'NEXT_STEP_PREPARE:'

    def _plan_extras(self, known):
        accepted = self._unit._state['executor_accepted'].get(known.execution_id)
        if accepted is None or accepted.reconciliation_reference is None:
            raise ExecutionConflict('MISSING_NEXT_STEP_UNKNOWN_REFERENCE')
        return dict(previous_attempt_id=known.attempt_id,
                    unknown_receipt_fingerprint=canonical_hash(accepted.receipt.model_dump(mode='json')))

    def _plan(self, request, scope, followup_id, allowed_step, permission, **kwargs):
        self._unit._authorized(request, scope, permission)
        policy = self._unit._state.get('executor_policy_authorizations', {}).get(followup_id)
        record = self._unit._state.get('executor_policy_records', {}).get(followup_id)
        if (type(policy) is not ExecutorPolicyAuthorization or type(record) is not ExecutorPolicyRecord
                or policy.version != 'EXECUTOR_POLICY_AUTH_V1_FIXTURE'
                or policy.authorization_id != followup_id or record.authorization_id != followup_id
                or policy.plan.contract_version != 'EXECUTOR_CONTINUE_POLICY_V1_FIXTURE'
                or policy.plan.expected_state != 'NEXT_STEP_DECISION_RECORDED'):
            raise ExecutionConflict('NEXT_STEP_CONTINUE_AUTHORIZATION_REQUIRED')
        plan = super()._plan(request, scope, followup_id, allowed_step, permission, **kwargs)
        for record in self._unit._state.get('execution_records', {}).values():
            if type(record) is NextStepPreparationRecord and record.next_step_id == plan.next_step_id:
                raise ExecutionConflict('STEP_ALREADY_PREPARED')
        return plan

    def issue(self, request, scope, authority, plan, intent, *, permission=False):
        if type(plan) is not NextStepPreparationPlan:
            raise ExecutionConflict('PREPARATION_PLAN_REQUIRED')
        intent = ExecutionIntent.model_validate_json(intent.model_dump_json())
        return super().issue(request, scope, authority, plan, intent, permission=permission)

    def stage(self, request, scope, authority, grant, *, permission=False, fail_at=None):
        # Even the inherited stage entry point can produce preparation data only.
        if (type(grant) is not NextStepPreparationAuthorization
                or grant.version != 'NEXT_STEP_PREPARATION_AUTH_V1_FIXTURE'
                or type(grant.plan) is not NextStepPreparationPlan):
            raise ExecutionConflict('PREPARATION_AUTHORIZATION_REQUIRED')
        return super().stage(request, scope, authority, grant, permission=permission, fail_at=fail_at)

    def prepare(self, request, scope, authority, grant, *, permission=False, fail_at=None):
        return self.stage(request, scope, authority, grant, permission=permission, fail_at=fail_at)
