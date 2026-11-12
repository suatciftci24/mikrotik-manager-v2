"""New next-step CONTINUE/CANCEL behavior only; memory fixtures, no external IO."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from uuid import UUID
from backend.tests import test_aaa_next_step_decision as fixtures
from app.simulation.aaa_atomic import AtomicConflict
from app.simulation.aaa_worker import Claim
from app.simulation.aaa_executor_policy import ExecutorPolicyIntent, ExecutorPolicyAuthorization, ExecutorPolicyRecord


class NextStepPolicyTests(TestCase):
    def prepare(self, outcome='SUCCESS', prefix=1):
        helper = fixtures.NextStepDecisionTests(methodName='runTest')
        self.addCleanup(helper.doCleanups)
        f = helper.prepare(outcome, prefix)
        self.decision = helper.apply(helper.issue())
        self.f, self.command = f, helper.command
        self.history = f.unit.snapshot()
        return f

    def plan(self, kind='CONTINUE'):
        f = self.f
        return f.policy.plan(f.request, f.scope, self.decision.authorization_id, kind, permission=True)

    def issue(self, kind='CONTINUE', number=9950, seconds=60, plan=None):
        f = self.f
        return f.policy.issue(f.request, f.scope, f.authority, plan or self.plan(kind),
            ExecutorPolicyIntent(authorization_id=UUID(int=number), seconds=seconds), permission=True)

    def apply(self, grant, **kwargs):
        f = self.f
        return f.policy.apply(f.request, f.scope, f.authority, grant, permission=True, **kwargs)

    def snapshot(self):
        return self.f.unit.snapshot(), self.f.provider.snapshot()

    def test_both_policies_both_decisions_both_steps_hold_and_preserve_history(self):
        for kind in ('CONTINUE', 'CANCEL'):
            for outcome in ('SUCCESS', 'REJECTED'):
                for prefix in (1, 2):
                    with self.subTest(kind=kind,outcome=outcome,prefix=prefix):
                        f = self.prepare(outcome,prefix)
                        provider = f.provider.snapshot()
                        plan = self.plan(kind)
                        self.assertEqual(plan.expected_state, 'NEXT_STEP_DECISION_RECORDED')
                        self.assertEqual(plan.execution_id, self.command.execution_id)
                        grant = self.issue(kind,plan=plan)
                        self.assertEqual(ExecutorPolicyAuthorization.model_validate_json(grant.model_dump_json()),grant)
                        record = self.apply(grant)
                        self.assertEqual(record.state, 'NEXT_STEP_CONTINUE_HELD' if kind=='CONTINUE' else 'NEXT_STEP_CANCELLED_HELD')
                        self.assertEqual(ExecutorPolicyRecord.model_validate_json(record.model_dump_json()),record)
                        state = f.unit.snapshot()
                        key = next(iter(state['journal']))
                        self.assertEqual(state['journal'][key].state,record.state)
                        self.assertEqual(state['audit'][:-1],self.history['audit'])
                        self.assertEqual(state['outbox'][key][:-1],self.history['outbox'][key])
                        self.assertEqual(state['outbox'][key][-1].status,'HELD')
                        self.assertEqual(state['audit'][-1][6],record.state)
                        self.assertFalse(record.automatic_dispatch)
                        self.assertFalse(record.external_effects_reversed)
                        self.assertEqual(state['execution_records'],self.history['execution_records'])
                        for table in ('executor_accepted','executor_decision_records','executor_decision_authorizations'):
                            self.assertEqual(state[table],self.history[table])
                        for table in ('executor_policy_records','executor_policy_authorizations'):
                            for old_id,value in self.history[table].items():
                                self.assertEqual(state[table][old_id],value)
                        self.assertEqual(state['executor_policy_audit'][:len(self.history['executor_policy_audit'])],self.history['executor_policy_audit'])
                        owner = next(iter(state['owners'].values()))
                        self.assertEqual(owner.authority,'LOCAL')
                        self.assertEqual(owner.active_request,f.request.request_id)
                        self.assertEqual(owner.revision,plan.owner_revision+1)
                        self.assertEqual(owner.fence,plan.owner_fence+1)
                        self.assertEqual(state['leases'][key].token,plan.worker_token+1)
                        self.assertEqual(provider,f.provider.snapshot())
                        before=self.snapshot()
                        with self.assertRaises(AtomicConflict):
                            f.unit.claim(f.request,f.scope,f.worker,Claim(attempt_id=UUID(int=9999)),permission=True)
                        with self.assertRaises(AtomicConflict):
                            f.next.plan(f.request,f.scope,grant.authorization_id,'COMMIT_OWNER_CAS',permission=True)
                        self.assertEqual(before,self.snapshot())

    def test_plan_binding_changes_and_contract_version_rejected(self):
        self.prepare()
        plan=self.plan()
        for changes in ({'tenant_id':'other'},{'subscriber_id':'wrong'},{'execution_id':self.f.command.execution_id},
                        {'previous_plan_hash':'0'*64},{'evidence_fingerprint':'0'*64},
                        {'unknown_receipt_fingerprint':'0'*64},{'owner_revision':999}, {'worker_token':999},
                        {'expected_state':'EXECUTOR_DECISION_RECORDED'}, {'contract_version':'wrong'}):
            before=self.snapshot()
            with self.assertRaises((AtomicConflict,PermissionError)):
                self.issue(plan=plan.model_copy(update=changes))
            self.assertEqual(before,self.snapshot())

    def test_event_attempt_receipt_and_decision_history_tampering_fail_closed(self):
        for kind in ('EVENT','ATTEMPT','RECEIPT','DECISION','VERSION','AUDIT'):
            f=self.prepare()
            record=f.unit._state['executor_decision_records'][self.decision.authorization_id]
            if kind in ('EVENT','ATTEMPT','RECEIPT'):
                field={'EVENT':'event_id','ATTEMPT':'attempt_id','RECEIPT':'receipt_fingerprint'}[kind]
                evaluation=record.evaluation.model_copy(update={field:'0'*64 if kind=='RECEIPT' else UUID(int=9999)})
                f.unit._state['executor_decision_records'][record.authorization_id]=record.model_copy(update={'evaluation':evaluation})
            elif kind=='DECISION':
                del f.unit._state['executor_decision_authorizations'][record.authorization_id]
            elif kind=='VERSION':
                auth=f.unit._state['executor_decision_authorizations'][record.authorization_id]
                f.unit._state['executor_decision_authorizations'][record.authorization_id]=auth.model_copy(update={'version':'wrong'})
            else:
                f.unit._state['executor_decision_audit']=[r for r in f.unit._state['executor_decision_audit'] if r[0]!=record.authorization_id]
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.plan()
            self.assertEqual(before,self.snapshot())

    def test_cas_fencing_provider_drift_does_not_consume_authority(self):
        for table,field in (('owners','revision'),('owners','fence'),('journal','revision'),('leases','token'),('PROVIDER','highest')):
            self.prepare()
            grant=self.issue()
            if table=='PROVIDER':
                self.f.provider._state['highest']=(self.command.owner_fence,self.command.fencing_token+1)
            else:
                key,value=next(iter(self.f.unit._state[table].items()))
                self.f.unit._state[table][key]=value.model_copy(update={field:getattr(value,field)+1})
            before=self.snapshot()
            with self.assertRaises(AtomicConflict): self.apply(grant)
            self.assertEqual(before,self.snapshot())

    def test_five_fault_boundaries_are_atomic_for_both_policy_kinds(self):
        for kind in ('CONTINUE','CANCEL'):
            self.prepare()
            grant=self.issue(kind)
            before=self.snapshot()
            for fault in ('OWNER','JOURNAL','AUDIT','OUTBOX','AUTHORIZATION'):
                with self.assertRaises(AtomicConflict): self.apply(grant,fail_at=fault)
                self.assertEqual(before,self.snapshot())
            self.apply(grant)

    def test_ttl_permissions_scope_and_tampered_grant_reject(self):
        f=self.prepare()
        grant=self.issue(seconds=2)
        for authority in (f.authority.model_copy(update={'can_continue':False}),
                          f.authority.model_copy(update={'tenant_id':'other'}),
                          f.authority.model_copy(update={'actor_id':'other'})):
            before=self.snapshot()
            with self.assertRaises(PermissionError):
                f.policy.apply(f.request,f.scope,authority,grant,permission=True)
            self.assertEqual(before,self.snapshot())
        for changes in ({'version':'wrong'},{'authorization_id':UUID(int=99)}, {'actor_id':'other'}):
            before=self.snapshot()
            with self.assertRaises((AtomicConflict,PermissionError)): self.apply(grant.model_copy(update=changes))
            self.assertEqual(before,self.snapshot())
        f.clock.advance(2)
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.apply(grant)
        self.assertEqual(before,self.snapshot())

    def test_competing_continue_cancel_and_duplicate_have_one_cas_winner(self):
        f=self.prepare()
        grants=[self.issue('CONTINUE',number=9950),self.issue('CANCEL',number=9951)]
        def compete(grant):
            try: self.apply(grant); return 'WIN'
            except AtomicConflict: return 'CONFLICT'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(compete,grants)),['WIN','CONFLICT'])
        before=self.snapshot()
        for grant in grants:
            with self.assertRaises(AtomicConflict): self.apply(grant)
            self.assertEqual(before,self.snapshot())
        self.assertEqual(sum(r[0] in {g.authorization_id for g in grants} and r[3]=='CONSUMED'
                             for r in f.unit._state['executor_policy_audit']),1)

    def test_uncommitted_unknown_and_reused_authority_uuid_rejected(self):
        f=self.prepare()
        before=self.snapshot()
        with self.assertRaises(AtomicConflict):
            f.policy.plan(f.request,f.scope,UUID(int=123),'CONTINUE',permission=True)
        self.assertEqual(before,self.snapshot())
        self.issue()
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.issue()
        self.assertEqual(before,self.snapshot())

    def test_recorded_decision_type_must_match_definitive_evidence(self):
        f=self.prepare()
        key=self.decision.authorization_id
        record=f.unit._state['executor_decision_records'][key]
        grant=f.unit._state['executor_decision_authorizations'][key]
        f.unit._state['executor_decision_records'][key]=record.model_copy(update={'decision':'CONFIRM_REJECTION'})
        f.unit._state['executor_decision_authorizations'][key]=grant.model_copy(update={'decision':'CONFIRM_REJECTION'})
        before=self.snapshot()
        with self.assertRaises(AtomicConflict): self.plan()
        self.assertEqual(before,self.snapshot())
