"""Fake session contract tests, NOT PostgreSQL isolation/durability acceptance."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BooleanClauseList, Null
from app.repositories.aaa_metadata import *
from app.simulation.aaa_transition import synthetic_request
from app.simulation.aaa_atomic import AtomicPlan


class Result:
    def __init__(self, rows=(), count=0, scalar=None): self.rows,self.rowcount,self.scalar=rows,count,scalar
    def mappings(self): return self
    def one_or_none(self):
        if len(self.rows)>1: raise ValueError('duplicate fake row')
        return self.rows[0] if self.rows else None
    def scalar_one(self): return self.scalar


def matches(expr, row):
    if isinstance(expr,BooleanClauseList): return all(matches(c,row) for c in expr.clauses)
    left=row[expr.left.name]
    right=None if isinstance(expr.right,Null) else expr.right.value
    if expr.operator is operators.eq: return left==right
    if expr.operator is operators.is_: return left is right
    raise AssertionError('unsupported fake predicate')


class FakeDatabase:
    def __init__(self, clock):
        self.clock=clock;self.lock=RLock();self.state={t.name:[] for t in (owner,operations,actions,attempts,outbox,audit)}
        self.fail=None;self.commits=0;self.rollbacks=0
    def session(self): return FakeSession(self)


class FakeSession:
    def __init__(self, db): self.db=db
    def __enter__(self): return self
    def __exit__(self,*args): pass
    @contextmanager
    def begin(self):
        with self.db.lock:
            before=deepcopy(self.db.state)
            try: yield; self.db.commits+=1
            except BaseException:
                self.db.state=before;self.db.rollbacks+=1;raise
    def execute(self,stmt):
        if stmt.is_select:
            tables=stmt.get_final_froms()
            if not tables: return Result(scalar=self.db.clock)
            rows=self.db.state[tables[0].name]
            return Result([deepcopy(r) for r in rows if all(matches(c,r) for c in stmt._where_criteria)])
        name=stmt.table.name
        if self.db.fail==name: raise RuntimeError('injected fake write failure')
        rows=self.db.state[name]
        values={key:(value.value if hasattr(value,'value') else value) for key,value in stmt._values.items()}
        if stmt.is_insert:
            pks=[c.name for c in stmt.table.primary_key]
            if any(all(r[k]==values[k] for k in pks) for r in rows): raise ValueError('fake unique conflict')
            rows.append(deepcopy(values));return Result(count=1)
        selected=[r for r in rows if all(matches(c,r) for c in stmt._where_criteria)]
        for row in selected: row.update(deepcopy(values))
        return Result(count=len(selected))


class MetadataRepositoryTests(TestCase):
    def setUp(self):
        for target in ('socket.socket','sqlite3.connect','psycopg.connect'):
            self.enterContext(patch(target,side_effect=AssertionError('External IO forbidden')))
        f=synthetic_request();self.now=f.clock
        self.tenant=UUID(int=800)
        data=f.snapshot.model_dump(mode='json')
        data['reference'].update(store='PERSISTENT_WORKSPACE',tenant_id=str(self.tenant),account_id='demo-managed-sub-'+str(UUID(int=801)))
        data['nas']['router_id']='demo-managed-router-'+str(UUID(int=802))
        snapshot=type(f.snapshot).model_validate_json(__import__('json').dumps(data))
        plan=AtomicPlan(tenant_id=str(self.tenant),snapshot=snapshot,expected_account_revision=3,
            expected_source_revision=7,expected_target_revision=0,namespace_revision=2,authorization_policy_revision=1,preparation_sha256='a'*64)
        self.request=AtomicRequest(plan=plan,request_id=UUID(int=803),correlation_id=UUID(int=804),actor_id='fixture-actor',at=self.now)
        self.scope=Scope(tenant_id=self.tenant,subscriber_id=snapshot.reference.account_id,actor_id='fixture-actor')
        self.old=OwnerFixture(authority='LOCAL',revision=3,fence=5,active_request=self.request.request_id)
        self.new=self.old.model_copy(update={'revision':4,'fence':6})
        self.op=OperationFixture(plan_hash=plan.plan_hash(),fingerprint=self.request.fingerprint(),revision=1,
            state='FIXTURE_STEP_UNKNOWN',owner_revision=3,fence=5)
        self.next=self.op.model_copy(update={'revision':2,'owner_revision':4,'fence':6,'state':'NEXT_STEP_DECISION_RECORDED'})
        self.event=OutboxFixture(event_id=UUID(int=805),tenant_id=str(self.tenant),request_id=self.request.request_id,
            correlation_id=self.request.correlation_id,plan_hash=plan.plan_hash(),at=self.now,sequence=1,step='DECISION',status='HELD')
        self.db=FakeDatabase(self.now)
        self.db.state['subscribers'].append(dict(id=self.scope.subscriber_id,tenant_id=self.tenant,revision=3,source='LOCAL',aaa_fence=5,aaa_active_operation=self.request.request_id))
        self.payload={'version':'FIXTURE_TEST_ONLY','execution_id':str(UUID(int=806))}
        def authorize(session,scope): return scope==self.scope
        self.uow=PostgresMetadataUow(self.db.session,lambda s:True,authorize,lambda payload,scope,op:payload in (self.payload,{'outcome':'UNKNOWN'}))
        self.action=ActionMetadata(action_id=UUID(int=807),issued_at=self.now,expires_at=self.now+timedelta(seconds=60),payload=self.payload)
        with self.uow.transaction(self.scope) as repo:
            repo.reserve(self.request,self.op);repo.issue(self.request.request_id,self.action)

    def consume(self, attempt=None):
        with self.uow.transaction(self.scope) as repo:
            repo.consume(self.request.request_id,self.action.action_id,self.payload,self.old,self.new,1,self.next,self.event,UUID(int=808),attempt,lease_token=9)

    def test_atomic_commit_replay_and_consistency(self):
        self.consume()
        self.assertEqual(self.db.state['subscribers'][0]['revision'],4)
        self.assertEqual(self.db.state['operations'][0]['state'],'NEXT_STEP_DECISION_RECORDED')
        self.assertEqual(len(self.db.state['events']),1);self.assertEqual(len(self.db.state['outbox']),1)
        before=deepcopy(self.db.state)
        with self.assertRaises(MetadataConflict):self.consume()
        self.assertEqual(before,self.db.state)

    def test_atomic_failures_and_caught_exception_poison_uow(self):
        for table in ('subscribers','actions','operations','events','outbox'):
            before=deepcopy(self.db.state);self.db.fail=table
            with self.assertRaises(RuntimeError):self.consume()
            self.assertEqual(before,self.db.state)
        self.db.fail='events'
        before=deepcopy(self.db.state)
        with self.assertRaises(MetadataConflict):
            with self.uow.transaction(self.scope) as repo:
                try:repo.consume(self.request.request_id,self.action.action_id,self.payload,self.old,self.new,1,self.next,self.event,UUID(int=808),lease_token=9)
                except RuntimeError:pass
        self.assertEqual(before,self.db.state)

    def test_concurrent_cas_one_commit(self):
        def compete(_):
            try:self.consume();return 'WIN'
            except MetadataConflict:return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertCountEqual(list(pool.map(compete,range(2))),['WIN','CONFLICT'])
        self.assertEqual(len(self.db.state['events']),1)

    def test_expired_stale_fencing_wrong_tenant_actor(self):
        for scope in (self.scope.model_copy(update={'tenant_id':UUID(int=1)}),self.scope.model_copy(update={'actor_id':'foreign'})):
            with self.assertRaises(PermissionError):
                with self.uow.transaction(scope) as repo:repo.reserve(self.request,self.op)
        before=deepcopy(self.db.state);self.db.clock=self.action.expires_at
        with self.assertRaises(MetadataConflict):self.consume()
        self.assertEqual(before,self.db.state)
        self.db.clock=self.now;self.db.state['subscribers'][0]['aaa_fence']=99
        before=deepcopy(self.db.state)
        with self.assertRaises(MetadataConflict):self.consume()
        self.assertEqual(before,self.db.state)

    def test_idempotency_and_conflicting_payload(self):
        with self.uow.transaction(self.scope) as repo:
            _,replayed=repo.reserve(self.request,self.op);self.assertTrue(replayed)
        before=deepcopy(self.db.state)
        with self.assertRaises(MetadataConflict):
            with self.uow.transaction(self.scope) as repo:repo.reserve(self.request.model_copy(update={'correlation_id':UUID(int=1)}),self.op)
        self.assertEqual(before,self.db.state)

    def test_unknown_immutable_and_attempt_failure_rollback(self):
        attempt=AttemptMetadata(attempt_id=UUID(int=809),execution_id=UUID(int=806),event_id=self.event.event_id,state='UNKNOWN',receipt={'outcome':'UNKNOWN'})
        self.db.fail='attempts';before=deepcopy(self.db.state)
        with self.assertRaises(RuntimeError):self.consume(attempt)
        self.assertEqual(before,self.db.state)
        self.db.fail=None;self.consume(attempt)
        self.assertEqual(self.db.state['attempts'][0]['receipt'],{'outcome':'UNKNOWN'})
        before=deepcopy(self.db.state)
        with self.assertRaises(MetadataConflict):self.consume(attempt)
        self.assertEqual(before,self.db.state)

    def test_target_and_contract_gates_fail_closed(self):
        blocked=PostgresMetadataUow(self.db.session,lambda s:False,lambda s,c:True,lambda *a:True)
        with self.assertRaises(PermissionError):
            with blocked.transaction(self.scope):pass
        with self.assertRaises(MetadataConflict):
            with self.uow.transaction(self.scope) as repo:repo.issue(self.request.request_id,self.action.model_copy(update={'payload':{'password':'forbidden'}}))

    def test_repository_cannot_escape_uow_and_postgresql_sql_compiles_offline(self):
        from sqlalchemy.dialects.postgresql import dialect
        with self.uow.transaction(self.scope) as repo: repo.reserve(self.request,self.op)
        before=deepcopy(self.db.state)
        with self.assertRaisesRegex(MetadataConflict,'UNIT_OF_WORK_CLOSED'): repo.reserve(self.request,self.op)
        self.assertEqual(before,self.db.state)
        sql=str(select(owner).where(owner.c.tenant_id==self.tenant,owner.c.id==self.scope.subscriber_id).with_for_update().compile(dialect=dialect()))
        self.assertIn('FOR UPDATE',sql)
        self.assertIn('tenant_id',sql)
