"""Single-step memory executor. Fake effect and atomic receipt acceptance are separate."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, field_validator
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, ProviderEvidence, ProviderCommand, _transition
from app.simulation.aaa_followup import held_checkpoint_hash


class ExecutorConflict(AtomicConflict):
    pass


class FixtureCrash(RuntimeError):
    pass


class ExecutorContext(ReadContract):
    environment: Literal['AAA_EXECUTOR_FIXTURE_ONLY'] = 'AAA_EXECUTOR_FIXTURE_ONLY'
    tenant_id: str
    worker_id: str
    can_execute: bool = False
    can_accept: bool = False
    can_record_timeout: bool = False


class AttemptIntent(ReadContract):
    attempt_id: UUID
    seconds: int = Field(default=30, ge=1, le=300)


class ExecutorCommand(ReadContract):
    contract_version: Literal['AAA_FIXTURE_EXECUTOR_V1'] = 'AAA_FIXTURE_EXECUTOR_V1'
    execution_id: UUID
    tenant_id: str
    request_id: UUID
    subscriber_id: str
    event_id: UUID
    attempt_id: UUID
    plan_hash: str
    allowed_step: Literal['FENCE_LOCAL', 'ENABLE_RADIUS', 'COMMIT_OWNER_CAS']
    owner_revision: int
    owner_fence: int
    fencing_token: int
    worker_id: str
    expires_at: datetime

    @field_validator('expires_at')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Aware fixture attempt expiry required')
        return value.astimezone(timezone.utc)


class ExecutorReceipt(ExecutorCommand):
    receipt_version: Literal['AAA_EXECUTOR_RECEIPT_V1_FIXTURE'] = 'AAA_EXECUTOR_RECEIPT_V1_FIXTURE'
    provider_evidence_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    outcome: Literal['SUCCESS', 'REJECTED', 'UNKNOWN']


class ReceiptAcceptance(ReadContract):
    receipt: ExecutorReceipt
    owner_revision: int
    operation_revision: int
    state: Literal['FIXTURE_STEP_SUCCEEDED', 'FIXTURE_STEP_REJECTED', 'FIXTURE_STEP_UNKNOWN']
    reconciliation_required: bool
    checkpoint_fingerprint: str
    automatic_retry: Literal[False] = False
    provider_dispatch: Literal[False] = False
    external_writes: Literal[False] = False


class FixtureExecutor:
    def __init__(self, unit, provider, *, outcome='SUCCESS'):
        if type(unit) is not LeasedMemoryOutbox or type(provider) is not FakeFencedProvider:
            raise TypeError('Explicit memory fixtures required')
        if outcome not in ('SUCCESS', 'REJECTED', 'UNKNOWN', 'APPLY_THEN_UNKNOWN'):
            raise ValueError('Unsupported fixture outcome')
        self._unit, self._provider, self._outcome = unit, provider, outcome
        with unit._lock, provider._lock:
            for key, empty in (('executor_claims', {}), ('executor_attempts', set()), ('executor_status', {}),
                               ('executor_accepted', {}), ('executor_audit', []), ('executor_provider_sources', {})):
                unit._state.setdefault(key, empty)
            provider._state.setdefault('executor_receipts', {})

    def _scope(self, request, scope, context, permission, flag):
        self._unit._authorized(request, scope, permission)
        if (type(context) is not ExecutorContext or context.environment != 'AAA_EXECUTOR_FIXTURE_ONLY'
                or context.tenant_id != request.plan.tenant_id or not getattr(context, flag)):
            raise PermissionError('SEPARATE_FIXTURE_EXECUTOR_PERMISSION_REQUIRED')

    def _staged(self, request, execution_id):
        unit = self._unit
        key, owner_key, op = unit._match(unit._state, request)
        if op.state == 'FIXTURE_STEP_UNKNOWN':
            raise ExecutorConflict('READ_ONLY_RECONCILIATION_REQUIRED')
        staged = unit._state.get('execution_records', {}).get(execution_id)
        grant = unit._state.get('execution_authorizations', {}).get(execution_id)
        owner, lease, events = unit._state['owners'][owner_key], unit._state['leases'][key], unit._state['outbox'][key]
        if (staged is None or grant is None or op.state != 'FIXTURE_EXECUTION_STAGED'
                or staged.execution_plan_hash != grant.plan.plan_hash() or staged.allowed_step != grant.plan.allowed_step
                or staged.owner_revision != owner.revision or owner.revision != op.owner_revision
                or owner.revision != grant.plan.owner_revision + 1 or owner.fence != staged.owner_fence
                or owner.fence != op.fence or owner.fence != grant.plan.owner_fence + 1
                or owner.active_request != request.request_id or owner.authority != request.plan.source
                or lease.status != 'DONE' or lease.token != staged.worker_token or lease.operation_revision != op.revision
                or held_checkpoint_hash(owner, op, lease, events) != staged.checkpoint_fingerprint
                or events[-1].event_id != uuid5(execution_id, staged.execution_plan_hash)
                or events[-1].step != 'FIXTURE_STAGE:' + staged.allowed_step or events[-1].status != 'HELD'
                or events[-1].plan_hash != staged.execution_plan_hash or self._provider._account != owner_key):
            raise ExecutorConflict('STAGED_OWNER_FENCE_EVENT_OR_PLAN_CONFLICT')
        audit = [r for r in unit._state['audit'] if r[:2] == key]
        if (staged.continue_plan_hash != grant.plan.continue_plan_hash or staged.decision_id != grant.plan.decision_id
                or op.revision != grant.plan.operation_revision + 1 or lease.token != grant.plan.worker_token + 1
                or not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash,
                                                 op.revision, 'FIXTURE_EXECUTION_STAGED')
                or sum(r[0] == execution_id and r[3] == 'CONSUMED' for r in unit._state['execution_audit']) != 1):
            raise ExecutorConflict('STAGED_AUTHORIZATION_OR_AUDIT_CONFLICT')
        return key, owner_key, op, owner, staged, grant.plan, events[-1]

    def _evidence(self, request):
        provider = self._provider
        receipts = tuple(sorted((r for (tenant, req, _), r in provider._state['receipts'].items()
            if (tenant, req) == (request.plan.tenant_id, request.request_id)), key=lambda r: r.command.sequence))
        return ProviderEvidence(tenant_id=request.plan.tenant_id, account_id=request.plan.snapshot.reference.account_id,
            plan_hash=request.plan.plan_hash(), complete=bool(receipts) and all(r.outcome == 'APPLIED' for r in receipts),
            receipts=receipts, current=provider._state['provider'])

    def _receipt_hash(self, command):
        return canonical_hash({'command': command.model_dump(mode='json'),
                               'provider': self._provider._state['provider'].model_dump(mode='json')})

    def _command(self, request, command, context, *, expired=False, coordinator=False):
        unit = self._unit
        stored = unit._state['executor_claims'].get(command.execution_id)
        if (unit._state['executor_provider_sources'].get(command.execution_id) != id(self._provider)
                or stored != command or command.request_id != request.request_id or command.tenant_id != request.plan.tenant_id
                or command.subscriber_id != request.plan.snapshot.reference.account_id
                or not coordinator and command.worker_id != context.worker_id
                or not expired and unit._clock.now() >= command.expires_at):
            raise ExecutorConflict('UNKNOWN_FOREIGN_OR_EXPIRED_ATTEMPT')
        binding = self._staged(request, command.execution_id)
        _, _, _, owner, staged, _, event = binding
        if (command.owner_revision != owner.revision or command.owner_fence != owner.fence
                or command.fencing_token != staged.worker_token or command.event_id != event.event_id
                or command.plan_hash != staged.execution_plan_hash or command.allowed_step != staged.allowed_step):
            raise ExecutorConflict('ATTEMPT_REVISION_FENCE_OR_CONTENT_CONFLICT')
        return binding

    def claim(self, request, scope, context, execution_id, intent: AttemptIntent, *, permission=False):
        self._scope(request, scope, context, permission, 'can_execute')
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction():
            if execution_id in unit._state['executor_claims']:
                existing = unit._state['executor_claims'][execution_id]
                if existing.attempt_id != intent.attempt_id:
                    raise ExecutorConflict('EXECUTION_ATTEMPT_ALREADY_BOUND')
                self._command(request, existing, context)
                return existing
            _, _, _, owner, staged, plan, event = self._staged(request, execution_id)
            proof = self._evidence(request)
            if not proof.complete or canonical_hash(proof.model_dump(mode='json')) != plan.provider_evidence_fingerprint:
                raise ExecutorConflict('READ_ONLY_RECONCILIATION_REQUIRED')
            attempt_key = (request.plan.tenant_id, intent.attempt_id)
            if attempt_key in unit._state['executor_attempts']:
                raise ExecutorConflict('ATTEMPT_UUID_REUSED')
            command = ExecutorCommand(execution_id=execution_id, tenant_id=request.plan.tenant_id, request_id=request.request_id,
                subscriber_id=request.plan.snapshot.reference.account_id, event_id=event.event_id,
                attempt_id=intent.attempt_id, plan_hash=staged.execution_plan_hash, allowed_step=staged.allowed_step,
                owner_revision=owner.revision, owner_fence=owner.fence, fencing_token=staged.worker_token,
                worker_id=context.worker_id, expires_at=unit._clock.now() + timedelta(seconds=intent.seconds))
            source = unit._state['executor_provider_sources'].get(execution_id)
            if source is not None and source != id(self._provider):
                raise ExecutorConflict('WRONG_FIXTURE_PROVIDER_SOURCE')
            unit._state['executor_provider_sources'][execution_id] = id(self._provider)
            unit._state['executor_claims'][execution_id] = command
            unit._state['executor_attempts'].add(attempt_key)
            unit._state['executor_status'][execution_id] = 'CLAIMED'
            return command

    def run(self, request, scope, context, command, *, permission=False, crash=None):
        self._scope(request, scope, context, permission, 'can_execute')
        if crash not in (None, 'AFTER_DISPATCH', 'AFTER_EFFECT'):
            raise ValueError('Unknown fixture crash')
        unit, provider = self._unit, self._provider
        with unit._lock, provider._lock:
            _, _, _, _, _, plan, _ = self._command(request, command, context)
            status = unit._state['executor_status'][command.execution_id]
            if status == 'RESPONDED':
                known = provider._state['executor_receipts'][command.execution_id]
                if known.provider_evidence_fingerprint != self._receipt_hash(command):
                    raise ExecutorConflict('READ_ONLY_RECONCILIATION_REQUIRED')
                return known
            if status != 'CLAIMED':
                raise ExecutorConflict('READ_ONLY_RECONCILIATION_REQUIRED')
            proof = self._evidence(request)
            if not proof.complete or canonical_hash(proof.model_dump(mode='json')) != plan.provider_evidence_fingerprint:
                raise ExecutorConflict('READ_ONLY_RECONCILIATION_REQUIRED')
            token = (command.owner_fence, command.fencing_token)
            if token <= provider._state['highest']:
                raise ExecutorConflict('STALE_PROVIDER_FENCE')
            with unit._transaction():
                unit._state['executor_status'][command.execution_id] = 'IN_FLIGHT'
                unit._state['executor_audit'].append((command.execution_id, command.attempt_id, 'STARTED', unit._clock.now()))
            if crash == 'AFTER_DISPATCH':
                raise FixtureCrash('Fixture dispatch outcome unknown')
            candidate = deepcopy(provider._state)
            current = candidate['provider']
            if self._outcome in ('SUCCESS', 'APPLY_THEN_UNKNOWN') and command.allowed_step != 'COMMIT_OWNER_CAS':
                candidate['provider'] = fixture_effect(request, command, plan.step_sequence, current, operation_revision=plan.operation_revision + 1)
            candidate['highest'] = token
            outcome = 'UNKNOWN' if self._outcome == 'APPLY_THEN_UNKNOWN' else self._outcome
            receipt = ExecutorReceipt(**command.model_dump(), outcome=outcome,
                provider_evidence_fingerprint=canonical_hash({'command': command.model_dump(mode='json'),
                    'provider': candidate['provider'].model_dump(mode='json')}))
            candidate['executor_receipts'][command.execution_id] = receipt
            provider._state = candidate
            if crash == 'AFTER_EFFECT':
                raise FixtureCrash('Fixture response lost after possible effect')
            with unit._transaction():
                unit._state['executor_status'][command.execution_id] = 'RESPONDED'
            return receipt

    def _accept(self, request, context, command, receipt, *, coordinator=False, fail_at=None):
        unit, provider = self._unit, self._provider
        if (unit._state['executor_provider_sources'].get(command.execution_id) != id(provider)
                or command.request_id != request.request_id or unit._state['executor_claims'].get(command.execution_id) != command):
            raise ExecutorConflict('UNKNOWN_ATTEMPT')
        previous = unit._state['executor_accepted'].get(command.execution_id)
        key, owner_key, op = unit._match(unit._state, request)
        owner, lease = unit._state['owners'][owner_key], unit._state['leases'][key]
        if previous:
            if (receipt != previous.receipt or owner.revision != previous.owner_revision
                    or op.revision != previous.operation_revision or owner.fence != command.owner_fence
                    or lease.token != command.fencing_token
                    or held_checkpoint_hash(owner, op, lease, unit._state['outbox'][key]) != previous.checkpoint_fingerprint
                    or not coordinator and (context.worker_id != command.worker_id or unit._clock.now() >= command.expires_at)):
                raise ExecutorConflict('DUPLICATE_RECEIPT_CONTENT_OR_STALE_FENCE')
            return previous
        _, _, op, owner, _, _, _ = self._command(request, command, context, expired=coordinator, coordinator=coordinator)
        if unit._state['executor_status'][command.execution_id] not in ('IN_FLIGHT', 'RESPONDED'):
            raise ExecutorConflict('RECEIPT_WITHOUT_EXECUTION')
        if (not coordinator and provider._state['executor_receipts'].get(command.execution_id) != receipt
                or receipt.provider_evidence_fingerprint != self._receipt_hash(command)):
            raise ExecutorConflict('UNTRUSTED_OR_STALE_PROVIDER_RECEIPT')
        state = {'SUCCESS': 'FIXTURE_STEP_SUCCEEDED', 'REJECTED': 'FIXTURE_STEP_REJECTED', 'UNKNOWN': 'FIXTURE_STEP_UNKNOWN'}[receipt.outcome]
        with unit._transaction(fail_at):
            final_owner = command.allowed_step == 'COMMIT_OWNER_CAS' and receipt.outcome == 'SUCCESS'
            owner = owner.model_copy(update={'revision': owner.revision + 1,
                'authority': request.plan.target if final_owner else owner.authority,
                'active_request': None if final_owner else owner.active_request})
            op = op.model_copy(update={'state': state, 'revision': op.revision + 1, 'owner_revision': owner.revision})
            unit._state['owners'][owner_key], unit._state['journal'][key] = owner, op
            unit._state['leases'][key] = lease.model_copy(update={'operation_revision': op.revision})
            events = tuple(e.model_copy(update={'status': 'ACKED' if receipt.outcome == 'SUCCESS' else
                'CANCELLED' if receipt.outcome == 'REJECTED' else 'UNKNOWN',
                'result': {'SUCCESS': 'APPLIED', 'REJECTED': 'NOT_APPLIED', 'UNKNOWN': 'UNKNOWN'}[receipt.outcome]})
                if e.event_id == command.event_id else e for e in unit._state['outbox'][key])
            unit._state['outbox'][key] = events
            accepted = ReceiptAcceptance(receipt=receipt, owner_revision=owner.revision, operation_revision=op.revision,
                                          state=state, reconciliation_required=receipt.outcome == 'UNKNOWN',
                checkpoint_fingerprint=held_checkpoint_hash(owner, op, unit._state['leases'][key], events))
            unit._state['executor_accepted'][command.execution_id] = accepted
            unit._state['executor_status'][command.execution_id] = 'ACCEPTED'
            unit._audit(unit._state, request, op, state)
            unit._state['executor_audit'].append((command.execution_id, command.attempt_id, state, unit._clock.now()))
            return accepted

    def accept(self, request, scope, context, receipt: ExecutorReceipt, *, permission=False, fail_at=None):
        self._scope(request, scope, context, permission, 'can_accept')
        command = ExecutorCommand(**receipt.model_dump(exclude={'receipt_version', 'provider_evidence_fingerprint', 'outcome'}))
        with self._unit._lock, self._provider._lock:
            return self._accept(request, context, command, receipt, fail_at=fail_at)

    def timeout(self, request, scope, context, command, *, permission=False, fail_at=None):
        self._scope(request, scope, context, permission, 'can_record_timeout')
        with self._unit._lock, self._provider._lock:
            previous = self._unit._state['executor_accepted'].get(command.execution_id)
            if previous and previous.receipt.outcome != 'UNKNOWN':
                raise ExecutorConflict('DEFINITE_RESULT_ALREADY_ACCEPTED')
            receipt = previous.receipt if previous else ExecutorReceipt(**command.model_dump(), outcome='UNKNOWN',
                provider_evidence_fingerprint=self._receipt_hash(command))
            return self._accept(request, context, command, receipt, coordinator=True, fail_at=fail_at)

    def unknown_evidence(self, request, scope, context, execution_id, *, permission=False):
        self._scope(request, scope, context, permission, 'can_record_timeout')
        with self._unit._lock, self._provider._lock:
            accepted = self._unit._state['executor_accepted'].get(execution_id)
            if accepted is None or accepted.receipt.request_id != request.request_id or not accepted.reconciliation_required:
                raise ExecutorConflict('UNKNOWN_RECONCILIATION_REQUIRED')
            return deepcopy({'accepted': accepted, 'provider_receipt': self._provider._state['executor_receipts'].get(execution_id),
                'provider_state': self._provider._state['provider'], 'unit': self._unit.snapshot()})


def fixture_effect(request, command, sequence, current, *, operation_revision):
    """Shared pure effect check for execution and independent evidence verification."""
    if command.allowed_step == 'COMMIT_OWNER_CAS':
        return current
    source_fence = current.owner_fence if command.allowed_step == 'ENABLE_RADIUS' else command.owner_fence
    root_command = ProviderCommand(tenant_id=command.tenant_id, account_id=command.subscriber_id,
        store=request.plan.snapshot.reference.store, request_id=request.request_id,
        correlation_id=request.correlation_id, request_fingerprint=request.fingerprint(),
        plan_hash=command.plan_hash, event_id=command.event_id, sequence=sequence,
        step=command.allowed_step, worker_id=command.worker_id, attempt_id=command.attempt_id,
        owner_fence=source_fence, worker_token=command.fencing_token, operation_revision=operation_revision)
    return _transition(root_command, current, 'APPLIED')
