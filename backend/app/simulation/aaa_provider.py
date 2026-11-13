"""Fenced fake provider and read-only evidence assessment. No live adapter or IO."""
from copy import deepcopy
from threading import RLock
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox, LeaseConflict


class ProviderConflict(AtomicConflict):
    pass


class ProviderCommand(ReadContract):
    version: Literal['AAA_FAKE_PROVIDER_V1'] = 'AAA_FAKE_PROVIDER_V1'
    tenant_id: str
    account_id: str
    store: str
    request_id: UUID
    correlation_id: UUID
    request_fingerprint: str
    plan_hash: str
    event_id: UUID
    sequence: int = Field(ge=1, le=3)
    step: Literal['STAGE_DISABLED_TARGET', 'FENCE_LOCAL', 'ENABLE_RADIUS']
    worker_id: str
    attempt_id: UUID
    owner_fence: int = Field(ge=1)
    worker_token: int = Field(ge=1)
    operation_revision: int = Field(ge=1)

    def digest(self):
        return canonical_hash(self.model_dump(mode='json'))


class ProviderState(ReadContract):
    generation: int = 0
    local_enabled: bool = True
    radius_state: Literal['ABSENT', 'DISABLED', 'ENABLED'] = 'ABSENT'
    fenced_request: UUID | None = None
    owner_fence: int = 0


class ProviderReceipt(ReadContract):
    origin: Literal['FAKE_PROVIDER_EVIDENCE_ONLY'] = 'FAKE_PROVIDER_EVIDENCE_ONLY'
    command: ProviderCommand
    outcome: Literal['APPLIED', 'NOT_APPLIED', 'UNKNOWN']
    before: ProviderState
    after: ProviderState


class ProviderEvidence(ReadContract):
    origin: Literal['FAKE_PROVIDER_READ_ONLY'] = 'FAKE_PROVIDER_READ_ONLY'
    tenant_id: str
    account_id: str
    plan_hash: str
    complete: bool
    receipts: tuple[ProviderReceipt, ...]
    current: ProviderState


class ReconciliationAssessment(ReadContract):
    status: Literal['PROVIDER_APPLIED_CONFIRMED', 'PROVIDER_NOT_APPLIED_CONFIRMED',
                    'READ_ONLY_RECONCILIATION_REQUIRED']
    reason: str
    automatic_resume: Literal[False] = False
    live_ready: Literal[False] = False
    external_writes: Literal[False] = False


def _transition(command, before, outcome):
    after = before.model_copy(update={'generation': before.generation + 1})
    if outcome != 'APPLIED':
        return after
    if command.step == 'STAGE_DISABLED_TARGET' and before.local_enabled and before.radius_state == 'ABSENT':
        return after.model_copy(update={'radius_state': 'DISABLED'})
    if command.step == 'FENCE_LOCAL' and before.local_enabled and before.radius_state == 'DISABLED':
        return after.model_copy(update={'local_enabled': False, 'fenced_request': command.request_id,
                                        'owner_fence': command.owner_fence})
    if (command.step == 'ENABLE_RADIUS' and not before.local_enabled and before.radius_state == 'DISABLED'
            and before.fenced_request == command.request_id and before.owner_fence == command.owner_fence):
        return after.model_copy(update={'radius_state': 'ENABLED'})
    raise ProviderConflict('UNSAFE_PROVIDER_STATE')


def _unit(unit):
    if type(unit) is not LeasedMemoryOutbox:
        raise TypeError('Only the explicit leased memory fixture is accepted')


class FakeFencedProvider:
    """Independent caller-owned provider memory; outcomes are fixed fixture scripts."""
    def __init__(self, plan, *, outcomes=None, subscriber_adapter=None):
        if subscriber_adapter is not None:
            from app.adapters.aaa_freeradius import FreeRadiusFixtureAdapter
            from app.adapters.aaa_routeros import RouterOsFixtureAdapter
            if type(subscriber_adapter) not in (FreeRadiusFixtureAdapter,RouterOsFixtureAdapter):
                raise TypeError('ONLY_PURE_FIXTURE_ADAPTERS_ALLOWED')
        self.subscriber_adapter = subscriber_adapter
        outcomes = dict(outcomes or {})
        if any(k not in plan.steps[:3] or v not in ('APPLIED', 'NOT_APPLIED', 'UNKNOWN')
               for k, v in outcomes.items()):
            raise ValueError('Unsupported provider fixture script')
        self._account = (plan.tenant_id, plan.snapshot.reference.store, plan.snapshot.reference.account_id)
        self._outcomes = outcomes
        self._lock = RLock()
        self._state = {'provider': ProviderState(), 'highest': (0, 0), 'attempts': {}, 'receipts': {}}

    def snapshot(self):
        with self._lock:
            return deepcopy(self._state)

    def project_subscriber(self, command, current, now, *, include_mapping=False):
        """Pure fake effect; durable account/result is committed by the PG bridge.

        Unlike a remote device this projection has no independent side effect,
        so audit failure rolls back the entire synthetic operation.
        """
        from datetime import date, timedelta
        from zoneinfo import ZoneInfo
        from app.simulation.aaa_integration_preparation import SyntheticAaaCommand
        if type(command) is not SyntheticAaaCommand:
            raise PermissionError('TYPED_SYNTHETIC_COMMAND_REQUIRED')
        command = SyntheticAaaCommand.model_validate_json(command.model_dump_json())
        if self._account != (str(command.tenant_id), 'PERSISTENT_WORKSPACE', command.subscriber_id):
            raise PermissionError('PROVIDER_SUBSCRIBER_BINDING_REQUIRED')
        if current != command.before or now.utcoffset() is None:
            raise ProviderConflict('SUBSCRIBER_PREVIEW_CHANGED')
        if command.operation == 'EXTEND':
            if current.expires_on is None or command.days is None:
                raise ProviderConflict('KNOWN_EXPIRY_AND_DAYS_REQUIRED')
            today = now.astimezone(ZoneInfo('Europe/Istanbul')).date()
            expected = max(date.fromisoformat(current.expires_on), today) + timedelta(days=command.days)
            if command.after.expires_on != expected.isoformat():
                raise ProviderConflict('TURKEY_EXPIRY_PREVIEW_CHANGED')
        mapping = None
        if self.subscriber_adapter is not None:
            from app.adapters.aaa_freeradius import FreeRadiusFixtureAdapter
            from app.adapters.aaa_routeros import RouterOsFixtureAdapter
            if type(self.subscriber_adapter) not in (FreeRadiusFixtureAdapter,RouterOsFixtureAdapter):
                raise TypeError('ONLY_PURE_FIXTURE_ADAPTERS_ALLOWED')
            mapping = self.subscriber_adapter.prepare(command,now)
        return (command.after,mapping) if include_mapping else command.after

    def _command(self, unit, request, scope, context, lease, permission, *, allow_done=False):
        _unit(unit)
        key, current, op = unit._validated(request, scope, context, lease, permission, allow_done=allow_done)
        ref = request.plan.snapshot.reference
        if self._account != (request.plan.tenant_id, ref.store, ref.account_id):
            raise PermissionError('PROVIDER_ACCOUNT_SCOPE_DENIED')
        event = next(e for e in unit._state['outbox'][key] if e.event_id == current.event_id)
        if current.purpose != 'DELIVER' or not current.dispatched or event.step not in request.plan.steps[:3]:
            raise ProviderConflict('PROVIDER_DELIVERY_NOT_ALLOWED')
        dispatch = [r for r in unit._state['worker_audit'] if r[:4] ==
            (request.plan.tenant_id, request.request_id, current.event_id, op.plan_hash)
            and r[4:7] == (current.worker_id, current.attempt_id, current.token) and r[8] == 'DISPATCH']
        if len(dispatch) != 1:
            raise ProviderConflict('DISPATCH_EVIDENCE_REQUIRED')
        return ProviderCommand(tenant_id=request.plan.tenant_id, account_id=ref.account_id, store=ref.store,
            request_id=request.request_id, correlation_id=request.correlation_id,
            request_fingerprint=request.fingerprint(), plan_hash=op.plan_hash, event_id=event.event_id,
            sequence=event.sequence, step=event.step, worker_id=current.worker_id, attempt_id=current.attempt_id,
            owner_fence=op.fence, worker_token=current.token, operation_revision=dispatch[0][7])

    def command(self, unit, request, scope, context, lease, *, permission=False):
        _unit(unit)
        with unit._lock:
            return self._command(unit, request, scope, context, lease, permission)

    def execute(self, unit, request, scope, context, lease, command: ProviderCommand, *, permission=False):
        _unit(unit)
        # Fixed lock order; no lease/owner change can occur between validation and fake effect.
        with unit._lock, self._lock:
            expected = self._command(unit, request, scope, context, lease, permission, allow_done=True)
            # DONE permits only exact receipt replay, not an effect under a closed lease.
            if command != expected:
                raise ProviderConflict('PLAN_EVENT_ATTEMPT_OR_OWNER_MISMATCH')
            token = (command.owner_fence, command.worker_token)
            if token < self._state['highest']:
                raise ProviderConflict('STALE_PROVIDER_FENCE')
            attempt_key = (command.tenant_id, command.request_id, command.attempt_id)
            event_key = (command.tenant_id, command.request_id, command.event_id)
            used = self._state['attempts'].get(attempt_key)
            if used is not None and used != command.digest():
                raise ProviderConflict('ATTEMPT_CONTENT_CONFLICT')
            previous = self._state['receipts'].get(event_key)
            if previous:
                if previous.command != command:
                    raise ProviderConflict('EVENT_CONTENT_CONFLICT')
                return previous
            key, _, op = unit._match(unit._state, request)
            current = unit._state['leases'][key]
            if current.status != 'ACTIVE' or (used is None and token == self._state['highest']):
                raise ProviderConflict('CLOSED_OR_REUSED_PROVIDER_FENCE')
            prefix = sorted((r for (t, req, _), r in self._state['receipts'].items()
                if (t, req) == (command.tenant_id, command.request_id)), key=lambda r: r.command.sequence)
            if len(prefix) != command.sequence - 1 or any(r.outcome != 'APPLIED' for r in prefix):
                raise ProviderConflict('PROVIDER_ORDER_CONFLICT')
            before = self._state['provider']
            outcome = self._outcomes.get(command.step, 'APPLIED')
            after = _transition(command, before, outcome)
            receipt = ProviderReceipt(command=command, outcome=outcome, before=before, after=after)
            candidate = deepcopy(self._state)
            candidate['provider'], candidate['highest'] = after, token
            candidate['attempts'][attempt_key], candidate['receipts'][event_key] = command.digest(), receipt
            self._state = candidate
            return receipt

    def observe(self, unit, request, scope, context, lease, *, permission=False):
        _unit(unit)
        with unit._lock, self._lock:
            _, current, _ = unit._validated(request, scope, context, lease, permission)
            if current.purpose != 'RECONCILE':
                raise LeaseConflict('RECONCILIATION_LEASE_REQUIRED')
            receipts = tuple(sorted((r for (t, req, _), r in self._state['receipts'].items()
                if (t, req) == (request.plan.tenant_id, request.request_id)), key=lambda r: r.command.sequence))
            ref = request.plan.snapshot.reference
            if self._account != (request.plan.tenant_id, ref.store, ref.account_id):
                raise PermissionError('PROVIDER_ACCOUNT_SCOPE_DENIED')
            return ProviderEvidence(tenant_id=request.plan.tenant_id, account_id=ref.account_id,
                plan_hash=request.plan.plan_hash(), complete=bool(receipts) and all(r.outcome != 'UNKNOWN' for r in receipts),
                receipts=receipts, current=self._state['provider'])


def accept_provider_response(unit, provider, request, scope, context, lease, receipt, *, permission=False):
    """Validate both current lease and provider-owned receipt; never accept a caller ACK claim."""
    _unit(unit)
    if type(provider) is not FakeFencedProvider:
        raise TypeError('Explicit fake provider required')
    with unit._lock, provider._lock:
        expected = provider._command(unit, request, scope, context, lease, permission, allow_done=True)
        known = provider._state['receipts'].get((expected.tenant_id, expected.request_id, expected.event_id))
        if known is None or receipt != known or receipt.command != expected:
            raise ProviderConflict('UNTRUSTED_OR_CONTRADICTORY_RECEIPT')
        key, _, op = unit._match(unit._state, request)
        if unit._state['leases'][key].status == 'DONE':
            event = next(e for e in unit._state['outbox'][key] if e.event_id == expected.event_id)
            if event.result != receipt.outcome:
                raise ProviderConflict('ACK_NACK_RESULT_CONFLICT')
            return op
        if receipt.outcome == 'APPLIED':
            return unit.ack(request, scope, context, lease, permission=permission)
        return unit.nack(request, scope, context, lease, receipt.outcome, permission=permission)


def assess_unknown(request, recovery, state, evidence: ProviderEvidence):
    """Pure comparison; classification cannot ACK, resume, compensate or change ownership."""
    def blocked(reason):
        return ReconciliationAssessment(status='READ_ONLY_RECONCILIATION_REQUIRED', reason=reason)
    key = (request.plan.tenant_id, request.request_id)
    ref = request.plan.snapshot.reference
    op = state['journal'].get(key)
    owner = state['owners'].get((request.plan.tenant_id, ref.store, ref.account_id))
    events = state['outbox'].get(key, ())
    if (op is None or owner is None or op.state != 'RECONCILIATION'
            or op.plan_hash != request.plan.plan_hash() or op.fingerprint != request.fingerprint()
            or op.owner_revision != request.plan.expected_account_revision + 1
            or owner.revision != op.owner_revision or owner.active_request != request.request_id
            or owner.fence != op.fence or owner.authority != request.plan.source
            or recovery.operation_revision != op.revision or recovery.purpose != 'RECONCILE'
            or state['leases'].get(key) != recovery or recovery.status != 'ACTIVE'
            or evidence.tenant_id != request.plan.tenant_id or evidence.account_id != ref.account_id
            or evidence.plan_hash != op.plan_hash or not evidence.complete):
        return blocked('JOURNAL_OWNER_OR_PROVIDER_EVIDENCE_MISMATCH')
    audit = [r for r in state['audit'] if r[:2] == key]
    if not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, 'RECONCILIATION'):
        return blocked('JOURNAL_AUDIT_CONFLICT')
    unknown = [e for e in events if e.status == 'UNKNOWN']
    if len(unknown) != 1 or unknown[0].event_id != recovery.event_id or len(events) != len(request.plan.steps):
        return blocked('INCOMPLETE_OUTBOX_HISTORY')
    head = unknown[0]
    if head.sequence > 3 or len(evidence.receipts) != head.sequence:
        return blocked('MISSING_PROVIDER_PREFIX')
    for sequence, event in enumerate(events, 1):
        expected_id = uuid5(request.request_id, request.plan.tenant_id + ':' + op.plan_hash + ':' + str(sequence))
        if (event.sequence != sequence or event.event_id != expected_id or event.step != request.plan.steps[sequence - 1]
                or event.plan_hash != op.plan_hash or event.correlation_id != request.correlation_id
                or event.tenant_id != request.plan.tenant_id or event.request_id != request.request_id
                or sequence < head.sequence and (event.status != 'ACKED' or event.result != 'APPLIED')
                or sequence > head.sequence and (event.status != 'PENDING' or event.result is not None)):
            return blocked('CONTRADICTORY_OUTBOX_ORDER')
    previous_state = None
    for sequence, receipt in enumerate(evidence.receipts, 1):
        command, event = receipt.command, events[sequence - 1]
        dispatch = [row for row in state['worker_audit'] if row[:4] ==
                    (request.plan.tenant_id, request.request_id, command.event_id, op.plan_hash)
                    and row[4:9] == (command.worker_id, command.attempt_id, command.worker_token,
                                    command.operation_revision, 'DISPATCH')]
        if (command.sequence != sequence or command.event_id != event.event_id or command.step != event.step
                or command.plan_hash != op.plan_hash or command.request_fingerprint != op.fingerprint
                or command.tenant_id != request.plan.tenant_id or command.request_id != request.request_id
                or command.account_id != ref.account_id or command.store != ref.store
                or command.correlation_id != request.correlation_id or command.owner_fence != op.fence
                or command.worker_token >= recovery.token or len(dispatch) != 1
                or receipt.outcome == 'UNKNOWN' or sequence < head.sequence and receipt.outcome != 'APPLIED'
                or previous_state is not None and receipt.before != previous_state
                or receipt.after.generation != receipt.before.generation + 1):
            return blocked('PROVIDER_RECEIPT_OR_DISPATCH_CONFLICT')
        try:
            if (sequence == 1 and receipt.before != ProviderState()
                    or _transition(command, receipt.before, receipt.outcome) != receipt.after):
                return blocked('CONTRADICTORY_PROVIDER_STATE')
        except ProviderConflict:
            return blocked('CONTRADICTORY_PROVIDER_STATE')
        previous_state = receipt.after
    last = evidence.receipts[-1]
    if (evidence.current != last.after or last.command.operation_revision + 1 != op.revision
            or head.result not in ('UNKNOWN', last.outcome)):
        return blocked('LATE_OR_CONTRADICTORY_PROVIDER_RESULT')
    return ReconciliationAssessment(status='PROVIDER_APPLIED_CONFIRMED' if last.outcome == 'APPLIED'
                                    else 'PROVIDER_NOT_APPLIED_CONFIRMED',
                                    reason='STEP_EVIDENCE_CONSISTENT_OPERATION_REMAINS_RECONCILIATION')


def reconcile_unknown(unit, provider, request, scope, context, lease, *, permission=False):
    _unit(unit)
    if type(provider) is not FakeFencedProvider:
        raise TypeError('Explicit fake provider required')
    with unit._lock:
        _, current, _ = unit._validated(request, scope, context, lease, permission)
        proof = provider.observe(unit, request, scope, context, current, permission=permission)
        return assess_unknown(request, current, unit.snapshot(), proof)
