"""DI-only durable adapter for the existing AAA fixture engine. No app wiring.

PostgreSQL owns owner/audit/outbox and typed authorization/receipt records.
The engine runs on a private rehydrated unit; SQL commit precedes any result.
Only the exact fake provider is allowed. Its evidence is NOT crash durable.
"""
import json
from uuid import UUID, uuid4, uuid5
from sqlalchemy import select, insert, update, func, text
from app.repositories import aaa_metadata as db
from app.repositories.aaa_checkpoint_codec import encode, decode
from app.repositories.aaa_membership import SessionMembershipResolver
from app.repositories.aaa_owner_contract import OwnerScope, locked_owner, owner_cas_predicates, require_metadata_transition
from app.simulation.aaa_atomic import OwnerFixture, OperationFixture, OutboxFixture, canonical_hash
from app.simulation.aaa_worker import LeasedMemoryOutbox, FakeLeaseClock
from app.simulation.aaa_provider import FakeFencedProvider
from app.simulation.aaa_executor import FixtureExecutor

AUTH = {'decision_authorizations': 'decision_records', 'followup_authorizations': 'followup_records',
        'execution_authorizations': 'execution_records', 'executor_decision_authorizations': 'executor_decision_records',
        'executor_policy_authorizations': 'executor_policy_records'}
EXTERNAL = {'owners', 'journal', 'outbox', 'audit', 'executor_accepted', *AUTH}
VERSION = 'AAA_PG_FIXTURE_CHECKPOINT_V1'


class BridgeConflict(ValueError):
    pass


class PostgresFixtureBridge:
    def __init__(self, sessions, resolver, provider):
        if not callable(sessions) or type(resolver) is not SessionMembershipResolver or type(provider) is not FakeFencedProvider:
            raise TypeError('EXPLICIT_PG_FIXTURE_DEPENDENCIES_REQUIRED')
        self.sessions, self.resolver, self.provider = sessions, resolver, provider

    def _scope(self, request, scope):
        if request.plan.snapshot.reference.store != 'PERSISTENT_WORKSPACE':
            raise PermissionError('PERSISTENT_WORKSPACE_REQUIRED')
        result = OwnerScope(tenant_id=UUID(request.plan.tenant_id), actor_id=request.actor_id,
                            subscriber_id=request.plan.snapshot.reference.account_id)
        if scope.tenant_id != str(result.tenant_id) or scope.actor_id != result.actor_id or scope.store != 'PERSISTENT_WORKSPACE':
            raise PermissionError('REQUEST_SCOPE_REQUIRED')
        return result

    def _authorize(self, session, request, scope, principal, capability):
        owner_scope = self._scope(request, scope)
        proof = self.resolver.resolve(session, principal, owner_scope, capability,
                                      router_id=request.plan.snapshot.nas.router_id)
        return owner_scope, proof

    def _load(self, session, request, scope, proof):
        tenant = UUID(request.plan.tenant_id)
        owner_row = session.execute(select(db.owner).where(db.owner.c.tenant_id == tenant,
            db.owner.c.id == request.plan.snapshot.reference.account_id).with_for_update()).mappings().one_or_none()
        op = session.execute(select(db.operations).where(db.operations.c.tenant_id == tenant,
            db.operations.c.operation_id == request.request_id).with_for_update()).mappings().one_or_none()
        if not owner_row or not op or op['fingerprint'] != request.fingerprint() or op['actor_id'] != request.actor_id:
            raise BridgeConflict('CHECKPOINT_SCOPE_REQUIRED')
        envelope = op['checkpoint']
        if envelope.get('version') != VERSION or envelope.get('provider_source') != id(self.provider):
            raise BridgeConflict('CHECKPOINT_VERSION_OR_PROVIDER_REJECTED')
        state = decode(envelope['engine'])
        key = (request.plan.tenant_id, request.request_id)
        owner_key = (request.plan.tenant_id, 'PERSISTENT_WORKSPACE', request.plan.snapshot.reference.account_id)
        state['owners'] = {owner_key: OwnerFixture(authority=owner_row['source'], revision=owner_row['revision'],
            fence=owner_row['aaa_fence'], active_request=owner_row['aaa_active_operation'])}
        state['journal'] = {key: OperationFixture.model_validate_json(json.dumps(envelope['journal']))}
        if (state['journal'][key].revision != op['revision'] or state['journal'][key].state != op['state']
                or state['journal'][key].plan_hash != op['plan_hash']
                or state['journal'][key].owner_revision != owner_row['revision']
                or state['journal'][key].fence != owner_row['aaa_fence']):
            raise BridgeConflict('OWNER_JOURNAL_DRIFT')
        events = session.execute(select(db.outbox).where(db.outbox.c.tenant_id == tenant,
            db.outbox.c.operation_id == request.request_id)).mappings().all()
        state['outbox'] = {key: tuple(sorted((OutboxFixture.model_validate_json(json.dumps(e['payload']))
                                             for e in events), key=lambda e: e.sequence))}
        rows = session.execute(select(db.audit).where(db.audit.c.tenant_id == tenant,
            db.audit.c.subscriber_id == owner_key[2])).mappings().all()
        rows = [r for r in rows if r['changes'].get('operation_id') == str(request.request_id)
                and '_aaa_engine' in r['changes']]
        state['audit'] = [decode(r['changes']['_aaa_engine']) for r in sorted(rows, key=lambda r: r['changes']['position'])]
        for name in AUTH:
            state[name] = {}
        for row in session.execute(select(db.actions).where(db.actions.c.tenant_id == tenant,
                db.actions.c.operation_id == request.request_id)).mappings():
            payload = row['payload']
            name, grant = payload['registry'], decode(payload['contract'])
            if (name not in AUTH or grant.authorization_id != row['action_id']
                    or canonical_hash(payload) != row['fingerprint'] or grant.actor_id != request.actor_id
                    or row['actor_id'] != request.actor_id or row['subscriber_id'] != owner_key[2]
                    or grant.issued_at != row['issued_at'] or grant.expires_at != row['expires_at']):
                raise BridgeConflict('AUTHORIZATION_STORAGE_BINDING_REQUIRED')
            state[name][row['action_id']] = grant
            if (row['consumed_at'] is not None) != (row['action_id'] in state[AUTH[name]]):
                raise BridgeConflict('AUTHORIZATION_CONSUMPTION_DRIFT')
            # A staged execution cannot outlive actor/membership/policy epochs.
            record = state.get('execution_records', {}).get(row['action_id'])
            if (name == 'execution_authorizations' and record is not None
                    and record.owner_revision == owner_row['revision']
                    and op['state'] == 'EXECUTION_AUTHORIZED_HELD'
                    and payload.get('freshness') != proof.model_dump(mode='json', exclude={'capability'})):
                raise PermissionError('EXECUTION_MEMBERSHIP_EPOCH_CHANGED')
        state['executor_accepted'] = {}
        for row in session.execute(select(db.attempts).where(db.attempts.c.tenant_id == tenant,
                db.attempts.c.operation_id == request.request_id)).mappings():
            receipt = decode(row['receipt'])
            if (receipt.receipt.execution_id != row['execution_id'] or receipt.receipt.attempt_id != row['attempt_id']
                    or receipt.receipt.event_id != row['event_id'] or receipt.state != row['state']):
                raise BridgeConflict('RECEIPT_STORAGE_BINDING_REQUIRED')
            state['executor_accepted'][row['execution_id']] = receipt
        clock = FakeLeaseClock(session.execute(select(func.clock_timestamp())).scalar_one())
        unit = LeasedMemoryOutbox(request.plan, clock)
        unit._state = state
        unit._authorized(request, scope, True)
        return unit, envelope['generation']

    def _write(self, session, request, unit, before, generation, proof):
        state = unit.snapshot()
        key, owner_key, op = unit._match(state, request)
        if set(state['owners']) != {owner_key} or set(state['journal']) != {key} or set(state['outbox']) != {key}:
            raise BridgeConflict('SINGLE_SCOPED_OPERATION_REQUIRED')
        tenant = UUID(request.plan.tenant_id)
        current = state['owners'][owner_key]
        envelope = {'version': VERSION, 'generation': generation + 1, 'provider_source': id(self.provider),
                    'engine': encode({k: v for k, v in state.items() if k not in EXTERNAL}),
                    'journal': op.model_dump(mode='json')}
        if current.revision != op.owner_revision or current.fence != op.fence:
            raise BridgeConflict('OWNER_JOURNAL_BINDING_REQUIRED')
        if before is None:
            session.execute(insert(db.owner).values(tenant_id=tenant, id=owner_key[2], source=current.authority,
                revision=current.revision, aaa_fence=current.fence, aaa_active_operation=current.active_request))
            session.execute(insert(db.operations).values(tenant_id=tenant, operation_id=request.request_id,
                subscriber_id=owner_key[2], actor_id=request.actor_id, fingerprint=request.fingerprint(),
                plan_hash=op.plan_hash, plan=request.plan.model_dump(mode='json'), revision=op.revision,
                state=op.state, checkpoint=envelope))
        else:
            previous = before['owners'][owner_key]
            if (current.revision not in (previous.revision, previous.revision + 1)
                    or current.fence not in (previous.fence, previous.fence + 1)
                    or current.active_request != previous.active_request and current.authority == previous.authority):
                raise BridgeConflict('MONOTONIC_OWNER_TRANSITION_REQUIRED')
            # Final source flip is possible only after the exact engine accepted
            # a SUCCESS receipt for the canonical COMMIT_OWNER_CAS step.
            if current.authority != previous.authority:
                accepted = [v for k, v in state['executor_accepted'].items() if k not in before['executor_accepted']]
                if (current.authority != 'RADIUS' or current.active_request is not None or len(accepted) != 1
                        or accepted[0].receipt.allowed_step != 'COMMIT_OWNER_CAS' or accepted[0].receipt.outcome != 'SUCCESS'):
                    raise BridgeConflict('PROVEN_FINAL_OWNER_COMMIT_REQUIRED')
            predicates = (db.owner.c.tenant_id == tenant, db.owner.c.id == owner_key[2],
                db.owner.c.revision == previous.revision, db.owner.c.aaa_fence == previous.fence,
                db.owner.c.source == previous.authority,
                db.owner.c.aaa_active_operation.is_(None) if previous.active_request is None else
                db.owner.c.aaa_active_operation == previous.active_request)
            if session.execute(update(db.owner).where(*predicates).values(source=current.authority,
                    revision=current.revision, aaa_fence=current.fence, aaa_active_operation=current.active_request)).rowcount != 1:
                raise BridgeConflict('OWNER_CAS_CONFLICT')
            changed = session.execute(update(db.operations).where(db.operations.c.tenant_id == tenant,
                db.operations.c.operation_id == request.request_id,
                db.operations.c.checkpoint['generation'].as_integer() == generation).values(
                    revision=op.revision, state=op.state, checkpoint=envelope)).rowcount
            if changed != 1:
                raise BridgeConflict('CHECKPOINT_GENERATION_CONFLICT')
        now = session.execute(select(func.clock_timestamp())).scalar_one()
        for name, records in AUTH.items():
            for identity, grant in state.get(name, {}).items():
                payload = {'registry': name, 'contract': encode(grant),
                           'freshness': proof.model_dump(mode='json', exclude={'capability'})}
                old = before.get(name, {}).get(identity) if before else None
                if old is None:
                    session.execute(insert(db.actions).values(tenant_id=tenant, action_id=identity,
                        operation_id=request.request_id, subscriber_id=owner_key[2], actor_id=request.actor_id,
                        payload=payload, fingerprint=canonical_hash(payload), issued_at=grant.issued_at,
                        expires_at=grant.expires_at, consumed_at=now if identity in state.get(records, {}) else None))
                elif grant != old:
                    raise BridgeConflict('IMMUTABLE_AUTHORIZATION_REQUIRED')
                elif identity in state.get(records, {}) and identity not in before.get(records, {}):
                    issued = session.execute(select(db.actions.c.payload).where(db.actions.c.tenant_id == tenant,
                        db.actions.c.action_id == identity)).scalar_one()
                    if issued.get('freshness') != payload['freshness']:
                        raise PermissionError('AUTHORIZATION_MEMBERSHIP_EPOCH_CHANGED')
                    if session.execute(update(db.actions).where(db.actions.c.tenant_id == tenant,
                        db.actions.c.action_id == identity, db.actions.c.consumed_at.is_(None)).values(consumed_at=now)).rowcount != 1:
                        raise BridgeConflict('AUTHORIZATION_ALREADY_USED')
        old_events = {e.event_id: e for e in before['outbox'][key]} if before else {}
        if not set(old_events).issubset({e.event_id for e in state['outbox'][key]}):
            raise BridgeConflict('OUTBOX_HISTORY_REQUIRED')
        for event in state['outbox'][key]:
            values = dict(status=event.status, payload=event.model_dump(mode='json'))
            if event.event_id in old_events:
                if event != old_events[event.event_id]:
                    session.execute(update(db.outbox).where(db.outbox.c.tenant_id == tenant,
                        db.outbox.c.event_id == event.event_id).values(**values))
            else:
                session.execute(insert(db.outbox).values(tenant_id=tenant, event_id=event.event_id,
                    operation_id=request.request_id, fencing_token=current.fence, **values))
        old_audit = before['audit'] if before else []
        if state['audit'][:len(old_audit)] != old_audit:
            raise BridgeConflict('APPEND_ONLY_AUDIT_REQUIRED')
        for position, row in enumerate(state['audit'][len(old_audit):], len(old_audit)):
            session.execute(insert(db.audit).values(id=str(uuid5(tenant, str(request.request_id) + ':' + str(position))),
                tenant_id=tenant, subscriber_id=owner_key[2], actor_id=request.actor_id, revision=row[5],
                occurred_at=row[-1].isoformat(), operation=row[6],
                changes={'operation_id': str(request.request_id), 'position': position, '_aaa_engine': encode(row)}))
        for identity, receipt in state.get('executor_accepted', {}).items():
            previous = before.get('executor_accepted', {}).get(identity) if before else None
            if previous is not None and previous != receipt:
                raise BridgeConflict('IMMUTABLE_RECEIPT_REQUIRED')
            if previous is None:
                session.execute(insert(db.attempts).values(tenant_id=tenant, attempt_id=receipt.receipt.attempt_id,
                    operation_id=request.request_id, execution_id=identity, event_id=receipt.receipt.event_id,
                    state=receipt.state, receipt=encode(receipt)))

    def seed_fixture(self, request, scope, principal, unit):
        """Explicit synthetic bootstrap only. Never called from application APIs."""
        if type(unit) is not LeasedMemoryOutbox:
            raise TypeError('EXPLICIT_FIXTURE_REQUIRED')
        with self.sessions() as session, session.begin():
            _, proof = self._authorize(session, request, scope, principal, 'AAA_SEED')
            unit._authorized(request, scope, True)
            self._write(session, request, unit, None, 0, proof)

    def invoke(self, request, scope, principal, capability, callback):
        with self.sessions() as session, session.begin():
            _, proof = self._authorize(session, request, scope, principal, capability)
            unit, generation = self._load(session, request, scope, proof)
            before = unit.snapshot()
            result = callback(unit)
            if unit.snapshot() != before:
                self._write(session, request, unit, before, generation, proof)
        return result

    def read(self, request, scope, principal, capability='AAA_READ'):
        with self.sessions() as session, session.begin():
            _, proof = self._authorize(session, request, scope, principal, capability)
            return self._load(session, request, scope, proof)

    def run(self, request, scope, principal, context, command, *, outcome='SUCCESS', crash=None, fail_response=False):
        unit, generation = self.read(request, scope, principal, 'AAA_EXECUTE')
        before = unit.snapshot()

        def save():
            nonlocal before, generation
            with self.sessions() as session, session.begin():
                _, proof = self._authorize(session, request, scope, principal, 'AAA_EXECUTE')
                fresh, current = self._load(session, request, scope, proof)
                if current != generation or fresh.snapshot() != before:
                    raise BridgeConflict('STALE_EXECUTION_CHECKPOINT')
                # Re-read DB wall time after locks. A detached unit's clock may
                # have aged while waiting; expiry must deny BEFORE fake effect.
                unit._clock = fresh._clock
                if unit._state['executor_status'][command.execution_id] == 'IN_FLIGHT':
                    FixtureExecutor(unit, self.provider)._command(request, command, context)
                self._write(session, request, unit, before, generation, proof)
            before, generation = unit.snapshot(), generation + 1

        receipt = FixtureExecutor(unit, self.provider, outcome=outcome).run(request, scope, context, command,
            permission=True, crash=crash, dispatch_checkpoint=save)
        if fail_response:
            raise BridgeConflict('INJECTED_POST_EFFECT_RESPONSE_LOSS')
        save()
        return receipt

    def daily_touch(self, request, scope, principal, expected):
        with self.sessions() as session, session.begin():
            owner_scope, _ = self._authorize(session, request, scope, principal, 'DAILY_OWNER')
            row = session.execute(select(db.owner).where(db.owner.c.tenant_id == owner_scope.tenant_id,
                db.owner.c.id == owner_scope.subscriber_id).with_for_update()).mappings().one_or_none()
            current = locked_owner(row, owner_scope, operation_id=None, writer='DAILY_OWNER', expected=expected)
            after = current.model_copy(update={'revision': current.revision + 1, 'fence': current.fence + 1})
            require_metadata_transition(current, after, operation_id=None, writer='DAILY_OWNER')
            if session.execute(update(db.owner).where(*owner_cas_predicates(db.owner, owner_scope, current,
                operation_id=None, writer='DAILY_OWNER')).values(revision=after.revision, aaa_fence=after.fence)).rowcount != 1:
                raise BridgeConflict('DAILY_OWNER_CAS_CONFLICT')
            session.execute(insert(db.audit).values(id=str(uuid4()), tenant_id=owner_scope.tenant_id,
                subscriber_id=owner_scope.subscriber_id, actor_id=owner_scope.actor_id, revision=after.revision,
                occurred_at=session.execute(select(func.clock_timestamp())).scalar_one().isoformat(),
                operation='AAA_FIXTURE_DAILY_TOUCH', changes={'fixture_only': True}))
        return after

    def subscriber_change(self, request, scope, principal, command):
        """Only a pure FakeFencedProvider projection, canonical owner and audit.

        No normal subscriber store, network, DDL or provider dispatch. The owner
        slot must already have been reserved in the isolated fixture namespace.
        """
        from app.simulation.aaa_integration_preparation import SyntheticAaaCommand, SyntheticAaaReceipt
        if type(command) is not SyntheticAaaCommand:
            raise PermissionError('TYPED_SYNTHETIC_COMMAND_REQUIRED')
        command = SyntheticAaaCommand.model_validate_json(command.model_dump_json())
        owner_scope = self._scope(request, scope)
        if (command.tenant_id != owner_scope.tenant_id or command.actor_id != owner_scope.actor_id
                or command.subscriber_id != owner_scope.subscriber_id
                or command.router_id != request.plan.snapshot.nas.router_id):
            raise PermissionError('SUBSCRIBER_COMMAND_SCOPE_REQUIRED')
        digest = command.fingerprint()
        with self.sessions() as session, session.begin():
            self._authorize(session, request, scope, principal, 'AAA_SUBSCRIBER_' + command.operation)
            # Serialize the exact fixture username across actors/subscriber IDs.
            # The lock is transaction scoped and never contacts a remote provider.
            namespace = canonical_hash([str(command.tenant_id), command.router_id, command.after.username])
            session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:namespace,0))'),
                            {'namespace':namespace})
            row = session.execute(select(db.owner).where(db.owner.c.tenant_id == owner_scope.tenant_id,
                db.owner.c.id == owner_scope.subscriber_id).with_for_update()).mappings().one_or_none()
            current = locked_owner(row, owner_scope, operation_id=None, writer='DAILY_OWNER')
            if current.authority != command.expected_source:
                raise PermissionError('SUBSCRIBER_SOURCE_CHANGED')
            prior = session.execute(select(db.audit).where(db.audit.c.id == str(command.request_id))).mappings().one_or_none()
            if prior:
                receipt = self._subscriber_receipt(prior)
                if (receipt.fingerprint != digest or receipt.tenant_id != owner_scope.tenant_id
                        or receipt.actor_id != owner_scope.actor_id or receipt.subscriber_id != owner_scope.subscriber_id):
                    raise BridgeConflict('SUBSCRIBER_REQUEST_ID_CONFLICT')
                return receipt
            if (current.revision, current.fence) != (command.expected_revision, command.expected_fence):
                raise BridgeConflict('SUBSCRIBER_OWNER_PREVIEW_CHANGED')
            history = session.execute(select(db.audit).where(db.audit.c.tenant_id == owner_scope.tenant_id,
                db.audit.c.subscriber_id == owner_scope.subscriber_id,
                db.audit.c.operation.in_(['AAA_SYNTHETIC_' + kind for kind in ('CREATE','EXTEND','PLAN','STATUS')]))
                .order_by(db.audit.c.revision.desc()).limit(1)).mappings().one_or_none()
            saved = self._subscriber_receipt(history) if history else None
            if saved and (saved.revision != current.revision or saved.fence != current.fence
                          or saved.source != current.authority or saved.router_id != command.router_id):
                raise BridgeConflict('SUBSCRIBER_AUDIT_OWNER_DRIFT')
            if command.operation == 'CREATE':
                duplicate = session.execute(select(db.audit.c.id).where(
                    db.audit.c.tenant_id == command.tenant_id, db.audit.c.subscriber_id != command.subscriber_id,
                    db.audit.c.operation == 'AAA_SYNTHETIC_CREATE',
                    db.audit.c.changes['_aaa_subscriber']['receipt']['router_id'].as_string() == command.router_id,
                    db.audit.c.changes['_aaa_subscriber']['receipt']['after']['username'].as_string() == command.after.username)
                    .limit(1)).first()
                if duplicate:
                    raise BridgeConflict('SYNTHETIC_USERNAME_ALREADY_OWNED')
            now = session.execute(select(func.clock_timestamp())).scalar_one()
            after = self.provider.project_subscriber(command, saved.after if saved else None, now)
            owner_after = current.model_copy(update={'revision':current.revision+1, 'fence':current.fence+1})
            require_metadata_transition(current, owner_after, operation_id=None, writer='DAILY_OWNER')
            if session.execute(update(db.owner).where(*owner_cas_predicates(db.owner, owner_scope, current,
                    operation_id=None, writer='DAILY_OWNER')).values(revision=owner_after.revision,
                    aaa_fence=owner_after.fence)).rowcount != 1:
                raise BridgeConflict('SUBSCRIBER_OWNER_CAS_CONFLICT')
            receipt = SyntheticAaaReceipt(request_id=command.request_id, tenant_id=command.tenant_id,
                actor_id=command.actor_id, subscriber_id=command.subscriber_id, router_id=command.router_id,
                source=command.expected_source, operation=command.operation, fingerprint=digest,
                before=command.before, after=after, revision=owner_after.revision, fence=owner_after.fence, occurred_at=now)
            session.execute(insert(db.audit).values(id=str(command.request_id), tenant_id=command.tenant_id,
                subscriber_id=command.subscriber_id, actor_id=command.actor_id, revision=receipt.revision,
                occurred_at=receipt.occurred_at.isoformat(), operation='AAA_SYNTHETIC_' + command.operation,
                changes={'_aaa_subscriber': {'command':command.model_dump(mode='json'),
                                           'receipt':receipt.model_dump(mode='json')}}))
        return receipt

    def subscriber_result(self, request, scope, principal, request_id):
        """Authenticated UUID recovery; absence is UNKNOWN, never a successful write."""
        if type(request_id) is not UUID:
            raise PermissionError('TYPED_SUBSCRIBER_REQUEST_ID_REQUIRED')
        with self.sessions() as session, session.begin():
            owner_scope, _ = self._authorize(session, request, scope, principal, 'AAA_SUBSCRIBER_READ')
            row = session.execute(select(db.owner).where(db.owner.c.tenant_id == owner_scope.tenant_id,
                db.owner.c.id == owner_scope.subscriber_id).with_for_update()).mappings().one_or_none()
            current = locked_owner(row, owner_scope, operation_id=None, writer='DAILY_OWNER')
            event = session.execute(select(db.audit).where(db.audit.c.id == str(request_id),
                db.audit.c.tenant_id == owner_scope.tenant_id,
                db.audit.c.subscriber_id == owner_scope.subscriber_id)).mappings().one_or_none()
            if event is None:
                return None
            receipt = self._subscriber_receipt(event)
            if receipt.actor_id != principal.actor_id or receipt.source != current.authority:
                raise PermissionError('SUBSCRIBER_RECEIPT_OWNER_CHANGED')
            return receipt

    @staticmethod
    def _subscriber_receipt(event):
        from app.simulation.aaa_integration_preparation import SyntheticAaaCommand, SyntheticAaaReceipt
        try:
            record = event['changes']['_aaa_subscriber']
            command = SyntheticAaaCommand.model_validate_json(json.dumps(record['command']))
            receipt = SyntheticAaaReceipt.model_validate_json(json.dumps(record['receipt']))
            if (str(receipt.request_id) != event['id'] or receipt.tenant_id != event['tenant_id']
                    or receipt.subscriber_id != event['subscriber_id'] or receipt.actor_id != event['actor_id']
                    or receipt.revision != event['revision'] or receipt.occurred_at.isoformat() != event['occurred_at']
                    or 'AAA_SYNTHETIC_' + receipt.operation != event['operation']
                    or receipt.fingerprint != command.fingerprint() or receipt.request_id != command.request_id
                    or receipt.before != command.before or receipt.after != command.after
                    or receipt.tenant_id != command.tenant_id or receipt.actor_id != command.actor_id
                    or receipt.router_id != command.router_id or receipt.subscriber_id != command.subscriber_id
                    or receipt.operation != command.operation or receipt.source != command.expected_source
                    or receipt.revision != command.expected_revision+1 or receipt.fence != command.expected_fence+1):
                raise ValueError()
            return receipt
        except (KeyError, TypeError, ValueError):
            raise BridgeConflict('SUBSCRIBER_AUDIT_RECEIPT_CONFLICT') from None
