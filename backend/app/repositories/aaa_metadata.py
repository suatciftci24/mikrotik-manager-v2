"""DI-only PostgreSQL metadata prototype. No engine, config, connection or DDL on import.

Tables describe a proposed schema, not the installed workspace schema. Application
wiring is blocked until owner writers, schema and target guards receive acceptance.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from sqlalchemy import MetaData, Table, Column, String, BigInteger, DateTime, JSON, select, insert, update, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from app.integrations.aaa_contracts import ReadContract
from app.simulation.aaa_atomic import AtomicRequest, OperationFixture, OwnerFixture, OutboxFixture, canonical_hash

from app.repositories.aaa_owner_contract import (OwnerScope, require_ownership, locked_owner, owner_cas_predicates, require_metadata_transition)

metadata = MetaData()
# Projection of existing owner/event tables, with UNAPPLIED proposed owner metadata.
owner = Table('subscribers', metadata, Column('id', String, primary_key=True),
    Column('tenant_id', PgUUID), Column('revision', BigInteger), Column('source', String),
    Column('aaa_fence', BigInteger), Column('aaa_active_operation', PgUUID), schema='v2_subscriber_workspace')
audit = Table('events', metadata, Column('id', String, primary_key=True), Column('tenant_id', PgUUID),
    Column('subscriber_id', String), Column('actor_id', String), Column('revision', BigInteger),
    Column('occurred_at', String), Column('operation', String), Column('changes', JSON), schema='v2_subscriber_workspace')
operations = Table('operations', metadata, Column('tenant_id', PgUUID, primary_key=True),
    Column('operation_id', PgUUID, primary_key=True), Column('subscriber_id', String), Column('actor_id', String),
    Column('fingerprint', String), Column('plan_hash', String), Column('plan', JSON),
    Column('revision', BigInteger), Column('state', String), Column('checkpoint', JSON), schema='v2_aaa')
actions = Table('actions', metadata, Column('tenant_id', PgUUID, primary_key=True), Column('action_id', PgUUID, primary_key=True),
    Column('operation_id', PgUUID), Column('subscriber_id', String), Column('actor_id', String),
    Column('fingerprint', String), Column('issued_at', DateTime(timezone=True)), Column('expires_at', DateTime(timezone=True)),
    Column('consumed_at', DateTime(timezone=True)), Column('payload', JSON), schema='v2_aaa')
attempts = Table('attempts', metadata, Column('tenant_id', PgUUID, primary_key=True), Column('attempt_id', PgUUID, primary_key=True),
    Column('operation_id', PgUUID), Column('execution_id', PgUUID), Column('event_id', PgUUID),
    Column('state', String), Column('receipt', JSON), Column('evidence', JSON), schema='v2_aaa')
outbox = Table('outbox', metadata, Column('tenant_id', PgUUID, primary_key=True), Column('event_id', PgUUID, primary_key=True),
    Column('operation_id', PgUUID), Column('status', String), Column('fencing_token', BigInteger),
    Column('lease_expires_at', DateTime(timezone=True)), Column('payload', JSON), schema='v2_aaa')


class MetadataConflict(ValueError):
    pass


Scope = OwnerScope


class ActionMetadata(ReadContract):
    action_id: UUID
    issued_at: datetime
    expires_at: datetime
    payload: dict  # Caller supplies a serialized strict versioned AAA contract, revalidated by gate.

    @field_validator('issued_at', 'expires_at')
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError('Aware time required')
        return value.astimezone(timezone.utc)


class AttemptMetadata(ReadContract):
    attempt_id: UUID
    execution_id: UUID
    event_id: UUID
    state: Literal['CLAIMED', 'IN_FLIGHT', 'RESPONDED', 'UNKNOWN', 'ACCEPTED']
    receipt: dict | None = None
    evidence: dict | None = None


class PostgresMetadataRepository:
    def __init__(self, session, scope, authorize, validate_contract):
        self.session, self.scope = session, scope
        self.authorize, self.validate_contract = authorize, validate_contract
        self.failed = False
        self.active = True

    def _check(self):
        if not self.active:
            raise MetadataConflict('UNIT_OF_WORK_CLOSED')
        if self.failed:
            raise MetadataConflict('TRANSACTION_POISONED')
        require_ownership(self.scope, self.authorize(self.session, self.scope))

    def _key(self, table, identity):
        return (table.c.tenant_id == self.scope.tenant_id, table.c[list(table.primary_key.columns)[1].name] == identity)

    def _execute(self, statement):
        try:
            return self.session.execute(statement)
        except BaseException:
            self.failed = True
            raise

    def reserve(self, request: AtomicRequest, checkpoint: OperationFixture):
        self._check()
        if (request.plan.tenant_id != str(self.scope.tenant_id) or request.actor_id != self.scope.actor_id
                or request.plan.snapshot.reference.store != 'PERSISTENT_WORKSPACE'
                or request.plan.snapshot.reference.account_id != self.scope.subscriber_id
                or checkpoint.fingerprint != request.fingerprint() or checkpoint.plan_hash != request.plan.plan_hash()):
            raise MetadataConflict('REQUEST_SCOPE_OR_PLAN_CONFLICT')
        # All callers lock owner first. Unique constraints remain required in eventual DDL.
        locked = self._execute(select(owner).where(owner.c.tenant_id == self.scope.tenant_id,
            owner.c.id == self.scope.subscriber_id).with_for_update()).mappings().one_or_none()
        locked_owner(locked, self.scope, operation_id=request.request_id)
        row = self._execute(select(operations).where(*self._key(operations, request.request_id)).with_for_update()).mappings().one_or_none()
        if row:
            if (row['fingerprint'], row['actor_id'], row['subscriber_id']) != (request.fingerprint(), self.scope.actor_id, self.scope.subscriber_id):
                raise MetadataConflict('IDEMPOTENCY_CONFLICT')
            return row, True
        if (locked['revision'] != request.plan.expected_account_revision
                or locked['aaa_active_operation'] != request.request_id
                or locked['aaa_fence'] != checkpoint.fence or checkpoint.owner_revision != locked['revision']):
            raise MetadataConflict('OWNER_RESERVATION_PREREQUISITE_REQUIRED')
        self._execute(insert(operations).values(tenant_id=self.scope.tenant_id, operation_id=request.request_id,
            subscriber_id=self.scope.subscriber_id, actor_id=self.scope.actor_id, fingerprint=request.fingerprint(),
            plan_hash=request.plan.plan_hash(), plan=request.plan.model_dump(mode='json'), revision=checkpoint.revision,
            state=checkpoint.state, checkpoint=checkpoint.model_dump(mode='json')))
        return checkpoint, False

    def issue(self, operation_id, action: ActionMetadata):
        self._check()
        action = ActionMetadata.model_validate_json(action.model_dump_json())
        if not 1 <= (action.expires_at-action.issued_at).total_seconds() <= 300:
            raise MetadataConflict('INVALID_AUTHORIZATION_TTL')
        if self.validate_contract(action.payload, self.scope, operation_id) is not True:
            raise MetadataConflict('VERSIONED_CONTRACT_REQUIRED')
        locked = self._execute(select(owner).where(owner.c.tenant_id == self.scope.tenant_id,
            owner.c.id == self.scope.subscriber_id).with_for_update()).mappings().one_or_none()
        locked_owner(locked, self.scope, operation_id=operation_id)
        op = self._execute(select(operations).where(*self._key(operations, operation_id)).with_for_update()).mappings().one_or_none()
        now = self._execute(select(func.clock_timestamp())).scalar_one()
        if (op is None or op['subscriber_id'] != self.scope.subscriber_id or op['actor_id'] != self.scope.actor_id
                or not action.issued_at <= now < action.expires_at):
            raise MetadataConflict('ACTION_OPERATION_SCOPE_OR_TIME_CONFLICT')
        self._execute(insert(actions).values(tenant_id=self.scope.tenant_id, action_id=action.action_id,
            operation_id=operation_id, subscriber_id=self.scope.subscriber_id, actor_id=self.scope.actor_id,
            fingerprint=canonical_hash(action.payload), issued_at=action.issued_at, expires_at=action.expires_at,
            consumed_at=None, payload=action.payload))

    def consume(self, operation_id, action_id, payload, expected_owner: OwnerFixture,
                new_owner: OwnerFixture, expected_revision: int, checkpoint: OperationFixture,
                event: OutboxFixture, audit_id: UUID, attempt: AttemptMetadata | None = None, *, lease_token: int):
        self._check()
        require_metadata_transition(expected_owner, new_owner, operation_id=operation_id)
        if (type(lease_token) is not int or lease_token < 1 or checkpoint.revision != expected_revision+1
                or checkpoint.owner_revision != new_owner.revision or checkpoint.fence != new_owner.fence
                or event.request_id != operation_id or event.tenant_id != str(self.scope.tenant_id)
                or checkpoint.plan_hash != event.plan_hash or event.status != 'HELD'
                or new_owner.authority != expected_owner.authority
                or new_owner.active_request != operation_id or expected_owner.active_request != operation_id):
            raise MetadataConflict('METADATA_CAS_OR_HELD_CONTRACT_REQUIRED')
        if self.validate_contract(payload, self.scope, operation_id) is not True:
            raise MetadataConflict('VERSIONED_CONTRACT_REQUIRED')
        try:
            row = self._execute(select(owner).where(owner.c.tenant_id == self.scope.tenant_id,
                owner.c.id == self.scope.subscriber_id).with_for_update()).mappings().one_or_none()
            locked_owner(row, self.scope, operation_id=operation_id, expected=expected_owner)
            op = self._execute(select(operations).where(*self._key(operations, operation_id)).with_for_update()).mappings().one_or_none()
            grant = self._execute(select(actions).where(*self._key(actions, action_id)).with_for_update()).mappings().one_or_none()
            # Clock must be read by the injected transaction AFTER locks, never a client clock.
            now = self.session.execute(select(func.clock_timestamp())).scalar_one()
            if (row is None or op is None or grant is None or op['subscriber_id'] != self.scope.subscriber_id
                    or op['actor_id'] != self.scope.actor_id or op['revision'] != expected_revision
                    or op['fingerprint'] != checkpoint.fingerprint or op['plan_hash'] != checkpoint.plan_hash or grant['operation_id'] != operation_id
                    or grant['subscriber_id'] != self.scope.subscriber_id or grant['actor_id'] != self.scope.actor_id
                    or grant['fingerprint'] != canonical_hash(payload) or grant['consumed_at'] is not None
                    or not grant['issued_at'] <= now < grant['expires_at']):
                raise MetadataConflict('AUTHORIZATION_CAS_SCOPE_OR_EXPIRY_CONFLICT')
            predicates = owner_cas_predicates(owner, self.scope, expected_owner, operation_id=operation_id)
            if self._execute(update(owner).where(*predicates).values(revision=new_owner.revision,
                aaa_fence=new_owner.fence)).rowcount != 1:
                raise MetadataConflict('OWNER_CAS_OR_FENCE_CONFLICT')
            if self._execute(update(actions).where(*self._key(actions, action_id), actions.c.consumed_at.is_(None))
                .values(consumed_at=now)).rowcount != 1:
                raise MetadataConflict('AUTHORIZATION_REPLAY')
            if self._execute(update(operations).where(*self._key(operations, operation_id), operations.c.revision == expected_revision)
                .values(revision=checkpoint.revision, state=checkpoint.state, checkpoint=checkpoint.model_dump(mode='json'))).rowcount != 1:
                raise MetadataConflict('JOURNAL_CAS_CONFLICT')
            self._execute(insert(outbox).values(tenant_id=self.scope.tenant_id,event_id=event.event_id,
                operation_id=operation_id,status='HELD',fencing_token=lease_token,payload=event.model_dump(mode='json')))
            self._execute(insert(audit).values(id=str(audit_id),tenant_id=self.scope.tenant_id,
                subscriber_id=self.scope.subscriber_id,actor_id=self.scope.actor_id,revision=new_owner.revision,
                occurred_at=now.isoformat(),operation='AAA',changes={'_aaa':{'action':str(action_id),
                    'operation':str(operation_id),'state':checkpoint.state,'payload_fingerprint':canonical_hash(payload)}}))
            if attempt:
                if (attempt.state != 'UNKNOWN' or attempt.receipt is None
                        or str(attempt.execution_id) != payload.get('execution_id')
                        or attempt.event_id != event.event_id
                        or self.validate_contract(attempt.receipt, self.scope, operation_id) is not True
                        or attempt.evidence is not None and self.validate_contract(attempt.evidence, self.scope, operation_id) is not True):
                    raise MetadataConflict('ONLY_UNKNOWN_CHECKPOINT_PERSISTENCE_SUPPORTED')
                self._execute(insert(attempts).values(tenant_id=self.scope.tenant_id,attempt_id=attempt.attempt_id,
                    operation_id=operation_id,execution_id=attempt.execution_id,event_id=attempt.event_id,
                    state='UNKNOWN',receipt=attempt.receipt,evidence=attempt.evidence))
        except BaseException:
            self.failed = True
            raise


class PostgresMetadataUow:
    def __init__(self, sessions, target_guard, authorize, validate_contract):
        # No default engine/session selection. All gates must be explicitly injected.
        if not all(callable(x) for x in (sessions,target_guard,authorize,validate_contract)):
            raise TypeError('Explicit injected factory and guards required')
        self.sessions,self.target_guard,self.authorize,self.validate_contract=sessions,target_guard,authorize,validate_contract

    @contextmanager
    def transaction(self, scope: Scope):
        with self.sessions() as session:
            with session.begin():
                if type(scope) is not Scope or self.target_guard(session) is not True:
                    raise PermissionError('VERIFIED_DISPOSABLE_TARGET_AND_OWNER_WRITERS_REQUIRED')
                repo=PostgresMetadataRepository(session,scope,self.authorize,self.validate_contract)
                try:
                    yield repo
                    if repo.failed:
                        raise MetadataConflict('TRANSACTION_POISONED')
                finally:
                    repo.active = False
