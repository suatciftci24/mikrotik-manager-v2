"""Only the prepared UNKNOWN decision bridge, using existing memory fixtures."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from uuid import UUID
from backend.tests import test_aaa_prepared_evidence as fixtures
from app.simulation.aaa_executor_decision import ExecutorDecisionIntent, AuthorizedExecutorDecision
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_worker import Claim


class PreparedDecisionTests(TestCase):
    def setup_fixture(self, outcome='SUCCESS'):
        helper=fixtures.PreparedEvidenceTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        self.f=helper.setup_fixture(outcome)
        self.command,self.accepted=helper.command,helper.accepted
        self.evaluation=helper.evaluate()
        return self.f

    def issue(self, number=12000, seconds=60, evaluation=None, decision=None):
        f=self.f
        return f.service.issue(f.request,f.scope,f.context,evaluation or self.evaluation,
            ExecutorDecisionIntent(authorization_id=UUID(int=number),seconds=seconds,
                decision=decision or ('CONFIRM_SUCCESS' if self.evaluation.status=='CONFIRMED_SUCCESS' else 'CONFIRM_REJECTION')),permission=True)

    def apply(self, grant, **kwargs):
        f=self.f
        return f.service.apply(f.request,f.scope,f.context,grant,permission=True,**kwargs)

    def snapshot(self): return self.f.unit.snapshot(),self.f.provider.snapshot()

    def test_same_contract_issue_then_atomic_decision_without_success_or_dispatch(self):
        for outcome in ('SUCCESS','REJECTED'):
            f=self.setup_fixture(outcome)
            before=self.snapshot()
            grant=self.issue()
            self.assertEqual(AuthorizedExecutorDecision.model_validate_json(grant.model_dump_json()),grant)
            self.assertEqual(grant.evaluation.execution_plan_contract,'PREPARED_EXECUTION_PLAN_V1_FIXTURE')
            issued=self.snapshot()
            for table in ('owners','journal','audit','outbox','executor_accepted'):
                self.assertEqual(before[0][table],issued[0][table])
            record=self.apply(grant)
            self.assertEqual(record.state,'NEXT_STEP_DECISION_RECORDED')
            state=f.unit.snapshot()
            for table in ('executor_accepted','executor_policy_records','executor_policy_authorizations','execution_records','execution_authorizations'):
                self.assertEqual(state[table],before[0][table])
            for key,value in before[0]['executor_decision_records'].items(): self.assertEqual(state['executor_decision_records'][key],value)
            self.assertEqual(state['audit'][:-1],before[0]['audit'])
            self.assertEqual(state['executor_policy_audit'],before[0]['executor_policy_audit'])
            owner=next(iter(state['owners'].values()))
            self.assertEqual(owner.authority,'LOCAL')
            self.assertEqual(owner.active_request,f.request.request_id)
            self.assertEqual(owner.revision,self.evaluation.owner_revision+1)
            self.assertEqual(owner.fence,self.evaluation.owner_fence+1)
            events=next(iter(state['outbox'].values()))
            self.assertEqual(events[-1].status,'HELD')
            self.assertFalse(any(e.status=='PENDING' for e in events))
            self.assertEqual(f.provider.snapshot(),before[1])
            self.assertFalse(record.automatic_dispatch)
            self.assertEqual(state['executor_accepted'][self.command.execution_id],self.accepted)
            snapshot=self.snapshot()
            with self.assertRaises(AtomicConflict):
                f.unit.claim(f.request,f.scope,f.worker,Claim(attempt_id=UUID(int=12099)),permission=True)
            self.assertEqual(snapshot,self.snapshot())

    def test_evaluation_binding_and_wrong_decision_cannot_issue(self):
        self.setup_fixture()
        for field,value in [('tenant_id','wrong'),('subscriber_id','wrong'),('execution_id',UUID(int=1)),
                            ('event_id',UUID(int=1)),('attempt_id',UUID(int=1)),('plan_hash','0'*64),
                            ('receipt_fingerprint','0'*64),('evidence_fingerprint','0'*64),('owner_revision',1),
                            ('fencing_token',1),('version','wrong'),('execution_plan_contract',None)]:
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.issue(evaluation=self.evaluation.model_copy(update={field:value}))
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(AtomicConflict): self.issue(decision='CONFIRM_REJECTION')

    def test_missing_unknown_or_non_independent_evidence_rejected(self):
        f=self.setup_fixture()
        original=self.snapshot()
        for kind in ('MISSING','UNKNOWN','PROVENANCE','CHECKPOINT'):
            f.unit._state=deepcopy(original[0]);f.provider._state=deepcopy(original[1])
            if kind=='MISSING': del f.provider._state['executor_receipts'][self.command.execution_id]
            elif kind=='UNKNOWN': f.provider._state['executor_receipts'][self.command.execution_id]=self.accepted.receipt
            elif kind=='PROVENANCE': del f.provider._state['executor_evidence'][self.command.execution_id]
            else:
                key,op=next(iter(f.unit._state['journal'].items()))
                f.unit._state['journal'][key]=op.model_copy(update={'state':'EXECUTION_AUTHORIZED_HELD'})
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.issue()
            self.assertEqual(before,self.snapshot())

    def test_fresh_cas_fencing_and_provider_evidence_required_at_consumption(self):
        f=self.setup_fixture()
        grant=self.issue()
        original=self.snapshot()
        for table,field in [('owners','revision'),('owners','fence'),('journal','revision'),('leases','token'),('provider','highest'),('provider','executor_evidence')]:
            f.unit._state=deepcopy(original[0]);f.provider._state=deepcopy(original[1])
            if table=='provider':
                if field=='highest': f.provider._state['highest']=(999,999)
                else: del f.provider._state['executor_evidence'][self.command.execution_id]
            else:
                key,value=next(iter(f.unit._state[table].items()))
                f.unit._state[table][key]=value.model_copy(update={field:getattr(value,field)+1})
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.apply(grant)
            self.assertEqual(before,self.snapshot())

    def test_expired_wrong_scope_permission_and_grant_version_fail_closed(self):
        f=self.setup_fixture()
        grant=self.issue(seconds=2)
        for context in (f.context.model_copy(update={'can_apply_decision':False}),f.context.model_copy(update={'can_evaluate':False}),
                        f.context.model_copy(update={'tenant_id':'wrong'}),f.context.model_copy(update={'actor_id':'wrong'})):
            before=self.snapshot()
            with self.assertRaises(PermissionError): f.service.apply(f.request,f.scope,context,grant,permission=True)
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(AtomicConflict): self.apply(grant.model_copy(update={'version':'wrong'}))
        f.clock.advance(2)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.apply(grant)
        self.assertEqual(before,self.snapshot())

    def test_five_atomic_faults_preserve_grant_and_entire_history(self):
        self.setup_fixture()
        grant=self.issue()
        before=self.snapshot()
        for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
            with self.assertRaises(AtomicConflict): self.apply(grant,fail_at=fault)
            self.assertEqual(before,self.snapshot())
        self.apply(grant)

    def test_duplicate_reused_uuid_and_concurrent_grants_have_one_winner(self):
        f=self.setup_fixture()
        grants=[self.issue(number=12000),self.issue(number=12001)]
        with self.assertRaises(AtomicConflict): self.issue(number=12000)
        def compete(grant):
            try: self.apply(grant);return 'WIN'
            except AtomicConflict:return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete,grants)),['WIN','CONFLICT'])
        before=self.snapshot()
        for grant in grants:
            with self.assertRaises(AtomicConflict): self.apply(grant)
            self.assertEqual(before,self.snapshot())
        self.assertEqual(sum(r[0] in {g.authorization_id for g in grants} and r[2]=='CONSUMED'
                             for r in f.unit._state['executor_decision_audit']),1)
