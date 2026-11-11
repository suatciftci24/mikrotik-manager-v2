"""One-use fixture decision authorization, independent from provider evidence assessment."""
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, assess_unknown

Decision = Literal['ACCEPT_APPLIED_EVIDENCE', 'ACCEPT_NOT_APPLIED_EVIDENCE']


class DecisionConflict(AtomicConflict):
    pass


class FixtureDecisionAuthority(ReadContract):
    environment: Literal['AAA_DECISION_FIXTURE_ONLY'] = 'AAA_DECISION_FIXTURE_ONLY'
    tenant_id: str
    actor_id: str
    can_issue: bool = False
    can_commit: bool = False


class DecisionIntent(ReadContract):
    authorization_id: UUID
    decision: Decision
    lifetime_seconds: int = Field(default=60, ge=1, le=300)


class ReconciliationAuthorization(ReadContract):
    version: Literal['AAA_RECONCILIATION_AUTH_V1_FIXTURE'] = 'AAA_RECONCILIATION_AUTH_V1_FIXTURE'
    authorization_id: UUID
    tenant_id: str
    store: str
    subscriber_id: str
    request_id: UUID
    actor_id: str
    plan_hash: str
    event_id: UUID
    owner_revision: int
    operation_revision: int
    owner_fence: int
    worker_token: int
    worker_id: str
    attempt_id: UUID
    evidence_fingerprint: str
    decision: Decision
    issued_at: datetime
    expires_at: datetime


class DecisionRecord(ReadContract):
    origin: Literal['AAA_ATOMIC_DECISION_FIXTURE_ONLY'] = 'AAA_ATOMIC_DECISION_FIXTURE_ONLY'
    authorization_id: UUID
    tenant_id: str
    subscriber_id: str
    request_id: UUID
    plan_hash: str
    event_id: UUID
    decision: Decision
    evidence_fingerprint: str
    provider_evidence_fingerprint: str
    previous_owner_revision: int
    owner_revision: int
    operation_revision: int
    automatic_dispatch: Literal[False] = False
    external_writes: Literal[False] = False
    live_ready: Literal[False] = False


class FixtureDecisionService:
    """No real grants, signature keys or endpoints; registry belongs to the same memory UoW."""
    def __init__(self, unit, provider):
        if type(unit) is not LeasedMemoryOutbox or type(provider) is not FakeFencedProvider:
            raise TypeError('Explicit in-memory fixtures required')
        self._unit, self._provider = unit, provider
        with unit._lock:
            for key, empty in (('decision_authorizations', {}), ('decision_records', {}), ('decision_audit', [])):
                unit._state.setdefault(key, empty)

    def _privilege(self, request, scope, authority, capability):
        if (type(authority) is not FixtureDecisionAuthority
                or authority.environment != 'AAA_DECISION_FIXTURE_ONLY'
                or authority.tenant_id != request.plan.tenant_id or authority.actor_id != scope.actor_id
                or not getattr(authority, capability)):
            raise PermissionError('SEPARATE_FIXTURE_DECISION_PERMISSION_REQUIRED')

    def _collect(self, request, scope, worker, lease, permission):
        unit, provider = self._unit, self._provider
        key, current, op = unit._validated(request, scope, worker, lease, permission)
        proof = provider.observe(unit, request, scope, worker, current, permission=permission)
        state = unit.snapshot()
        assessment = assess_unknown(request, current, state, proof)
        if assessment.status == 'READ_ONLY_RECONCILIATION_REQUIRED':
            raise DecisionConflict('EVIDENCE_NOT_CONFIRMED')
        ref = request.plan.snapshot.reference
        owner = state['owners'][(request.plan.tenant_id, ref.store, ref.account_id)]
        fingerprint = canonical_hash({'evidence': proof.model_dump(mode='json'),
            'journal': op.model_dump(mode='json'), 'owner': owner.model_dump(mode='json'),
            'outbox': [event.model_dump(mode='json') for event in state['outbox'][key]]})
        return key, current, op, owner, assessment, fingerprint

    def _decision_matches(self, decision, assessment):
        expected = 'PROVIDER_APPLIED_CONFIRMED' if decision == 'ACCEPT_APPLIED_EVIDENCE' else 'PROVIDER_NOT_APPLIED_CONFIRMED'
        if assessment.status != expected:
            raise DecisionConflict('DECISION_EVIDENCE_CONFLICT')

    def issue(self, request, scope, worker, lease, authority: FixtureDecisionAuthority,
              intent: DecisionIntent, *, permission=False):
        self._privilege(request, scope, authority, 'can_issue')
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction():
            if intent.authorization_id in unit._state['decision_authorizations']:
                raise DecisionConflict('AUTHORIZATION_ID_ALREADY_ISSUED')
            _, current, op, owner, assessment, digest = self._collect(request, scope, worker, lease, permission)
            self._decision_matches(intent.decision, assessment)
            ref = request.plan.snapshot.reference
            now = unit._clock.now()
            authorization = ReconciliationAuthorization(authorization_id=intent.authorization_id,
                tenant_id=request.plan.tenant_id, store=ref.store, subscriber_id=ref.account_id,
                request_id=request.request_id, actor_id=authority.actor_id, plan_hash=op.plan_hash,
                event_id=current.event_id, owner_revision=owner.revision, operation_revision=op.revision,
                owner_fence=owner.fence, worker_token=current.token, worker_id=current.worker_id,
                attempt_id=current.attempt_id, evidence_fingerprint=digest, decision=intent.decision,
                issued_at=now, expires_at=min(now + timedelta(seconds=intent.lifetime_seconds), current.expires_at))
            unit._state['decision_authorizations'][intent.authorization_id] = authorization
            unit._state['decision_audit'].append((intent.authorization_id, authority.actor_id, 'ISSUED', now, digest))
            return authorization

    def commit(self, request, scope, worker, lease, authority: FixtureDecisionAuthority,
               authorization: ReconciliationAuthorization, *, permission=False, fail_at=None):
        self._privilege(request, scope, authority, 'can_commit')
        unit = self._unit
        fault = None if fail_at == 'AUTHORIZATION' else fail_at
        with unit._lock, self._provider._lock, unit._transaction(fault):
            stored = unit._state['decision_authorizations'].get(authorization.authorization_id)
            if stored is None or stored != authorization:
                raise DecisionConflict('UNKNOWN_OR_TAMPERED_AUTHORIZATION')
            if stored.authorization_id in unit._state['decision_records']:
                raise DecisionConflict('AUTHORIZATION_ALREADY_USED')
            now = unit._clock.now()
            if now < stored.issued_at or now >= stored.expires_at:
                raise DecisionConflict('AUTHORIZATION_EXPIRED')
            ref = request.plan.snapshot.reference
            if (stored.tenant_id != request.plan.tenant_id or stored.store != ref.store
                    or stored.subscriber_id != ref.account_id or stored.request_id != request.request_id
                    or stored.plan_hash != request.plan.plan_hash() or stored.actor_id != authority.actor_id):
                raise DecisionConflict('AUTHORIZATION_SCOPE_MISMATCH')
            key, current, op, owner, assessment, digest = self._collect(request, scope, worker, lease, permission)
            if (current.event_id != stored.event_id or owner.revision != stored.owner_revision
                    or op.revision != stored.operation_revision or owner.fence != stored.owner_fence
                    or current.token != stored.worker_token or current.attempt_id != stored.attempt_id
                    or current.worker_id != stored.worker_id or digest != stored.evidence_fingerprint):
                raise DecisionConflict('CAS_FENCE_OR_EVIDENCE_CHANGED')
            self._decision_matches(stored.decision, assessment)
            provider_digest = canonical_hash(self._provider.observe(unit, request, scope, worker, current, permission=permission).model_dump(mode='json'))
            owner_key = (stored.tenant_id, stored.store, stored.subscriber_id)
            # Hold the reservation: confirming a provider step is not a completed source transition.
            owner = owner.model_copy(update={'revision': owner.revision + 1, 'fence': owner.fence + 1})
            op = op.model_copy(update={'state': 'DECISION_RECORDED', 'revision': op.revision + 1,
                                      'owner_revision': owner.revision, 'fence': owner.fence})
            events = []
            for event in unit._state['outbox'][key]:
                if event.event_id == stored.event_id:
                    applied = stored.decision == 'ACCEPT_APPLIED_EVIDENCE'
                    event = event.model_copy(update={'status': 'ACKED' if applied else 'CANCELLED',
                                                     'result': 'APPLIED' if applied else 'NOT_APPLIED'})
                elif event.status == 'PENDING':
                    event = event.model_copy(update={'status': 'CANCELLED'})
                events.append(event)
            unit._state['owners'][owner_key], unit._state['journal'][key] = owner, op
            unit._state['outbox'][key] = tuple(events)
            # Revoke the recovery worker in the same publication, not after the decision.
            revoked = current.model_copy(update={'status': 'DONE', 'token': current.token + 1,
                                                 'operation_revision': op.revision})
            unit._state['leases'][key] = revoked
            record = DecisionRecord(authorization_id=stored.authorization_id, tenant_id=stored.tenant_id,
                subscriber_id=stored.subscriber_id, request_id=stored.request_id, plan_hash=stored.plan_hash,
                event_id=stored.event_id, decision=stored.decision, evidence_fingerprint=digest,
                provider_evidence_fingerprint=provider_digest,
                previous_owner_revision=stored.owner_revision, owner_revision=owner.revision,
                operation_revision=op.revision)
            unit._state['decision_records'][stored.authorization_id] = record
            unit._audit(unit._state, request, op, 'DECISION_RECORDED')
            unit._record(revoked, 'DECISION_RECORDED')
            unit._state['decision_audit'].append((stored.authorization_id, authority.actor_id, 'CONSUMED', now, digest))
            if fail_at == 'AUTHORIZATION':
                raise DecisionConflict('INJECTED_AUTHORIZATION_FAILURE')
            return record
