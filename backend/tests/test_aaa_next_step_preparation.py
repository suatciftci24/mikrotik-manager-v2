"""Only new preparation behavior; existing test classes are fixture builders only."""
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from uuid import UUID
from backend.tests import test_aaa_next_step_policy as fixtures
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_execution import ExecutionIntent
from app.simulation.aaa_executor import AttemptIntent
from app.simulation.aaa_worker import Claim
from app.simulation.aaa_next_step_preparation import (NextStepPreparationService, NextStepPreparationPlan,
    NextStepPreparationAuthorization, NextStepPreparationRecord)


class NextStepPreparationTests(TestCase):
    def setup_fixture(self, kind='CONTINUE', outcome='SUCCESS', prefix=1):
        helper=fixtures.NextStepPolicyTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f=helper.prepare(outcome,prefix)
        self.policy=helper.apply(helper.issue(kind))
        self.service=NextStepPreparationService(self.f.unit,self.f.provider)
        self.history=self.f.unit.snapshot()
        return self.f

    def plan(self, step='COMMIT_OWNER_CAS'):
        f=self.f
        return self.service.plan(f.request,f.scope,self.policy.authorization_id,step,permission=True)

    def issue(self, number=9990, seconds=60, plan=None):
        f=self.f
        return self.service.issue(f.request,f.scope,f.execution_authority,plan or self.plan(),
            ExecutionIntent(authorization_id=UUID(int=number),lifetime_seconds=seconds),permission=True)

    def prepare(self, grant, **kwargs):
        f=self.f
        return self.service.prepare(f.request,f.scope,f.execution_authority,grant,permission=True,**kwargs)

    def snapshot(self): return self.f.unit.snapshot(),self.f.provider.snapshot()

    def test_preparation_roundtrip_preserves_history_and_cannot_execute(self):
        f=self.setup_fixture()
        provider=f.provider.snapshot()
        plan=self.plan()
        self.assertEqual(NextStepPreparationPlan.model_validate_json(plan.model_dump_json()),plan)
        self.assertFalse(plan.execution_authorized)
        self.assertEqual(plan.step_sequence,4)
        self.assertEqual(plan.previous_execution_id,self.policy.execution_id)
        grant=self.issue(plan=plan)
        self.assertEqual(NextStepPreparationAuthorization.model_validate_json(grant.model_dump_json()),grant)
        record=self.prepare(grant)
        self.assertEqual(NextStepPreparationRecord.model_validate_json(record.model_dump_json()),record)
        self.assertEqual(record.state,'NEXT_STEP_PREPARED_HELD')
        self.assertFalse(record.execution_authorized)
        self.assertFalse(record.provider_dispatch)
        state=f.unit.snapshot()
        key=next(iter(state['journal']))
        self.assertEqual(state['journal'][key].state,record.state)
        self.assertEqual(state['audit'][:-1],self.history['audit'])
        self.assertEqual(state['outbox'][key][:-1],self.history['outbox'][key])
        self.assertEqual(state['outbox'][key][-1].status,'HELD')
        for table in ('executor_accepted','executor_decision_records','executor_decision_authorizations',
                      'executor_policy_records','executor_policy_authorizations'):
            self.assertEqual(state[table],self.history[table])
        for key_,value in self.history['execution_records'].items():
            self.assertEqual(state['execution_records'][key_],value)
        owner=next(iter(state['owners'].values()))
        self.assertEqual(owner.authority,'LOCAL')
        self.assertEqual(owner.active_request,f.request.request_id)
        self.assertEqual(owner.revision,plan.owner_revision+1)
        self.assertEqual(owner.fence,plan.owner_fence+1)
        self.assertEqual(provider,f.provider.snapshot())
        before=self.snapshot()
        with self.assertRaises(AtomicConflict):
            f.executor.claim(f.request,f.scope,f.runner,grant.authorization_id,AttemptIntent(attempt_id=UUID(int=9999)),permission=True)
        with self.assertRaises(AtomicConflict):
            f.unit.claim(f.request,f.scope,f.worker,Claim(attempt_id=UUID(int=9999)),permission=True)
        self.assertEqual(before,self.snapshot())

    def test_cancel_rejection_wrong_step_or_exhausted_plan_blocked(self):
        for kind,outcome,prefix,step in [('CANCEL','SUCCESS',1,'COMMIT_OWNER_CAS'),
                                       ('CONTINUE','REJECTED',1,'COMMIT_OWNER_CAS'),
                                       ('CONTINUE','SUCCESS',2,'COMMIT_OWNER_CAS'),
                                       ('CONTINUE','SUCCESS',1,'ENABLE_RADIUS')]:
            self.setup_fixture(kind,outcome,prefix)
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.plan(step)
            self.assertEqual(before,self.snapshot())

    def test_scope_plan_binding_versions_and_missing_history_fail_closed(self):
        self.setup_fixture()
        plan=self.plan()
        for changes in ({'tenant_id':'wrong'},{'subscriber_id':'wrong'},{'previous_execution_id':UUID(int=4)},
                        {'previous_event_id':UUID(int=4)},{'previous_attempt_id':UUID(int=4)},
                        {'unknown_receipt_fingerprint':'0'*64},{'evidence_fingerprint':'0'*64},
                        {'next_step_id':UUID(int=4)},{'step_sequence':3},{'owner_revision':1},
                        {'worker_token':1},{'contract_version':'wrong'},{'reference_version':'wrong'}):
            before=self.snapshot()
            with self.assertRaises((AtomicConflict,PermissionError)): self.issue(plan=plan.model_copy(update=changes))
            self.assertEqual(before,self.snapshot())
        del self.f.unit._state['executor_decision_records'][self.policy.decision_id]
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.plan()
        self.assertEqual(before,self.snapshot())

    def test_expiry_permission_and_changed_authorization_rejected(self):
        f=self.setup_fixture()
        grant=self.issue(seconds=2)
        for authority in (f.execution_authority.model_copy(update={'can_stage':False}),
                          f.execution_authority.model_copy(update={'tenant_id':'wrong'})):
            before=self.snapshot()
            with self.assertRaises(PermissionError):
                self.service.prepare(f.request,f.scope,authority,grant,permission=True)
            self.assertEqual(before,self.snapshot())
        for changes in ({'version':'wrong'},{'authorization_id':UUID(int=1)}):
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.prepare(grant.model_copy(update=changes))
            self.assertEqual(before,self.snapshot())
        f.clock.advance(2)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.prepare(grant)
        self.assertEqual(before,self.snapshot())

    def test_drift_after_issue_rejected_without_consumption(self):
        for table,field in (('owners','revision'),('owners','fence'),('journal','revision'),('leases','token'),('PROVIDER','highest')):
            f=self.setup_fixture()
            grant=self.issue()
            if table=='PROVIDER': f.provider._state['highest']=(999,999)
            else:
                key,value=next(iter(f.unit._state[table].items()))
                f.unit._state[table][key]=value.model_copy(update={field:getattr(value,field)+1})
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.prepare(grant)
            self.assertEqual(before,self.snapshot())

    def test_five_fault_boundaries_restore_everything(self):
        self.setup_fixture()
        grant=self.issue()
        before=self.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.assertRaises(AtomicConflict): self.prepare(grant,fail_at=fault)
            self.assertEqual(before,self.snapshot())
        self.prepare(grant)

    def test_concurrent_prepare_duplicate_and_reused_uuid_have_single_winner(self):
        f=self.setup_fixture()
        grants=[self.issue(number=9990),self.issue(number=9991)]
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.issue(number=9990)
        self.assertEqual(before,self.snapshot())
        def compete(grant):
            try: self.prepare(grant); return 'WIN'
            except AtomicConflict: return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete,grants)),['WIN','CONFLICT'])
        before=self.snapshot()
        for grant in grants:
            with self.assertRaises(AtomicConflict): self.prepare(grant)
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(AtomicConflict): self.plan()
        self.assertEqual(sum(type(r) is NextStepPreparationRecord for r in f.unit._state['execution_records'].values()),1)

    def test_unknown_provider_unresolved_state_policy_version_and_issue_permission_blocked(self):
        for kind in ('UNKNOWN','UNRESOLVED','POLICY_VERSION','ISSUE_PERMISSION'):
            f=self.setup_fixture()
            if kind=='UNKNOWN':
                receipt=f.provider._state['executor_receipts'][self.policy.execution_id]
                f.provider._state['executor_receipts'][self.policy.execution_id]=receipt.model_copy(update={'outcome':'UNKNOWN'})
            elif kind=='UNRESOLVED':
                key,op=next(iter(f.unit._state['journal'].items()))
                f.unit._state['journal'][key]=op.model_copy(update={'state':'FIXTURE_STEP_UNKNOWN'})
            elif kind=='POLICY_VERSION':
                policy=f.unit._state['executor_policy_authorizations'][self.policy.authorization_id]
                f.unit._state['executor_policy_authorizations'][self.policy.authorization_id]=policy.model_copy(update={'version':'wrong'})
            before=self.snapshot()
            if kind=='ISSUE_PERMISSION':
                plan=self.plan()
                with self.assertRaises(PermissionError):
                    self.service.issue(f.request,f.scope,f.execution_authority.model_copy(update={'can_issue':False}),
                        plan,ExecutionIntent(authorization_id=UUID(int=9990)),permission=True)
            else:
                with self.assertRaises(AtomicConflict): self.plan()
            self.assertEqual(before,self.snapshot())
