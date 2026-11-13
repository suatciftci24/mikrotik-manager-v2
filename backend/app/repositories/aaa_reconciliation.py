"""Durable fixture-only evaluation. Never dispatches, retries or commits ownership."""
from datetime import datetime, timedelta
import json
from typing import Literal
from uuid import UUID, uuid5
from pydantic import Field, model_serializer
from sqlalchemy import select, insert, update, func
from app.integrations.aaa_contracts import ReadContract
from app.repositories import aaa_metadata as db
from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge, BridgeConflict
from app.repositories.aaa_checkpoint_codec import decode
from app.simulation.aaa_atomic import canonical_hash


class RemoteObservation(ReadContract):
    source_identity: str | None = None
    source_revision: int | None = Field(default=None,ge=1)
    tenant_id: UUID
    operation_id: UUID
    execution_id: UUID
    subscriber_id: str
    router_id: str
    plan_hash: str
    dispatch_fingerprint: str
    owner_revision: int
    fence: int
    sequence: int = Field(ge=1)
    observed_at: datetime
    valid_until: datetime
    outcome: Literal['APPLIED','NOT_APPLIED','UNKNOWN']

    @model_serializer(mode='wrap')
    def compatible_projection(self, handler):
        data = handler(self)
        for name in ('source_identity','source_revision'):
            if data.get(name) is None: data.pop(name,None)
        return data


class ReconciliationReceipt(ReadContract):
    fixture_only: Literal[True] = True
    automatic_resume: Literal[False] = False
    evaluation_id: UUID
    execution_id: UUID
    operation_id: UUID
    tenant_id: UUID
    actor_id: str
    subscriber_id: str
    router_id: str
    fingerprint: str
    revision: int
    owner_revision: int
    fence: int
    status: Literal['CONFIRMED_APPLIED','CONFIRMED_NOT_APPLIED','UNKNOWN']
    observation: RemoteObservation | None
    last_observation: RemoteObservation | None
    occurred_at: datetime


class DurableFixtureReconciliation:
    """Reader and verifier must be trusted independent fixture dependencies.

    Verification is never a flag from a request body. Only sanitized typed
    observations are stored. Production evidence authentication is not supplied.
    """
    def __init__(self, bridge, reader, verifier):
        if type(bridge) is not PostgresFixtureBridge or not callable(reader) or not callable(verifier):
            raise TypeError('EXPLICIT_RECONCILIATION_DEPENDENCIES_REQUIRED')
        self.bridge,self.reader,self.verifier = bridge,reader,verifier
        self.observer = None

    @classmethod
    def with_observer(cls, bridge, observer, verifier, runtime_guard):
        from app.integrations.aaa_remote_observer import RemoteEvidenceVerifier
        from app.integrations.aaa_runtime_guard import RuntimePrincipalGuard
        if (not callable(getattr(observer,'observe',None)) or type(verifier) is not RemoteEvidenceVerifier
                or type(runtime_guard) is not RuntimePrincipalGuard):
            raise TypeError('EXPLICIT_OBSERVER_AND_PRINCIPAL_BOUNDARY_REQUIRED')
        result = cls(bridge,lambda _:None,lambda _:False)
        result.observer,result.evidence_verifier,result.runtime_guard = observer,verifier,runtime_guard
        return result

    def evaluate(self, request, scope, principal, *, execution_id, evaluation_id,
                 expected_revision, owner_revision, fence):
        if type(execution_id) is not UUID or type(evaluation_id) is not UUID:
            raise PermissionError('TYPED_RECONCILIATION_UUID_REQUIRED')
        if any(type(v) is not int or v < 0 for v in (expected_revision,owner_revision,fence)):
            raise PermissionError('EXPLICIT_RECONCILIATION_REVISIONS_REQUIRED')
        digest = canonical_hash([request.fingerprint(),str(execution_id),str(evaluation_id),
                                 expected_revision,owner_revision,fence])
        identity = str(uuid5(UUID(request.plan.tenant_id),'reconciliation:'+str(evaluation_id)))
        with self.bridge.sessions() as s, s.begin():
            if self.observer is not None:
                self.runtime_guard.check(s,request,scope,principal)
            owner_scope,_ = self.bridge._authorize(s,request,scope,principal,'AAA_DECISION')
            self.bridge._authorize(s,request,scope,principal,'AAA_SUBSCRIBER_READ')
            owner = s.execute(select(db.owner).where(db.owner.c.tenant_id==owner_scope.tenant_id,
                db.owner.c.id==owner_scope.subscriber_id).with_for_update()).mappings().one()
            operation = s.execute(select(db.operations).where(db.operations.c.tenant_id==owner_scope.tenant_id,
                db.operations.c.operation_id==request.request_id).with_for_update()).mappings().one()
            if (operation['fingerprint'] != request.fingerprint() or operation['actor_id'] != principal.actor_id
                    or operation['subscriber_id'] != owner_scope.subscriber_id
                    or operation['plan_hash'] != request.plan.plan_hash()
                    or owner['source'] != request.plan.source
                    or operation['state'] != 'FIXTURE_STEP_UNKNOWN'
                    or owner['aaa_active_operation'] != request.request_id):
                raise BridgeConflict('RECONCILIATION_OWNER_OPERATION_CHANGED')
            prior = s.execute(select(db.audit).where(db.audit.c.id==identity)).mappings().one_or_none()
            if prior:
                saved = ReconciliationReceipt.model_validate_json(json.dumps(prior['changes']))
                if (saved.fingerprint != digest or saved.actor_id != principal.actor_id
                        or saved.tenant_id != owner_scope.tenant_id or saved.operation_id != request.request_id
                        or saved.subscriber_id != owner_scope.subscriber_id or saved.execution_id != execution_id
                        or saved.evaluation_id != evaluation_id or saved.router_id != request.plan.snapshot.nas.router_id
                        or prior['operation'] != 'AAA_RECONCILIATION_EVALUATED'
                        or prior['tenant_id'] != saved.tenant_id or prior['actor_id'] != saved.actor_id
                        or prior['subscriber_id'] != saved.subscriber_id or prior['revision'] != saved.revision
                        or prior['occurred_at'] != saved.occurred_at.isoformat()):
                    raise BridgeConflict('RECONCILIATION_UUID_CONFLICT')
                return saved
            if (owner['revision'],owner['aaa_fence']) != (owner_revision,fence):
                raise BridgeConflict('RECONCILIATION_OWNER_CAS_CHANGED')
            attempt = s.execute(select(db.attempts).where(db.attempts.c.tenant_id==owner_scope.tenant_id,
                db.attempts.c.operation_id==request.request_id,db.attempts.c.execution_id==execution_id)).mappings().one()
            accepted = decode(attempt['receipt'])
            if (attempt['state'] != 'FIXTURE_STEP_UNKNOWN' or accepted.receipt.outcome != 'UNKNOWN'
                    or accepted.receipt.execution_id != execution_id
                    or accepted.receipt.tenant_id != str(owner_scope.tenant_id)
                    or accepted.receipt.request_id != request.request_id
                    or accepted.receipt.subscriber_id != owner_scope.subscriber_id
                    or accepted.receipt.attempt_id != attempt['attempt_id']
                    or accepted.receipt.event_id != attempt['event_id']):
                raise BridgeConflict('DURABLE_UNKNOWN_RECEIPT_REQUIRED')
            keys = (db.reconciliations.c.tenant_id==owner_scope.tenant_id,
                    db.reconciliations.c.execution_id==execution_id)
            row = s.execute(select(db.reconciliations).where(*keys).with_for_update()).mappings().one_or_none()
            if (row['revision'] if row else 0) != expected_revision:
                raise BridgeConflict('RECONCILIATION_REVISION_CHANGED')
            if row:
                latest = ReconciliationReceipt.model_validate_json(json.dumps(row['receipt']))
                audit_id = str(uuid5(owner_scope.tenant_id,'reconciliation:'+str(latest.evaluation_id)))
                audit = s.execute(select(db.audit.c.changes).where(db.audit.c.id==audit_id)).scalar_one()
                if (row['operation_id'] != request.request_id or latest.revision != row['revision']
                        or latest.execution_id != execution_id or latest.tenant_id != owner_scope.tenant_id
                        or (latest.last_observation.model_dump(mode='json') if latest.last_observation else None) != row['evidence']
                        or audit != row['receipt']):
                    raise BridgeConflict('RECONCILIATION_AUDIT_DRIFT')
            now = s.execute(select(func.clock_timestamp())).scalar_one()
            dispatch = accepted.receipt.model_dump(mode='json',exclude={
                'receipt_version','provider_evidence_fingerprint','outcome'})
            observation = None
            try:
                if self.observer is not None:
                    from app.integrations.aaa_remote_observer import ObservationChallenge
                    challenge = ObservationChallenge(evaluation_id=evaluation_id,execution_id=execution_id,
                        tenant_id=owner_scope.tenant_id,operation_id=request.request_id,
                        subscriber_id=owner_scope.subscriber_id,router_id=request.plan.snapshot.nas.router_id,
                        plan_hash=accepted.receipt.plan_hash,dispatch_fingerprint=canonical_hash(dispatch),
                        owner_revision=owner_revision,fence=fence,requested_at=now,deadline=now+timedelta(seconds=5))
                    envelope = self.observer.observe(challenge)
                    verified_at = s.execute(select(func.clock_timestamp())).scalar_one()
                    candidate = self.evidence_verifier.verify(envelope,challenge,verified_at)
                    now = verified_at
                else:
                    candidate = self.reader(execution_id)
                if type(candidate) is RemoteObservation:
                    candidate = RemoteObservation.model_validate_json(candidate.model_dump_json())
                    bound = (candidate.tenant_id==owner_scope.tenant_id and candidate.operation_id==request.request_id
                        and candidate.execution_id==execution_id and candidate.subscriber_id==owner_scope.subscriber_id
                        and candidate.router_id==request.plan.snapshot.nas.router_id
                        and candidate.plan_hash==accepted.receipt.plan_hash
                        and candidate.dispatch_fingerprint==canonical_hash(dispatch)
                        and (candidate.owner_revision,candidate.fence)==(owner_revision,fence))
                    if (bound and candidate.observed_at.utcoffset() is not None
                            and candidate.valid_until.utcoffset() is not None
                            and candidate.observed_at<=now<candidate.valid_until
                            and (self.observer is not None or self.verifier(candidate) is True)):
                        observation = candidate
            except Exception:
                pass  # Missing/unreachable/unverified remote evidence remains UNKNOWN.
            # Reader/verifier may have consumed the entire freshness window.
            now = s.execute(select(func.clock_timestamp())).scalar_one()
            if observation is not None and now >= observation.valid_until:
                observation = None
            if row and observation is not None:
                old = row['evidence']
                if old and (observation.sequence < old['sequence'] or
                        observation.observed_at < datetime.fromisoformat(old['observed_at']) or
                        observation.source_identity != old.get('source_identity') or
                        observation.source_revision != old.get('source_revision') or
                        observation.sequence == old['sequence'] and observation.model_dump(mode='json') != old):
                    if self.observer is not None:
                        observation = None
                    else:
                        raise BridgeConflict('REMOTE_OBSERVATION_REGRESSION_OR_CONFLICT')
            status = {'APPLIED':'CONFIRMED_APPLIED','NOT_APPLIED':'CONFIRMED_NOT_APPLIED','UNKNOWN':'UNKNOWN'}[
                observation.outcome if observation else 'UNKNOWN']
            receipt = ReconciliationReceipt(evaluation_id=evaluation_id,execution_id=execution_id,
                operation_id=request.request_id,tenant_id=owner_scope.tenant_id,actor_id=principal.actor_id,
                subscriber_id=owner_scope.subscriber_id,router_id=request.plan.snapshot.nas.router_id,
                fingerprint=digest,revision=expected_revision+1,owner_revision=owner_revision,fence=fence,
                status=status,observation=observation,occurred_at=now,
                last_observation=observation or (RemoteObservation.model_validate_json(json.dumps(row['evidence']))
                                                 if row and row['evidence'] else None))
            values = dict(operation_id=request.request_id,revision=receipt.revision,receipt=receipt.model_dump(mode='json'),
                          evidence=observation.model_dump(mode='json') if observation is not None else row['evidence'] if row else None)
            if row:
                if s.execute(update(db.reconciliations).where(*keys,db.reconciliations.c.revision==expected_revision)
                             .values(**values)).rowcount != 1:
                    raise BridgeConflict('RECONCILIATION_CAS_FAILED')
            else:
                s.execute(insert(db.reconciliations).values(tenant_id=owner_scope.tenant_id,execution_id=execution_id,**values))
            s.execute(insert(db.audit).values(id=identity,tenant_id=owner_scope.tenant_id,
                subscriber_id=owner_scope.subscriber_id,actor_id=principal.actor_id,revision=receipt.revision,
                occurred_at=now.isoformat(),operation='AAA_RECONCILIATION_EVALUATED',changes=receipt.model_dump(mode='json')))
        return receipt
