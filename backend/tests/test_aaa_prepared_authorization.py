from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
from backend.tests import test_aaa_next_step_preparation as fixtures
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_execution import ExecutionIntent
from app.simulation.aaa_executor import AttemptIntent
from app.simulation.aaa_worker import Claim
from app.simulation.aaa_prepared_authorization import (PreparedExecutionService, PreparedExecutionPlan,
    PreparedExecutionAuthorization, PreparedExecutionRecord)


class PreparedAuthorizationTests(TestCase):
    def setup_fixture(self):
        helper=fixtures.NextStepPreparationTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f=helper.setup_fixture()
        self.prepared=helper.prepare(helper.issue())
        self.service=PreparedExecutionService(self.f.unit,self.f.provider)
        # Setup alone uses previous fake effects; the new authorization flow must never call them.
        for target in ('app.simulation.aaa_executor.FixtureExecutor.run',
                       'app.simulation.aaa_provider.FakeFencedProvider.execute'):
            self.enterContext(patch(target,side_effect=AssertionError('Provider execution forbidden')))
        return self.f

    def plan(self):
        f=self.f
        return self.service.plan(f.request,f.scope,self.prepared.authorization_id,'COMMIT_OWNER_CAS',permission=True)

    def issue(self, number=10000, seconds=60, plan=None):
        f=self.f
        return self.service.issue(f.request,f.scope,f.execution_authority,plan or self.plan(),
            ExecutionIntent(authorization_id=UUID(int=number),lifetime_seconds=seconds),permission=True)

    def consume(self, grant, **kwargs):
        f=self.f
        return self.service.consume(f.request,f.scope,f.execution_authority,grant,permission=True,**kwargs)

    def snapshot(self): return self.f.unit.snapshot(),self.f.provider.snapshot()

    def test_issue_and_consume_are_separate_metadata_only_and_preserve_history(self):
        f=self.setup_fixture()
        before=self.snapshot()
        plan=self.plan()
        self.assertEqual(before,self.snapshot())
        self.assertEqual(PreparedExecutionPlan.model_validate_json(plan.model_dump_json()),plan)
        grant=self.issue(plan=plan)
        self.assertEqual(PreparedExecutionAuthorization.model_validate_json(grant.model_dump_json()),grant)
        issued=self.snapshot()
        for table in ('owners','journal','audit','outbox','execution_records'):
            self.assertEqual(before[0][table],issued[0][table])
        record=self.consume(grant)
        self.assertEqual(record.state,'EXECUTION_AUTHORIZED_HELD')
        self.assertEqual(PreparedExecutionRecord.model_validate_json(record.model_dump_json()),record)
        self.assertFalse(record.provider_dispatch)
        state=f.unit.snapshot()
        for table in ('executor_accepted','executor_decision_records','executor_policy_records'):
            self.assertEqual(before[0][table],state[table])
        for identity,value in before[0]['execution_records'].items(): self.assertEqual(state['execution_records'][identity],value)
        self.assertEqual(before[0]['audit'],state['audit'][:-1])
        owner=next(iter(state['owners'].values()))
        self.assertEqual(owner.authority,'LOCAL')
        self.assertEqual(owner.active_request,f.request.request_id)
        self.assertEqual(owner.revision,plan.owner_revision+1)
        self.assertEqual(owner.fence,plan.owner_fence+1)
        key=next(iter(state['outbox']))
        self.assertEqual(state['outbox'][key][:-1],before[0]['outbox'][key])
        self.assertEqual(state['outbox'][key][-1].status,'HELD')
        self.assertEqual(f.provider.snapshot(),before[1])
        snapshot=self.snapshot()
        with self.assertRaises(PermissionError):
            f.executor.claim(f.request,f.scope,f.runner.model_copy(update={'can_execute':False}),grant.authorization_id,AttemptIntent(attempt_id=UUID(int=10099)),permission=True)
        with self.assertRaises(AtomicConflict):
            f.unit.claim(f.request,f.scope,f.worker,Claim(attempt_id=UUID(int=10099)),permission=True)
        self.assertEqual(snapshot,self.snapshot())

    def test_all_binding_fields_and_contract_mismatch_rejected(self):
        self.setup_fixture()
        plan=self.plan()
        for field,value in [('tenant_id','wrong'),('subscriber_id','wrong'),('previous_execution_id',UUID(int=1)),
                            ('previous_event_id',UUID(int=1)),('previous_attempt_id',UUID(int=1)),
                            ('next_step_id',UUID(int=1)),('preparation_fingerprint','0'*64),
                            ('unknown_receipt_fingerprint','0'*64),('evidence_fingerprint','0'*64),
                            ('owner_revision',1),('worker_token',1),('contract_version','wrong'),
                            ('allowed_step','ENABLE_RADIUS')]:
            before=self.snapshot()
            with self.assertRaises((AtomicConflict,PermissionError)): self.issue(plan=plan.model_copy(update={field:value}))
            self.assertEqual(before,self.snapshot())

    def test_drift_cas_fence_evidence_or_preparation_rejected(self):
        # Fresh setup per mutation; patches are scoped to this test instance, not execution paths.
        self.setup_fixture()
        original=self.snapshot()
        for table,field in [('owners','revision'),('owners','fence'),('journal','revision'),('leases','token'),('provider','highest'),('record','state')]:
            self.f.unit._state=deepcopy(original[0])
            self.f.provider._state=deepcopy(original[1])
            grant=self.issue()
            if table=='provider': self.f.provider._state['highest']=(999,999)
            elif table=='record':
                old=self.f.unit._state['execution_records'][self.prepared.authorization_id]
                self.f.unit._state['execution_records'][self.prepared.authorization_id]=old.model_copy(update={'state':'CANCELLED'})
            else:
                key,old=next(iter(self.f.unit._state[table].items()))
                self.f.unit._state[table][key]=old.model_copy(update={field:getattr(old,field)+1})
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.consume(grant)
            self.assertEqual(before,self.snapshot())

    def test_expiry_scope_permission_and_version_fail_closed(self):
        f=self.setup_fixture()
        grant=self.issue(seconds=2)
        for authority in (f.execution_authority.model_copy(update={'can_stage':False}),
                          f.execution_authority.model_copy(update={'tenant_id':'other'})):
            before=self.snapshot()
            with self.assertRaises(PermissionError): self.service.consume(f.request,f.scope,authority,grant,permission=True)
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(AtomicConflict): self.consume(grant.model_copy(update={'version':'wrong'}))
        f.clock.advance(2)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.consume(grant)
        self.assertEqual(before,self.snapshot())

    def test_five_atomic_failures_do_not_consume_authority(self):
        self.setup_fixture()
        grant=self.issue()
        before=self.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.assertRaises(AtomicConflict): self.consume(grant,fail_at=fault)
            self.assertEqual(before,self.snapshot())
        self.consume(grant)

    def test_concurrent_cas_duplicate_and_replayed_issue_fail_closed(self):
        self.setup_fixture()
        grants=[self.issue(number=10000),self.issue(number=10001)]
        with self.assertRaises(AtomicConflict): self.issue(number=10000)
        def compete(grant):
            try: self.consume(grant); return 'WIN'
            except AtomicConflict: return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete,grants)),['WIN','CONFLICT'])
        before=self.snapshot()
        for grant in grants:
            with self.assertRaises(AtomicConflict): self.consume(grant)
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(AtomicConflict): self.plan()

    def test_unknown_cancelled_missing_evidence_and_issue_permission_blocked(self):
        f=self.setup_fixture()
        original=self.snapshot()
        for kind in ('UNKNOWN','CANCELLED','MISSING_EVIDENCE','MISSING_PREPARATION','ISSUE_PERMISSION'):
            f.unit._state=deepcopy(original[0]); f.provider._state=deepcopy(original[1])
            if kind in ('UNKNOWN','CANCELLED'):
                key,op=next(iter(f.unit._state['journal'].items()))
                f.unit._state['journal'][key]=op.model_copy(update={'state':'FIXTURE_STEP_UNKNOWN' if kind=='UNKNOWN' else 'NEXT_STEP_CANCELLED_HELD'})
            elif kind=='MISSING_EVIDENCE':
                del f.provider._state['executor_receipts'][self.policy_execution_id()]
            elif kind=='MISSING_PREPARATION':
                del f.unit._state['execution_records'][self.prepared.authorization_id]
            before=self.snapshot()
            if kind=='ISSUE_PERMISSION':
                plan=self.plan()
                with self.assertRaises(PermissionError):
                    self.service.issue(f.request,f.scope,f.execution_authority.model_copy(update={'can_issue':False}),plan,
                        ExecutionIntent(authorization_id=UUID(int=10000)),permission=True)
            else:
                with self.assertRaises(AtomicConflict): self.plan()
            self.assertEqual(before,self.snapshot())

    def policy_execution_id(self):
        grant=self.f.unit._state['execution_authorizations'][self.prepared.authorization_id]
        return grant.plan.previous_execution_id
