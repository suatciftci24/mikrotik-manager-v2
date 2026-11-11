"""Fixture-only CONTINUE/CANCEL plans. Neither path dispatches or reverses provider effects."""
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicConflict, OutboxFixture, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox
from app.simulation.aaa_provider import FakeFencedProvider, ProviderEvidence


class FollowupConflict(AtomicConflict):
    pass


class CheckpointPlan(ReadContract):
    tenant_id: str
    store: str
    subscriber_id: str
    request_id: UUID
    previous_plan_hash: str
    decision_id: UUID
    evidence_fingerprint: str
    provider_evidence_fingerprint: str
    owner_revision: int
    operation_revision: int
    owner_fence: int
    worker_token: int
    expected_state: Literal['DECISION_RECORDED'] = 'DECISION_RECORDED'
    checkpoint_fingerprint: str
    automatic_dispatch: Literal[False] = False

    def plan_hash(self):
        return canonical_hash(self.model_dump(mode='json'))


class ContinuePlan(CheckpointPlan):
    contract_version: Literal['AAA_CONTINUE_PLAN_V1_FIXTURE'] = 'AAA_CONTINUE_PLAN_V1_FIXTURE'
    kind: Literal['CONTINUE'] = 'CONTINUE'
    execution_policy: Literal['FRESH_PLAN_AND_SEPARATE_EXECUTION_AUTH_REQUIRED'] = 'FRESH_PLAN_AND_SEPARATE_EXECUTION_AUTH_REQUIRED'


class CancelPlan(CheckpointPlan):
    contract_version: Literal['AAA_CANCEL_PLAN_V1_FIXTURE'] = 'AAA_CANCEL_PLAN_V1_FIXTURE'
    kind: Literal['CANCEL'] = 'CANCEL'
    external_effects: Literal['NOT_REVERSED_BY_CANCEL'] = 'NOT_REVERSED_BY_CANCEL'


class FixtureFollowupAuthority(ReadContract):
    environment: Literal['AAA_FOLLOWUP_FIXTURE_ONLY'] = 'AAA_FOLLOWUP_FIXTURE_ONLY'
    tenant_id: str
    actor_id: str
    can_continue: bool = False
    can_cancel: bool = False


class FollowupIntent(ReadContract):
    authorization_id: UUID
    lifetime_seconds: int = Field(default=60, ge=1, le=300)


class FollowupAuthorization(ReadContract):
    version: Literal['AAA_FOLLOWUP_AUTH_V1_FIXTURE'] = 'AAA_FOLLOWUP_AUTH_V1_FIXTURE'
    authorization_id: UUID
    actor_id: str
    plan: ContinuePlan | CancelPlan
    issued_at: datetime
    expires_at: datetime


class FollowupRecord(ReadContract):
    authorization_id: UUID
    plan_hash: str
    previous_plan_hash: str
    decision_id: UUID
    kind: Literal['CONTINUE', 'CANCEL']
    state: Literal['CONTINUE_HELD', 'CANCELLED_HELD']
    previous_owner_revision: int
    owner_revision: int
    checkpoint_fingerprint: str
    external_effects_reversed: Literal[False] = False
    automatic_dispatch: Literal[False] = False
    external_writes: Literal[False] = False


class FixtureFollowupService:
    def __init__(self, unit, provider):
        if type(unit) is not LeasedMemoryOutbox or type(provider) is not FakeFencedProvider:
            raise TypeError('Explicit memory fixtures required')
        self._unit, self._provider = unit, provider
        with unit._lock:
            for key, empty in (('followup_authorizations', {}), ('followup_records', {}), ('followup_audit', [])):
                unit._state.setdefault(key, empty)

    def _privilege(self, request, scope, authority, plan):
        if (type(plan) not in (ContinuePlan, CancelPlan) or type(authority) is not FixtureFollowupAuthority
                or authority.environment != 'AAA_FOLLOWUP_FIXTURE_ONLY'
                or authority.tenant_id != request.plan.tenant_id or authority.actor_id != scope.actor_id
                or not (authority.can_continue if plan.kind == 'CONTINUE' else authority.can_cancel)):
            raise PermissionError('SEPARATE_CONTINUE_OR_CANCEL_PERMISSION_REQUIRED')

    def _checkpoint(self, request, scope, decision_id, permission):
        unit, provider = self._unit, self._provider
        unit._authorized(request, scope, permission)
        key, owner_key, op = unit._match(unit._state, request)
        record = unit._state.get('decision_records', {}).get(decision_id)
        grant = unit._state.get('decision_authorizations', {}).get(decision_id)
        owner, lease = unit._state['owners'][owner_key], unit._state['leases'][key]
        ref = request.plan.snapshot.reference
        if (record is None or grant is None or op.state != 'DECISION_RECORDED'
                or record.request_id != request.request_id or record.tenant_id != request.plan.tenant_id
                or record.subscriber_id != ref.account_id or record.plan_hash != request.plan.plan_hash()
                or record.evidence_fingerprint != grant.evidence_fingerprint or record.event_id != grant.event_id
                or record.decision != grant.decision or record.previous_owner_revision != grant.owner_revision
                or (grant.tenant_id, grant.store, grant.subscriber_id, grant.request_id, grant.plan_hash)
                   != (*owner_key, request.request_id, op.plan_hash)
                or owner.revision != record.owner_revision or owner.revision != op.owner_revision
                or owner.revision != grant.owner_revision + 1 or op.revision != record.operation_revision
                or op.revision != grant.operation_revision + 1 or owner.fence != op.fence
                or owner.fence != grant.owner_fence + 1 or owner.authority != request.plan.source
                or owner.active_request != request.request_id or lease.status != 'DONE'
                or lease.token != grant.worker_token + 1 or lease.operation_revision != op.revision
                or (lease.worker_id, lease.attempt_id, lease.event_id, lease.plan_hash)
                   != (grant.worker_id, grant.attempt_id, grant.event_id, op.plan_hash)
                or provider._account != owner_key):
            raise FollowupConflict('CHECKPOINT_CAS_DECISION_OR_FENCE_CONFLICT')
        events = unit._state['outbox'][key]
        head = next((e.sequence for e in events if e.event_id == record.event_id), None)
        if len(events) != len(request.plan.steps) or head is None:
            raise FollowupConflict('CHECKPOINT_OUTBOX_CONFLICT')
        for sequence, event in enumerate(events, 1):
            applied = record.decision == 'ACCEPT_APPLIED_EVIDENCE'
            expected = ('ACKED', 'APPLIED') if sequence < head or sequence == head and applied else (
                ('CANCELLED', 'NOT_APPLIED') if sequence == head else ('CANCELLED', None))
            if (event.event_id != uuid5(request.request_id, request.plan.tenant_id + ':' + op.plan_hash + ':' + str(sequence))
                    or event.sequence != sequence or event.step != request.plan.steps[sequence - 1]
                    or (event.tenant_id, event.request_id, event.plan_hash, event.correlation_id) !=
                       (request.plan.tenant_id, request.request_id, op.plan_hash, request.correlation_id)
                    or (event.status, event.result) != expected):
                raise FollowupConflict('CHECKPOINT_OUTBOX_CONFLICT')
        receipts = tuple(sorted((r for (tenant, req, _), r in provider._state['receipts'].items()
            if (tenant, req) == key), key=lambda r: r.command.sequence))
        proof = ProviderEvidence(tenant_id=request.plan.tenant_id, account_id=ref.account_id,
            plan_hash=op.plan_hash, complete=bool(receipts) and all(r.outcome != 'UNKNOWN' for r in receipts),
            receipts=receipts, current=provider._state['provider'])
        proof_hash = canonical_hash(proof.model_dump(mode='json'))
        if not proof.complete or proof_hash != record.provider_evidence_fingerprint:
            raise FollowupConflict('PROVIDER_EVIDENCE_CHANGED')
        audit = [r for r in unit._state['audit'] if r[:2] == key]
        if (not audit or audit[-1][2:7] != (request.correlation_id, request.actor_id, op.plan_hash, op.revision, 'DECISION_RECORDED')
                or sum(r[0] == decision_id and r[2] == 'CONSUMED' for r in unit._state['decision_audit']) != 1):
            raise FollowupConflict('DECISION_AUDIT_CONFLICT')
        digest = canonical_hash({'record': record.model_dump(mode='json'), 'owner': owner.model_dump(mode='json'),
            'operation': op.model_dump(mode='json'), 'lease': lease.model_dump(mode='json'),
            'outbox': [e.model_dump(mode='json') for e in events], 'provider_evidence': proof_hash})
        return dict(tenant_id=request.plan.tenant_id, store=ref.store, subscriber_id=ref.account_id,
            request_id=request.request_id, previous_plan_hash=op.plan_hash, decision_id=decision_id,
            evidence_fingerprint=record.evidence_fingerprint, provider_evidence_fingerprint=proof_hash,
            owner_revision=owner.revision, operation_revision=op.revision, owner_fence=owner.fence,
            worker_token=lease.token, checkpoint_fingerprint=digest)

    def plan(self, request, scope, decision_id, kind, *, permission=False):
        if kind not in ('CONTINUE', 'CANCEL'):
            raise ValueError('Unknown followup kind')
        with self._unit._lock, self._provider._lock:
            data = self._checkpoint(request, scope, decision_id, permission)
            return ContinuePlan(**data) if kind == 'CONTINUE' else CancelPlan(**data)

    def issue(self, request, scope, authority, plan, intent: FollowupIntent, *, permission=False):
        self._privilege(request, scope, authority, plan)
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction():
            if intent.authorization_id in unit._state['followup_authorizations']:
                raise FollowupConflict('AUTHORIZATION_ID_REUSED')
            if self.plan(request, scope, plan.decision_id, plan.kind, permission=permission) != plan:
                raise FollowupConflict('STALE_OR_MISMATCHED_PLAN')
            now = unit._clock.now()
            grant = FollowupAuthorization(authorization_id=intent.authorization_id, actor_id=authority.actor_id,
                plan=plan, issued_at=now, expires_at=now + timedelta(seconds=intent.lifetime_seconds))
            unit._state['followup_authorizations'][intent.authorization_id] = grant
            unit._state['followup_audit'].append((intent.authorization_id, plan.plan_hash(), authority.actor_id, 'ISSUED', now))
            return grant

    def commit(self, request, scope, authority, grant: FollowupAuthorization, *, permission=False, fail_at=None):
        self._privilege(request, scope, authority, grant.plan)
        unit = self._unit
        with unit._lock, self._provider._lock, unit._transaction(None if fail_at == 'AUTHORIZATION' else fail_at):
            if unit._state['followup_authorizations'].get(grant.authorization_id) != grant:
                raise FollowupConflict('UNKNOWN_OR_TAMPERED_AUTHORIZATION')
            if grant.authorization_id in unit._state['followup_records']:
                raise FollowupConflict('AUTHORIZATION_ALREADY_USED')
            now = unit._clock.now()
            if grant.actor_id != authority.actor_id or now < grant.issued_at or now >= grant.expires_at:
                raise FollowupConflict('AUTHORIZATION_EXPIRED_OR_FOREIGN')
            plan = grant.plan
            if self.plan(request, scope, plan.decision_id, plan.kind, permission=permission) != plan:
                raise FollowupConflict('STALE_CAS_FENCE_OR_EVIDENCE')
            key, owner_key, op = unit._match(unit._state, request)
            owner = unit._state['owners'][owner_key]
            owner = owner.model_copy(update={'revision': owner.revision + 1, 'fence': owner.fence + 1})
            state = 'CONTINUE_HELD' if plan.kind == 'CONTINUE' else 'CANCELLED_HELD'
            op = op.model_copy(update={'state': state, 'revision': op.revision + 1,
                                      'owner_revision': owner.revision, 'fence': owner.fence})
            unit._state['owners'][owner_key], unit._state['journal'][key] = owner, op
            trace = OutboxFixture(event_id=uuid5(grant.authorization_id, plan.plan_hash()),
                tenant_id=plan.tenant_id, request_id=request.request_id, correlation_id=request.correlation_id,
                plan_hash=plan.plan_hash(), at=now, sequence=len(unit._state['outbox'][key]) + 1,
                step='CONTINUE_EXECUTION_REVIEW' if plan.kind == 'CONTINUE' else 'CANCEL_NO_ROLLBACK_ASSUMED', status='HELD')
            unit._state['outbox'][key] += (trace,)
            lease = unit._state['leases'][key].model_copy(update={'token': plan.worker_token + 1,
                'operation_revision': op.revision, 'status': 'DONE'})
            unit._state['leases'][key] = lease
            record = FollowupRecord(authorization_id=grant.authorization_id, plan_hash=plan.plan_hash(),
                previous_plan_hash=plan.previous_plan_hash, decision_id=plan.decision_id,
                kind=plan.kind, state=state, previous_owner_revision=plan.owner_revision, owner_revision=owner.revision,
                checkpoint_fingerprint=held_checkpoint_hash(owner, op, lease, unit._state['outbox'][key]))
            unit._state['followup_records'][grant.authorization_id] = record
            unit._audit(unit._state, request, op, state)
            unit._record(lease, state)
            unit._state['followup_audit'].append((grant.authorization_id, plan.plan_hash(), authority.actor_id, 'CONSUMED', now))
            if fail_at == 'AUTHORIZATION':
                raise FollowupConflict('INJECTED_AUTHORIZATION_FAILURE')
            return record


def held_checkpoint_hash(owner, operation, lease, events):
    return canonical_hash({'owner': owner.model_dump(mode='json'), 'operation': operation.model_dump(mode='json'),
                           'lease': lease.model_dump(mode='json'), 'events': [e.model_dump(mode='json') for e in events]})
