"""Deterministic memory-only AAA transition traces; no account store or provider IO."""
from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, field_validator
from app.integrations.aaa_contracts import (
    ReadContract, AaaSnapshot, PreviewScope, PreviewProof, AccountReference,
    AaaIdentity, NasReference, ProfileReference, SubscriptionTerms,
    require_preview_scope, inspect_aaa_snapshot, snapshot_fingerprint,
    validate_preview_proof, compare_preview_proofs, collision_key,
)


class SimulationRequest(ReadContract):
    fixture: Literal['AAA_MEMORY_FIXTURE_V1'] = 'AAA_MEMORY_FIXTURE_V1'
    snapshot: AaaSnapshot
    scope: PreviewScope
    proof: PreviewProof
    clock: datetime
    peers: tuple[AaaSnapshot, ...] = ()
    namespace_complete: bool = False
    fail_at: Literal['NONE', 'AFTER_TARGET_STAGED', 'AFTER_SOURCE_SWITCH'] = 'NONE'
    compensation: Literal['SUCCEEDS', 'BLOCKED'] = 'SUCCEEDS'

    @field_validator('clock')
    @classmethod
    def aware_clock(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Simulation clock must be timezone-aware')
        return value.astimezone(timezone.utc)


class PlannedChange(ReadContract):
    field: Literal['authority', 'revision']
    before: str | int
    after: str | int


class ExpectedAudit(ReadContract):
    origin: Literal['SIMULATED_EXPECTATION'] = 'SIMULATED_EXPECTATION'
    event_id: UUID
    request_id: UUID
    actor_id: str
    account_id: str | None
    phase: str
    occurred_at: datetime


class SimulationResult(ReadContract):
    mode: Literal['AAA_IN_MEMORY_SIMULATION'] = 'AAA_IN_MEMORY_SIMULATION'
    outcome: Literal['PASS', 'BLOCKED']
    label: Literal['Sentetik simülasyon başarılı', 'Sentetik simülasyon bloke']
    live_ready: Literal[False] = False
    external_writes: Literal[False] = False
    evidence: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    planned_changes: tuple[PlannedChange, ...] = ()
    simulated_final_authority: Literal['LOCAL', 'RADIUS', 'UNKNOWN'] | None = None
    simulated_final_revision: int | None = None
    expected_audit: tuple[ExpectedAudit, ...] = ()
    rollback_plan: tuple[str, ...] = ('REREAD_AUTHORIZED_METADATA', 'CONFIRM_SINGLE_AUTHORITY',
                                    'CAS_COMPENSATION_ONLY_IF_REVISION_MATCHES', 'AUDIT_CORRELATE')
    replayed: bool = False


class SimulationReceipt(ReadContract):
    """Caller-owned temporary simulation output, never a durable/live operation receipt."""
    proof: PreviewProof
    tenant_id: str | None
    request_signature: str = Field(pattern=r'^[0-9a-f]{64}$')
    result: SimulationResult


def request_signature(request: SimulationRequest):
    # Current subject revision may advance before a replay; the original proof is frozen.
    # Replay returns history even when the observed clock/current subject advances.
    # Fixture peers and failure controls remain frozen scenario request content.
    content = request.model_dump(mode='json', exclude={'snapshot', 'scope', 'clock'})
    content['tenant_id'] = request.scope.tenant_id
    import json
    return sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def simulate_transition(request: SimulationRequest, previous: SimulationReceipt | None = None):
    """Return (trace, temporary receipt); never mutate request, peers, proof or previous."""
    snapshot, scope, proof = request.snapshot, request.scope, request.proof
    signature = request_signature(request)

    def audit(phase, authorized=True):
        return ExpectedAudit(event_id=uuid5(proof.request_id, phase), request_id=proof.request_id,
                             actor_id=scope.actor_id, account_id=snapshot.reference.account_id if authorized else None,
                             phase=phase, occurred_at=request.clock)

    def finish(blockers=(), evidence=(), changes=(), authority=None, revision=None, events=()):
        result = SimulationResult(outcome='BLOCKED' if blockers else 'PASS',
                                  label='Sentetik simülasyon bloke' if blockers else 'Sentetik simülasyon başarılı',
                                  evidence=tuple(evidence), blockers=tuple(dict.fromkeys(blockers)),
                                  planned_changes=tuple(changes), simulated_final_authority=authority,
                                  simulated_final_revision=revision, expected_audit=tuple(events))
        receipt = SimulationReceipt(proof=proof, tenant_id=scope.tenant_id, request_signature=signature, result=result)
        return result, receipt

    try:
        require_preview_scope(snapshot, scope)
        for peer in request.peers:
            require_preview_scope(peer, scope)
    except PermissionError:
        return finish(('SCOPE_DENIED',), events=(audit('PRECHECK_DENIED', False),))
    if proof.actor_id != scope.actor_id or proof.store != snapshot.reference.store or proof.account_id != snapshot.reference.account_id:
        return finish(('PROOF_IDENTITY_MISMATCH',), events=(audit('PRECHECK_REJECTED'),))
    if previous and compare_preview_proofs(previous.proof, proof) != 'UNRELATED':
        if (compare_preview_proofs(previous.proof, proof) != 'MATCH'
                or previous.tenant_id != scope.tenant_id or previous.request_signature != signature):
            # Keep the first receipt; a rejected retry must not overwrite it.
            result, _ = finish(('IDEMPOTENCY_CONFLICT',), events=(audit('REPLAY_CONFLICT'),))
            return result, previous
        result = SimulationResult(**{**previous.result.model_dump(), 'replayed': True, 'expected_audit': ()})
        return result, previous
    try:
        validate_preview_proof(snapshot, scope, proof)
    except ValueError:
        return finish(('STALE_OR_MISMATCHED_PROOF',), events=(audit('PRECHECK_REJECTED'),))
    assessment = inspect_aaa_snapshot(snapshot, scope, request.peers)
    blockers = list(assessment['findings'])
    identity, nas, profile, terms = snapshot.identity, snapshot.nas, snapshot.profile, snapshot.terms
    if not request.namespace_complete:
        blockers.append('SYNTHETIC_NAMESPACE_INCOMPLETE')
    if any(collision_key(peer) is None for peer in request.peers):
        blockers.append('PEER_NAMESPACE_UNRESOLVED')
    if identity.realm is None:
        blockers.append('REALM_MISSING')
    if not all((nas.router_id, nas.nas_id, nas.nas_identifier, nas.mapping_revision)):
        blockers.append('NAS_FIXTURE_MAPPING_MISSING')
    if not all((profile.plan_id, profile.plan_name, profile.aaa_profile_id,
                profile.mapping_revision, profile.attribute_policy_version)):
        blockers.append('PROFILE_FIXTURE_MAPPING_MISSING')
    for peer in request.peers:
        other = peer.profile
        if (other.plan_id == profile.plan_id and peer.access_type == snapshot.access_type
                and other.mapping_revision == profile.mapping_revision
                and (other.aaa_profile_id, other.attribute_policy_version)
                    != (profile.aaa_profile_id, profile.attribute_policy_version)):
            blockers.append('PROFILE_MAPPING_CONFLICT')
    if terms.account_status not in ('ACTIVE', 'PAUSED'):
        blockers.append('ACCOUNT_STATUS_UNRESOLVED')
    if terms.expires_at_utc is not None and request.clock >= terms.expires_at_utc:
        blockers.append('SUBSCRIPTION_EXPIRED')
    if blockers:
        return finish(blockers, authority=snapshot.authority, revision=snapshot.reference.revision,
                      events=(audit('PRECHECK_BLOCKED'),))
    evidence = ('AUTHORIZED_SYNTHETIC_SCOPE', 'FROZEN_PROOF_MATCH', 'EXPLICIT_NAMESPACE_POLICY',
                'SYNTHETIC_NAMESPACE_COMPLETE', 'SYNTHETIC_NAS_PROFILE_FIXTURES',
                'LIVE_IDENTITY_NAS_PROFILE_AND_WRITE_AUTH_UNVERIFIED')
    changes = (PlannedChange(field='authority', before='LOCAL', after='RADIUS'),
               PlannedChange(field='revision', before=snapshot.reference.revision, after=snapshot.reference.revision + 1))
    events = [audit('PRECHECK_PASSED'), audit('TARGET_STAGED_MODELED')]
    switched = request.fail_at != 'AFTER_TARGET_STAGED'
    if switched:
        events.append(audit('SOURCE_SWITCH_MODELED'))
    if request.fail_at == 'NONE':
        events.append(audit('TRANSITION_SUCCESS_MODELED'))
        return finish(evidence=evidence, changes=changes, authority='RADIUS',
                      revision=snapshot.reference.revision + 1, events=events)
    events.append(audit('PARTIAL_FAILURE_MODELED'))
    if request.compensation == 'BLOCKED':
        events.append(audit('COMPENSATION_BLOCKED_MODELED'))
        return finish(('PARTIAL_FAILURE', 'COMPENSATION_REVISION_CONFLICT', 'READ_ONLY_RECONCILIATION_REQUIRED'),
                      evidence, changes, 'RADIUS' if switched else 'LOCAL',
                      snapshot.reference.revision + (1 if switched else 0), events)
    events.append(audit('COMPENSATION_SUCCESS_MODELED'))
    # Compensation never rewinds a modeled committed revision.
    return finish(('PARTIAL_FAILURE_COMPENSATED',), evidence, changes, 'LOCAL',
                  snapshot.reference.revision + (2 if switched else 0), events)


def synthetic_request(**changes):
    """Fixed .invalid fixture only; never reads an existing account or credential."""
    snapshot = AaaSnapshot(reference=AccountReference(store='LEGACY_DEMO', account_id='demo-sub-aaa-memory',
                           revision=3, tenant_id='aaa-memory-tenant', subscription_id=UUID(int=1)),
                           authority='LOCAL', access_type='PPPOE',
                           identity=AaaIdentity(username_raw='aaa.memory', username_canonical='aaa.memory',
                                                realm='aaa-memory.invalid', normalization='EXACT'),
                           nas=NasReference(router_id='demo-router-aaa-memory', nas_id=UUID(int=2),
                                            nas_identifier='AAA-MEMORY-NAS', mapping_revision=1),
                           profile=ProfileReference(plan_id=UUID(int=3), plan_name='AAA memory plan',
                                                    aaa_profile_id=UUID(int=4), mapping_revision=1,
                                                    attribute_policy_version='memory-v1'),
                           terms=SubscriptionTerms(expires_on=date(2026, 12, 23),
                                                   expiration_policy='END_OF_DAY_INCLUSIVE',
                                                   expires_at_utc=datetime(2026, 12, 23, 21, tzinfo=timezone.utc),
                                                   account_status='PAUSED'), uniqueness_policy='TENANT_REALM_EXACT')
    snapshot = changes.pop('snapshot', snapshot)
    scope = PreviewScope(actor_id='aaa-memory-actor', store='LEGACY_DEMO', tenant_id='aaa-memory-tenant',
                         readable_router_ids=('demo-router-aaa-memory',))
    proof = PreviewProof(request_id=UUID(int=100), actor_id=scope.actor_id, store=snapshot.reference.store,
                         account_id=snapshot.reference.account_id, expected_revision=snapshot.reference.revision,
                         snapshot_sha256=snapshot_fingerprint(snapshot))
    return SimulationRequest(**{**dict(snapshot=snapshot, scope=scope, proof=proof,
                                      clock=datetime(2026, 11, 11, 9, tzinfo=timezone.utc), namespace_complete=True), **changes})


def changed_snapshot(snapshot, **changes):
    return AaaSnapshot(**{**snapshot.model_dump(), **changes})


def changed_request(request, **changes):
    return SimulationRequest(**{**request.model_dump(), **changes})


def scenario_matrix():
    """Independent fixture cases; only replay cases explicitly share a temporary receipt."""
    base = synthetic_request()
    s = base.snapshot
    alter = lambda **changes: synthetic_request(snapshot=changed_snapshot(s, **changes))
    peer_ref = AccountReference(**{**s.reference.model_dump(), 'account_id': 'demo-sub-aaa-memory-peer'})
    duplicate = changed_snapshot(s, reference=peer_ref, authority='RADIUS')
    other_identity = AaaIdentity(username_raw='aaa.other', username_canonical='aaa.other',
                                 realm='aaa-memory.invalid', normalization='EXACT')
    conflicting_profile = ProfileReference(**{**s.profile.model_dump(), 'aaa_profile_id': UUID(int=40)})
    profile_peer = changed_snapshot(duplicate, identity=other_identity, profile=conflicting_profile)
    _, receipt = simulate_transition(base)
    changed = alter(profile=conflicting_profile)
    advanced = changed_request(base, snapshot=changed_snapshot(s, authority='RADIUS',
                               reference=AccountReference(**{**s.reference.model_dump(), 'revision': 4})))
    expired = SubscriptionTerms(expires_on=date(2026, 11, 10), expiration_policy='END_OF_DAY_INCLUSIVE',
                                expires_at_utc=datetime(2026, 11, 10, 21, tzinfo=timezone.utc), account_status='ACTIVE')
    return (
        ('complete_pppoe', base, None, 'PASS', None),
        ('complete_hotspot', alter(access_type='HOTSPOT'), None, 'PASS', None),
        ('missing_realm', alter(identity=AaaIdentity(username_raw='aaa.memory', username_canonical='aaa.memory',
                                normalization='EXACT')), None, 'BLOCKED', 'REALM_MISSING'),
        ('missing_nas', alter(nas=NasReference(router_id='demo-router-aaa-memory')), None, 'BLOCKED', 'NAS_FIXTURE_MAPPING_MISSING'),
        ('missing_profile', alter(profile=ProfileReference()), None, 'BLOCKED', 'PROFILE_FIXTURE_MAPPING_MISSING'),
        ('unknown_authority', alter(authority='UNKNOWN'), None, 'BLOCKED', 'NOT_A_LOCAL_TRANSITION_CANDIDATE'),
        ('unknown_access', alter(access_type='UNKNOWN'), None, 'BLOCKED', 'ACCESS_TYPE_UNKNOWN'),
        ('tenant_denied', changed_request(base, scope=PreviewScope(**{**base.scope.model_dump(),
                            'tenant_id': 'other-memory-tenant'})), None, 'BLOCKED', 'SCOPE_DENIED'),
        ('router_denied', changed_request(base, scope=PreviewScope(**{**base.scope.model_dump(),
                            'readable_router_ids': ()})), None, 'BLOCKED', 'SCOPE_DENIED'),
        ('duplicate_identity', changed_request(base, peers=(duplicate,)), None, 'BLOCKED', 'VISIBLE_NAMESPACE_CONFLICT_RISK'),
        ('profile_conflict', changed_request(base, peers=(profile_peer,)), None, 'BLOCKED', 'PROFILE_MAPPING_CONFLICT'),
        ('expired', alter(terms=expired), None, 'BLOCKED', 'SUBSCRIPTION_EXPIRED'),
        ('stale_revision', changed_request(base, proof=PreviewProof(**{**base.proof.model_dump(),
                            'expected_revision': 4})), None, 'BLOCKED', 'STALE_OR_MISMATCHED_PROOF'),
        ('same_uuid_replay', base, receipt, 'PASS', None),
        ('replay_after_revision_advance', advanced, receipt, 'PASS', None),
        ('same_uuid_changed_content', changed, receipt, 'BLOCKED', 'IDEMPOTENCY_CONFLICT'),
        ('incomplete_namespace', changed_request(base, namespace_complete=False), None, 'BLOCKED', 'SYNTHETIC_NAMESPACE_INCOMPLETE'),
        ('partial_before_switch', changed_request(base, fail_at='AFTER_TARGET_STAGED'), None, 'BLOCKED', 'PARTIAL_FAILURE_COMPENSATED'),
        ('partial_after_switch', changed_request(base, fail_at='AFTER_SOURCE_SWITCH'), None, 'BLOCKED', 'PARTIAL_FAILURE_COMPENSATED'),
        ('compensation_blocked', changed_request(base, fail_at='AFTER_SOURCE_SWITCH', compensation='BLOCKED'),
         None, 'BLOCKED', 'COMPENSATION_REVISION_CONFLICT'),
    )
