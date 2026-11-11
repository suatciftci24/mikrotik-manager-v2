"""Read-only executor UNKNOWN evidence and separately authorized memory decision."""
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, OutboxFixture, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, ProviderEvidence, ProviderState, ProviderReceipt
from app.simulation.aaa_followup import held_checkpoint_hash
from app.simulation.aaa_executor import ExecutorCommand, ExecutorReceipt, ReceiptAcceptance, fixture_effect
from app.simulation.aaa_execution import ExecutionRecord, ExecutionAuthorization


class ExecutorDecisionConflict(AtomicConflict):
    pass


class ExecutorEvidenceContext(ReadContract):
    environment: Literal['AAA_EXECUTOR_RECONCILIATION_FIXTURE_ONLY'] = 'AAA_EXECUTOR_RECONCILIATION_FIXTURE_ONLY'
    tenant_id: str
    actor_id: str
    can_evaluate: bool = False
    can_issue_decision: bool = False
    can_apply_decision: bool = False


class EvidenceEvaluation(ReadContract):
    version: Literal['EVIDENCE_EVALUATION_V1_FIXTURE'] = 'EVIDENCE_EVALUATION_V1_FIXTURE'
    source: Literal['PINNED_FAKE_PROVIDER_READER'] = 'PINNED_FAKE_PROVIDER_READER'
    tenant_id: str
    subscriber_id: str
    request_id: UUID
    execution_id: UUID
    event_id: UUID | None = None
    attempt_id: UUID | None = None
    plan_hash: str | None = None
    fencing_token: int | None = None
    owner_fence: int | None = None
    owner_revision: int | None = None
    operation_revision: int | None = None
    provider_evidence_fingerprint: str | None = None
    evidence_fingerprint: str
    status: Literal['CONFIRMED_SUCCESS', 'CONFIRMED_REJECTION', 'READ_ONLY_RECONCILIATION_REQUIRED']
    reason: str
    observed_at: datetime
    decision_authority: Literal[False] = False
    automatic_dispatch: Literal[False] = False


class ExecutorDecisionIntent(ReadContract):
    authorization_id: UUID
    decision: Literal['CONFIRM_SUCCESS', 'CONFIRM_REJECTION']
    seconds: int = Field(default=60, ge=1, le=300)


class AuthorizedExecutorDecision(ReadContract):
    version: Literal['AUTHORIZED_DECISION_V1_EXECUTOR_FIXTURE'] = 'AUTHORIZED_DECISION_V1_EXECUTOR_FIXTURE'
    authorization_id: UUID
    actor_id: str
    evaluation: EvidenceEvaluation
    decision: Literal['CONFIRM_SUCCESS', 'CONFIRM_REJECTION']
    issued_at: datetime
    expires_at: datetime


class ExecutorDecisionRecord(ReadContract):
    authorization_id: UUID
    evaluation: EvidenceEvaluation
    decision: Literal['CONFIRM_SUCCESS', 'CONFIRM_REJECTION']
    owner_revision: int
    operation_revision: int
    checkpoint_fingerprint: str
    state: Literal['EXECUTOR_DECISION_RECORDED'] = 'EXECUTOR_DECISION_RECORDED'
    automatic_dispatch: Literal[False] = False
    external_writes: Literal[False] = False


class ExecutorReconciliationService:
    def __init__(self, unit, provider):
        if type(unit) is not LeasedMemoryOutbox or type(provider) is not FakeFencedProvider:
            raise TypeError('Explicit memory fixtures required')
        self._unit, self._provider = unit, provider
        with unit._lock:
            for key, empty in (('executor_decision_authorizations', {}), ('executor_decision_records', {}),
                               ('executor_decision_audit', [])):
                unit._state.setdefault(key, empty)

    def _guard(self, request, scope, context, permission, capability):
        self._unit._authorized(request, scope, permission)
        if (type(context) is not ExecutorEvidenceContext
                or context.environment != 'AAA_EXECUTOR_RECONCILIATION_FIXTURE_ONLY'
                or context.tenant_id != request.plan.tenant_id or context.actor_id != scope.actor_id
                or not getattr(context, capability)):
            raise PermissionError('SEPARATE_EXECUTOR_EVIDENCE_OR_DECISION_PERMISSION_REQUIRED')

    def _evaluate(self, request, execution_id, *, checkpoint=None):
        unit, provider = self._unit, self._provider
        state = unit._state if checkpoint is None else checkpoint
        key, owner_key, op = unit._match(state, request)
        accepted = state.get('executor_accepted', {}).get(execution_id)
        staged = state.get('execution_records', {}).get(execution_id)
        grant = state.get('execution_authorizations', {}).get(execution_id)
        command = state.get('executor_claims', {}).get(execution_id)
        owner, lease, events = state['owners'][owner_key], state['leases'][key], state['outbox'][key]
        known = provider._state.get('executor_receipts', {}).get(execution_id)
        current = provider._state['provider']
        def dump(value):
            return value.model_dump(mode='json') if isinstance(value, ReadContract) else None
        fingerprint = canonical_hash({'version': 'EVIDENCE_EVALUATION_V1_FIXTURE', 'accepted': dump(accepted),
            'command': dump(command), 'staged': dump(staged), 'grant': dump(grant), 'provider_receipt': dump(known),
            'provider': dump(current), 'provider_fence': provider._state['highest'],
            'provider_source': state.get('executor_provider_sources', {}).get(execution_id),
            'reader_source': id(provider), 'owner': dump(owner),
            'journal': dump(op), 'lease': dump(lease), 'outbox': [dump(e) for e in events]})
        safe_command = command if type(command) is ExecutorCommand else None
        def result(status, reason):
            return EvidenceEvaluation(tenant_id=request.plan.tenant_id, subscriber_id=owner_key[2],
                request_id=request.request_id, execution_id=execution_id,
                event_id=safe_command.event_id if safe_command else None, attempt_id=safe_command.attempt_id if safe_command else None,
                plan_hash=safe_command.plan_hash if safe_command else None, fencing_token=safe_command.fencing_token if safe_command else None,
                owner_fence=owner.fence, owner_revision=owner.revision, operation_revision=op.revision,
                provider_evidence_fingerprint=known.provider_evidence_fingerprint if type(known) is ExecutorReceipt else None,
                evidence_fingerprint=fingerprint, status=status, reason=reason, observed_at=unit._clock.now())
        def blocked(reason):
            return result('READ_ONLY_RECONCILIATION_REQUIRED', reason)
        if (type(accepted) is not ReceiptAcceptance or type(command) is not ExecutorCommand
                or type(staged) is not ExecutionRecord or type(grant) is not ExecutionAuthorization
                or type(known) is not ExecutorReceipt or type(current) is not ProviderState or provider._account != owner_key
                or state.get('executor_provider_sources', {}).get(execution_id) != id(provider)):
            return blocked('MISSING_OR_UNVERIFIABLE_PROVIDER_SOURCE')
        unknown = accepted.receipt
        if (unknown.outcome != 'UNKNOWN' or accepted.state != 'FIXTURE_STEP_UNKNOWN'
                or not accepted.reconciliation_required or op.state != 'FIXTURE_STEP_UNKNOWN'
                or op.owner_revision != owner.revision or owner.revision != accepted.owner_revision
                or owner.revision != command.owner_revision + 1 or op.revision != accepted.operation_revision
                or owner.fence != command.owner_fence or owner.fence != op.fence
                or lease.token != command.fencing_token or lease.operation_revision != op.revision or lease.status != 'DONE'
                or owner.active_request != request.request_id or owner.authority != request.plan.source
                or held_checkpoint_hash(owner, op, lease, events) != accepted.checkpoint_fingerprint):
            return blocked('UNKNOWN_CHECKPOINT_CAS_OR_FENCING_CONFLICT')
        def receipt_command(receipt):
            return ExecutorCommand(**receipt.model_dump(exclude={'receipt_version', 'provider_evidence_fingerprint', 'outcome'}))
        if (receipt_command(unknown) != command or receipt_command(known) != command
                or command.request_id != request.request_id or command.tenant_id != request.plan.tenant_id
                or command.subscriber_id != owner_key[2] or command.execution_id != execution_id
                or command.plan_hash != staged.execution_plan_hash or command.plan_hash != grant.plan.plan_hash()
                or command.allowed_step != staged.allowed_step or command.allowed_step != grant.plan.allowed_step
                or command.event_id != uuid5(execution_id, command.plan_hash)
                or state['executor_status'].get(execution_id) != 'ACCEPTED'):
            return blocked('EXECUTION_EVENT_ATTEMPT_PLAN_OR_RECEIPT_CONFLICT')
        if (known.outcome not in ('SUCCESS', 'REJECTED')
                or provider._state['highest'] != (command.owner_fence, command.fencing_token)
                or known.provider_evidence_fingerprint != canonical_hash({'command': dump(command), 'provider': dump(current)})):
            return blocked('UNKNOWN_OR_STALE_PROVIDER_RESULT')
        prefix = [r for (tenant, req, _), r in provider._state['receipts'].items() if (tenant, req) == key]
        if any(type(r) is not ProviderReceipt for r in prefix):
            return blocked('UNVERIFIABLE_PROVIDER_PREFIX')
        receipts = tuple(sorted(prefix, key=lambda r: r.command.sequence))
        if not receipts or len(receipts) != grant.plan.step_sequence - 1 or any(r.outcome != 'APPLIED' for r in receipts):
            return blocked('INCOMPLETE_INDEPENDENT_PROVIDER_PREFIX')
        before = receipts[-1].after
        pre_evidence = ProviderEvidence(tenant_id=request.plan.tenant_id, account_id=owner_key[2], plan_hash=op.plan_hash,
                                        complete=True, receipts=receipts, current=before)
        if canonical_hash(pre_evidence.model_dump(mode='json')) != grant.plan.provider_evidence_fingerprint:
            return blocked('PRIOR_PROVIDER_EVIDENCE_CHANGED')
        try:
            expected = fixture_effect(request, command, grant.plan.step_sequence, before, operation_revision=grant.plan.operation_revision + 1) if known.outcome == 'SUCCESS' else before
        except AtomicConflict:
            return blocked('CONTRADICTORY_PROVIDER_EFFECT')
        if expected != current:
            return blocked('CONTRADICTORY_PROVIDER_EFFECT')
        head = [e for e in events if e.event_id == command.event_id]
        audit = [r for r in state['audit'] if r[:2] == key]
        if (len(head) != 1 or head[0].status != 'UNKNOWN' or head[0].result != 'UNKNOWN'
                or head[0].step != 'FIXTURE_STAGE:' + command.allowed_step or head[0].plan_hash != command.plan_hash
                or any(e.status == 'PENDING' for e in events)
                or not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, 'FIXTURE_STEP_UNKNOWN')
                or sum(r[:3] == (execution_id, command.attempt_id, 'STARTED') for r in state['executor_audit']) != 1
                or sum(r[:3] == (execution_id, command.attempt_id, 'FIXTURE_STEP_UNKNOWN') for r in state['executor_audit']) != 1):
            return blocked('JOURNAL_OUTBOX_OR_EXECUTOR_AUDIT_CONFLICT')
        return result('CONFIRMED_SUCCESS' if known.outcome == 'SUCCESS' else 'CONFIRMED_REJECTION',
                      'INDEPENDENT_PROVIDER_EVIDENCE_CONSISTENT_NO_DECISION_GRANTED')

    def evaluate(self, request, scope, context, execution_id, *, permission=False):
        self._guard(request, scope, context, permission, 'can_evaluate')
        with self._unit._lock, self._provider._lock:
            return self._evaluate(request, execution_id)

    def _supported(self, decision, evaluation):
        expected = 'CONFIRMED_SUCCESS' if decision == 'CONFIRM_SUCCESS' else 'CONFIRMED_REJECTION'
        if evaluation.status != expected:
            raise ExecutorDecisionConflict('READ_ONLY_RECONCILIATION_REQUIRED')

    def issue(self, request, scope, context, evaluation: EvidenceEvaluation, intent: ExecutorDecisionIntent, *, permission=False):
        self._guard(request, scope, context, permission, 'can_issue_decision')
        self._guard(request, scope, context, permission, 'can_evaluate')
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction():
            if intent.authorization_id in unit._state['executor_decision_authorizations']:
                raise ExecutorDecisionConflict('AUTHORIZATION_ID_REUSED')
            fresh = self._evaluate(request, evaluation.execution_id)
            if fresh.model_dump(exclude={'observed_at'}) != evaluation.model_dump(exclude={'observed_at'}):
                raise ExecutorDecisionConflict('EVALUATION_SCOPE_OR_EVIDENCE_CHANGED')
            self._supported(intent.decision, fresh)
            now = unit._clock.now()
            grant = AuthorizedExecutorDecision(authorization_id=intent.authorization_id, actor_id=context.actor_id,
                evaluation=fresh, decision=intent.decision, issued_at=now, expires_at=now + timedelta(seconds=intent.seconds))
            unit._state['executor_decision_authorizations'][intent.authorization_id] = grant
            unit._state['executor_decision_audit'].append((intent.authorization_id, context.actor_id, 'ISSUED', fresh.evidence_fingerprint, now))
            return grant

    def apply(self, request, scope, context, grant: AuthorizedExecutorDecision, *, permission=False, fail_at=None):
        self._guard(request, scope, context, permission, 'can_apply_decision')
        self._guard(request, scope, context, permission, 'can_evaluate')
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction(None if fail_at == 'AUTHORIZATION' else fail_at):
            if unit._state['executor_decision_authorizations'].get(grant.authorization_id) != grant:
                raise ExecutorDecisionConflict('UNKNOWN_OR_TAMPERED_AUTHORIZATION')
            if grant.authorization_id in unit._state['executor_decision_records']:
                raise ExecutorDecisionConflict('AUTHORIZATION_ALREADY_USED')
            now = unit._clock.now()
            if context.actor_id != grant.actor_id or now < grant.issued_at or now >= grant.expires_at:
                raise ExecutorDecisionConflict('AUTHORIZATION_EXPIRED_OR_FOREIGN')
            fresh = self._evaluate(request, grant.evaluation.execution_id)
            if fresh.model_dump(exclude={'observed_at'}) != grant.evaluation.model_dump(exclude={'observed_at'}):
                raise ExecutorDecisionConflict('CAS_FENCE_SCOPE_OR_EVIDENCE_CHANGED')
            self._supported(grant.decision, fresh)
            key, owner_key, op = unit._match(unit._state, request)
            owner = unit._state['owners'][owner_key].model_copy(update={
                'revision': fresh.owner_revision + 1, 'fence': fresh.owner_fence + 1})
            op = op.model_copy(update={'state': 'EXECUTOR_DECISION_RECORDED', 'revision': op.revision + 1,
                                      'owner_revision': owner.revision, 'fence': owner.fence})
            unit._state['owners'][owner_key], unit._state['journal'][key] = owner, op
            events = tuple(e.model_copy(update={'status': 'ACKED' if grant.decision == 'CONFIRM_SUCCESS' else 'CANCELLED',
                'result': 'APPLIED' if grant.decision == 'CONFIRM_SUCCESS' else 'NOT_APPLIED'})
                if e.event_id == fresh.event_id else e for e in unit._state['outbox'][key])
            unit._state['outbox'][key] = events + (OutboxFixture(event_id=uuid5(grant.authorization_id, fresh.evidence_fingerprint),
                tenant_id=fresh.tenant_id, request_id=request.request_id, correlation_id=request.correlation_id,
                plan_hash=fresh.plan_hash, at=now, sequence=len(events) + 1, step='EXECUTOR_RECONCILIATION_DECISION', status='HELD'),)
            lease = unit._state['leases'][key].model_copy(update={'status': 'DONE', 'token': fresh.fencing_token + 1,
                                                                'operation_revision': op.revision})
            unit._state['leases'][key] = lease
            record = ExecutorDecisionRecord(authorization_id=grant.authorization_id, evaluation=fresh,
                decision=grant.decision, owner_revision=owner.revision, operation_revision=op.revision,
                checkpoint_fingerprint=held_checkpoint_hash(owner, op, lease, unit._state['outbox'][key]))
            unit._state['executor_decision_records'][grant.authorization_id] = record
            unit._audit(unit._state, request, op, 'EXECUTOR_DECISION_RECORDED')
            unit._record(lease, 'EXECUTOR_DECISION_RECORDED')
            unit._state['executor_decision_audit'].append((grant.authorization_id, context.actor_id, 'CONSUMED', fresh.evidence_fingerprint, now))
            if fail_at == 'AUTHORIZATION':
                raise ExecutorDecisionConflict('INJECTED_AUTHORIZATION_FAILURE')
            return record
