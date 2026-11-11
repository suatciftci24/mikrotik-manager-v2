"""Fenced worker rehearsal over the atomic fixture UoW. No timers, IO or live worker."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Literal
from uuid import UUID

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import MemoryAtomicUnit, AtomicConflict


class LeaseConflict(AtomicConflict):
    pass


class FakeLeaseClock:
    def __init__(self, at: datetime):
        if at.utcoffset() is None:
            raise ValueError('Aware fixture clock required')
        self._at = at.astimezone(timezone.utc)
        self._lock = RLock()

    def now(self):
        with self._lock:
            return self._at

    def advance(self, seconds: int):
        if type(seconds) is not int or seconds < 0:
            raise ValueError('Fixture clock cannot move backwards')
        with self._lock:
            self._at += timedelta(seconds=seconds)


class WorkerContext(ReadContract):
    tenant_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1, max_length=100)
    can_deliver: bool = False
    can_compensate: bool = False


class Claim(ReadContract):
    attempt_id: UUID
    seconds: int = Field(default=30, ge=1, le=300)
    purpose: Literal['DELIVER', 'RECONCILE'] = 'DELIVER'


class WorkerLease(ReadContract):
    version: Literal['AAA_WORKER_LEASE_V1_FIXTURE'] = 'AAA_WORKER_LEASE_V1_FIXTURE'
    tenant_id: str
    request_id: UUID
    plan_hash: str
    event_id: UUID
    worker_id: str
    attempt_id: UUID
    token: int = Field(ge=1)
    operation_revision: int = Field(ge=1)
    expires_at: datetime
    purpose: Literal['DELIVER', 'RECONCILE']
    status: Literal['ACTIVE', 'DONE', 'RELEASED'] = 'ACTIVE'
    dispatched: bool = False
    live_ready: Literal[False] = False
    external_writes: Literal[False] = False


class LeasedMemoryOutbox(MemoryAtomicUnit):
    """Owns its fixture UoW; inherited unfenced write entrypoints are closed."""
    def __init__(self, plan, clock: FakeLeaseClock):
        if type(clock) is not FakeLeaseClock:
            raise TypeError('Explicit fake clock required')
        super().__init__(plan)
        self._clock = clock
        self._state.update(leases={}, attempts=set(), worker_audit=[])

    def _audit(self, state, request, op, phase):
        super()._audit(state, request, op, phase)
        state['audit'][-1] = (*state['audit'][-1][:-1], self._clock.now())

    @contextmanager
    def _transaction(self, fail_at=None):
        with self._lock:
            original = self._state
            self._state = deepcopy(original)
            try:
                yield
                self._publish(self._state, fail_at)
            except BaseException:
                self._state = original
                raise

    def _worker_scope(self, request, scope, context, permission):
        self._authorized(request, scope, permission)
        if context.tenant_id != request.plan.tenant_id or not context.can_deliver:
            raise PermissionError('WORKER_SCOPE_DENIED')

    def _record(self, lease, phase):
        self._state['worker_audit'].append((lease.tenant_id, lease.request_id, lease.event_id,
            lease.plan_hash, lease.worker_id, lease.attempt_id, lease.token,
            lease.operation_revision, phase, self._clock.now()))

    def _validated(self, request, scope, context, supplied, permission, *, allow_done=False):
        self._worker_scope(request, scope, context, permission)
        key, _, op = self._match(self._state, request)
        current = self._state['leases'].get(key)
        identity = ('tenant_id', 'request_id', 'plan_hash', 'event_id', 'worker_id', 'attempt_id', 'token', 'purpose')
        if (current is None or any(getattr(current, k) != getattr(supplied, k) for k in identity)
                or current.worker_id != context.worker_id or self._clock.now() >= current.expires_at
                or current.status not in (('ACTIVE', 'DONE') if allow_done else ('ACTIVE',))
                or current.operation_revision != op.revision):
            raise LeaseConflict('STALE_EXPIRED_OR_FOREIGN_LEASE')
        if current.status == 'ACTIVE' and current.purpose == 'DELIVER':
            head = super().next_event(request, scope, permission=permission)
            if head is None or head.event_id != current.event_id:
                raise LeaseConflict('LEASE_EVENT_ORDER_CONFLICT')
        return key, current, op

    def claim(self, request, scope, context: WorkerContext, claim: Claim, *, permission=False, fail_at=None):
        self._worker_scope(request, scope, context, permission)
        with self._transaction(fail_at):
            key, _, op = self._match(self._state, request)
            old = self._state['leases'].get(key)
            now = self._clock.now()
            if old and old.status == 'ACTIVE' and now < old.expires_at:
                if (old.worker_id == context.worker_id and old.attempt_id == claim.attempt_id
                        and (old.purpose == claim.purpose or old.purpose == 'RECONCILE' and op.state == 'RECONCILIATION')):
                    return self._validated(request, scope, context, old, permission)[1]
                raise LeaseConflict('LEASE_BUSY')
            if (key, claim.attempt_id) in self._state['attempts']:
                raise LeaseConflict('ATTEMPT_ID_REUSED')
            # A crashed worker may have changed an external target. Do not redeliver blindly.
            if old and old.status == 'ACTIVE' and old.dispatched and old.purpose == 'DELIVER':
                event = next(e for e in self._state['outbox'][key] if e.event_id == old.event_id)
                if event.step not in ('COMMIT_OWNER_CAS', 'COMPENSATED'):
                    op = super().settle(request, scope, old.event_id, 'UNKNOWN', old.operation_revision,
                                        permission=permission)
            purpose = claim.purpose
            if op.state == 'RECONCILIATION':
                purpose = 'RECONCILE'
                event = next(e for e in self._state['outbox'][key] if e.status == 'UNKNOWN')
            else:
                if purpose == 'RECONCILE':
                    raise LeaseConflict('RECONCILIATION_NOT_REQUIRED')
                event = super().next_event(request, scope, permission=permission)
                if event is None:
                    raise LeaseConflict('NO_PENDING_EVENT')
            lease = WorkerLease(tenant_id=request.plan.tenant_id, request_id=request.request_id,
                plan_hash=op.plan_hash, event_id=event.event_id, worker_id=context.worker_id,
                attempt_id=claim.attempt_id, token=old.token + 1 if old else 1,
                operation_revision=op.revision, expires_at=now + timedelta(seconds=claim.seconds), purpose=purpose)
            self._state['leases'][key] = lease
            self._state['attempts'].add((key, claim.attempt_id))
            self._record(lease, 'CLAIM_' + purpose)
            return lease

    def renew(self, request, scope, context, lease, *, seconds=30, permission=False):
        seconds = Claim(attempt_id=lease.attempt_id, seconds=seconds).seconds
        with self._transaction():
            key, current, _ = self._validated(request, scope, context, lease, permission)
            renewed = current.model_copy(update={'expires_at': max(current.expires_at,
                self._clock.now() + timedelta(seconds=seconds))})
            self._state['leases'][key] = renewed
            self._record(renewed, 'RENEW')
            return renewed

    def dispatch(self, request, scope, context, lease, *, permission=False):
        """Marks possible external dispatch; returns fixture metadata, never invokes a provider."""
        with self._transaction():
            key, current, _ = self._validated(request, scope, context, lease, permission)
            if current.purpose != 'DELIVER' or current.dispatched:
                raise LeaseConflict('DELIVERY_NOT_ALLOWED')
            current = current.model_copy(update={'dispatched': True})
            self._state['leases'][key] = current
            self._record(current, 'DISPATCH')
            return next(e for e in self._state['outbox'][key] if e.event_id == current.event_id)

    def ack(self, request, scope, context, lease, *, permission=False, fail_at=None):
        with self._transaction(fail_at):
            key, current, op = self._validated(request, scope, context, lease, permission, allow_done=True)
            if current.status == 'DONE':
                event = next(e for e in self._state['outbox'][key] if e.event_id == current.event_id)
                if event.status == 'ACKED' and event.result == 'APPLIED':
                    return op
                raise LeaseConflict('ACK_RESULT_CONFLICT')
            if current.purpose != 'DELIVER' or not current.dispatched:
                raise LeaseConflict('ACK_WITHOUT_DELIVERY')
            op = super().settle(request, scope, current.event_id, 'APPLIED', current.operation_revision,
                                permission=permission)
            current = current.model_copy(update={'status': 'DONE', 'operation_revision': op.revision})
            self._state['leases'][key] = current
            self._record(current, 'ACK')
            return op

    def retry(self, request, scope, context, lease, *, permission=False):
        with self._transaction():
            key, current, _ = self._validated(request, scope, context, lease, permission)
            if current.purpose != 'DELIVER' or current.dispatched:
                raise LeaseConflict('UNPROVEN_RETRY_FORBIDDEN')
            current = current.model_copy(update={'status': 'RELEASED'})
            self._state['leases'][key] = current
            self._record(current, 'RETRY_NOT_SENT')
            return current

    def nack(self, request, scope, context, lease, outcome='UNKNOWN', *, permission=False, fail_at=None):
        if outcome not in ('UNKNOWN', 'NOT_APPLIED'):
            raise ValueError('NACK requires explicit unknown or not-applied outcome')
        with self._transaction(fail_at):
            key, current, _ = self._validated(request, scope, context, lease, permission)
            if current.purpose != 'DELIVER':
                raise LeaseConflict('RECONCILIATION_IS_READ_ONLY')
            op = super().settle(request, scope, current.event_id, outcome, current.operation_revision,
                                permission=permission)
            current = current.model_copy(update={'status': 'DONE', 'operation_revision': op.revision})
            self._state['leases'][key] = current
            self._record(current, 'NACK_' + outcome)
            return op

    def compensate(self, request, scope, context, lease, evidence, *, permission=False, fail_at=None):
        with self._transaction(fail_at):
            key, current, _ = self._validated(request, scope, context, lease, permission)
            if current.purpose != 'RECONCILE' or not context.can_compensate:
                raise PermissionError('SEPARATE_COMPENSATION_PERMISSION_REQUIRED')
            op = super().compensate(request, scope, evidence, permission=permission, compensation_permission=True)
            current = current.model_copy(update={'status': 'DONE', 'operation_revision': op.revision})
            self._state['leases'][key] = current
            self._record(current, 'COMPENSATED')
            return op

    def settle(self, *args, **kwargs):
        raise LeaseConflict('USE_FENCED_ACK_OR_NACK')

    def next_event(self, *args, **kwargs):
        raise LeaseConflict('USE_WORKER_CLAIM')
